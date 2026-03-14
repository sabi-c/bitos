# Dependency Audit Report

Date: 2026-03-14  
Repository: `bitos`

Requested input files:
- `requirements-device.txt`
- `requirements-server.txt`

Result of file lookup in repository:
- Neither file exists in this checkout.
- Available requirement files are `requirements.txt` and `web_preview/requirements.txt`.

Audit commands requested and executed:

```bash
pip install pip-audit --break-system-packages
pip-audit -r requirements-device.txt 2>&1
pip-audit -r requirements-server.txt 2>&1
pip list --outdated 2>&1
```

Environment constraints observed:
- `requirements-device.txt` and `requirements-server.txt` are not present in this repository tree.
- `pip-audit` installation failed both via configured proxy (`403 Forbidden`) and direct egress (`[Errno 101] Network is unreachable`), so CVE scanning could not be executed.
- `pip list --outdated` could not complete due the same package-index connectivity limitation (repeated retries against package index).
- `pip-audit` installation failed due to blocked package index/proxy access (`403 Forbidden`), so CVE scanning could not be executed.
- `pip list --outdated` could not complete due the same network/proxy limitation (repeated retries against package index).

## CVEs found

| Package | CVE ID | Severity | Fix version | Action needed |
|---|---|---|---|---|
| N/A | N/A | Unknown | N/A | `pip-audit` unavailable in this environment; rerun once package index access is available. |

## Outdated packages

| Package | Current version | Latest version | Safe to upgrade? |
|---|---|---|---|
| N/A | N/A | N/A | Unknown: `pip list --outdated` could not fetch latest metadata due proxy/network restriction. |

## Recommendations

- **Upgrade immediately (HIGH CVE):**
  - None identified in this run because CVE scan could not be executed.
- **Upgrade next sprint (MED CVE or significantly outdated):**
  - Re-run this audit in CI or a network-enabled environment with:
    - `pip install pip-audit --break-system-packages`
    - `pip-audit -r requirements-device.txt`
    - `pip-audit -r requirements-server.txt`
    - `pip list --outdated`
  - Ensure `requirements-device.txt` and `requirements-server.txt` are added to the repo (or update audit scripts to use actual requirement file paths such as `requirements.txt` / `web_preview/requirements.txt`).
  - Ensure `requirements-device.txt` and `requirements-server.txt` are added to the repo (or update audit scripts to use actual requirement file paths).
- **Packages fine (LOW or no issues):**
  - No package-level determination could be made in this run due audit tooling/network constraints.
