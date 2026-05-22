"""
prep_dataset.py
===============
Merges all quality Gemini run JSONs + manual_run_01.jsonl into a single
fine-tuning JSONL.

Filters applied:
  - Gemini runs: only include if final_ante >= 2
  - Phases kept: SELECTING_HAND, BLIND_SELECT, SHOP, SMODS_BOOSTER_OPENED
  - Drop actions: _api_error
  - Drop entries where reasoning is empty / fallback / api_error
  - Drop entries with empty prompts

Output: runs/training_data.jsonl
"""
from __future__ import annotations
import json
import glob
import os
from collections import Counter

# ── config ────────────────────────────────────────────────────────────────────

RUNS_DIR      = "runs"
MANUAL_FILE   = "runs/manual_run_01.jsonl"
OUTPUT_FILE   = "runs/training_data.jsonl"
MIN_ANTE      = 2          # minimum final_ante to include a Gemini run

KEEP_PHASES   = {"SELECTING_HAND", "BLIND_SELECT", "SHOP", "SMODS_BOOSTER_OPENED"}
DROP_ACTIONS  = {"_api_error"}

BAD_REASONING = {"", "fallback", "(no reasoning provided)", "api_error"}


def _reasoning(entry: dict) -> str:
    r = entry.get("params", {}).get("reasoning", "") or ""
    return str(r).strip()


def _is_good(entry: dict) -> bool:
    if entry.get("phase") not in KEEP_PHASES:
        return False
    if entry.get("action") in DROP_ACTIONS:
        return False
    if not entry.get("prompt", "").strip():
        return False
    r = _reasoning(entry)
    if not r:
        return False
    r_lower = r.lower()
    if r_lower.startswith("fallback") or r_lower.startswith("api_error"):
        return False
    return True


def _normalise(entry: dict, source: str) -> dict:
    """Return a clean entry in the unified format."""
    return {
        "ante":   entry.get("ante"),
        "round":  entry.get("round"),
        "phase":  entry.get("phase"),
        "action": entry.get("action"),
        "params": {
            k: v for k, v in entry.get("params", {}).items()
        },
        "source": source,
        "prompt": entry.get("prompt", ""),
    }


# ── load manual run ────────────────────────────────────────────────────────────

manual_entries: list[dict] = []
with open(MANUAL_FILE) as f:
    for line in f:
        if line.strip():
            e = json.loads(line)
            if _is_good(e):
                manual_entries.append(_normalise(e, "human"))

print(f"Manual run  : {len(manual_entries)} entries (after filter)")

# ── load gemini runs ───────────────────────────────────────────────────────────

gemini_entries: list[dict] = []
skipped_runs  = 0
included_runs = 0

early_died = 0
for path in sorted(glob.glob(os.path.join(RUNS_DIR, "*.json"))):
    data = json.load(open(path))
    final_ante = data.get("final_ante", 0) or 0
    source = data.get("source", "gemini")

    # Drop ollama runs entirely
    if source == "ollama":
        skipped_runs += 1
        continue

    if final_ante < MIN_ANTE:
        skipped_runs += 1
        early_died += 1
        continue

    log = data.get("action_log", [])
    good = [_normalise(e, source) for e in log if _is_good(e)]
    if good:
        included_runs += 1
        gemini_entries.extend(good)

print(f"  → died at ante 1 (dropped): {early_died}")

print(f"Gemini runs : {included_runs} runs included, {skipped_runs} skipped (ante < {MIN_ANTE})")
print(f"Gemini entries: {len(gemini_entries)} (after filter)")

# ── merge & write ──────────────────────────────────────────────────────────────

all_entries = manual_entries + gemini_entries

with open(OUTPUT_FILE, "w") as f:
    for entry in all_entries:
        f.write(json.dumps(entry) + "\n")

# ── report ────────────────────────────────────────────────────────────────────

action_counts = Counter(e["action"] for e in all_entries)
source_counts = Counter(e["source"] for e in all_entries)
phase_counts  = Counter(e["phase"]  for e in all_entries)

print(f"\n{'='*50}")
print(f"Output: {OUTPUT_FILE}")
print(f"Total examples: {len(all_entries)}")
print(f"\nBy source:")
for s, n in source_counts.most_common():
    print(f"  {s:12s} {n:4d}  ({n/len(all_entries)*100:.1f}%)")
print(f"\nBy action:")
for a, n in action_counts.most_common():
    print(f"  {a:25s} {n:4d}  ({n/len(all_entries)*100:.1f}%)")
print(f"\nBy phase:")
for p, n in phase_counts.most_common():
    print(f"  {p:25s} {n:4d}  ({n/len(all_entries)*100:.1f}%)")

# Check reasoning completeness
missing_r = sum(1 for e in all_entries if not _reasoning(e))
print(f"\nMissing reasoning: {missing_r}/{len(all_entries)}")

# ── discard stats ──────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print("Discard usage stats (SELECTING_HAND entries only):")

hand_entries = [e for e in all_entries if e["phase"] == "SELECTING_HAND"]
plays   = [e for e in hand_entries if e["action"] == "play_hand"]
discards = [e for e in hand_entries if e["action"] == "discard_cards"]

print(f"  play_hand     : {len(plays):4d}  ({len(plays)/len(hand_entries)*100:.1f}%)")
print(f"  discard_cards : {len(discards):4d}  ({len(discards)/len(hand_entries)*100:.1f}%)")
print(f"  total         : {len(hand_entries):4d}")

print(f"\nBy source (SELECTING_HAND only):")
for src in ("human", "gemini"):
    src_hand = [e for e in hand_entries if e["source"] == src]
    src_disc = [e for e in src_hand if e["action"] == "discard_cards"]
    if src_hand:
        print(f"  {src:8s}  plays={len(src_hand)-len(src_disc):3d}  discards={len(src_disc):3d}  "
              f"discard_rate={len(src_disc)/len(src_hand)*100:.1f}%")
