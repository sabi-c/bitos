"""BITOS Memory System — structured fact storage, extraction, and retrieval.

Provides:
- MemoryStore: SQLite-backed fact + episode storage with FTS5 search
- FactExtractor: LLM-powered fact extraction from conversations (Haiku)
- MemoryRetriever: Ranked memory recall combining text relevance, recency, frequency
"""

from memory.memory_store import MemoryStore
from memory.fact_extractor import FactExtractor
from memory.retriever import MemoryRetriever

__all__ = ["MemoryStore", "FactExtractor", "MemoryRetriever"]
