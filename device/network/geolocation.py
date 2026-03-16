"""IP-based geolocation for automatic timezone detection.

Uses the free ip-api.com service (no API key required, 45 req/min limit).
Results are cached in DeviceRepository settings so the API is only called
once per boot (or when explicitly refreshed).
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GEOLOCATION_API_URL = "http://ip-api.com/json/"
REQUEST_TIMEOUT = 5.0

# Keys used in DeviceRepository settings
SETTING_LOCATION = "geolocation"
SETTING_TIMEZONE = "timezone"


def fetch_geolocation(timeout: float = REQUEST_TIMEOUT) -> Optional[dict]:
    """Call ip-api.com and return parsed location info.

    Returns a dict with keys: city, region, country, timezone, lat, lon.
    Returns None on any failure.
    """
    try:
        resp = httpx.get(
            GEOLOCATION_API_URL,
            timeout=timeout,
            params={"fields": "status,city,regionName,country,timezone,lat,lon"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            logger.warning("geolocation_api_failed status=%s", data.get("status"))
            return None
        return {
            "city": data.get("city", ""),
            "region": data.get("regionName", ""),
            "country": data.get("country", ""),
            "timezone": data.get("timezone", ""),
            "lat": data.get("lat", 0.0),
            "lon": data.get("lon", 0.0),
        }
    except Exception as exc:
        logger.warning("geolocation_fetch_failed error=%s", exc)
        return None


def set_system_timezone(timezone: str) -> bool:
    """Attempt to set the system timezone via timedatectl.

    Falls back to writing /etc/timezone on systems without timedatectl.
    Returns True if the timezone was set successfully.
    """
    if not timezone:
        return False
    try:
        result = subprocess.run(
            ["sudo", "timedatectl", "set-timezone", timezone],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("system_timezone_set tz=%s", timezone)
            return True
        logger.warning("timedatectl_failed stderr=%s", result.stderr.strip())
    except FileNotFoundError:
        logger.debug("timedatectl not found, trying /etc/timezone")
    except Exception as exc:
        logger.warning("timedatectl_error error=%s", exc)

    # Fallback: write /etc/timezone directly
    try:
        with open("/etc/timezone", "w", encoding="utf-8") as f:
            f.write(timezone + "\n")
        subprocess.run(["sudo", "dpkg-reconfigure", "-f", "noninteractive", "tzdata"],
                       capture_output=True, timeout=10)
        logger.info("system_timezone_set_fallback tz=%s", timezone)
        return True
    except Exception as exc:
        logger.debug("timezone_fallback_failed error=%s", exc)
        return False


def detect_and_set_timezone(repository=None) -> Optional[dict]:
    """Fetch geolocation, set system timezone, and cache in repository.

    If the repository already has a cached location, returns it without
    making an API call (unless the cache has no timezone).

    Args:
        repository: DeviceRepository instance (optional). When provided,
            results are cached in settings.

    Returns:
        Location dict or None on failure.
    """
    # Check cache first
    if repository is not None:
        cached = repository.get_setting(SETTING_LOCATION, default=None)
        if cached:
            try:
                location = json.loads(cached) if isinstance(cached, str) else cached
                if location.get("timezone"):
                    logger.info(
                        "geolocation_cached tz=%s city=%s",
                        location.get("timezone"),
                        location.get("city"),
                    )
                    return location
            except (json.JSONDecodeError, TypeError):
                pass

    location = fetch_geolocation()
    if location is None:
        return None

    tz = location.get("timezone", "")
    if tz:
        set_system_timezone(tz)

    # Persist to repository
    if repository is not None:
        try:
            repository.set_setting(SETTING_LOCATION, json.dumps(location))
            repository.set_setting(SETTING_TIMEZONE, tz)
        except Exception as exc:
            logger.warning("geolocation_cache_save_failed error=%s", exc)

    logger.info(
        "geolocation_detected tz=%s city=%s region=%s",
        tz,
        location.get("city"),
        location.get("region"),
    )
    return location
