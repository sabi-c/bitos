# Memory & Context Systems Research for BITOS

**Date:** 2026-03-17
**Scope:** Lightweight memory architectures for Pi Zero 2W + Mac mini server
**Status:** Research complete, recommendation included

---

## Current BITOS Memory Stack

Before evaluating alternatives, here is what already exists:

- **SQLite** — messages, heartbeat, scheduled actions, animation config (WAL mode)
- **Obsidian Vault Indexer** — 3,847 files, 35K chunks, 3-tier relevance scoring
- **Memory Store** — SQLite-backed conversation memory + fact extraction
- **Memory Consolidator** — Haiku subagent runs every 8 turns, compresses memories
- **Live Context** — auto-refreshing ambient signals (time, weather, tasks, headlines)
- **Self-Model** — persistent agent identity in 5 editable blocks

The current system works but has gaps: no vector similarity search, no temporal knowledge graph, no semantic deduplication, and no structured relationship tracking between memories.

---

## 1. Mem0

**Repository:** github.com/mem0ai/mem0 | **License:** Apache 2.0

### How It Works

Mem0 extracts "memories" (atomic facts) from conversations using an LLM, then stores them in a vector database. On each new message, it:

1. Sends conversation to LLM to extract facts ("user prefers dark mode", "user's name is Seb")
2. Searches existing memories for conflicts/duplicates
3. Adds new memories, updates conflicting ones, deletes superseded ones
4. Returns relevant memories on `memory.search(query, user_id)`

### Architecture

```
Conversation → LLM Extraction → Conflict Resolution → Vector Store
                                                      ↕
                                              History (SQLite)
                                                      ↕
                                        Optional: Graph Store (Neo4j)
```

### Storage Backends

| Component   | Default                | Alternatives                          |
|-------------|------------------------|---------------------------------------|
| Vector      | Qdrant (local, /tmp)   | ChromaDB, Pinecone, Weaviate, Milvus  |
| LLM         | OpenAI gpt-4.1-nano    | Anthropic Claude, Ollama (local)      |
| Embeddings  | OpenAI text-embed-3-sm | Any sentence-transformers model       |
| Graph       | None                   | Neo4j, Memgraph                       |
| History     | SQLite (~/.mem0/)      | SQLite                                |

### BITOS Fit Assessment

**Strengths:**
- Dead simple API: `memory.add()`, `memory.search()`, `memory.get_all()`
- Fact-level granularity is exactly what a personal companion needs
- Conflict resolution prevents contradictory memories
- Can use Anthropic Claude (already in the stack) as the extraction LLM
- SQLite history store aligns with existing architecture
- Self-hosted, no cloud dependency required

**Weaknesses:**
- Requires an LLM call on every `memory.add()` (latency + cost)
- Default Qdrant dependency adds a service to manage
- Graph memory (Neo4j) is optional but adds significant complexity
- No built-in temporal tracking (when facts changed)

**RAM on Mac mini:** ~200-500MB (Qdrant local) or ~50MB (ChromaDB ephemeral)
**Retrieval latency:** ~100-300ms (vector search) + LLM extraction time on add

### Verdict: STRONG CANDIDATE

Mem0 is the most practical drop-in upgrade. It does exactly what BITOS needs — extract facts from conversations and retrieve them by relevance — with minimal infrastructure.

---

## 2. Letta (formerly MemGPT)

**Repository:** github.com/letta-ai/letta | **License:** Apache 2.0

### How It Works

Based on the MemGPT paper (arXiv:2310.08560), Letta treats the LLM like an operating system that manages its own memory through function calls. The LLM decides what to remember, forget, and retrieve.

### Memory Architecture (Three Tiers)

