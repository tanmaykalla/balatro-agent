from __future__ import annotations
import json
import time as _time

from agent_memory import RunMemory
from strategies import Strategy
from balatrobot_client import BalatrobotClient, BalatrobotError
from llm_clients import GeminiFlashLiteClient, ToolCall
from phase_prompts import PromptBuilder
from agent_tools import (
    PHASE_TOOLS, SELECTING_HAND_TOOLS, SHOP_TOOLS,
    BLIND_SELECT_TOOLS, BOOSTER_PACK_TOOLS,
)

# Hand rank for missed-discard detection (0 = High Card, 1 = Pair, ...)
_HAND_RANK_NUM = {
    "High Card": 0, "Pair": 1, "Two Pair": 2, "Three of a Kind": 3,
    "Straight": 4, "Flush": 5, "Full House": 6, "Four of a Kind": 7,
    "Straight Flush": 8,
}

def _best_hand_rank(playable_lines: list[str]) -> int:
    """Parse the best hand rank from _detect_hands() output lines."""
    best = -1
    for line in playable_lines:
        for name, rank in _HAND_RANK_NUM.items():
            if line.startswith(name + ":"):
                if rank > best:
                    best = rank
                break
    return best


def _log_action(memory: RunMemory, G: dict, tool_call: ToolCall,
                extra: dict | None = None, prompt: str | None = None) -> None:
    # API error sentinel — game keeps running but don't pollute training data
    if tool_call.name == "_api_error":
        return
    ante    = G.get("ante_num", "?")
    round_n = G.get("round_num", "?")
    phase   = G.get("state", "?")
    action  = tool_call.name
    reasoning = str(tool_call.params.get("reasoning", "") or "")
    cards   = tool_call.params.get("cards", "")
    index   = tool_call.params.get("index", "")

    # Build a compact terminal line
    detail = ""
    if cards != "":
        detail = f" cards={cards}"
    elif index != "":
        detail = f" idx={index}"

    ts = _time.strftime("%H:%M:%S")
    status = f"  ✗ {extra.get('error','')[:60]}" if extra and "error" in extra else ""
    print(f"  {ts} A{ante}R{round_n} [{phase}] {action}{detail}{status}")
    if reasoning:
        print(f"    ↳ {reasoning[:100]}")

    entry = {
        "ante": ante,
        "round": round_n,
        "phase": phase,
        "action": action,
        "params": tool_call.params,
        "reasoning": reasoning,
        "source": memory.source,
    }
    if not reasoning:
        print(f"  [warn] empty reasoning on {action}")
    # Text-response fallback: real decision attempt but mark it so it can be filtered
    if "fallback" in reasoning:
        entry["fallback_reason"] = "text_response"
    if prompt is not None:
        entry["prompt"] = prompt
    if extra:
        entry.update(extra)
    memory.action_log.append(entry)


def _record_wallet(memory: RunMemory, G: dict) -> None:
    memory.wallet_history.append({
        "ante": G.get("ante_num"), "round": G.get("round_num"),
        "money": G.get("money", 0),
    })


def _conv_append(history: list[dict], tool_call: ToolCall, new_state: str) -> None:
    """Append tool call + result to history in a format both Gemini and Ollama accept."""
    if tool_call.name == "_api_error":
        return   # don't pollute history with API error entries
    history.append({
        "role": "assistant",
        "content": f"Called {tool_call.name}({json.dumps(tool_call.params)})",
    })
    history.append({
        "role": "user",
        "content": f"Action executed. New game state: {new_state}",
    })


