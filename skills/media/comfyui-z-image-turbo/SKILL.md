---
name: comfyui-z-image-turbo
description: Image and video generation using Z-Image Turbo AIO and SVD via ComfyUI
---

# ComfyUI + Z-Image Turbo AIO + SVD

## Prerequisites
- ComfyUI installed at `~/ComfyUI` (DO NOT DELETE after use - keep persistent!)
- Python venv at `~/sd-venv` (DO NOT DELETE)
- Z-Image Turbo model at `~/.cache/sd-models/z-image-turbo/`

## Custom Nodes (required)
```bash
git clone --depth 1 https://github.com/rgthree/rgthree-comfy.git ~/ComfyUI/custom_nodes/rgthree-comfy
git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes.git ~/ComfyUI/custom_nodes/ComfyUI-KJNodes
git clone --depth 1 https://github.com/edelvarden/comfyui_image_metadata_extension.git ~/ComfyUI/custom_nodes/comfyui_image_metadata_extension
git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git ~/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite
pip install -r requirements.txt for each
```

## Image Generation (Z-Image Turbo AIO)
Settings from model author:
- **Steps:** 9
- **CFG:** 1.0 (DO NOT CHANGE)
- **Sampler:** `res_multistep` (from KJNodes)
- **Scheduler:** `simple`
- **Resolution:** 1920×1088 (tested on RTX 4060 8GB)
- **NO negative prompts** (model ignores them)
- Natural language prompts work best (100-300 words)

API workflow nodes:
```
CheckpointLoaderSimple → z-image-turbo-fp16-aio.safetensors
CLIPTextEncode → positive prompt
CLIPTextEncode → "" (empty negative)
EmptyLatentImage → 1920x1088
KSampler → 9 steps, cfg 1.0, res_multistep, simple
VAEDecode
SaveImage
```

## Video Generation (SVD XT 1.1)
### Required Models
- `~/ComfyUI/models/checkpoints/svd_xt_1_1.safetensors` (gated, needs HF token)
- `~/ComfyUI/models/clip_vision/ViT-L-14-openai.safetensors` (from SVD repo's `image_encoder/model.fp16.safetensors`)

Download CLIP Vision from SVD repo:
```python
from huggingface_hub import hf_hub_download, login
login(token="YOUR_TOKEN")
path = hf_hub_download("stabilityai/stable-video-diffusion-img2vid-xt-1-1",
    "image_encoder/model.fp16.safetensors", local_dir="~/ComfyUI/models/clip_vision")
```

### SVD API Workflow
CRITICAL: SVD uses CLIP Vision, NOT regular CLIP text encoder!
- Use `CLIPVisionLoader` node (loads ViT-L-14-openai.safetensors)
- Do NOT use CLIP from CheckpointLoaderSimple for SVD

```
CheckpointLoaderSimple → svd_xt_1_1.safetensors
CLIPVisionLoader → ViT-L-14-openai.safetensors
LoadImage → input image
ImageScale → 1024x576
SVD_img2vid_Conditioning → clip_vision from CLIPVisionLoader, 25 frames, motion_bucket_id=127, fps=5
KSampler → 25 steps, cfg 2.5, euler, normal
VAEDecode
VHS_VideoCombine → h264-mp4, pingpong=False, save_output=True, loop_count=0
```

## Starting ComfyUI
```bash
~/sd-venv/bin/python ~/ComfyUI/main.py --listen --port 8188
# Output to log file, NOT pipe (avoids BrokenPipeError with tqdm)
```

## API Usage
```python
import json, subprocess
workflow = { ... }  # nodes dict
r = subprocess.run(["curl", "-s", "-X", "POST", "http://127.0.0.1:8188/prompt",
    "-H", "Content-Type: application/json",
    "-d", json.dumps({"prompt": workflow})], ...)
```

## Checking Available NVIDIA NIM Models
```python
from openai import OpenAI
client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key="nvapi-...")
models = client.models.list()
for m in models.data:
    if 'nemotron' in m.id.lower():
        print(m.id)
```

## Pitfalls
- **DO NOT delete ComfyUI/sd-venv after use** - keep persistent!
- **BrokenPipeError**: Start ComfyUI with output to log file, not pipe: `log = open("/tmp/comfyui.log", "w"); Popen(..., stdout=log, stderr=log)`
- **VHS_VideoCombine** requires: `pingpong=False, save_output=True, loop_count=0` (missing = validation error)
- **SVD CLIP type mismatch**: `CheckpointLoaderSimple` returns CLIP (text), SVD needs CLIP_VISION (image). Use separate `CLIPVisionLoader` node.
- **Gated models**: SVD XT 1.1 requires HF account + license acceptance on the model page
- **NVIDIA NIM reasoning models** (Nemotron-Super): return `content=None`, data in `reasoning_content` field. Use `meta/llama-3.3-70b-instruct` instead for normal chat.
- Z-Image Turbo FP16 = 19GB, needs ~16GB VRAM. FP8 = 10GB for lower VRAM
- **Ollama qwen3.5:4b**: add `"think": False` to request body, otherwise response field is empty (thinking mode)
