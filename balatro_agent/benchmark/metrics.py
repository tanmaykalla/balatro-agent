"""
Benchmark metrics extraction.
Reads per-run JSONs from a results dir + meta.json, computes:
  - Skill axis: progress, peak chip efficiency, weak blind rate
  - Efficiency axis: tokens/decision, p50 latency
  - Reliability axis: api errors, timeouts, nudges, consistency
Returns normalised 0-100 scores per agent and a composite.
"""
from __future__ import annotations
import glob
import json
import os
import statistics as stats
from collections import Counter, defaultdict


# Pricing for cost estimates ($/M tokens, input/output)
COST_PER_M_TOKENS = {
    "gemini-2.5-flash": (0.10, 0.40),
}
# Char-to-token approximation
CHARS_PER_TOKEN = 3.5


def _chars_to_tokens(chars: int) -> int:
    return int(chars / CHARS_PER_TOKEN)


def _estimate_cost(model: str, in_chars: int, out_chars: int) -> float:
    in_tok  = _chars_to_tokens(in_chars)  / 1_000_000
    out_tok = _chars_to_tokens(out_chars) / 1_000_000
    pricing = COST_PER_M_TOKENS.get(model, (0.0, 0.0))
    return in_tok * pricing[0] + out_tok * pricing[1]


# ── per-run extraction ────────────────────────────────────────────────────────

_PROMPT_TARGET_RE  = None
_PROMPT_SCORED_RE  = None

def _re():
    global _PROMPT_TARGET_RE, _PROMPT_SCORED_RE
    if _PROMPT_TARGET_RE is None:
        import re
        _PROMPT_TARGET_RE = re.compile(r"Blind target:\s*(\d+)")
        _PROMPT_SCORED_RE = re.compile(r"Chips scored so far:\s*(\d+)")
    return _PROMPT_TARGET_RE, _PROMPT_SCORED_RE


def _derive_blinds_from_actions(actions: list[dict]) -> list[dict]:
    """When blind_history is missing (scripted-bot logs), reconstruct from action prompts."""
    rx_t, rx_s = _re()
    # Group actions by (ante, round) and find target + max scored
    grouped: dict[tuple, dict] = {}
    for a in actions:
        key = (a.get("ante"), a.get("round"))
        prompt = a.get("prompt", "") or ""
        mt = rx_t.search(prompt)
        ms = rx_s.search(prompt)
        if not mt:
            continue
        target = int(mt.group(1))
        scored = int(ms.group(1)) if ms else 0
        g = grouped.setdefault(key, {"target": target, "max_scored": 0,
                                     "play_count": 0, "ante": a.get("ante")})
        g["max_scored"] = max(g["max_scored"], scored)
        if a.get("action") == "play_hand":
            g["play_count"] += 1
    blinds = []
    for key, g in sorted(grouped.items(), key=lambda kv: kv[0] or (0, 0)):
        hands_used = max(1, g["play_count"])
        blinds.append({
            "ante": g["ante"], "target_score": g["target"],
            "achieved_score": g["max_scored"],
            "hands_left_at_finish": max(0, 4 - hands_used),
        })
    return blinds


