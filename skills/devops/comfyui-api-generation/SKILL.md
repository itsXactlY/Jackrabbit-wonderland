---
name: comfyui-api-generation
description: Run ComfyUI headlessly via API to generate images with custom models
version: 1.0.0
---

# ComfyUI API Generation

Run ComfyUI as a background process and queue image generation tasks via HTTP API.

## Setup

```bash
# Clone
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ~/ComfyUI
cd ~/ComfyUI

# Install deps (use a dedicated venv, NOT hermes venv - diffusers conflicts)
python3 -m venv ~/.comfy-venv
~/.comfy-venv/bin/pip install -r requirements.txt

# Symlink models
ln -s ~/.cache/sd-models/MODEL.safetensors ~/ComfyUI/models/checkpoints/

# Install custom nodes (e.g. for res_multistep sampler)
git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes.git ~/ComfyUI/custom_nodes/ComfyUI-KJNodes
git clone --depth 1 https://github.com/rgthree/rgthree-comfy.git ~/ComfyUI/custom_nodes/rgthree-comfy
~/.comfy-venv/bin/pip install -r ~/ComfyUI/custom_nodes/*/requirements.txt
```

## Start ComfyUI

CRITICAL: Do NOT capture stdout/stderr with subprocess.PIPE - tqdm progress bars will crash with BrokenPipeError.

```python
import subprocess

# CORRECT: redirect to log file
log = open("/tmp/comfyui.log", "w")
proc = subprocess.Popen(
    [python, "main.py", "--listen", "--port", "8188"],
    cwd="~/ComfyUI",
    stdout=log, stderr=log
)

# WRONG: this will crash on generation
proc = subprocess.Popen(..., stdout=subprocess.PIPE, stderr=subprocess.PIPE)
```

## Queue Generation via API

```python
import json, subprocess, time

workflow = {
    "3": {"class_type": "KSampler", "inputs": {
        "seed": 42, "steps": 9, "cfg": 1.0,
        "sampler_name": "res_multistep",  # or "euler_ancestral"
        "scheduler": "simple",            # or "beta"
        "denoise": 1.0,
        "model": ["4", 0], "positive": ["6", 0],
        "negative": ["7", 0], "latent_image": ["5", 0]
    }},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "your prompt here", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "output", "images": ["8", 0]}}
}

# Queue
r = subprocess.run(["curl", "-s", "-X", "POST", "http://127.0.0.1:8188/prompt",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps({"prompt": workflow})],
                   capture_output=True, text=True, timeout=30)
prompt_id = json.loads(r.stdout)["prompt_id"]

# Poll for completion
for i in range(120):
    r2 = subprocess.run(["curl", "-s", "http://127.0.0.1:8188/history"],
                        capture_output=True, text=True, timeout=10)
    history = json.loads(r2.stdout)
    if prompt_id in history:
        outputs = history[prompt_id].get("outputs", {})
        if outputs:
            for nid, out in outputs.items():
                if "images" in out:
                    for img in out["images"]:
                        print(f"Generated: {img['filename']}")
            break
    time.sleep(5)
```

## Z-Image Turbo AIO Settings

```
Model: SeeSee21/Z-Image-Turbo-AIO (HuggingFace)
Steps: 9, CFG: 1.0
Sampler: res_multistep (from ComfyUI-KJNodes)
Scheduler: simple
FP16 ~20GB VRAM, FP8 ~10GB VRAM
NO negative prompts (model ignores them)
```

## SVD Image-to-Video

### Additional Setup

```bash
# Install VideoHelperSuite (for VHS_VideoCombine node)
git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git ~/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite
~/.comfy-venv/bin/pip install -r ~/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt

# Download SVD model (GATED - requires HF token + license acceptance)
# Accept license at: https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1
# Then download with token:
python3 -c "
from huggingface_hub import login, hf_hub_download
login(token='YOUR_HF_TOKEN')
hf_hub_download('stabilityai/stable-video-diffusion-img2vid-xt-1-1',
    'svd_xt_1_1.safetensors',
    local_dir='~/ComfyUI/models/checkpoints',
    local_dir_use_symlinks=False)
# Also download CLIP Vision (image encoder) - REQUIRED, not bundled with checkpoint!
hf_hub_download('stabilityai/stable-video-diffusion-img2vid-xt-1-1',
    'image_encoder/model.fp16.safetensors',
    local_dir='~/ComfyUI/models/clip_vision',
    local_dir_use_symlinks=False)
# Rename to standard name ComfyUI expects
import shutil
shutil.copy2('~/ComfyUI/models/clip_vision/image_encoder/model.fp16.safetensors',
             '~/ComfyUI/models/clip_vision/ViT-L-14-openai.safetensors')
"
```

### SVD Workflow (Image-to-Video)

```python
workflow = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "svd_xt_1_1.safetensors"}},
    "9": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "ViT-L-14-openai.safetensors"}},
    "2": {"class_type": "LoadImage", "inputs": {"image": "input_image.png"}},  # must be in ComfyUI/input/
    "3": {"class_type": "ImageScale", "inputs": {
        "upscale_method": "lanczos", "width": 1024, "height": 576, "crop": "center", "image": ["2", 0]
    }},
    "5": {"class_type": "SVD_img2vid_Conditioning", "inputs": {
        "clip_vision": ["9", 0],  # MUST use CLIPVisionLoader, NOT CheckpointLoaderSimple's clip output!
        "init_image": ["3", 0], "vae": ["1", 2],
        "width": 1024, "height": 576, "video_frames": 25,
        "motion_bucket_id": 127, "fps": 5, "augmentation_level": 0.0
    }},
    "6": {"class_type": "KSampler", "inputs": {
        "seed": 42, "steps": 25, "cfg": 2.5, "sampler_name": "euler", "scheduler": "normal",
        "denoise": 1.0, "model": ["1", 0], "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["5", 2]
    }},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
    "8": {"class_type": "VHS_VideoCombine", "inputs": {
        "images": ["7", 0], "frame_rate": 5, "filename_prefix": "output_video",
        "format": "video/h264-mp4", "pingpong": False, "save_output": True, "loop_count": 0
    }}
}
```

### Pitfalls

- **BrokenPipeError**: Never use subprocess.PIPE for ComfyUI stdout/stderr
- **Missing sampler**: `res_multistep` requires ComfyUI-KJNodes custom node
- **VRAM**: FP16 needs ~20GB, FP8 needs ~10GB; use `--lowvram` flag for 8GB cards
- **Hermes venv conflicts**: ComfyUI needs its own venv (diffusers version conflicts with hermes)
- **CLIP Vision mismatch**: SVD needs `CLIPVisionLoader` (not `CheckpointLoaderSimple`'s CLIP output) - type mismatch: `CLIP` vs `CLIP_VISION`
- **Missing CLIP Vision model**: SVD repo bundles image_encoder separately - download `image_encoder/model.fp16.safetensors` and rename to `ViT-L-14-openai.safetensors` in `clip_vision/`
- **SVD is gated**: Requires HF account + license acceptance on model page
- **VHS_VideoCombine**: Requires `ComfyUI-VideoHelperSuite` custom node; boolean params (`pingpong`, `save_output`) must be actual booleans, not strings
- **DO NOT DELETE ComfyUI/venv between uses**: Keep setup permanent, only restart the process when adding custom nodes