class BlindSelectHandler:
    def handle(self, G: dict, strategy: Strategy, memory: RunMemory,
               gemini: GeminiFlashLiteClient, prompts: PromptBuilder,
               system_prompt: str, bot: BalatrobotClient) -> dict:
        blinds = G.get("blinds") or {}
        cur = blinds.get("current") or blinds.get("active") or {}
        blind_type = cur.get("name") or cur.get("key") or ""

        # --- Boss blind detection: use multiple signals, any one suffices ---
        # 1. The "boss" sub-object in blinds has status SELECT/CURRENT
        boss_obj = blinds.get("boss") or {}
        boss_status = (boss_obj.get("status") or "").upper()
        boss_by_status = boss_status in ("SELECT", "CURRENT", "ACTIVE")
        # 2. The current blind key/name contains "boss"
        boss_by_name = "boss" in blind_type.lower()
        # 3. round_num within an ante: small=1, big=2, boss=3
        boss_by_round = G.get("round_num", 0) % 3 == 0 and G.get("round_num", 0) > 0
        is_boss = boss_by_status or boss_by_name or boss_by_round

        is_small = (
            "small" in blind_type.lower()
            or (blinds.get("small") or {}).get("status", "").upper() in ("SELECT", "CURRENT")
        )
        is_big = (
            "big" in blind_type.lower()
            or (blinds.get("big") or {}).get("status", "").upper() in ("SELECT", "CURRENT")
        )

        print(f"  [blind] type='{blind_type}' boss_by_status={boss_by_status} "
              f"boss_by_name={boss_by_name} boss_by_round={boss_by_round} → is_boss={is_boss}")

        allow_skip = not is_boss
        if is_small and not strategy.blind.skip_small:
            allow_skip = False
        if is_big and not strategy.blind.skip_big:
            allow_skip = False
        if strategy.blind.skip_condition == "never":
            allow_skip = False
        if strategy.blind.skip_condition == "comfortable_margin":
            last = memory.blind_history[-1] if memory.blind_history else None
            if last is None:
                # No history yet — trust the strategy's skip flags
                comfortable = True
            else:
                comfortable = False
                if not last.get("skipped"):
                    tgt = last.get("target_score", 0) or 0
                    ach = last.get("achieved_score", 0) or 0
                    if tgt and ach >= 2 * tgt:
                        comfortable = True
                    if last.get("hands_left_at_finish", 0) >= 1:
                        comfortable = True
            if not comfortable:
                allow_skip = False

        tools = BLIND_SELECT_TOOLS if allow_skip else [BLIND_SELECT_TOOLS[0]]
        user_msg = prompts.build_gamestate_prompt(G, memory)
        if not allow_skip:
            user_msg += "\n\nNOTE: skipping is not permitted here. You must select."

        tool_call = gemini.call(system_prompt, user_msg, tools, [])

        # Hard safety: never skip boss blind regardless of LLM choice
        if tool_call.name == "skip_blind" and (not allow_skip or is_boss):
            tool_call = ToolCall("select_blind",
                                 {"reasoning": "skip disallowed (boss blind or limit), forcing select"})

        if tool_call.name == "skip_blind":
            G = bot.skip()
            skipped = True
        else:
            G = bot.select()
            skipped = False

        _log_action(memory, {"ante_num": G.get("ante_num"), "round_num": G.get("round_num"),
                             "state": "BLIND_SELECT"}, tool_call, prompt=user_msg)
        memory.blind_history.append({
            "ante": memory.ante_num, "blind_type": blind_type, "skipped": skipped,
            "target_score": cur.get("chips") or cur.get("score"),
            "achieved_score": 0, "hands_left_at_finish": 0,
        })
        return G


class SelectingHandHandler:
    def handle(self, G: dict, strategy: Strategy, memory: RunMemory,
               gemini: GeminiFlashLiteClient, prompts: PromptBuilder,
               system_prompt: str, bot: BalatrobotClient) -> dict:
        history: list[dict] = []
        discards_used = 0
        hands_used = 0
        initial_hands = (G.get("round") or {}).get("hands_left", 0)

        while G.get("state") == "SELECTING_HAND":
            limit = strategy.combo.max_discards_per_round
            hands_left = (G.get("round") or {}).get("hands_left", 0)
            is_last_round = hands_left == 1
            waive = strategy.combo.waive_limit_last_round and is_last_round
            discards_left = (G.get("round") or {}).get("discards_left", 0)
            allow_discard = (
                discards_left > 0
                and (limit == 0 or discards_used < limit or waive)
            )

            tools = list(SELECTING_HAND_TOOLS) if allow_discard else [SELECTING_HAND_TOOLS[0]]
            user_msg = prompts.build_gamestate_prompt(G, memory)
            if not allow_discard:
                user_msg += "\n\nNOTE: discarding is not permitted (limit reached or 0 left). You must play."

            tool_call = gemini.call(system_prompt, user_msg, tools, history)

            # ── Missed-discard diagnostic ──────────────────────────────────────
            if allow_discard and tool_call.name == "play_hand" and discards_left > 1:
                from phase_prompts import _detect_hands as _dh
                hand_cards = (G.get("hand") or {}).get("cards") or []
                playable = _dh(hand_cards)
                best_rank = _best_hand_rank(playable)
                if best_rank <= 1:   # High Card or Pair — discard was likely better
                    print(f"\n  ⚠ MISSED DISCARD OPPORTUNITY")
                    print(f"    discards_left={discards_left}  best_hand_rank={best_rank}"
                          f"  ({'Pair' if best_rank == 1 else 'High Card'})")
                    print(f"    model chose: play_hand  cards={tool_call.params.get('cards')}")
                    print(f"    reasoning: {str(tool_call.params.get('reasoning','') or '')[:120]}")
                    print(f"    ── prompt sent ──")
                    for line in user_msg.splitlines():
                        print(f"    {line}")
                    print(f"    ── end prompt ──\n")
            # ──────────────────────────────────────────────────────────────────

            try:
                if tool_call.name == "discard_cards" and allow_discard:
                    cards = tool_call.params.get("cards", [])
                    if len(cards) > 5:
                        print(f"  [warn] discard list has {len(cards)} cards — clamping to 5")
                        cards = cards[:5]
                        tool_call = ToolCall(tool_call.name, {**tool_call.params, "cards": cards})
                    G = bot.discard(cards)
                    discards_used += 1
                elif tool_call.name == "play_hand":
                    G = bot.play(tool_call.params.get("cards", []))
                    hands_used += 1
                else:
                    G = bot.play(tool_call.params.get("cards", [0, 1, 2, 3, 4]))
                    hands_used += 1
            except BalatrobotError as e:
                _log_action(memory, G, tool_call, {"error": str(e)}, prompt=user_msg)
                G = bot.get_gamestate()
                continue

            _log_action(memory, G, tool_call, prompt=user_msg)
            _conv_append(history, tool_call, G.get("state", "?"))

        chips = (G.get("round") or {}).get("chips", 0)
        memory.hand_history.append({
            "ante": memory.ante_num, "round": memory.round_num,
            "hand_type": "mixed", "score": chips,
            "hands_used": hands_used, "discards_used": discards_used,
        })
        if memory.blind_history:
            memory.blind_history[-1]["achieved_score"] = chips
            memory.blind_history[-1]["hands_left_at_finish"] = (G.get("round") or {}).get("hands_left", 0)
        return G


