"""SQLite-backed memory store with FTS5 full-text search and optional sqlite-vec.

Tables:
  facts       — atomic facts about the user (preferences, biographical, etc.)
  episodes    — conversation episode summaries
  embeddings  — vector embeddings for semantic search (requires sqlite-vec)
  facts_fts   — FTS5 virtual table on facts.content

All timestamps are ISO 8601 UTC strings. IDs are UUIDs as TEXT.
Database lives at server/data/memory.db with WAL mode for concurrent reads.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "memory.db"

VALID_CATEGORIES = {
    "preference", "biographical", "relationship",
    "habit", "opinion", "knowledge", "general",
}


def _word_set(text: str) -> set[str]:
    """Lowercase word set for Jaccard similarity."""
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


class MemoryStore:
    """Persistent fact and episode storage backed by SQLite + FTS5.

    Optionally loads sqlite-vec for vector similarity search.
    All public methods are synchronous (designed for run_in_executor).
    """

    DEDUP_THRESHOLD = 0.75  # Jaccard similarity above this = duplicate

    def __init__(self, db_path: Optional[str | Path] = None):
        self._db_path = Path(db_path) if db_path else DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._has_vec = False
        self._connect()
        self._init_tables()

    # ── Connection management ────────────────────────────────────────────

    def _connect(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        # Try loading sqlite-vec
        try:
            self._conn.enable_load_extension(True)
            import sqlite_vec
            sqlite_vec.load(self._conn)
            self._has_vec = True
            logger.info("sqlite-vec loaded successfully")
        except Exception:
            self._has_vec = False
            logger.debug("sqlite-vec not available — vector search disabled")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._connect()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Schema ───────────────────────────────────────────────────────────

    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                source TEXT DEFAULT 'auto',
                confidence REAL DEFAULT 0.8,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                active INTEGER DEFAULT 1,
                superseded_by TEXT
            );

            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                summary TEXT NOT NULL,
                key_topics TEXT,
                emotional_tone TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS extraction_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                user_message TEXT,
                extracted_facts TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
            CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(active);
            CREATE INDEX IF NOT EXISTS idx_facts_updated ON facts(updated_at);
            CREATE INDEX IF NOT EXISTS idx_episodes_conv ON episodes(conversation_id);
        """)

        # FTS5 virtual table — separate creation since IF NOT EXISTS works differently
        try:
            self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5("
                "content, category, content=facts, content_rowid=rowid"
                ")"
            )
        except sqlite3.OperationalError:
            # FTS5 table already exists or content= sync issue — try simpler version
            try:
                self.conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5("
                    "fact_id UNINDEXED, content, category"
                    ")"
                )
            except sqlite3.OperationalError:
                pass  # Table already exists

        # sqlite-vec embeddings table (optional)
        if self._has_vec:
            try:
                self.conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0("
                    "fact_id TEXT PRIMARY KEY, vector float[384]"
                    ")"
                )
            except sqlite3.OperationalError:
                logger.debug("embeddings table already exists or vec0 issue")

        self.conn.commit()

    # ── FTS helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _escape_fts(query: str) -> str:
        """Escape FTS5 special characters, returning OR-joined quoted words."""
        for ch in ['"', "'", '*', '-', '+', '(', ')', ':', '^', '{', '}']:
            query = query.replace(ch, ' ')
        words = [w.strip() for w in query.split() if w.strip()]
        if not words:
            return ""
        return " OR ".join(f'"{w}"' for w in words)

    def _find_duplicate(self, content: str) -> Optional[str]:
        """Return fact_id of an existing similar fact, or None."""
        safe_q = self._escape_fts(content)
        if not safe_q:
            return None

        try:
            rows = self.conn.execute(
                "SELECT fact_id, content FROM facts_fts WHERE facts_fts MATCH ? LIMIT 20",
                (safe_q,),
            ).fetchall()
        except sqlite3.OperationalError:
            # Fallback: search facts table directly
            words = content.lower().split()[:3]
            if not words:
                return None
            like_clause = " AND ".join("content LIKE ?" for _ in words)
            params = [f"%{w}%" for w in words]
            rows = self.conn.execute(
                f"SELECT id as fact_id, content FROM facts WHERE active = 1 AND {like_clause} LIMIT 20",
                params,
            ).fetchall()

        new_words = _word_set(content)
        for row in rows:
            existing_words = _word_set(row["content"])
            if _jaccard(new_words, existing_words) >= self.DEDUP_THRESHOLD:
                return row["fact_id"]
        return None

    # ── Fact CRUD ────────────────────────────────────────────────────────

    def add_fact(
        self,
        content: str,
        category: str = "general",
        source: str = "auto",
        confidence: float = 0.8,
    ) -> Optional[str]:
        """Store a new fact. Returns fact_id, or None if duplicate/empty."""
        content = content.strip()
        if not content:
            return None

        if category not in VALID_CATEGORIES:
            category = "general"

        # Dedup check
        existing = self._find_duplicate(content)
        if existing:
            logger.debug("Dedup skip (similar to %s): %.60s", existing, content)
            return existing

        fact_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            "INSERT INTO facts (id, content, category, source, confidence, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fact_id, content, category, source, confidence, now, now),
        )

        # Update FTS index
        try:
            self.conn.execute(
                "INSERT INTO facts_fts (fact_id, content, category) VALUES (?, ?, ?)",
                (fact_id, content, category),
            )
        except sqlite3.OperationalError:
            pass  # FTS sync issue — non-critical

        self.conn.commit()
        logger.info("Stored fact %s: %.80s", fact_id[:8], content)
        return fact_id

    def update_fact(self, fact_id: str, content: str) -> bool:
        """Update a fact's content. Returns True if updated."""
        content = content.strip()
        if not content:
            return False

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE facts SET content = ?, updated_at = ? WHERE id = ? AND active = 1",
            (content, now, fact_id),
        )
        if cursor.rowcount > 0:
            try:
                self.conn.execute(
                    "UPDATE facts_fts SET content = ? WHERE fact_id = ?",
                    (content, fact_id),
                )
            except sqlite3.OperationalError:
                pass
            self.conn.commit()
            return True
        return False

    def get_fact(self, fact_id: str) -> Optional[dict]:
        """Get a single fact by ID. Increments access_count."""
        row = self.conn.execute(
            "SELECT id, content, category, source, confidence, created_at, "
            "updated_at, access_count, last_accessed FROM facts "
            "WHERE id = ? AND active = 1",
            (fact_id,),
        ).fetchone()

        if not row:
            return None

        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE facts SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
            (now, fact_id),
        )
        self.conn.commit()
        return dict(row)

    def search_facts(self, query: str, limit: int = 10) -> list[dict]:
        """Search facts using FTS5 keyword matching."""
        safe_q = self._escape_fts(query)
        if not safe_q:
            return []

        try:
            rows = self.conn.execute(
                "SELECT f.id, f.content, f.category, f.confidence, f.source, "
                "f.created_at, f.access_count, f.last_accessed "
                "FROM facts_fts ft "
                "JOIN facts f ON f.id = ft.fact_id "
                "WHERE facts_fts MATCH ? AND f.active = 1 "
                "ORDER BY ft.rank LIMIT ?",
                (safe_q, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            words = query.lower().split()[:5]
            if not words:
                return []
            like_clause = " OR ".join("content LIKE ?" for _ in words)
            params = [f"%{w}%" for w in words] + [limit]
            rows = self.conn.execute(
                f"SELECT id, content, category, confidence, source, "
                f"created_at, access_count, last_accessed "
                f"FROM facts WHERE active = 1 AND ({like_clause}) LIMIT ?",
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    def get_recent_facts(self, limit: int = 20) -> list[dict]:
        """Return most recently updated active facts."""
        rows = self.conn.execute(
            "SELECT id, content, category, confidence, source, created_at, "
            "updated_at, access_count, last_accessed "
            "FROM facts WHERE active = 1 ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_facts_by_category(self, category: str) -> list[dict]:
        """Return all active facts in a category."""
        rows = self.conn.execute(
            "SELECT id, content, category, confidence, source, created_at, "
            "updated_at, access_count "
            "FROM facts WHERE active = 1 AND category = ? ORDER BY updated_at DESC",
            (category,),
        ).fetchall()
        return [dict(r) for r in rows]

    def deactivate_fact(self, fact_id: str) -> bool:
        """Soft-delete a fact."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE facts SET active = 0, updated_at = ? WHERE id = ? AND active = 1",
            (now, fact_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def supersede_fact(self, old_fact_id: str, new_content: str, **kwargs) -> Optional[str]:
        """Mark old fact as superseded and create a new one."""
        new_id = self.add_fact(new_content, **kwargs)
        if new_id and new_id != old_fact_id:
            now = datetime.now(timezone.utc).isoformat()
            self.conn.execute(
                "UPDATE facts SET active = 0, superseded_by = ?, updated_at = ? WHERE id = ?",
                (new_id, now, old_fact_id),
            )
            self.conn.commit()
        return new_id

    def count_facts(self, active_only: bool = True) -> int:
        """Return total fact count."""
        where = "WHERE active = 1" if active_only else ""
        row = self.conn.execute(f"SELECT COUNT(*) FROM facts {where}").fetchone()
        return row[0] if row else 0

    # ── Episode CRUD ─────────────────────────────────────────────────────

    def add_episode(
        self,
        conversation_id: str,
        summary: str,
        key_topics: Optional[list[str]] = None,
        emotional_tone: str = "neutral",
    ) -> str:
        """Store a conversation episode summary."""
        episode_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO episodes (id, conversation_id, summary, key_topics, emotional_tone, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (episode_id, conversation_id, summary,
             json.dumps(key_topics or []), emotional_tone, now),
        )
        self.conn.commit()
        return episode_id

    def get_episodes(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Return episodes, optionally filtered by conversation."""
        if conversation_id:
            rows = self.conn.execute(
                "SELECT id, conversation_id, summary, key_topics, emotional_tone, created_at "
                "FROM episodes WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, conversation_id, summary, key_topics, emotional_tone, created_at "
                "FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            try:
                d["key_topics"] = json.loads(d["key_topics"])
            except (json.JSONDecodeError, TypeError):
                d["key_topics"] = []
            results.append(d)
        return results

    # ── Extraction log ───────────────────────────────────────────────────

    def log_extraction(
        self,
        conversation_id: str,
        user_message: str,
        extracted_facts: list[dict],
    ) -> None:
        """Write extraction event to the log table."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO extraction_log (conversation_id, user_message, extracted_facts, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, user_message, json.dumps(extracted_facts), now),
        )
        self.conn.commit()

    # ── Vector operations (optional, requires sqlite-vec) ────────────────

    @property
    def has_vector_search(self) -> bool:
        return self._has_vec

    def store_embedding(self, fact_id: str, vector: bytes) -> bool:
        """Store a vector embedding for a fact. Vector should be float32 bytes."""
        if not self._has_vec:
            return False
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO embeddings (fact_id, vector) VALUES (?, ?)",
                (fact_id, vector),
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.debug("Failed to store embedding: %s", e)
            return False

    def vector_search(self, query_vector: bytes, limit: int = 10) -> list[dict]:
        """Search facts by vector similarity. Returns [{fact_id, distance}, ...]."""
        if not self._has_vec:
            return []
        try:
            rows = self.conn.execute(
                "SELECT fact_id, distance FROM embeddings "
                "WHERE vector MATCH ? ORDER BY distance LIMIT ?",
                (query_vector, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.debug("Vector search failed: %s", e)
            return []
