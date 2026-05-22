"""
Reasoning Post-Processor
========================
Takes a raw observer JSONL (reasoning: "") and lets you fill in reasoning
either manually (interactive) or automatically via Claude.

Usage:
    # Interactive — review each action and type reasoning yourself
    python3 add_reasoning.py --input runs/manual_run.jsonl --mode manual

    # Automatic — Claude fills in reasoning based on game state + action
    python3 add_reasoning.py --input runs/manual_run.jsonl --mode llm

    # Skip already-filled entries and only process blanks
    python3 add_reasoning.py --input runs/manual_run.jsonl --mode manual --blanks-only

Output: overwrites the input file with reasoning filled in.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


CLAUDE_REASONING_PROMPT = """You are annotating Balatro gameplay data for fine-tuning an AI agent.

Given a game state prompt and the action the human player took, write a short 1-3 sentence
reasoning that explains WHY the human made that choice. Be specific about:
- What hand/option was chosen and why it was best
- Why discarding (or not discarding) was the right call
- Any strategic consideration (chip target, hands left, joker synergy)

Keep it concise — 1-3 sentences max. Write in first person as the decision-maker.
Do NOT mention "the human" — write as if YOU made the decision.

Game state:
{prompt}

Action taken: {action}
Params: {params}

Write only the reasoning text, nothing else."""


def _fmt_action(entry: dict) -> str:
    action = entry["action"]
    params = entry["params"]
    cards  = params.get("cards", params.get("index", ""))
    return f"{action}({cards})" if cards != "" else action


def _interactive(entries: list[dict], blanks_only: bool) -> list[dict]:
    total = sum(1 for e in entries if not blanks_only or not e["params"].get("reasoning"))
    done  = 0
    for entry in entries:
        if blanks_only and entry["params"].get("reasoning"):
            continue
        done += 1
        print(f"\n── [{done}/{total}] A{entry['ante']}R{entry['round']} "
              f"[{entry['phase']}] {_fmt_action(entry)} ──")
        # Show abbreviated prompt
        for line in entry.get("prompt", "").splitlines()[:30]:
            print(f"  {line}")
        if len(entry.get("prompt", "").splitlines()) > 30:
            print("  ...")
        print(f"\nAction: {_fmt_action(entry)}")
        reasoning = input("Reasoning (Enter to skip): ").strip()
        if reasoning:
            entry["params"]["reasoning"] = reasoning
    return entries


def _llm(entries: list[dict], blanks_only: bool) -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("[error] anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[error] ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    total  = sum(1 for e in entries if not blanks_only or not e["params"].get("reasoning"))
    done   = 0

    for entry in entries:
        if blanks_only and entry["params"].get("reasoning"):
            continue
        done += 1
        print(f"  [{done}/{total}] {_fmt_action(entry)} ... ", end="", flush=True)

        prompt_text = CLAUDE_REASONING_PROMPT.format(
            prompt=entry.get("prompt", "(no prompt)"),
            action=entry["action"],
            params=json.dumps({k: v for k, v in entry["params"].items() if k != "reasoning"}),
        )
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt_text}],
        )
        reasoning = resp.content[0].text.strip()
        entry["params"]["reasoning"] = reasoning
        print(reasoning[:80])

    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",       required=True)
    parser.add_argument("--mode",        choices=["manual", "llm"], default="manual")
    parser.add_argument("--blanks-only", action="store_true",
                        help="Only process entries with empty reasoning")
    args = parser.parse_args()

    with open(args.input) as f:
        entries = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(entries)} entries from {args.input}")
    blank_count = sum(1 for e in entries if not e["params"].get("reasoning"))
    print(f"  {blank_count} have empty reasoning")

    if args.mode == "manual":
        entries = _interactive(entries, args.blanks_only)
    else:
        entries = _llm(entries, args.blanks_only)

    # Save back
    with open(args.input, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    filled = sum(1 for e in entries if e["params"].get("reasoning"))
    print(f"\nSaved {args.input} — {filled}/{len(entries)} entries have reasoning")


if __name__ == "__main__":
    main()
