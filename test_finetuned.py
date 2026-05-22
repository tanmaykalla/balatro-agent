"""Quick test of the fine-tuned Balatro model with proper chat template."""
import mlx_lm

MODEL_PATH    = "models/Qwen3-8B-4bit"
ADAPTER_PATH  = "finetune_adapters"

SYSTEM = """You are an expert Balatro player making decisions in a live game.
Read the game state carefully and call the appropriate tool to take your action.
Always fill in the reasoning field explaining your decision."""

USER = """/no_think
# Phase: SELECTING_HAND | Ante 1 Round 1
Money: $4 | Hands left: 4 | Discards left: 3

## Hand (8 cards)
[0] 5♥  [1] K♠  [2] K♥  [3] 7♦  [4] 3♣  [5] K♦  [6] 2♠  [7] 9♥

## Jokers
(none)

## Score target
Blind: Small | Chips needed: 300"""

model, tokenizer = mlx_lm.load(MODEL_PATH, adapter_path=ADAPTER_PATH)

messages = [
    {"role": "system",    "content": SYSTEM},
    {"role": "user",      "content": USER},
]

prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)

print("── Prompt (last 200 chars) ──")
print(prompt[-200:])
print("\n── Response ──")

response = mlx_lm.generate(
    model,
    tokenizer,
    prompt=prompt,
    max_tokens=150,
    verbose=True,
)
