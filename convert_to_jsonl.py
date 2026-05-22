"""
convert_to_jsonl.py — converts all run JSON logs into JSONL for MLX-LM LoRA fine-tuning.

Reads from:
  - week1-prototype/finetune_logs/*.json   (strategy + manual runs)
  - balatro_agent/runs/*.json              (gemini runs)

Outputs:
  - finetune_data/train.jsonl
  - finetune_data/valid.jsonl

Format per line (Qwen3 chat + tool-call):
  {"messages": [
    {"role": "system",    "content": "<game rules + strategy>"},
    {"role": "user",      "content": "<game state prompt>"},
    {"role": "assistant", "content": "<tool_call>\\n{...}\\n</tool_call>"}
  ]}

Run:
  python3 convert_to_jsonl.py
"""

import json
import glob
import random
import os

# ── Config ────────────────────────────────────────────────────────────────────

SOURCES = [
    "week1-prototype/finetune_logs/*.json",
    "balatro_agent/runs/*.json",
]

# Individual JSONL files (flat list of entries, not full run JSONs)
JSONL_SOURCES = [
    ("balatro_agent/runs/manual_run_01.jsonl", "human"),
]
OUT_DIR       = "finetune_data/"
TRAIN_SPLIT   = 0.9        # 90% train, 10% valid
SEED          = 42

# Actions to skip — automatic/non-decisions
SKIP_ACTIONS  = {"cash_out", "_api_error"}

# Minimum prompt length — very short prompts are malformed
MIN_PROMPT_LEN = 50

# Quality filters matching prep_dataset.py
MIN_ANTE      = 2          # drop runs that died at ante 1
SKIP_SOURCES  = {"ollama"} # ollama runs are low quality
BAD_REASONING = {"", "fallback", "(no reasoning provided)", "api_error"}
KEEP_PHASES   = {"SELECTING_HAND", "BLIND_SELECT", "SHOP", "SMODS_BOOSTER_OPENED"}

# Default system prompt for runs that don't have one saved
DEFAULT_SYSTEM_PROMPT = """You are an expert Balatro player making decisions in a live game.
Read the game state carefully and call the appropriate tool to take your action.
Always fill in the reasoning field explaining your decision."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def format_tool_call(action: str, params: dict) -> str:
    """Format action as a Qwen3-style <tool_call> block."""
    # arguments = params minus reasoning (reasoning goes in separately)
    arguments = {k: v for k, v in params.items()}
    payload = {"name": action, "arguments": arguments}
    return f"<tool_call>\n{json.dumps(payload, ensure_ascii=False)}\n</tool_call>"


def entry_to_example(entry: dict, system_prompt: str):
    """Convert one action_log entry to a training example, or None if invalid."""
    action  = entry.get("action", "")
    prompt  = entry.get("prompt", "")
    params  = entry.get("params", {})

    # Filter bad entries
    if action in SKIP_ACTIONS:
        return None
    if not prompt or len(prompt) < MIN_PROMPT_LEN:
        return None
    if not action:
        return None
    if "error" in entry:
        return None
    # Only keep meaningful game phases
    if entry.get("phase") not in KEEP_PHASES:
        return None
    # Skip fallback/api_error reasoning
    reasoning = str(params.get("reasoning", "") or "").strip()
    r_lower = reasoning.lower()
    if not reasoning or r_lower in BAD_REASONING:
        return None
    if r_lower.startswith("fallback") or r_lower.startswith("api_error"):
        return None
    # Skip fallback entries (LLM failed to produce a real tool call)
    if entry.get("fallback_reason"):
        return None

    tool_call_str = format_tool_call(action, params)

    return {
        "messages": [
            {"role": "system",    "content": system_prompt},
            {"role": "user",      "content": prompt},
            {"role": "assistant", "content": tool_call_str},
        ]
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    examples = []
    stats = {}

    for pattern in SOURCES:
        files = glob.glob(os.path.join(base, pattern))
        for f in files:
            try:
                d = json.load(open(f))
            except Exception as e:
                print(f"  [skip] {f}: {e}")
                continue

            source     = d.get("source", "unknown")
            final_ante = d.get("final_ante", 0) or 0

            # Drop ollama runs entirely
            if source in SKIP_SOURCES:
                print(f"  [skip] {os.path.basename(f)} — ollama source")
                continue

            # Drop runs that died at ante 1
            if final_ante < MIN_ANTE:
                print(f"  [skip] {os.path.basename(f)} — died at ante {final_ante}")
                continue

            # Skip runs with fewer than 5 real entries (crashes/aborts)
            action_log = d.get("action_log", [])
            real_entries = [e for e in action_log if "error" not in e]
            if len(real_entries) < 5:
                print(f"  [skip] {os.path.basename(f)} — only {len(real_entries)} entries")
                continue

            system_prompt = d.get("system_prompt") or DEFAULT_SYSTEM_PROMPT

            run_examples = 0
            for entry in action_log:
                ex = entry_to_example(entry, system_prompt)
                if ex:
                    ex["_source"] = source   # tag for stats (stripped before writing)
                    examples.append(ex)
                    run_examples += 1

            stats[source] = stats.get(source, 0) + run_examples

    # ── Load flat JSONL sources (manual runs) ─────────────────────────────────
    for jsonl_path, source in JSONL_SOURCES:
        full_path = os.path.join(base, jsonl_path)
        if not os.path.exists(full_path):
            print(f"  [skip] {jsonl_path} — not found")
            continue
        system_prompt = DEFAULT_SYSTEM_PROMPT
        count = 0
        with open(full_path) as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                ex = entry_to_example(entry, system_prompt)
                if ex:
                    ex["_source"] = source
                    examples.append(ex)
                    count += 1
        stats[source] = stats.get(source, 0) + count
        print(f"  [jsonl] {os.path.basename(jsonl_path)} — {count} entries")

    print(f"\nLoaded {len(examples)} examples:")
    for source, count in sorted(stats.items()):
        print(f"  {source:12s}  {count:5d}")

    # Shuffle and split
    random.seed(SEED)
    random.shuffle(examples)
    split = int(len(examples) * TRAIN_SPLIT)
    train = examples[:split]
    valid = examples[split:]

    # Write JSONL — strip internal _source tag
    os.makedirs(os.path.join(base, OUT_DIR), exist_ok=True)
    for name, subset in [("train", train), ("valid", valid)]:
        path = os.path.join(base, OUT_DIR, f"{name}.jsonl")
        with open(path, "w") as f:
            for ex in subset:
                clean = {k: v for k, v in ex.items() if k != "_source"}
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")
        print(f"\n{name}.jsonl  →  {len(subset)} examples  ({path})")

    # Preview one training example
    print("\n── Example training entry (train[0]) ──")
    ex = train[0]
    msgs = ex["messages"]
    print(f"system  : {msgs[0]['content'][:80]}...")
    print(f"user    : {msgs[1]['content'][:200]}...")
    print(f"assistant: {msgs[2]['content']}")


if __name__ == "__main__":
    main()
