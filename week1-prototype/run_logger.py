"""
run_logger.py — unified action logging for week1-prototype strategy runs and manual play.

Produces the same JSON format as balatro_agent/agent_memory.py so both data sources
feed the same fine-tuning pipeline.
"""
from __future__ import annotations
import json
import os
import uuid
from typing import Optional

from perception import GameState, Action, Strategy, RANK_VALUE


# ── Prompt formatter ──────────────────────────────────────────────────────────

def format_state_prompt(state: GameState) -> str:
    """
    Convert a GameState to the same human-readable text that
    balatro_agent/phase_prompts.py produces, so prompts are comparable
    across strategy runs, manual play, and Gemini runs.
    """
    parts: list[str] = []
    parts.append(f"# Phase: {state.phase} | Ante {state.ante_num} Round {state.round_num}")
    parts.append(
        f"Money: ${state.money} | "
        f"Hands left: {state.hands_left} | "
        f"Discards left: {state.discards_left}"
    )

    if state.blind_chips_required:
        parts.append(
            f"Blind target: {state.blind_chips_required} | "
            f"Chips scored so far: {state.chips}"
        )

    if state.hand:
        parts.append("\n## Hand")
        for c in state.hand:
            parts.append(f"  [{c.index}] {c.key} ({c.rank} of {c.suit})"
                         + (" [DEBUFFED]" if c.debuffed else ""))

    if state.jokers:
        parts.append("\n## Jokers")
        for i, j in enumerate(state.jokers):
            sell = (j.get("cost") or {}).get("sell", "?")
            parts.append(f"  [{i}] {j.get('label', j.get('key', '?'))} (sell ${sell})")

    if state.consumables:
        parts.append("\n## Consumables")
        for i, c in enumerate(state.consumables):
            parts.append(f"  [{i}] {c.get('label', c.get('key', '?'))}")

    if state.phase == "SHOP" and state.shop_cards:
        parts.append("\n## Shop")
        for i, sc in enumerate(state.shop_cards):
            cost = (sc.get("cost") or {}).get("buy", "?")
            parts.append(
                f"  [{i}] {sc.get('label', sc.get('key', '?'))} "
                f"({sc.get('set', '?')}) — ${cost}"
            )

    if state.pack_cards:
        parts.append("\n## Pack Contents")
        for i, c in enumerate(state.pack_cards):
            parts.append(f"  [{i}] {c.get('label', c.get('key', '?'))}")

    return "\n".join(parts)


# ── Reasoning deriver ─────────────────────────────────────────────────────────

def _derive_reasoning(state: GameState, action: Action, strategy: Strategy) -> str:
    """One-line human-readable explanation of why the strategy chose this action."""
    t = action.action_type

    if t == "play":
        hand_type = action.meta.get("hand_type", "?")
        cards = [state.hand[i].key for i in (action.payload.get("cards") or [])
                 if i < len(state.hand)]
        return (f"{strategy.name}: play {hand_type} with {cards} "
                f"(blind target {state.blind_chips_required}, scored {state.chips})")

    if t == "discard":
        cards = [state.hand[i].key for i in (action.payload.get("cards") or [])
                 if i < len(state.hand)]
        return (f"{strategy.name}: discard {cards} to build toward "
                f"{strategy.combo.target_hand or 'best hand'}")

    if t == "select_blind":
        return (f"{strategy.name}: select {state.current_blind} blind "
                f"(margin {state.last_score_margin:.1f}x)")

    if t == "skip_blind":
        return (f"{strategy.name}: skip {state.current_blind} blind "
                f"(margin {state.last_score_margin:.1f}x, "
                f"hands used last round {state.hands_used_last_round})")

    if t == "buy":
        idx = action.payload.get("card", 0)
        choices = state.shop_cards
        key = choices[idx].get("key", "?") if idx < len(choices) else "?"
        return f"{strategy.name}: buy {key} from shop"

    if t == "sell":
        idx = action.payload.get("card", 0)
        key = state.jokers[idx].get("key", "?") if idx < len(state.jokers) else "?"
        return f"{strategy.name}: sell joker {key} to make room"

    if t == "use":
        idx = action.payload.get("consumable", 0)
        key = state.consumables[idx].get("key", "?") if idx < len(state.consumables) else "?"
        return f"{strategy.name}: use consumable {key}"

    if t == "reroll":
        return f"{strategy.name}: reroll shop (wallet ${state.money})"

    if t == "next_round":
        return f"{strategy.name}: finish shop and proceed"

    if t == "cash_out":
        return f"{strategy.name}: cash out round"

    return f"{strategy.name}: {t}"


# ── Action → canonical name mapping ──────────────────────────────────────────

_ACTION_TO_LOG_NAME = {
    "play":          "play_hand",
    "discard":       "discard_cards",
    "select_blind":  "select_blind",
    "skip_blind":    "skip_blind",
    "buy":           "buy_card",
    "sell":          "sell_joker",
    "use":           "use_consumable",
    "reroll":        "reroll_shop",
    "next_round":    "finish_shop",
    "cash_out":      "cash_out",
    "pack":          "pack_select",
}


# ── RunLogger ─────────────────────────────────────────────────────────────────

