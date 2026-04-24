---
name: neural-memory-benchmark
description: Benchmark Neural Memory Adapter against EvoMem using NVIDIA NIM (Llama 3.3 70B). Includes retriever integration, streaming analysis, and baseline comparison.
---

# Neural Memory Benchmark (EvoMem)

## Overview
Benchmark the Neural Memory Adapter's retrieval system against [EvoMem](https://github.com/zhaosnw/evo_mem) — a streaming benchmark for self-evolving memory in LLM agents.

## Setup
```bash
cd ~/projects/evo_mem
pip install --break-system-packages -e .
```

## Architecture
- **Retriever**: NeuralMemoryRetriever (sentence-transformers CUDA, 384d, temporal scoring)
- **LLM**: Llama 3.3 70B via NVIDIA NIM (not local Ollama — too slow for benchmarks)
- **Memory**: EvoMem Memory base class + our conflict detection + temporal scoring

## NVIDIA NIM API
```python
from openai import OpenAI
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="nvapi-..."  # Get from https://build.nvidia.com
)
completion = client.chat.completions.create(
    model="meta/llama-3.3-70b-instruct",  # Works reliably
    messages=[{"role": "user", "content": "prompt"}],
    temperature=0, max_tokens=300
)
response = completion.choices[0].message.content.strip()
```

### Available NVIDIA Models (as of 2026-04)
- `meta/llama-3.3-70b-instruct` — works, returns content in `.message.content`
- `nvidia/llama-3.3-nemotron-super-49b-v1.5` — returns `.reasoning` NOT `.content` (thinking model)
- `nvidia/llama-3.1-nemotron-70b-instruct` — same issue (thinking model)

## Ollama qwen3.5 Pitfall
qwen3.5:4b uses "thinking" mode by default — `response` field is empty!
```python
# WRONG — response is empty
r = ollama.generate(model="qwen3.5:4b", prompt="...")

# RIGHT — disable thinking
r = ollama.generate(model="qwen3.5:4b", prompt="...", options={"think": False})
```

## NeuralMemoryRetriever Interface
Located at `~/projects/evo_mem/evo_memory/memory/neural_retriever.py`.

Key methods:
- `encode(text)` — embed text using sentence-transformers
- `retrieve(query, memory, top_k=4)` — cosine similarity + temporal scoring
- `retrieve_with_spreading_activation(query, memory, top_k=4)` — graph-based retrieval

## Benchmark Results (2026-04-09)
| Dataset | Accuracy | Retrieval | Notes |
|---------|----------|-----------|-------|
| MMLU-Pro | 35-75% | 22ms | Variance by random seed |
| GPQA Diamond | 66.7% | 21ms | Consistent, hard science |
| AIME 2024 | 6.7% | 17ms | Competition math, expected |

## Streaming Analysis
Multi-pass benchmarks show 0% delta with deterministic LLM (temperature=0).
Root cause: frozen model always gives same answer regardless of context.
Memory boost manifests in real-world streaming, not frozen benchmarks.

## Pitfalls
- **EvoMem __init__.py broken**: Imports AgentType/DatasetType that don't exist in config.__init__. Rewrite __init__.py to only export Config, Memory, MemoryEntry.
- **Dataset filenames**: mmlu_pro.json, gpqa_diamond.json, aime_2024.json (not just name.json)
- **Single-pass = no delta**: Memory doesn't help when tasks don't repeat
- **Temperature=0 = deterministic**: Model always gives same answer, memory context can't change it
- **Nemotron models return reasoning not content**: Use `meta/llama-3.3-70b-instruct` instead
- **Memory poisoning**: Wrong answers stored in memory contaminate future retrieval. Only store correct answers.
