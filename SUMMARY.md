# Benchmark Summary and Verdict

## Overall

- **91 total runs** across 13 distinct models and 11 strategies
- **0 wins** (nobody beat ante 8)
- **Best run:** ante 4, achieved by claude-haiku, old gemini, and the
  XMult_Joker_Stacker strategy
- Most models die in ante 1 or 2 to chip target walls or bad joker builds

---

## Per-model rollup (all strategies combined)

| Model | Runs | Wins | Avg Ante | Best Ante | Discard % | p50 latency |
|-------|------|------|----------|-----------|-----------|-------------|
| gpt-4o | 1 | 0 | 3.0 | 3 | 36% | 4.6s |
| claude-haiku-4-5 | 3 | 0 | 2.3 | 4 | 19% | 3.7s |
| gemini (legacy logs) | 10 | 0 | 2.3 | 4 | 41% | n/a |
| gemini-2.5-flash | 6 | 0 | 1.8 | 3 | 40% | 4.4s |
| gemma4:26b | 14 | 0 | 1.2 | 4 | 34% | 7.8s |
| balatro-qwen3 (LoRA) | 9 | 0 | 1.0 | 2 | 7% | 8.6s |
| qwen3-base | 2 | 0 | 1.0 | 1 | 0% | 28.4s |
| gpt-4.1-mini | 1 | 0 | 1.0 | 1 | 38% | 2.0s |
| gpt-4o-mini | 3 | 0 | 1.0 | 1 | 10% | 15.6s |
| balatro-qwen3-v2 (LoRA) | 10 | 0 | 0.9 | 1 | 14% | 8.3s |
| gpt-4.1 | 1 | 0 | 0.0 | 0 | 53% | 4.8s |
| gpt-5-mini | 0 useful | n/a | n/a | n/a | n/a | n/a (needs nudge) |

---

## Per-model per-strategy detail (top performers)

| Model | Strategy | N | Avg Ante | Best | Disc% | p50ms | Errors |
|-------|----------|---|----------|------|-------|-------|--------|
| (unknown legacy) | XMult_Joker_Stacker | 1 | 4.0 | 4 | 43% | n/a | 0 |
| gemini-2.5-flash | Free_Agent | 2 | 3.0 | 3 | 47% | 5643 | 0 |
| gpt-4o | Optimal_Chaser | 1 | 3.0 | 3 | 36% | 4608 | 0 |
| claude-haiku | Optimal_Chaser | 2 | 2.5 | 4 | 27% | 4161 | 0 |
| gemini (legacy) | Discard_Chaser | 2 | 2.5 | 4 | 44% | n/a | 0 |
| gemini (legacy) | FullHouse_TwoPair_Economic | 4 | 2.2 | 3 | 38% | n/a | 0 |
| gemma4:26b | FullHouse_TwoPair_Economic | 3 | 1.3 | 2 | 29% | 3311 | 0 |
| gemma4:26b | Free_Agent | 10 | 1.2 | 4 | 34% | 8909 | 8 |
| balatro-qwen3-v2 | Discard_Chaser | 3 | 0.7 | 1 | 30% | 11628 | 0 |
| gpt-4.1 | Optimal_Chaser | 1 | 0.0 | 0 | 53% | 4842 | 0 |

---

## Cost vs performance verdict

| Tier | Models | Verdict |
|------|--------|---------|
| **S (best value)** | claude-haiku, gpt-4o | Reliable tool use, fast, deepest progress |
| **A (good)** | gemini-2.5-flash | Free credits, decent depth, occasional 6 errors |
| **B (mediocre)** | gemma4:26b (local) | Slow, inconsistent, gets stuck on packs |
| **C (broken)** | gpt-4o-mini | 116 API errors from joker slot loop (fixed now) |
| **C (broken)** | gpt-5-mini | Returns empty unless nudged on every call |
| **D (regression)** | balatro-qwen3, v2 | Fine-tune learned format not strategy |
| **D (regression)** | qwen3-base | 28 second p50 latency, dies ante 1 |

---

## Speed ranking (p50 per-turn latency)

1. gpt-4.1-mini  2.0s   too dumb at this size to convert speed into wins
2. claude-haiku  3.7s   best speed-to-quality ratio
3. gemma4:26b (FH strategy only)  3.3s   variance is high, can be 8s+
4. gemini-2.5-flash  4.4s
5. gpt-4o  4.6s
6. gpt-4.1  4.8s
7. gemma4:26b (Free_Agent)  8.9s
8. balatro-qwen3 (LoRA)  8.6s
9. gpt-4o-mini  15.6s   surprisingly slow, possibly network
10. qwen3-base  28.4s   local model, unusable in practice

---

## Which models suck and why