```
┌─────────────────────────────────────────────┐
│              MAIN CONTEXT                    │
│  (fits in LLM context window)               │
│  ┌──────────┐  ┌──────────┐                │
│  │ Persona  │  │  Human   │  ← Core Memory │
│  │  Block   │  │  Block   │    (editable)  │
│  └──────────┘  └──────────┘                │
│  + Recent conversation + system prompt       │
├─────────────────────────────────────────────┤
│           RECALL MEMORY                      │
│  Full conversation history (searchable)      │
│  Retrieved via recall_memory_search()        │
├─────────────────────────────────────────────┤
│           ARCHIVAL MEMORY                    │
│  Long-term vector store (unlimited)          │
│  Retrieved via archival_memory_search()      │
│  Written via archival_memory_insert()        │
└─────────────────────────────────────────────┘
```

### Self-Editing Memory

The agent has tools to modify its own memory:
- `core_memory_append(label, content)` — add to persona/human block
- `core_memory_replace(label, old, new)` — edit core memory in-place
- `archival_memory_insert(content)` — save to long-term store
- `archival_memory_search(query)` — retrieve from archive
- `recall_memory_search(query)` — search conversation history

The LLM autonomously decides when to use these tools. This means it can notice "user just told me their birthday" and update the Human block without explicit programming.

### BITOS Fit Assessment

**Strengths:**
- Most sophisticated memory model — the agent truly manages its own context
- Core memory blocks map directly to BITOS self-model concept
- Conversation search (recall) solves "what did we talk about last week?"
- Agent-driven memory means less custom extraction code

**Weaknesses:**
- Heavy framework — Letta is a full agent platform, not a memory library
- Requires running Letta server (Node.js 18+) as a separate service
- Opinionated architecture conflicts with existing FastAPI + raw Anthropic SDK
- Extra LLM calls for every memory operation (agent must "think" about memory)
- Overkill for BITOS — would mean replacing the entire agent framework

**RAM on Mac mini:** ~500MB-1GB (Letta server + database)
**Retrieval latency:** Variable — depends on agent reasoning loop

### Verdict: INSPIRING BUT WRONG FIT

The MemGPT memory model (core blocks + archival + recall) is the best conceptual framework. But adopting Letta the platform would mean rewriting BITOS. Better to steal the ideas and implement them natively.

---

## 3. A-MEM (Agentic Memory)

**Repository:** github.com/agiresearch/A-mem | **License:** Research project

### How It Works

A-MEM uses Zettelkasten principles — each memory is a structured "note" with:
- Content and contextual description
- Auto-extracted tags and keywords
- Semantic connections to other notes (like wiki links)
- Timestamps and metadata

When adding a memory, the system:
1. Generates a structured note with attributes via LLM
2. Creates contextual descriptions and tags
3. Searches existing memories for semantic connections
4. Establishes links between related notes
5. Allows continuous refinement of the memory graph

Uses ChromaDB for vector embeddings, supports OpenAI or Ollama for LLM processing.

### BITOS Fit Assessment

**Strengths:**
- Zettelkasten linking creates a web of connected memories
- Auto-tagging and keyword extraction are useful
- Research shows it outperforms baselines on memory benchmarks

**Weaknesses:**
- Research project, not production-hardened
- Limited community (compared to Mem0)
- ChromaDB dependency
- Every memory operation requires LLM calls for note generation
- No temporal tracking of fact changes

**RAM on Mac mini:** ~200MB (ChromaDB + Python process)
**Retrieval latency:** ~200-500ms

### Verdict: INTERESTING RESEARCH, NOT PRODUCTION-READY

The Zettelkasten linking concept is valuable. Could be implemented as a feature on top of a simpler system rather than adopted wholesale.

---

## 4. Vector Stores Comparison

### ChromaDB

**Architecture:** Python-native, embedded or client-server, SQLite + DuckDB backend
**Storage:** Persistent to disk, SQLite for metadata, HNSW index for vectors

| Metric         | Value                              |
|----------------|-------------------------------------|
| RAM footprint  | ~50-200MB (depends on collection)  |
| Latency        | ~10-50ms for 10K-100K vectors      |
| Persistence    | SQLite + parquet files              |
| Embedding      | Built-in sentence-transformers     |
| Pi Zero 2W     | Possible but tight at 512MB RAM    |

