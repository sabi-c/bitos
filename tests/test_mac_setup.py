from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mac_setup_script_exists_and_is_executable():
    script = ROOT / "scripts/mac_setup.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_mac_setup_uses_strict_shell_flags():
    mac_setup = _read("scripts/mac_setup.sh")
    assert "set -euo pipefail" in mac_setup


def test_makefile_has_mac_targets():
    makefile = _read("Makefile")
    for target in [
        "mac-setup:",
        "mac-start:",
        "mac-stop:",
        "mac-restart:",
        "mac-logs:",
        "mac-status:",
    ]:
        assert target in makefile


def test_mac_setup_references_all_eight_steps():
    mac_setup = _read("scripts/mac_setup.sh")
    for step in [
        "[1/8]",
        "[2/8]",
        "[3/8]",
        "[4/8]",
        "[5/8]",
        "[6/8]",
        "[7/8]",
        "[8/8]",
    ]:
        assert step in mac_setup


def test_plist_template_has_required_launchagent_keys():
    mac_setup = _read("scripts/mac_setup.sh")
    required = [
        "<key>Label</key>",
        "<key>ProgramArguments</key>",
        "<key>WorkingDirectory</key>",
        "<key>EnvironmentVariables</key>",
        "<key>KeepAlive</key>",
        "<key>RunAtLoad</key>",
        "<key>StandardOutPath</key>",
        "<key>StandardErrorPath</key>",
        "com.bitos.server",
        "server.main:app",
    ]
    for item in required:
        assert item in mac_setup
