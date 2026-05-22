# strategy.py — all strategy profiles
# Change ACTIVE to switch which strategy runs in main.py

from perception import (
    Strategy, ComboStrategy, SpendStrategy, BlindStrategy,
    run_strategy, best_hand, RANK_VALUE, HAND_RANK,
)
from jokers import buy_list, sell_list


# ── St1 : FH_2P ───────────────────────────────────────────────────────────────
# Full House primary, Two Pair fallback.
# Skip blinds only when scoring well (margin ≥ 2×) or cleared fast (≤ 2 hands).

FH_2P = Strategy(
    name="FullHouse_TwoPair_Economic",
    combo=ComboStrategy(
        target_hand  = "Full House",
        keep_mode    = "pairs",
        main_suit    = None,
        keep_n       = 2,
        max_discards = 2,
    ),
    spend=SpendStrategy(
        planets  = ["c_earth", "c_uranus", "c_mercury"],
        jokers   = [
            "j_family", "j_mad", "j_duo", "j_jolly",
            "j_blueprint", "j_brainstorm", "j_glass",
        ],
        tarots           = ["c_hermit", "c_temperance"],
        vouchers         = [],
        spend_limit      = 0,
        spend_limit_pct  = 0.8,
        reroll           = True,
        reroll_threshold = 30,
        sell_jokers      = sell_list(max_sell_tier=2),
        buy_fallback_tier = 4,   # buy any tier-1–4 joker as fallback
    ),
    blind=BlindStrategy(
        skip_small           = True,
        skip_big             = True,
        skip_if_margin_above = 2.0,   # skip only if last score > 2× blind target
        skip_if_hands_le     = 2,     # skip only if cleared in ≤ 2 hands
    ),
)


# ── St2 : FH_TWOPAIR_STRATEGY ─────────────────────────────────────────────────
# Full House primary, Two Pair fallback. Leaner joker list.
# Same blind skip logic as St1.

FH_TWOPAIR_STRATEGY = Strategy(
    name="FullHouse_TwoPair_Economic_v2",
    combo=ComboStrategy(
        target_hand  = "Full House",
        keep_mode    = "pairs",
        main_suit    = None,
        keep_n       = 2,
        max_discards = 2,
    ),
    spend=SpendStrategy(
        planets  = ["c_earth", "c_uranus", "c_mercury"],
        jokers   = [
            "j_family", "j_mad", "j_duo", "j_jolly",
            "j_blueprint", "j_brainstorm",
        ],
        tarots           = ["c_hermit", "c_temperance"],
        vouchers         = [],
        spend_limit      = 0,
        spend_limit_pct  = 0.8,
        reroll           = True,
        reroll_threshold = 30,
        sell_jokers      = sell_list(max_sell_tier=2),
        buy_fallback_tier = 4,   # buy any tier-1–4 joker as fallback
    ),
    blind=BlindStrategy(
        skip_small           = True,
        skip_big             = True,
        skip_if_margin_above = 2.0,
        skip_if_hands_le     = 2,
    ),
)


# ── St3 : MULT_STACKER ────────────────────────────────────────────────────────
# Purely focused on stacking xMult jokers.
# Skips blinds probabilistically (60%) — every $ saved is a reroll.

MULT_STACKER = Strategy(
    name="xMult_Joker_Stacker",
    combo=ComboStrategy(
        target_hand  = "Full House",
        keep_mode    = "pairs",
        main_suit    = None,
        keep_n       = 2,
        max_discards = 0,
    ),
    spend=SpendStrategy(
        planets  = ["c_earth", "c_jupiter"],
        jokers   = [
            "j_blueprint", "j_brainstorm", "j_glass", "j_steel_joker",
            "j_oops", "j_acrobat", "j_dusk", "j_hanging_chad",
            "j_invisible", "j_campfire",
        ],
        tarots           = ["c_hermit", "c_temperance"],
        vouchers         = [],
        spend_limit      = 0,
        spend_limit_pct  = 0.9,
        reroll           = True,
        reroll_threshold = 20,
        sell_jokers      = sell_list(max_sell_tier=3),
        buy_fallback_tier = 2,   # aggressively buy tier-1/2 xMult jokers as fallback
    ),
    blind=BlindStrategy(
        skip_small       = True,
        skip_big         = True,
        skip_probability = 0.6,    # 60% chance to skip — probabilistic
    ),
)


# ── St4 : FLUSH_JOKER_SPECIALIST ─────────────────────────────────────────────
# Locks into Hearts flush, never deviates.
# Conservative skip — flush needs consistent scoring.

