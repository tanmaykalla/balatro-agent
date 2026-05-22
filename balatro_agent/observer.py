"""
Balatro Manual Play Observer
============================
Passively watches the live game via balatrobot and records every decision
the human makes — game state (= prompt) + inferred action + empty reasoning.

Reasoning can be filled in later manually or with an LLM.

Usage:
    python3 observer.py [--out runs/manual_run.jsonl]

While running:
    - Play Balatro normally via the game UI
    - The observer silently logs every action in the background
    - Press Ctrl+C to stop and save

Output format (one JSON object per line):
    {
        "ante": 1, "round": 1, "phase": "SELECTING_HAND",
        "action": "play_hand",
        "params": {"cards": [0, 1, 2, 3, 4], "reasoning": ""},
        "source": "human",
        "prompt": "# Phase: SELECTING_HAND ..."
    }
"""
from __future__ import annotations
import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from balatrobot_client import BalatrobotClient
from phase_prompts import PromptBuilder
from agent_memory import RunMemory


POLL_INTERVAL = 0.4   # seconds between polls
STABLE_TICKS  = 2     # consecutive identical states before we consider it "settled"


# ── helpers ───────────────────────────────────────────────────────────────────

def _hand_ids(G: dict) -> list[int]:
    """Return card IDs currently in hand, preserving order."""
    cards = (G.get("hand") or {}).get("cards") or []
    return [c.get("id", -1) for c in cards]


def _hand_index_map(G: dict) -> dict[int, int]:
    """Map card id → hand index for the current state."""
    cards = (G.get("hand") or {}).get("cards") or []
    return {c.get("id", -1): i for i, c in enumerate(cards)}


def _joker_ids(G: dict) -> set[int]:
    cards = (G.get("jokers") or {}).get("cards") or []
    return {c.get("id", -1) for c in cards}


def _consumable_ids(G: dict) -> set[int]:
    cards = (G.get("consumables") or {}).get("cards") or []
    return {c.get("id", -1) for c in cards}


def _shop_card_ids(G: dict) -> set[int]:
    cards = (G.get("shop") or {}).get("cards") or []
    return {c.get("id", -1) for c in cards}


def _money(G: dict) -> int:
    return G.get("money", 0)


def _discards_left(G: dict) -> int:
    return (G.get("round") or {}).get("discards_left", 0)


def _hands_left(G: dict) -> int:
    return (G.get("round") or {}).get("hands_left", 0)


def _score(G: dict) -> int:
    return (G.get("round") or {}).get("chips", 0)


# ── action inference ──────────────────────────────────────────────────────────

