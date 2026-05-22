"""
jokers.py — Balatro joker catalog

Each entry:
  name       : human-readable label
  tags       : list of effect categories
  buy_tier   : 1 (must-have) → 5 (low priority); None = never buy
  sell_tier  : 1 (sell first / dump) → 5 (keep always)

Tags:
  mult_x       xMult scaling
  mult_add     flat +Mult
  chips        +Chips / chip scaling
  economy      generates money
  amplifier    copies or amplifies another joker
  retrigger    causes cards to score multiple times
  hand_type    syncs with a specific poker hand
  probability  scales with lucky/random effects
  utility      deck / hand manipulation
"""

from __future__ import annotations
from typing import List, Optional


JOKER_CATALOG: dict[str, dict] = {

    # ── Tier 1 — must-have ────────────────────────────────────────────────────
    "j_family":      {"name": "The Family",        "tags": ["mult_x", "hand_type"],   "buy_tier": 1, "sell_tier": 5},
    "j_glass":       {"name": "Glass Joker",        "tags": ["mult_x"],                "buy_tier": 1, "sell_tier": 5},
    "j_blueprint":   {"name": "Blueprint",          "tags": ["amplifier"],             "buy_tier": 1, "sell_tier": 5},
    "j_brainstorm":  {"name": "Brainstorm",         "tags": ["amplifier"],             "buy_tier": 1, "sell_tier": 5},
    "j_ramen":       {"name": "Ramen",              "tags": ["mult_x"],                "buy_tier": 1, "sell_tier": 4},
    "j_acrobat":     {"name": "Acrobat",            "tags": ["mult_x"],                "buy_tier": 1, "sell_tier": 5},
    "j_oops":        {"name": "Oops! All 6s",       "tags": ["probability"],           "buy_tier": 1, "sell_tier": 5},
    "j_stencil":     {"name": "Joker Stencil",      "tags": ["mult_x"],                "buy_tier": 1, "sell_tier": 5},
    "j_hologram":    {"name": "Hologram",           "tags": ["mult_x"],                "buy_tier": 1, "sell_tier": 5},
    "j_perkeo":      {"name": "Perkeo",             "tags": ["amplifier"],             "buy_tier": 1, "sell_tier": 5},
    "j_triboulet":   {"name": "Triboulet",          "tags": ["mult_x"],                "buy_tier": 1, "sell_tier": 5},

    # ── Tier 2 ────────────────────────────────────────────────────────────────
    "j_duo":         {"name": "The Duo",            "tags": ["mult_x", "hand_type"],   "buy_tier": 2, "sell_tier": 4},
    "j_trio":        {"name": "The Trio",           "tags": ["mult_x", "hand_type"],   "buy_tier": 2, "sell_tier": 4},
    "j_quartet":     {"name": "The Quartet",        "tags": ["mult_x", "hand_type"],   "buy_tier": 2, "sell_tier": 4},
    "j_mad":         {"name": "Mad Joker",          "tags": ["mult_add", "hand_type"], "buy_tier": 2, "sell_tier": 3},
    "j_bloodstone":  {"name": "Bloodstone",         "tags": ["mult_x", "probability"], "buy_tier": 2, "sell_tier": 4},
    "j_flower_pot":  {"name": "Flower Pot",         "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_throwback":   {"name": "Throwback",          "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_steel_joker": {"name": "Steel Joker",        "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_invisible":   {"name": "Invisible Joker",    "tags": ["amplifier"],             "buy_tier": 2, "sell_tier": 5},
    "j_the_tribe":   {"name": "The Tribe",          "tags": ["mult_x", "hand_type"],   "buy_tier": 2, "sell_tier": 5},
    "j_ancient":     {"name": "Ancient Joker",      "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 5},
    "j_campfire":    {"name": "Campfire",           "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_seeing_double": {"name": "Seeing Double",    "tags": ["mult_x", "hand_type"],   "buy_tier": 2, "sell_tier": 3},
    "j_mime":        {"name": "Mime",               "tags": ["retrigger"],             "buy_tier": 2, "sell_tier": 4},
    "j_gros_michel": {"name": "Gros Michel",        "tags": ["mult_add"],              "buy_tier": 2, "sell_tier": 3},
    "j_cavendish":   {"name": "Cavendish",          "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_card_sharp":  {"name": "Card Sharp",         "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_madness":     {"name": "Madness",            "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_vampire":     {"name": "Vampire",            "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_obelisk":     {"name": "Obelisk",            "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_photograph":  {"name": "Photograph",         "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_erosion":     {"name": "Erosion",            "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_hack":        {"name": "Hack",               "tags": ["retrigger"],             "buy_tier": 2, "sell_tier": 4},
    "j_baron":       {"name": "Baron",              "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_turtle_bean": {"name": "Turtle Bean",        "tags": ["utility"],               "buy_tier": 2, "sell_tier": 3},
    "j_yorick":      {"name": "Yorick",             "tags": ["mult_x"],                "buy_tier": 2, "sell_tier": 4},
    "j_chicot":      {"name": "Chicot",             "tags": ["utility"],               "buy_tier": 2, "sell_tier": 4},
    "j_luchador":    {"name": "Luchador",           "tags": ["utility"],               "buy_tier": 2, "sell_tier": 3},
    "j_shortcut":    {"name": "Shortcut",           "tags": ["utility"],               "buy_tier": 2, "sell_tier": 3},

    # ── Tier 3 ────────────────────────────────────────────────────────────────
    "j_jolly":       {"name": "Jolly Joker",        "tags": ["mult_add", "hand_type"], "buy_tier": 3, "sell_tier": 2},
    "j_zany":        {"name": "Zany Joker",         "tags": ["mult_add", "hand_type"], "buy_tier": 3, "sell_tier": 2},
    "j_smiley_face": {"name": "Smiley Face",        "tags": ["mult_add"],              "buy_tier": 3, "sell_tier": 2},
    "j_onyx_agate":  {"name": "Onyx Agate",         "tags": ["mult_add"],              "buy_tier": 3, "sell_tier": 2},
    "j_bootstraps":  {"name": "Bootstraps",         "tags": ["mult_add", "economy"],   "buy_tier": 3, "sell_tier": 3},
    "j_shoot_the_moon": {"name": "Shoot the Moon",  "tags": ["mult_add"],              "buy_tier": 3, "sell_tier": 2},
    "j_swashbuckler": {"name": "Swashbuckler",      "tags": ["mult_add", "economy"],   "buy_tier": 3, "sell_tier": 3},
    "j_dusk":        {"name": "Dusk",               "tags": ["retrigger"],             "buy_tier": 3, "sell_tier": 3},
    "j_hanging_chad": {"name": "Hanging Chad",      "tags": ["retrigger"],             "buy_tier": 3, "sell_tier": 3},
    "j_droll":       {"name": "Droll Joker",        "tags": ["mult_add", "hand_type"], "buy_tier": 3, "sell_tier": 2},
    "j_crafty":      {"name": "Crafty Joker",       "tags": ["chips", "hand_type"],    "buy_tier": 3, "sell_tier": 2},
    "j_four_fingers": {"name": "Four Fingers",      "tags": ["utility"],               "buy_tier": 3, "sell_tier": 3},
    "j_smeared_joker": {"name": "Smeared Joker",    "tags": ["utility"],               "buy_tier": 3, "sell_tier": 3},
    "j_half":        {"name": "Half Joker",         "tags": ["mult_add"],              "buy_tier": 3, "sell_tier": 2},
    "j_pareidolia":  {"name": "Pareidolia",         "tags": ["utility"],               "buy_tier": 3, "sell_tier": 2},
    "j_ice_cream":   {"name": "Ice Cream",          "tags": ["chips"],                 "buy_tier": 3, "sell_tier": 2},
    "j_rough_gem":   {"name": "Rough Gem",          "tags": ["economy"],               "buy_tier": 3, "sell_tier": 2},
    "j_red_card":    {"name": "Red Card",           "tags": ["mult_add"],              "buy_tier": 3, "sell_tier": 2},
    "j_seance":      {"name": "Séance",             "tags": ["utility"],               "buy_tier": 3, "sell_tier": 2},
    "j_vagabond":    {"name": "Vagabond",           "tags": ["utility"],               "buy_tier": 3, "sell_tier": 2},
    "j_midas_mask":  {"name": "Midas Mask",         "tags": ["economy"],               "buy_tier": 3, "sell_tier": 2},
    "j_gift_card":   {"name": "Gift Card",          "tags": ["economy"],               "buy_tier": 3, "sell_tier": 2},
    "j_mail":        {"name": "Mail-In Rebate",     "tags": ["economy"],               "buy_tier": 3, "sell_tier": 2},
    "j_riff_raff":   {"name": "Riff-raff",          "tags": ["utility"],               "buy_tier": 3, "sell_tier": 2},
    "j_square":      {"name": "Square Joker",       "tags": ["chips", "hand_type"],    "buy_tier": 3, "sell_tier": 2},

    # ── Tier 4 ────────────────────────────────────────────────────────────────
    "j_sly":         {"name": "Sly Joker",          "tags": ["mult_add", "hand_type"], "buy_tier": 4, "sell_tier": 1},
    "j_supernova":   {"name": "Supernova",          "tags": ["mult_add"],              "buy_tier": 4, "sell_tier": 2},
    "j_banner":      {"name": "Banner",             "tags": ["mult_add"],              "buy_tier": 4, "sell_tier": 2},
    "j_green_joker": {"name": "Green Joker",        "tags": ["mult_add"],              "buy_tier": 4, "sell_tier": 1},
    "j_abstract":    {"name": "Abstract Joker",     "tags": ["mult_add"],              "buy_tier": 4, "sell_tier": 2},
    "j_fibonacci":   {"name": "Fibonacci",          "tags": ["mult_add"],              "buy_tier": 4, "sell_tier": 2},
    "j_bull":        {"name": "Bull",               "tags": ["chips", "economy"],      "buy_tier": 4, "sell_tier": 3},
    "j_to_do_list":  {"name": "To Do List",         "tags": ["economy"],               "buy_tier": 4, "sell_tier": 2},
    "j_reserved_parking": {"name": "Reserved Parking", "tags": ["economy"],           "buy_tier": 4, "sell_tier": 2},
    "j_rocket":      {"name": "Rocket",             "tags": ["economy"],               "buy_tier": 4, "sell_tier": 2},
    "j_satellite":   {"name": "Satellite",          "tags": ["economy"],               "buy_tier": 4, "sell_tier": 2},
    "j_cloud_9":     {"name": "Cloud 9",            "tags": ["economy"],               "buy_tier": 4, "sell_tier": 2},
    "j_superposition": {"name": "Superposition",    "tags": ["economy"],               "buy_tier": 4, "sell_tier": 2},
    "j_egg":         {"name": "Egg",               "tags": ["economy"],               "buy_tier": 4, "sell_tier": 3},
    "j_lucky_cat":   {"name": "Lucky Cat",          "tags": ["mult_x", "probability"], "buy_tier": 4, "sell_tier": 3},

    # ── Tier 5 / filler ───────────────────────────────────────────────────────
    "j_joker":       {"name": "Joker",              "tags": ["mult_add"],              "buy_tier": 5, "sell_tier": 1},
    "j_wily":        {"name": "Wily Joker",         "tags": ["mult_add", "hand_type"], "buy_tier": 5, "sell_tier": 1},
    "j_clever":      {"name": "Clever Joker",       "tags": ["mult_add", "hand_type"], "buy_tier": 5, "sell_tier": 1},
    "j_devious":     {"name": "Devious Joker",      "tags": ["mult_add", "hand_type"], "buy_tier": 5, "sell_tier": 1},
    "j_crazy":       {"name": "Crazy Joker",        "tags": ["mult_add", "hand_type"], "buy_tier": 5, "sell_tier": 1},
}


def buy_list(tags: Optional[List[str]] = None, max_tier: int = 5) -> List[str]:
    """
    Return joker keys in buy-priority order (tier 1 first), up to max_tier.
    Optionally filter to entries that contain ALL of the specified tags.
    """
    results = [
        (k, v) for k, v in JOKER_CATALOG.items()
        if v["buy_tier"] is not None
        and v["buy_tier"] <= max_tier
        and (tags is None or all(t in v["tags"] for t in tags))
    ]
    results.sort(key=lambda x: x[1]["buy_tier"])
    return [k for k, _ in results]


def sell_list(min_sell_tier: int = 1, max_sell_tier: int = 3) -> List[str]:
    """
    Return joker keys that should be sold, sorted sell-first (tier 1 first).
    Default range (1–3) covers fillers and weak +Mult; excludes xMult keepers.
    """
    results = [
        (k, v) for k, v in JOKER_CATALOG.items()
        if v["sell_tier"] is not None
        and min_sell_tier <= v["sell_tier"] <= max_sell_tier
    ]
    results.sort(key=lambda x: x[1]["sell_tier"])
    return [k for k, _ in results]