**Best for:** Prototyping, small-medium collections (<1M vectors)
**Install:** `pip install chromadb`

### Qdrant

**Architecture:** Rust-native, client-server or embedded Python mode
**Storage:** Custom engine with WAL, HNSW index, on-disk or in-memory

| Metric         | Value                              |
|----------------|-------------------------------------|
| RAM footprint  | ~100-500MB (server mode)           |
| Latency        | ~5-20ms for 100K vectors           |
| Persistence    | Custom binary format on disk       |
| Quantization   | Scalar/binary, up to 97% RAM reduction |
| Pi Zero 2W     | Embedded Python mode possible      |

**Best for:** Production use, larger collections, when you need speed
**Embedded mode:** `QdrantClient(path="./qdrant_data")` — no server needed

### LanceDB

**Architecture:** Rust core, embedded (like SQLite for vectors), Lance columnar format
**Storage:** Lance files on disk, zero-copy reads

| Metric         | Value                              |
|----------------|-------------------------------------|
| RAM footprint  | ~30-100MB (truly embedded)         |
| Latency        | ~10-30ms for 100K vectors          |
| Persistence    | Lance columnar files               |
| Versioning     | Built-in automatic versioning      |
| Pi Zero 2W     | Best candidate — minimal overhead  |

**Best for:** Embedded use cases, edge devices, when you want SQLite-like simplicity
**Install:** `pip install lancedb`

### sqlite-vec

**Architecture:** SQLite extension — vector search inside your existing SQLite database
**Storage:** Your existing SQLite file

| Metric         | Value                              |
|----------------|-------------------------------------|
| RAM footprint  | ~5-20MB (extension only)           |
| Latency        | ~20-100ms for 10K-50K vectors      |
| Persistence    | Same SQLite file as everything else|
| Pi Zero 2W     | YES — runs on ARM64, minimal RAM   |
| Platforms      | Linux ARM64, macOS ARM64, WASM     |

**Best for:** When you already use SQLite and want vector search without another service
**Install:** `pip install sqlite-vec`

### Recommendation: sqlite-vec + ChromaDB hybrid

**sqlite-vec** is the obvious choice for BITOS because:
- Zero new infrastructure — extends existing SQLite databases
- ARM64 Linux wheels available (Pi Zero 2W compatible)
- Negligible RAM overhead
- Same backup/replication as other SQLite data
- Perfect for <100K vectors (BITOS scale)

Use **ChromaDB on Mac mini** as the primary vector store for heavier operations (vault indexing), and **sqlite-vec on Pi** as a local cache for recent/frequent memories.

---

## 5. SimpleMem / Minimal Approaches

### The "Just Use SQLite" Approach

The simplest proven memory system for a personal AI companion:

```python
# Schema
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    embedding BLOB,          -- via sqlite-vec
    category TEXT,            -- preference, fact, event, relationship
    subject TEXT,             -- who/what this is about
    confidence REAL DEFAULT 1.0,
    source TEXT,              -- conversation_id or "extracted"
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,     -- optional TTL
    superseded_by INTEGER REFERENCES memories(id)
);

CREATE TABLE memory_links (
    source_id INTEGER REFERENCES memories(id),
    target_id INTEGER REFERENCES memories(id),
    relation TEXT,            -- "contradicts", "elaborates", "related_to"
    strength REAL DEFAULT 1.0
);

-- FTS5 for keyword search
CREATE VIRTUAL TABLE memories_fts USING fts5(content, category, subject);

-- sqlite-vec for semantic search
CREATE VIRTUAL TABLE memories_vec USING vec0(
    embedding float[384]     -- all-MiniLM-L6-v2 dimensions
);
```

### Hybrid Retrieval

