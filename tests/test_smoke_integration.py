import importlib.util
import runpy
import unittest
from pathlib import Path


class SmokeIntegrationTests(unittest.TestCase):
    def test_smoke_test_main_runs_if_script_present(self):
        path = Path("scripts/smoke_test.py")
        if not path.exists():
            self.skipTest("scripts/smoke_test.py not present in this repository")
        namespace = runpy.run_path(str(path), run_name="__main__")
        main = namespace.get("main")
        if callable(main):
            main()

    def test_verify_hardware_imports_if_present(self):
        path = Path("scripts/verify_hardware.py")
        if not path.exists():
            self.skipTest("scripts/verify_hardware.py not present in this repository")

        spec = importlib.util.spec_from_file_location("verify_hardware", str(path))
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        self.assertIsNotNone(module)

    def test_setup_scripts_exist_and_use_strict_flags(self):
        scripts = [
            Path("scripts/setup/01_tailscale.sh"),
            Path("scripts/setup/02_security.sh"),
            Path("scripts/setup/02b_secrets.sh"),
            Path("scripts/setup/03_resilience.sh"),
            Path("scripts/setup/04_bitos_service.sh"),
        ]
        for script in scripts:
            self.assertTrue(script.exists(), f"missing {script}")
            content = script.read_text()
            self.assertIn("set -euo pipefail", content)


if __name__ == "__main__":
    unittest.main()
