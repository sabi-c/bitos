#!/usr/bin/env python3
"""Quick smoke test. Run after boot: python scripts/smoke_test.py"""
import os
import sys
import urllib.request


def main() -> int:
    base = os.environ.get("SERVER_URL", "http://localhost:8000")
    results: list[str] = []

    def check(name, fn):
        try:
            fn()
            results.append(f"  ✓ {name}")
        except Exception as e:
            results.append(f"  ✗ {name}: {e}")

    check("Server reachable", lambda: urllib.request.urlopen(f"{base}/health", timeout=5))
    check(
        "Claude API key set",
        lambda: (_ for _ in ()).throw(Exception("Not set")) if not os.environ.get("ANTHROPIC_API_KEY") else None,
    )
    check(
        "Database exists",
        lambda: (_ for _ in ()).throw(Exception("Missing"))
        if not os.path.exists(os.environ.get("BITOS_DB_FILE", "device/data/bitos.db"))
        else None,
    )
    check("Font file exists", lambda: open("device/assets/fonts/PressStart2P.ttf", "rb").close())

    print("BITOS SMOKE TEST")
    print("─" * 30)
    for r in results:
        print(r)

    fails = [r for r in results if "✗" in r]
    print("─" * 30)
    if fails:
        print(f"FAILED: {len(fails)} issue(s)")
        return 1

    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
