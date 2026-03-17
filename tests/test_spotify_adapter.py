"""Tests for SpotifyAdapter — API calls with mocked spotipy."""
import json
import os
import sys
import types
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
def mock_spotipy():
    """Create a SpotifyAdapter with a mocked spotipy client."""
    # We need to mock spotipy before importing the adapter
    mock_sp = MagicMock()
    mock_auth = MagicMock()
    mock_auth.get_cached_token.return_value = {"access_token": "test-token"}

    with patch.dict(os.environ, {
        "SPOTIFY_CLIENT_ID": "test-id",
        "SPOTIFY_CLIENT_SECRET": "test-secret",
    }):
        from integrations.spotify_adapter import SpotifyAdapter

        adapter = SpotifyAdapter.__new__(SpotifyAdapter)
        adapter._sp = mock_sp
        adapter._auth_manager = mock_auth
        adapter._available = True

    return adapter, mock_sp


class TestSpotifyAdapterPlayback:
    def test_get_now_playing(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.current_playback.return_value = {
            "item": {
                "name": "Bohemian Rhapsody",
                "artists": [{"name": "Queen"}],
                "album": {"name": "A Night at the Opera", "images": [{"url": "http://img.jpg"}]},
                "uri": "spotify:track:123",
                "id": "123",
                "duration_ms": 354000,
            },
            "progress_ms": 120000,
            "is_playing": True,
        }

        result = adapter.get_now_playing()
        assert result is not None
        assert result["track"] == "Bohemian Rhapsody"
        assert result["artist"] == "Queen"
        assert result["is_playing"] is True
        assert result["progress_ms"] == 120000

    def test_get_now_playing_nothing(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.current_playback.return_value = None
        assert adapter.get_now_playing() is None

    def test_play_resume(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.play() is True
        mock_sp.start_playback.assert_called_once_with()

    def test_play_uri(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.play(uri="spotify:track:abc") is True
        mock_sp.start_playback.assert_called_once_with(uris=["spotify:track:abc"])

    def test_play_context(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.play(context_uri="spotify:album:xyz") is True
        mock_sp.start_playback.assert_called_once_with(context_uri="spotify:album:xyz")

    def test_pause(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.pause() is True
        mock_sp.pause_playback.assert_called_once()

    def test_skip(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.skip() is True
        mock_sp.next_track.assert_called_once()

    def test_previous(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.previous() is True
        mock_sp.previous_track.assert_called_once()

    def test_set_volume(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.set_volume(75) is True
        mock_sp.volume.assert_called_once_with(75)

    def test_set_volume_clamp(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        adapter.set_volume(150)
        mock_sp.volume.assert_called_with(100)
        adapter.set_volume(-10)
        mock_sp.volume.assert_called_with(0)

    def test_shuffle(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.shuffle(True) is True
        mock_sp.shuffle.assert_called_once_with(True)

    def test_repeat(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.repeat("track") is True
        mock_sp.repeat.assert_called_once_with("track")

    def test_seek(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.seek(60000) is True
        mock_sp.seek_track.assert_called_once_with(60000)


class TestSpotifyAdapterSearch:
    def test_search_tracks(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.search.return_value = {
            "tracks": {
                "items": [
                    {
                        "name": "Bohemian Rhapsody",
                        "artists": [{"name": "Queen"}],
                        "album": {"name": "A Night at the Opera"},
                        "uri": "spotify:track:123",
                        "duration_ms": 354000,
                    }
                ]
            }
        }

        results = adapter.search("bohemian rhapsody")
        assert len(results) == 1
        assert results[0]["name"] == "Bohemian Rhapsody"
        assert results[0]["artist"] == "Queen"
        assert results[0]["uri"] == "spotify:track:123"

    def test_search_artists(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.search.return_value = {
            "artists": {
                "items": [
                    {
                        "name": "Queen",
                        "uri": "spotify:artist:abc",
                        "genres": ["rock", "classic rock"],
                        "followers": {"total": 50000000},
                    }
                ]
            }
        }

        results = adapter.search("queen", search_type="artist")
        assert len(results) == 1
        assert results[0]["name"] == "Queen"

    def test_search_empty(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.search.return_value = {"tracks": {"items": []}}
        assert adapter.search("nonexistent") == []


class TestSpotifyAdapterRecommendations:
    def test_get_recommendations(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.recommendations.return_value = {
            "tracks": [
                {
                    "name": "Don't Stop Me Now",
                    "artists": [{"name": "Queen"}],
                    "album": {"name": "Jazz"},
                    "uri": "spotify:track:456",
                    "duration_ms": 210000,
                }
            ]
        }

        results = adapter.get_recommendations(seed_tracks=["123"])
        assert len(results) == 1
        assert results[0]["name"] == "Don't Stop Me Now"

    def test_get_recommendations_with_audio_features(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.recommendations.return_value = {"tracks": []}

        adapter.get_recommendations(
            seed_genres=["chill"],
            target_energy=0.3,
            target_valence=0.5,
        )
        mock_sp.recommendations.assert_called_once()
        call_kwargs = mock_sp.recommendations.call_args
        assert call_kwargs.kwargs.get("target_energy") == 0.3

    def test_get_top_items_tracks(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.current_user_top_tracks.return_value = {
            "items": [
                {
                    "name": "Track A",
                    "artists": [{"name": "Artist A"}],
                    "uri": "spotify:track:a",
                }
            ]
        }

        results = adapter.get_top_items(item_type="tracks", time_range="short_term")
        assert len(results) == 1
        assert results[0]["name"] == "Track A"

    def test_get_top_items_artists(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.current_user_top_artists.return_value = {
            "items": [
                {
                    "name": "Artist A",
                    "uri": "spotify:artist:a",
                    "genres": ["rock"],
                }
            ]
        }

        results = adapter.get_top_items(item_type="artists")
        assert len(results) == 1
        assert results[0]["name"] == "Artist A"


class TestSpotifyAdapterQueue:
    def test_queue_track(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        assert adapter.queue_track("spotify:track:123") is True
        mock_sp.add_to_queue.assert_called_once_with("spotify:track:123")

    def test_get_queue(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.queue.return_value = {
            "queue": [
                {"name": "Track A", "artists": [{"name": "Artist A"}], "uri": "spotify:track:a"},
                {"name": "Track B", "artists": [{"name": "Artist B"}], "uri": "spotify:track:b"},
            ]
        }
        results = adapter.get_queue()
        assert len(results) == 2
        assert results[0]["name"] == "Track A"


class TestSpotifyAdapterUnavailable:
    def test_methods_return_defaults_when_unavailable(self):
        from integrations.spotify_adapter import SpotifyAdapter

        adapter = SpotifyAdapter.__new__(SpotifyAdapter)
        adapter._sp = None
        adapter._auth_manager = None
        adapter._available = False

        assert adapter.get_now_playing() is None
        assert adapter.play() is False
        assert adapter.pause() is False
        assert adapter.skip() is False
        assert adapter.previous() is False
        assert adapter.set_volume(50) is False
        assert adapter.shuffle(True) is False
        assert adapter.repeat("off") is False
        assert adapter.seek(0) is False
        assert adapter.search("test") == []
        assert adapter.get_playlists() == []
        assert adapter.queue_track("uri") is False
        assert adapter.get_recently_played() == []
        assert adapter.get_recommendations() == []
        assert adapter.get_top_items() == []
        assert adapter.get_queue() == []
        assert adapter.get_user_profile() is None

    def test_error_handling(self, mock_spotipy):
        adapter, mock_sp = mock_spotipy
        mock_sp.current_playback.side_effect = Exception("API Error")
        assert adapter.get_now_playing() is None

        mock_sp.start_playback.side_effect = Exception("API Error")
        assert adapter.play() is False