```python
async def recall(query: str, limit: int = 5) -> list[Memory]:
    # 1. Semantic search via sqlite-vec
    embedding = embed(query)
    vec_results = db.execute("""
        SELECT id, distance FROM memories_vec
        WHERE embedding MATCH ? ORDER BY distance LIMIT ?
    """, [embedding, limit * 2])

    # 2. Keyword search via FTS5
    fts_results = db.execute("""
        SELECT id, rank FROM memories_fts
        WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?
    """, [query, limit * 2])

    # 3. Merge and rank (reciprocal rank fusion)
    merged = reciprocal_rank_fusion(vec_results, fts_results)
    return merged[:limit]
```

### LLM-Based Extraction (What Mem0 Does, DIY)

```python
EXTRACT_PROMPT = """Extract atomic facts from this conversation.
Return JSON array of objects with: content, category, subject, confidence.
Categories: preference, fact, event, relationship, opinion, plan.
Only extract NEW information not already in existing memories.

Existing memories:
{existing}

Conversation:
{conversation}"""

async def extract_memories(conversation: list[dict], user_id: str):
    existing = await recall(conversation[-1]["content"])
    response = await haiku.messages.create(
        model="claude-haiku-4-5-20250415",
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
            existing=existing, conversation=conversation
        )}]
    )
    facts = json.loads(response.content[0].text)
    for fact in facts:
        await store_memory(fact, user_id)
```

### Verdict: THIS IS THE RECOMMENDATION

This approach gives you 80% of Mem0's functionality with:
- Zero new dependencies (SQLite + sqlite-vec extension)
- Full control over extraction logic
- Uses Haiku (already in the stack) for extraction
- Same database as everything else
- Runs on both Mac mini and Pi Zero 2W

---

## 6. Zep / Graphiti

**Website:** getzep.com | **Graph engine:** github.com/getzep/graphiti

### Architecture

Zep is a context engineering platform built on **Graphiti**, a temporal knowledge graph. The key innovation is bi-temporal fact tracking — every fact has `valid_at` and `invalid_at` timestamps.

```
Conversation → Fact Extraction → Temporal Knowledge Graph
                                        ↕
                                  Entity Nodes
                                  Fact Edges (with time ranges)
                                  Episode Provenance
```

### Graphiti Details

- **Nodes:** Entities (people, places, concepts) with evolving summaries
- **Edges:** Facts as triplets with temporal validity windows
- **Episodes:** Raw source data, every derived fact traces back to source
- **Storage:** Neo4j 5.26+, FalkorDB, Kuzu (embedded), or Amazon Neptune
- **Search:** Hybrid — semantic + keyword + graph traversal

### BITOS Fit Assessment

**Strengths:**
- Temporal tracking is killer for a personal companion ("you used to like X, now you prefer Y")
- Kuzu backend is embedded (like SQLite) — no server needed
- Graphiti is a library, not a platform — can integrate with existing FastAPI
- Sub-second query latency
- Provenance tracking (know where every fact came from)

**Weaknesses:**
- Requires a graph database (even Kuzu adds complexity)
- LLM calls for entity/relationship extraction on every ingestion
- More complex than flat memory stores
- Zep Cloud is the primary product; self-hosted is legacy/community
- Graphiti alone is usable but less documented for standalone use
- NOTE: Kuzu repo was archived Oct 2025 — check current status

**RAM on Mac mini:** ~200-500MB (Kuzu embedded) or ~500MB-1GB (Neo4j)
**Retrieval latency:** ~50-200ms (graph traversal + vector search)

### Verdict: FUTURE UPGRADE PATH

Graphiti's temporal knowledge graph is the most sophisticated option. Not recommended for initial implementation (too much complexity) but is the right upgrade when BITOS memory needs to track how facts change over time.

---

## 7. Knowledge Graphs

### Neo4j

- Full-featured graph database, Cypher query language
- RAM: 1-4GB minimum, typically wants 8GB+
- Excellent for complex relationship queries
- Overkill for personal companion with <10K entities
- Docker deployment on Mac mini is straightforward
- **Verdict:** Too heavy for BITOS scale

### Kuzu (Embedded Graph DB)

