"""
manual_play.py — record a human Balatro session as fine-tuning data.

Run:
    python3 manual_play.py

Commands during play:
    play  0 1 2 3 4     — play cards at these indices
    discard 3 4         — discard cards at these indices
    buy   0             — buy shop item at index
    sell  2             — sell joker at index
    use   0             — use consumable at index
    select              — select the blind
    skip                — skip the blind
    reroll              — reroll the shop
    next                — finish shop / advance
    pack  0             — pick pack card at index
    packskip            — skip the pack
"""

from perception import BalatrobotPerception
from run_logger import run_manual
import json

LOG_DIR = "finetune_logs/"

def main():
    perception = BalatrobotPerception()
    print("Starting game... make sure Balatro is running with balatrobot mod.")
    perception.start_game()

    log_path = run_manual(perception, strategy_name="human", log_dir=LOG_DIR)

    # Show a quick summary
    with open(log_path) as f:
        data = json.load(f)
    entries = data["action_log"]
    print(f"\n=== Session complete ===")
    print(f"Entries logged : {len(entries)}")
    print(f"Saved to       : {log_path}")
    if entries:
        print(f"\nFirst entry preview:")
        e = entries[0]
        print(f"  phase={e['phase']}  action={e['action']}  reasoning={e['reasoning'][:60]}")
        print(f"  prompt (first 200 chars): {e['prompt'][:200]}")

if __name__ == "__main__":
    main()