class RunLogger:
    """
    Accumulates action_log entries during a run and saves to JSON.
    Output format matches balatro_agent run JSONs for unified fine-tuning.
    """

    def __init__(self, strategy_name: str, source: str = "strategy",
                 system_prompt: str = "", log_dir: str = "runs/"):
        self.run_id = uuid.uuid4().hex[:12]
        self.strategy_name = strategy_name
        self.source = source
        self.system_prompt = system_prompt
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.action_log: list[dict] = []

    def log(self, state: GameState, action: Action, reasoning: str, prompt: str) -> None:
        canonical = _ACTION_TO_LOG_NAME.get(action.action_type, action.action_type)

        params: dict = {}
        if action.payload.get("cards") is not None:
            params["cards"] = action.payload["cards"]
        idx = (action.payload.get("card")
               or action.payload.get("joker")
               or action.payload.get("consumable"))
        if idx is not None:
            params["index"] = idx
        params["reasoning"] = reasoning

        entry = {
            "ante":      state.ante_num,
            "round":     state.round_num,
            "phase":     state.phase,
            "action":    canonical,
            "params":    params,
            "reasoning": reasoning,
            "prompt":    prompt,
            "source":    self.source,
        }
        self.action_log.append(entry)

    def save(self, run_num: int | None = None) -> str:
        # Filename: {strategy_name}_run{02d}_{run_id}.json  e.g. FH_2P_run03_a1b2c3d4e5f6.json
        slug = self.strategy_name.replace(" ", "_")
        num_part = f"_run{run_num:02d}" if run_num is not None else ""
        filename = f"{slug}{num_part}_{self.run_id}.json"
        path = os.path.join(self.log_dir, filename)
        data = {
            "run_id":        self.run_id,
            "run_num":       run_num,
            "strategy_name": self.strategy_name,
            "source":        self.source,
            "system_prompt": self.system_prompt,
            "action_log":    self.action_log,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  [log] saved {len(self.action_log)} entries → {path}", flush=True)
        return path


# ── Manual play mode ──────────────────────────────────────────────────────────

def _prompt_human(state: GameState) -> tuple[Action, str]:
    """
    Parse a human command and return (Action, reasoning).

    Commands:
      play  0 1 2 3 4       — play cards at these indices
      discard 3 4           — discard cards at these indices
      buy   0               — buy shop item at index
      sell  2               — sell joker at index
      use   0               — use consumable at index (optionally: use 0 targets 1 2)
      select                — select the current blind
      skip                  — skip the current blind
      reroll                — reroll the shop
      next                  — finish shop / advance
      pack  0               — select pack card at index
      packskip              — skip current pack
    """
    _ALIASES = {
        "p": "play", "d": "discard", "b": "buy", "s": "sell",
        "u": "use", "r": "reroll", "n": "next", "sel": "select",
    }

    while True:
        try:
            raw = input("action> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return Action(action_type="next_round"), "manual session ended"

        if not raw:
            continue

        parts = raw.split()
        cmd = _ALIASES.get(parts[0], parts[0]).lower()
        nums = []
        for p in parts[1:]:
            if p.isdigit():
                nums.append(int(p))

        action: Optional[Action] = None

        if cmd == "play":
            cards = nums if nums else [0, 1, 2, 3, 4]
            action = Action("play", {"cards": cards})
        elif cmd == "discard":
            if not nums:
                print("  usage: discard <idx> [idx ...]")
                continue
            action = Action("discard", {"cards": nums})
        elif cmd == "buy":
            idx = nums[0] if nums else 0
            action = Action("buy", {"card": idx})
        elif cmd == "sell":
            idx = nums[0] if nums else 0
            action = Action("sell", {"card": idx})
        elif cmd == "use":
            # use 0 targets 1 2  → payload {"consumable": 0, "cards": [1,2]}
            idx = nums[0] if nums else 0
            # check for "targets" keyword
            targets: list[int] = []
            if "targets" in parts:
                ti = parts.index("targets")
                targets = [int(x) for x in parts[ti+1:] if x.isdigit()]
            payload = {"consumable": idx}
            if targets:
                payload["cards"] = targets
            action = Action("use", payload)
        elif cmd == "select":
            action = Action("select_blind")
        elif cmd == "skip":
            action = Action("skip_blind")
        elif cmd == "reroll":
            action = Action("reroll")
        elif cmd in ("next", "finish"):
            action = Action("next_round")
        elif cmd == "pack":
            idx = nums[0] if nums else 0
            action = Action("select_blind", {"card": idx})
        elif cmd == "packskip":
            action = Action("skip_blind")
        else:
            print(f"  unknown command '{cmd}'. try: play/discard/buy/sell/use/select/skip/reroll/next/pack/packskip")
            continue

        try:
            reasoning = input("reasoning> ").strip() or f"manual: {cmd}"
        except (EOFError, KeyboardInterrupt):
            reasoning = f"manual: {cmd}"

        return action, reasoning


def run_manual(perception, strategy_name: str = "human",
               log_dir: str = "runs/") -> str:
    """
    Interactive CLI mode: human makes every decision, all actions are logged
    in the same format as strategy and Gemini runs.

    Returns the path of the saved run JSON.
    """
    from perception import run_strategy  # only for type hints; not called in manual mode

    logger = RunLogger(strategy_name=strategy_name, source="manual", log_dir=log_dir)
    print(f"\n=== Manual Play Mode  run_id={logger.run_id} ===")
    print("Commands: play/discard/buy/sell/use/select/skip/reroll/next/pack/packskip")
    print("Ctrl-C or 'next' at end to finish.\n")

    print(f"  Saving to: finetune_logs/human_<id>.json when done (Ctrl-C to stop early)\n")
    try:
        while not perception.is_game_over():
            state = perception.get_state()
            print(f"  [is_game_over=False, phase={state.phase}, entries so far={len(logger.action_log)}]")
            prompt = format_state_prompt(state)
            print("\n" + prompt + "\n")

            action, reasoning = _prompt_human(state)
            perception.take_action(action)
            logger.log(state, action, reasoning, prompt)
    except KeyboardInterrupt:
        print("\n[interrupted — saving partial run]")
    except Exception as e:
        print(f"\n[error: {e} — saving partial run]")
    finally:
        return logger.save()
