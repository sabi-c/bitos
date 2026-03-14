from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_install_script_uses_two_service_names_only():
    install = _read("scripts/install.sh")
    assert "bitos.service" not in install
    assert "bitos-server" in install
    assert "bitos-device" in install


def test_service_setup_script_creates_both_units():
    service_setup = _read("scripts/setup/04_bitos_service.sh")
    assert "/etc/systemd/system/bitos-server.service" in service_setup
    assert "/etc/systemd/system/bitos-device.service" in service_setup
    assert "systemctl enable bitos-server bitos-device" in service_setup


def test_day_one_references_two_services():
    day_one = _read("scripts/day_one.sh")
    assert "bitos-server" in day_one
    assert "bitos-device" in day_one


def test_day_one_health_wait_has_timeout():
    day_one = _read("scripts/day_one.sh")
    assert "MAX_WAIT=30" in day_one
    assert "WAITED=0" in day_one
    assert "if [ $WAITED -ge $MAX_WAIT ]; then" in day_one
    assert "ERROR: Server didn't start in ${MAX_WAIT}s" in day_one
