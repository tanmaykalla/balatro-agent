"""
report_generator.py — Generates a self-contained HTML report for each strategy.

One HTML file per strategy is written to reports/<strategy_name>.html.
All charts are embedded as base64 PNG images — no external files needed.
"""

from __future__ import annotations

import base64
import io
import os
from collections import Counter, defaultdict
from typing import List

import matplotlib
matplotlib.use("Agg")   # no GUI — render to buffer
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from metrics import RunMetrics, HandRecord


# ── Colour palette ─────────────────────────────────────────────────────────────

BLIND_COLOURS = {"small": "#4caf50", "big": "#ff9800", "boss": "#f44336", "": "#9e9e9e"}
HAND_COLOURS  = [
    "#5c6bc0", "#42a5f5", "#26c6da", "#66bb6a",
    "#ffca28", "#ffa726", "#ef5350", "#ab47bc",
]


# ── Helper: render a figure to base64 PNG string ──────────────────────────────

def _fig_to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return encoded


# ── Chart builders ─────────────────────────────────────────────────────────────

def _chart_ante_reached(runs: List[RunMetrics]) -> str:
    """Bar chart — ante reached per run, coloured by win/loss."""
    fig, ax = plt.subplots(figsize=(7, 3.2))
    colours = ["#43a047" if r.won else "#e53935" for r in runs]
    bars = ax.bar([f"Run {r.run_num}" for r in runs],
                  [r.ante_reached_at_game_end for r in runs],
                  color=colours, edgecolor="white", linewidth=0.8)
    ax.set_ylim(0, 9)
    ax.set_yticks(range(0, 10))
    ax.axhline(8, color="#43a047", linestyle="--", linewidth=1.2, label="Win (ante 8)")
    ax.set_ylabel("Ante reached")
    ax.set_title("Ante reached per run")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, r in zip(bars, runs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                "WIN" if r.won else str(r.ante_reached_at_game_end),
                ha="center", va="bottom", fontsize=8, fontweight="bold",
                color="#43a047" if r.won else "#e53935")
    fig.tight_layout()
    return _fig_to_b64(fig)


