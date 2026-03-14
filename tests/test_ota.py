from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))

import main as server_main


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_device_version_returns_expected_fields():
    client = TestClient(server_main.app)
    response = client.get("/device/version")
    assert response.status_code == 200
    payload = response.json()
    for key in ["version", "commit", "branch", "behind", "update_available", "last_checked"]:
        assert key in payload
    assert isinstance(payload["behind"], int)


def test_device_update_requires_confirmed():
    client = TestClient(server_main.app)
    response = client.post("/device/update", json={"target": "both", "confirmed": False})
    assert response.status_code == 403


def test_ota_update_script_exists_is_executable_and_strict():
    script = ROOT / "scripts/ota_update.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111
    assert "set -euo pipefail" in script.read_text(encoding="utf-8")


def test_setup_everything_script_exists():
    script = ROOT / "scripts/setup_everything.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_makefile_has_setup_help_update_all_targets():
    makefile = _read("Makefile")
    for target in ["setup:", "help:", "update-all:"]:
        assert target in makefile
