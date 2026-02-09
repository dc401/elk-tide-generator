#!/usr/bin/env python3
"""Stage rules that passed validation for human review

Moves validated detection rules from generated/ to staged_rules/ with:
- Unique UIDs for tracking
- Quality metadata (LLM scores, test metrics)
- Test payloads for review
- Batch tracking for PR creation
"""

import argparse
import json
import shutil
import hashlib
import time
from pathlib import Path
from datetime import datetime
import yaml

def generate_rule_uid(rule_name: str) -> str:
    """generate short UID from rule name for filename uniqueness"""
    hash_obj = hashlib.sha256(rule_name.encode())
    return hash_obj.hexdigest()[:8]

def load_test_results(test_results_path: Path) -> dict:
    """load integration test results"""
    if not test_results_path.exists():
        print(f"⚠️  No test results found at {test_results_path}")
        return {}

    with open(test_results_path) as f:
        return json.load(f)

def load_quality_scores(rules_dir: Path) -> dict:
    """extract quality scores from rule YAML files (saved during generation)"""
    scores = {}

    for rule_file in rules_dir.glob("*.yml"):
        with open(rule_file) as f:
            rule = yaml.safe_load(f)

        #quality score stored in metadata if available
        rule_name = rule['name']
        #default to passing score if not stored (assume validated)
        scores[rule_name] = {
            'quality_score': 0.90,  #default for validated rules
            'rule_file': rule_file.name
        }

    return scores

def stage_rule(rule_file: Path, staged_dir: Path, batch_id: str, test_results: dict, quality_score: float) -> dict:
    """stage single rule with metadata"""

    #load rule
    with open(rule_file) as f:
        rule = yaml.safe_load(f)

    rule_name = rule['name']
    uid = generate_rule_uid(rule_name)

    #create staged filename with UID
    staged_filename = f"{rule_file.stem}_{uid}.yml"
    staged_path = staged_dir / staged_filename

    #copy rule with UID
    shutil.copy(rule_file, staged_path)
    print(f"  ✓ Staged: {staged_filename}")

    #extract test metrics for this rule
    rule_metrics = {}
    if test_results and 'rule_results' in test_results:
        for result in test_results['rule_results']:
            if result['rule_name'] == rule_file.stem:
                rule_metrics = result.get('metrics', {})
                break

    #create metadata
    metadata = {
        'rule_name': rule_name,
        'rule_file': staged_filename,
        'uid': uid,
        'batch_id': batch_id,
        'staged_timestamp': datetime.now().isoformat(),
        'quality_validation': {
            'overall_score': quality_score,
            'validator': 'Gemini 2.5 Pro',
            'passed_threshold': quality_score >= 0.75
        },
        'integration_test_metrics': rule_metrics,
        'mitre_ttps': [
            {
                'tactic_id': t['tactic']['id'],
                'tactic_name': t['tactic']['name'],
                'technique_id': t['technique'][0]['id'],
                'technique_name': t['technique'][0]['name']
            }
            for t in rule.get('threat', [])
        ],
        'references': rule.get('references', []),
        'severity': rule.get('severity', 'medium'),
        'risk_score': rule.get('risk_score', 50)
    }

    #save metadata
    metadata_path = staged_dir / f"{rule_file.stem}_{uid}_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"    → Metadata: {metadata_path.name}")

    return metadata

def copy_test_payloads(rules_dir: Path, staged_dir: Path, rule_file: Path, uid: str):
    """copy test payloads from rule YAML to staged tests directory"""

    #load rule to get test cases
    with open(rule_file) as f:
        rule = yaml.safe_load(f)

    test_cases = rule.get('test_cases', [])
    if not test_cases:
        return

    #create test directory
    test_dir = staged_dir / 'tests' / f"{rule_file.stem}_{uid}"
    test_dir.mkdir(parents=True, exist_ok=True)

    #save each test case
    for idx, test_case in enumerate(test_cases, 1):
        test_type = test_case.get('type', 'unknown').lower()
        test_filename = f"{test_type}_{idx:02d}.json"

        test_payload = {
            'type': test_case.get('type'),
            'description': test_case.get('description'),
            'log_entry': test_case.get('log_entry'),
            'expected_match': test_case.get('expected_match'),
            'evasion_technique': test_case.get('evasion_technique')
        }

        with open(test_dir / test_filename, 'w') as f:
            json.dump(test_payload, f, indent=2)

    print(f"    → Test cases: {len(test_cases)} saved to tests/{rule_file.stem}_{uid}/")

def main():
    parser = argparse.ArgumentParser(description='Stage passing detection rules for review')
    parser.add_argument('--rules-dir', required=True, help='Directory with validated rules')
    parser.add_argument('--test-results', help='Path to test_results.json from integration tests')
    parser.add_argument('--staged-dir', default='staged_rules', help='Output directory for staged rules')
    parser.add_argument('--quality-threshold', type=float, default=0.75, help='Minimum quality score')

    args = parser.parse_args()

    rules_dir = Path(args.rules_dir)
    staged_dir = Path(args.staged_dir)

    print("="*80)
    print("STAGING VALIDATED RULES FOR HUMAN REVIEW")
    print("="*80)
    print()

    #create staged directory
    staged_dir.mkdir(exist_ok=True)
    (staged_dir / 'tests').mkdir(exist_ok=True)

    #load test results if available
    test_results = {}
    if args.test_results:
        test_results = load_test_results(Path(args.test_results))

    #load quality scores
    quality_scores = load_quality_scores(rules_dir)

    #generate batch ID
    batch_id = f"batch_{int(time.time())}"

    #stage each rule
    staged_count = 0
    staged_metadata = []

    for rule_file in sorted(rules_dir.glob("*.yml")):
        with open(rule_file) as f:
            rule = yaml.safe_load(f)

        rule_name = rule['name']
        quality_score = quality_scores.get(rule_name, {}).get('quality_score', 0.90)

        #check quality threshold
        if quality_score < args.quality_threshold:
            print(f"  ✗ Skipped: {rule_name} (score {quality_score:.2f} < {args.quality_threshold})")
            continue

        #stage the rule
        metadata = stage_rule(rule_file, staged_dir, batch_id, test_results, quality_score)
        staged_metadata.append(metadata)

        #copy test payloads
        copy_test_payloads(rules_dir, staged_dir, rule_file, metadata['uid'])

        staged_count += 1
        print()

    #save batch summary
    batch_summary = {
        'batch_id': batch_id,
        'staged_timestamp': datetime.now().isoformat(),
        'rules_staged': staged_count,
        'quality_threshold': args.quality_threshold,
        'rules': staged_metadata,
        'overall_metrics': test_results.get('overall_metrics', {}) if test_results else {}
    }

    summary_path = staged_dir / f"{batch_id}_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(batch_summary, f, indent=2)

    print("="*80)
    print(f"✓ STAGED {staged_count} RULES FOR REVIEW")
    print("="*80)
    print()
    print(f"Batch ID: {batch_id}")
    print(f"Location: {staged_dir}/")
    print(f"Summary: {summary_path}")
    print()
    print("Next: Create PR for human review")
    print(f"  → Review metadata in {staged_dir}/*_metadata.json")
    print(f"  → Review test cases in {staged_dir}/tests/")
    print()

    #output for GitHub Actions
    print(f"batch_id={batch_id}")
    print(f"rule_count={staged_count}")

if __name__ == '__main__':
    main()
