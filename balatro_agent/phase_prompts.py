from __future__ import annotations
from collections import Counter
from itertools import combinations
from strategies import Strategy
from agent_memory import RunMemory


RANK_ORDER = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"T":10,"10":10,
              "J":11,"Q":12,"K":13,"A":14}


def _card_rank(c: dict) -> int:
    v = c.get("value") or {}
    r = v.get("rank", c.get("rank", "?"))
    return RANK_ORDER.get(str(r), 0)


def _card_suit(c: dict) -> str:
    v = c.get("value") or {}
    return v.get("suit", c.get("suit", "?"))


def _hand_name(cards: list[dict]) -> str | None:
    """Return the best poker hand name for exactly 5 cards, or None."""
    if len(cards) != 5:
        return None
    ranks = sorted([_card_rank(c) for c in cards], reverse=True)
    suits = [_card_suit(c) for c in cards]
    counts = sorted(Counter(ranks).values(), reverse=True)
    is_flush    = len(set(suits)) == 1
    is_straight = (len(set(ranks)) == 5 and ranks[0] - ranks[4] == 4) or \
                  (set(ranks) == {14, 2, 3, 4, 5})  # wheel

    if is_straight and is_flush:
        return "Straight Flush"
    if counts[0] == 4:
        return "Four of a Kind"
    if counts[0] == 3 and counts[1] == 2:
        return "Full House"
    if is_flush:
        return "Flush"
    if is_straight:
        return "Straight"
    if counts[0] == 3:
        return "Three of a Kind"
    if counts[0] == 2 and counts[1] == 2:
        return "Two Pair"
    if counts[0] == 2:
        return "Pair"
    return "High Card"


# Hand score priority for ranking
_HAND_RANK = {
    "Straight Flush": 8, "Four of a Kind": 7, "Full House": 6,
    "Flush": 5, "Straight": 4, "Three of a Kind": 3,
    "Two Pair": 2, "Pair": 1, "High Card": 0,
}


def _detect_hands(hand_cards: list[dict]) -> list[str]:
    """Return human-readable lines showing the best playable hands with card indices."""
    if not hand_cards:
        return []

    seen: dict[str, tuple] = {}  # hand_name → (indices, rank)
    n = len(hand_cards)
    play_size = min(5, n)

    for combo in combinations(range(n), play_size):
        cards = [hand_cards[i] for i in combo]
        name = _hand_name(cards)
        if name is None:
            continue
        rank = _HAND_RANK.get(name, 0)
        if name not in seen or rank > seen[name][1]:
            seen[name] = (list(combo), rank)

    if not seen:
        return ["No hands detected"]

    lines = []
    for name, (indices, _) in sorted(seen.items(), key=lambda x: -x[1][1]):
        def _card_label(c: dict) -> str:
            v = c.get("value") or {}
            r = v.get("rank", c.get("rank", "?"))
            s = v.get("suit", c.get("suit", "?"))
            return f"{r}{s}"
        card_labels = [_card_label(hand_cards[i]) for i in indices]
        lines.append(f"{name}: play indices {indices}  ({', '.join(card_labels)})")
    return lines