def _infer_action(prev: dict, curr: dict) -> dict | None:
    """
    Compare two consecutive game states and return an action dict, or None
    if nothing meaningful changed.

    Returns:
        {"action": str, "params": dict}
    """
    prev_phase = prev.get("state", "")
    curr_phase = curr.get("state", "")

    # ── SELECTING_HAND ────────────────────────────────────────────────────────
    if prev_phase == "SELECTING_HAND":
        prev_ids = _hand_ids(prev)
        curr_ids = _hand_ids(curr)

        if set(prev_ids) == set(curr_ids):
            return None  # hand unchanged, no action yet

        gone_ids = set(prev_ids) - set(curr_ids)
        prev_idx_map = {cid: i for i, cid in enumerate(prev_ids)}
        gone_indices = sorted(prev_idx_map[cid] for cid in gone_ids if cid in prev_idx_map)

        if not gone_indices:
            return None

        # Discard: discard_count decreased; Play: score or hand_count changed
        if _discards_left(curr) < _discards_left(prev):
            return {"action": "discard_cards",
                    "params": {"cards": gone_indices, "reasoning": ""}}
        else:
            return {"action": "play_hand",
                    "params": {"cards": gone_indices, "reasoning": ""}}

    # ── BLIND_SELECT ──────────────────────────────────────────────────────────
    if prev_phase == "BLIND_SELECT" and curr_phase != "BLIND_SELECT":
        # Detect skip vs select by whether round advanced or stayed same
        prev_round = prev.get("round_num", 0)
        curr_round = curr.get("round_num", 0)
        # If we skipped, round_num stays the same but the blind advances
        # Hard to distinguish perfectly without balatrobot hook; use money heuristic:
        # skipping gives a TAG (no money change), selecting starts the round
        if curr_phase == "SELECTING_HAND":
            return {"action": "select_blind", "params": {"reasoning": ""}}
        elif curr_phase == "BLIND_SELECT":
            # Still in blind select — likely skipped one and another appeared
            return {"action": "skip_blind", "params": {"reasoning": ""}}

    # ── SHOP ─────────────────────────────────────────────────────────────────
    if prev_phase == "SHOP" and curr_phase in ("SHOP", "SMODS_BOOSTER_OPENED",
                                                "SELECTING_HAND", "BLIND_SELECT"):
        prev_money = _money(prev)
        curr_money = _money(curr)
        money_delta = prev_money - curr_money  # positive = spent

        prev_jokers = _joker_ids(prev)
        curr_jokers = _joker_ids(curr)
        new_jokers = curr_jokers - prev_jokers
        lost_jokers = prev_jokers - curr_jokers

        prev_cons = _consumable_ids(prev)
        curr_cons = _consumable_ids(curr)
        new_cons = curr_cons - prev_cons

        prev_shop = _shop_card_ids(prev)
        curr_shop = _shop_card_ids(curr)
        bought_from_shop = prev_shop - curr_shop

        # Sold a joker (money went up, lost a joker)
        if lost_jokers and curr_money > prev_money:
            lost_idx = _find_joker_index(prev, next(iter(lost_jokers)))
            return {"action": "sell_joker",
                    "params": {"index": lost_idx, "reasoning": ""}}

        # Bought something
        if money_delta > 0 and bought_from_shop:
            bought_id = next(iter(bought_from_shop))
            bought_idx = _find_shop_index(prev, bought_id)
            if curr_phase == "SMODS_BOOSTER_OPENED":
                return {"action": "buy_pack",
                        "params": {"index": bought_idx, "reasoning": ""}}
            return {"action": "buy_card",
                    "params": {"index": bought_idx, "reasoning": ""}}

        # Rerolled (shop changed but nothing obviously bought)
        if money_delta > 0 and not bought_from_shop and not new_jokers and not new_cons:
            return {"action": "reroll_shop", "params": {"reasoning": ""}}

        # Left the shop
        if curr_phase != "SHOP":
            return {"action": "finish_shop", "params": {"reasoning": ""}}

    # ── SMODS_BOOSTER_OPENED ─────────────────────────────────────────────────
    if prev_phase == "SMODS_BOOSTER_OPENED":
        prev_cons = _consumable_ids(prev)
        curr_cons = _consumable_ids(curr)
        new_cons = curr_cons - prev_cons

        prev_jokers = _joker_ids(prev)
        curr_jokers = _joker_ids(curr)
        new_jokers = curr_jokers - prev_jokers

        if new_cons or new_jokers:
            # Selected a card from the pack
            pack = prev.get("pack") or prev.get("opened_pack") or {}
            pack_cards = pack.get("cards") or []
            # Find which pack card is now gone
            prev_pack_ids = {c.get("id", -1): i for i, c in enumerate(pack_cards)}
            curr_pack = curr.get("pack") or curr.get("opened_pack") or {}
            curr_pack_ids = {c.get("id", -1) for c in (curr_pack.get("cards") or [])}
            selected = [i for cid, i in prev_pack_ids.items() if cid not in curr_pack_ids]
            idx = selected[0] if selected else 0
            return {"action": "select_pack_card",
                    "params": {"index": idx, "reasoning": ""}}

        if curr_phase == "SHOP":
            return {"action": "skip_pack", "params": {"reasoning": ""}}

    return None


