"""Tests for server/memory/memory_store.py — SQLite-backed fact + episode storage."""

import json
import os
import sys
import tempfile

import pytest

# Ensure server/ is on the path
SERVER_DIR = os.path.join(os.path.dirname(__file__), "..", "server")
sys.path.insert(0, SERVER_DIR)

from memory.memory_store import MemoryStore, VALID_CATEGORIES


@pytest.fixture
def store(tmp_path):
    """Create a fresh MemoryStore with a temp database."""
    db_path = tmp_path / "test_memory.db"
    s = MemoryStore(db_path=db_path)
    yield s
    s.close()


class TestFactCRUD:
    def test_add_fact_returns_id(self, store):
        fact_id = store.add_fact("Seb prefers dark mode", category="preference")
        assert fact_id is not None
        assert len(fact_id) == 36  # UUID format

    def test_add_empty_fact_returns_none(self, store):
        assert store.add_fact("") is None
        assert store.add_fact("   ") is None

    def test_get_fact(self, store):
        fact_id = store.add_fact("Seb lives in London", category="biographical")
        fact = store.get_fact(fact_id)
        assert fact is not None
        assert fact["content"] == "Seb lives in London"
        assert fact["category"] == "biographical"

    def test_get_fact_increments_access_count(self, store):
        fact_id = store.add_fact("Seb uses vim")
        store.get_fact(fact_id)  # access_count: 0 -> 1
        store.get_fact(fact_id)  # access_count: 1 -> 2
        fact = store.get_fact(fact_id)  # reads count=2, then increments to 3
        assert fact["access_count"] == 2  # Value read before this call's increment

    def test_get_nonexistent_fact(self, store):
        assert store.get_fact("nonexistent-uuid") is None

    def test_update_fact(self, store):
        fact_id = store.add_fact("Seb likes coffee")
        updated = store.update_fact(fact_id, "Seb loves espresso")
        assert updated is True
        fact = store.get_fact(fact_id)
        assert fact["content"] == "Seb loves espresso"

    def test_update_nonexistent(self, store):
        assert store.update_fact("bad-id", "new content") is False

    def test_update_empty_content(self, store):
        fact_id = store.add_fact("something")
        assert store.update_fact(fact_id, "") is False

    def test_deactivate_fact(self, store):
        fact_id = store.add_fact("temporary fact")
        assert store.deactivate_fact(fact_id) is True
        assert store.get_fact(fact_id) is None

    def test_deactivate_nonexistent(self, store):
        assert store.deactivate_fact("bad-id") is False

    def test_supersede_fact(self, store):
        old_id = store.add_fact("Seb works at CompanyA", category="biographical")
        new_id = store.supersede_fact(old_id, "Seb works at CompanyB", category="biographical")
        assert new_id is not None
        assert new_id != old_id
        # Old fact should be deactivated
        assert store.get_fact(old_id) is None
        # New fact should be active
        new_fact = store.get_fact(new_id)
        assert new_fact["content"] == "Seb works at CompanyB"

    def test_invalid_category_defaults_to_general(self, store):
        fact_id = store.add_fact("some fact", category="invalid_cat")
        fact = store.get_fact(fact_id)
        assert fact["category"] == "general"

    def test_all_valid_categories(self, store):
        for cat in VALID_CATEGORIES:
            fid = store.add_fact(f"fact for {cat}", category=cat)
            fact = store.get_fact(fid)
            assert fact["category"] == cat


class TestDeduplication:
    def test_duplicate_fact_returns_existing_id(self, store):
        id1 = store.add_fact("Seb prefers dark mode in all apps")
        id2 = store.add_fact("Seb prefers dark mode in all apps")
        assert id1 == id2

    def test_similar_fact_is_deduplicated(self, store):
        id1 = store.add_fact("Seb prefers dark mode in his applications")
        id2 = store.add_fact("Seb prefers dark mode in all applications")
        # High word overlap should trigger dedup
        assert id1 == id2

    def test_different_facts_are_both_stored(self, store):
        id1 = store.add_fact("Seb likes cats")
        id2 = store.add_fact("Seb drives a Tesla Model 3")
        assert id1 != id2


class TestSearch:
    def test_search_finds_matching_fact(self, store):
        store.add_fact("Seb prefers dark mode", category="preference")
        store.add_fact("Seb lives in Berlin", category="biographical")
        results = store.search_facts("dark mode")
        assert len(results) >= 1
        assert any("dark mode" in r["content"] for r in results)

    def test_search_empty_query(self, store):
        assert store.search_facts("") == []

    def test_search_no_results(self, store):
        store.add_fact("Seb likes pizza")
        results = store.search_facts("quantum mechanics")
        assert len(results) == 0

    def test_search_respects_limit(self, store):
        for i in range(15):
            store.add_fact(f"Fact number {i} about coding style {i}")
        results = store.search_facts("coding", limit=5)
        assert len(results) <= 5

    def test_get_recent_facts(self, store):
        store.add_fact("fact one")
        store.add_fact("fact two")
        store.add_fact("fact three")
        recent = store.get_recent_facts(limit=2)
        assert len(recent) == 2

    def test_get_facts_by_category(self, store):
        store.add_fact("pref one", category="preference")
        store.add_fact("bio one", category="biographical")
        store.add_fact("pref two", category="preference")
        prefs = store.get_facts_by_category("preference")
        assert len(prefs) == 2
        assert all(f["category"] == "preference" for f in prefs)


class TestEpisodes:
    def test_add_and_get_episode(self, store):
        eid = store.add_episode(
            conversation_id="conv-123",
            summary="Discussed project timeline",
            key_topics=["project", "deadline"],
            emotional_tone="focused",
        )
        assert eid is not None

        episodes = store.get_episodes(conversation_id="conv-123")
        assert len(episodes) == 1
        assert episodes[0]["summary"] == "Discussed project timeline"
        assert episodes[0]["key_topics"] == ["project", "deadline"]
        assert episodes[0]["emotional_tone"] == "focused"

    def test_get_all_episodes(self, store):
        store.add_episode("conv-1", "First conversation")
        store.add_episode("conv-2", "Second conversation")
        episodes = store.get_episodes()
        assert len(episodes) == 2

    def test_episode_limit(self, store):
        for i in range(10):
            store.add_episode(f"conv-{i}", f"Episode {i}")
        episodes = store.get_episodes(limit=3)
        assert len(episodes) == 3


class TestExtractionLog:
    def test_log_extraction(self, store):
        # Should not raise
        store.log_extraction(
            conversation_id="conv-456",
            user_message="I live in Paris",
            extracted_facts=[{"content": "User lives in Paris", "category": "biographical"}],
        )


class TestCountAndStats:
    def test_count_facts(self, store):
        assert store.count_facts() == 0
        store.add_fact("fact one")
        store.add_fact("fact two")
        assert store.count_facts() == 2

    def test_count_includes_deactivated(self, store):
        fid = store.add_fact("will be removed")
        store.deactivate_fact(fid)
        assert store.count_facts(active_only=True) == 0
        assert store.count_facts(active_only=False) == 1

    def test_has_vector_search_property(self, store):
        # sqlite-vec likely not installed in test env
        assert isinstance(store.has_vector_search, bool)
