"""
observe.py — passive observer for human Balatro play.

Run AFTER launching Balatro with balatrobot mod. Play normally with
mouse/keyboard. This script polls the game state every 0.4s, diffs
before/after to infer what action you took, and logs it.

Run:
    python3 observe.py

Press Ctrl-C to stop and save.
"""

import time
import json
from perception import BalatrobotPerception, GameState
from run_logger import RunLogger, format_state_prompt, _ACTION_TO_LOG_NAME

POLL_INTERVAL = 0.4   # seconds between state polls
LOG_DIR = "finetune_logs/"


# ── State change detection ────────────────────────────────────────────────────

def _state_fingerprint(s: GameState) -> tuple:
    """A hashable summary of the parts of state that matter for change detection."""
    return (
        s.phase,
        s.ante_num,
        s.round_num,
        s.hands_left,
        s.discards_left,
        s.money,
        tuple(c.id for c in s.hand),
        tuple(j.get("key", "") for j in s.jokers),
        tuple(c.get("key", "") for c in s.consumables),
        tuple(c.get("key", "") for c in s.shop_cards),
    )


def _state_changed(prev: GameState, curr: GameState) -> bool:
    return _state_fingerprint(prev) != _state_fingerprint(curr)


# ── Action inference ──────────────────────────────────────────────────────────

def _removed_card_indices(prev: GameState, curr: GameState) -> list:
    """Return indices (in prev.hand) of cards that left the hand between states.
    Matches by card key (e.g. 'H_A') since IDs are just positional."""
    prev_keys = [c.key for c in prev.hand]
    curr_keys = list(c.key for c in curr.hand)
    remaining = list(curr_keys)
    removed_keys = []
    for k in prev_keys:
        if k in remaining:
            remaining.remove(k)
        else:
            removed_keys.append(k)
    return [c.index for c in prev.hand if c.key in removed_keys]


def _missing_key(prev_list: list, curr_list: list) -> str:
    """Return the first key that's in prev but not in curr (accounting for duplicates)."""
    remaining = list(curr_list)
    for k in prev_list:
        if k in remaining:
            remaining.remove(k)
        else:
            return k
    return ""


