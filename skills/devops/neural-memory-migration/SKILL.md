---
name: neural-memory-migration
description: Migrate data into Neural Memory from Honcho exports or other sources, and configure the Hermes agent to use it. Covers fast bulk import, connection building, and plugin integration.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [memory, migration, honcho, neural-memory, bulk-import, plugin]
    related_skills: [neural-memory-first]
---

# Neural Memory Migration & Integration

Complete guide for bulk-importing data into Neural Memory and wiring it into the Hermes agent harness.

## When to Use

- Neural Memory DB is empty or lost
- Importing from Honcho export (`/home/alca/honcho_export/`)
- Configuring the Hermes agent to use Neural Memory
- Fixing broken Neural Memory integration

## Prerequisites

- `sentence-transformers` installed (for GPU-accelerated embeddings)
- `neural-memory-adapter` project at `~/projects/neural-memory-adapter/`
- Honcho export at `/home/alca/honcho_export/`

## Step 1: Fast Bulk Import

**Key insight**: Use batch embedding + direct SQLite bulk insert. Do NOT use `mem.remember()` per-message — it does O(n²) auto-connecting and runs at ~10 msg/s.

**Target**: ~3500 msg/s with batch=256 on GPU.

### Import Script Pattern

```python
#!/usr/bin/env python3
"""Import Honcho Export into Neural Memory — fast bulk mode."""

import json, sqlite3, struct, sys, time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "projects/neural-memory-adapter/python"))
from neural_memory import Memory
from embed_provider import EmbeddingProvider

DB_PATH = Path.home() / ".neural_memory" / "memory.db"
EXPORT_DIR = Path("/home/alca/honcho_export")

def clear_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM memories")
    conn.execute("DELETE FROM connections")
    conn.commit()
    conn.close()

def bulk_insert(label_prefix, texts, labels, embedder):
    """Batch embed + direct SQLite insert (NO auto-connect)."""
    dim = embedder.dim
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    
    BATCH = 256
    for i in range(0, len(texts), BATCH):
        batch_t = texts[i:i+BATCH]
        batch_l = labels[i:i+BATCH]
        embeddings = embedder.embed_batch(batch_t)
        rows = [
            (l, t, struct.pack(f'{dim}f', *e))
            for l, t, e in zip(batch_l, batch_t, embeddings)
        ]
        conn.executemany(
            "INSERT INTO memories (label, content, embedding) VALUES (?, ?, ?)", rows
        )
        conn.commit()
    conn.close()

def import_messages(embedder):
    """Import 21K+ messages."""
    with open(EXPORT_DIR / "messages.json") as f:
        messages = json.load(f)
    
    texts, labels = [], []
    for msg in messages:
        content = msg.get("content", "").strip()
        if not content:
            continue
        peer = msg.get("peer_name", "?")
        session = msg.get("session_name", "?")
        ts = msg.get("created_at", "")[:19]
        if len(content) > 8000:
            content = content[:8000]
        texts.append(content)
        labels.append(f"msg:{peer}:{session}:{ts}")
    
    t0 = time.time()
    bulk_insert("messages", texts, labels, embedder)
    print(f"  {len(texts)} messages in {time.time()-t0:.1f}s")

def build_connections(threshold=0.15, window=200):
    """Windowed nearest-neighbor connections (O(n*window) not O(n²))."""
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("SELECT id, embedding FROM memories ORDER BY id").fetchall()
    dim = len(rows[0][1]) // 4
    ids = [r[0] for r in rows]
    embs = [list(struct.unpack(f'{dim}f', r[1])) for r in rows]
    total = len(ids)
    
    import math
    def cosine(a, b):
        dot = sum(x*y for x,y in zip(a,b))
        na = math.sqrt(sum(x*x for x in a))
        nb = math.sqrt(sum(x*x for x in b))
        return dot / (na * nb) if na * nb > 0 else 0
    
    conns = []
    for i in range(total):
        for j in range(max(0, i-window), min(total, i+window)):
            if j <= i: continue
            sim = cosine(embs[i], embs[j])
            if sim > threshold:
                conns.append((ids[i], ids[j], sim))
    
    conn.executemany(
        "INSERT OR IGNORE INTO connections (source_id, target_id, weight, edge_type) VALUES (?, ?, ?, 'similar')",
        conns
    )
    conn.commit()
    conn.close()
    print(f"  {len(conns)} connections built")
```

### Performance Numbers

| Method | Speed | 21K Messages |
|---|---|---|
| `mem.remember()` per msg | ~10 msg/s | ~36 min |
| Batch embed + `remember_embedding()` | ~50 msg/s | ~7 min (still O(n²) auto-connect) |
| **Batch embed + direct SQLite** | **~3500 msg/s** | **~6 sec** |
| Connection building (window=200) | ~115/s | ~3.3 min |