- Embedded like SQLite — no server process
- Columnar storage, Cypher-compatible
- Built-in vector index and full-text search
- RAM: ~50-200MB for small graphs
- **Caveat:** Repository archived Oct 2025 — may have maintenance issues
- **Verdict:** Best lightweight graph option IF maintained

### NetworkX (In-Memory Python Graphs)

- Pure Python, zero infrastructure
- Good for <10K nodes (BITOS scale)
- No built-in persistence (serialize to JSON/pickle)
- RAM: ~50-100MB for small graphs
- Can compute centrality, shortest paths, clustering
- **Verdict:** Good for lightweight relationship tracking, pair with SQLite for persistence

### SQLite-Based Graph (DIY)

```sql
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    type TEXT,           -- person, place, concept, preference
    summary TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP
);

CREATE TABLE relations (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER REFERENCES entities(id),
    predicate TEXT,      -- "likes", "works_at", "lives_in"
    object_id INTEGER REFERENCES entities(id),
    confidence REAL,
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,  -- NULL = still valid
    source TEXT              -- conversation_id
);
```

This gives you 70% of a knowledge graph with zero new dependencies. Recursive CTEs in SQLite handle multi-hop traversal for small graphs.

### Verdict: Start with SQLite graph tables, upgrade to Graphiti/Kuzu if relationship queries become important.

---

## 8. Production Personal AI Assistants

### What They Actually Use

**Rabbit R1 (LAM):**
- Cloud-based, no meaningful on-device memory
- "Large Action Model" focused on app automation, not personal memory
- Personalization through repeated interactions, not explicit memory store

**Humane AI Pin:**
- Cloud-first architecture (all processing server-side)
- Company pivoted/sold to HP — not a reference implementation
- No published memory architecture

**Rewind.ai (now Limitless):**
- Records everything (screen, audio), stores locally with compression
- Uses local embedding + search for retrieval
- Key insight: **compress and index everything, search at query time**
- Local-first with cloud sync optional
- Relevant pattern: continuous recording + async indexing + on-demand retrieval

**Apple Intelligence (on-device):**
- Semantic index over on-device data (messages, photos, notes)
- On-device embedding model (~50MB)
- SQLite-backed local search
- Relevant pattern: **small embedding model + SQLite = works on constrained devices**

**Common patterns across production systems:**
1. Heavy lifting (LLM calls, embedding) happens on server
2. Local device stores only what it needs for immediate context
3. Fact extraction happens asynchronously (not blocking conversation)
4. Hybrid retrieval (semantic + keyword + recency) outperforms any single method
5. Simpler systems ship faster and work more reliably

---

## Comparative Evaluation Matrix

| System       | RAM (Mac mini) | Latency | Persistence | Recall Quality | Integration | Cost      | Score |
|-------------|---------------|---------|-------------|---------------|-------------|-----------|-------|
| Mem0         | 200-500MB     | 100-300ms| Yes        | High          | Medium      | Free+LLM  | 8/10  |
| Letta        | 500MB-1GB    | Variable | Yes        | Very High     | Low (rewrite)| Free+LLM | 6/10  |
| A-MEM        | ~200MB       | 200-500ms| Yes        | High          | Low         | Free+LLM  | 5/10  |
| ChromaDB     | 50-200MB     | 10-50ms | Yes        | Medium (vec only)| High     | Free      | 7/10  |
| Qdrant       | 100-500MB    | 5-20ms  | Yes        | Medium (vec only)| High     | Free      | 7/10  |
| LanceDB      | 30-100MB     | 10-30ms | Yes        | Medium (vec only)| High     | Free      | 7/10  |
| sqlite-vec   | 5-20MB       | 20-100ms| Yes        | Medium (vec only)| Very High| Free      | 9/10  |
| Zep/Graphiti | 200MB-1GB    | 50-200ms| Yes        | Very High     | Medium      | Free+LLM  | 7/10  |
| SQLite DIY   | ~0 extra     | 10-50ms | Yes        | High (hybrid) | Perfect     | Free+LLM  | 9/10  |

