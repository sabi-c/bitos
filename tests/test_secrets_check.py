import os
import subprocess
import pytest
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = ROOT / "scripts/setup/check_secrets.sh"
BOOTSTRAP_SCRIPT = ROOT / "scripts/setup/02b_secrets.sh"


class SecretsScriptsTests(unittest.TestCase):
    def _run(self, cmd: list[str], env: dict[str, str]):
        return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)

    def test_check_secrets_exits_zero_when_all_keys_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp) / "secrets"
            secrets.write_text(
                "\n".join(
                    [
                        "ANTHROPIC_API_KEY=sk-ant-test",
                        "BITOS_DEVICE_TOKEN=abc",
                        "BITOS_PIN_HASH=hash",
                        "BITOS_BLE_SECRET=ble",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["BITOS_SECRETS_FILE"] = str(secrets)
            res = self._run(["bash", str(CHECK_SCRIPT)], env)

            self.assertEqual(res.returncode, 0, msg=res.stdout + res.stderr)
            self.assertIn("All secrets configured", res.stdout)

    def test_check_secrets_exits_one_when_key_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp) / "secrets"
            secrets.write_text(
                "\n".join(
                    [
                        "ANTHROPIC_API_KEY=sk-ant-test",
                        "BITOS_DEVICE_TOKEN=abc",
                        "BITOS_PIN_HASH=hash",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["BITOS_SECRETS_FILE"] = str(secrets)
            res = self._run(["bash", str(CHECK_SCRIPT)], env)

            self.assertEqual(res.returncode, 1)
            self.assertIn("BITOS_BLE_SECRET MISSING", res.stdout)

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Secrets bootstrap test requires real Pi filesystem",
    )
    def test_secrets_bootstrap_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp) / "secrets"
            env = os.environ.copy()
            env["BITOS_SECRETS_FILE"] = str(secrets)
            env["BITOS_SUDO_BIN"] = ""

            first = self._run(["bash", str(BOOTSTRAP_SCRIPT)], env)
            self.assertEqual(first.returncode, 0, msg=first.stdout + first.stderr)
            first_content = secrets.read_text(encoding="utf-8")

            second = self._run(["bash", str(BOOTSTRAP_SCRIPT)], env)
            self.assertEqual(second.returncode, 0, msg=second.stdout + second.stderr)
            second_content = secrets.read_text(encoding="utf-8")

            self.assertEqual(first_content, second_content)
            self.assertEqual(second_content.count("BITOS_DEVICE_TOKEN="), 1)
            self.assertEqual(second_content.count("BITOS_PIN_HASH="), 1)
            self.assertEqual(second_content.count("BITOS_BLE_SECRET="), 1)


if __name__ == "__main__":
    unittest.main()
