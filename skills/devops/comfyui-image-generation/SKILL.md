---
name: comfyui-image-generation
description: Generate images and videos using ComfyUI with Z-Image Turbo AIO (8-step, photorealistic) and SVD (video)
---

# ComfyUI Image & Video Generation

## Quick Start
```bash
cd ~/ComfyUI && ~/sd-venv/bin/python main.py --listen --port 8188
```

## Model Locations
- Checkpoints: `~/ComfyUI/models/checkpoints/`
- CLIP Vision: `~/ComfyUI/models/clip_vision/`
- Model cache: `~/.cache/sd-models/z-image-turbo/`

## Z-Image Turbo AIO (Photorealistic, 8-step)
- Model: `z-image-turbo-fp16-aio.safetensors` (19GB) or fp8 (10GB)
- Settings: Steps=9, CFG=1.0, Sampler=res_multistep, Scheduler=simple
- Resolution: 1920x1088 tested on RTX 4060 Ti 16GB
- Requires: rgthree-comfy, ComfyUI-KJNodes (res_multistep sampler)
- NO negative prompts needed!

## SVD XT 1.1 (Image-to-Video)
- Model: `svd_xt_1_1.safetensors` (4.45GB) - GATED, needs HF auth
- CLIP Vision: `ViT-L-14-openai.safetensors` (1.2GB) - from image_encoder/
- Download CLIP Vision from same repo as SVD
- Requires: ComfyUI-VideoHelperSuite (VHS_VideoCombine node)

## API Workflow (POST /prompt)
```python
import json, subprocess

workflow = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
    "2": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
    "3": {"class_type": "KSampler", "inputs": {
        "seed": 42, "steps": 9, "cfg": 1.0, "sampler_name": "res_multistep",
        "scheduler": "simple", "denoise": 1.0,
        "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0]
    }},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt...", "clip": ["1", 1]}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
    "6": {"class_type": "EmptyLatentImage", "inputs": {"width": 1920, "height": 1088, "batch_size": 1}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["1", 2]}},
    "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "output", "images": ["7", 0]}}
}
```

## SVD Video Workflow
- CLIP Vision loaded separately via CLIPVisionLoader (NOT from CheckpointLoaderSimple!)
- VHS_VideoCombine needs pingpong, save_output, loop_count as booleans

## Pitfalls
- **Keep running**: ~/ComfyUI + ~/sd-venv are persistent. DO NOT reinstall or delete between sessions. Just restart the process with `pkill -f "ComfyUI/main.py"` then relaunch.
- **BrokenPipeError**: ComfyUI crashes when stderr is a pipe. Start with `stdout=open("/tmp/comfyui.log","w"), stderr=open("/tmp/comfyui.log","w")` — NOT `subprocess.PIPE`.
- **CLIP != CLIP_VISION**: SVD needs CLIPVisionLoader, not CheckpointLoaderSimple's CLIP. Node ID for SVD_img2vid_Conditioning must use `["clip_vision_loader_node", 0]` not `["checkpoint_loader", 1]`.
- **res_multistep sampler**: Only via ComfyUI-KJNodes custom node. Standard ComfyUI doesn't have it.
- **SVD XT 1.1 is gated**: Need HF account + license. Use `huggingface_hub.login(token=...)` then `hf_hub_download()`.
- **CLIP Vision**: Download `image_encoder/model.fp16.safetensors` from the SVD repo, copy to `~/ComfyUI/models/clip_vision/ViT-L-14-openai.safetensors`.
- **VHS_VideoCombine**: Needs ComfyUI-VideoHelperSuite custom node. Inputs `pingpong`, `save_output`, `loop_count` are required booleans.
- **Keep running**: ~/ComfyUI + ~/sd-venv are persistent. DO NOT reinstall or delete between sessions. Just restart the process.
- **Don't delete after use**: Previous sessions deleted ComfyUI+venv after each generation. STOP doing that. Keep everything.
- **Z-Image Turbo can't use diffusers**: It uses Qwen3 text encoder, not CLIP. Only ComfyUI supports it.
- **FP16 needs ~20GB VRAM**: Use fp8 (10GB) for 16GB cards, or fp16 with attention/VAE slicing.
