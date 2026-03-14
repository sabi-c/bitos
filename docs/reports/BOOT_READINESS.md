## CRITICAL (will prevent boot)
- **Fixed:** `python -c "import device.main"` previously failed with `ModuleNotFoundError: No module named 'display'` because `device/main.py` uses legacy top-level intra-package imports (`from display...`, `from screens...`) that do not resolve when importing as `device.main` from repo root. Added `device/__init__.py` bootstrap to put `device/` on `sys.path`, and the required import checks now pass.
- **Fixed:** `scripts/install.sh` was missing. Added a minimal first-boot installer script that creates `.venv`, installs requirements, runs setup scripts, and prints next-step secret instructions.

## HIGH (will prevent core feature working)
- `run-pi` / `run-pi-server` require both `.venv` and `/etc/bitos/secrets` to exist; without running installer + secret provisioning first, these targets fail immediately. This is expected but operationally strict for first boot.
- `scripts/verify_hardware.py` executes checks at import time (top-level) rather than only under `__main__`; this is safe for direct execution but can surprise tooling/import contexts.

## MEDIUM (degraded experience)
- `docs/planning/FIRST_BOOT.md` does not exist in this repo, despite being referenced by audit instructions.
- `GPIOButtonHandler` uses shared mutable `_press_times` across GPIO callbacks and delayed threads without locking; under rapid presses, there is race potential causing occasional misclassification of short/double/triple events.
- `AudioPipeline` mock path writes temp files under `/tmp` but does not clean them up after transcription.

## LOW (polish)
- Makefile still has both old (`dev-*`) and new (`run-*`) target families, which can create operator ambiguity.

## VERDICT
**READY** — critical boot blockers were fixed (import chain + missing installer), server/device import/startup checks are passing, and remaining issues are operational/documentation reliability gaps rather than immediate boot blockers.