GAME_KNOWLEDGE = """You are an expert Balatro player making decisions in a live game.

## Goal

Beat all 8 antes. Each ante has 3 blinds: Small → Big → Boss.
You win by clearing the Boss blind of Ante 8.
Each blind has a chip target. You must reach it by playing poker hands.
You lose a blind if you run out of hands before reaching the target.

## How Scoring Works

Every hand you play scores:  CHIPS × MULT  =  final score added to your total.

CHIPS come from:
  - Base chips for the hand type (see table below)
  - +10 chips per scoring card that has chip enhancements
  - Each face card (J, Q, K) = 10 chips, Ace = 11, number cards = face value

MULT comes from:
  - Base mult for the hand type
  - Flat +Mult bonuses from jokers, enhancements, seals
  - xMult multipliers applied AFTER all flat bonuses (extremely powerful)

Example: Full House base = 40 chips × 4 mult = 160.
  Add joker giving +10 mult → 40 × 14 = 560.
  Add joker giving ×2 mult → 40 × 28 = 1120.
  xMult stacks multiply each other — two ×2 jokers = ×4 total.

## Poker Hands — Base Score and Priority

Play the HIGHEST scoring hand you can make every time.

  Hand              Base Chips  Base Mult  Score  Notes
  ──────────────────────────────────────────────────────
  High Card              5         1         5    Worst — avoid unless no choice
  Pair                  10         2        20    Only use if nothing better
  Two Pair              20         2        40    Decent early game
  Three of a Kind       30         3        90    Good
  Straight              30         4       120    5 consecutive ranks (A can be low or high)
  Flush                 35         4       140    5 same suit — very consistent
  Full House            40         4       160    Pair + Three of a Kind
  Four of a Kind        60         7       420    Excellent
  Straight Flush       100         8       800    Outstanding
  Royal Flush          100         8       800    A K Q J 10 same suit
  Five of a Kind       120        12      1440    Requires joker effects

IMPORTANT: Each hand type can be leveled up with Planet cards.
  Each level adds +15 chips and +1 mult to that hand type permanently.
  A leveled-up Pair scores much better than a base Flush if you have planets.

## Discard Strategy

You have a limited number of discards per round. Use them wisely.

GOOD reasons to discard:
  - You have 4 cards of the same suit and can complete a Flush (discard the off-suit card)
  - You have 4 consecutive cards and can complete a Straight (discard the gap card)
  - You have 3-of-a-kind and can try for 4-of-a-kind
  - You have two separate pairs and can try for Full House or better
  - Your best available hand scores far below the blind target

BAD reasons to discard:
  - You already have a Flush or Straight — do NOT discard, just play it
  - You are on your last hand — play whatever you have, discards wasted
  - Your current hand already beats the remaining target needed

ALWAYS ask: "Does my current hand + remaining hands cover the target?
  If yes, play now. If no, consider whether a discard significantly improves it."

## Card Values for Chips

  Ace = 11 chips    King = 10    Queen = 10    Jack = 10
  10 = 10           9 = 9        8 = 8         7 = 7
  6 = 6             5 = 5        4 = 4         3 = 3    2 = 2

Only cards that SCORE contribute chips (i.e., the cards that make the hand).
Kicker cards in pairs/two-pair DO contribute chips even if they don't form the combo.

## Game Loop

  BLIND_SELECT  → pick a blind to play or skip (boss cannot be skipped)
  SELECTING_HAND → play or discard until you beat the target
  ROUND_EVAL    → automatic cash-out, nothing to do
  SHOP          → buy items, sell jokers, reroll
  repeat until Ante 8 done or game over

## Items — What to Buy

JOKERS (most important):
  - +Chips jokers: add flat chips to every hand. Good early.
  - +Mult jokers: add flat mult. Better than +chips late game.
  - xMult jokers: multiply total mult. Best in the game. Always buy.
  - Hand-type jokers: only fire when you play their specific hand. Buy only if
    you consistently play that hand type.
  - Economy jokers: give money. Good early for compounding interest.
  Joker slots = 5 by default. Sell your weakest joker if slots are full
  and a clearly better one appears.

PLANET CARDS (second most important):
  Level up whichever hand you play most. Each level = +15 chips +1 mult.
  Use them immediately — they stack permanently for the whole run.

TAROT CARDS:
  Powerful one-time effects: enhance cards (foil/holographic/polychrome),
  change suits, add seals, duplicate cards. Use before leaving the shop.
  The Hermit (c_hermit): doubles your money. Buy early every time.
  The Temperance (c_temperance): gives money equal to total joker sell value.

VOUCHERS:
  Permanent upgrades. High long-term value. Buy early if you can afford them.
  Examples: Overstock (extra shop slot), Clearance Sale (20% discount),
  Director's Cut (reroll discount).

PACKS:
  Arcana Pack = tarot cards, Celestial Pack = planet cards,
  Buffoon Pack = jokers, Standard Pack = playing cards.
  Buffoon Packs are highest priority — extra joker selection.

## Economy

INTEREST: +$1 for every $5 you hold at end of round (max +$5/round).
  Holding $20 gives +$4 per round. This compounds — save when you can.
  Do NOT overspend early just to buy marginal items.

REROLL: Costs $5, goes up $1 each reroll (resets next shop).
  Only reroll if: shop has nothing useful AND you have $10+ spare.

## Blind Skipping

Skipping Small or Big blind gives a TAG reward (free joker, planet, etc.).
NEVER skip the Boss blind — not an option.
Skip when you won the last blind comfortably (score was ≥2× target or had hands left over).
Select when you are behind on scoring power and need the practice round.

## Decision Rules — Follow These Every Time

1. Always fill in `reasoning` — explain which hand you chose and why.
2. SELECTING_HAND:
   a. Check the PLAYABLE HANDS section below — use those exact indices.
   b. Compare the best available hand to the remaining target needed.
   c. If the best hand + remaining hands can reach the target, play it.
   d. If not, consider discarding to improve — but only if the improvement is clear.
   e. On the LAST hand, always play — discards are wasted.
3. SHOP:
   a. Check what you can afford (interest rule: keep $5 multiples if possible).
   b. Buy xMult jokers first, then +Mult, then Planets, then everything else.
   c. Use any tarot/planet consumables you are holding before finishing shop.
   d. Only reroll if nothing useful is in the shop and you have spare cash.
4. Never play High Card if ANY better hand is available.
5. Never discard part of a completed Flush or Straight.
"""


