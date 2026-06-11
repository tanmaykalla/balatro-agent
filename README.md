# Balatro LLM Agent

An autonomous agent framework that plays **Balatro** (a poker-based roguelike) using Large Language Models as the decision maker. The agent reads the live game state, reasons about poker hands, jokers, and economy, then calls tools to play cards, discard, buy items, and progress through antes.

## What it does

The agent connects to a running Balatro instance via the [Balatrobot](https://github.com/besteon/balatrobot) mod (a Lua mod that exposes the game's internal state over a local TCP/JSON-RPC socket). It then drives the game end-to-end: selecting blinds, playing or discarding hands, and making shop decisions — all via native LLM function calling.

Multiple LLM backends and gameplay strategies are supported, making it easy to benchmark model quality under identical conditions.

---

## Architecture

```
balatro_agent/
├── main.py                    CLI entrypoint — picks LLM backend + strategy
├── agent.py                   Top-level run loop
├── balatrobot_client.py       TCP/JSON-RPC wrapper for the Lua mod
├── llm_clients.py             All LLM backends (Gemini, Claude, OpenAI, Ollama)
├── phase_handlers.py          One handler class per game phase
├── phase_prompts.py           Builds system + game-state prompts
├── agent_tools.py             JSON-schema tool definitions per phase
├── strategies.py              Personality dataclasses (target hand, joker prio)
├── agent_memory.py            Per-run memory (wallet, hand history, joker buys)
├── run_logger.py              Writes per-run JSON to runs/
└── benchmark/                 Harness for running many agents back-to-back
    ├── agents.py              Agent roster definitions
    ├── runner.py              Subprocess launcher with timeout + SIGTERM rescue
    └── results/<timestamp>/   Aggregated per-bench outputs
```

### Run loop

```python
while game.state != GAME_OVER:
    G = bot.get_gamestate()
    handler = HANDLERS[G.state]
    G = handler.handle(G, strategy, memory, llm, prompts, system_prompt, bot)
```

Each handler covers one phase, builds a prompt, forces a tool call, executes the action, and loops until the phase advances.

| Phase | Handler | Allowed tools |
|-------|---------|--------------|
| `BLIND_SELECT` | `BlindHandler` | `select_blind`, `skip_blind` |
| `SELECTING_HAND` | `HandHandler` | `play_hand`, `discard_cards` |
| `SHOP` | `ShopHandler` | `buy_card`, `buy_voucher`, `buy_pack`, `sell_joker`, `reroll_shop`, `finish_shop` |
| `SMODS_BOOSTER_OPENED` | `BoosterPackHandler` | `pick_pack_card`, `skip_pack` |

---

## LLM Backends

| Backend | Models tested |
|---------|--------------|
| Gemini | `gemini-2.5-flash` |
| Claude | `claude-haiku-4-5`, `claude-sonnet` |
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-5-mini`, `o4-mini` |
| Ollama (local) | `qwen3-base`, `gemma4:26b`, `balatro-qwen3` (LoRA), `balatro-qwen3-v2` (LoRA) |

All backends use **native function calling** — no free-text parsing. If a model fails to call a tool, a nudge message is sent before falling back to a safe default.

Every tool call requires a `reasoning` string, which is logged to the run JSON for post-hoc analysis.

---

## Strategies

Strategies are `Strategy` dataclasses in `strategies.py` that configure what hand to chase, joker priorities, spend caps, and blind skip conditions. The same LLM behaves very differently under different strategies.

| Key | Personality |
|-----|-------------|
| `FH_TWOPAIR_ECONOMIC` | Build Full House, save money, sell weak jokers |
| `XMULT_STACKER` | Stack multiplicative-mult jokers above all else |
| `FLUSH_JOKER_SPECIALIST` | Flush-only with Flush jokers, aggressive rerolls |
| `ECONOMY_MACHINE` | Maximise interest, buy only economy jokers |
| `FREE_AGENT` | No constraints, full LLM autonomy |
| `OPTIMAL_CHASER` | Best-hand-available with aggressive discard rules |
| `DISCARD_CHASER` | Discard-heavy, chase any made hand |

---

## Benchmark Results

95 total runs across 13 models and 11 strategies. Best result: **ante 4** (claude-haiku, gemini legacy, XMult_Joker_Stacker). No model has beaten ante 8 yet.

| Model | Runs | Avg Ante | Best Ante | p50 Latency |
|-------|------|----------|-----------|-------------|
| claude-haiku-4-5 | 5 | 2.0 | 4 | 3.1s |
| gemini-2.5-flash | 6 | 1.8 | 3 | 4.4s |
| gpt-4o | 2 | 2.0 | 3 | 4.9s |
| gemma4:26b | 14 | 1.2 | 4 | 7.8s |
| balatro-qwen3 (LoRA) | 9 | 1.0 | 2 | 8.6s |
| balatro-qwen3-v2 (LoRA) | 10 | 0.9 | 1 | 8.3s |

---

## Fine-tuning (Qwen3-8B LoRA)

A Qwen3-8B 4bit model was fine-tuned on gameplay traces using **MLX-LM** (Apple Silicon native) with LoRA rank 8 / alpha 16 — training only 0.118% of weights (9.7M / 8.19B).

**Dataset:** 609 examples extracted from run JSONs (548 train / 61 val). Each example is a `(system_prompt, game_state, tool_call)` triple.

**Result:** The fine-tuned model plays correctly but is conservative with discards and doesn't generalise well past ante 1. Details in [FINETUNING.md](FINETUNING.md).

---

## Setup

### Prerequisites

- Balatro (Steam) with [Steamodded](https://github.com/Steamodded/smods) and [Balatrobot](https://github.com/besteon/balatrobot) mod installed
- Python 3.11+
- API keys for whichever LLM backends you want to use

### Install

```bash
pip install -r balatro_agent/requirements.txt
```

### Run

```bash
# Start Balatro (via Steam), then:
cd balatro_agent
python3 main.py --model gemini --strategy FREE_AGENT
```

### Benchmark

```bash
cd balatro_agent
python3 -m benchmark.runner                               # full roster
python3 -m benchmark.runner --agent "gpt4o,claude-haiku"  # selected agents
python3 -m benchmark.runner --runs 3                      # 3 runs per agent
python3 -m benchmark.runner --dry-run                     # preview planned runs
```

---

## Run Output

Each run produces `runs/<id>.json` with:
- `final_ante`, `won`, `rounds_played`
- `wallet_history`, `hand_history`, `joker_history`
- `action_log` — every tool call with reasoning text
- `agent_stats` — latencies, API errors, nudge retries, model name
- `system_prompt` — full prompt used for the run

---

## Related docs

- [PROJECT.md](PROJECT.md) — full architecture reference
- [FINETUNING.md](FINETUNING.md) — fine-tuning stack and results
- [SUMMARY.md](SUMMARY.md) — benchmark summary across all runs
- [WEEK1_STRATEGIES.md](WEEK1_STRATEGIES.md) — early rule-based (non-LLM) strategies