def _chart_hand_frequency(all_hands: List[HandRecord]) -> str:
    """Horizontal bar chart — how often each hand type was played, split by blind."""
    if not all_hands:
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.text(0.5, 0.5, "No hand data", ha="center", va="center", transform=ax.transAxes)
        return _fig_to_b64(fig)

    counter: Counter = Counter(h.hand_type for h in all_hands)
    hand_types = [k for k, _ in counter.most_common()]
    counts     = [counter[k] for k in hand_types]

    # Breakdown by blind within each hand type
    blind_breakdown: dict = defaultdict(Counter)
    for h in all_hands:
        blind_breakdown[h.hand_type][h.blind] += 1

    fig, ax = plt.subplots(figsize=(7, max(3, len(hand_types) * 0.55 + 1)))
    y = range(len(hand_types))

    blind_order = ["small", "big", "boss", ""]
    lefts = [0] * len(hand_types)
    for blind in blind_order:
        segment = [blind_breakdown[ht][blind] for ht in hand_types]
        if any(s > 0 for s in segment):
            ax.barh(list(y), segment, left=lefts, color=BLIND_COLOURS[blind],
                    label=blind or "unknown", edgecolor="white", linewidth=0.5)
            lefts = [l + s for l, s in zip(lefts, segment)]

    ax.set_yticks(list(y))
    ax.set_yticklabels(hand_types)
    ax.set_xlabel("Times played")
    ax.set_title("Hand type frequency (by blind)")
    ax.legend(title="Blind", fontsize=8, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    for i, (ht, total) in enumerate(zip(hand_types, counts)):
        ax.text(total + 0.2, i, str(total), va="center", fontsize=8)
    fig.tight_layout()
    return _fig_to_b64(fig)


def _chart_score_distribution(all_hands: List[HandRecord]) -> str:
    """Box-and-whisker chart — chips scored per play, grouped by hand type."""
    if not all_hands:
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.text(0.5, 0.5, "No hand data", ha="center", va="center", transform=ax.transAxes)
        return _fig_to_b64(fig)

    by_type: dict = defaultdict(list)
    for h in all_hands:
        if h.chips_scored > 0:
            by_type[h.hand_type].append(h.chips_scored)

    # Sort by median score descending
    sorted_types = sorted(by_type, key=lambda k: float(np.median(by_type[k])), reverse=True)
    data         = [by_type[k] for k in sorted_types]
    colours      = [HAND_COLOURS[i % len(HAND_COLOURS)] for i in range(len(sorted_types))]

    fig, ax = plt.subplots(figsize=(max(6, len(sorted_types) * 1.1 + 2), 4))
    bp = ax.boxplot(data, patch_artist=True, notch=False, vert=True,
                    medianprops=dict(color="white", linewidth=2))
    for patch, colour in zip(bp["boxes"], colours):
        patch.set_facecolor(colour)
        patch.set_alpha(0.85)

    ax.set_xticks(range(1, len(sorted_types) + 1))
    ax.set_xticklabels(sorted_types, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Chips scored")
    ax.set_title("Score distribution by hand type")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.get_major_formatter().set_scientific(False)
    fig.tight_layout()
    return _fig_to_b64(fig)


def _chart_score_over_antes(runs: List[RunMetrics]) -> str:
    """Line chart — cumulative chips scored per ante per run."""
    fig, ax = plt.subplots(figsize=(8, 3.8))
    has_data = False
    for i, run in enumerate(runs):
        if not run.hands:
            continue
        has_data = True
        ante_chips: dict = defaultdict(int)
        for h in run.hands:
            ante_chips[h.ante] += h.chips_scored
        antes  = sorted(ante_chips)
        totals = [ante_chips[a] for a in antes]
        label  = f"Run {run.run_num}" + (" ✓" if run.won else "")
        ax.plot(antes, totals, marker="o", markersize=5, linewidth=1.6,
                label=label, color=HAND_COLOURS[i % len(HAND_COLOURS)])

    if not has_data:
        ax.text(0.5, 0.5, "No hand data", ha="center", va="center", transform=ax.transAxes)
    else:
        ax.set_xlabel("Ante")
        ax.set_ylabel("Total chips scored")
        ax.set_title("Total chips scored per ante (per run)")
        ax.set_xticks(range(1, 9))
        ax.legend(fontsize=8, ncol=2)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _fig_to_b64(fig)


def _chart_joker_usage(all_hands: List[HandRecord]) -> str:
    """Horizontal bar chart — joker appearance count across all plays, top 15."""
    joker_count: Counter = Counter()
    joker_chips: dict    = defaultdict(list)
    for h in all_hands:
        for jk in set(h.joker_keys):   # count each joker once per hand play
            joker_count[jk] += 1
            joker_chips[jk].append(h.chips_scored)

    if not joker_count:
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.text(0.5, 0.5, "No joker data", ha="center", va="center", transform=ax.transAxes)
        return _fig_to_b64(fig)

    top15 = [k for k, _ in joker_count.most_common(15)]
    counts = [joker_count[k] for k in top15]
    avgs   = [int(np.mean(joker_chips[k])) for k in top15]

    fig, ax = plt.subplots(figsize=(8, max(3, len(top15) * 0.55 + 1)))
    y = range(len(top15))
    bars = ax.barh(list(y), counts, color="#5c6bc0", alpha=0.85, edgecolor="white")
    ax.set_yticks(list(y))
    ax.set_yticklabels(top15, fontsize=9)
    ax.set_xlabel("Plays active (hands where joker was held)")
    ax.set_title("Top jokers by plays active")
    ax.spines[["top", "right"]].set_visible(False)
    for i, (bar, avg) in enumerate(zip(bars, avgs)):
        ax.text(bar.get_width() + 0.15, i, f"avg {avg:,} chips", va="center", fontsize=8)
    fig.tight_layout()
    return _fig_to_b64(fig)


# ── Statistics tables ──────────────────────────────────────────────────────────

def _hand_stats_table(all_hands: List[HandRecord]) -> str:
    by_type: dict = defaultdict(list)
    for h in all_hands:
        by_type[h.hand_type].append(h.chips_scored)

    rows = ""
    for ht in sorted(by_type, key=lambda k: -float(np.median(by_type[k]))):
        scores = by_type[ht]
        rows += (
            f"<tr><td>{ht}</td><td>{len(scores)}</td>"
            f"<td>{int(np.mean(scores)):,}</td>"
            f"<td>{int(np.median(scores)):,}</td>"
            f"<td>{max(scores):,}</td>"
            f"<td>{min(scores):,}</td></tr>\n"
        )
    if not rows:
        rows = "<tr><td colspan='6'>No data</td></tr>"
    return f"""
<table>
  <thead><tr>
    <th>Hand type</th><th>Count</th><th>Avg chips</th>
    <th>Median</th><th>Best</th><th>Worst</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _joker_stats_table(all_hands: List[HandRecord]) -> str:
    joker_count: Counter = Counter()
    joker_chips: dict    = defaultdict(list)
    for h in all_hands:
        for jk in set(h.joker_keys):
            joker_count[jk] += 1
            joker_chips[jk].append(h.chips_scored)

    if not joker_count:
        return "<p>No joker data recorded.</p>"

    rows = ""
    for jk, count in joker_count.most_common(20):
        scores = joker_chips[jk]
        rows += (
            f"<tr><td><code>{jk}</code></td><td>{count}</td>"
            f"<td>{int(np.mean(scores)):,}</td>"
            f"<td>{max(scores):,}</td></tr>\n"
        )
    return f"""
<table>
  <thead><tr>
    <th>Joker key</th><th>Plays held</th><th>Avg chips (that play)</th><th>Best chips</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _run_detail_table(runs: List[RunMetrics]) -> str:
    rows = ""
    for r in runs:
        hand_counts = Counter(h.hand_type for h in r.hands)
        top_hands = ", ".join(f"{ht}×{cnt}" for ht, cnt in hand_counts.most_common(3))
        rows += (
            f"<tr>"
            f"<td>{r.run_num}</td>"
            f"<td>{r.ante_reached_at_game_end}</td>"
            f"<td class=\"{'won' if r.won else 'lost'}\">"
            f"{'WIN' if r.won else 'loss'}</td>"
            f"<td>${r.total_dollars_earned:,}</td>"
            f"<td>{len(r.hands)}</td>"
            f"<td>{top_hands or '—'}</td>"
            f"</tr>\n"
        )
    return f"""
<table>
  <thead><tr>
    <th>Run</th><th>Ante</th><th>Result</th>
    <th>Dollars</th><th>Hands played</th><th>Top hands (this run)</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _score_table(all_hands: List[HandRecord]) -> str:
    """Full per-hand log table."""
    if not all_hands:
        return "<p>No hand records.</p>"

    rows = ""
    for h in all_hands:
        joker_str = ", ".join(f"<code>{jk}</code>" for jk in h.joker_keys) or "—"
        rows += (
            f"<tr>"
            f"<td>Run {h.run_num}</td>"
            f"<td>{h.ante}</td>"
            f"<td style='color:{BLIND_COLOURS.get(h.blind, '#000')}'>{h.blind}</td>"
            f"<td><strong>{h.hand_type}</strong></td>"
            f"<td>{h.chips_scored:,}</td>"
            f"<td style='font-size:0.8em'>{joker_str}</td>"
            f"</tr>\n"
        )
    return f"""
<details>
<summary><strong>All {len(all_hands)} hand records (click to expand)</strong></summary>
<div style="overflow-x:auto">
<table>
  <thead><tr>
    <th>Run</th><th>Ante</th><th>Blind</th><th>Hand type</th>
    <th>Chips scored</th><th>Jokers active</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</div>
</details>"""


# ── HTML skeleton ─────────────────────────────────────────────────────────────

_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem;
       background: #fafafa; color: #212121; }
h1   { color: #1a237e; border-bottom: 3px solid #3949ab; padding-bottom: .4rem; }
h2   { color: #283593; margin-top: 2rem; }
h3   { color: #3949ab; margin-top: 1.5rem; }
.stat-grid { display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1rem 0 2rem; }
.stat-card { background: #fff; border: 1px solid #c5cae9;
             border-radius: 8px; padding: 1rem 1.5rem; min-width: 120px;
             box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.stat-card .value { font-size: 2rem; font-weight: 700; color: #1a237e; }
.stat-card .label { font-size: .8rem; color: #757575; margin-top: .2rem; }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr;
              gap: 1.5rem; margin: 1.5rem 0; }
.chart-grid img { width: 100%; border-radius: 6px;
                  border: 1px solid #e0e0e0; background: #fff; }
table { border-collapse: collapse; width: 100%; background: #fff;
        border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08);
        margin: .5rem 0 1.5rem; }
th    { background: #3949ab; color: #fff; padding: .55rem .9rem;
        text-align: left; font-weight: 600; font-size: .85rem; }
td    { padding: .48rem .9rem; font-size: .88rem; border-bottom: 1px solid #e8eaf6; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #e8eaf6; }
.won  { color: #43a047; font-weight: 700; }
.lost { color: #e53935; font-weight: 700; }
code  { background: #e8eaf6; border-radius: 3px; padding: .1rem .3rem;
        font-size: .82em; color: #283593; }
details { margin: 1rem 0; }
summary { cursor: pointer; padding: .5rem; background: #e8eaf6;
          border-radius: 4px; font-size: .9rem; }
@media (max-width: 700px) { .chart-grid { grid-template-columns: 1fr; } }
"""


def generate_report(
    strategy_name: str,
    runs: List[RunMetrics],
    reports_dir: str = "reports",
) -> str:
    """
    Generate a self-contained HTML report for a strategy.
    Returns the path to the written file.
    """
    os.makedirs(reports_dir, exist_ok=True)
    all_hands = [h for r in runs for h in r.hands]

    # ── Summary stats ─────────────────────────────────────────────────────────
    n_runs      = len(runs)
    wins        = sum(1 for r in runs if r.won)
    avg_ante    = sum(r.ante_reached_at_game_end for r in runs) / n_runs
    max_ante    = max(r.ante_reached_at_game_end for r in runs)
    avg_dollars = sum(r.total_dollars_earned for r in runs) / n_runs
    total_hands = len(all_hands)
    most_common_hand = (
        Counter(h.hand_type for h in all_hands).most_common(1)[0][0]
        if all_hands else "—"
    )
    avg_chips = int(np.mean([h.chips_scored for h in all_hands])) if all_hands else 0

    # ── Charts ────────────────────────────────────────────────────────────────
    c_ante   = _chart_ante_reached(runs)
    c_freq   = _chart_hand_frequency(all_hands)
    c_dist   = _chart_score_distribution(all_hands)
    c_antes  = _chart_score_over_antes(runs)
    c_joker  = _chart_joker_usage(all_hands)

    # ── Tables ────────────────────────────────────────────────────────────────
    t_runs   = _run_detail_table(runs)
    t_hands  = _hand_stats_table(all_hands)
    t_jokers = _joker_stats_table(all_hands)
    t_log    = _score_table(all_hands)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Balatro Agent — {strategy_name}</title>
  <style>{_CSS}</style>
</head>
<body>

<h1>Strategy: {strategy_name}</h1>

<div class="stat-grid">
  <div class="stat-card"><div class="value">{wins}/{n_runs}</div><div class="label">Wins</div></div>
  <div class="stat-card"><div class="value">{avg_ante:.1f}</div><div class="label">Avg ante reached</div></div>
  <div class="stat-card"><div class="value">{max_ante}</div><div class="label">Best ante</div></div>
  <div class="stat-card"><div class="value">${avg_dollars:.0f}</div><div class="label">Avg dollars earned</div></div>
  <div class="stat-card"><div class="value">{total_hands}</div><div class="label">Total hands played</div></div>
  <div class="stat-card"><div class="value">{avg_chips:,}</div><div class="label">Avg chips / hand</div></div>
  <div class="stat-card"><div class="value">{most_common_hand}</div><div class="label">Most played hand</div></div>
</div>

<h2>Run results</h2>
{t_runs}

<h2>Charts</h2>
<div class="chart-grid">
  <img src="data:image/png;base64,{c_ante}"  alt="Ante reached per run"/>
  <img src="data:image/png;base64,{c_freq}"  alt="Hand type frequency"/>
  <img src="data:image/png;base64,{c_dist}"  alt="Score distribution by hand type"/>
  <img src="data:image/png;base64,{c_antes}" alt="Chips scored per ante"/>
</div>

<h2>Hand type statistics</h2>
{t_hands}

<h2>Joker usage</h2>
<div class="chart-grid" style="grid-template-columns:1fr">
  <img src="data:image/png;base64,{c_joker}" alt="Joker usage"/>
</div>
{t_jokers}

<h2>Detailed hand log</h2>
{t_log}

</body>
</html>"""

    safe_name = strategy_name.replace(" ", "_").replace("/", "-")
    out_path  = os.path.join(reports_dir, f"{safe_name}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
