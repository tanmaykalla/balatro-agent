# Fine-tuning Notes — Qwen3-8B Balatro Agent

## Goal

Take an open-weight base model (Qwen3-8B 4bit) and fine-tune it on Balatro
gameplay traces so it learns to call the right tool for each phase without
needing the large system prompt. Run it locally via Ollama and compare it
against frontier cloud models on the same benchmark.

---

## Stack

| Component | Tool | Why |
|-----------|------|-----|
| Base model | Qwen3-8B 4bit | Strong at tool calling, fits in 36GB unified memory |
| Training framework | **MLX-LM** (Apple silicon native) | Runs LoRA on M4 Pro without any cloud cost |
| Fine-tune type | **LoRA** rank 8, alpha 16 | Only 0.118% of weights trained (9.7M / 8.19B) |
| Inference runtime | **Ollama** + GGUF Q4_K_M | Same interface as the cloud LLM clients |
| Format conversion | llama.cpp `convert_hf_to_gguf.py` + `llama-quantize` | MLX export does not support Qwen3 GGUF |

---

## Data preparation

### Source

All previously-saved run JSONs in `runs/`. Each JSON contains an `action_log`
list where every entry is one tool call the LLM made, paired with the game
state it saw and the reasoning it produced.

### Conversion: `convert_to_jsonl.py`

Walks every run JSON, and for each action emits one chat-format example:

```json
{
  "messages": [
    {"role": "system",    "content": "<full GAME_KNOWLEDGE + strategy>"},
    {"role": "user",      "content": "<game state prompt at this turn>"},
    {"role": "assistant", "content": "<tool call as JSON>"}
  ]
}
```

The assistant content is the tool call serialised as JSON, so the model learns
the exact `{"name": "...", "arguments": {...}}` format we will parse at
inference time.

**Filters applied during conversion:**
- Drop fallback / nudged actions (those are non-decisions)
- Drop runs that ended in API errors before any progress
- Drop turns where the action was rejected by the bot (bad indices)
- Keep only the highest-quality strategies (Optimal_Chaser, Free_Agent,
  Flush_Joker_Specialist, FH_TwoPair_Economic, XMult_Joker_Stacker)

**Split:**
- 548 training examples
- 61 validation examples (10%)

Some examples exceed 2048 tokens because of long shop prompts. Those get
truncated at training time (warning logged).

---

## Training config (`finetune_config.yaml`)

```yaml
model: "models/Qwen3-8B-4bit"
data: "finetune_data"
fine_tune_type: lora
num_layers: 16
lora_parameters:
  rank: 8
  alpha: 16
  dropout: 0.05
  scale: 10.0

batch_size: 1
grad_accumulation_steps: 4    # effective batch = 4
iters: 1000
learning_rate: 1e-5
max_seq_length: 2048
grad_checkpoint: true
seed: 42
```

**Why these numbers:**
- `rank 8 / alpha 16`: small LoRA is enough for tool-format learning, prevents
  overfitting on 548 examples
- `learning_rate 1e-5`: low because we are not retraining knowledge, only
  surface tool format
- `iters 1000`: matched to ~7 epochs over 548 examples (548 / 4 per step ~= 137
  steps per epoch, so 1000 ~= 7.3 epochs)
- `num_layers 16`: top 16 transformer layers (output-facing), per MLX docs
- `grad_checkpoint`: dropped peak memory from ~13GB to ~9GB, fits comfortably
  on 36GB M4 Pro alongside Balatro itself

---

## Training run

Wall clock: about 3 hours on M4 Pro 36GB, peak 9.3 GB RAM, 157 tokens/sec.

**Validation loss progression:**

| Iter | Val loss |
|------|----------|
| 0 (random LoRA, baseline) | 2.833 |
| 100 | 1.358 |
| 200 | 0.127 |
| 300 | 0.058 |
| 400 | 0.071 |
| 500 | 0.024 |
| 600 | 0.057 |
| 700 | 0.033 |
| 800 | 0.027 |
| 900 | 0.040 |
| 1000 | 0.035 |

Loss converged around iter 200 to 300. Iters 400 to 1000 mostly oscillate in
the 0.024 to 0.071 band, which is typical of overfit-ready territory.

**Final adapter chosen:** iter 500 (`finetune_adapters/0000500_adapters.safetensors`),
lowest val loss with the cleanest train/val gap.

---

## Conversion pipeline (MLX adapter to Ollama)

Large generated model files are not committed to Git. See
`MODEL_ARTIFACTS.md` for the local artifact inventory and storage policy.

