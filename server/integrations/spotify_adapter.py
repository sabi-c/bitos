"""Spotify Web API adapter for BITOS.

Handles OAuth2 Authorization Code + PKCE flow, playback control,
search, playlists, queue, and now-playing metadata.

Env vars:
    SPOTIFY_CLIENT_ID    - from Spotify Developer Dashboard
    SPOTIFY_CLIENT_SECRET - for auth code flow
    SPOTIFY_REDIRECT_URI - callback URL (default: http://localhost:8000/callback/spotify)

Dependencies:
    spotipy>=2.24.0 (optional — graceful fallback if not installed)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Optional spotipy import ──────────────────────────────────────────────

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    _HAS_SPOTIPY = True
except ImportError:
    spotipy = None  # type: ignore[assignment]
    SpotifyOAuth = None  # type: ignore[assignment, misc]
    _HAS_SPOTIPY = False
    logger.info("spotipy not installed — Spotify integration disabled")

# ── Config ───────────────────────────────────────────────────────────────

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get(
    "SPOTIFY_REDIRECT_URI", "http://localhost:8000/callback/spotify"
)

_SCOPES = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "user-read-recently-played "
    "user-top-read "
    "playlist-read-private "
    "playlist-read-collaborative "
    "user-library-read"
)

# ── Listening history DB ────────────────────────────────────────────────

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "listening_history.db"


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
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

        CREATE INDEX IF NOT EXISTS idx_lh_played
          ON listening_history(played_at DESC);

        CREATE INDEX IF NOT EXISTS idx_lh_artist
          ON listening_history(artist_name, played_at DESC);

        CREATE INDEX IF NOT EXISTS idx_lh_track_id
          ON listening_history(spotify_track_id);
    """)


# Initialise tables on import
try:
    _init_conn = _get_db()
    _ensure_tables(_init_conn)
    _init_conn.close()
except Exception as _e:
    logger.warning("listening_history db init failed (non-critical): %s", _e)


# ── SpotifyAdapter ──────────────────────────────────────────────────────


