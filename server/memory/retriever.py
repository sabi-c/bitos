"""Memory retriever: ranked recall combining FTS5, recency, and access frequency.

Score formula:
  final_score = text_relevance * 0.5 + recency * 0.3 + frequency * 0.2

When sqlite-vec is available, vector similarity results are merged via
reciprocal rank fusion before applying the composite score.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)

# Weights for composite scoring
W_TEXT = 0.5
W_RECENCY = 0.3
W_FREQUENCY = 0.2

# Recency half-life: facts older than this (in days) get half the recency score
RECENCY_HALF_LIFE_DAYS = 30.0

# RRF constant (standard value from information retrieval literature)
RRF_K = 60


def _recency_score(updated_at: Optional[str]) -> float:
    """Exponential decay score based on how recently a fact was updated.

    Returns 1.0 for facts updated just now, decaying toward 0.
    Half-life is RECENCY_HALF_LIFE_DAYS.
    """
    if not updated_at:
        return 0.1  # Unknown age gets minimal recency credit

    try:
        then = datetime.fromisoformat(updated_at)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = max(0, (now - then).total_seconds() / 86400)
        return math.exp(-0.693 * age_days / RECENCY_HALF_LIFE_DAYS)
    except (ValueError, TypeError):
        return 0.1


def _frequency_score(access_count: int, max_count: int) -> float:
    """Normalized frequency score (0 to 1).

    Uses log scale to prevent power-law domination.
    """
    if max_count <= 0:
        return 0.0
    if access_count <= 0:
        return 0.0
    return math.log1p(access_count) / math.log1p(max_count)


class MemoryRetriever:
    """Retrieve and rank memories by composite relevance score."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def retrieve(self, query: str, limit: int = 10) -> list[dict]:
        """Retrieve the most relevant memories for a query.

        Returns list of dicts:
          [{fact_id, content, category, relevance_score, last_accessed}, ...]
        """
        if not query.strip():
            return []

        # 1. FTS5 text search — get candidate pool
        fts_results = self._store.search_facts(query, limit=limit * 3)

        # 2. Vector search if available — merge with FTS results
        # (Skipped for now — sqlite-vec embedding generation not wired yet.
        #  When ready, call self._store.vector_search() and merge via RRF.)

        if not fts_results:
            # Fall back to recent facts if no text matches
            return self._score_and_rank(
                self._store.get_recent_facts(limit=limit),
                limit,
            )

        return self._score_and_rank(fts_results, limit)

    def retrieve_for_context(self, query: str, limit: int = 5) -> list[str]:
        """Convenience: retrieve facts formatted as strings for system prompt injection.

        Returns list of fact content strings, most relevant first.
        """
        results = self.retrieve(query, limit=limit)
        return [r["content"] for r in results]

    def _score_and_rank(self, candidates: list[dict], limit: int) -> list[dict]:
        """Apply composite scoring to candidate facts and return top-N."""
        if not candidates:
            return []

        # Find max access count for normalization
        max_access = max(
            (c.get("access_count", 0) for c in candidates),
            default=1,
        )

        scored = []
        for i, fact in enumerate(candidates):
            # Text relevance: inverse rank position from FTS (first = best)
            text_rel = 1.0 / (i + 1)

            # Recency
            recency = _recency_score(
                fact.get("updated_at") or fact.get("created_at")
            )

            # Frequency
            freq = _frequency_score(fact.get("access_count", 0), max_access)

            # Composite score
            score = (W_TEXT * text_rel) + (W_RECENCY * recency) + (W_FREQUENCY * freq)

            scored.append({
                "fact_id": fact.get("id", ""),
                "content": fact.get("content", ""),
                "category": fact.get("category", "general"),
                "relevance_score": round(score, 4),
                "last_accessed": fact.get("last_accessed"),
                "confidence": fact.get("confidence", 0.8),
            })

        # Sort by composite score descending
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Touch access counts for returned results
        for item in scored[:limit]:
            fid = item["fact_id"]
            if fid:
                try:
                    self._store.get_fact(fid)  # Increments access_count
                except Exception:
                    pass

        return scored[:limit]

    def merge_with_vector(
        self,
        fts_results: list[dict],
        vec_results: list[dict],
    ) -> list[dict]:
        """Merge FTS and vector search results using reciprocal rank fusion.

        For future use when sqlite-vec embeddings are wired in.
        """
        scores: dict[str, float] = {}
        metadata: dict[str, dict] = {}

        for rank, result in enumerate(fts_results):
            fid = result.get("id", "")
            scores[fid] = scores.get(fid, 0) + 1.0 / (rank + RRF_K)
            metadata[fid] = result

        for rank, result in enumerate(vec_results):
            fid = result.get("fact_id", "")
            scores[fid] = scores.get(fid, 0) + 1.0 / (rank + RRF_K)
            if fid not in metadata:
                # Need to fetch full fact
                full = self._store.get_fact(fid)
                if full:
                    metadata[fid] = full

        # Sort by RRF score
        ranked_ids = sorted(scores, key=scores.get, reverse=True)
        merged = []
        for fid in ranked_ids:
            if fid in metadata:
                m = metadata[fid].copy()
                m["rrf_score"] = scores[fid]
                merged.append(m)

        return merged