**Total: ~3.4 minutes for 21.6K memories + 2.8M connections.**

### Embedding Dimension Note

- Honcho `message_embeddings.json`: 9524-dim — NOT compatible with Neural Memory (384-dim)
- Honcho `documents.json` embeddings: 9524-dim — also NOT compatible
- **Must re-embed ALL text from scratch** using `all-MiniLM-L6-v2` (384-dim)
- Skip `message_embeddings.json` entirely (234MB of unusable data)

## Step 2: Configure Hermes Agent

The Neural Memory plugin exists at `~/.hermes/hermes-agent/plugins/memory/neural/` but is NOT activated by default.

### Config Changes (`~/.hermes/config.yaml`)

Add the `memory` section:

```yaml
memory:
  provider: neural
  memory_enabled: true
  user_profile_enabled: true
  neural:
    db_path: ~/.neural_memory/memory.db    # NOT hermes.db!
    embedding_backend: auto
    consolidation_interval: 300
    max_episodic: 50000
    prefetch_limit: 10
    search_limit: 10
```

### Plugin Config Fix (`plugins/memory/neural/config.py`)

Default DB path must be `memory.db` not `hermes.db`:

```python
DEFAULT_DB_PATH = str(Path.home() / ".neural_memory" / "memory.db")
```

## Step 3: Improve Plugin Quality

### Prefetch: Synchronous > Background Thread

The default background-thread prefetch misses results on first turn. Make it synchronous:

```python
def prefetch(self, query: str, *, session_id: str = "") -> str:
    if not self._memory or not query:
        return ""
    limit = self._config.get("prefetch_limit", 10) if self._config else 10
    try:
        results = self._memory.recall(query, k=limit)
        if not results:
            return ""
        lines = []
        for r in results:
            sim = r.get("similarity", 0)
            content = r.get("content", "")
            label = r.get("label", "")
            if len(content) > 400:
                content = content[:400] + "..."
            lines.append(f"[{sim:.2f}|{label}] {content}")
        return f"## Neural Memory ({len(results)} recalled)\n" + "\n---\n".join(lines)
    except Exception as e:
        return ""
```

### System Prompt: Be Aggressive

The model needs STRONG instructions to use `neural_recall` instead of `session_search`:

```python
def system_prompt_block(self) -> str:
    # ... get stats ...
    return (
        f"# Neural Memory System\n"
        f"ACTIVE with {total} memories and {connections} graph connections.\n"
        f"MANDATORY: Before answering about past conversations, projects, "
        f"user preferences, or prior work, ALWAYS use neural_recall FIRST.\n"
        f"Do NOT use session_search or terminal for memory lookups.\n"
    )
```

### Tool Descriptions: "MANDATORY" Keyword

Update `neural_recall` description to include "MANDATORY" and "ALWAYS prefer this over session_search".

## How the Integration Works (run_agent.py)

```
User message
  → run_agent.py reads config memory.provider = "neural"
  → load_memory_provider("neural") → NeuralMemoryProvider
  → provider.initialize() → loads SQLite DB + embedder
  → provider.get_tool_schemas() → adds neural_recall/remember/think/graph to tools
  → Before each API call: provider.prefetch(query) → injects <memory-context> block
  → Model sees system prompt + memory context + tools
  → Model calls neural_recall → provider.handle_tool_call() → SQLite search
```

## Verification

```bash
# Check DB
sqlite3 ~/.neural_memory/memory.db "SELECT COUNT(*) FROM memories; SELECT COUNT(*) FROM connections;"

# Check config
python3 -c "import yaml; c=yaml.safe_load(open('$HOME/.hermes/config.yaml')); print(c.get('memory',{}))"

# Test recall
cd ~/projects/neural-memory-adapter/python
python3 -c "
from neural_memory import Memory
m = Memory(use_cpp=False)
for q in ['BTQuant', 'DayZ', 'Chihuahua']:
    r = m.recall(q, k=3)
    print(f'{q}: {len(r)} results')
    for x in r: print(f'  [{x[\"similarity\"]:.3f}] {x[\"content\"][:80]}')
m.close()
"
```

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| No neural tools in agent | `memory.provider` not set | Add to config.yaml |
| Empty results | Wrong DB path (`hermes.db` vs `memory.db`) | Fix config.py DEFAULT_DB_PATH |
| Import takes 30+ min | Using `mem.remember()` per message | Use bulk insert pattern |
| Prefetch always empty | Background thread race condition | Make prefetch synchronous |
| Model uses session_search | Weak tool descriptions | Add "MANDATORY" to descriptions |
