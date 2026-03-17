"""Music listening logger and taste profile builder for BITOS.

Polls Spotify recently-played API every 60s to log new plays.
Builds aggregate taste profile for agent music intelligence.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Same DB as spotify_adapter listening_history
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "listening_history.db"

# Taste profile cache key prefix
_TASTE_KEY_PREFIX = "taste_"


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Ensure taste_profile table exists alongside listening_history."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS taste_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
    """)


# Init tables on import
try:
    _init_conn = _get_db()
    _ensure_tables(_init_conn)
    _init_conn.close()
except Exception as _e:
    logger.warning("music_logger db init failed (non-critical): %s", _e)


class MusicLogger:
    """Tracks listening history and builds taste profile.

    Polls Spotify recently-played API to log new plays.
    Builds aggregate taste profile periodically.
    """

    def __init__(self, spotify_adapter=None):
        self._spotify = spotify_adapter
        self._last_poll_time: float = 0

    def set_spotify(self, spotify_adapter) -> None:
        """Set or replace the Spotify adapter (for lazy init)."""
        self._spotify = spotify_adapter

    def poll_and_log(self) -> int:
        """Poll recently played and log new entries.

        Delegates to SpotifyAdapter.log_recently_played() which handles
        dedup and persistence. Returns count of new entries logged.
        """
        if not self._spotify or not self._spotify.available:
            return 0

        try:
            count = self._spotify.log_recently_played()
            self._last_poll_time = time.time()
            return count
        except Exception as exc:
            logger.warning("music_logger_poll_error: %s", exc)
            return 0

    def build_taste_profile(self) -> dict[str, Any]:
        """Aggregate listening history into taste profile.

        Returns a dict with top artists, listening patterns, etc.
        Also persists the profile in the taste_profile table.
        """
        conn = _get_db()
        try:
            profile = {
                "top_artists_30d": self._top_artists(conn, days=30),
                "total_tracks_30d": self._count(conn, days=30),
                "total_hours_30d": self._total_hours(conn, days=30),
                "listening_by_hour": self._by_hour_of_day(conn),
                "listening_by_day": self._by_day_of_week(conn),
                "discovery_rate": self._new_artist_rate(conn, days=30),
                "top_contexts": self._top_contexts(conn, days=30),
                "top_tracks_30d": self._top_tracks(conn, days=30),
            }

            # Persist profile
            now = time.time()
            for key, value in profile.items():
                conn.execute(
                    """INSERT OR REPLACE INTO taste_profile (key, value, updated_at)
                       VALUES (?, ?, ?)""",
                    (f"{_TASTE_KEY_PREFIX}{key}", json.dumps(value), now),
                )
            conn.commit()

            logger.info("taste_profile_built: %d artists, %d tracks in 30d",
                        len(profile.get("top_artists_30d", [])),
                        profile.get("total_tracks_30d", 0))
            return profile

        except Exception as exc:
            logger.warning("taste_profile_build_error: %s", exc)
            return {}
        finally:
            conn.close()

    def get_cached_profile(self) -> dict[str, Any]:
        """Get the last-built taste profile from DB cache."""
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT key, value FROM taste_profile WHERE key LIKE ?",
                (f"{_TASTE_KEY_PREFIX}%",),
            ).fetchall()
            profile = {}
            for row in rows:
                key = row["key"].replace(_TASTE_KEY_PREFIX, "", 1)
                try:
                    profile[key] = json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    profile[key] = row["value"]
            return profile
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Aggregation queries
    # ------------------------------------------------------------------

    @staticmethod
    def _top_artists(conn: sqlite3.Connection, days: int = 30, limit: int = 10) -> list[dict]:
        """Top artists by play count in the last N days."""
        cutoff = _days_ago_iso(days)
        rows = conn.execute(
            """SELECT artist_name, COUNT(*) as plays
               FROM listening_history
               WHERE played_at >= ?
               GROUP BY artist_name
               ORDER BY plays DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [{"artist": r["artist_name"], "plays": r["plays"]} for r in rows]

    @staticmethod
    def _top_tracks(conn: sqlite3.Connection, days: int = 30, limit: int = 10) -> list[dict]:
        """Top tracks by play count in the last N days."""
        cutoff = _days_ago_iso(days)
        rows = conn.execute(
            """SELECT track_name, artist_name, COUNT(*) as plays
               FROM listening_history
               WHERE played_at >= ?
               GROUP BY spotify_track_id
               ORDER BY plays DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [
            {"track": r["track_name"], "artist": r["artist_name"], "plays": r["plays"]}
            for r in rows
        ]

    @staticmethod
    def _count(conn: sqlite3.Connection, days: int = 30) -> int:
        """Total track plays in the last N days."""
        cutoff = _days_ago_iso(days)
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM listening_history WHERE played_at >= ?",
            (cutoff,),
        ).fetchone()
        return row["cnt"] if row else 0

    @staticmethod
    def _total_hours(conn: sqlite3.Connection, days: int = 30) -> float:
        """Total listening hours in the last N days."""
        cutoff = _days_ago_iso(days)
        row = conn.execute(
            "SELECT COALESCE(SUM(duration_ms), 0) as total_ms FROM listening_history WHERE played_at >= ?",
            (cutoff,),
        ).fetchone()
        return round((row["total_ms"] or 0) / 3_600_000, 1)

    @staticmethod
    def _by_hour_of_day(conn: sqlite3.Connection, days: int = 30) -> dict[str, int]:
        """Listening distribution by hour of day (0-23)."""
        cutoff = _days_ago_iso(days)
        rows = conn.execute(
            """SELECT played_at FROM listening_history WHERE played_at >= ?""",
            (cutoff,),
        ).fetchall()

        hours: Counter = Counter()
        for row in rows:
            try:
                dt = datetime.fromisoformat(row["played_at"].replace("Z", "+00:00"))
                hours[str(dt.hour)] += 1
            except (ValueError, AttributeError):
                pass
        return dict(hours.most_common(24))

    @staticmethod
    def _by_day_of_week(conn: sqlite3.Connection, days: int = 30) -> dict[str, int]:
        """Listening distribution by day of week."""
        cutoff = _days_ago_iso(days)
        rows = conn.execute(
            "SELECT played_at FROM listening_history WHERE played_at >= ?",
            (cutoff,),
        ).fetchall()

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        days_counter: Counter = Counter()
        for row in rows:
            try:
                dt = datetime.fromisoformat(row["played_at"].replace("Z", "+00:00"))
                days_counter[day_names[dt.weekday()]] += 1
            except (ValueError, AttributeError):
                pass
        return dict(days_counter)

    @staticmethod
    def _new_artist_rate(conn: sqlite3.Connection, days: int = 30) -> float:
        """Percentage of plays in last N days from artists not heard before that period."""
        cutoff = _days_ago_iso(days)

        # Artists heard before the period
        old_artists = set()
        rows = conn.execute(
            "SELECT DISTINCT artist_name FROM listening_history WHERE played_at < ?",
            (cutoff,),
        ).fetchall()
        for r in rows:
            old_artists.add(r["artist_name"])

        # Recent plays
        recent = conn.execute(
            "SELECT artist_name FROM listening_history WHERE played_at >= ?",
            (cutoff,),
        ).fetchall()

        if not recent:
            return 0.0

        new_count = sum(1 for r in recent if r["artist_name"] not in old_artists)
        return round(new_count / len(recent) * 100, 1)

    @staticmethod
    def _top_contexts(conn: sqlite3.Connection, days: int = 30, limit: int = 5) -> list[dict]:
        """Top listening contexts (playlists, albums, etc.)."""
        cutoff = _days_ago_iso(days)
        rows = conn.execute(
            """SELECT context, COUNT(*) as plays
               FROM listening_history
               WHERE played_at >= ? AND context != '' AND context IS NOT NULL
               GROUP BY context
               ORDER BY plays DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [{"context": r["context"], "plays": r["plays"]} for r in rows]


# ── Helpers ──────────────────────────────────────────────────────────────

def _days_ago_iso(days: int) -> str:
    """Return ISO timestamp for N days ago."""
    from datetime import timedelta
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.isoformat()


# ── Module-level singleton ───────────────────────────────────────────────

_instance: MusicLogger | None = None


def get_music_logger() -> MusicLogger:
    """Get or create the singleton MusicLogger."""
    global _instance
    if _instance is None:
        _instance = MusicLogger()
    return _instance
