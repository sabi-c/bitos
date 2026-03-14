#!/usr/bin/env python3
"""Validate TASK_TRACKER formatting for Active Backlog vs Iteration Log rows."""
from pathlib import Path
import re
import sys

text = Path("docs/planning/TASK_TRACKER.md").read_text().splitlines()

active = False
errors = []
for idx, line in enumerate(text, 1):
    if line.startswith("## Active Backlog"):
        active = True
        continue
    if line.startswith("## Iteration Log"):
        active = False
        continue
    if line.startswith("## "):
        active = False

    if active and re.match(r"^\|\s*20\d\d-\d\d-\d\d\s*\|", line):
        errors.append(f"Line {idx}: date-formatted row found in Active Backlog")

if errors:
    print("TASK_TRACKER validation FAILED")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("TASK_TRACKER validation OK")
