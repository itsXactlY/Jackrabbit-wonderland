---
name: memoryagentbench-setup
description: Set up and run MemoryAgentBench benchmarks — NIM-hosted LLM + FAISS embedding retriever with multiple embedding model options.
---

# MemoryAgentBench Setup & Run

## Project Location
`~/projects/MemoryAgentBench/`

## Architecture
- **LLM**: Via NVIDIA NIM (OpenAI-compatible API) or OpenAI
- **Retriever**: FAISS + LangChain Embeddings (Contriever, Qwen3-Embedding-4B, NV-Embed-v2, sentence-transformers, OpenAI)
- **Datasets**: EventQA, LongMemEval, FactConsolidation, Ruler, DetectiveQA, InfBench, ICL, Recsys

## Config Format (YAML)
```yaml
agent_name: Embedding_rag_neural_memory
model: meta/llama-3.3-70b-instruct
temperature: 0.0
input_length_limit: 300000
buffer_length: 15000
output_dir: ./outputs/neural_memory
retrieve_num: 10
```

## .env Setup (NIM as OpenAI replacement)
```env
OPENAI_API_KEY=napi-YOUR-KEY
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
```

## Run Command
```bash
cd ~/projects/MemoryAgentBench
python main.py \
  --agent_config configs/agent_conf/RAG_Agents/neural_memory/Embedding_rag_neural_memory.yaml \
  --dataset_config configs/data_conf/Conflict_Resolution/Factconsolidation_mh_6k.yaml \
  --force
```

## Embedding Model Selection (agent.py + TextRetriever)
The agent_name in config determines the embedding model via pattern matching in `agent.py`:
- `rag_contriever` → `facebook/contriever`
- `rag_text_embedding_3_large` → `text-embedding-3-large`
- `rag_text_embedding_3_small` → `text-embedding-3-small`
- `rag_qwen3_embedding_4b` → `Qwen/Qwen3-Embedding-4B`
- `rag_neural_memory` → `sentence-transformers/all-MiniLM-L6-v2`

## Adding Custom Embedding Models
1. Add Embeddings subclass in `methods/embedding_retriever.py` (must implement `embed_documents` + `embed_query`)
2. Add elif branch in `TextRetriever.__init__` matching the model name
3. Add agent_name pattern in `agent.py` `_handle_embedding_rag` method

## Dependencies
System python3 needs packages installed with `--break-system-packages`:
```bash
pip install --break-system-packages python-dotenv openai langchain langchain-openai langchain-community faiss-cpu sentence-transformers transformers torch rouge-score nltk datasets tiktoken
```

## Dataset Sizes
| Dataset | Size | Notes |
|---------|------|-------|
| FactConsolidation 6k | Tiny | Good for quick test |
| FactConsolidation 32k | Small | |
| FactConsolidation 64k | Medium | |
| EventQA 64k | Medium | |
| LongMemEval | Variable | Memory-focused |

## Pitfalls
- **System python3**: The benchmark uses system `/usr/bin/python3`, NOT the Hermes venv. Install deps there.
- **agent_name matching**: Must contain the pattern (e.g., `rag_neural_memory`), not equal it. `Embedding_rag_neural_memory` works.
- **No venv**: Project has no built-in venv — all deps must be system-installed.
- **sentence-transformers lazy import**: The `SentenceTransformerEmbeddings` class imports `sentence_transformers` inside `__init__` to avoid import errors when not using that model.
