"""
perception.py — Balatro agent core

Sections:
  1. Data models          (Card, GameState, Action)
  2. Perception interface (PerceptionLayer ABC)
  3. Balatrobot impl      (BalatrobotPerception)
  4. Strategy framework   (ComboStrategy, SpendStrategy, BlindStrategy, Strategy)
  5. Strategy runner      (run_strategy)
  6. Card / hand utils    (used by runner and strategies)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
import requests


# ══════════════════════════════════════════════════════════════════════════════
# 1. Data models
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Card:
    index: int      # 0-based position in hand — used in play/discard API calls
    id: int         # game's internal card ID
    key: str        # e.g. "D_K", "S_8"
    suit: str       # "H", "D", "C", "S"
    rank: str       # "A", "K", "Q", "J", "T", "9"…"2"
    debuffed: bool = False   # True when boss blind has nullified this card


@dataclass
class GameState:
    round_num: int
    ante_num: int
    money: int
    chips: int
    hand: List[Card]
    phase: str            # MENU | BLIND_SELECT | SELECTING_HAND | ROUND_EVAL | SHOP | GAME_OVER
    jokers: List[dict]       = field(default_factory=list)
    consumables: List[dict]  = field(default_factory=list)
    shop_cards: List[dict]   = field(default_factory=list)
    pack_cards: List[dict]   = field(default_factory=list)   # contents of an opened booster
    discards_left: int  = 0
    discards_used: int  = 0
    hands_left: int     = 0
    jokers_limit: int   = 5    # max joker slots (parsed from API)
    current_blind: str  = ""   # "small" | "big" | "boss" | ""
    won: bool           = False
    blind_chips_required: int   = 0    # chips needed to beat the active blind
    last_score_margin: float    = 0.0  # last completed round: chips_scored / chips_required
    hands_used_last_round: int  = 0    # hands played in the last completed round


@dataclass
class Action:
    action_type: str          # play | discard | select_blind | skip_blind |
                              # cash_out | next_round | buy | use | reroll
    payload: dict = field(default_factory=dict)
    meta: dict    = field(default_factory=dict)   # logging only — never sent to API


# ══════════════════════════════════════════════════════════════════════════════
# 2. Perception interface
# ══════════════════════════════════════════════════════════════════════════════

class PerceptionLayer(ABC):
    """Swappable interface between agent and game.
    Week 1 = Balatrobot JSON-RPC.  Week 4 = Computer Use."""

    @abstractmethod
    def start_game(self) -> None: ...

    @abstractmethod
    def get_state(self) -> GameState: ...

    @abstractmethod
    def take_action(self, action: Action) -> Optional["GameState"]: ...

    @abstractmethod
    def is_game_over(self) -> bool: ...

    @abstractmethod
    def get_game_over_result(self) -> dict: ...


# ══════════════════════════════════════════════════════════════════════════════
# 3. Balatrobot implementation
# ══════════════════════════════════════════════════════════════════════════════

class BalatrobotPerception(PerceptionLayer):
    """HTTP/JSON-RPC 2.0 wrapper around the Balatrobot mod API (port 12346)."""

    _ACTION_TO_RPC = {
        "play": "play", "discard": "discard",
        "select_blind": "select", "skip_blind": "skip",
        "cash_out": "cash_out", "next_round": "next_round",
        "buy": "buy", "reroll": "reroll", "use": "use", "sell": "sell",
        "pack": "pack",   # booster pack select/skip — distinct from blind select/skip
    }

    def __init__(self, api_url: str = "http://localhost:12346"):
        self.api_url = api_url
        self._last_state: Optional[GameState] = None
        self._rpc_id = 0
        # Round-level tracking for smart blind skipping
        self._last_round_chips: int  = 0
        self._last_round_target: int = 1
        self._round_start_hands: int = 4

    # ── RPC transport ─────────────────────────────────────────────────────────

    def _rpc(self, method: str, params=None, _retries: int = 6) -> dict:
        self._rpc_id += 1
        body: dict = {"jsonrpc": "2.0", "method": method, "id": self._rpc_id}
        if params:
            body["params"] = params

        for attempt in range(_retries):
            try:
                resp = requests.post(
                    self.api_url, json=body, timeout=15,
                    headers={"Connection": "close"},
                )
                resp.raise_for_status()
                result = resp.json()
                if "error" in result:
                    raise RuntimeError(f"RPC error [{method}]: {result['error']}")
                return result.get("result", {})

            except requests.exceptions.ReadTimeout:
                wait = 2 ** attempt   # 1 → 2 → 4 → 8 → 16 → 32 s
                if attempt < _retries - 1:
                    print(f"  [game busy / timeout on '{method}', retrying in {wait}s…]",
                          flush=True)
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"RPC '{method}' timed out after {_retries} attempts — "
                        "game may be stuck on a pop-up."
                    )
            except requests.ConnectionError as exc:
                wait = 2 ** attempt
                if attempt < _retries - 1:
                    print(f"  [connection dropped on '{method}', retrying in {wait}s…]",
                          flush=True)
                    time.sleep(wait)
                else:
                    raise RuntimeError(
                        f"Cannot reach Balatrobot at {self.api_url} after {_retries} attempts. "
                        "Is Balatro running with the mod loaded?"
                    ) from exc

    # ── State parsing ─────────────────────────────────────────────────────────

    def _parse_card(self, raw: dict, index: int) -> Card:
        key   = raw.get("key", "")
        value = raw.get("value", {})
        suit  = value.get("suit", key.split("_")[0] if "_" in key else "")
        rank  = value.get("rank", key.split("_")[1] if "_" in key else "")
        debuffed = bool(raw.get("debuffed") or value.get("debuffed"))
        return Card(index=index, id=raw.get("id", index), key=key,
                    suit=suit, rank=rank, debuffed=debuffed)

    def _parse_state(self, raw: dict) -> GameState:
        ri   = raw.get("round", {})
        hand_raw = raw.get("hand", {})
        cards_raw = hand_raw.get("cards", []) if isinstance(hand_raw, dict) else []

        def _area(key: str) -> List[dict]:
            d = raw.get(key, {})
            return d.get("cards", []) if isinstance(d, dict) else []

        # Determine which blind is currently active (SELECT = choosing, CURRENT = playing)
        current_blind = ""
        for btype in ("small", "big", "boss"):
            if raw.get("blinds", {}).get(btype, {}).get("status") in ("SELECT", "CURRENT"):
                current_blind = btype
                break

        jokers_raw   = raw.get("jokers", {})
        jokers_limit = jokers_raw.get("limit", 5) if isinstance(jokers_raw, dict) else 5

        # Blind chip requirement — look in whichever blind slot is active/selected
        blind_chips = 0
        for btype in ("small", "big", "boss"):
            bdata = raw.get("blinds", {}).get(btype, {})
            if bdata.get("status") in ("SELECT", "CURRENT", "PLAYED"):
                blind_chips = bdata.get("chips", 0)
                break

        # Pack cards — present when a booster pack is open
        pack_raw = raw.get("pack") or raw.get("opened_pack") or {}
        pack_cards_raw = pack_raw.get("cards") or []

        return GameState(
            round_num     = raw.get("round_num", 0),
            ante_num      = raw.get("ante_num", 1),
            money         = raw.get("money", 0),
            chips         = ri.get("chips", 0),
            hand          = [self._parse_card(c, i) for i, c in enumerate(cards_raw)],
            phase         = raw.get("state", "MENU"),
            jokers        = _area("jokers"),
            consumables   = _area("consumables"),
            shop_cards    = _area("shop"),
            pack_cards    = list(pack_cards_raw),
            discards_left = ri.get("discards_left", 0),
            discards_used = ri.get("discards_used", 0),
            hands_left    = ri.get("hands_left", 0),
            jokers_limit  = jokers_limit,
            current_blind = current_blind,
            won           = raw.get("won", False),
            blind_chips_required = blind_chips,
        )

    # ── PerceptionLayer impl ──────────────────────────────────────────────────

    def start_game(self) -> None:
        # Navigate to main menu — retry a few times in case of an animation pop-up
        for attempt in range(4):
            try:
                self._rpc("menu")
                time.sleep(0.8)   # wait for menu transition
                break
            except RuntimeError:
                time.sleep(1.5)
        # Start a new game with a fresh random seed
        result = self._rpc("start", {"deck": "RED", "stake": "WHITE"})
        self._last_state = self._parse_state(result)
        # Reset round-tracking state so margin calculations start clean
        self._last_round_chips  = 0
        self._last_round_target = 1
        self._round_start_hands = 4

    def get_state(self) -> GameState:
        state = self._parse_state(self._rpc("gamestate"))
        prev  = self._last_state

        if prev is not None:
            # Record final score when a round ends
            if prev.phase == "ROUND_EVAL" and state.phase != "ROUND_EVAL":
                self._last_round_chips  = prev.chips
                self._last_round_target = max(prev.blind_chips_required, 1)
            # Record initial hand count when a new round starts
            if prev.phase == "BLIND_SELECT" and state.phase == "SELECTING_HAND":
                self._round_start_hands = state.hands_left

        # Inject tracking into state (fields are mutable dataclass attrs)
        state.last_score_margin   = self._last_round_chips / self._last_round_target
        state.hands_used_last_round = (
            self._round_start_hands - state.hands_left
            if state.phase == "SELECTING_HAND" else 0
        )

        self._last_state = state
        return state

    def take_action(self, action: Action) -> Optional[GameState]:
        method = self._ACTION_TO_RPC.get(action.action_type, action.action_type)
        try:
            raw = self._rpc(method, action.payload or None)
            if raw:
                self._last_state = self._parse_state(raw)
                return self._last_state
            return None
        except RuntimeError as exc:
            err = str(exc)
            if "INVALID_STATE" in err:
                print(f"  [INVALID_STATE on '{action.action_type}' in phase "
                      f"'{self._last_state.phase if self._last_state else '?'}' "
                      f"— refreshing state]", flush=True)
                time.sleep(1.0)
                self.get_state()
            elif "joker slots are full" in err.lower() or "cannot purchase joker" in err.lower():
                # Slots full — sell cheapest joker immediately then let loop retry
                state = self._last_state
                if state and state.jokers:
                    dummy_spend = SpendStrategy()   # empty sell list → sells lowest catalog tier
                    idx = _worst_joker_index(state, dummy_spend)
                    if idx is not None:
                        sell_key = state.jokers[idx].get("key", "?")
                        print(f"  [joker slots full — emergency sell [{sell_key}] idx={idx}]",
                              flush=True)
                        sell_raw = self._rpc("sell", {"joker": idx})
                        if sell_raw:
                            self._last_state = self._parse_state(sell_raw)
                return None
            else:
                raise
        return None

    def is_game_over(self) -> bool:
        return self._last_state is not None and self._last_state.phase == "GAME_OVER"

    def get_game_over_result(self) -> dict:
        state = self.get_state()
        return {
            "ante_reached_at_game_end": state.ante_num,
            "won": state.won,
            "final_money": state.money,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 4. Strategy framework
# ══════════════════════════════════════════════════════════════════════════════
#
#  Every strategy is ONE Strategy object = ComboStrategy + SpendStrategy + BlindStrategy.
#  The runner (Section 5) reads the config and produces Actions — no logic lives
#  inside the strategy dataclasses themselves.
#
# ══════════════════════════════════════════════════════════════════════════════

# ── 4a. Combo strategy ────────────────────────────────────────────────────────

@dataclass
class ComboStrategy:
    """
    Controls SELECTING_HAND decisions (what to play and what to discard).

    target_hand : the hand type to aim for.
                  "Full House" | "Two Pair" | "Three of a Kind" |
                  "Flush" | "Straight" | "Four of a Kind" | "Pair" | "High Card"

    keep_mode   : how to identify keeper cards before discarding.
                  "pairs"      – keep cards that share a rank with another card.
                  "flush_suit" – keep cards matching main_suit (for flush builds).
                  "high_card"  – keep the top N cards by rank value.

    main_suit   : "H" | "D" | "C" | "S" | None
                  Required when keep_mode = "flush_suit".
                  When None with keep_mode = "flush_suit", auto-picks the most
                  common suit in the current hand each turn.

    keep_n      : used only when keep_mode = "high_card". How many cards to keep.
    """
    target_hand: Optional[str] = "Full House"
    # None = no target; always play best available hand, never discard to build
    keep_mode: str           = "pairs"
    # "pairs"      – keep cards sharing a rank
    # "flush_suit" – keep cards matching main_suit (or dominant suit)
    # "high_card"  – keep top keep_n cards by rank value
    # "random"     – discard 1 random card per round (chaos mode)
    main_suit: Optional[str] = None         # "H" | "D" | "C" | "S" | None
    keep_n: int              = 2            # only for keep_mode="high_card"
    max_discards: int        = 0            # max discards to use per round (0 = use all available)


# ── 4b. Spend strategy ────────────────────────────────────────────────────────

@dataclass
class SpendStrategy:
    """
    Controls SHOP decisions (what to buy and use).

    Each list is an ordered priority list of card keys.
    The runner scans the shop left-to-right through these lists, buying the
    first affordable match.  Empty list = never buy that category.

    spend_limit : max $ to spend total per shop visit (0 = no limit).
    reroll      : if True and money > reroll_threshold, reroll once per shop.
    reroll_threshold : minimum money on hand before rerolling is allowed.
    """
    jokers:   List[str] = field(default_factory=list)
    tarots:   List[str] = field(default_factory=list)
    planets:  List[str] = field(default_factory=list)
    vouchers: List[str] = field(default_factory=list)
    spend_limit: int      = 0    # hard $ cap per shop visit (0 = no limit)
    spend_limit_pct: float = 0.0 # fraction of wallet to cap spend (0.0 = disabled)
                                 # e.g. 0.8 = never spend more than 80% of current money
                                 # applied only from ante 3+ (antes 1-2 always spend freely)
    reroll: bool          = False
    reroll_threshold: int = 8
    sell_jokers: List[str] = field(default_factory=list)
    buy_fallback_tier: int = 3
    # 0 = only buy explicitly listed jokers.
    # 1-5 = if nothing on the explicit list is in shop, buy any catalog joker
    #        up to this tier as a fallback (tier 1 = best, 5 = anything).
    # Ordered list of joker keys to sell (sell-first = index 0) when a joker slot is needed.
    # Use jokers.sell_list() to auto-populate from the catalog.
    # Special value "*" = sell the first held joker not in the buy priority list.


# ── 4c. Blind strategy ────────────────────────────────────────────────────────

@dataclass
class BlindStrategy:
    """
    Controls BLIND_SELECT decisions (play vs skip).

    skip_small / skip_big : enable skipping for that blind type.

    skip_probability      : 1.0 = always skip (when enabled), < 1.0 = probabilistic.
    skip_if_margin_above  : only skip if last round score ÷ chip requirement ≥ this value.
                            0.0 = no margin check (always skip when enabled).
                            2.0 = skip only when last score was ≥ 2× the blind target.
    skip_if_hands_le      : only skip if last round was cleared in ≤ this many hands.
                            0 = no hand-count check.
    """
    skip_small: bool  = False
    skip_big:   bool  = False
    skip_probability:     float = 1.0   # < 1.0 → probabilistic skip
    skip_if_margin_above: float = 0.0   # 0 = no margin check
    skip_if_hands_le:     int   = 0     # 0 = no hand-count check


# ── 4d. Top-level Strategy ────────────────────────────────────────────────────

@dataclass
class Strategy:
    """
    A complete named strategy profile.
    Pass one of these to run_strategy() each game tick.
    """
    name:   str
    combo:  ComboStrategy  = field(default_factory=ComboStrategy)
    spend:  SpendStrategy  = field(default_factory=SpendStrategy)
    blind:  BlindStrategy  = field(default_factory=BlindStrategy)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Strategy runner
# ══════════════════════════════════════════════════════════════════════════════

# Phases that indicate a booster/card pack is open for selection.
# Balatrobot maps Balatro's G.STATE to these strings.
_PACK_PHASES = frozenset({
    "TAROT_PACK", "PLANET_PACK", "BUFFOON_PACK", "STANDARD_PACK", "SPECTRAL_PACK",
    "MEGA_STANDARD_PACK", "MEGA_BUFFOON_PACK", "MEGA_ARCANA_PACK", "MEGA_CELESTIAL_PACK",
    "SMODS_BOOSTER_OPENED",         # Steamodded booster state
    "TAROT_PACK_SELECT",
    "OPEN_BOOSTER",
})


def run_strategy(state: GameState, strategy: Strategy) -> Action:
    """
    Translate a Strategy config into a concrete Action for the current game state.
    This is the only function that needs to know about the API; the Strategy
    dataclasses stay pure data.
    """
    phase = state.phase

    # ── Pack selection (tag rewards, booster packs) ───────────────────────────
    if phase in _PACK_PHASES or "PACK" in phase.upper():
        return _pack_action(state, strategy.spend)

    # ── Blind selection ───────────────────────────────────────────────────────
    if phase == "BLIND_SELECT":
        return _blind_action(state, strategy.blind)

    # ── Playing / discarding ──────────────────────────────────────────────────
    if phase == "SELECTING_HAND":
        discard = _combo_discard(state, strategy.combo)
        if discard:
            keys_out = [state.hand[i].key for i in discard.payload["cards"]]
            print(f"  DISCARD {keys_out}  (left={state.discards_left})", flush=True)
            return discard

        hand_type, indices = _combo_play(state, strategy.combo)
        joker_labels = [j.get("label", j.get("key", "?")) for j in state.jokers]
        joker_keys   = [j.get("key", "?") for j in state.jokers]
        print(
            f"  PLAY {hand_type}  "
            f"cards={[state.hand[i].key for i in indices]}  "
            f"jokers=[{', '.join(joker_labels) or 'none'}]",
            flush=True,
        )
        return Action(
            action_type="play",
            payload={"cards": indices},
            meta={"hand_type": hand_type, "joker_keys": joker_keys,
                  "blind": state.current_blind, "ante": state.ante_num},
        )

    # ── Cash out ──────────────────────────────────────────────────────────────
    if phase == "ROUND_EVAL":
        return Action(action_type="cash_out")

    # ── Shop ──────────────────────────────────────────────────────────────────
    if phase == "SHOP":
        # 1. Use any consumables already held
        use = _use_consumable(state, strategy.spend)
        if use:
            key = state.consumables[use.payload["consumable"]].get("key", "?")
            print(f"  USE [{key}]", flush=True)
            return use

        # 2. Sell a low-value joker if slots are full and shop has something wanted
        sell = _sell_for_slot(state, strategy.spend)
        if sell:
            key = state.jokers[sell.payload["joker"]].get("key", "?")
            print(f"  SELL joker [{key}] to make room  (slots={len(state.jokers)}/{state.jokers_limit})", flush=True)
            return sell

        # 3. Buy from shop
        buy = _spend_buy(state, strategy.spend)
        if buy:
            card = state.shop_cards[buy.payload["card"]]
            print(
                f"  BUY [{card.get('label','?')}]  "
                f"${card.get('cost',{}).get('buy','?')}  "
                f"(bank=${state.money})",
                flush=True,
            )
            return buy

        # 4. Reroll if configured and affordable
        if strategy.spend.reroll and state.money >= strategy.spend.reroll_threshold:
            print(f"  REROLL  (bank=${state.money})", flush=True)
            return Action(action_type="reroll")

        return Action(action_type="next_round")

    # ── Game over ─────────────────────────────────────────────────────────────
    if phase == "GAME_OVER":
        return Action(action_type="next_round")   # will be caught by is_game_over() before use

    # ── Unknown phase ─────────────────────────────────────────────────────────
    print(f"  [unknown phase '{phase}' — waiting]", flush=True)
    return Action(action_type="next_round")   # safe no-op: advances or does nothing


# ══════════════════════════════════════════════════════════════════════════════
# 6. Card / hand utilities  (used by runner — not called by strategies directly)
# ══════════════════════════════════════════════════════════════════════════════

RANK_VALUE: Dict[str, int] = {
    "A": 14, "K": 13, "Q": 12, "J": 11, "T": 10,
    "9": 9,  "8": 8,  "7": 7,  "6": 6,  "5": 5,
    "4": 4,  "3": 3,  "2": 2,
}

HAND_RANK: Dict[str, int] = {
    "High Card": 1, "Pair": 2, "Two Pair": 3, "Three of a Kind": 4,
    "Straight": 5, "Flush": 6, "Full House": 7, "Four of a Kind": 8,
}


def _rank_groups(hand: List[Card]) -> List[List[int]]:
    """Group hand indices by rank; sorted best-group-first."""
    groups: dict = {}
    for i, c in enumerate(hand):
        groups.setdefault(c.rank, []).append(i)
    return sorted(
        groups.values(),
        key=lambda g: (len(g), RANK_VALUE.get(hand[g[0]].rank, 0)),
        reverse=True,
    )


def best_hand(hand: List[Card]) -> Tuple[str, List[int]]:
    """Return (hand_type_name, indices) for the best detectable hand."""
    by_size    = _rank_groups(hand)
    pairs_plus = [g for g in by_size if len(g) >= 2]
    trips      = [g for g in by_size if len(g) >= 3]

    if by_size and len(by_size[0]) >= 4:
        return "Four of a Kind", by_size[0][:4]
    if trips:
        others = [g for g in pairs_plus if g is not trips[0]]
        if others:
            return "Full House", trips[0][:3] + others[0][:2]
        return "Three of a Kind", trips[0][:3]
    if len(pairs_plus) >= 2:
        return "Two Pair", pairs_plus[0][:2] + pairs_plus[1][:2]
    if pairs_plus:
        return "Pair", pairs_plus[0][:2]
    best_idx = max(range(len(hand)), key=lambda i: RANK_VALUE.get(hand[i].rank, 0))
    return "High Card", [best_idx]


# ── Blind runner ──────────────────────────────────────────────────────────────

def _blind_action(state: GameState, b: BlindStrategy) -> Action:
    """
    Decide select vs skip.
    Skipping is gated by:
      1. skip_small / skip_big flag
      2. skip_if_margin_above  — skip only if last score ≥ N × blind target
      3. skip_if_hands_le      — skip only if last round cleared in ≤ N hands
      4. skip_probability      — probabilistic gate (< 1.0)
    Boss blinds can never be skipped.
    """
    import random

    want_skip = (
        (state.current_blind == "small" and b.skip_small) or
        (state.current_blind == "big"   and b.skip_big)
    )
    if not want_skip:
        return Action(action_type="select_blind")

    # Margin check: skip only if last round score was comfortable enough
    if b.skip_if_margin_above > 0 and state.last_score_margin < b.skip_if_margin_above:
        print(f"  SELECT {state.current_blind} blind (margin {state.last_score_margin:.1f}x < "
              f"{b.skip_if_margin_above}x threshold — playing it)", flush=True)
        return Action(action_type="select_blind")

    # Hand-count check: skip only if last round finished quickly
    if b.skip_if_hands_le > 0 and state.hands_used_last_round > b.skip_if_hands_le:
        print(f"  SELECT {state.current_blind} blind (used {state.hands_used_last_round} hands last round, "
              f"threshold ≤{b.skip_if_hands_le} — playing it)", flush=True)
        return Action(action_type="select_blind")

    # Probability gate
    if b.skip_probability < 1.0 and random.random() >= b.skip_probability:
        print(f"  SELECT {state.current_blind} blind (prob skip rolled off)", flush=True)
        return Action(action_type="select_blind")

    print(f"  SKIP {state.current_blind} blind  (ante={state.ante_num}, "
          f"margin={state.last_score_margin:.1f}x)", flush=True)
    return Action(action_type="skip_blind")


# ── Combo runner ──────────────────────────────────────────────────────────────

def _combo_discard(state: GameState, c: ComboStrategy) -> Optional[Action]:
    """
    Decide which cards to discard.
    Priority:
      1. Always discard debuffed cards first (they score 0).
      2. Then apply keep_mode / target logic for combo building.
    """
    if state.discards_left <= 0:
        return None
    # Respect per-round discard cap (0 = unlimited)
    if c.max_discards > 0 and state.discards_used >= c.max_discards:
        return None

    # Priority 1: debuffed cards are dead weight — always discard them
    debuffed = [i for i, card in enumerate(state.hand) if card.debuffed]
    if debuffed:
        return Action(action_type="discard", payload={"cards": debuffed[:5]})

    # No target → random discard only (chaos mode)
    if c.target_hand is None and c.keep_mode != "random":
        return None

    # Skip discard if hand already meets or beats target
    if c.target_hand is not None:
        hand_type, _ = best_hand(state.hand)
        if HAND_RANK.get(hand_type, 0) >= HAND_RANK.get(c.target_hand, 7):
            return None

    keepers = _identify_keepers(state.hand, c)
    to_discard = [i for i in range(len(state.hand)) if i not in keepers][:5]
    if not to_discard:
        return None
    return Action(action_type="discard", payload={"cards": to_discard})


def _identify_keepers(hand: List[Card], c: ComboStrategy) -> set:
    """Return set of indices to keep given the combo keep_mode."""
    if c.keep_mode == "flush_suit":
        suit = c.main_suit or _dominant_suit(hand)
        kept = {i for i, card in enumerate(hand) if card.suit == suit}
        # always keep at least 1 card
        if not kept:
            kept = {max(range(len(hand)), key=lambda i: RANK_VALUE.get(hand[i].rank, 0))}
        return kept

    if c.keep_mode == "high_card":
        sorted_idx = sorted(range(len(hand)), key=lambda i: RANK_VALUE.get(hand[i].rank, 0), reverse=True)
        return set(sorted_idx[:c.keep_n])

    if c.keep_mode == "random":
        # Keep all but one randomly chosen card (discard exactly 1 random card)
        import random
        all_idx = list(range(len(hand)))
        if len(all_idx) <= 1:
            return set(all_idx)
        victim = random.choice(all_idx)
        return set(i for i in all_idx if i != victim)

    # default: "pairs" — keep every card that shares a rank with another
    groups = _rank_groups(hand)
    paired = [g for g in groups if len(g) >= 2]
    if paired:
        return {idx for g in paired for idx in g}
    # no pairs — keep highest card
    return {max(range(len(hand)), key=lambda i: RANK_VALUE.get(hand[i].rank, 0))}


def _dominant_suit(hand: List[Card]) -> str:
    """Return the suit that appears most in the hand."""
    counts: Dict[str, int] = {}
    for c in hand:
        counts[c.suit] = counts.get(c.suit, 0) + 1
    return max(counts, key=lambda s: counts[s])


def _combo_play(state: GameState, c: ComboStrategy) -> Tuple[str, List[int]]:
    """
    Select which cards to play. Returns (hand_type_name, indices).

    Always plays EXACTLY 5 cards (or all cards if fewer than 5 in hand).
    After identifying the best scoring hand, the remaining slots are filled with
    the highest-rank cards not already included — extra cards contribute their
    chip face values even when they don't improve the hand type.
    """
    hand = state.hand

    if c.keep_mode == "flush_suit":
        suit = c.main_suit or _dominant_suit(hand)
        flush_cards = [i for i, card in enumerate(hand) if card.suit == suit]
        if len(flush_cards) >= 5:
            return f"Flush ({suit})", flush_cards[:5]
        if len(flush_cards) >= 4:
            # Close enough — pad with one best remaining card
            extras = _top_unused(hand, set(flush_cards[:4]), 1)
            return f"Flush ({suit})", flush_cards[:4] + extras
        # Not enough suited cards — fall through to best_hand

    hand_type, core = best_hand(hand)

    # Pad core up to 5 with highest non-core cards (they add chip face value)
    padded = _pad_to_five(hand, core)
    return hand_type, padded


def _top_unused(hand: List[Card], used: set, n: int) -> List[int]:
    """Return indices of the top-n highest-rank cards not in `used`."""
    available = sorted(
        [i for i in range(len(hand)) if i not in used],
        key=lambda i: RANK_VALUE.get(hand[i].rank, 0),
        reverse=True,
    )
    return available[:n]


def _pad_to_five(hand: List[Card], core: List[int]) -> List[int]:
    """
    Fill `core` up to 5 cards by appending the highest available remaining cards.
    Returns at most 5 indices, at least len(core).
    """
    if len(core) >= 5:
        return core[:5]
    extras = _top_unused(hand, set(core), 5 - len(core))
    return core + extras


# ── Spend runner ──────────────────────────────────────────────────────────────

# Planet cards — always auto-use, no target cards needed
_PLANET_KEYS = {
    "c_earth", "c_uranus", "c_venus", "c_mercury",
    "c_mars", "c_jupiter", "c_saturn", "c_neptune", "c_pluto",
    "c_eris", "c_ceres", "c_planet_x",
}

# Tarots that need no target cards
_AUTO_TAROTS = {
    "c_hermit", "c_high_priestess", "c_emperor", "c_wheel_of_fortune",
    "c_fool", "c_judgement", "c_temperance",
}

# Tarots that require N hand-card targets
# Strategy: pick best N cards (highest rank) as enhancement targets;
#            for destructive tarots (hanged_man) pick the worst N instead.
_TAROT_TARGET_COUNT: Dict[str, int] = {
    "c_magician":   2,   # Lucky to 2 cards
    "c_empress":    2,   # Mult enhancement to 2 cards
    "c_hierophant": 2,   # Bonus to 2 cards
    "c_strength":   2,   # +1 rank to 2 cards
    "c_hanged_man": 2,   # destroys 2 cards  (we pick worst)
    "c_death":      2,   # converts left card type to right
    "c_lovers":     1,   # Wild Card to 1 card
    "c_chariot":    1,   # Steel to 1 card
    "c_justice":    1,   # Glass to 1 card
    "c_devil":      1,   # Gold to 1 card
    "c_tower":      1,   # Stone to 1 card
    "c_star":       3,   # converts 3 to Diamonds
    "c_moon":       3,   # converts 3 to Clubs
    "c_sun":        3,   # converts 3 to Hearts
    "c_world":      3,   # converts 3 to Spades
}
_DESTRUCTIVE_TAROTS = {"c_hanged_man"}


def _use_consumable(state: GameState, s: SpendStrategy) -> Optional[Action]:
    """
    Use the highest-priority consumable we're holding.
    Planets are auto-used immediately.
    Tarots that need target cards receive the best (or worst) cards from hand.
    """
    wanted = set(s.planets) | set(s.tarots)

    def _make_use(i: int, key: str) -> Action:
        n = _TAROT_TARGET_COUNT.get(key, 0)
        if n == 0 or not state.hand:
            return Action(action_type="use", payload={"consumable": i})
        # Pick target card indices
        sorted_by_rank = sorted(range(len(state.hand)),
                                key=lambda j: RANK_VALUE.get(state.hand[j].rank, 0),
                                reverse=(key not in _DESTRUCTIVE_TAROTS))
        targets = sorted_by_rank[:min(n, len(state.hand))]
        return Action(action_type="use", payload={"consumable": i, "cards": targets})

    # 1. Use wanted consumable (priority list match)
    for i, card in enumerate(state.consumables):
        key = card.get("key", "")
        if key in wanted and (key in _PLANET_KEYS or key in _AUTO_TAROTS or key in _TAROT_TARGET_COUNT):
            return _make_use(i, key)

    # 2. Use any planet immediately (always beneficial)
    for i, card in enumerate(state.consumables):
        key = card.get("key", "")
        if key in _PLANET_KEYS:
            return _make_use(i, key)

    # 3. Use any other auto-tarot or target-tarot we happen to be holding
    for i, card in enumerate(state.consumables):
        key = card.get("key", "")
        if key in _AUTO_TAROTS or key in _TAROT_TARGET_COUNT:
            return _make_use(i, key)

    return None


def _spend_buy(state: GameState, s: SpendStrategy) -> Optional[Action]:
    """
    Buy the best affordable item according to spend priority lists.
    If no explicit-list joker is available, falls back to buying any catalog
    joker up to s.buy_fallback_tier (0 = disabled).
    """
    from jokers import JOKER_CATALOG

    # Compute effective wallet cap for this visit
    effective_limit = s.spend_limit
    if s.spend_limit_pct > 0.0 and state.ante_num >= 3:
        pct_cap = int(state.money * s.spend_limit_pct)
        effective_limit = pct_cap if effective_limit == 0 else min(effective_limit, pct_cap)

    best_idx, best_score = None, (999, 999, 999)

    for i, card in enumerate(state.shop_cards):
        key  = card.get("key", "")
        cost = card.get("cost", {}).get("buy", 9999)
        cset = card.get("set", "").upper()   # normalise — API may return "Joker"/"JOKER"

        if effective_limit and cost > effective_limit:
            continue
        if cost > state.money:
            continue

        if   cset == "PLANET"  and key in s.planets:
            score = (1, s.planets.index(key), 0)
        elif cset == "JOKER"   and key in s.jokers:
            score = (2, s.jokers.index(key), 0)
        elif cset == "JOKER"   and "*" in s.jokers:
            score = (2, 9999, cost)           # wildcard: cheapest joker
        elif cset == "TAROT"   and key in s.tarots:
            score = (3, s.tarots.index(key), 0)
        elif cset == "VOUCHER" and key in s.vouchers:
            score = (4, s.vouchers.index(key), 0)
        elif (cset == "JOKER" and s.buy_fallback_tier > 0
              and key not in s.jokers and "*" not in s.jokers):
            # Fallback: buy catalog joker if its buy_tier is within the allowed tier.
            # Unknown jokers (not in catalog) get a neutral tier of 4 so they are
            # purchased when buy_fallback_tier >= 4.
            tier = JOKER_CATALOG.get(key, {}).get("buy_tier", 4)
            if tier <= s.buy_fallback_tier:
                score = (5, tier, cost)       # lower priority than explicit buys
            else:
                continue
        else:
            continue

        if score < best_score:
            best_score, best_idx = score, i

    if best_idx is not None:
        return Action(action_type="buy", payload={"card": best_idx})

    # Debug: log shop contents when nothing is bought so we can diagnose key/set mismatches
    if state.shop_cards:
        items = [(c.get("key","?"), c.get("set","?"), c.get("cost",{}).get("buy","?"))
                 for c in state.shop_cards]
        print(f"  [shop pass — nothing matched. items={items}  "
              f"cap=${effective_limit or '∞'}  wallet=${state.money}]", flush=True)
    return None


# ── Pack runner ──────────────────────────────────────────────────────────────

def _pack_action(state: GameState, s: SpendStrategy) -> Action:
    """
    Handle booster pack / tag reward selection.

    Pack choices come through state.shop_cards (Balatrobot exposes them there).
    If a wanted tarot/planet/joker is in the pack, select it.
    Otherwise skip the pack entirely.

    API:
      select  → {"card": 0-based-index}  picks a card from the pack
      skip    → (no params)              closes the pack without taking anything
    """
    wanted = (set(s.tarots) | set(s.planets) | (set(s.jokers) - {"*"}))

    # Prefer pack_cards (opened booster); fall back to shop_cards (tag rewards)
    choices = state.pack_cards if state.pack_cards else state.shop_cards
    for i, card in enumerate(choices):
        key = card.get("key", "")
        if key in wanted:
            print(f"  SELECT pack [{key}] (index {i})", flush=True)
            return Action(action_type="pack", payload={"card": i})

    print(f"  SKIP pack (nothing wanted from {[c.get('key','?') for c in choices]})", flush=True)
    return Action(action_type="pack", payload={"skip": True})


# ── Sell runner ──────────────────────────────────────────────────────────────

def _worst_joker_index(state: GameState, s: SpendStrategy) -> Optional[int]:
    """
    Return the index (in state.jokers) of the joker most worth selling.
    Priority:
      1. First match in s.sell_jokers list (explicit sell order)
      2. Any joker NOT in s.jokers (not wanted)
      3. Last joker in the list (oldest acquired, lowest priority by default)
    """
    from jokers import JOKER_CATALOG
    # Explicit sell list
    for sell_key in s.sell_jokers:
        if sell_key == "*":
            continue
        for i, joker in enumerate(state.jokers):
            if joker.get("key", "") == sell_key:
                return i
    # Wildcard / fallback: joker not in our buy list
    keep_keys = set(s.jokers) - {"*"}
    for i, joker in enumerate(state.jokers):
        if joker.get("key", "") not in keep_keys:
            return i
    # All jokers are wanted — sell the one with the LOWEST sell_tier (most expendable).
    # sell_tier 1 = dump first, sell_tier 5 = keep always.
    worst_sell_i, worst_sell_t = 0, 999
    for i, joker in enumerate(state.jokers):
        t = JOKER_CATALOG.get(joker.get("key", ""), {}).get("sell_tier", 3)
        if t < worst_sell_t:
            worst_sell_t, worst_sell_i = t, i
    return worst_sell_i if state.jokers else None


def _sell_for_slot(state: GameState, s: SpendStrategy) -> Optional[Action]:
    """
    Sell the lowest-priority held joker if joker slots are full AND the shop
    contains any joker (wanted or fallback-tier).

    Normalises the 'set' field to uppercase to handle Balatrobot casing variants.
    """
    if len(state.jokers) < state.jokers_limit:
        return None  # still have open slots — no need to sell

    # Check if shop has any joker at all (uppercase normalised)
    def shop_has_joker() -> bool:
        for card in state.shop_cards:
            if card.get("set", "").upper() == "JOKER":
                return True
        return False

    if not shop_has_joker():
        return None

    idx = _worst_joker_index(state, s)
    if idx is None:
        return None
    return Action(action_type="sell", payload={"joker": idx})


# ══════════════════════════════════════════════════════════════════════════════
# Backwards-compat alias
# ══════════════════════════════════════════════════════════════════════════════

def smart_full_house_strategy(state: GameState) -> Action:
    """Legacy wrapper — uses the default Full House Hunter strategy."""
    return run_strategy(state, FULL_HOUSE_HUNTER)


# Placeholder — will be replaced once real strategies are defined below
FULL_HOUSE_HUNTER = Strategy(
    name="Full House Hunter",
    combo=ComboStrategy(
        target_hand="Full House",
        keep_mode="pairs",
    ),
    spend=SpendStrategy(
        planets=["c_earth", "c_uranus", "c_venus", "c_mercury"],
        jokers=["j_mad", "j_zany", "j_jolly", "j_joker", "j_supernova", "j_green_joker", "j_banner"],
        tarots=["c_hermit", "c_high_priestess", "c_emperor"],
        vouchers=[],
    ),
    blind=BlindStrategy(skip_small=False, skip_big=False),
)