FLUSH_JOKER_SPECIALIST = Strategy(
    name="Flush_Joker_Specialist",
    combo=ComboStrategy(
        target_hand  = "Flush",
        keep_mode    = "flush_suit",
        main_suit    = "H",
        keep_n       = 2,
        max_discards = 2,
    ),
    spend=SpendStrategy(
        planets  = ["c_jupiter"],
        jokers   = [
            "j_the_tribe", "j_droll", "j_crafty",
            "j_four_fingers", "j_smeared_joker",
            "j_bloodstone", "j_ancient", "j_seeing_double",
        ],
        tarots           = ["c_hermit", "c_temperance"],
        vouchers         = ["v_clearance_sale", "v_liquidation"],
        spend_limit      = 0,
        spend_limit_pct  = 0.8,
        reroll           = True,
        reroll_threshold = 25,
        sell_jokers      = sell_list(max_sell_tier=2),
        buy_fallback_tier = 4,   # buy any tier-1–4 joker as fallback
    ),
    blind=BlindStrategy(
        skip_small           = True,
        skip_big             = False,
        skip_if_margin_above = 2.0,
        skip_if_hands_le     = 2,
    ),
)


# ── St5 : MONEY_MACHINE ───────────────────────────────────────────────────────
# Economy snowball. Play blinds conservatively — interest is king.
# Never skip big blind (scoring floor is low without mult jokers).

MONEY_MACHINE = Strategy(
    name="Economy_Money_Machine",
    combo=ComboStrategy(
        target_hand  = "Two Pair",
        keep_mode    = "pairs",
        main_suit    = None,
        keep_n       = 2,
        max_discards = 1,
    ),
    spend=SpendStrategy(
        planets  = ["c_uranus", "c_mercury"],
        jokers   = [
            "j_to_do_list", "j_swashbuckler", "j_bull", "j_bootstraps",
            "j_reserved_parking", "j_rocket", "j_satellite",
            "j_cloud_9", "j_superposition",
        ],
        tarots           = ["c_hermit", "c_temperance"],
        vouchers         = ["v_overstock", "v_liquidation", "v_clearance_sale", "v_directors_cut"],
        spend_limit      = 0,
        spend_limit_pct  = 0.5,
        reroll           = True,
        reroll_threshold = 40,
        sell_jokers      = sell_list(max_sell_tier=2),
        buy_fallback_tier = 5,   # economy jokers are tier 4-5 — allow broad fallback
    ),
    blind=BlindStrategy(
        skip_small           = True,
        skip_big             = False,
        skip_if_margin_above = 2.0,
        skip_if_hands_le     = 2,
    ),
)


# ── St6 : MERCENARY ──────────────────────────────────────────────────────────
# Opportunistic — buys best available every ante, no fixed plan.
# Probabilistic blind skipping: 50%.

MERCENARY = Strategy(
    name="Mercenary_Opportunist",
    combo=ComboStrategy(
        target_hand  = None,
        keep_mode    = "high_card",
        main_suit    = None,
        keep_n       = 3,
        max_discards = 2,
    ),
    spend=SpendStrategy(
        planets  = [],
        jokers   = buy_list(),    # all catalog jokers, tier 1 → 5
        tarots           = ["c_hermit", "c_temperance"],
        vouchers         = [],
        spend_limit      = 0,
        spend_limit_pct  = 0.8,
        reroll           = True,
        reroll_threshold = 30,
        sell_jokers      = sell_list(max_sell_tier=2),
        buy_fallback_tier = 0,   # buy_list already covers everything
    ),
    blind=BlindStrategy(
        skip_small       = True,
        skip_big         = True,
        skip_probability = 0.5,
    ),
)


# ── St7 : RANDOM_CHAOS ───────────────────────────────────────────────────────
# Pure chaos — 1 random discard, buys first joker seen, never skips.

RANDOM_CHAOS = Strategy(
    name="Random_Chaos",
    combo=ComboStrategy(
        target_hand  = None,
        keep_mode    = "random",
        main_suit    = None,
        keep_n       = 5,
        max_discards = 1,
    ),
    spend=SpendStrategy(
        planets          = [],
        jokers           = ["*"],
        tarots           = [],
        vouchers         = [],
        spend_limit      = 0,
        spend_limit_pct  = 0.0,
        reroll           = False,
        reroll_threshold = 0,
        sell_jokers      = ["*"],
        buy_fallback_tier = 0,
    ),
    blind=BlindStrategy(skip_small=False, skip_big=False),
)


# ── Active strategy ───────────────────────────────────────────────────────────
ACTIVE = FH_2P

ALL_STRATEGIES = [
    FH_2P,
    FH_TWOPAIR_STRATEGY,
    MULT_STACKER,
    FLUSH_JOKER_SPECIALIST,
    MONEY_MACHINE,
    MERCENARY,
    RANDOM_CHAOS,
]