class PromptBuilder:
    def build_system_prompt(self, strategy: Strategy) -> str:
        c = strategy.combo
        s = strategy.spend
        b = strategy.blind
        is_free = not c.target_hand and not s.jokers and not s.planets

        if is_free:
            strategy_section = (
                f"\n## Personality: {strategy.name}\n"
                "You have full autonomy. Read the game state and make the best "
                "decisions you can — there are no hard constraints on what to buy, "
                "play, or skip. Use your game knowledge to win."
            )
        else:
            discard_limit = str(c.max_discards_per_round) if c.max_discards_per_round else "unlimited"
            strategy_section = f"""
## Personality: {strategy.name}

- Target hand: {c.target_hand or "your choice"}
- Joker priority (buy these first): {s.jokers or "[opportunistic]"}
- Planet priority: {s.planets or "[none]"}
- Tarot targets: {s.tarots or "[none]"}
- Voucher priority: {s.vouchers or "[none]"}
- Spend cap: {int(s.spend_limit_pct * 100)}% of wallet (exempt in antes: {s.spend_limit_exempt_antes})
- Reroll: {"yes, when wallet >= $" + str(s.reroll_threshold) if s.reroll else "no"}
- Max discards per round: {discard_limit}
- Skip condition: {b.skip_condition} (skip small={b.skip_small}, skip big={b.skip_big})
"""
            if c.discard_notes:
                strategy_section += c.discard_notes
        return GAME_KNOWLEDGE + strategy_section

    def build_gamestate_prompt(self, G: dict, memory: RunMemory) -> str:
        state = G.get("state", "UNKNOWN")
        ante = G.get("ante_num", "?")
        round_num = G.get("round_num", "?")
        money = G.get("money", 0)
        round_info = G.get("round", {}) or {}
        hands_left = round_info.get("hands_left", "?")
        discards_left = round_info.get("discards_left", "?")
        chips = round_info.get("chips", 0)

        parts: list[str] = []
        parts.append(f"# Phase: {state} | Ante {ante} Round {round_num}")
        parts.append(f"Money: ${money} | Hands left: {hands_left} | Discards left: {discards_left}")

        blinds = G.get("blinds") or {}
        if blinds:
            cur = blinds.get("current") or blinds.get("active") or {}
            target = cur.get("chips") or cur.get("score") or cur.get("target")
            if target:
                parts.append(f"Blind target: {target} | Chips scored so far: {chips}")

        hand_cards = (G.get("hand") or {}).get("cards") or []
        if hand_cards:
            parts.append("\n## Hand")
            for i, c in enumerate(hand_cards):
                v = c.get("value") or {}
                rank = v.get("rank", c.get("rank", "?"))
                suit = v.get("suit", c.get("suit", "?"))
                label = c.get("label", f"{rank}{suit}")
                parts.append(f"  [{i}] {label} ({rank} of {suit})")
            # Pre-compute best hands so agent doesn't have to
            parts.append(f"\n## PLAYABLE HANDS (use these exact indices — do not guess)")
            parts.append(f"  ⚠ DISCARD LIMIT: maximum 5 card indices per discard call")
            for line in _detect_hands(hand_cards):
                parts.append(f"  {line}")

        jokers = (G.get("jokers") or {}).get("cards") or []
        joker_limit = (G.get("jokers") or {}).get("limit") or 5
        joker_count = len(jokers)
        slots_full = joker_count >= joker_limit
        slot_warn = " ⚠ SLOTS FULL — must sell a joker before buying another" if slots_full else f" ({joker_count}/{joker_limit} slots used)"
        parts.append(f"\n## Jokers{slot_warn}")
        for i, j in enumerate(jokers):
            sell = (j.get("cost") or {}).get("sell", "?")
            parts.append(f"  [{i}] {j.get('label', j.get('key', '?'))} (sell ${sell})")
        if slots_full:
            parts.append("  → Use sell_joker [index] to free a slot before buying.")

        consumables = (G.get("consumables") or {}).get("cards") or []
        if consumables:
            parts.append("\n## Consumables")
            for i, c in enumerate(consumables):
                parts.append(f"  [{i}] {c.get('label', c.get('key', '?'))}")

        if state == "SHOP":
            shop_cards = (G.get("shop") or {}).get("cards") or []
            vouchers = (G.get("vouchers") or {}).get("cards") or []
            packs = (G.get("packs") or {}).get("cards") or []
            reroll_cost = round_info.get("reroll_cost", "?")
            parts.append(f"\n## Shop (reroll cost ${reroll_cost})")
            if shop_cards:
                parts.append("Cards:")
                for i, sc in enumerate(shop_cards):
                    cost = (sc.get("cost") or {}).get("buy", "?")
                    parts.append(
                        f"  [{i}] {sc.get('label', sc.get('key', '?'))} "
                        f"({sc.get('set', '?')}) — ${cost}"
                    )
            if vouchers:
                parts.append("Vouchers:")
                for i, v in enumerate(vouchers):
                    cost = (v.get("cost") or {}).get("buy", "?")
                    parts.append(f"  [{i}] {v.get('label', v.get('key', '?'))} — ${cost}")
            if packs:
                parts.append("Packs:")
                for i, p in enumerate(packs):
                    cost = (p.get("cost") or {}).get("buy", "?")
                    parts.append(f"  [{i}] {p.get('label', p.get('key', '?'))} — ${cost}")

        if state == "SMODS_BOOSTER_OPENED":
            pack = G.get("pack") or G.get("opened_pack") or {}
            cards = pack.get("cards") or []
            if cards:
                parts.append("\n## Pack Contents")
                for i, c in enumerate(cards):
                    parts.append(f"  [{i}] {c.get('label', c.get('key', '?'))}")

        parts.append("\n" + memory.to_summary_prompt())
        return "\n".join(parts)
