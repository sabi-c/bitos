import importlib.util
import json
import sys
import time
from pathlib import Path

DEVICE_ROOT = Path(__file__).resolve().parents[1] / "device"
sys.path.insert(0, str(DEVICE_ROOT))

spec = importlib.util.spec_from_file_location("device_entry", DEVICE_ROOT / "main.py")
device_main = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(device_main)


def test_restore_state_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(device_main.os.path, "exists", lambda _: False)
    assert device_main._restore_state() is None


def test_restore_state_returns_none_when_stale(tmp_path, monkeypatch):
    state_path = tmp_path / "bitos_state.json"
    state_path.write_text(json.dumps({"timestamp": time.time() - 400}))

    monkeypatch.setattr(device_main.os.path, "exists", lambda _: True)
    monkeypatch.setattr(device_main, "open", lambda *_args, **_kwargs: state_path.open("r", encoding="utf-8"), raising=False)

    assert device_main._restore_state() is None


def test_restore_state_returns_fresh_state_and_deletes_file(tmp_path, monkeypatch):
    state_path = tmp_path / "bitos_state.json"
    payload = {"timestamp": time.time(), "session_id": 42}
    state_path.write_text(json.dumps(payload))

    monkeypatch.setattr(device_main.os.path, "exists", lambda _: True)
    monkeypatch.setattr(device_main, "open", lambda *_args, **_kwargs: state_path.open("r", encoding="utf-8"), raising=False)

    removed = {"called": False}

    def _remove(_):
        removed["called"] = True
        state_path.unlink()

    monkeypatch.setattr(device_main.os, "remove", _remove)

    assert device_main._restore_state() == payload
    assert removed["called"]
    assert not state_path.exists()


def test_restore_state_deletes_file_after_read(tmp_path, monkeypatch):
    state_path = tmp_path / "bitos_state.json"
    state_path.write_text(json.dumps({"timestamp": time.time(), "foo": "bar"}))

    monkeypatch.setattr(device_main.os.path, "exists", lambda _: True)
    monkeypatch.setattr(device_main, "open", lambda *_args, **_kwargs: state_path.open("r", encoding="utf-8"), raising=False)
    monkeypatch.setattr(device_main.os, "remove", lambda _: state_path.unlink())

    _ = device_main._restore_state()

    assert not state_path.exists()


def test_crash_handler_writes_crash_file(tmp_path):
    crash_path = tmp_path / "bitos_crash.json"
    device_main._handle_main_loop_crash(RuntimeError("boom"), crash_path=str(crash_path))

    payload = json.loads(crash_path.read_text())
    assert payload["error"] == "boom"
    assert isinstance(payload["timestamp"], float)
