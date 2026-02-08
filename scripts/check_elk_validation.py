#!/usr/bin/env python3
"""check ELK validation results"""
import json
import sys

with open('generated/ELK_VALIDATION_REPORT.json') as f:
    report = json.load(f)

approved = report.get('approved_queries', 0)
rejected = report.get('rejected_queries', 0)

print(f"\n{'='*80}")
print("ELK QUERY VALIDATION RESULTS")
print(f"{'='*80}\n")
print(f"Approved Queries: {approved}")
print(f"Rejected Queries: {rejected}")
print(f"\n{'='*80}\n")

if approved == 0:
    print("❌ No queries passed validation")
    print("Fix Sigma → ELK conversion issues before integration testing")
    sys.exit(1)
else:
    print(f"✅ {approved} queries ready for integration testing")
    sys.exit(0)
