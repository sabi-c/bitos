"""Tests for MusicLogger — polling, dedup, taste profile aggregation."""
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure server/ is on path
SERVER_DIR = os.path.join(os.path.dirname(__file__), "..", "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

INTEGRATIONS_DIR = os.path.join(SERVER_DIR, "integrations")
if INTEGRATIONS_DIR not in sys.path:
    sys.path.insert(0, INTEGRATIONS_DIR)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary listening history DB."""
    db_path = tmp_path / "test_listening.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listening_history (
            id TEXT PRIMARY KEY,
            spotify_track_id TEXT,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            duration_ms INTEGER,
            played_at TEXT,
            context TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_lh_played ON listening_history(played_at DESC);
        CREATE INDEX IF NOT EXISTS idx_lh_artist ON listening_history(artist_name, played_at DESC);
        CREATE INDEX IF NOT EXISTS idx_lh_track_id ON listening_history(spotify_track_id);

        CREATE TABLE IF NOT EXISTS taste_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
    """)
    conn.close()
    return db_path


@pytest.fixture
def populated_db(tmp_db):
    """Create a DB with some listening history."""
    conn = sqlite3.connect(str(tmp_db))
    now = datetime.now(timezone.utc)

    entries = [
        ("lh_001", "t1", "Bohemian Rhapsody", "Queen", "Night at the Opera", 354000,
         (now - timedelta(days=1)).isoformat(), "album"),
        ("lh_002", "t2", "Don't Stop Me Now", "Queen", "Jazz", 210000,
         (now - timedelta(days=2)).isoformat(), "playlist"),
        ("lh_003", "t3", "Hey Jude", "The Beatles", "Hey Jude", 420000,
         (now - timedelta(days=3)).isoformat(), "album"),
        ("lh_004", "t1", "Bohemian Rhapsody", "Queen", "Night at the Opera", 354000,
         (now - timedelta(days=5)).isoformat(), "album"),
        ("lh_005", "t4", "Stairway to Heaven", "Led Zeppelin", "IV", 480000,
         (now - timedelta(days=10)).isoformat(), ""),
        ("lh_006", "t5", "Hotel California", "Eagles", "Hotel California", 390000,
         (now - timedelta(days=15)).isoformat(), "playlist"),
        # Old entry (40 days ago, outside 30-day window)
        ("lh_007", "t6", "Old Song", "Old Artist", "Old Album", 200000,
         (now - timedelta(days=40)).isoformat(), ""),
    ]
    for entry in entries:
        conn.execute(
            """INSERT INTO listening_history
               (id, spotify_track_id, track_name, artist_name, album_name,
                duration_ms, played_at, context)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            entry,
        )
    conn.commit()
    conn.close()
    return tmp_db


class TestMusicLoggerPolling:
    def test_poll_and_log_success(self):
        """Test that poll_and_log delegates to SpotifyAdapter."""
        from integrations.music_logger import MusicLogger

        mock_sp = MagicMock()
        mock_sp.available = True
        mock_sp.log_recently_played.return_value = 3

        ml = MusicLogger(spotify_adapter=mock_sp)
        count = ml.poll_and_log()
        assert count == 3
        mock_sp.log_recently_played.assert_called_once()

    def test_poll_and_log_unavailable(self):
        """Test graceful handling when Spotify is unavailable."""
        from integrations.music_logger import MusicLogger

        mock_sp = MagicMock()
        mock_sp.available = False

        ml = MusicLogger(spotify_adapter=mock_sp)
        count = ml.poll_and_log()
        assert count == 0

    def test_poll_and_log_no_adapter(self):
        """Test graceful handling when no adapter is set."""
        from integrations.music_logger import MusicLogger

        ml = MusicLogger()
        count = ml.poll_and_log()
        assert count == 0

    def test_set_spotify(self):
        """Test lazy adapter initialization."""
        from integrations.music_logger import MusicLogger

        ml = MusicLogger()
        mock_sp = MagicMock()
        mock_sp.available = True
        mock_sp.log_recently_played.return_value = 1

        ml.set_spotify(mock_sp)
        assert ml.poll_and_log() == 1


class TestMusicLoggerTasteProfile:
    def test_build_taste_profile(self, populated_db):
        """Test taste profile building from listening history."""
        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", populated_db):
            ml = MusicLogger()
            profile = ml.build_taste_profile()

        assert "top_artists_30d" in profile
        assert "total_tracks_30d" in profile
        assert "total_hours_30d" in profile
        assert "listening_by_hour" in profile
        assert "listening_by_day" in profile
        assert "discovery_rate" in profile
        assert "top_tracks_30d" in profile

        # Queen should be top artist (3 plays in 30 days)
        top_artists = profile["top_artists_30d"]
        assert len(top_artists) > 0
        assert top_artists[0]["artist"] == "Queen"
        assert top_artists[0]["plays"] >= 2

        # Total tracks in 30d should be 6 (not 7 — old song is outside window)
        assert profile["total_tracks_30d"] == 6

    def test_build_taste_profile_persists(self, populated_db):
        """Test that taste profile is persisted in taste_profile table."""
        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", populated_db):
            ml = MusicLogger()
            ml.build_taste_profile()

            # Check it was persisted
            cached = ml.get_cached_profile()
            assert "top_artists_30d" in cached
            assert len(cached["top_artists_30d"]) > 0

    def test_get_cached_profile_empty(self, tmp_db):
        """Test empty cache returns empty dict."""
        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", tmp_db):
            ml = MusicLogger()
            profile = ml.get_cached_profile()
            assert profile == {}

    def test_top_tracks(self, populated_db):
        """Test top tracks aggregation."""
        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", populated_db):
            ml = MusicLogger()
            profile = ml.build_taste_profile()

        top_tracks = profile["top_tracks_30d"]
        assert len(top_tracks) > 0
        # Bohemian Rhapsody played twice in 30d
        br = [t for t in top_tracks if t["track"] == "Bohemian Rhapsody"]
        assert len(br) == 1
        assert br[0]["plays"] == 2

    def test_total_hours(self, populated_db):
        """Test total listening hours calculation."""
        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", populated_db):
            ml = MusicLogger()
            profile = ml.build_taste_profile()

        # Sum of durations for 6 tracks in 30d window
        assert profile["total_hours_30d"] > 0

    def test_top_contexts(self, populated_db):
        """Test top listening contexts."""
        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", populated_db):
            ml = MusicLogger()
            profile = ml.build_taste_profile()

        contexts = profile["top_contexts"]
        assert len(contexts) > 0
        # album and playlist should be in contexts
        context_names = [c["context"] for c in contexts]
        assert "album" in context_names

    def test_discovery_rate_no_old_data(self, tmp_db):
        """Test discovery rate when there's no old data."""
        conn = sqlite3.connect(str(tmp_db))
        now = datetime.now(timezone.utc)
        conn.execute(
            """INSERT INTO listening_history
               (id, spotify_track_id, track_name, artist_name, album_name,
                duration_ms, played_at, context)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("lh_new", "t1", "New Song", "New Artist", "New Album", 200000,
             now.isoformat(), ""),
        )
        conn.commit()
        conn.close()

        from integrations.music_logger import MusicLogger

        with patch("integrations.music_logger._DB_PATH", tmp_db):
            ml = MusicLogger()
            profile = ml.build_taste_profile()

        # All artists are "new" since there's no old data
        assert profile["discovery_rate"] == 100.0


class TestMusicLoggerSingleton:
    def test_singleton(self):
        from integrations.music_logger import get_music_logger

        with patch("integrations.music_logger._instance", None):
            ml1 = get_music_logger()
            # Reset to test the singleton behavior
            from integrations import music_logger as ml_mod
            ml2 = get_music_logger()
            assert ml1 is ml2
