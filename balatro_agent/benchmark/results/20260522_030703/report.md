# Balatro Agent Benchmark

- **Run timestamp**: 20260522_030703
- **Strategy (LLM agents)**: FREE_AGENT
- **Runs per agent**: 3
- **Wall-clock cap**: 900s

## Leaderboard

| Agent | Progress | Max Ante | Peak Eff | Weak Blinds | p50 lat | Toks/dec | Cost/run | Fail% | **Score** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted-flush | 2.33 | 3 | 0.00× | 0% | 0.0s | 0 | $0.0000 | 0% | **50.0** |

## Sub-Score Breakdown

| Agent | 🎯 Skill | ⚡ Efficiency | 🛡️ Reliability | **Composite** |
|---|---:|---:|---:|---:|
| scripted-flush | 50.0 | 50.0 | 50.0 | **50.0** |

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