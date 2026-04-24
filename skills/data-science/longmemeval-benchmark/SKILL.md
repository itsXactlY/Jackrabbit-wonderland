---
name: longmemeval-benchmark
description: Benchmark memory systems against LongMemEval (ICLR 2025) - 500 questions testing long-term chat memory
---

# LongMemEval Benchmark for Memory Systems

## Overview
LongMemEval tests 5 long-term memory abilities with 500 questions:
- Information Extraction, Multi-Session Reasoning, Knowledge Updates, Temporal Reasoning, Abstention

Repo: https://github.com/xiaowu0162/longmemeval

## Data
Download to `~/projects/LongMemEval/data/`:
```bash
wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json
wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json
wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_m_cleaned.json
```

Oracle = 14.7MB (with haystack sessions), S = 264MB, M = 2.6GB

## Pipeline
1. **Index**: Embed all chat turns from haystack_sessions
2. **Retrieve**: For each question, find top-k most similar sessions (cosine similarity)
3. **Answer**: Feed retrieved context + question to LLM
4. **Judge**: Use LLM judge to evaluate (GPT-4o or local)

## Results Format (JSONL)
```json
{"question_id": "gpt4_xxx", "hypothesis": "The answer is..."}
```

## Evaluation
```bash
python src/evaluation/evaluate_qa.py gpt-4o-mini results.jsonl data/longmemeval_oracle.json
```

## Our Results (Neural Memory Adapter + qwen3.5:4b)
- Overall: 94/500 = 18.8%
- single-session-user: 45.7%, single-session-assistant: 35.7%
- knowledge-update: 17.9%, multi-session: 11.3%
- temporal-reasoning: 9.0%, single-session-preference: 3.3%
- 500 questions in 23min (2.7s/question)
- Retriever: TF-IDF+SVD (384d), LLM: qwen3.5:4b

## NVIDIA NIM (alternative to Ollama)
```python
from openai import OpenAI
client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key="nvapi-...")
completion = client.chat.completions.create(
    model="meta/llama-3.3-70b-instruct",
    messages=[{"role": "user", "content": prompt}],
    temperature=0, max_tokens=300
)
answer = completion.choices[0].message.content
```
~5s/question, much faster than local Ollama. List models: `client.models.list()`

## Neural Memory Adapter Bottlenecks (from benchmark analysis)
1. **TF-IDF → sentence-transformers**: Already in embed_provider.py, auto-selects CUDA if available. Falls back to TF-IDF if sentence-transformers broken (missing botocore dep). Fix: `pip install botocore` in hermes venv.
2. **4B model = temporal-reasoning killer**: qwen3.5:4b at 9% on temporal reasoning is a model capability issue, not retrieval. Need ≥26B (Gemma 4 26B, Llama 3.3 70B).
3. **knowledge-update = architecture problem**: Need conflict detection - implemented in memory_client.py: `remember()` auto-detects semantic similarity >0.7 + content differ heuristics (numbers, dates, negations, keyword diff >30%).
4. **temporal-reasoning needs timestamps in retrieval**: Implemented `temporal_weight` param in `recall()`, exponential decay (24h half-life) on last_accessed.

## Pitfalls
- **qwen3.5 thinking mode**: Returns empty `response`, content in `thinking`. Fix: add `"think": False` to Ollama API call
- **Ollama API**: Use `curl` to `http://127.0.0.1:11434/api/generate` with `"think": False`
- **NVIDIA NIM reasoning models** (nemotron-super): `content=None`, data in `reasoning_content`. Use `meta/llama-3.3-70b-instruct` for normal output.
- **NVIDIA NIM available models**: `client.models.list()` returns 189+ models. Nemotron-3-super-120b, llama-3.3-70b-instruct, etc.
- **EmbeddingProvider**: Attribute is `.dim` not `.dimension`
- **Cache turns index**: Save to .npy to avoid re-embedding on resume
- **`python3` system Python**: Missing numpy/sd-venv deps. Always use `~/sd-venv/bin/python`
- **EvoMem** (https://github.com/zhaosnw/evo_mem): Streaming benchmark, not benchmaxxed. Better for testing self-evolving memory. Cloned at ~/projects/evo_mem
