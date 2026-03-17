"""Tests for music tool handlers in agent_tools.py."""
import json
import os
import sys
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
def mock_spotify():
    """Provide a mock SpotifyAdapter via the agent_tools singleton."""
    mock_sp = MagicMock()
    mock_sp.available = True
    mock_sp.installed = True

    with patch("agent_tools._get_spotify", return_value=mock_sp):
        yield mock_sp


@pytest.fixture
def mock_spotify_unavailable():
    """Provide an unavailable SpotifyAdapter."""
    mock_sp = MagicMock()
    mock_sp.available = False

    with patch("agent_tools._get_spotify", return_value=mock_sp):
        yield mock_sp


class TestPlayMusic:
    def test_play_resume(self, mock_spotify):
        from agent_tools import _play_music

        mock_spotify.play.return_value = True
        result = json.loads(_play_music({}))
        assert result["success"] is True
        assert result["action"] == "resumed"

    def test_play_search(self, mock_spotify):
        from agent_tools import _play_music

        mock_spotify.search.return_value = [
            {"name": "Hey Jude", "artist": "The Beatles", "uri": "spotify:track:abc"}
        ]
        mock_spotify.play.return_value = True

        result = json.loads(_play_music({"query": "hey jude"}))
        assert result["success"] is True
        assert result["track"] == "Hey Jude"

    def test_play_no_results(self, mock_spotify):
        from agent_tools import _play_music

        mock_spotify.search.return_value = []
        result = json.loads(_play_music({"query": "nonexistent"}))
        assert "error" in result

    def test_play_unavailable(self, mock_spotify_unavailable):
        from agent_tools import _play_music

        result = json.loads(_play_music({}))
        assert "error" in result


class TestPauseMusic:
    def test_pause(self, mock_spotify):
        from agent_tools import _pause_music

        mock_spotify.pause.return_value = True
        result = json.loads(_pause_music({}))
        assert result["success"] is True


class TestSkipTrack:
    def test_skip(self, mock_spotify):
        from agent_tools import _skip_track

        mock_spotify.skip.return_value = True
        result = json.loads(_skip_track({}))
        assert result["success"] is True


class TestPreviousTrack:
    def test_previous(self, mock_spotify):
        from agent_tools import _previous_track

        mock_spotify.previous.return_value = True
        result = json.loads(_previous_track({}))
        assert result["success"] is True


class TestGetNowPlaying:
    def test_now_playing(self, mock_spotify):
        from agent_tools import _get_now_playing

        mock_spotify.get_now_playing.return_value = {
            "track": "Hey Jude",
            "artist": "The Beatles",
            "album": "Hey Jude",
            "progress_ms": 60000,
            "duration_ms": 420000,
            "is_playing": True,
            "uri": "spotify:track:abc",
        }

        result = json.loads(_get_now_playing({}))
        assert result["playing"] is True
        assert result["track"] == "Hey Jude"
        assert result["progress"] == "1:00"
        assert result["duration"] == "7:00"

    def test_nothing_playing(self, mock_spotify):
        from agent_tools import _get_now_playing

        mock_spotify.get_now_playing.return_value = None
        result = json.loads(_get_now_playing({}))
        assert result["playing"] is False


class TestQueueTrack:
    def test_queue(self, mock_spotify):
        from agent_tools import _queue_track

        mock_spotify.search.return_value = [
            {"name": "Song", "artist": "Artist", "uri": "spotify:track:xyz"}
        ]
        mock_spotify.queue_track.return_value = True

        result = json.loads(_queue_track({"query": "song"}))
        assert result["success"] is True
        assert result["action"] == "queued"

    def test_queue_no_query(self, mock_spotify):
        from agent_tools import _queue_track

        result = json.loads(_queue_track({}))
        assert "error" in result


class TestSearchMusic:
    def test_search(self, mock_spotify):
        from agent_tools import _search_music

        mock_spotify.search.return_value = [
            {"name": "Song", "artist": "Artist", "uri": "uri"}
        ]

        result = json.loads(_search_music({"query": "test", "type": "track"}))
        assert result["count"] == 1


class TestSetMusicVolume:
    def test_set_volume(self, mock_spotify):
        from agent_tools import _set_music_volume

        mock_spotify.set_volume.return_value = True
        result = json.loads(_set_music_volume({"level": 75}))
        assert result["success"] is True

    def test_invalid_volume(self, mock_spotify):
        from agent_tools import _set_music_volume

        result = json.loads(_set_music_volume({"level": 150}))
        assert "error" in result

    def test_non_int_volume(self, mock_spotify):
        from agent_tools import _set_music_volume

        result = json.loads(_set_music_volume({"level": "loud"}))
        assert "error" in result