---

## Recommended Architecture

### Phase 1: Enhanced SQLite Memory (Implement Now)

Extend the current SQLite-based system with sqlite-vec for vector search and structured fact extraction. This is the highest-value, lowest-risk path.

```
┌─────────────────────────────────────────────────────────┐
│                    MAC MINI SERVER                        │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │              FastAPI Server                    │       │
│  │                                                │       │
│  │  ┌─────────┐  ┌──────────┐  ┌─────────────┐ │       │
│  │  │  Chat   │  │ Memory   │  │   Vault     │ │       │
│  │  │ Handler │  │ Manager  │  │  Indexer    │ │       │
│  │  └────┬────┘  └─────┬────┘  └──────┬──────┘ │       │
│  │       │              │              │         │       │
│  │  ┌────▼──────────────▼──────────────▼──────┐ │       │
│  │  │           SQLite (WAL mode)              │ │       │
│  │  │                                          │ │       │
│  │  │  memories     — atomic facts             │ │       │
│  │  │  memories_vec — sqlite-vec embeddings    │ │       │
│  │  │  memories_fts — FTS5 keyword search      │ │       │
│  │  │  entities     — people, places, concepts │ │       │
│  │  │  relations    — entity relationships     │ │       │
│  │  │  messages     — conversation history     │ │       │
│  │  │  vault_chunks — obsidian content         │ │       │
│  │  └─────────────────────────────────────────┘ │       │
│  │                                                │       │
│  │  ┌──────────────┐  ┌────────────────────┐    │       │
│  │  │ Embedding    │  │ Fact Extractor     │    │       │
│  │  │ (MiniLM-L6)  │  │ (Haiku subagent)   │    │       │
│  │  └──────────────┘  └────────────────────┘    │       │
│  └──────────────────────────────────────────────┘       │
│                          ↕ WebSocket                     │
└──────────────────────────┬──────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Pi Zero 2W  │
                    │             │
                    │ SQLite cache│
                    │ (recent 50  │
                    │  memories)  │
                    └─────────────┘
```

### Components to Build

**1. Memory Table + sqlite-vec (new)**
```python
# src/memory/vector_store.py
import sqlite3
import sqlite_vec
import numpy as np
from sentence_transformers import SentenceTransformer

class MemoryVectorStore:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dims, ~80MB
        self._init_tables()

    def _init_tables(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT,
                subject TEXT,
                confidence REAL DEFAULT 1.0,
                source_conversation TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                superseded_by INTEGER REFERENCES memories(id),
                active INTEGER DEFAULT 1
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
                id INTEGER PRIMARY KEY,
                embedding float[384]
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, category, subject,
                content=memories, content_rowid=id
            );
        """)

    def add(self, content: str, category: str, subject: str,
            confidence: float = 1.0, source: str = None) -> int:
        embedding = self.model.encode(content)
        cursor = self.db.execute(
            "INSERT INTO memories (content, category, subject, confidence, source_conversation) VALUES (?, ?, ?, ?, ?)",
            (content, category, subject, confidence, source)
        )
        mem_id = cursor.lastrowid
        self.db.execute(
            "INSERT INTO memories_vec (id, embedding) VALUES (?, ?)",
            (mem_id, embedding.tobytes())
        )
        self.db.commit()
        return mem_id

    def search(self, query: str, limit: int = 5) -> list[dict]:
        embedding = self.model.encode(query)

        # Semantic search
        vec_rows = self.db.execute("""
            SELECT v.id, v.distance, m.content, m.category, m.subject, m.confidence
            FROM memories_vec v
            JOIN memories m ON v.id = m.id
            WHERE m.active = 1 AND embedding MATCH ?
            ORDER BY distance LIMIT ?
        """, [embedding.tobytes(), limit * 2]).fetchall()

        # Keyword search
        fts_rows = self.db.execute("""
            SELECT m.id, rank, m.content, m.category, m.subject, m.confidence
            FROM memories_fts f
            JOIN memories m ON f.rowid = m.id
            WHERE memories_fts MATCH ? AND m.active = 1
            ORDER BY rank LIMIT ?
        """, [query, limit * 2]).fetchall()

        # Reciprocal rank fusion
        scores = {}
        for rank, row in enumerate(vec_rows):
            scores[row[0]] = scores.get(row[0], 0) + 1.0 / (rank + 60)
        for rank, row in enumerate(fts_rows):
            scores[row[0]] = scores.get(row[0], 0) + 1.0 / (rank + 60)

        top_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
        results = []
        for mid in top_ids:
            row = self.db.execute(
                "SELECT id, content, category, subject, confidence FROM memories WHERE id = ?",
                (mid,)
            ).fetchone()
            if row:
                results.append({
                    "id": row[0], "content": row[1], "category": row[2],
                    "subject": row[3], "confidence": row[4], "score": scores[mid]
                })
        return results

    def supersede(self, old_id: int, new_content: str, **kwargs) -> int:
        """Mark old memory as superseded, create new one."""
        new_id = self.add(new_content, **kwargs)
        self.db.execute(
            "UPDATE memories SET active = 0, superseded_by = ? WHERE id = ?",
            (new_id, old_id)
        )
        self.db.commit()
        return new_id
```