This was the hardest part. MLX-LM's `--export-gguf` does not support Qwen3.
Homebrew's `convert_hf_to_gguf.py` is missing sibling Python modules.

**What worked:**

```bash
# 1. Fuse the LoRA into the base, export HF format (float16)
mlx_lm.fuse \
  --model models/Qwen3-8B-4bit \
  --adapter-path finetune_adapters \
  --save-path models/Qwen3-8B-balatro-f16 \
  --de-quantize

# 2. Clone llama.cpp (need the full repo, not the brew install)
git clone --depth 1 https://github.com/ggerganov/llama.cpp /tmp/llama.cpp
pip3 install -r /tmp/llama.cpp/requirements.txt

# 3. Convert HF -> GGUF f16
python3 /tmp/llama.cpp/convert_hf_to_gguf.py \
  models/Qwen3-8B-balatro-f16 \
  --outfile models/Qwen3-8B-balatro-f16.gguf \
  --outtype f16

# 4. Quantize to Q4_K_M
llama-quantize \
  models/Qwen3-8B-balatro-f16.gguf \
  models/Qwen3-8B-balatro-Q4_K_M.gguf \
  Q4_K_M

# 5. Modelfile + ollama create
ollama create balatro-qwen3 -f Modelfile.balatro
```

**Modelfile.balatro:**
```
FROM ./Qwen3-8B-balatro-Q4_K_M.gguf
TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_ctx 8192
PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>
```

---

## What worked

1. **MLX-LM on M4 Pro is genuinely usable.** 3 hours for 1000 iters of LoRA on
   an 8B model with peak 9.3 GB. No cloud bill.
2. **Tool format learning was rapid.** Val loss dropped from 2.83 to 0.13 in
   the first 200 iters. The model picked up the JSON tool-call shape quickly.
3. **Inference latency is acceptable.** balatro-qwen3 runs at ~8.6s p50 per
   turn, comparable to gemma4 26B and faster than qwen3-base 28s.
4. **The pipeline is reproducible.** Once the llama.cpp clone trick was found,
   the whole convert-and-import process takes 10 minutes.
5. **Q4_K_M loses very little quality.** No measurable difference in tool
   format compliance between f16 and Q4 in spot checks.

## What did not work

1. **The fine-tuned models did not get better at Balatro.** Across nine runs,
   `balatro-qwen3` and `balatro-qwen3-v2` averaged ante 1.0 and never beat
   ante 2. They learned the tool format but not the strategy.

2. **0% discard rate in many runs.** The training data was full of
   short, panicked games where the agent never discarded. The model learned
   that pattern instead of learning when to discard.

3. **No win-vs-loss signal in the training data.** Every action got equal
   weight regardless of whether the run reached ante 4 or died in ante 1.
   Supervised learning on indiscriminate logs teaches the model to imitate
   the average bad player.

4. **MLX `--export-gguf` for Qwen3 is unsupported.** Wasted 30 minutes
   confirming the error before pivoting to the llama.cpp pipeline.

5. **Homebrew `convert_hf_to_gguf.py` is broken in isolation.** It needs
   sibling Python modules that the brew package omits. Cloning the full repo
   is the only reliable path.

6. **Sequence truncation at 2048 dropped useful shop context.** Some examples
   were 3000+ tokens; truncation may have removed the joker list that informed
   the chosen action. Need to either pre-split or bump max_seq_length to 4096
   on a higher-memory host.

7. **`qwen3-base` does not support `"think": true`.** The base variant returns
   400 errors when thinking mode is requested. Qwen3 thinking only works on
   the chat-tuned variant. The `qwen3-base-think` benchmark slot had to be
   dropped.

---

## Lessons for the next round

1. **Filter the training set by outcome.** Only learn from runs that reached
   at least ante 3, or weight each example by `final_ante / max_ante`. Imitation
   learning on bad games produces bad imitations.

2. **Use a reward-aware method (DPO, ORPO, or rejection sampling).** Pair
   each shop decision with a worse alternative and train the model to prefer
   the winner. This gives a strategy signal that SFT cannot.

3. **Generate synthetic high-quality data first.** Use gpt-4o or claude-sonnet
   to play 50 to 100 deliberately-good runs, then fine-tune on those. Distill
   the frontier model into the local one.

4. **Bump max_seq_length to 4096** and pre-split long shop turns into
   sub-decisions so we stop dropping context.

5. **Train on action diff, not action absolute.** Frame each example as the
   delta from a default policy ("would the default pick this? if not, why?")
   so the model learns when to deviate, not what the default is.

6. **Try a smaller base.** Qwen3-4B might be enough for tool-format learning
   and would let us iterate much faster.
