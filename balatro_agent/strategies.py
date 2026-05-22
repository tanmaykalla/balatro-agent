from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ComboStrategy:
    target_hand: str | None
    keep_mode: str
    main_suit: str | None
    keep_n: int
    max_discards_per_round: int
    waive_limit_last_round: bool
    discard_notes: str = ""


@dataclass
class SpendStrategy:
    planets: list[str]
    jokers: list[str]
    tarots: list[str]
    vouchers: list[str]
    spend_limit_pct: float
    spend_limit_exempt_antes: list[int]
    reroll: bool
    reroll_threshold: int
    voucher_min_wallet: int


@dataclass
class BlindStrategy:
    skip_small: bool
    skip_big: bool
    skip_condition: str


@dataclass
class Strategy:
    name: str
    combo: ComboStrategy
    spend: SpendStrategy
    blind: BlindStrategy


STRATEGIES: dict[str, Strategy] = {
    "FH_TWOPAIR_ECONOMIC": Strategy(
        name="FullHouse_TwoPair_Economic",
        combo=ComboStrategy(
            target_hand="Full House", keep_mode="pairs", main_suit=None,
            keep_n=2, max_discards_per_round=2, waive_limit_last_round=True,
        ),
        spend=SpendStrategy(
            planets=["c_earth", "c_uranus", "c_mercury"],
            jokers=["j_family", "j_mad", "j_duo", "j_jolly", "j_blueprint", "j_brainstorm"],
            tarots=["c_hermit", "c_temperance"], vouchers=[],
            spend_limit_pct=0.8, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=30, voucher_min_wallet=20,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=True, skip_condition="comfortable_margin"),
    ),
    "MULT_STACKER": Strategy(
        name="xMult_Joker_Stacker",
        combo=ComboStrategy(
            target_hand="Full House", keep_mode="pairs", main_suit=None,
            keep_n=2, max_discards_per_round=0, waive_limit_last_round=False,
        ),
        spend=SpendStrategy(
            planets=["c_earth", "c_jupiter"],
            jokers=[
                "j_blueprint", "j_brainstorm", "j_glass", "j_steel", "j_oops",
                "j_acrobat", "j_dusk", "j_hanging_chad", "j_invisible", "j_campfire",
            ],
            tarots=["c_hermit", "c_temperance"], vouchers=[],
            spend_limit_pct=0.9, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=20, voucher_min_wallet=20,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=True, skip_condition="comfortable_margin"),
    ),
    "FLUSH_JOKER_SPECIALIST": Strategy(
        name="Flush_Joker_Specialist",
        combo=ComboStrategy(
            target_hand="Flush", keep_mode="flush_suit", main_suit="H",
            keep_n=2, max_discards_per_round=2, waive_limit_last_round=True,
        ),
        spend=SpendStrategy(
            planets=["c_jupiter"],
            jokers=[
                "j_tribe", "j_droll", "j_crafty", "j_four_fingers", "j_smeared",
                "j_bloodstone", "j_ancient", "j_seeing_double",
            ],
            tarots=["c_hermit", "c_temperance"],
            vouchers=["v_clearance_sale", "v_liquidation"],
            spend_limit_pct=0.8, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=25, voucher_min_wallet=20,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=False, skip_condition="comfortable_margin"),
    ),
    "MONEY_MACHINE": Strategy(
        name="Economy_Money_Machine",
        combo=ComboStrategy(
            target_hand="Two Pair", keep_mode="pairs", main_suit=None,
            keep_n=2, max_discards_per_round=1, waive_limit_last_round=False,
        ),
        spend=SpendStrategy(
            planets=["c_venus", "c_mercury"],
            jokers=[
                "j_todo_list", "j_swashbuckler", "j_bull", "j_bootstraps",
                "j_reserved_parking", "j_rocket", "j_satellite", "j_cloud_9",
            ],
            tarots=["c_hermit", "c_temperance"],
            vouchers=["v_overstock_norm", "v_liquidation", "v_clearance_sale", "v_directors_cut"],
            spend_limit_pct=0.5, spend_limit_exempt_antes=[],
            reroll=True, reroll_threshold=40, voucher_min_wallet=20,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=False, skip_condition="comfortable_margin"),
    ),
    "MERCENARY": Strategy(
        name="Mercenary_Opportunist",
        combo=ComboStrategy(
            target_hand=None, keep_mode="high_card", main_suit=None,
            keep_n=3, max_discards_per_round=2, waive_limit_last_round=True,
        ),
        spend=SpendStrategy(
            planets=[], jokers=[], tarots=["c_hermit", "c_temperance"], vouchers=[],
            spend_limit_pct=0.8, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=30, voucher_min_wallet=20,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=True, skip_condition="comfortable_margin"),
    ),
    "FREE_AGENT": Strategy(
        name="Free_Agent",
        combo=ComboStrategy(
            target_hand=None, keep_mode="high_card", main_suit=None,
            keep_n=3,                       # let model discard up to 2 if it wants
            max_discards_per_round=0,       # 0 == "unlimited" per phase_prompts.py
            waive_limit_last_round=True,
        ),
        spend=SpendStrategy(
            planets=[], jokers=[], tarots=[], vouchers=[],
            spend_limit_pct=1.0, spend_limit_exempt_antes=[1, 2, 3, 4, 5, 6, 7, 8],
            reroll=True, reroll_threshold=0, voucher_min_wallet=0,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=True, skip_condition="comfortable_margin"),
    ),
    "RANDOM_CHAOS": Strategy(
        name="Random_Chaos",
        combo=ComboStrategy(
            target_hand=None, keep_mode="high_card", main_suit=None,
            keep_n=5, max_discards_per_round=1, waive_limit_last_round=False,
        ),
        spend=SpendStrategy(
            planets=[], jokers=[], tarots=[], vouchers=[],
            spend_limit_pct=1.0, spend_limit_exempt_antes=[1, 2, 3, 4, 5, 6, 7, 8],
            reroll=False, reroll_threshold=0, voucher_min_wallet=999,
        ),
        blind=BlindStrategy(skip_small=False, skip_big=False, skip_condition="never"),
    ),
    "OPTIMAL_CHASER": Strategy(
        name="Optimal_Chaser",
        combo=ComboStrategy(
            target_hand=None, keep_mode="high_card", main_suit=None,
            keep_n=2, max_discards_per_round=3, waive_limit_last_round=True,
            discard_notes="""
## Hand Priority — Chase in This Exact Order
Every turn, check if you can build toward a better hand. Chase from top down:
  1. Flush (5 same suit) — highest priority, best chip/mult ratio
  2. Straight (5 consecutive ranks, any suit)
  3. Full House (3-of-a-kind + pair)
  4. Three of a Kind
  5. Two Pair
  6. Pair
  7. High Card — only play if nothing better is achievable

## Discard Rules — Discards Are Your PRIMARY Tool, Not a Last Resort
USE DISCARDS AGGRESSIVELY every turn to build toward your target hand.
Default behaviour: ALWAYS try to discard unless you already have a Flush or Straight.

Step-by-step every SELECTING_HAND turn:
  1. If hands_left=1 OR discards_left=0 → PLAY your best available hand. No exceptions.
  2. Check if you already have a Flush or Straight → PLAY immediately.
  3. Check for Flush draw (4 same suit) → discard the 1 off-suit card. Always.
  4. Check for Flush draw (3 same suit, discards_left ≥ 2) → discard both off-suit cards.
  5. Check for Straight draw (4 consecutive) → discard the 1 non-consecutive card.
  6. Have Three of a Kind → discard the 2 non-matching cards (aim for Full House).
  7. Have Two Pair → discard the 1 kicker card (aim for Full House).
  8. Have One Pair → discard 2 worst non-pair cards (aim for Three of a Kind).
  9. Have High Card only → discard 3 lowest cards, keep highest 2.
  10. Flush draw always beats pair draw — even if you have Two Pair, chase the Flush if 4-to-flush is visible.
  11. Never burn discards for a marginal gain (e.g. Pair → slightly better Pair).

## Joker Buy Priority (Ante 1: buy anything useful; Ante 2+: commit to your build)
  TIER 1 — Always buy (xMult jokers — most powerful):
    Oops! All 6s (×2 mult), Madness (×mult scaling), Glass Joker, Bootstraps, Hologram
  TIER 2 — Buy if affordable (+Mult jokers):
    Supernova, Ride the Bus, Runner, Hack, Blackboard, Scary Face
  TIER 3 — Buy if no Tier 1/2 available (+Chips jokers):
    Walkie Talkie, Smiley Face, Egg, Triboulet, Square Joker
  TIER 4 — Economy only ($ jokers — only buy early if broke):
    Bull, Swashbuckler, Satellite, To Do List

## After Ante 1: Commit to Your Build
  - Identify which hand type you are scoring best with (Flush, Straight, Pairs).
  - Continue buying jokers and planets that reinforce that hand type.
  - Do NOT switch strategy mid-run (e.g. don't buy Flush jokers if you are running pairs).
  - Sell weak jokers to make room for better ones in later antes.
""",
        ),
        spend=SpendStrategy(
            planets=[],   # agent chooses based on what hand it is building
            jokers=[
                # xMult tier (always buy)
                "j_oops", "j_madness", "j_glass", "j_bootstraps", "j_hologram",
                # +Mult tier
                "j_supernova", "j_ride_the_bus", "j_runner", "j_hack", "j_blackboard",
                # Flush boosters
                "j_tribe", "j_droll", "j_four_fingers", "j_smeared",
                # Pair/FH boosters
                "j_family", "j_mad", "j_duo", "j_jolly",
                # Wildcards
                "j_blueprint", "j_brainstorm",
            ],
            tarots=["c_hermit", "c_temperance"],
            vouchers=["v_clearance_sale", "v_overstock_norm"],
            spend_limit_pct=0.85, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=20, voucher_min_wallet=15,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=False, skip_condition="comfortable_margin"),
    ),
    "FLUSH_FAST": Strategy(
        name="Flush_Fast",
        combo=ComboStrategy(
            target_hand="Flush", keep_mode="flush_suit", main_suit=None,
            keep_n=2, max_discards_per_round=3, waive_limit_last_round=True,
            discard_notes="""
## Discard Rules (follow exactly)
1. If you have 5+ same suit → PLAY immediately (Flush complete).
2. If you have 4 same suit → discard the 1 off-suit card.
3. If you have 3 same suit → discard the 2 off-suit cards (if discards_left ≥ 2).
4. If last hand or 0 discards left → play best available hand.
5. Flush > Straight > Full House > everything else. Always chase the flush first.
""",
        ),
        spend=SpendStrategy(
            planets=["c_jupiter", "c_saturn"],
            jokers=["j_tribe", "j_droll", "j_four_fingers", "j_smeared", "j_oops", "j_blueprint"],
            tarots=["c_hermit", "c_temperance"],
            vouchers=["v_clearance_sale"],
            spend_limit_pct=0.75, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=25, voucher_min_wallet=18,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=False, skip_condition="comfortable_margin"),
    ),
    "FH_DISCARD": Strategy(
        name="FullHouse_Discard",
        combo=ComboStrategy(
            target_hand="Full House", keep_mode="pairs", main_suit=None,
            keep_n=2, max_discards_per_round=2, waive_limit_last_round=True,
            discard_notes="""
## Discard Rules (follow exactly)
1. If last hand or 0 discards left → play best available hand immediately.
2. Full House complete → PLAY. Do not discard.
3. Three of a Kind → discard the 2 non-matching cards (fishing for Full House).
4. Two Pair → discard the 1 kicker card (fishing for Full House).
5. One Pair → discard 2-3 worst non-pair cards (fishing for Three of a Kind or Full House).
6. High Card only → discard 3 lowest cards, keep top 2.
7. NEVER burn discards for a marginal improvement (e.g. Pair → slightly better Pair).
""",
        ),
        spend=SpendStrategy(
            planets=["c_earth", "c_uranus", "c_mercury"],
            jokers=["j_family", "j_mad", "j_duo", "j_jolly", "j_blueprint", "j_brainstorm"],
            tarots=["c_hermit", "c_temperance"], vouchers=[],
            spend_limit_pct=0.8, spend_limit_exempt_antes=[1, 2],
            reroll=True, reroll_threshold=30, voucher_min_wallet=20,
        ),
        blind=BlindStrategy(skip_small=True, skip_big=True, skip_condition="comfortable_margin"),
    ),
    "DISCARD_CHASER": Strategy(
        name="Discard_Chaser",
        combo=ComboStrategy(
            target_hand="Flush",
            keep_mode="flush_suit",
            main_suit=None,          # pick dominant suit each hand dynamically
            keep_n=2,
            max_discards_per_round=3,
            waive_limit_last_round=True,
            discard_notes="""
## Discard Decision Tree — Follow This Exactly

Evaluate your hand in this order every time you are in SELECTING_HAND:

**STEP 1 — Never discard if:**
  - You are on the LAST hand (hands_left = 1). Play whatever you have.
  - You have 0 discards left. Play your best available hand.
  - Your best hand already scores enough to reach the remaining chip target.

**STEP 2 — COUNT your suit distribution:**
  Check how many cards you hold in each suit (♠ ♥ ♦ ♣).

**STEP 3 — Apply the first matching rule:**

  RULE A — Flush complete (≥5 same suit):
    → PLAY immediately. Do not discard. This is your target hand.

  RULE B — 4-to-a-Flush (exactly 4 cards of one suit, 1 off-suit):
    → Discard the 1 off-suit card. Always. Even if that card is high-rank.
    → After drawing, you will very likely complete the flush.

  RULE C — 3-to-a-Flush + 2 junk (3 of one suit, the other 2 are different suits):
    → Discard BOTH off-suit junk cards.
    → You draw 2 new cards — good chance to hit the flush suit.
    → Only do this if discards_left ≥ 2.

  RULE D — Straight complete (5 consecutive ranks, any suits):
    → PLAY immediately. Do not discard.

  RULE E — 4-to-a-Straight (4 consecutive ranks, 1 non-consecutive card):
    → Discard the 1 non-consecutive card.
    → Example hand: 7♥ 8♠ 9♦ T♣ K♥ → discard K♥, draw for J or 6.

  RULE F — 4-to-a-Straight with one gap (e.g. 7 8 _ T J — missing 9):
    → Discard the two worst non-straight cards to fish for the gap card.
    → Only if discards_left ≥ 1 and this is not your last hand.

  RULE G — Three of a Kind (no flush draw possible):
    → Discard the 2 non-matching cards.
    → You draw 2; chance of hitting Four of a Kind or Full House.
    → Only if discards_left ≥ 2.

  RULE H — Two Pair (no flush or straight draw):
    → Discard the 1 kicker card (the one that belongs to neither pair).
    → Drawing 1 card gives you a chance at Full House.
    → Only if discards_left ≥ 1.

  RULE I — One Pair, no draw potential:
    → Discard the 3 worst non-pair cards.
    → You draw 3; fishing for Three of a Kind / Full House / Flush.
    → Only if discards_left ≥ 3. If only 1–2 discards left, discard the 1–2 worst.

  RULE J — High Card only (no pair, no draw):
    → Discard the 3–4 lowest-rank cards.
    → Keep your highest 1–2 cards as anchors.
    → Only if discards_left ≥ 2, otherwise play as-is.

**STEP 4 — Flush draw takes priority over pair draws:**
  If Rule B or C applies AND you also have a pair, still discard the off-suit
  cards — a Flush scores more than a Pair (140 vs 20 base) and is more reliable.

**STEP 5 — Minimum improvement threshold:**
  Only discard if the EXPECTED improvement is at least one hand tier higher
  (e.g., Pair → Flush, High Card → Pair). Never burn discards to go from
  Two Pair to a slightly better Two Pair.
""",
        ),
        spend=SpendStrategy(
            planets=["c_jupiter", "c_saturn"],   # Flush + Straight planets
            jokers=[
                # Flush-boosting jokers (highest priority)
                "j_tribe",           # +15 mult when flush played
                "j_droll",           # +10 mult when flush played
                "j_crafty",          # +3 mult for each club in flush hand
                "j_four_fingers",    # flushes/straights in 4 cards (game-changer)
                "j_smeared",         # hearts/diamonds count as same suit
                # Economy / chip floor (survival)
                "j_bull",            # +$2 per $5 held — compounds with interest
                "j_bootstraps",      # +$1 per $2 held — economy engine
                "j_loyaumont",       # +4 mult on flush (if available)
                # Flat chip boosters that fire on any hand
                "j_supernova",       # +mult equal to hand plays this run
                "j_runner",          # +15 chips when straight played
                # xMult wildcards — always buy when seen
                "j_oops",            # ×2 mult — incredibly powerful
                "j_blueprint",       # copies leftmost joker
                "j_brainstorm",      # copies rightmost joker
                "j_glass",           # ×2 mult per Glass card played
            ],
            tarots=["c_hermit", "c_temperance", "c_hanged_man"],
            vouchers=["v_clearance_sale", "v_overstock_norm"],
            spend_limit_pct=0.75,
            spend_limit_exempt_antes=[1, 2],
            reroll=True,
            reroll_threshold=25,
            voucher_min_wallet=18,
        ),
        blind=BlindStrategy(
            skip_small=True,
            skip_big=False,          # only skip small; play big to avoid risk of falling behind
            skip_condition="comfortable_margin",
        ),
    ),
}