class BoosterPackHandler:
    # Max seconds to spend on a single booster pack before auto-skipping
    PACK_DECISION_TIMEOUT = 30.0

    def handle(self, G: dict, strategy: Strategy, memory: RunMemory,
               gemini: GeminiFlashLiteClient, prompts: PromptBuilder,
               system_prompt: str, bot: BalatrobotClient) -> dict:
        import time as _time
        history: list[dict] = []
        pack_start = _time.monotonic()
        decisions = 0
        while G.get("state") == "SMODS_BOOSTER_OPENED":
            # Auto-skip if pack is taking too long (local models get stuck)
            elapsed = _time.monotonic() - pack_start
            if elapsed > self.PACK_DECISION_TIMEOUT and decisions > 0:
                print(f"  [pack] auto-skip after {elapsed:.0f}s ({decisions} decisions)")
                G = bot.pack(skip=True)
                break
            user_msg = prompts.build_gamestate_prompt(G, memory)
            t0 = _time.monotonic()
            tool_call = gemini.call(system_prompt, user_msg, BOOSTER_PACK_TOOLS, history)
            decisions += 1
            # Also skip immediately if this single LLM call took too long
            if _time.monotonic() - t0 > self.PACK_DECISION_TIMEOUT:
                print(f"  [pack] auto-skip — LLM too slow for pack decisions")
                try:
                    G = bot.pack(skip=True)
                except BalatrobotError:
                    G = bot.get_gamestate()
                break
            try:
                if tool_call.name == "skip_pack":
                    G = bot.pack(skip=True)
                else:
                    idx = tool_call.params.get("index", 0)
                    targets = tool_call.params.get("target_cards") or None
                    G = bot.pack(card=idx, targets=targets)
            except BalatrobotError as e:
                _log_action(memory, G, tool_call, {"error": str(e)}, prompt=user_msg)
                G = bot.get_gamestate()
                continue
            _log_action(memory, G, tool_call, prompt=user_msg)
            _conv_append(history, tool_call, G.get("state", "?"))
        return G


