---
name: memory-agent-bench
description: Set up and run MemoryAgentBench (ICLR 2026) for benchmarking memory-augmented LLM agents. Compare neural memory systems against mem0, letta, cognee, hipporag.
---

# MemoryAgentBench Setup & Integration

ICLR 2026 benchmark for memory-augmented agents. 4 categories: Accurate Retrieval, Test-Time Learning, Long-Range Understanding, Conflict Resolution.

## Setup

```bash
git clone https://github.com/HUST-AI-HYZ/MemoryAgentBench.git ~/projects/MemoryAgentBench
cd ~/projects/MemoryAgentBench
pip install -r requirements.txt
```

## NVIDIA NIM (instead of OpenAI)

Create `.env` in project root:
```
OPENAI_API_KEY=nvapi-YOUR_KEY_HERE
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
```

Model in agent configs: `meta/llama-3.3-70b-instruct`

## Running Benchmarks

```bash
python main.py \
  --agent_config configs/agent_conf/RAG_Agents/neural_memory/Embedding_rag_neural_memory.yaml \
  --dataset_config configs/data_conf/Accurate_Retrieval/LongMemEval/Longmemeval_s.yaml
```

Dataset configs in `configs/data_conf/`:
- `Accurate_Retrieval/` - LongMemEval, EventQA, Ruler
- `Conflict_Resolution/` - FactConsolidation (single/multi-hop)
- `Long_Range_Understanding/` - DetectiveQA, InfBench
- `Test_Time_Learning/` - ICL (classification), RecSys

## Adding Custom Embedding (e.g. sentence-transformers)

1. Agent config YAML in `configs/agent_conf/RAG_Agents/YOUR_AGENT/`:
```yaml
agent_name: Embedding_rag_neural_memory
model: meta/llama-3.3-70b-instruct
temperature: 0.0
input_length_limit: 300000
buffer_length: 15000
output_dir: ./outputs/neural_memory
retrieve_num: 10
```

2. In `agent.py`, add handler mapping in `_handle_embedding_rag`:
```python
elif any(agent_name in self.agent_name for agent_name in ["rag_neural_memory"]):
    embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
```

3. Add to `rag_handlers` dict in `_process_rag_query`:
```python
"rag_neural_memory": lambda: self._handle_embedding_rag(message, context_id, tokenizer),
```

## Architecture

The benchmark uses "inject once, query multiple times":
- Long context is split into chunks
- Agent memorizes chunks sequentially
- Then answers questions from different parts
- Tests retrieval, reasoning, conflict resolution

## Pre-built Agents

| Agent | Type | Memory System |
|-------|------|---------------|
| Long_context_agent | Baseline | Full context in prompt |
| Embedding_rag_* | RAG | Vector similarity |
| Structure_rag_cognee | Graph RAG | Cognee knowledge graph |
| Structure_rag_mem0 | Agentic | Mem0 memory system |
| Structure_rag_letta | Agentic | Letta/MemGPT |
| Self_rag | Adaptive | Self-reflective retrieval |
| HippoRAG | Graph | Hippocampal-inspired |

## Pitfalls

- **NIM Nemotron returns reasoning not content**: Use `meta/llama-3.3-70b-instruct` instead
- **sentence-transformers needs torch + CUDA**: Ensure model loads on GPU for speed
- **Chunk size matters**: Match to dataset config, affects retrieval granularity
- **Temperature 0 for deterministic**: But memory can't change outputs in single-pass benchmarks - need streaming/multi-turn for real memory delta
- **Do NOT delete between sessions**: Keep repo + results persistent
