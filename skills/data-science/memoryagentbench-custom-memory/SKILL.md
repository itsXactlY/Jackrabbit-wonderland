---
name: memoryagentbench-custom-memory
description: Run MemoryAgentBench benchmarks with custom memory systems (e.g., Neural Memory). Covers integration of custom embedding retrievers, handling reasoning models, rate limit mitigation, and output parsing fixes.
---

# MemoryAgentBench Custom Memory Integration

## When to use
When benchmarking a custom memory/RAG system against MemoryAgentBench categories (Conflict Resolution, Accurate Retrieval, Test-Time Learning, Long-Range Understanding).

## Prerequisites
- MemoryAgentBench cloned at `~/projects/MemoryAgentBench/`
- Python packages: `sentence-transformers`, `langchain-openai`, `langchain-core`, `langchain-community`, `faiss-cpu`, `python-dotenv`, `tiktoken`, `editdistance`, `semantic-text-splitter`, `rank-bm25`, `nltk` (with `punkt_tab` downloaded)
- NLTK data: `python3 -c "import nltk; nltk.download('punkt_tab')"`

## Integration Steps

### 1. Add embedding class to `methods/embedding_retriever.py`

```python
from sentence_transformers import SentenceTransformer

class SentenceTransformerEmbeddings(Embeddings):
    """Embedding class using sentence-transformers (e.g., all-MiniLM-L6-v2)."""
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
```

### 2. Wire into TextRetriever `__init__`

Add `elif` branch BEFORE the `else` fallback to OpenAI:
```python
elif "sentence-transformers" in embedding_model_name:
    self.embedding_model = SentenceTransformerEmbeddings(model_name=embedding_model_name)
```

### 3. Fix langchain imports (if using newer langchain)

```python
# Old (broken):
from langchain.schema import Document
from langchain.embeddings.base import Embeddings

# New (working):
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
```

### 4. Create agent config YAML

Location: `configs/agent_conf/RAG_Agents/neural_memory/Embedding_rag_neural_memory.yaml`

```yaml
agent_name: Embedding_rag_neural_memory
model: <your_llm_model>
temperature: 0.0
input_length_limit: 300000
buffer_length: 15000
output_dir: ./outputs/neural_memory
max_tokens: 1024
retrieve_num: 10
```

**CRITICAL:** `max_tokens` in agent config is OVERRIDDEN by `generation_max_length` in the dataset config YAML! Must edit the dataset config too.

### 5. Edit dataset config `generation_max_length`

Default is often 10 (way too low). Set to 512-1024:
```yaml
generation_max_length: 1024
```

### 6. Handle Azure vs OpenAI routing in `agent.py`

The `_handle_embedding_rag` method hardcodes `use_azure=True`. For non-Azure endpoints:
```python
if "neural_memory" in self.agent_name:
    rag_system = RAGSystem(self.retriever, self.model, self.temperature, self.max_tokens)
else:
    rag_system = RAGSystem(..., use_azure=True, ...)
```

### 7. Handle reasoning models (e.g., xiaomi/mimo-v2-pro)

Reasoning models return `content: null` and put the answer in `reasoning` field:
```python
answer_text = response.choices[0].message.content
if not answer_text and hasattr(response.choices[0].message, 'reasoning'):
    answer_text = response.choices[0].message.reasoning
```

### 8. Add retry logic for rate-limited APIs

```python
max_retries = 8
base_delay = 5  # seconds
for attempt in range(max_retries):
    try:
        response = self.llm.chat.completions.create(...)
        break
    except openai.RateLimitError:
        wait = base_delay * (2 ** attempt)  # 5, 10, 20, 40, 80, 160, 320, 640
        print(f"Rate limited, retrying in {wait}s...")
        time.sleep(wait)
```

### 9. Fix output parsing (strip markdown)

In `utils/eval_other_utils.py`, `parse_output()` function:
```python
clean_answer = re.sub(f'^{re.escape(answer_prefix)}', '', extracted_text, flags=re.IGNORECASE).strip()
# Add these lines:
clean_answer = re.sub(r'\*+', '', clean_answer)
clean_answer = re.sub(r'_+', '', clean_answer)
```

This fixes cases where model returns `**Belgium**` instead of `Belgium`, costing 3-5% accuracy.

## Running Benchmarks

### .env setup
```bash
# For Ollama (local, no rate limits):
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1

# For Hermes/Nous:
OPENAI_API_KEY=<agent_key_from_~/.hermes/auth.json>
OPENAI_BASE_URL=https://inference-api.nousresearch.com/v1
```

### Command
```bash
cd ~/projects/MemoryAgentBench
CUDA_VISIBLE_DEVICES=0 python3 main.py \
  --agent_config configs/agent_conf/RAG_Agents/neural_memory/Embedding_rag_neural_memory.yaml \
  --dataset_config configs/data_conf/<category>/<dataset>.yaml \
  --force
```

### Dataset categories (smallest first)
| Category | Dataset | Context Size |
|----------|---------|-------------|
| Conflict Resolution | factconsolidation_mh_6k | 6k |
| Accurate Retrieval | Eventqa_64k | 65k |
| Long-Range Understanding | Detective_QA | 200k |
| Test-Time Learning | ICL_nlu | 131k |

### Run sequentially to avoid rate limits!

## Results location
`./outputs/neural_memory/<Category>/<dataset>_results.json`

## Pitfalls

1. **`generation_max_length` overrides agent `max_tokens`** — Always check dataset YAML!
2. **Azure routing is hardcoded** — Must patch `agent.py` for non-Azure endpoints
3. **Reasoning models return null content** — Must check `reasoning` field as fallback
4. **Markdown in output kills exact_match** — Strip `*` and `_` from parsed answers
5. **Rate limits compound** — Run benchmarks sequentially, not parallel
6. **`punkt_tab` not auto-downloaded** — Run `nltk.download('punkt_tab')` before first run
