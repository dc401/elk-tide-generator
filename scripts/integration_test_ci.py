#!/usr/bin/env python3
"""Integration testing with native Elasticsearch - YAML output"""

import subprocess
import sys
import time
import yaml
from pathlib import Path
from typing import Dict
from datetime import datetime

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


def install_elasticsearch():
    """install Elasticsearch via Ubuntu package"""
    print("\n[1/7] Installing Elasticsearch...")
    
    commands = [
        "wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | sudo gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg",
        "echo 'deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main' | sudo tee /etc/apt/sources.list.d/elastic-8.x.list",
        "sudo apt-get update",
        "sudo apt-get install -y elasticsearch"
    ]
    
    for cmd in commands:
        subprocess.run(cmd, shell=True, check=True)
    
    print("  ✓ Elasticsearch installed")


def start_elasticsearch():
    """start Elasticsearch service"""
    print("\n[2/7] Starting Elasticsearch...")
    
    config_update = """
xpack.security.enabled: false
xpack.security.enrollment.enabled: false
"""
    subprocess.run(f"echo '{config_update}' | sudo tee -a /etc/elasticsearch/elasticsearch.yml", shell=True, check=True)
    subprocess.run("sudo systemctl start elasticsearch", shell=True, check=True)
    
    es_url = "http://localhost:9200"
    for _ in range(30):
        try:
            result = subprocess.run(f"curl -sf {es_url}/_cluster/health", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                import json
                health = json.loads(result.stdout)
                if health.get('status') in ['green', 'yellow']:
                    print(f"  ✓ Elasticsearch healthy (status: {health['status']})")
                    return es_url
        except Exception:
            pass
        time.sleep(2)
    
    raise TimeoutError("Elasticsearch not healthy")


def create_test_index(es_client: Elasticsearch, index_name: str = "test-logs"):
    """create index for test payloads"""
    print("\n[3/7] Creating test index...")
    
    if es_client.indices.exists(index=index_name):
        es_client.indices.delete(index=index_name)
    
    es_client.indices.create(
        index=index_name,
        body={
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "event.action": {"type": "keyword"},
                    "event.category": {"type": "keyword"},
                    "event.type": {"type": "keyword"},
                    "process.name": {"type": "keyword"},
                    "process.command_line": {"type": "text"},
                    "file.path": {"type": "keyword"},
                    "file.extension": {"type": "keyword"},
                    "service.name": {"type": "keyword"},
                    "user.name": {"type": "keyword"},
                    "host.name": {"type": "keyword"}
                }
            }
        }
    )
    
    print(f"  ✓ Created index: {index_name}")
    return index_name


def ingest_test_payloads(es_client: Elasticsearch, rules_dir: Path, index_name: str) -> Dict:
    """load all test payloads into Elasticsearch"""
    print("\n[4/7] Ingesting test payloads...")
    
    test_catalog = {}
    total_payloads = 0
    
    #read YAML rules
    for rule_file in rules_dir.glob("*.yml"):
        with open(rule_file) as f:
            rule_data = yaml.safe_load(f)
        
        rule_name = rule_data['name']
        test_cases = rule_data.get('test_cases', [])
        
        if not test_cases:
            continue
        
        test_catalog[rule_name] = {'TP': [], 'FN': [], 'FP': [], 'TN': []}
        
        actions = []
        for idx, test_case in enumerate(test_cases):
            test_type = test_case['type']
            log_entry = test_case['log_entry']
            
            doc_id = f"{rule_name}_{test_type}_{idx}"
            log_entry['_test_id'] = doc_id
            log_entry['_test_type'] = test_type
            log_entry['_rule_name'] = rule_name
            
            actions.append({
                '_index': index_name,
                '_id': doc_id,
                '_source': log_entry
            })
            
            test_catalog[rule_name][test_type].append(doc_id)
            total_payloads += 1
        
        if actions:
            success, _ = bulk(es_client, actions, raise_on_error=False)
            print(f"  ✓ {rule_name}: {success} payloads")
    
    es_client.indices.refresh(index=index_name)
    print(f"\n  Total: {total_payloads} payloads")
    return test_catalog


