"""
Benchmark report generator.
Reads aggregated metrics + emits a markdown leaderboard.

Usage:
    python3 -m benchmark.report <results_dir>
"""
from __future__ import annotations
import json
import os
import sys

from benchmark.metrics import aggregate_agents


def _row(agent: str, a: dict) -> str:
    return (f"| {agent} | {a.get('mean_progress',0):.2f} | {a.get('max_ante',0)} | "
            f"{a.get('peak_efficiency',0):.2f}× | {a.get('weak_blind_rate',0):.0%} | "
            f"{a.get('p50_latency',0):.1f}s | {a.get('tokens_per_decision',0):.0f} | "
            f"${a.get('mean_cost',0):.4f} | {a.get('failure_rate',0):.0%} | "
            f"**{a.get('score_composite',0):.1f}** |")


def write_report(results_dir: str) -> str:
    agg = aggregate_agents(results_dir)
    by_agent = agg["by_agent"]
    # Sort by composite score descending
    ranked = sorted(by_agent.items(), key=lambda x: -x[1].get("score_composite", 0))

    lines: list[str] = []
    lines.append("# Balatro Agent Benchmark")
    lines.append("")
    meta_path = os.path.join(results_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        lines.append(f"- **Run timestamp**: {meta.get('timestamp')}")
        lines.append(f"- **Strategy (LLM agents)**: {meta.get('strategy')}")
        lines.append(f"- **Runs per agent**: {meta.get('runs_per_agent')}")
        lines.append(f"- **Wall-clock cap**: {meta.get('timeout_sec')}s")
    lines.append("")
    lines.append("## Leaderboard")
    lines.append("")
    lines.append("| Agent | Progress | Max Ante | Peak Eff | Weak Blinds | p50 lat | Toks/dec | Cost/run | Fail% | **Score** |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label, a in ranked:
        if a.get("valid_runs", 0) == 0:
            lines.append(f"| {label} | — | — | — | — | — | — | — | — | **0 (no runs)** |")
        else:
            lines.append(_row(label, a))
    lines.append("")

    lines.append("## Sub-Score Breakdown")
    lines.append("")
    lines.append("| Agent | 🎯 Skill | ⚡ Efficiency | 🛡️ Reliability | **Composite** |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, a in ranked:
        lines.append(f"| {label} | {a.get('score_skill',0):.1f} | "
                     f"{a.get('score_efficiency',0):.1f} | "
                     f"{a.get('score_reliability',0):.1f} | "
                     f"**{a.get('score_composite',0):.1f}** |")
    lines.append("")

    lines.append("## Detailed Stats")
    lines.append("")
    for label, a in ranked:
        lines.append(f"### {label}")
        if a.get("valid_runs", 0) == 0:
            lines.append(f"- No valid runs ({a.get('total_runs', 0)} attempted, {a.get('timeouts',0)} timeouts)")
            lines.append("")
            continue
        lines.append(f"- Runs: {a.get('valid_runs')}/{a.get('total_runs')}  "
                     f"(timeouts: {a.get('timeouts',0)}, missing: {a.get('missing_runs',0)})")
        lines.append(f"- **Skill**: progress {a.get('mean_progress',0):.2f} (±{a.get('progress_std',0):.2f}), "
                     f"max ante {a.get('max_ante',0)}, wins {a.get('wins',0)}")
        lines.append(f"- **Pace**: peak efficiency {a.get('peak_efficiency',0):.2f}×, "
                     f"median pace {a.get('median_pace',0):.2f}, "
                     f"weak blind rate {a.get('weak_blind_rate',0):.1%}")
        lines.append(f"- **Latency**: p50 {a.get('p50_latency',0):.1f}s, "
                     f"p95 {a.get('p95_latency',0):.1f}s")
        lines.append(f"- **Tokens**: {a.get('tokens_per_decision',0):.0f}/decision "
                     f"(in {a.get('total_in_tokens',0):,} / out {a.get('total_out_tokens',0):,} total)")
        lines.append(f"- **Cost**: ~${a.get('mean_cost',0):.4f}/run")
        lines.append(f"- **Reliability**: {a.get('api_errors',0)} API errors, "
                     f"{a.get('nudge_retries',0)} nudge-retries, "
                     f"failure rate {a.get('failure_rate',0):.1%}")
        lines.append(f"- **Action mix**: discard rate {a.get('discard_rate',0):.1%}, "
                     f"jokers bought (avg/run) {a.get('mean_jokers_bought',0):.1f}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("### Scoring formula")
    lines.append("")
    lines.append("- **Skill** (50%): 50% progress + 25% peak chip efficiency + 25% inverse weak-blind-rate")
    lines.append("- **Efficiency** (25%): 50% inverse p50 latency + 50% inverse tokens/decision")
    lines.append("- **Reliability** (25%): 60% inverse failure rate + 40% inverse run-to-run progress std")
    lines.append("- Each axis is min-max normalised to 0–100 across the roster, then weighted-summed.")
    lines.append("")
    lines.append("### Notes")
    lines.append("")
    lines.append("- Pace metrics assume 4 hands per blind. \"Weak blind\" = passed but used most hands.")
    lines.append("- Scripted-bot latency, tokens, cost are zero (Python rule eval, no LLM).")
    lines.append("- Cost is estimated from char→token at 3.5 chars/token + listed model pricing.")

    out_path = os.path.join(results_dir, "report.md")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    return out_path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 -m benchmark.report <results_dir>")
        return 1
    path = write_report(sys.argv[1])
    print(f"Wrote: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
