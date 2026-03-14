import unittest
from pathlib import Path


class SetupScriptsTests(unittest.TestCase):
    def test_setup_scripts_exist(self):
        scripts = [
            "scripts/setup/01_tailscale.sh",
            "scripts/setup/02_security.sh",
            "scripts/setup/02b_secrets.sh",
            "scripts/setup/03_resilience.sh",
            "scripts/setup/04_bitos_service.sh",
        ]
        for script in scripts:
            self.assertTrue(Path(script).exists(), f"missing {script}")

    def test_setup_scripts_use_strict_shell_flags(self):
        scripts = [
            Path("scripts/setup/01_tailscale.sh"),
            Path("scripts/setup/02_security.sh"),
            Path("scripts/setup/02b_secrets.sh"),
            Path("scripts/setup/03_resilience.sh"),
            Path("scripts/setup/04_bitos_service.sh"),
        ]
        for script in scripts:
            content = script.read_text()
            self.assertIn("set -euo pipefail", content)

    def test_setup_readme_exists_and_lists_scripts(self):
        readme = Path("scripts/setup/README.md")
        self.assertTrue(readme.exists())
        content = readme.read_text()
        for name in [
            "01_tailscale.sh",
            "02_security.sh",
            "02b_secrets.sh",
            "03_resilience.sh",
            "04_bitos_service.sh",
        ]:
            self.assertIn(name, content)

    def test_offline_ai_script_exists_and_has_expected_content(self):
        script = Path("scripts/setup/06_offline_ai.sh")
        self.assertTrue(script.exists())
        content = script.read_text()
        self.assertIn("set -euo pipefail", content)
        self.assertIn("piper", content.lower())
        self.assertIn("whisper.cpp", content)


if __name__ == "__main__":
    unittest.main()