**2. Fact Extractor Subagent (enhance existing)**
```python
# src/subagents/fact_extractor.py
EXTRACTION_PROMPT = """You are a fact extraction agent for a personal AI companion.

Extract atomic facts from this conversation between Seb (user) and the AI assistant.
Only extract NEW information. Skip anything already known.

Already known facts:
{existing_memories}

Conversation:
{conversation}

Return a JSON array. Each item:
{{
  "content": "atomic fact in third person (e.g., 'Seb prefers dark mode')",
  "category": "preference|fact|event|relationship|opinion|plan|routine",
  "subject": "who or what this fact is about",
  "confidence": 0.0 to 1.0,
  "supersedes": null or "brief description of old fact this replaces"
}}

Return [] if no new facts. Be selective — only extract meaningful, reusable information."""
```

**3. Entity Relationship Tables (simple graph)**
```sql
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT,             -- person, place, project, concept
    summary TEXT,
    first_mentioned TEXT DEFAULT (datetime('now')),
    last_mentioned TEXT DEFAULT (datetime('now')),
    mention_count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS entity_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER REFERENCES entities(id),
    predicate TEXT NOT NULL,  -- "works_on", "likes", "knows", "lives_in"
    object_id INTEGER REFERENCES entities(id),
    confidence REAL DEFAULT 1.0,
    valid_from TEXT DEFAULT (datetime('now')),
    valid_until TEXT,         -- NULL = still valid
    source TEXT               -- conversation_id
);

CREATE INDEX idx_entity_name ON entities(name);
CREATE INDEX idx_relations_subject ON entity_relations(subject_id);
CREATE INDEX idx_relations_object ON entity_relations(object_id);
```

### Phase 2: Mem0 Integration (Month 2)

If DIY extraction quality is insufficient, swap in Mem0 as the memory manager while keeping SQLite + sqlite-vec as the storage backend.

```python
from mem0 import Memory

config = {
    "llm": {
        "provider": "anthropic",
        "config": {"model": "claude-haiku-4-5-20250415"}
    },
    "embedder": {
        "provider": "huggingface",
        "config": {"model": "all-MiniLM-L6-v2"}
    },
    "vector_store": {
        "provider": "chroma",
        "config": {"path": "./data/mem0_chroma"}
    }
}
memory = Memory.from_config(config)
```

Mem0 handles deduplication, conflict resolution, and fact updates automatically. The trade-off is less control over extraction logic.

### Phase 3: Temporal Knowledge Graph (Month 4+)

When BITOS needs to track how facts change over time ("you used to work at X, now you work at Y"), add Graphiti with Kuzu (or a successor embedded graph DB) on top of the existing memory layer.

This is only worth doing once there are thousands of memories and temporal queries matter.

