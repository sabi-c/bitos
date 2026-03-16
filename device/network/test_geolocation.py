"""Tests for IP geolocation timezone detection."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from network.geolocation import (
    SETTING_LOCATION,
    SETTING_TIMEZONE,
    detect_and_set_timezone,
    fetch_geolocation,
    set_system_timezone,
)


SAMPLE_API_RESPONSE = {
    "status": "success",
    "city": "Los Angeles",
    "regionName": "California",
    "country": "United States",
    "timezone": "America/Los_Angeles",
    "lat": 34.0522,
    "lon": -118.2437,
}

EXPECTED_LOCATION = {
    "city": "Los Angeles",
    "region": "California",
    "country": "United States",
    "timezone": "America/Los_Angeles",
    "lat": 34.0522,
    "lon": -118.2437,
}


class TestFetchGeolocation:
    """Tests for the fetch_geolocation function."""

    @patch("network.geolocation.httpx.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_API_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_geolocation()

        assert result == EXPECTED_LOCATION
        mock_get.assert_called_once()

    @patch("network.geolocation.httpx.get")
    def test_api_failure_status(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "fail", "message": "reserved range"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_geolocation()
        assert result is None

    @patch("network.geolocation.httpx.get")
    def test_network_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        result = fetch_geolocation()
        assert result is None

    @patch("network.geolocation.httpx.get")
    def test_timeout(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.TimeoutException("timed out")

        result = fetch_geolocation()
        assert result is None


class TestSetSystemTimezone:
    """Tests for the set_system_timezone function."""

    @patch("network.geolocation.subprocess.run")
    def test_timedatectl_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        assert set_system_timezone("America/Los_Angeles") is True
        mock_run.assert_called_once_with(
            ["sudo", "timedatectl", "set-timezone", "America/Los_Angeles"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    @patch("network.geolocation.subprocess.run")
    def test_timedatectl_fails(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="Failed")

        # Will try fallback, which will also fail in test env
        assert set_system_timezone("America/Los_Angeles") is False

    def test_empty_timezone(self):
        assert set_system_timezone("") is False
        assert set_system_timezone(None) is False


class TestDetectAndSetTimezone:
    """Tests for the full detect_and_set_timezone flow."""

    @patch("network.geolocation.set_system_timezone")
    @patch("network.geolocation.fetch_geolocation")
    def test_fresh_detection(self, mock_fetch, mock_set_tz):
        mock_fetch.return_value = EXPECTED_LOCATION
        mock_set_tz.return_value = True
        repo = MagicMock()
        repo.get_setting.return_value = None

        result = detect_and_set_timezone(repository=repo)

        assert result == EXPECTED_LOCATION
        mock_set_tz.assert_called_once_with("America/Los_Angeles")
        repo.set_setting.assert_any_call(SETTING_LOCATION, json.dumps(EXPECTED_LOCATION))
        repo.set_setting.assert_any_call(SETTING_TIMEZONE, "America/Los_Angeles")

    @patch("network.geolocation.set_system_timezone")
    @patch("network.geolocation.fetch_geolocation")
    def test_cached_location(self, mock_fetch, mock_set_tz):
        repo = MagicMock()
        repo.get_setting.return_value = json.dumps(EXPECTED_LOCATION)

        result = detect_and_set_timezone(repository=repo)

        assert result == EXPECTED_LOCATION
        mock_fetch.assert_not_called()
        mock_set_tz.assert_not_called()

    @patch("network.geolocation.fetch_geolocation")
    def test_no_repository(self, mock_fetch):
        mock_fetch.return_value = EXPECTED_LOCATION

        with patch("network.geolocation.set_system_timezone") as mock_tz:
            mock_tz.return_value = True
            result = detect_and_set_timezone(repository=None)

        assert result == EXPECTED_LOCATION

    @patch("network.geolocation.fetch_geolocation")
    def test_api_failure_no_cache(self, mock_fetch):
        mock_fetch.return_value = None
        repo = MagicMock()
        repo.get_setting.return_value = None

        result = detect_and_set_timezone(repository=repo)
        assert result is None
