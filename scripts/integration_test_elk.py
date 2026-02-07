#!/usr/bin/env python3
"""
Integration test Sigma rules with ephemeral Elasticsearch

Deploys temporary Elasticsearch container, ingests test payloads,
converts Sigma rules to ES queries, runs detection, calculates metrics.

Platform-agnostic: Works with any Sigma rules for any log source.
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.exceptions import ConnectionError as ESConnectionError
except ImportError:
    print("ERROR: elasticsearch library not installed")
    print("Run: pip install elasticsearch")
    sys.exit(1)

import yaml
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from sigma.rule import SigmaRule
from sigma.backends.elasticsearch import LuceneBackend

def start_elasticsearch() -> bool:
    """start ephemeral Elasticsearch container"""
    print("\n[1/7] Starting Elasticsearch container...")

    #check if container already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", "name=sigma-test-elasticsearch"],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        print("  ✓ Elasticsearch already running")
        return True

    #start new container
    cmd = [
        "docker", "run", "-d",
        "--name", "sigma-test-elasticsearch",
        "-p", "9200:9200",
        "-e", "discovery.type=single-node",
        "-e", "xpack.security.enabled=false",
        "-e", "ES_JAVA_OPTS=-Xms256m -Xmx256m",
        "-e", "bootstrap.memory_lock=false",
        "docker.elastic.co/elasticsearch/elasticsearch:8.12.0"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ Failed to start Elasticsearch: {result.stderr}")
        return False

    print("  ✓ Elasticsearch container started")
    return True

def wait_for_elasticsearch(timeout: int = 120) -> bool:
    """wait for Elasticsearch to be ready"""
    print("\n[2/7] Waiting for Elasticsearch to be ready...")

    import requests

    start_time = time.time()
    last_log_time = 0

    while time.time() - start_time < timeout:
        try:
            #use requests library for health check (more reliable than es.ping())
            response = requests.get('http://localhost:9200/_cluster/health', timeout=3)
            if response.status_code == 200:
                health = response.json()
                status = health.get('status', 'unknown')
                print(f"\n  ✓ Elasticsearch ready after {int(time.time() - start_time)}s (status: {status})")
                return True
        except (requests.exceptions.RequestException, Exception) as e:
            #show progress every 5 seconds
            current_time = time.time()
            if current_time - last_log_time >= 5:
                print(f"  Waiting... {int(current_time - start_time)}s", end='\r', flush=True)
                last_log_time = current_time

        time.sleep(2)

    print(f"\n  ✗ Elasticsearch not ready after {timeout}s")
    return False

def convert_sigma_to_elasticsearch(rules_dir: Path) -> Dict[str, str]:
    """convert Sigma rules to Elasticsearch queries"""
    print("\n[3/7] Converting Sigma rules to Elasticsearch queries...")

    backend = LuceneBackend()
    queries = {}

    rule_files = list(rules_dir.glob('*.yml')) + list(rules_dir.glob('*.yaml'))

    for rule_file in rule_files:
        with open(rule_file) as f:
            rule = SigmaRule.from_yaml(f)

        lucene_queries = backend.convert_rule(rule)
        lucene_query = '\n'.join(lucene_queries) if isinstance(lucene_queries, list) else str(lucene_queries)

        queries[rule.id] = {
            'title': rule.title,
            'query': lucene_query,
            'level': rule.level.name,
            'file': rule_file.name
        }

    print(f"  ✓ Converted {len(queries)} Sigma rules to Elasticsearch queries")
    return queries

def ingest_test_payloads(es: Elasticsearch, tests_dir: Path) -> Dict[str, List[str]]:
    """ingest test payloads into Elasticsearch"""
    print("\n[4/7] Ingesting test payloads into Elasticsearch...")

    index_name = "test-logs"

    #create index
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)

    es.indices.create(index=index_name, body={
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "protoPayload": {"type": "object", "enabled": True},
                "resource": {"type": "object", "enabled": True},
                "_scenario": {"type": "keyword"},
                "_expected_detection": {"type": "boolean"}
            }
        }
    })

    payload_map = {}
    total_ingested = 0

    for rule_dir in sorted(tests_dir.iterdir()):
        if not rule_dir.is_dir():
            continue

        payload_map[rule_dir.name] = []

        for payload_file in rule_dir.glob('*.json'):
            with open(payload_file) as f:
                payload = json.load(f)

            doc_id = f"{rule_dir.name}_{payload_file.stem}"

            #ingest to elasticsearch
            es.index(index=index_name, id=doc_id, document=payload)

            payload_map[rule_dir.name].append({
                'id': doc_id,
                'scenario': payload.get('_scenario'),
                'expected': payload.get('_expected_detection')
            })

            total_ingested += 1

    #refresh index
    es.indices.refresh(index=index_name)

    print(f"  ✓ Ingested {total_ingested} test payloads into index '{index_name}'")
    return payload_map

def run_detection_queries(es: Elasticsearch, queries: Dict, index_name: str = "test-logs") -> Dict[str, List[str]]:
    """run Elasticsearch queries and collect matches"""
    print("\n[5/7] Running detection queries...")

    detections = {}

    for rule_id, rule_info in queries.items():
        query_dsl = {
            "query": {
                "query_string": {
                    "query": rule_info['query'],
                    "default_field": "*",
                    "analyze_wildcard": True
                }
            },
            "size": 100
        }

        try:
            response = es.search(index=index_name, body=query_dsl)

            matched_ids = [hit['_id'] for hit in response['hits']['hits']]
            detections[rule_id] = matched_ids

        except Exception as e:
            print(f"  ⚠ Error running query for {rule_info['title']}: {e}")
            detections[rule_id] = []

    total_detections = sum(len(ids) for ids in detections.values())
    print(f"  ✓ Ran {len(queries)} detection queries, {total_detections} total matches")

    return detections

def calculate_metrics(payload_map: Dict, detections: Dict, queries: Dict) -> Dict:
    """calculate precision, recall, F1 for each rule"""
    print("\n[6/7] Calculating detection metrics...")

    results = {}

    for rule_dir, payloads in payload_map.items():
        #find matching rule by directory name (contains rule ID)
        rule_id = None
        for rid in queries.keys():
            if rid[:8] in rule_dir:  #match first 8 chars of UUID
                rule_id = rid
                break

        if not rule_id:
            continue

        detected_ids = set(detections.get(rule_id, []))

        #categorize payloads
        tp = 0  #true positive: expected detection, was detected
        fp = 0  #false positive: not expected, was detected
        tn = 0  #true negative: not expected, not detected
        fn = 0  #false negative: expected detection, not detected

        for payload_info in payloads:
            doc_id = payload_info['id']
            expected = payload_info['expected']
            detected = doc_id in detected_ids

            if expected and detected:
                tp += 1
            elif not expected and detected:
                fp += 1
            elif not expected and not detected:
                tn += 1
            elif expected and not detected:
                fn += 1

        #calculate metrics
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
            'f1_score': f1_score,
            'total_payloads': len(payloads),
            'detections': len([p for p in payloads if p['id'] in detected_ids])
        }

    print(f"  ✓ Calculated metrics for {len(results)} rules")
    return results

def print_results(results: Dict):
    """print test results"""
    print("\n[7/7] Test Results\n")
    print("="*80)
    print("INTEGRATION TEST RESULTS")
    print("="*80)
    print()

    #summary statistics
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

    #per-rule results
    print(f"\n{'='*80}")
    print("PER-RULE RESULTS")
    print("="*80)

    for rule_id, metrics in sorted(results.items(), key=lambda x: x[1]['f1_score'], reverse=True):
        print(f"\n{metrics['rule_title']} (Level: {metrics['rule_level']})")
        print(f"  TP: {metrics['tp']}  FP: {metrics['fp']}  TN: {metrics['tn']}  FN: {metrics['fn']}")
        print(f"  Precision: {metrics['precision']:.2f}  Recall: {metrics['recall']:.2f}  F1: {metrics['f1_score']:.2f}")

        if metrics['fp'] > 0:
            print(f"  ⚠ {metrics['fp']} false positive(s) detected")
        if metrics['fn'] > 0:
            print(f"  ⚠ {metrics['fn']} false negative(s) (missed detections)")

    print(f"\n{'='*80}\n")

def cleanup_elasticsearch():
    """stop and remove Elasticsearch container"""
    print("\nCleaning up Elasticsearch container...")

    subprocess.run(
        ["docker", "stop", "sigma-test-elasticsearch"],
        capture_output=True
    )
    subprocess.run(
        ["docker", "rm", "sigma-test-elasticsearch"],
        capture_output=True
    )

    print("  ✓ Elasticsearch container removed")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Integration test Sigma rules with Elasticsearch')
    parser.add_argument('--rules', default='generated/sigma_rules',
                       help='Directory containing Sigma rules')
    parser.add_argument('--tests', default='generated/tests',
                       help='Directory containing test payloads')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Keep Elasticsearch running after test')
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
    print("SIGMA RULE INTEGRATION TESTING")
    print("="*80)
    print(f"\nRules: {rules_dir}")
    print(f"Tests: {tests_dir}")

    try:
        #start elasticsearch
        if not start_elasticsearch():
            return 1

        #wait for ready
        if not wait_for_elasticsearch():
            cleanup_elasticsearch()
            return 1

        es = Elasticsearch(['http://localhost:9200'])

        #convert sigma rules
        queries = convert_sigma_to_elasticsearch(rules_dir)

        #ingest test payloads
        payload_map = ingest_test_payloads(es, tests_dir)

        #run detection queries
        detections = run_detection_queries(es, queries)

        #calculate metrics
        results = calculate_metrics(payload_map, detections, queries)

        #print results
        print_results(results)

        #save results to file
        output_file = Path('generated/INTEGRATION_TEST_RESULTS.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {output_file}")

    finally:
        if not args.no_cleanup:
            cleanup_elasticsearch()

    return 0

if __name__ == '__main__':
    sys.exit(main())
