#!/usr/bin/env python3
"""filter rules that pass both quality and integration thresholds"""
import json
import shutil
import os
import sys
from pathlib import Path
from datetime import datetime

#load quality report
try:
    with open('generated/QUALITY_REPORT.json') as f:
        quality_report = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"ERROR: Failed to load quality report: {e}")
    sys.exit(1)

#load integration test results
try:
    with open('generated/INTEGRATION_TEST_RESULTS.json') as f:
        test_results = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"ERROR: Failed to load integration test results: {e}")
    sys.exit(1)

#validate required fields
if 'rule_evaluations' not in quality_report:
    print("ERROR: Quality report missing 'rule_evaluations' field")
    sys.exit(1)

#filter rules that pass BOTH quality and integration thresholds
passing_rules = []

for eval_result in quality_report['rule_evaluations']:
    rule_id = eval_result.get('rule_id')
    decision = eval_result.get('deployment_decision', 'REJECT')

    #check if rule exists in test results
    if rule_id not in test_results:
        continue

    metrics = test_results[rule_id]

    #criteria for staging:
    # - LLM judge decision: APPROVE or CONDITIONAL
    # - Integration test F1 >= 0.75
    # - Integration test precision >= 0.80
    # - At least 1 TP detected

    if (decision in ['APPROVE', 'CONDITIONAL'] and
        metrics.get('f1_score', 0) >= 0.75 and
        metrics.get('precision', 0) >= 0.80 and
        metrics.get('tp', 0) >= 1):

        passing_rules.append({
            'rule_id': rule_id,
            'rule_title': eval_result.get('rule_title'),
            'quality_score': eval_result.get('overall_quality_score', 0),
            'f1_score': metrics.get('f1_score', 0),
            'precision': metrics.get('precision', 0),
            'recall': metrics.get('recall', 0)
        })

print(f"\n{'='*80}")
print(f"STAGING FILTER RESULTS")
print(f"{'='*80}\n")
print(f"Total rules evaluated: {len(quality_report['rule_evaluations'])}")
print(f"Rules passing quality gate: {len(passing_rules)}")
print()

if not passing_rules:
    print("⚠️  No rules passed both quality and integration thresholds")
    print("No rules will be staged for human review")
    exit(0)

#create staged_rules directory
staged_dir = Path('staged_rules')
staged_dir.mkdir(exist_ok=True)

batch_id = f"batch_{int(datetime.now().timestamp())}"
batch_file = staged_dir / f"{batch_id}.json"

#copy passing rules to staged_rules
for rule_info in passing_rules:
    rule_id = rule_info['rule_id']

    #find rule file
    rule_file = None
    for f in Path('generated/sigma_rules').glob('*.yml'):
        with open(f) as rf:
            content = rf.read()
            if f"id: {rule_id}" in content:
                rule_file = f
                break

    if rule_file:
        dest_file = staged_dir / rule_file.name
        shutil.copy(rule_file, dest_file)
        print(f"✓ Staged: {rule_info['rule_title'][:60]}")

#save batch metadata
batch_metadata = {
    'batch_id': batch_id,
    'timestamp': datetime.now().isoformat(),
    'rules': passing_rules,
    'criteria': {
        'llm_judge': 'APPROVE or CONDITIONAL',
        'f1_score': '>= 0.75',
        'precision': '>= 0.80',
        'min_tp': '>= 1'
    }
}

with open(batch_file, 'w') as f:
    json.dump(batch_metadata, f, indent=2)

print(f"\n✓ Saved batch metadata: {batch_file}")
print(f"\nBatch ID: {batch_id}")
print(f"Rules staged: {len(passing_rules)}")

#set outputs for GitHub Actions
with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
    f.write(f"batch_id={batch_id}\n")
    f.write(f"rule_count={len(passing_rules)}\n")
