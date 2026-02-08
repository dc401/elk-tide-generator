#!/usr/bin/env python3
"""filter test payloads for passing rules only"""
import json
import shutil
import sys
from pathlib import Path

#load passing rule IDs
try:
    with open('generated/PASSING_RULE_IDS.json') as f:
        data = json.load(f)
        passing_ids = set(data.get('rule_ids', []))
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"ERROR: Failed to load passing rule IDs: {e}")
    sys.exit(1)

if not passing_ids:
    print("WARNING: No passing rule IDs found")
    sys.exit(0)

#filter test directories
tests_dir = Path('generated/tests')
tests_backup = Path('generated/tests_backup')

if tests_dir.exists():
    tests_backup.mkdir(exist_ok=True)

    #move all tests to backup
    for item in tests_dir.iterdir():
        if item.is_dir():
            shutil.move(str(item), str(tests_backup / item.name))

    #restore only tests for passing rules
    for rule_id in passing_ids:
        rule_prefix = rule_id[:8]

        #find matching test directory
        for test_dir in tests_backup.iterdir():
            if rule_prefix in test_dir.name:
                shutil.move(str(test_dir), str(tests_dir / test_dir.name))
                break

print("✓ Filtered test payloads")
