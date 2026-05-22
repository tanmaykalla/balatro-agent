"""Gemini function-calling tool schemas, grouped by game phase.

Each tool requires a `reasoning` string parameter so every decision is logged.
"""


def _int_array(desc: str) -> dict:
    return {"type": "array", "items": {"type": "integer"}, "description": desc}


REASONING = {"type": "string", "description": "Brief explanation of why this action was chosen."}


SELECTING_HAND_TOOLS = [
    {
        "name": "play_hand",
        "description": "Play the selected cards as a poker hand.",
        "parameters": {
            "type": "object",
            "properties": {
                "cards": _int_array("0-based indices of cards in hand to play."),
                "reasoning": REASONING,
            },
            "required": ["cards", "reasoning"],
        },
    },
    {
        "name": "discard_cards",
        "description": "Discard the selected cards to draw replacements. MAXIMUM 5 cards — never pass more than 5 indices.",
        "parameters": {
            "type": "object",
            "properties": {
                "cards": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "0-based indices of cards to discard. Must be 1–5 items. Never include more than 5.",
                    "maxItems": 5,
                },
                "reasoning": REASONING,
            },
            "required": ["cards", "reasoning"],
        },
    },
]


SHOP_TOOLS = [
    {
        "name": "buy_card",
        "description": "Buy a card (joker/consumable) from the shop by 0-based index.",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer"}, "reasoning": REASONING},
            "required": ["index", "reasoning"],
        },
    },
    {
        "name": "buy_voucher",
        "description": "Buy a voucher from the shop by 0-based index.",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer"}, "reasoning": REASONING},
            "required": ["index", "reasoning"],
        },
    },
    {
        "name": "buy_pack",
        "description": "Buy a booster pack from the shop by 0-based index.",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer"}, "reasoning": REASONING},
            "required": ["index", "reasoning"],
        },
    },
    {
        "name": "sell_joker",
        "description": "Sell a joker you currently own by 0-based index.",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer"}, "reasoning": REASONING},
            "required": ["index", "reasoning"],
        },
    },
    {
        "name": "use_consumable",
        "description": "Use a tarot/planet/spectral consumable by 0-based index. target_cards is required for tarots that target cards in hand.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
                "target_cards": _int_array("0-based indices of cards in hand to target. Empty array if not applicable."),
                "reasoning": REASONING,
            },
            "required": ["index", "target_cards", "reasoning"],
        },
    },
    {
        "name": "reroll_shop",
        "description": "Reroll the shop for new contents at the current reroll cost.",
        "parameters": {
            "type": "object",
            "properties": {"reasoning": REASONING},
            "required": ["reasoning"],
        },
    },
    {
        "name": "finish_shop",
        "description": "Leave the shop and proceed to the next blind selection.",
        "parameters": {
            "type": "object",
            "properties": {"reasoning": REASONING},
            "required": ["reasoning"],
        },
    },
]


BLIND_SELECT_TOOLS = [
    {
        "name": "select_blind",
        "description": "Accept the current blind and start playing it.",
        "parameters": {
            "type": "object",
            "properties": {"reasoning": REASONING},
            "required": ["reasoning"],
        },
    },
    {
        "name": "skip_blind",
        "description": "Skip the current blind in exchange for a tag reward.",
        "parameters": {
            "type": "object",
            "properties": {"reasoning": REASONING},
            "required": ["reasoning"],
        },
    },
]


BOOSTER_PACK_TOOLS = [
    {
        "name": "select_pack_card",
        "description": "Pick a card from the opened booster pack. target_cards is required for tarots that target cards in hand.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
                "target_cards": _int_array("0-based indices of hand cards to target. Empty array if not applicable."),
                "reasoning": REASONING,
            },
            "required": ["index", "target_cards", "reasoning"],
        },
    },
    {
        "name": "skip_pack",
        "description": "Close the booster pack without picking anything.",
        "parameters": {
            "type": "object",
            "properties": {"reasoning": REASONING},
            "required": ["reasoning"],
        },
    },
]


PHASE_TOOLS: dict[str, list[dict]] = {
    "SELECTING_HAND": SELECTING_HAND_TOOLS,
    "SHOP": SHOP_TOOLS,
    "BLIND_SELECT": BLIND_SELECT_TOOLS,
    "SMODS_BOOSTER_OPENED": BOOSTER_PACK_TOOLS,
}
