#!/usr/bin/env python3
"""
Mock integration test without Docker requirement

Simulates Elasticsearch integration test by:
1. Converting Sigma rules to ES queries
2. Matching test payloads against detection logic
3. Calculating metrics without actual Elasticsearch

Use this when Docker is not available.
"""

import json
import yaml
import re
import ssl
from pathlib import Path
from typing import Dict, List

ssl._create_default_https_context = ssl._create_unverified_context

from sigma.rule import SigmaRule
from sigma.backends.elasticsearch import LuceneBackend

def convert_sigma_to_elasticsearch(rules_dir: Path) -> Dict:
    """convert Sigma rules to Elasticsearch queries"""
    print("\n[1/4] Converting Sigma rules to Elasticsearch queries...")

    backend = LuceneBackend()
    queries = {}

    rule_files = list(rules_dir.glob('*.yml')) + list(rules_dir.glob('*.yaml'))

    for rule_file in rule_files:
        with open(rule_file) as f:
            rule_yaml = yaml.safe_load(f)
            rule = SigmaRule.from_yaml(open(rule_file))

        lucene_queries = backend.convert_rule(rule)
        lucene_query = '\n'.join(lucene_queries) if isinstance(lucene_queries, list) else str(lucene_queries)

        #store detection as dict for matching
        queries[str(rule.id)] = {
            'title': rule.title,
            'query': lucene_query,
            'level': rule.level.name,
            'file': rule_file.name,
            'detection': rule_yaml.get('detection', {})
        }

    print(f"  ✓ Converted {len(queries)} Sigma rules")
    return queries

def simple_match(payload: Dict, detection: Dict) -> bool:
    """simple payload matching against detection logic"""
    #extract selection criteria
    if 'selection' not in detection:
        return False

    selection = detection['selection']

    #check if payload matches selection
    for field, expected_value in selection.items():
        #handle field modifiers
        base_field = field.split('|')[0]

        #navigate nested fields
        payload_value = payload
        for part in base_field.split('.'):
            if isinstance(payload_value, dict) and part in payload_value:
                payload_value = payload_value[part]
            else:
                return False  #field not found

        #check value match
        if isinstance(expected_value, list):
            if payload_value not in expected_value:
                return False
        else:
            if payload_value != expected_value:
                return False

    #check filter_legitimate
    if 'filter_legitimate' in detection and detection['filter_legitimate']:
        filter_cond = detection['filter_legitimate']

        for field, filter_value in filter_cond.items():
            base_field = field.split('|')[0]

            #navigate nested fields
            payload_value = payload
            for part in base_field.split('.'):
                if isinstance(payload_value, dict) and part in payload_value:
                    payload_value = payload_value[part]
                else:
                    break

            #check if matches filter (if so, exclude)
            modifier = field.split('|')[1] if '|' in field else None

            if modifier == 'endswith':
                if isinstance(filter_value, str) and str(payload_value).endswith(filter_value):
                    return False  #filtered out
                if isinstance(filter_value, list):
                    for fv in filter_value:
                        if str(payload_value).endswith(fv):
                            return False

    return True  #matched selection, not filtered

def simulate_detection(queries: Dict, tests_dir: Path) -> Dict:
    """simulate running detection queries"""
    print("\n[2/4] Simulating detection queries...")

    detections = {}

    for rule_id, rule_info in queries.items():
        matched_payloads = []

        #find test directory for this rule
        for rule_dir in tests_dir.iterdir():
            if not rule_dir.is_dir():
                continue

            if str(rule_id)[:8] not in rule_dir.name:
                continue

            #check each payload
            for payload_file in rule_dir.glob('*.json'):
                with open(payload_file) as f:
                    payload = json.load(f)

                #simple matching
                if simple_match(payload, rule_info['detection']):
                    matched_payloads.append(f"{rule_dir.name}_{payload_file.stem}")

        detections[rule_id] = matched_payloads

    total_detections = sum(len(ids) for ids in detections.values())
    print(f"  ✓ Simulated {len(queries)} queries, {total_detections} matches")

    return detections