---

## Migration Path from Current System

### Step 1 (Day 1-2): Add sqlite-vec

1. `pip install sqlite-vec sentence-transformers`
2. Add `memories_vec` virtual table to existing SQLite database
3. Embed existing memories from `memory/store.py`
4. Add hybrid search (vector + FTS5) to memory retrieval

### Step 2 (Day 3-5): Structured Fact Extraction

1. Replace current fact extraction with structured extractor (Haiku subagent)
2. Add `category`, `subject`, `confidence` fields to memories
3. Add `superseded_by` for fact updates (temporal awareness lite)
4. Wire extraction into memory consolidator (runs every 8 turns, already exists)

### Step 3 (Week 2): Entity Tracking

1. Add `entities` and `entity_relations` tables
2. Extract entities from conversations using Haiku
3. Build simple relationship graph in SQLite
4. Surface in context: "Seb mentioned [person] 5 times this week"

### Step 4 (Week 3): Memory-Aware Context Assembly

1. Before each chat response, retrieve top-5 relevant memories
2. Include in system prompt alongside live context and self-model
3. Track which memories were useful (reinforce relevance scoring)

### What NOT to Change

- Keep SQLite as the single database engine
- Keep the existing vault indexer (it works)
- Keep the memory consolidator (8-turn cycle is good)
- Keep Haiku for sub-agent work (cheap, fast)
- Do NOT add Neo4j, Qdrant server, or any new infrastructure services

---

## Embedding Model Recommendation

For BITOS, use **all-MiniLM-L6-v2** via sentence-transformers:

| Property       | Value                    |
|----------------|--------------------------|
| Dimensions     | 384                      |
| Model size     | ~80MB                    |
| Speed          | ~5ms per embedding (CPU) |
| Quality        | Good enough for personal memory |
| RAM            | ~150MB loaded            |
| Runs on Pi?    | Yes, but slow (~50ms/embed) |

Run on Mac mini for indexing. For Pi, either:
- Pre-compute embeddings server-side and sync
- Use a tiny model like `all-MiniLM-L12-v2` locally for cache queries
- Skip local vector search; just use FTS5 keyword search on Pi

---

## Cost Analysis

| Component                    | One-time | Monthly  |
|------------------------------|----------|----------|
| sqlite-vec                   | Free     | Free     |
| sentence-transformers model  | Free     | Free     |
| Haiku fact extraction (est.) | —        | ~$2-5    |
| Additional SQLite storage    | Free     | Free     |
| **Total incremental cost**   | **$0**   | **~$2-5** |

Compared to alternatives:
- Mem0 with OpenAI: ~$5-15/mo (gpt-4.1-nano extraction calls)
- Qdrant server: Free but +200MB RAM
- Neo4j: Free but +1GB RAM, Docker overhead
- Zep Cloud: $25+/mo

---

## Final Recommendation

**Build a "Mem0-inspired" system natively in SQLite.**

The reasoning:

1. **BITOS already uses SQLite for everything.** Adding sqlite-vec extends it with vector search at near-zero cost. No new services, no new databases, no Docker containers.

2. **Haiku is already in the stack.** Using it for fact extraction costs ~$2-5/mo and produces good-quality structured memories.

3. **The MemGPT/Letta memory model is the right conceptual framework** — core context blocks (self-model), searchable conversation history (recall), and long-term facts (archival). BITOS already has pieces of this; it just needs the vector search and structured extraction layers.

4. **Temporal fact tracking via `superseded_by` gives 80% of Graphiti's value** at 5% of the complexity. Full temporal knowledge graphs are a Phase 3 concern.

5. **sqlite-vec runs on Pi Zero 2W.** This means the device can do local memory lookups without server calls — critical for offline scenarios.

The upgrade path is clear: SQLite + sqlite-vec now, evaluate Mem0 as a drop-in if extraction quality needs improvement, add Graphiti/knowledge graph later if relationship queries become important. Each phase is additive, not a rewrite.