class TestMusicRecommend:
    def test_recommend_current(self, mock_spotify):
        from agent_tools import _music_recommend

        mock_spotify.get_now_playing.return_value = {
            "uri": "spotify:track:123", "is_playing": True
        }
        mock_spotify.get_recommendations.return_value = [
            {"name": "Rec1", "artist": "Art1", "album": "Alb1", "uri": "uri1", "duration_ms": 200000}
        ]

        result = json.loads(_music_recommend({"based_on": "current"}))
        assert result["count"] == 1
        assert result["based_on"] == "current"

    def test_recommend_mood(self, mock_spotify):
        from agent_tools import _music_recommend

        mock_spotify.get_now_playing.return_value = {
            "uri": "spotify:track:123", "is_playing": True
        }
        mock_spotify.get_recommendations.return_value = [
            {"name": "Chill Song", "artist": "Art", "album": "Alb", "uri": "uri", "duration_ms": 180000}
        ]

        result = json.loads(_music_recommend({"based_on": "mood", "mood": "chill"}))
        assert result["count"] >= 1

    def test_recommend_genre(self, mock_spotify):
        from agent_tools import _music_recommend

        mock_spotify.get_recommendations.return_value = []
        result = json.loads(_music_recommend({"based_on": "genre", "genre": "jazz"}))
        assert "recommendations" in result

    def test_recommend_history(self, mock_spotify):
        from agent_tools import _music_recommend

        mock_spotify.get_top_items.return_value = [
            {"name": "T1", "artist": "A1", "uri": "spotify:track:t1"},
        ]
        mock_spotify.get_recommendations.return_value = [
            {"name": "R1", "artist": "A1", "album": "Al1", "uri": "u1", "duration_ms": 200000}
        ]

        result = json.loads(_music_recommend({"based_on": "history"}))
        assert result["count"] >= 1

    def test_recommend_nothing_playing(self, mock_spotify):
        from agent_tools import _music_recommend

        mock_spotify.get_now_playing.return_value = None
        result = json.loads(_music_recommend({"based_on": "current"}))
        assert "error" in result

    def test_recommend_unavailable(self, mock_spotify_unavailable):
        from agent_tools import _music_recommend

        result = json.loads(_music_recommend({"based_on": "current"}))
        assert "error" in result


class TestMusicTasteProfile:
    def test_taste_profile_from_cache(self, mock_spotify):
        from agent_tools import _music_taste_profile

        with patch("integrations.music_logger.get_music_logger") as mock_ml_fn:
            mock_ml = MagicMock()
            mock_ml.get_cached_profile.return_value = {
                "top_artists_30d": [{"artist": "Queen", "plays": 50}],
                "total_tracks_30d": 200,
            }
            mock_ml_fn.return_value = mock_ml

            result = json.loads(_music_taste_profile({}))
            assert "top_artists_30d" in result

    def test_taste_profile_fallback_to_spotify(self, mock_spotify):
        from agent_tools import _music_taste_profile

        with patch("integrations.music_logger.get_music_logger") as mock_ml_fn:
            mock_ml = MagicMock()
            mock_ml.get_cached_profile.return_value = {}
            mock_ml.build_taste_profile.return_value = {}
            mock_ml_fn.return_value = mock_ml

            mock_spotify.get_top_items.return_value = [{"name": "Track A"}]

            result = json.loads(_music_taste_profile({}))
            assert result["source"] == "spotify_api"


class TestMoodMapping:
    def test_all_moods_have_params(self):
        from agent_tools import MOOD_TO_SPOTIFY_PARAMS

        expected_moods = ["chill", "energetic", "melancholic", "focused", "happy",
                          "angry", "romantic", "sleepy", "workout", "study", "party"]
        for mood in expected_moods:
            assert mood in MOOD_TO_SPOTIFY_PARAMS
            params = MOOD_TO_SPOTIFY_PARAMS[mood]
            assert "target_energy" in params
            assert "target_valence" in params

    def test_energy_range(self):
        from agent_tools import MOOD_TO_SPOTIFY_PARAMS

        for mood, params in MOOD_TO_SPOTIFY_PARAMS.items():
            assert 0.0 <= params["target_energy"] <= 1.0, f"{mood} energy out of range"
            assert 0.0 <= params["target_valence"] <= 1.0, f"{mood} valence out of range"
