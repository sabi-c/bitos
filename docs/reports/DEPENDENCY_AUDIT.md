# BITOS Dependency Audit

Scope: Python runtime dependencies used by `device/` and `server/` plus toolchain assumptions from docs.

## Findings

| Dependency/Area | Severity | Risk | Recommendation |
|---|---|---|---|
| `httpx` outbound requests | HIGH | Blocking network calls without strict timeout policy can stall user-facing flows if future callsites omit timeouts. | Enforce shared timeout constants and wrapper helpers for all outbound HTTP usage. |
| `subprocess` usage for `nmcli` (`device/bluetooth/wifi_manager.py`) | HIGH | Shell-command execution without mandatory timeout/retry policy risks indefinite process hangs on hardware. | Standardize subprocess timeout, retry, and error classification helpers for networking commands. |
| `pygame` font/resource loading | MED | Font construction in render loops can degrade frame performance and increase allocation churn. | Cache font objects once per screen/overlay lifecycle and reuse across frames. |
| Crypto optionality (`cryptography`) | MED | Partial/optional crypto availability can cause behavior differences between CI/dev/hardware. | Define explicit install/runtime checks and fail-fast messaging when crypto features are required. |
| Audit tooling continuity | LOW | Reproducible dependency/security audit output is not yet published as a recurring artifact. | Add periodic dependency/audit report generation into CI or a repeatable script. |

## Summary
- Highest dependency risk is operational: timeouts and failure-handling policy consistency across network and subprocess boundaries.
- Centralizing timeout/retry conventions will reduce drift and production-only failures.
