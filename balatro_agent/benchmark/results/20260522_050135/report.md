# Balatro Agent Benchmark

- **Run timestamp**: 20260522_050135
- **Strategy (LLM agents)**: FREE_AGENT
- **Runs per agent**: 3
- **Wall-clock cap**: 900s

## Leaderboard

| Agent | Progress | Max Ante | Peak Eff | Weak Blinds | p50 lat | Toks/dec | Cost/run | Fail% | **Score** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted-flush | 2.33 | 3 | 0.00× | 0% | 0.0s | 0 | $0.0000 | 0% | **67.9** |
| qwen3-base-think | — | — | — | — | — | — | — | — | **0 (no runs)** |
| gemma4-noThink | 1.67 | 1 | 0.00× | 0% | 3.4s | 2243 | $0.0000 | 0% | **59.7** |
| gemma4-think | 1.67 | 1 | 0.00× | 0% | 3.4s | 2243 | $0.0000 | 0% | **59.7** |
| balatro-v1 | 1.67 | 1 | 0.00× | 0% | 4.0s | 2192 | $0.0000 | 0% | **59.7** |
| gemini | 3.78 | 3 | 0.00× | 0% | 5.4s | 2305 | $0.0178 | 0% | **55.7** |
| balatro-v2 | 1.44 | 1 | 0.00× | 0% | 7.9s | 2198 | $0.0000 | 0% | **54.7** |
| qwen3-base-noThink | 1.67 | 1 | 0.00× | 0% | 26.0s | 2210 | $0.0000 | 0% | **49.0** |

## Sub-Score Breakdown

| Agent | 🎯 Skill | ⚡ Efficiency | 🛡️ Reliability | **Composite** |
|---|---:|---:|---:|---:|
| scripted-flush | 55.9 | 100.0 | 60.0 | **67.9** |
| qwen3-base-think | 25.0 | 100.0 | 100.0 | **62.5** |
| gemma4-noThink | 47.1 | 44.9 | 100.0 | **59.7** |
| gemma4-think | 47.1 | 44.9 | 100.0 | **59.7** |
| balatro-v1 | 47.1 | 44.7 | 100.0 | **59.7** |
| gemini | 75.0 | 39.6 | 33.3 | **55.7** |
| balatro-v2 | 44.1 | 37.2 | 93.3 | **54.7** |
| qwen3-base-noThink | 47.1 | 2.1 | 100.0 | **49.0** |

## Detailed Stats

### scripted-flush
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 2.33 (±1.15), max ante 3, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 0.0s, p95 0.0s
- **Tokens**: 0/decision (in 0 / out 0 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 39.7%, jokers bought (avg/run) 0.0

### qwen3-base-think
- No valid runs (0 attempted, 0 timeouts)

### gemma4-noThink
- Runs: 1/3  (timeouts: 2, missing: 2)
- **Skill**: progress 1.67 (±0.00), max ante 1, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 3.4s, p95 5.2s
- **Tokens**: 2243/decision (in 28,030 / out 1,124 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 37.5%, jokers bought (avg/run) 0.0

### gemma4-think
- Runs: 1/3  (timeouts: 2, missing: 2)
- **Skill**: progress 1.67 (±0.00), max ante 1, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 3.4s, p95 5.2s
- **Tokens**: 2243/decision (in 28,030 / out 1,124 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 37.5%, jokers bought (avg/run) 0.0

### balatro-v1
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 1.67 (±0.00), max ante 1, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 4.0s, p95 57.2s
- **Tokens**: 2192/decision (in 106,949 / out 2,657 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 0.0%, jokers bought (avg/run) 1.7

### gemini
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 3.78 (±0.19), max ante 3, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 5.4s, p95 10.6s
- **Tokens**: 2305/decision (in 482,943 / out 12,702 total)
- **Cost**: ~$0.0178/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.4%
- **Action mix**: discard rate 57.2%, jokers bought (avg/run) 7.3

### balatro-v2
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 1.44 (±0.19), max ante 1, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 7.9s, p95 10.2s
- **Tokens**: 2198/decision (in 45,092 / out 1,112 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 6.7%, jokers bought (avg/run) 0.3

### qwen3-base-noThink
- Runs: 2/3  (timeouts: 1, missing: 1)
- **Skill**: progress 1.67 (±0.00), max ante 1, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 26.0s, p95 124.7s
- **Tokens**: 2210/decision (in 68,612 / out 2,122 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 0 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 0.0%, jokers bought (avg/run) 1.0

---

### Scoring formula

- **Skill** (50%): 50% progress + 25% peak chip efficiency + 25% inverse weak-blind-rate
- **Efficiency** (25%): 50% inverse p50 latency + 50% inverse tokens/decision
- **Reliability** (25%): 60% inverse failure rate + 40% inverse run-to-run progress std
- Each axis is min-max normalised to 0–100 across the roster, then weighted-summed.

### Notes

- Pace metrics assume 4 hands per blind. "Weak blind" = passed but used most hands.
- Scripted-bot latency, tokens, cost are zero (Python rule eval, no LLM).
- Cost is estimated from char→token at 3.5 chars/token + listed model pricing.