def _infer_action(prev: GameState, curr: GameState):
    """
    Diff two consecutive states and return an action_log entry dict,
    or None if we can't confidently infer what happened
    (e.g. automatic transitions like ROUND_EVAL→SHOP).
    """
    pp, cp = prev.phase, curr.phase

    # ── Blind select / skip ───────────────────────────────────────────────────
    if pp == "BLIND_SELECT" and cp == "SELECTING_HAND":
        return {"action": "select_blind", "params": {"reasoning": ""}}

    if pp == "BLIND_SELECT" and cp == "BLIND_SELECT":
        # Skipped — money or round changed
        return {"action": "skip_blind", "params": {"reasoning": ""}}

    # ── Play hand ─────────────────────────────────────────────────────────────
    if pp == "SELECTING_HAND" and prev.hands_left > curr.hands_left:
        played_indices = _removed_card_indices(prev, curr)
        return {
            "action": "play_hand",
            "params": {"cards": played_indices, "reasoning": ""},
        }

    # ── Discard ───────────────────────────────────────────────────────────────
    if pp == "SELECTING_HAND" and prev.discards_left > curr.discards_left:
        discarded_indices = _removed_card_indices(prev, curr)
        return {
            "action": "discard_cards",
            "params": {"cards": discarded_indices, "reasoning": ""},
        }

    # ── Cash out (auto) — skip logging, not a human decision ─────────────────
    if pp == "ROUND_EVAL" and cp == "SHOP":
        return None

    # ── Finish shop ───────────────────────────────────────────────────────────
    if pp == "SHOP" and cp == "BLIND_SELECT":
        return {"action": "finish_shop", "params": {"reasoning": ""}}

    # ── SHOP actions — check what specifically changed ────────────────────────
    if pp == "SHOP" and cp == "SHOP":
        # Sell joker: joker disappeared AND money went up
        prev_jkeys = [j.get("key", "") for j in prev.jokers]
        curr_jkeys = [j.get("key", "") for j in curr.jokers]
        if curr.money > prev.money and len(curr_jkeys) < len(prev_jkeys):
            sold_key = _missing_key(prev_jkeys, curr_jkeys)
            idx = next((i for i, j in enumerate(prev.jokers)
                        if j.get("key", "") == sold_key), 0)
            return {"action": "sell_joker",
                    "params": {"index": idx, "key": sold_key, "reasoning": ""}}

        # Use consumable: consumable disappeared
        prev_ckeys = [c.get("key", "") for c in prev.consumables]
        curr_ckeys = [c.get("key", "") for c in curr.consumables]
        if len(prev_ckeys) > len(curr_ckeys):
            used_key = _missing_key(prev_ckeys, curr_ckeys)
            idx = next((i for i, c in enumerate(prev.consumables)
                        if c.get("key", "") == used_key), 0)
            return {"action": "use_consumable",
                    "params": {"index": idx, "key": used_key, "reasoning": ""}}

        # Reroll: money dropped AND shop items completely changed
        prev_skeys = set(c.get("key", "") for c in prev.shop_cards)
        curr_skeys = set(c.get("key", "") for c in curr.shop_cards)
        if curr.money < prev.money and not (prev_skeys & curr_skeys):
            return {"action": "reroll_shop", "params": {"reasoning": ""}}

        # Buy card: shop item disappeared AND money dropped
        prev_shop_keys = [c.get("key", "") for c in prev.shop_cards]
        curr_shop_keys = [c.get("key", "") for c in curr.shop_cards]
        if curr.money < prev.money and len(curr_shop_keys) < len(prev_shop_keys):
            bought_key = _missing_key(prev_shop_keys, curr_shop_keys)
            idx = next((i for i, c in enumerate(prev.shop_cards)
                        if c.get("key", "") == bought_key), 0)
            return {"action": "buy_card",
                    "params": {"index": idx, "key": bought_key, "reasoning": ""}}

    # ── Pack select ───────────────────────────────────────────────────────────
    if "PACK" in pp or "BOOSTER" in pp:
        if cp != pp:
            return {"action": "pack_select", "params": {"reasoning": ""}}

    return None


# ── Main observer loop ────────────────────────────────────────────────────────

def observe():
    perception = BalatrobotPerception()
    logger = RunLogger(strategy_name="human_observed", source="manual",
                       log_dir=LOG_DIR)

    print(f"\n=== Passive Observer  run_id={logger.run_id} ===")
    print("Play Balatro normally. This script watches and logs every action.")
    print("Press Ctrl-C to stop and save.\n")

    # Get initial state without starting a new game
    prev_state = perception.get_state()
    prev_prompt = format_state_prompt(prev_state)
    entries = 0

    try:
        while not perception.is_game_over():
            time.sleep(POLL_INTERVAL)

            try:
                curr_state = perception.get_state()
            except Exception as e:
                print(f"  [poll error: {e}]")
                continue

            if not _state_changed(prev_state, curr_state):
                continue

            # State changed — infer action
            action_dict = _infer_action(prev_state, curr_state)

            if action_dict is not None:
                entry = {
                    "ante":      prev_state.ante_num,
                    "round":     prev_state.round_num,
                    "phase":     prev_state.phase,
                    "action":    action_dict["action"],
                    "params":    action_dict["params"],
                    "reasoning": "",
                    "prompt":    prev_prompt,
                    "source":    "manual",
                }
                logger.action_log.append(entry)
                entries += 1
                print(f"  [{prev_state.phase}] {action_dict['action']}  "
                      f"params={action_dict['params']}  "
                      f"(total logged: {entries})")

            # Advance
            prev_state = curr_state
            prev_prompt = format_state_prompt(curr_state)

    except KeyboardInterrupt:
        print("\n[stopped]")
    except Exception as e:
        print(f"\n[error: {e}]")
    finally:
        path = logger.save()
        print(f"\nSaved {entries} entries → {path}")


if __name__ == "__main__":
    observe()
