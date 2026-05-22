# Balatro Agent Benchmark

- **Run timestamp**: 20260522_121224
- **Strategy (LLM agents)**: FREE_AGENT
- **Runs per agent**: 3
- **Wall-clock cap**: 900s

## Leaderboard

| Agent | Progress | Max Ante | Peak Eff | Weak Blinds | p50 lat | Toks/dec | Cost/run | Fail% | **Score** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma4-noThink | 2.78 | 3 | 0.00× | 0% | 3.5s | 2300 | $0.0000 | 2% | **62.5** |
| gemma4-think | 1.67 | 1 | 0.00× | 0% | 16.6s | 2426 | $0.0000 | 0% | **48.7** |
| balatro-v1 | 2.33 | 2 | 0.00× | 0% | 12.6s | 3497 | $0.0000 | 0% | **48.0** |
| balatro-v2 | 1.67 | 2 | 0.00× | 0% | 8.7s | 3249 | $0.0000 | 0% | **39.3** |

## Sub-Score Breakdown

| Agent | 🎯 Skill | ⚡ Efficiency | 🛡️ Reliability | **Composite** |
|---|---:|---:|---:|---:|
| gemma4-noThink | 75.0 | 100.0 | 0.0 | **62.5** |
| gemma4-think | 25.0 | 44.7 | 100.0 | **48.7** |
| balatro-v1 | 55.0 | 15.4 | 66.7 | **48.0** |
| balatro-v2 | 25.0 | 40.3 | 66.7 | **39.3** |

## Detailed Stats

### gemma4-noThink
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 2.78 (±0.69), max ante 3, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 3.5s, p95 6.2s
- **Tokens**: 2300/decision (in 423,643 / out 15,918 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 3 API errors, 7 nudge-retries, failure rate 2.5%
- **Action mix**: discard rate 50.9%, jokers bought (avg/run) 25.0

### gemma4-think
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 1.67 (±0.00), max ante 1, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 16.6s, p95 34.4s
- **Tokens**: 2426/decision (in 66,340 / out 1,518 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 2 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 61.1%, jokers bought (avg/run) 1.3

### balatro-v1
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 2.33 (±0.58), max ante 2, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 12.6s, p95 88.1s
- **Tokens**: 3497/decision (in 218,571 / out 21,093 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 4 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 18.1%, jokers bought (avg/run) 2.0

### balatro-v2
- Runs: 3/3  (timeouts: 0, missing: 0)
- **Skill**: progress 1.67 (±0.58), max ante 2, wins 0
- **Pace**: peak efficiency 0.00×, median pace 0.00, weak blind rate 0.0%
- **Latency**: p50 8.7s, p95 66.7s
- **Tokens**: 3249/decision (in 124,329 / out 7,576 total)
- **Cost**: ~$0.0000/run
- **Reliability**: 0 API errors, 2 nudge-retries, failure rate 0.0%
- **Action mix**: discard rate 34.5%, jokers bought (avg/run) 1.0

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