def calculate_metrics(tests_dir: Path, detections: Dict, queries: Dict) -> Dict:
    """calculate precision, recall, F1"""
    print("\n[3/4] Calculating detection metrics...")

    results = {}

    for rule_dir in sorted(tests_dir.iterdir()):
        if not rule_dir.is_dir():
            continue

        #find matching rule
        rule_id = None
        for rid in queries.keys():
            if rid[:8] in rule_dir.name:
                rule_id = rid
                break

        if not rule_id:
            continue

        detected_ids = set(detections.get(rule_id, []))

        tp = fp = tn = fn = 0

        for payload_file in rule_dir.glob('*.json'):
            with open(payload_file) as f:
                payload = json.load(f)

            doc_id = f"{rule_dir.name}_{payload_file.stem}"
            expected = payload.get('_expected_detection', False)
            detected = doc_id in detected_ids

            if expected and detected:
                tp += 1
            elif not expected and detected:
                fp += 1
            elif not expected and not detected:
                tn += 1
            elif expected and not detected:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        results[rule_id] = {
            'rule_title': queries[rule_id]['title'],
            'rule_level': queries[rule_id]['level'],
            'tp': tp,
            'fp': fp,
            'tn': tn,
            'fn': fn,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score
        }

    print(f"  ✓ Calculated metrics for {len(results)} rules")
    return results

def print_results(results: Dict):
    """print test results"""
    print("\n[4/4] Test Results\n")
    print("="*80)
    print("MOCK INTEGRATION TEST RESULTS")
    print("="*80)
    print()

    total_rules = len(results)
    total_tp = sum(r['tp'] for r in results.values())
    total_fp = sum(r['fp'] for r in results.values())
    total_tn = sum(r['tn'] for r in results.values())
    total_fn = sum(r['fn'] for r in results.values())

    avg_precision = sum(r['precision'] for r in results.values()) / total_rules if total_rules > 0 else 0
    avg_recall = sum(r['recall'] for r in results.values()) / total_rules if total_rules > 0 else 0
    avg_f1 = sum(r['f1_score'] for r in results.values()) / total_rules if total_rules > 0 else 0

    print(f"Rules tested: {total_rules}")
    print(f"\nOverall Metrics:")
    print(f"  True Positives:  {total_tp}")
    print(f"  False Positives: {total_fp}")
    print(f"  True Negatives:  {total_tn}")
    print(f"  False Negatives: {total_fn}")
    print(f"\nAverage Performance:")
    print(f"  Precision: {avg_precision:.2f}")
    print(f"  Recall:    {avg_recall:.2f}")
    print(f"  F1 Score:  {avg_f1:.2f}")

    print(f"\n{'='*80}")
    print("PER-RULE RESULTS")
    print("="*80)

    for rule_id, metrics in sorted(results.items(), key=lambda x: x[1]['f1_score'], reverse=True):
        print(f"\n{metrics['rule_title']} (Level: {metrics['rule_level']})")
        print(f"  TP: {metrics['tp']}  FP: {metrics['fp']}  TN: {metrics['tn']}  FN: {metrics['fn']}")
        print(f"  Precision: {metrics['precision']:.2f}  Recall: {metrics['recall']:.2f}  F1: {metrics['f1_score']:.2f}")

        if metrics['precision'] >= 0.80 and metrics['recall'] >= 0.70:
            print(f"  ✓ PASS: Meets quality thresholds")
        else:
            if metrics['precision'] < 0.80:
                print(f"  ⚠ LOW PRECISION: Too many false positives")
            if metrics['recall'] < 0.70:
                print(f"  ⚠ LOW RECALL: Missing true positives")

    print(f"\n{'='*80}\n")
    print("NOTE: This is a simplified simulation.")
    print("Real Elasticsearch integration provides more accurate matching.")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Mock integration test without Docker')
    parser.add_argument('--rules', default='generated/sigma_rules',
                       help='Directory containing Sigma rules')
    parser.add_argument('--tests', default='generated/tests',
                       help='Directory containing test payloads')
    args = parser.parse_args()

    rules_dir = Path(args.rules)
    tests_dir = Path(args.tests)

    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        return 1

    if not tests_dir.exists():
        print(f"ERROR: Tests directory not found: {tests_dir}")
        return 1

    print("="*80)
    print("MOCK SIGMA RULE INTEGRATION TESTING")
    print("="*80)
    print(f"\nRules: {rules_dir}")
    print(f"Tests: {tests_dir}")
    print("\nNOTE: Running without Docker - using simplified matching\n")

    #convert sigma rules
    queries = convert_sigma_to_elasticsearch(rules_dir)

    #simulate detection
    detections = simulate_detection(queries, tests_dir)

    #calculate metrics
    results = calculate_metrics(tests_dir, detections, queries)

    #print results
    print_results(results)

    #save results
    output_file = Path('generated/INTEGRATION_TEST_RESULTS.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {output_file}")

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
