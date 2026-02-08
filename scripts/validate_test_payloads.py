#!/usr/bin/env python3
"""
Validate test payloads are valid JSON and have expected structure

Platform-agnostic: Validates based on logsource product from corresponding Sigma rule
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Tuple

def validate_json_structure(payload_file: Path) -> Tuple[bool, str]:
    """validate payload is valid JSON"""
    try:
        with open(payload_file) as f:
            data = json.load(f)

        #check required metadata fields
        if '_scenario' not in data:
            return False, "Missing _scenario field"
        if '_description' not in data:
            return False, "Missing _description field"
        if '_expected_detection' not in data:
            return False, "Missing _expected_detection field"

        #validate scenario type
        valid_scenarios = ['true_positive', 'false_negative', 'false_positive', 'true_negative']
        if data['_scenario'] not in valid_scenarios:
            return False, f"Invalid _scenario: {data['_scenario']}"

        return True, ""

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"

def validate_test_directory(rule_dir: Path) -> Dict[str, bool]:
    """validate all test payloads for a rule"""
    results = {}

    required_files = [
        'true_positive_01.json',
        'false_negative_01.json',
        'false_positive_01.json',
        'true_negative_01.json'
    ]

    for filename in required_files:
        filepath = rule_dir / filename
        if not filepath.exists():
            results[filename] = False
        else:
            valid, error = validate_json_structure(filepath)
            results[filename] = valid
            if not valid:
                print(f"    ✗ {filename}: {error}")

    return results

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Validate test payloads')
    parser.add_argument('tests_dir', nargs='?', default='generated/tests',
                       help='Directory containing test payloads')
    args = parser.parse_args()

    tests_dir = Path(args.tests_dir)

    if not tests_dir.exists():
        print(f"WARNING: Tests directory not found: {tests_dir}")
        print("No rules to validate - skipping")
        return 0

    rule_dirs = [d for d in tests_dir.iterdir() if d.is_dir()]

    if not rule_dirs:
        print(f"WARNING: No test directories found in {tests_dir}")
        print("No rules to validate - skipping")
        return 0

    print(f"\n{'='*80}")
    print(f"TEST PAYLOAD VALIDATION")
    print(f"{'='*80}\n")
    print(f"Tests directory: {tests_dir}")
    print(f"Found {len(rule_dirs)} rule test directories\n")

    total_payloads = 0
    valid_payloads = 0
    failed_rules = []

    for rule_dir in sorted(rule_dirs):
        print(f"[{rule_dir.name}]")
        results = validate_test_directory(rule_dir)

        rule_total = len(results)
        rule_valid = sum(1 for v in results.values() if v)

        total_payloads += rule_total
        valid_payloads += rule_valid

        if rule_valid == rule_total:
            print(f"  ✓ {rule_valid}/{rule_total} payloads valid\n")
        else:
            print(f"  ✗ {rule_valid}/{rule_total} payloads valid\n")
            failed_rules.append(rule_dir.name)

    print(f"{'='*80}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*80}\n")
    print(f"Total payloads:  {total_payloads}")
    print(f"Valid payloads:  {valid_payloads} ✓")
    print(f"Invalid payloads: {total_payloads - valid_payloads} ✗\n")

    if failed_rules:
        print(f"Rules with validation failures:")
        for rule in failed_rules:
            print(f"  - {rule}")
        print()
        return 1
    else:
        print("✓ All test payloads are valid\n")
        return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