def extract_run_metrics(run_json_path: str) -> dict:
    """Pull all metrics from a single run JSON."""
    with open(run_json_path) as f:
        d = json.load(f)

    actions     = d.get("action_log",     []) or []
    blinds      = d.get("blind_history",  []) or []
    hands       = d.get("hand_history",   []) or []
    jokers      = d.get("joker_history",  []) or []
    stats_blob  = d.get("agent_stats",    {}) or {}

    # Derive blinds from action prompts if not present (scripted bot)
    if not blinds and actions:
        blinds = _derive_blinds_from_actions(actions)
    # Derive final_ante from actions if not stored
    final_ante  = int(d.get("final_ante", 0) or 0)
    if not final_ante and actions:
        final_ante = max((a.get("ante", 0) or 0) for a in actions)
    won         = bool(d.get("won", False))

    # ── Progress: continuous score ────────────────────────────────────────
    # final_ante + (rounds completed in current ante / 3)
    last_round = d.get("round_num", 0) or 0
    # Each ante has 3 blinds; estimate fractional progress
    rounds_in_ante = 0
    for b in blinds:
        if b.get("ante") == final_ante:
            rounds_in_ante += 1
    progress_score = final_ante + min(rounds_in_ante, 3) / 3.0

    # ── Pace metrics per blind ────────────────────────────────────────────
    blind_records = []
    for b in blinds:
        target = b.get("target_score") or 0
        ach    = b.get("achieved_score") or 0
        hands_left_finish = b.get("hands_left_at_finish") or 0
        if target <= 0:
            continue
        # Balatro: 4 hands per blind default — use hands_left_at_finish + assume max
        # Conservative: hands_used = 4 - hands_left_at_finish (clamp)
        hands_total = 4
        hands_used  = max(1, hands_total - hands_left_finish)
        passed      = ach >= target
        # Pace = (achieved / target) × (hands_total / hands_used)
        # Crushed it fast → high. Scraped by → near 1. Failed → < 1.
        pace = (ach / target) * (hands_total / hands_used)
        # Weak: passed but inefficient (pace < 0.5 means scored well below quota)
        # Failed: didn't pass at all
        weak = passed and pace < 1.0    # passed but used many hands for low ratio
        blind_records.append({
            "target": target, "achieved": ach, "passed": passed,
            "hands_used": hands_used, "pace": pace, "weak": weak,
        })

    if blind_records:
        # Refinement 1: only count "clearing-phase" blinds (passed) for weak rate
        passed_records = [b for b in blind_records if b["passed"]]
        weak_blind_rate = (sum(1 for b in passed_records if b["weak"])
                           / max(1, len(passed_records)))
        peak_efficiency = max(b["achieved"] / b["target"] for b in blind_records)
        median_pace     = stats.median(b["pace"] for b in blind_records)
    else:
        weak_blind_rate = 0.0
        peak_efficiency = 0.0
        median_pace     = 0.0

    # ── Decisions / latency / tokens ──────────────────────────────────────
    latencies = stats_blob.get("call_latencies", []) or []
    decision_count = len(latencies) or sum(1 for a in actions if "error" not in a)

    if latencies:
        p50 = stats.median(latencies)
        p95 = sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)]
    else:
        p50 = p95 = 0.0

    in_chars  = stats_blob.get("input_chars",  0)
    out_chars = stats_blob.get("output_chars", 0)
    in_tokens  = _chars_to_tokens(in_chars)
    out_tokens = _chars_to_tokens(out_chars)
    tokens_per_decision = ((in_tokens + out_tokens) / decision_count) if decision_count else 0
    model = stats_blob.get("model") or d.get("source", "")
    cost = _estimate_cost(model or "", in_chars, out_chars)

    # ── Reliability ───────────────────────────────────────────────────────
    api_errors    = stats_blob.get("api_errors", 0)
    nudge_retries = stats_blob.get("nudge_retries", 0)
    error_actions = sum(1 for a in actions if a.get("action") == "_api_error")
    balatrobot_errors = sum(1 for a in actions if "error" in a)
    total_decisions = decision_count or 1
    failure_rate = (api_errors + balatrobot_errors) / total_decisions

    # ── Action mix ─────────────────────────────────────────────────────────
    action_counts = Counter(a.get("action", "?") for a in actions if "error" not in a)
    hand_phase = [a for a in actions if a.get("phase") == "SELECTING_HAND"]
    plays    = sum(1 for a in hand_phase if a.get("action") == "play_hand")
    discards = sum(1 for a in hand_phase if a.get("action") == "discard_cards")
    discard_rate = discards / (plays + discards) if (plays + discards) else 0
    jokers_bought = sum(1 for j in jokers if j.get("action") == "buy")
    jokers_sold   = sum(1 for j in jokers if j.get("action") == "sell")

    return {
        "run_id":           d.get("run_id"),
        "won":              won,
        "final_ante":       final_ante,
        "progress_score":   progress_score,
        "peak_efficiency":  peak_efficiency,
        "weak_blind_rate":  weak_blind_rate,
        "median_pace":      median_pace,
        "decisions":        decision_count,
        "p50_latency":      p50,
        "p95_latency":      p95,
        "in_tokens":        in_tokens,
        "out_tokens":       out_tokens,
        "tokens_per_decision": tokens_per_decision,
        "estimated_cost":   cost,
        "api_errors":       api_errors,
        "nudge_retries":    nudge_retries,
        "balatrobot_errors": balatrobot_errors,
        "failure_rate":     failure_rate,
        "discard_rate":     discard_rate,
        "jokers_bought":    jokers_bought,
        "jokers_sold":      jokers_sold,
        "action_counts":    dict(action_counts),
    }