def execute_detection_rules(es_client: Elasticsearch, rules_dir: Path, index_name: str) -> Dict:
    """run detection queries and capture matches"""
    print("\n[5/7] Executing detection rules...")
    
    results = {}
    
    for rule_file in rules_dir.glob("*.yml"):
        with open(rule_file) as f:
            rule_data = yaml.safe_load(f)
        
        rule_name = rule_data['name']
        query_str = rule_data['query']
        
        print(f"\n  {rule_name}")
        
        try:
            response = es_client.search(
                index=index_name,
                body={"query": {"query_string": {"query": query_str}}, "size": 1000}
            )
            
            hits = response['hits']['hits']
            matched_ids = [hit['_source']['_test_id'] for hit in hits]
            
            print(f"    Matched: {len(matched_ids)} docs")
            
            results[rule_name] = {
                'query': query_str,
                'matched_count': len(matched_ids),
                'matched_ids': matched_ids
            }
        except Exception as e:
            print(f"    ✗ Error: {e}")
            results[rule_name] = {'query': query_str, 'error': str(e), 'matched_count': 0, 'matched_ids': []}
    
    return results


def calculate_metrics(test_catalog: Dict, query_results: Dict) -> Dict:
    """calculate TP/FP/FN/TN metrics"""
    print("\n[6/7] Calculating metrics...")
    
    metrics = {}
    
    for rule_name, expected in test_catalog.items():
        if rule_name not in query_results:
            continue
        
        matched_ids = set(query_results[rule_name]['matched_ids'])
        
        expected_tp = set(expected['TP'])
        expected_fn = set(expected['FN'])
        expected_fp = set(expected['FP'])
        expected_tn = set(expected['TN'])
        
        tp_detected = len(matched_ids & expected_tp)
        tp_total = len(expected_tp)
        
        fn_missed = len(expected_fn & matched_ids)
        fn_total = len(expected_fn)
        
        fp_triggered = len(matched_ids & expected_fp)
        fp_total = len(expected_fp)
        
        tn_triggered = len(matched_ids & expected_tn)
        tn_total = len(expected_tn)
        
        true_positives = tp_detected
        false_positives = fp_triggered + tn_triggered
        false_negatives = tp_total - tp_detected
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        metrics[rule_name] = {
            'tp_detected': tp_detected,
            'tp_total': tp_total,
            'fn_missed': fn_missed,
            'fn_total': fn_total,
            'fp_triggered': fp_triggered,
            'fp_total': fp_total,
            'tn_triggered': tn_triggered,
            'tn_total': tn_total,
            'precision': round(precision, 3),
            'recall': round(recall, 3),
            'f1_score': round(f1_score, 3),
            'pass_threshold': precision >= 0.80 and recall >= 0.70
        }
        
        print(f"\n  {rule_name}:")
        print(f"    TP: {tp_detected}/{tp_total}, FN: {fn_missed}/{fn_total}")
        print(f"    FP: {fp_triggered}/{fp_total}, TN issues: {tn_triggered}/{tn_total}")
        print(f"    Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1_score:.3f}")
        print(f"    {'✓ PASS' if metrics[rule_name]['pass_threshold'] else '✗ FAIL'}")
    
    return metrics


def save_results(metrics: Dict, test_catalog: Dict, query_results: Dict, output_file: str):
    """save results to YAML"""
    print(f"\n[7/7] Saving to {output_file}...")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_rules': len(metrics),
            'rules_passed': sum(1 for m in metrics.values() if m['pass_threshold']),
            'rules_failed': sum(1 for m in metrics.values() if not m['pass_threshold'])
        },
        'metrics': metrics,
        'test_catalog': test_catalog,
        'query_results': query_results
    }
    
    with open(output_file, 'w') as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n{'='*80}")
    print(f"Tested: {report['summary']['total_rules']}")
    print(f"Passed: {report['summary']['rules_passed']}")
    print(f"Failed: {report['summary']['rules_failed']}")
    print(f"{'='*80}")
    
    return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--rules-dir', default='generated/detection_rules')
    parser.add_argument('--output', default='integration_test_results.yml')
    parser.add_argument('--skip-install', action='store_true')
    
    args = parser.parse_args()
    
    rules_dir = Path(args.rules_dir)
    if not rules_dir.exists():
        print(f"ERROR: {rules_dir} not found")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print("ELASTICSEARCH INTEGRATION TESTING")
    print(f"{'='*80}\n")
    
    try:
        if not args.skip_install:
            install_elasticsearch()
        
        es_url = start_elasticsearch()
        es_client = Elasticsearch([es_url], request_timeout=30)
        
        index_name = create_test_index(es_client)
        test_catalog = ingest_test_payloads(es_client, rules_dir, index_name)
        query_results = execute_detection_rules(es_client, rules_dir, index_name)
        metrics = calculate_metrics(test_catalog, query_results)
        report = save_results(metrics, test_catalog, query_results, args.output)
        
        if report['summary']['rules_failed'] > 0:
            print(f"\n⚠ {report['summary']['rules_failed']} rule(s) need refinement")
            sys.exit(1)
        else:
            print("\n✓ All rules passed!")
    
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
