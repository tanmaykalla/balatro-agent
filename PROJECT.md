# Balatro LLM Agent — Project Overview

## What this project is

An autonomous agent framework that plays **Balatro** (a poker-based roguelike) using
Large Language Models as the decision maker. The agent reads the live game state,
reasons about poker hands, jokers, and economy, then calls tools to play cards,
discard, buy items, and progress through antes.

The framework supports multiple LLM backends (Gemini, Claude, OpenAI GPT, Ollama
local models) and multiple gameplay strategies. A benchmark harness runs all models
under identical conditions to compare their decision quality.

---

## How it talks to the game: Balatrobot

[Balatrobot](https://github.com/besteon/balatrobot) is a Lua mod that exposes
Balatro's internal game state over a local TCP/JSON-RPC socket. The mod is
installed via Steamodded (the standard Balatro mod loader).

**Launch sequence on this machine:**
1. Steam launches Balatro with the Balatrobot mod loaded.
2. The mod opens a JSON-RPC server on `127.0.0.1` (default port).
3. Our Python client connects and starts a new run with a chosen deck and stake.
4. Every game phase (BLIND_SELECT, SELECTING_HAND, SHOP, etc.) is exposed as a
   queryable state object containing hand cards, jokers, money, blind targets,
   shop contents, etc.

**Client side:** `balatrobot_client.py` wraps the socket with typed helpers:
- `bot.get_gamestate()` returns the full game dictionary
- `bot.play(cards=[...])` plays specific card indices
- `bot.discard(cards=[...])` discards card indices
- `bot.buy(card=i)` / `bot.sell(joker=i)` / `bot.reroll()` for shop
- `bot.select_blind(skip=False)` for blind selection
- `bot.pack(card=i, targets=[...])` for booster pack picks

If the game rejects an action (bad index, insufficient funds, slots full), the
client raises `BalatrobotError` with the server-side reason. We catch these and
feed them back into the LLM's conversation as error feedback.

---

## Architecture

```
balatro_agent/
├── main.py                    CLI entrypoint, picks LLM backend + strategy
├── agent.py                   Top-level run loop: pulls state, routes to handlers
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

### The run loop (agent.py)

```
while game.state != GAME_OVER:
    G = bot.get_gamestate()
    handler = HANDLERS[G.state]
    G = handler.handle(G, strategy, memory, llm, prompts, system_prompt, bot)
```

Each handler is responsible for one phase. It builds a prompt describing the
current state, asks the LLM to call one of N allowed tools, executes the tool
against the bot, and loops until the phase advances.

### Phase handlers

| Phase | Handler | Allowed tools |
|-------|---------|--------------|
| BLIND_SELECT | `BlindHandler` | `select_blind`, `skip_blind` |
| SELECTING_HAND | `HandHandler` | `play_hand(cards=[...])`, `discard_cards(cards=[...])` |
| SHOP | `ShopHandler` | `buy_card`, `buy_voucher`, `buy_pack`, `sell_joker`, `use_consumable`, `reroll_shop`, `finish_shop` |
| SMODS_BOOSTER_OPENED | `BoosterPackHandler` | `pick_pack_card(index, target_cards)`, `skip_pack` |

Booster packs have a 30 second hard cap because some local models hang on them.
Shop has a spend cap derived from `strategy.spend.spend_limit_pct`.

---

## Prompts

Every LLM call gets two messages:

1. **System prompt** built by `PromptBuilder.build_system_prompt(strategy)`. This
   includes the full `GAME_KNOWLEDGE` block (poker hand ranks, scoring formulas,
   discard heuristics, shop priority) plus a `## Personality` section that
   reflects the chosen strategy (target hand, joker priority, spend cap,
   skip conditions).

2. **Game state prompt** built by `PromptBuilder.build_gamestate_prompt(G, memory)`.
   This shows:
   - Phase, ante, round, money, hands left, discards left, blind target
   - Hand contents with index labels: `[0] AH (A of Hearts)`
   - **Pre-computed playable hands** with exact card indices (so the LLM does
     not have to enumerate combinations itself)
   - Jokers held with slot count and a `SLOTS FULL` warning when at limit
   - Consumables, shop cards, vouchers, packs
   - Run memory summary (wallet history, jokers bought, hands played)

The pre-computed PLAYABLE HANDS block was added after small models started
playing High Card when they had a Flush in hand. We enumerate all 5-card
combinations from the hand, classify each, and surface the indices of the best
hand of each type.

---

## Tool calling

Every backend uses **native function calling** so the agent never has to parse
free-text reasoning. Each backend's adapter converts our internal tool definitions
into the provider's schema:

- **Gemini:** `FunctionDeclaration` + `tool_config.mode=ANY`
- **Claude:** `tools=[...]` + `tool_choice={"type": "any"}` (forces tool use)
- **OpenAI:** `tools=[...]` + `tool_choice="required"`
- **Ollama:** `/api/chat` with `tools=[...]`

When a model fails to call a tool (occasionally happens with gpt-5-mini or
local models), we either nudge it with a follow-up message demanding a tool
call, or fall back to a safe default (`play_hand([0,1,2,3,4])`, `finish_shop`,
or `skip_pack`).

Every tool requires a `reasoning` string parameter. This is logged to the run
JSON for post-hoc analysis.

---

## Strategies (personalities)

Strategies live in `strategies.py` as a registry of `Strategy` dataclasses.
Each one is composed of three sub-strategies:

- **ComboStrategy** what hand to chase, max discards per round, discard notes
- **SpendStrategy** joker priority list, planet priority, voucher priority,
  spend cap as % of wallet, reroll behaviour
- **BlindStrategy** when to skip Small/Big blinds (boss is never skippable)

### Registered strategies

| Key | Personality |
|-----|-------------|
| `FH_TWOPAIR_ECONOMIC` | Build Full House, save money, sell weak jokers |
| `XMULT_STACKER` | Stack multiplicative-mult jokers above all else |
| `FLUSH_JOKER_SPECIALIST` | Flush-only with Flush jokers, aggressive rerolls |
| `ECONOMY_MACHINE` | Maximise interest, buy only economy jokers |
| `MERCENARY` | Buy whatever is cheapest, sell whatever pays most |
| `FREE_AGENT` | No constraints, full LLM autonomy |
| `RANDOM_CHAOS` | Stress-test with chaotic spend rules |
| `OPTIMAL_CHASER` | Best-hand-available with aggressive discard rules |
| `FLUSH_FAST` | Flush focus, 5-rule short prompt for fine-tuned models |
| `FH_DISCARD` | Full house focus, 7-rule discard prompt |
| `DISCARD_CHASER` | Discard-heavy, chase any made hand |

Strategies are injected into the system prompt. The same LLM can play very
differently under different strategies. This is the cleanest A/B knob in the
project.

---

## How LLMs fit in

Each LLM is wrapped in a client class with a uniform interface:

```python
class SomeClient:
    def call(self, system_prompt, user_message, tools, conversation_history) -> ToolCall
```

The client returns a `ToolCall(name, params)`. The phase handler executes that
against the bot and continues. Two extra clients exist for offline work:

- `OpenAIReportClient` / `ClaudeSonnetClient` generate post-run prose reports
  from the saved run JSON (used when `--no-report` is not set)

### Backends implemented

| Backend | Models tested | Notes |
|---------|--------------|-------|
| Gemini | gemini-2.5-flash | Best-cost cloud baseline |
| Claude | haiku, sonnet | Tool calling via `tool_choice=any` |
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-5-mini, o4-mini | gpt-5-mini needs nudge; uses `max_completion_tokens` for new models |
| Ollama (local) | qwen3-base, gemma4:26b, balatro-qwen3 (LoRA), balatro-qwen3-v2 | M4 Pro 36GB host |

---

## Benchmark harness

`benchmark/runner.py` launches each agent in a subprocess with:
- `start_new_session=True` so the entire process group can be killed
- 15 minute wall-clock cap per run
- SIGTERM first (10 second grace so the agent can save a partial run JSON)
- SIGKILL if SIGTERM does not work
- One run JSON per game saved to `runs/<id>.json`
- A `meta.json` per benchmark session with timeouts and statuses

Run shapes:
```
python3 -m benchmark.runner                              # full roster
python3 -m benchmark.runner --agent "gpt4o,claude-haiku" # selected
python3 -m benchmark.runner --runs 3                     # 3 per agent
python3 -m benchmark.runner --dry-run                    # show planned cmds
```

The runner is robust to:
- Hanging LLM calls (process kill on timeout)
- Hanging booster pack decisions (handler-level 30 second cap)
- Crashes that lose state (SIGTERM hook in `main.py` flushes partial JSON)
- Shop joker-slot-full loops (auto suggestion to sell the weakest joker)

---

## Run output format

Each run produces a JSON in `runs/<id>.json` containing:
- `run_id`, `strategy_name`, `source` (LLM provider name)
- `final_ante`, `won`, `rounds_played`
- `wallet_history` (money at end of each round)
- `hand_history` (hand type, score, hands used, discards used per round)
- `joker_history` (every buy/sell action)
- `action_log` (every tool call with reasoning text)
- `agent_stats` (input_chars, output_chars, call_latencies, api_errors,
  nudge_retries, model name)
- `system_prompt` (full system prompt used for the run)

These JSONs are the substrate for benchmark aggregation and for the
fine-tuning dataset.
