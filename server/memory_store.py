"""Long-term memory store: fact storage and retrieval with FTS5 full-text search.

SQLite-backed at server/data/memory.db (WAL mode). Stores extracted facts
about the user — preferences, personal info, work context, habits — and
provides keyword search via FTS5 for injection into the system prompt.

Deduplication: word-Jaccard similarity check before every insert (threshold 0.75).
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "data" / "memory.db"
DEDUP_THRESHOLD = 0.75  # Jaccard similarity above this -> skip insert


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            source TEXT DEFAULT 'auto',
            confidence REAL DEFAULT 0.8,
            category TEXT DEFAULT 'general',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS memory_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            user_message TEXT,
            extracted_facts TEXT,
            created_at TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
            fact_id UNINDEXED,
            content,
            category
        );
    """)


# Initialise tables on import
_init_conn = _get_conn()
_ensure_tables(_init_conn)
_init_conn.close()


# ── FTS query helpers ────────────────────────────────────────────────────

def _escape_fts_query(query: str) -> str:
    """Escape special FTS5 characters to prevent query syntax errors."""
    for char in ['"', "'", '*', '-', '+', '(', ')', ':', '^', '{', '}']:
        query = query.replace(char, ' ')
    words = [w.strip() for w in query.split() if w.strip()]
    if not words:
        return ""
    return " OR ".join(f'"{w}"' for w in words)


def _word_jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two word sets."""
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union > 0 else 0.0


def _find_similar(conn: sqlite3.Connection, content: str) -> int | None:
    """Return the fact id of an existing fact if sufficiently similar, else None."""
    safe_query = _escape_fts_query(content)
    if not safe_query:
        return None

    rows = conn.execute(
        "SELECT fact_id, content FROM facts_fts WHERE facts_fts MATCH ? LIMIT 20",
        (safe_query,),
    ).fetchall()

    new_words = set(content.lower().split())
    for row in rows:
        existing_words = set(row["content"].lower().split())
        if _word_jaccard(new_words, existing_words) >= DEDUP_THRESHOLD:
            return row["fact_id"]
    return None


# ── Public API ───────────────────────────────────────────────────────────

def add_fact(
    content: str,
    source: str = "auto",
    confidence: float = 0.8,
    category: str = "general",
) -> int:
    """Store a fact, skipping if a similar one already exists. Returns fact id."""
    content = content.strip()
    if not content:
        return 0

    conn = _get_conn()
    try:
        existing_id = _find_similar(conn, content)
        if existing_id:
            logger.debug("Dedup skip (similar to %s): %.60s", existing_id, content)
            return existing_id

        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO facts (content, source, confidence, category, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (content, source, confidence, category, now, now),
        )
        fact_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO facts_fts (fact_id, content, category) VALUES (?, ?, ?)",
            (fact_id, content, category),
        )
        conn.commit()
        logger.info("Stored fact #%d: %.80s", fact_id, content)
        return fact_id
    finally:
        conn.close()


def search_facts(query: str, limit: int = 10) -> list[dict]:
    """Search facts using FTS5 keyword matching. Returns list of fact dicts."""
    safe_query = _escape_fts_query(query)
    if not safe_query:
        return []

    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT f.id, f.content, f.category, f.confidence, f.source, f.created_at "
            "FROM facts_fts ft "
            "JOIN facts f ON f.id = ft.fact_id "
            "WHERE facts_fts MATCH ? AND f.active = 1 "
            "ORDER BY ft.rank LIMIT ?",
            (safe_query, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_facts(limit: int = 20) -> list[dict]:
    """Return most recent active facts."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, content, category, confidence, source, created_at, updated_at "
            "FROM facts WHERE active = 1 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_facts_by_category(category: str) -> list[dict]:
    """Return active facts in a given category."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, content, category, confidence, source, created_at "
            "FROM facts WHERE active = 1 AND category = ? ORDER BY created_at DESC",
            (category,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def deactivate_fact(fact_id: int) -> bool:
    """Soft-delete a fact. Returns True if a row was updated."""
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "UPDATE facts SET active = 0, updated_at = ? WHERE id = ?",
            (now, fact_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_fact(fact_id: int, content: str) -> bool:
    """Update a fact's content. Returns True if a row was updated."""
    content = content.strip()
    if not content:
        return False

    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "UPDATE facts SET content = ?, updated_at = ? WHERE id = ? AND active = 1",
            (content, now, fact_id),
        )
        # Update FTS index too
        if cursor.rowcount > 0:
            conn.execute(
                "UPDATE facts_fts SET content = ? WHERE fact_id = ?",
                (content, fact_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def log_extraction(
    conversation_id: str,
    user_message: str,
    extracted_facts: list[dict],
) -> None:
    """Write a raw extraction entry to the memory_log table."""
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO memory_log (conversation_id, user_message, extracted_facts, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, user_message, json.dumps(extracted_facts), now),
        )
        conn.commit()
    finally:
        conn.close()
