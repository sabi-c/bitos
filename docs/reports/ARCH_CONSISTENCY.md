# BITOS Architecture Consistency Audit

Scope: Runtime boundaries and layering expectations across UI, BLE/network, server, and companion lanes.

## Findings

| Pattern | Severity | Inconsistency | Recommendation |
|---|---|---|---|
| Render-layer purity (`device/overlays/notification.py`, `device/screens/panels/settings.py`) | HIGH | UI render functions perform repository reads, violating non-blocking render architecture. | Enforce state hydration outside render and render from immutable frame-state snapshots. |
| BLE network command boundary (`device/bluetooth/wifi_manager.py`) | HIGH | Network/system command boundary lacks a consistent non-blocking contract (timeouts + typed errors). | Introduce a BLE network command policy module with shared timeout/error semantics. |
| Logging standardization (`device/main.py`, `device/input/handler.py`) | MED | Mixed direct `print()` and logging patterns reduce observability consistency. | Standardize on structured logging with category tags and error context. |
| Settings source of truth (`device/screens/panels/settings.py`) | MED | UI-level hardcoded options diverge from repository-driven settings architecture intent. | Move option catalogs to repository-backed/config-managed sources. |
| Cross-lane audit completeness | LOW | Audit artifacts were previously inconsistent across report domains. | Maintain synchronized report set (`CODE_QUALITY`, `TEST_COVERAGE`, `DEPENDENCY_AUDIT`, `ARCH_CONSISTENCY`) per audit cycle. |

## Summary
- The primary architectural drift is localized and remediable without broad redesign.
- Enforcing render purity and BLE command contracts will produce the largest stability gains before hardware deployment.