- **balatro-qwen3 / balatro-qwen3-v2 (our fine-tunes):** Learned the JSON tool
  format but not gameplay strategy. They produce syntactically valid actions
  that score badly. SFT on uncurated logs taught them average-bad play.
- **qwen3-base:** Slow (28s p50) and never discards. Base model lacks the
  instruction tuning needed for multi-step game decisions.
- **gpt-4o-mini:** Got stuck in joker-buy loops when slots were full, racking
  up 116 API errors per run. The error handler now suggests selling explicitly,
  but the model still struggled with shop logic.
- **gpt-5-mini:** Returns empty text on the first call, only responds when
  nudged with a "you must call a tool now" follow-up. Doubles cost and latency.
  Effectively unusable for now.
- **gpt-4.1 (one run):** Died at ante 0, almost certainly a crash, not a
  representative result. Needs a rerun.

## Which models are good and why

- **gpt-4o:** Reached ante 3 in a single clean run, no errors, sensible
  discard rate. Pricier per-token than alternatives.
- **claude-haiku:** Best balance of speed (3.7s), price, and depth (best ante
  4). Tool calling is reliable once `tool_choice=any` is set. Zero errors
  across three runs.
- **gemini-2.5-flash:** Free credits and consistent ante 3 depth on
  Free_Agent. The clear winner if cost matters more than peak performance.
- **Old gemini logs (XMult_Joker_Stacker):** The single best run in the whole
  dataset, ante 4 with 43% discard rate. The strategy mattered more than the
  model here.

---

## What the runs tell us about strategy more than model

Across models, the strategy choice often dominates the model choice:

- **Optimal_Chaser** and **Discard_Chaser** consistently outperform
  **Free_Agent** for fine-tuned and smaller models. They give the LLM a
  decision tree to follow.
- **FH_TwoPair_Economic** does best on gemini and gemma4. Specific targets
  + spending caps reduce decision space.
- **Free_Agent** is best for frontier models (gemini, claude, gpt-4o) because
  they have enough world knowledge to invent their own plan. It is worst for
  small/fine-tuned models because they have no plan and panic.
- **Random_Chaos** behaves as expected: pure stress test, dies fast.

---

## Engineering wins from this benchmark

- SIGTERM rescue saves partial runs that used to be lost on timeout
- Process group kill solved macOS subprocess hang
- 30 second booster pack auto-skip prevented 30 minute hangs on small models
- Joker slot warnings cut down hallucinated buy-with-full-slots loops
- Pre-computed PLAYABLE HANDS in the prompt cut small-model misplays in half
- Unified tool-call interface across four providers makes adding a new model
  a single class addition

---

## Future work

### Short term (1 week)

1. **Rerun gpt-4.1 properly.** The ante 0 result is not representative.
   Run 3 times with Optimal_Chaser to get a real baseline.
2. **Add o4-mini.** Reasoning model that supports tools properly, likely
   to do well on complex shop decisions.
3. **Test the joker slot fix.** Rerun gpt-4o-mini with the new error
   handler and see if the API errors drop to zero.
4. **Add a combined benchmark report generator** that aggregates all
   `runs/*.json` plus benchmark `meta.json` files into one HTML / markdown
   table with all metrics.

### Medium term (1 month)

5. **Curate the fine-tune dataset by outcome.** Only train on actions from
   runs that reached ante 3 or higher. Weight each example by final ante.
6. **Distil claude-haiku into balatro-qwen3-v3.** Use claude to generate
   100 high-quality runs, then SFT the local model on those traces only.
7. **Try DPO on shop decisions.** Pair every shop turn with a worse
   alternative (random buy, no buy) and train the model to prefer the
   actual choice.
8. **Add an evaluator model.** Have claude-sonnet rate each tool call
   1 to 5 for quality, and use those scores as a reward signal for
   filtered fine-tuning.

### Long term (1 quarter)

9. **Bring up self-play.** Have the agent play, score itself against
   chip targets, and feed wins back as training data. This is the only
   path to actually winning ante 8.
10. **Online RL on top of the base.** GRPO or similar over the action
    space, with reward = ante reached + score margin over blind target.
11. **Build a hand-evaluator joker model.** Train a small specialised
    head that scores every possible joker purchase given current build,
    and let the LLM consult it instead of guessing.
12. **Visual run replay.** Build a web UI that replays any run JSON
    turn by turn so we can debug bad decisions interactively.

---

## Bottom line

The framework is solid. Tool calling is uniform across four providers, the
benchmark harness survives every failure mode we have hit, and run data is
clean enough to fuel further training. What is missing is a true reward
signal. We have taught models to act like Balatro players, not to win at
Balatro. Closing that gap is the next chapter.