class SpotifyAdapter:
    """Spotify Web API wrapper for BITOS agent tools.

    All methods are synchronous (spotipy is sync). The caller should run
    them in a thread executor if needed for async contexts.
    """

    def __init__(self) -> None:
        self._sp: Any | None = None
        self._auth_manager: Any | None = None
        self._available = False

        if not _HAS_SPOTIPY:
            logger.info("SpotifyAdapter: spotipy not installed, adapter disabled")
            return

        if not SPOTIFY_CLIENT_ID:
            logger.info("SpotifyAdapter: SPOTIFY_CLIENT_ID not set, adapter disabled")
            return

        cache_path = Path(__file__).resolve().parent.parent / "data" / ".spotify_cache"
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        self._auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET or None,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=_SCOPES,
            cache_path=str(cache_path),
            open_browser=False,
        )

        # Try to get a cached token
        token_info = self._auth_manager.get_cached_token()
        if token_info:
            self._sp = spotipy.Spotify(auth_manager=self._auth_manager)
            self._available = True
            logger.info("SpotifyAdapter: authenticated with cached token")
        else:
            logger.info(
                "SpotifyAdapter: no cached token — visit /spotify/auth to authenticate"
            )

    # ── Auth helpers ─────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Whether the adapter has a valid authenticated session."""
        return self._available

    @property
    def installed(self) -> bool:
        """Whether spotipy is installed."""
        return _HAS_SPOTIPY

    def get_auth_url(self) -> str | None:
        """Get the Spotify OAuth authorization URL for the user to visit."""
        if not self._auth_manager:
            return None
        return self._auth_manager.get_authorize_url()

    def handle_auth_callback(self, code: str) -> bool:
        """Exchange authorization code for access token. Returns True on success."""
        if not self._auth_manager:
            return False
        try:
            token_info = self._auth_manager.get_access_token(code, as_dict=True)
            if token_info:
                self._sp = spotipy.Spotify(auth_manager=self._auth_manager)
                self._available = True
                logger.info("SpotifyAdapter: OAuth callback successful")
                return True
        except Exception as exc:
            logger.error("SpotifyAdapter: OAuth callback failed: %s", exc)
        return False

    def _ensure_client(self) -> bool:
        """Ensure we have a valid client. Auto-refreshes token if expired."""
        if not self._sp or not self._auth_manager:
            return False
        # spotipy's auth_manager auto-refreshes on each request
        return True

    # ── Playback control ────────────────────────────────────────────

    def get_now_playing(self) -> dict | None:
        """Get the currently playing track. Returns None if nothing is playing."""
        if not self._ensure_client():
            return None
        try:
            current = self._sp.current_playback()
            if not current or not current.get("item"):
                return None
            item = current["item"]
            artists = ", ".join(a["name"] for a in item.get("artists", []))
            return {
                "track": item.get("name", ""),
                "artist": artists,
                "album": item.get("album", {}).get("name", ""),
                "album_art_url": (item.get("album", {}).get("images", [{}])[0].get("url", "") if item.get("album", {}).get("images") else ""),
                "uri": item.get("uri", ""),
                "spotify_track_id": item.get("id", ""),
                "progress_ms": current.get("progress_ms", 0),
                "duration_ms": item.get("duration_ms", 0),
                "is_playing": current.get("is_playing", False),
            }
        except Exception as exc:
            logger.warning("spotify_now_playing_error: %s", exc)
            return None

    def play(self, uri: str | None = None, context_uri: str | None = None) -> bool:
        """Start or resume playback. Optionally play a specific track or context."""
        if not self._ensure_client():
            return False
        try:
            kwargs: dict[str, Any] = {}
            if uri:
                kwargs["uris"] = [uri]
            elif context_uri:
                kwargs["context_uri"] = context_uri
            self._sp.start_playback(**kwargs)
            return True
        except Exception as exc:
            logger.warning("spotify_play_error: %s", exc)
            return False

    def pause(self) -> bool:
        """Pause playback."""
        if not self._ensure_client():
            return False
        try:
            self._sp.pause_playback()
            return True
        except Exception as exc:
            logger.warning("spotify_pause_error: %s", exc)
            return False

    def skip(self) -> bool:
        """Skip to next track."""
        if not self._ensure_client():
            return False
        try:
            self._sp.next_track()
            return True
        except Exception as exc:
            logger.warning("spotify_skip_error: %s", exc)
            return False

    def previous(self) -> bool:
        """Go to previous track."""
        if not self._ensure_client():
            return False
        try:
            self._sp.previous_track()
            return True
        except Exception as exc:
            logger.warning("spotify_previous_error: %s", exc)
            return False

    def set_volume(self, volume_percent: int) -> bool:
        """Set playback volume (0-100)."""
        if not self._ensure_client():
            return False
        try:
            vol = max(0, min(100, volume_percent))
            self._sp.volume(vol)
            return True
        except Exception as exc:
            logger.warning("spotify_volume_error: %s", exc)
            return False

    def shuffle(self, state: bool) -> bool:
        """Set shuffle on/off."""
        if not self._ensure_client():
            return False
        try:
            self._sp.shuffle(state)
            return True
        except Exception as exc:
            logger.warning("spotify_shuffle_error: %s", exc)
            return False

    def repeat(self, state: str) -> bool:
        """Set repeat mode: 'off', 'track', or 'context'."""
        if not self._ensure_client():
            return False
        try:
            self._sp.repeat(state)
            return True
        except Exception as exc:
            logger.warning("spotify_repeat_error: %s", exc)
            return False

    # ── Search & browse ─────────────────────────────────────────────

    def search(self, query: str, search_type: str = "track", limit: int = 5) -> list[dict]:
        """Search Spotify. Returns simplified results."""
        if not self._ensure_client():
            return []
        try:
            results = self._sp.search(q=query, type=search_type, limit=limit)
            items_key = f"{search_type}s"
            raw_items = results.get(items_key, {}).get("items", [])

            out: list[dict] = []
            for item in raw_items:
                if search_type == "track":
                    artists = ", ".join(a["name"] for a in item.get("artists", []))
                    out.append({
                        "name": item.get("name", ""),
                        "artist": artists,
                        "album": item.get("album", {}).get("name", ""),
                        "uri": item.get("uri", ""),
                        "duration_ms": item.get("duration_ms", 0),
                    })
                elif search_type == "artist":
                    out.append({
                        "name": item.get("name", ""),
                        "uri": item.get("uri", ""),
                        "genres": item.get("genres", [])[:3],
                        "followers": item.get("followers", {}).get("total", 0),
                    })
                elif search_type == "album":
                    artists = ", ".join(a["name"] for a in item.get("artists", []))
                    out.append({
                        "name": item.get("name", ""),
                        "artist": artists,
                        "uri": item.get("uri", ""),
                        "total_tracks": item.get("total_tracks", 0),
                    })
                elif search_type == "playlist":
                    out.append({
                        "name": item.get("name", ""),
                        "uri": item.get("uri", ""),
                        "owner": item.get("owner", {}).get("display_name", ""),
                        "tracks": item.get("tracks", {}).get("total", 0),
                    })
            return out
        except Exception as exc:
            logger.warning("spotify_search_error: %s", exc)
            return []

    def get_playlists(self, limit: int = 20) -> list[dict]:
        """Get the user's playlists."""
        if not self._ensure_client():
            return []
        try:
            results = self._sp.current_user_playlists(limit=limit)
            return [
                {
                    "name": p.get("name", ""),
                    "uri": p.get("uri", ""),
                    "tracks": p.get("tracks", {}).get("total", 0),
                    "owner": p.get("owner", {}).get("display_name", ""),
                }
                for p in results.get("items", [])
            ]
        except Exception as exc:
            logger.warning("spotify_playlists_error: %s", exc)
            return []

    def queue_track(self, uri: str) -> bool:
        """Add a track to the playback queue."""
        if not self._ensure_client():
            return False
        try:
            self._sp.add_to_queue(uri)
            return True
        except Exception as exc:
            logger.warning("spotify_queue_error: %s", exc)
            return False

    def get_recently_played(self, limit: int = 20) -> list[dict]:
        """Get recently played tracks."""
        if not self._ensure_client():
            return []
        try:
            results = self._sp.current_user_recently_played(limit=limit)
            return [
                {
                    "track_name": item["track"]["name"],
                    "artist_name": ", ".join(
                        a["name"] for a in item["track"].get("artists", [])
                    ),
                    "album_name": item["track"].get("album", {}).get("name", ""),
                    "spotify_track_id": item["track"].get("id", ""),
                    "duration_ms": item["track"].get("duration_ms", 0),
                    "played_at": item.get("played_at", ""),
                    "context_type": (item.get("context") or {}).get("type", ""),
                }
                for item in results.get("items", [])
            ]
        except Exception as exc:
            logger.warning("spotify_recently_played_error: %s", exc)
            return []

    # ── Listening history persistence ───────────────────────────────

    def log_recently_played(self) -> int:
        """Poll recently played and log new entries. Returns count of new entries logged."""
        tracks = self.get_recently_played(limit=20)
        if not tracks:
            return 0

        conn = _get_db()
        logged = 0
        try:
            for t in tracks:
                track_id = t.get("spotify_track_id", "")
                played_at = t.get("played_at", "")
                if not track_id or not played_at:
                    continue

                # Check if already logged (unique on track_id + played_at)
                exists = conn.execute(
                    "SELECT 1 FROM listening_history WHERE spotify_track_id = ? AND played_at = ?",
                    (track_id, played_at),
                ).fetchone()
                if exists:
                    continue

                row_id = f"lh_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """INSERT INTO listening_history
                       (id, spotify_track_id, track_name, artist_name, album_name,
                        duration_ms, played_at, context)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row_id,
                        track_id,
                        t.get("track_name", ""),
                        t.get("artist_name", ""),
                        t.get("album_name", ""),
                        t.get("duration_ms", 0),
                        played_at,
                        t.get("context_type", ""),
                    ),
                )
                logged += 1

            if logged:
                conn.commit()
                logger.info("spotify_logged_plays: %d new", logged)
        except Exception as exc:
            logger.warning("spotify_log_error: %s", exc)
        finally:
            conn.close()

        return logged

    def get_listening_history(self, limit: int = 20) -> list[dict]:
        """Get listening history from local DB."""
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM listening_history ORDER BY played_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ── Module-level singleton ──────────────────────────────────────────────

_instance: SpotifyAdapter | None = None


def get_spotify() -> SpotifyAdapter:
    """Get or create the singleton SpotifyAdapter."""
    global _instance
    if _instance is None:
        _instance = SpotifyAdapter()
    return _instance
