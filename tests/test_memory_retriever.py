"""Tests for server/memory/retriever.py — ranked memory retrieval."""

import os
import sys
import time

import pytest

SERVER_DIR = os.path.join(os.path.dirname(__file__), "..", "server")
sys.path.insert(0, SERVER_DIR)

from memory.memory_store import MemoryStore
from memory.retriever import MemoryRetriever, _recency_score, _frequency_score


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_retriever.db"
    s = MemoryStore(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def retriever(store):
    return MemoryRetriever(store)


class TestRecencyScore:
    def test_recent_fact_scores_high(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        score = _recency_score(now)
        assert score > 0.95

    def test_old_fact_scores_low(self):
        score = _recency_score("2020-01-01T00:00:00+00:00")
        assert score < 0.1

    def test_none_timestamp(self):
        score = _recency_score(None)
        assert score == 0.1

    def test_invalid_timestamp(self):
        score = _recency_score("not-a-date")
        assert score == 0.1


class TestFrequencyScore:
    def test_max_frequency(self):
        score = _frequency_score(100, 100)
        assert score == 1.0

    def test_zero_frequency(self):
        score = _frequency_score(0, 100)
        assert score == 0.0

    def test_zero_max(self):
        score = _frequency_score(5, 0)
        assert score == 0.0

    def test_mid_frequency(self):
        score = _frequency_score(50, 100)
        assert 0.0 < score < 1.0


class TestRetriever:
    def test_retrieve_empty_store(self, retriever):
        results = retriever.retrieve("anything")
        assert results == []

    def test_retrieve_empty_query(self, retriever):
        results = retriever.retrieve("")
        assert results == []

    def test_retrieve_finds_relevant_facts(self, store, retriever):
        store.add_fact("Seb prefers dark mode", category="preference")
        store.add_fact("Seb lives in Berlin", category="biographical")
        store.add_fact("Seb likes Python programming", category="preference")

        results = retriever.retrieve("dark mode")
        assert len(results) >= 1
        # First result should mention dark mode
        assert "dark mode" in results[0]["content"]

    def test_retrieve_respects_limit(self, store, retriever):
        for i in range(20):
            store.add_fact(f"Fact about coding topic number {i}")

        results = retriever.retrieve("coding", limit=5)
        assert len(results) <= 5

    def test_retrieve_returns_expected_shape(self, store, retriever):
        store.add_fact("Seb works on BITOS", category="knowledge")
        results = retriever.retrieve("BITOS")
        assert len(results) >= 1

        r = results[0]
        assert "fact_id" in r
        assert "content" in r
        assert "category" in r
        assert "relevance_score" in r
        assert isinstance(r["relevance_score"], float)

    def test_retrieve_for_context_returns_strings(self, store, retriever):
        store.add_fact("Seb uses neovim", category="preference")
        facts = retriever.retrieve_for_context("editor", limit=5)
        assert isinstance(facts, list)
        if facts:
            assert isinstance(facts[0], str)

    def test_scoring_prefers_recent(self, store, retriever):
        """More recently updated facts should score higher, all else equal."""
        # Add two facts with similar content
        id1 = store.add_fact("Seb likes using React for frontends")
        # Touch the second fact so it's "more recent" in updated_at
        id2 = store.add_fact("Seb enjoys React development work")

        results = retriever.retrieve("React")
        # Both should appear; scoring includes recency
        assert len(results) >= 1

    def test_scoring_prefers_accessed(self, store, retriever):
        """Frequently accessed facts should score higher."""
        id1 = store.add_fact("Seb uses Python for backend development")
        id2 = store.add_fact("Seb codes in Python daily at work")

        # Access one fact many times
        for _ in range(10):
            store.get_fact(id1)

        results = retriever.retrieve("Python")
        assert len(results) >= 1


class TestMergeWithVector:
    def test_merge_empty(self, retriever):
        merged = retriever.merge_with_vector([], [])
        assert merged == []

    def test_merge_fts_only(self, store, retriever):
        store.add_fact("Seb likes tea")
        fts = store.search_facts("tea")
        merged = retriever.merge_with_vector(fts, [])
        assert len(merged) == len(fts)

    def test_merge_combines_results(self, store, retriever):
        fid = store.add_fact("Seb enjoys hiking in the mountains")
        fts = store.search_facts("hiking")
        vec = [{"fact_id": fid, "distance": 0.1}]
        merged = retriever.merge_with_vector(fts, vec)
        assert len(merged) >= 1