class ShopHandler:
    def __init__(self, booster_handler: BoosterPackHandler):
        self.booster_handler = booster_handler

    def handle(self, G: dict, strategy: Strategy, memory: RunMemory,
               gemini: GeminiFlashLiteClient, prompts: PromptBuilder,
               system_prompt: str, bot: BalatrobotClient) -> dict:
        _record_wallet(memory, G)
        history: list[dict] = []

        while G.get("state") == "SHOP":
            user_msg = prompts.build_gamestate_prompt(G, memory)
            tool_call = gemini.call(system_prompt, user_msg, SHOP_TOOLS, history)

            if tool_call.name == "finish_shop":
                _log_action(memory, G, tool_call, prompt=user_msg)
                break

            cap_ok, cap_msg = self._spend_cap_ok(tool_call, G, strategy)
            if not cap_ok:
                _log_action(memory, G, tool_call, {"rejected": cap_msg}, prompt=user_msg)
                history.append({"role": "assistant",
                                "content": f"Called {tool_call.name}({json.dumps(tool_call.params)})"})
                history.append({"role": "user",
                                "content": f"Rejected: {cap_msg}. Choose a different action."})
                continue

            try:
                G = self._execute(tool_call, G, bot, memory)
            except BalatrobotError as e:
                err_str = str(e)
                _log_action(memory, G, tool_call, {"error": err_str}, prompt=user_msg)
                G = bot.get_gamestate()
                # Tell the LLM what went wrong so it doesn't repeat the same action
                history.append({"role": "assistant",
                                "content": f"Called {tool_call.name}({json.dumps(tool_call.params)})"})
                hint = err_str
                if "joker slots are full" in err_str.lower() or "joker slot" in err_str.lower():
                    jokers = (G.get("jokers") or {}).get("cards") or []
                    joker_limit = (G.get("jokers") or {}).get("limit") or 5
                    # Find the weakest joker (lowest sell value) to suggest selling
                    weakest_idx = 0
                    weakest_sell = 9999
                    for ji, jk in enumerate(jokers):
                        sv = (jk.get("cost") or {}).get("sell", 0)
                        if sv < weakest_sell:
                            weakest_sell = sv
                            weakest_idx = ji
                    hint = (f"{err_str}. "
                            f"Your joker slots are FULL ({len(jokers)}/{joker_limit}). "
                            f"You MUST call sell_joker with an index from your ## Jokers list before buying another joker. "
                            f"Suggested: sell_joker({weakest_idx}) — sells your lowest-value joker for ${weakest_sell}. "
                            "Do NOT call buy_card for a joker again until you have sold one.")
                elif "-32002" in err_str and tool_call.name == "use_consumable":
                    hint = (f"{err_str}. "
                            "This consumable requires target_cards pointing to cards in your hand. "
                            "You do not have a hand available in the shop, so you cannot use it here. "
                            "Choose a different action.")
                history.append({"role": "user", "content": f"Error: {hint}"})
                continue

            _log_action(memory, G, tool_call, prompt=user_msg)
            _conv_append(history, tool_call, G.get("state", "?"))

            if G.get("state") == "SMODS_BOOSTER_OPENED":
                G = self.booster_handler.handle(
                    G, strategy, memory, gemini, prompts, system_prompt, bot,
                )

        G = bot.next_round()
        return G

    @staticmethod
    def _spend_cap_ok(tc: ToolCall, G: dict, strategy: Strategy) -> tuple[bool, str]:
        money = G.get("money", 0)
        ante = G.get("ante_num", 1)
        exempt = ante in strategy.spend.spend_limit_exempt_antes
        if exempt:
            return True, ""
        cap = strategy.spend.spend_limit_pct * money
        if tc.name not in ("buy_card", "buy_voucher", "buy_pack"):
            return True, ""
        idx = tc.params.get("index", 0)
        cost = 0
        if tc.name == "buy_card":
            items = (G.get("shop") or {}).get("cards") or []
        elif tc.name == "buy_voucher":
            items = (G.get("vouchers") or {}).get("cards") or []
        else:
            items = (G.get("packs") or {}).get("cards") or []
        if 0 <= idx < len(items):
            cost = (items[idx].get("cost") or {}).get("buy", 0)
        if cost > cap:
            return False, f"cost ${cost} exceeds spend cap ${cap:.0f} ({int(strategy.spend.spend_limit_pct*100)}% of ${money})"
        return True, ""

    @staticmethod
    def _execute(tc: ToolCall, G: dict, bot: BalatrobotClient,
                 memory: RunMemory) -> dict:
        idx = tc.params.get("index", 0)
        if tc.name == "buy_card":
            items = (G.get("shop") or {}).get("cards") or []
            key = items[idx].get("key", "?") if 0 <= idx < len(items) else "?"
            cost = (items[idx].get("cost") or {}).get("buy", 0) if 0 <= idx < len(items) else 0
            memory.joker_history.append({"ante": G.get("ante_num"),
                                         "action": "buy", "joker_key": key, "cost": cost})
            return bot.buy(card=idx)
        if tc.name == "buy_voucher":
            return bot.buy(voucher=idx)
        if tc.name == "buy_pack":
            return bot.buy(pack=idx)
        if tc.name == "sell_joker":
            jokers = (G.get("jokers") or {}).get("cards") or []
            key = jokers[idx].get("key", "?") if 0 <= idx < len(jokers) else "?"
            sell = (jokers[idx].get("cost") or {}).get("sell", 0) if 0 <= idx < len(jokers) else 0
            memory.joker_history.append({"ante": G.get("ante_num"),
                                         "action": "sell", "joker_key": key, "cost": sell})
            return bot.sell(joker=idx)
        if tc.name == "use_consumable":
            targets = tc.params.get("target_cards") or None
            return bot.use(consumable=idx, cards=targets)
        if tc.name == "reroll_shop":
            return bot.reroll()
        return bot.get_gamestate()
