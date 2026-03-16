"""Service health checks — internet, backend, STT API, mic.

Run check_all() at startup or on-demand. Results are a dict of
service name → {"ok": bool, "detail": str, "latency_ms": int}.
"""

from __future__ import annotations

import logging
import os
import time
import threading

logger = logging.getLogger(__name__)


def _timed(fn):
    """Run fn(), return (result, latency_ms)."""
    t0 = time.monotonic()
    try:
        result = fn()
        ms = int((time.monotonic() - t0) * 1000)
        return result, ms
    except Exception as exc:
        ms = int((time.monotonic() - t0) * 1000)
        return exc, ms


def check_internet(timeout: float = 3.0) -> dict:
    """Ping a reliable public endpoint."""
    import urllib.request

    def _do():
        urllib.request.urlopen("https://httpbin.org/status/200", timeout=timeout)
        return True

    result, ms = _timed(_do)
    if isinstance(result, Exception):
        return {"ok": False, "detail": str(result)[:40], "latency_ms": ms}
    return {"ok": True, "detail": f"{ms}ms", "latency_ms": ms}


def check_backend(timeout: float = 3.0) -> dict:
    """Check BITOS backend /health endpoint."""
    import httpx

    base = os.environ.get("BITOS_SERVER_URL",
                          os.environ.get("SERVER_URL", "http://localhost:8000"))

    def _do():
        r = httpx.get(f"{base.rstrip('/')}/health", timeout=timeout)
        r.raise_for_status()
        return True

    result, ms = _timed(_do)
    if isinstance(result, Exception):
        return {"ok": False, "detail": str(result)[:40], "latency_ms": ms}
    return {"ok": True, "detail": f"{ms}ms @ {base}", "latency_ms": ms}


def check_groq_api(timeout: float = 5.0) -> dict:
    """Verify Groq API key is set and endpoint is reachable."""
    import httpx

    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return {"ok": False, "detail": "GROQ_API_KEY not set", "latency_ms": 0}

    def _do():
        # List models endpoint — lightweight auth check
        r = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        r.raise_for_status()
        return True

    result, ms = _timed(_do)
    if isinstance(result, Exception):
        detail = str(result)[:40]
        # Check for auth errors specifically
        if hasattr(result, "response") and getattr(result.response, "status_code", 0) == 401:
            detail = "invalid API key"
        return {"ok": False, "detail": detail, "latency_ms": ms}
    return {"ok": True, "detail": f"{ms}ms", "latency_ms": ms}


def check_openai_api(timeout: float = 5.0) -> dict:
    """Verify OpenAI API key is set and endpoint is reachable."""
    import httpx

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return {"ok": False, "detail": "OPENAI_API_KEY not set", "latency_ms": 0}

    def _do():
        r = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        r.raise_for_status()
        return True

    result, ms = _timed(_do)
    if isinstance(result, Exception):
        detail = str(result)[:40]
        if hasattr(result, "response") and getattr(result.response, "status_code", 0) == 401:
            detail = "invalid API key"
        return {"ok": False, "detail": detail, "latency_ms": ms}
    return {"ok": True, "detail": f"{ms}ms", "latency_ms": ms}


def check_mic() -> dict:
    """Check if ALSA recording device is accessible."""
    import subprocess

    mode = os.environ.get("BITOS_AUDIO", "mock").strip()
    if not mode or mode == "mock":
        return {"ok": True, "detail": "mock mode", "latency_ms": 0}

    device = mode if mode.startswith("hw:") else "hw:0"

    def _do():
        # Quick test: record 0.1s stereo (WM8960 requires stereo)
        r = subprocess.run(
            ["arecord", "-D", device, "-f", "S16_LE", "-r", "16000",
             "-c", "2", "-d", "1", "/dev/null"],
            capture_output=True, timeout=5, check=False,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[:60])
        return True

    result, ms = _timed(_do)
    if isinstance(result, Exception):
        return {"ok": False, "detail": str(result)[:40], "latency_ms": ms}
    return {"ok": True, "detail": f"device={device}", "latency_ms": ms}


class ServiceHealth:
    """Async health checker — runs all checks in background, provides status."""

    SERVICES = ["internet", "backend", "groq", "mic"]

    def __init__(self):
        self.results: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._running = False

    def check_all_async(self) -> None:
        """Run all health checks in parallel background threads."""
        if self._running:
            return
        self._running = True
        with self._lock:
            self.results = {}

        checks = {
            "internet": check_internet,
            "backend": check_backend,
            "groq": check_groq_api,
            "mic": check_mic,
        }

        def _run(name, fn):
            try:
                result = fn()
            except Exception as exc:
                result = {"ok": False, "detail": str(exc)[:40], "latency_ms": 0}
            with self._lock:
                self.results[name] = result
                logger.info("health_check name=%s ok=%s detail=%s",
                            name, result["ok"], result.get("detail", ""))
            if len(self.results) == len(checks):
                self._running = False

        for name, fn in checks.items():
            threading.Thread(target=_run, args=(name, fn), daemon=True).start()

    def is_complete(self) -> bool:
        with self._lock:
            return len(self.results) >= len(self.SERVICES)

    def all_ok(self) -> bool:
        with self._lock:
            if len(self.results) < len(self.SERVICES):
                return False
            return all(r.get("ok", False) for r in self.results.values())

    def summary_line(self) -> str:
        """One-line status for status bar: 'ALL OK' or 'groq: fail'."""
        with self._lock:
            if not self.results:
                return "checking..."
            failed = [n for n, r in self.results.items() if not r.get("ok", False)]
            if not failed:
                return "all services ok"
            return ", ".join(f"{n}: FAIL" for n in failed)

    def get(self, name: str) -> dict | None:
        with self._lock:
            return self.results.get(name)