def _find_joker_index(G: dict, card_id: int) -> int:
    cards = (G.get("jokers") or {}).get("cards") or []
    for i, c in enumerate(cards):
        if c.get("id") == card_id:
            return i
    return 0


def _find_shop_index(G: dict, card_id: int) -> int:
    for section in ("cards", "vouchers", "packs"):
        cards = (G.get("shop") or {}).get(section) or []
        for i, c in enumerate(cards):
            if c.get("id") == card_id:
                return i
    return 0


# ── observer ─────────────────────────────────────────────────────────────────

class ManualObserver:
    def __init__(self, out_path: str):
        self.bot      = BalatrobotClient()
        self.prompts  = PromptBuilder()
        self.out_path = out_path
        self.entries: list[dict] = []
        self._prev_G: dict | None = None
        self._prev_prompt: str = ""
        self._memory  = RunMemory(run_id="manual", strategy_name="human",
                                  source="human")

    def run(self):
        print(f"[observer] watching game → {self.out_path}")
        print("[observer] play normally in Balatro. Ctrl+C to stop.\n")

        prev_state_str = ""
        stable_count   = 0

        try:
            while True:
                try:
                    G = self.bot.get_gamestate()
                except Exception as e:
                    print(f"[observer] poll error: {e}")
                    time.sleep(1)
                    continue

                state = G.get("state", "")

                # Skip non-interactive states
                if state in ("MENU", "ROUND_EVAL", "GAME_OVER", ""):
                    if state == "GAME_OVER":
                        print("\n[observer] game over — stopping.")
                        break
                    self._prev_G = G
                    time.sleep(POLL_INTERVAL)
                    continue

                # Detect when state has settled (stopped changing)
                curr_str = json.dumps(G, sort_keys=True)
                if curr_str == prev_state_str:
                    stable_count += 1
                else:
                    stable_count  = 0
                    prev_state_str = curr_str

                if stable_count < STABLE_TICKS:
                    time.sleep(POLL_INTERVAL)
                    continue

                # State is stable — check if an action happened since last stable state
                if self._prev_G is not None:
                    action_dict = _infer_action(self._prev_G, G)
                    if action_dict:
                        phase = self._prev_G.get("state", "?")
                        ante  = self._prev_G.get("ante_num", "?")
                        rnd   = self._prev_G.get("round_num", "?")
                        entry = {
                            "ante":   ante,
                            "round":  rnd,
                            "phase":  phase,
                            "action": action_dict["action"],
                            "params": action_dict["params"],
                            "source": "human",
                            "prompt": self._prev_prompt,
                        }
                        self.entries.append(entry)
                        print(f"  ✓ A{ante}R{rnd} [{phase}] {action_dict['action']}"
                              f"  {action_dict['params'].get('cards', action_dict['params'].get('index', ''))}")

                # Capture prompt for the current stable state
                self._prev_prompt = self.prompts.build_gamestate_prompt(G, self._memory)
                self._memory.ante_num  = G.get("ante_num",  self._memory.ante_num)
                self._memory.round_num = G.get("round_num", self._memory.round_num)
                self._prev_G = G

                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n[observer] stopped by user.")

        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.out_path) or ".", exist_ok=True)
        with open(self.out_path, "w") as f:
            for entry in self.entries:
                f.write(json.dumps(entry) + "\n")
        print(f"[observer] saved {len(self.entries)} entries → {self.out_path}")
        # Print summary
        from collections import Counter
        c = Counter(e["action"] for e in self.entries)
        for action, count in c.most_common():
            print(f"  {action}: {count}")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Balatro manual play observer")
    parser.add_argument("--out", default="runs/manual_run.jsonl",
                        help="Output JSONL file path")
    args = parser.parse_args()

    obs = ManualObserver(out_path=args.out)
    obs.run()
