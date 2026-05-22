# Model Artifacts

Large model outputs are intentionally not committed to Git. Keep this repo for
source, configs, training data, reports, and lightweight logs; store model
weights in an artifact store such as Hugging Face Hub, S3/R2/GCS, or Git LFS.

## Local Artifacts

| Path | Size | Purpose |
|------|------|---------|
| `models/Qwen3-8B-4bit/` | 4.3 GB | Local base model used by `finetune_config.yaml` |
| `finetune_adapters/` | 777 MB | MLX LoRA checkpoints saved every 50 iters |
| `finetune_adapters/0000500_adapters.safetensors` | included above | Best adapter noted in `FINETUNING.md` |
| `fused_model/` | 4.3 GB | Fused local model export |
| `models/Qwen3-8B-balatro/` | 4.3 GB | Fine-tuned Balatro model |
| `models/Qwen3-8B-balatro-f16/` | 15 GB | Fused f16 export for conversion |
| `models/Qwen3-8B-balatro-v2-f16/` | 15 GB | Second fused f16 export |

## Git Policy

The project `.gitignore` excludes:

```gitignore
models/
fused_model/
finetune_adapters/
*.safetensors
```

Do not remove those ignores unless the repo is migrated to Git LFS and the
remote has enough quota for the artifacts.

## Rebuild Inputs Tracked In Git

- `finetune_config.yaml`
- `finetune_data/train.jsonl`
- `finetune_data/valid.jsonl`
- `convert_to_jsonl.py`
- `training.log`
- `FINETUNING.md`

## Recommended Upload Names

Use these names if publishing externally:

| Local path | Suggested remote artifact |
|------------|---------------------------|
| `finetune_adapters/` | `balatro-qwen3-lora-adapters` |
| `models/Qwen3-8B-balatro/` | `balatro-qwen3-q4` |
| `models/Qwen3-8B-balatro-f16/` | `balatro-qwen3-f16` |
| `models/Qwen3-8B-balatro-v2-f16/` | `balatro-qwen3-v2-f16` |

After upload, add the canonical URL and checksum here.