def _normalise(values: list[float], higher_better: bool = True) -> list[float]:
    """Normalise to 0-100 across the list."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [50.0] * len(values)
    if higher_better:
        return [100 * (v - lo) / (hi - lo) for v in values]
    else:
        return [100 * (hi - v) / (hi - lo) for v in values]


def aggregate_agents(results_dir: str) -> dict:
    """For each agent, average per-run metrics + compute composite score."""
    with open(os.path.join(results_dir, "meta.json")) as f:
        meta = json.load(f)

    by_agent: dict[str, list[dict]] = defaultdict(list)
    for r in meta["results"]:
        path = r.get("run_json")
        if not path or not os.path.exists(path):
            # Failed run — give worst-case placeholder
            by_agent[r["agent"]].append({"missing": True, "timeout": r.get("timeout")})
            continue
        try:
            m = extract_run_metrics(path)
            by_agent[r["agent"]].append(m)
        except Exception as e:
            print(f"  [warn] failed to parse {path}: {e}")
            by_agent[r["agent"]].append({"missing": True, "error": str(e)})

    # Per-agent aggregation
    agg = {}
    for agent, runs in by_agent.items():
        valid = [r for r in runs if not r.get("missing")]
        if not valid:
            agg[agent] = {"valid_runs": 0}
            continue
        def _m(field): return stats.mean(r[field] for r in valid)
        def _std(field):
            if len(valid) < 2: return 0.0
            return stats.stdev(r[field] for r in valid)
        agg[agent] = {
            "valid_runs":       len(valid),
            "total_runs":       len(runs),
            "missing_runs":     len(runs) - len(valid),
            "timeouts":         sum(1 for r in runs if r.get("timeout")),
            # Skill
            "mean_progress":    _m("progress_score"),
            "max_ante":         max(r["final_ante"] for r in valid),
            "wins":             sum(1 for r in valid if r["won"]),
            "peak_efficiency":  _m("peak_efficiency"),
            "weak_blind_rate":  _m("weak_blind_rate"),
            "median_pace":      _m("median_pace"),
            "progress_std":     _std("progress_score"),
            # Efficiency
            "p50_latency":      _m("p50_latency"),
            "p95_latency":      _m("p95_latency"),
            "tokens_per_decision": _m("tokens_per_decision"),
            "total_in_tokens":  sum(r["in_tokens"] for r in valid),
            "total_out_tokens": sum(r["out_tokens"] for r in valid),
            "mean_cost":        _m("estimated_cost"),
            # Reliability
            "api_errors":       sum(r["api_errors"] for r in valid),
            "nudge_retries":    sum(r["nudge_retries"] for r in valid),
            "failure_rate":     _m("failure_rate"),
            # Action mix
            "discard_rate":     _m("discard_rate"),
            "mean_jokers_bought": _m("jokers_bought"),
        }

    # Compute composite scores (normalised across agents)
    labels = list(agg.keys())
    def _col(field, default=0.0):
        return [agg[l].get(field, default) for l in labels]

    # Skill = 0.5*progress + 0.25*peak_eff + 0.25*(1 - weak_blind_rate)
    norm_progress = _normalise(_col("mean_progress"), higher_better=True)
    norm_peak     = _normalise(_col("peak_efficiency"), higher_better=True)
    norm_weak     = _normalise(_col("weak_blind_rate"), higher_better=False)
    skill = [0.5 * p + 0.25 * pk + 0.25 * w
             for p, pk, w in zip(norm_progress, norm_peak, norm_weak)]

    # Efficiency = 0.5*(low latency) + 0.5*(low tokens/decision)
    norm_lat = _normalise(_col("p50_latency"), higher_better=False)
    norm_tok = _normalise(_col("tokens_per_decision"), higher_better=False)
    efficiency = [0.5 * l + 0.5 * t for l, t in zip(norm_lat, norm_tok)]

    # Reliability = 0.6*(low failure rate) + 0.4*(low std)
    norm_fail = _normalise(_col("failure_rate"), higher_better=False)
    norm_std  = _normalise(_col("progress_std"), higher_better=False)
    reliability = [0.6 * f + 0.4 * s for f, s in zip(norm_fail, norm_std)]

    composite = [0.5 * s + 0.25 * e + 0.25 * r
                 for s, e, r in zip(skill, efficiency, reliability)]

    for i, l in enumerate(labels):
        agg[l]["score_skill"]       = round(skill[i], 1)
        agg[l]["score_efficiency"]  = round(efficiency[i], 1)
        agg[l]["score_reliability"] = round(reliability[i], 1)
        agg[l]["score_composite"]   = round(composite[i], 1)

    return {"by_agent": agg, "labels": labels}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 -m benchmark.metrics <results_dir>")
        sys.exit(1)
    agg = aggregate_agents(sys.argv[1])
    print(json.dumps(agg, indent=2))
