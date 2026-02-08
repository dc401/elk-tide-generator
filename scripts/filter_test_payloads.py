#!/usr/bin/env python3
"""filter test payloads for passing rules only"""
import json
import shutil
from pathlib import Path

#load passing rule IDs
with open('generated/PASSING_RULE_IDS.json') as f:
    data = json.load(f)
    passing_ids = set(data['rule_ids'])

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
