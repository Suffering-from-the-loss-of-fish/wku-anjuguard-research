---
license_name: qwen-research
license_link: https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE
language:
- en
pipeline_tag: image-text-to-text
tags:
- multimodal
- mlx
library_name: transformers
base_model:
- Qwen/Qwen2.5-VL-3B-Instruct
---

# mlx-community/Qwen2.5-VL-3B-Instruct-4bit
This model was converted to MLX format from [`Qwen/Qwen2.5-VL-3B-Instruct`]() using mlx-vlm version **0.1.11**.
Refer to the [original model card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) for more details on the model.
## Use with mlx

```bash
pip install -U mlx-vlm
```

```bash
python -m mlx_vlm.generate --model mlx-community/Qwen2.5-VL-3B-Instruct-4bit --max-tokens 100 --temp 0.0 --prompt "Describe this image." --image <path_to_image>
```
