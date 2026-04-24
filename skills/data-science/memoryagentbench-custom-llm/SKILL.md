---
name: memoryagentbench-custom-llm
description: Run MemoryAgentBench benchmarks with custom memory systems and LLM endpoints (Ollama, NVIDIA NIM, Hermes/Nous, etc.)
---

# MemoryAgentBench Custom LLM Integration

## When to Use
- Benchmarking custom memory/RAG systems against MemoryAgentBench's 4 evaluation categories
- Testing different LLM backends (local Ollama, cloud APIs, reasoning models)
- Comparing embedding approaches across standard benchmark tasks

## Architecture Overview

```
MemoryAgentBench/
├── configs/
│   ├── agent_conf/RAG_Agents/neural_memory/  # Your custom agent configs
│   └── data_conf/                            # Dataset configs by category
├── methods/embedding_retriever.py             # TextRetriever + RAGSystem
├── agent.py                                   # AgentWrapper (maps agent_name → embedding)
├── main.py                                    # Entry point
└── utils/eval_other_utils.py                  # parse_output, metrics
```

## Step 1: Add Custom Embedding to TextRetriever

In `methods/embedding_retriever.py`:

```python
# Add your embedding class (follows LangChain Embeddings interface)
class MyEmbeddings(Embeddings):
    def __init__(self, model_name="my-model"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

# Add elif branch in TextRetriever.__init__ (around line 154-165)
elif "my-embedding" in embedding_model_name:
    self.embedding_model = MyEmbeddings(model_name=embedding_model_name)
```

## Step 2: Wire Agent Name to Embedding

In `agent.py`, `_handle_embedding_rag` method (around line 920):

```python
elif any(agent_name in self.agent_name for agent_name in ["rag_my_memory"]):
    embedding_model_name = "my-embedding-model-name"
```

Also fix RAGSystem initialization for non-Azure endpoints:
```python
if "my_memory" in self.agent_name:
    rag_system = RAGSystem(self.retriever, self.model, self.temperature, self.max_tokens)
else:
    rag_system = RAGSystem(..., use_azure=True, ...)
```

## Step 3: Create Agent Config

Create `configs/agent_conf/RAG_Agents/neural_memory/Embedding_rag_my_memory.yaml`:

```yaml
agent_name: Embedding_rag_my_memory
model: my-llm-model
temperature: 0.0
input_length_limit: 300000
buffer_length: 15000
output_dir: ./outputs/my_memory
max_tokens: 1024
retrieve_num: 10
```

## Step 4: Configure LLM Endpoint

Edit `.env` in project root:

```bash
# Ollama (local)
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1

# NVIDIA NIM
OPENAI_API_KEY=nvapi-xxxxx
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1

# Hermes/Nous (requires agent_key from auth.json)
OPENAI_API_KEY=<agent_key>
OPENAI_BASE_URL=https://inference-api.nousresearch.com/v1
```

## Step 5: Run Benchmark

```bash
cd ~/projects/MemoryAgentBench
CUDA_VISIBLE_DEVICES=0 python main.py \
  --agent_config configs/agent_conf/RAG_Agents/neural_memory/Embedding_rag_my_memory.yaml \
  --dataset_config configs/data_conf/Conflict_Resolution/Factconsolidation_mh_6k.yaml \
  --force
```

## Available Dataset Categories

| Category | Config Path | Task Type |
|----------|-------------|-----------|
| Conflict Resolution | `data_conf/Conflict_Resolution/Factconsolidation_mh_6k.yaml` | Knowledge update conflict detection |
| Accurate Retrieval | `data_conf/Accurate_Retrieval/EventQA/Eventqa_64k.yaml` | Event prediction from context |
| Long-Range Understanding | `data_conf/Long_Range_Understanding/Detective_QA.yaml` | Multi-hop reasoning over long context |
| Test-Time Learning | `data_conf/Test_Time_Learning/ICL/ICL_nlu.yaml` | In-context learning classification |

## Pitfalls & Fixes

### 1. Output Parsing - Markdown Stripping
Models may output `**bold**` or `_italic_`. Fix in `utils/eval_other_utils.py`:
```python
clean_answer = re.sub(r'\*+', '', clean_answer)
clean_answer = re.sub(r'_+', '', clean_answer)
```

### 2. Reasoning Models (o1, mimo-v2-pro)
These return `content: null` with reasoning field. Fix in `methods/embedding_retriever.py`:
```python
answer_text = response.choices[0].message.content
if not answer_text and hasattr(response.choices[0].message, 'reasoning'):
    answer_text = response.choices[0].message.reasoning
```

### 3. Rate Limits
Add exponential backoff with 5s base delay:
```python
max_retries = 8
base_delay = 5
wait = base_delay * (2 ** attempt)  # 5, 10, 20, 40, 80, 160, 320
```

### 4. generation_max_length Controls max_tokens
The dataset config's `generation_max_length` field controls LLM max_tokens, NOT the agent config. Set appropriately per task (10 for short answers, 1024+ for verbose).

### 5. Import Fixes for Newer LangChain
```python
# Old (may fail)
from langchain.schema import Document
from langchain.embeddings.base import Embeddings

# New
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
```

### 6. NLTK Data
```bash
python -c "import nltk; nltk.download('punkt_tab')"
```

## Benchmark Results Reference

Results saved to `outputs/<agent_name>/` as JSON with metrics:
- `exact_match`, `f1`, `substring_exact_match`
- `rougeL_f1`, `rougeL_recall`, `rougeLsum_f1`, `rougeLsum_recall`
- `memory_construction_time`, `query_time_len`

## Typical Results (sentence-transformers/all-MiniLM-L6-v2 + various LLMs)

| Model | Conflict Resolution (EM) | EventQA (EM) | Detective QA (sub_EM) |
|-------|-------------------------|--------------|----------------------|
| qwen2.5:7b (Ollama) | 70% | 45% | 61% |
| qwen2.5:14b (Ollama) | 8%* | 64% | 34% |
| xiaomi/mimo-v2-pro | 70% | - | 78% |

*14b outputs verbose explanations, needs prompt tuning
