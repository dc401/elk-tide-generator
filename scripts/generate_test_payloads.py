#!/usr/bin/env python3
"""
Generate test payloads (TP/FN/FP/TN) from Sigma rules

Reads Sigma rules with embedded test_scenarios and generates realistic
log payloads for testing detection accuracy.

Platform-agnostic: Generates payloads based on logsource.product/service
"""

import json
import yaml
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any

def set_nested_field(obj: Dict, path: str, value: Any):
    """set nested field value using dot notation"""
    parts = path.split('.')
    for part in parts[:-1]:
        if part not in obj:
            obj[part] = {}
        obj = obj[part]
    obj[parts[-1]] = value

def generate_gcp_audit_log(fields: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """generate GCP audit log structure"""

    base_log = {
        "insertId": str(uuid.uuid4()),
        "logName": "projects/test-project/logs/cloudaudit.googleapis.com%2Factivity",
        "protoPayload": {
            "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
            "status": {"code": 0},
            "authenticationInfo": {"principalEmail": "user@example.com"},
            "requestMetadata": {
                "callerIp": "203.0.113.10",
                "callerSuppliedUserAgent": "gcloud/1.0"
            },
            "serviceName": "",
            "methodName": "",
            "authorizationInfo": [],
            "request": {},
            "response": {}
        },
        "resource": {"type": "unknown"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "NOTICE",
        "labels": {},
        "operation": {},
        "receiveTimestamp": datetime.now(timezone.utc).isoformat()
    }

    #populate fields from detection
    for field_path, value in fields.items():
        if value:
            set_nested_field(base_log, field_path, value)

    return base_log

def generate_aws_cloudtrail_log(fields: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """generate AWS CloudTrail log structure"""

    base_log = {
        "eventVersion": "1.08",
        "userIdentity": fields.get("userIdentity", {}),
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "eventSource": fields.get("eventSource", "iam.amazonaws.com"),
        "eventName": fields.get("eventName", ""),
        "awsRegion": fields.get("awsRegion", "us-east-1"),
        "sourceIPAddress": fields.get("sourceIPAddress", "203.0.113.10"),
        "userAgent": fields.get("userAgent", "aws-cli/2.0"),
        "requestParameters": fields.get("requestParameters", {}),
        "responseElements": fields.get("responseElements", {}),
        "requestID": str(uuid.uuid4()),
        "eventID": str(uuid.uuid4()),
        "eventType": fields.get("eventType", "AwsApiCall"),
        "recipientAccountId": fields.get("recipientAccountId", "123456789012")
    }

    return base_log

def generate_windows_event_log(fields: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """generate Windows Event Log structure"""

    base_log = {
        "EventID": fields.get("EventID", 4624),
        "ProviderName": fields.get("ProviderName", "Microsoft-Windows-Security-Auditing"),
        "TimeCreated": datetime.now(timezone.utc).isoformat(),
        "Computer": fields.get("Computer", "WORKSTATION01"),
        "Channel": fields.get("Channel", "Security"),
        "Level": fields.get("Level", 0),
        "Keywords": fields.get("Keywords", "0x8020000000000000"),
        "EventRecordID": fields.get("EventRecordID", 12345),
        "ProcessID": fields.get("ProcessID", 1234),
        "ThreadID": fields.get("ThreadID", 5678),
        "EventData": fields.get("EventData", {})
    }

    return base_log

def generate_kubernetes_audit_log(fields: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """generate Kubernetes audit log structure"""

    base_log = {
        "kind": "Event",
        "apiVersion": "audit.k8s.io/v1",
        "level": fields.get("level", "Metadata"),
        "auditID": str(uuid.uuid4()),
        "stage": fields.get("stage", "ResponseComplete"),
        "requestURI": fields.get("requestURI", ""),
        "verb": fields.get("verb", ""),
        "user": fields.get("user", {}),
        "sourceIPs": fields.get("sourceIPs", ["203.0.113.10"]),
        "userAgent": fields.get("userAgent", "kubectl/v1.25.0"),
        "objectRef": fields.get("objectRef", {}),
        "responseStatus": fields.get("responseStatus", {"code": 200}),
        "requestReceivedTimestamp": datetime.now(timezone.utc).isoformat(),
        "stageTimestamp": datetime.now(timezone.utc).isoformat()
    }

    return base_log

def generate_payload(logsource: Dict[str, str], fields: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """generate log payload based on logsource product"""

    product = logsource.get("product", "").lower()

    if product == "gcp":
        return generate_gcp_audit_log(fields, scenario)
    elif product == "aws":
        return generate_aws_cloudtrail_log(fields, scenario)
    elif product == "windows":
        return generate_windows_event_log(fields, scenario)
    elif product == "kubernetes":
        return generate_kubernetes_audit_log(fields, scenario)
    else:
        #generic log structure
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": str(uuid.uuid4()),
            "source": product,
            "fields": fields
        }

def extract_fields_from_detection(detection: Dict) -> Dict[str, Any]:
    """extract field values from Sigma detection section"""
    fields = {}

    for key, value in detection.items():
        if key == "condition":
            continue
        if isinstance(value, dict):
            for field_name, field_value in value.items():
                #handle field modifiers (field|contains, field|endswith)
                base_field = field_name.split('|')[0]

                if isinstance(field_value, list):
                    fields[base_field] = field_value[0] if field_value else ""
                else:
                    fields[base_field] = field_value

    return fields

def generate_test_payloads_for_rule(rule_path: Path, output_dir: Path):
    """generate TP/FN/FP/TN test payloads for a single Sigma rule"""

    with open(rule_path) as f:
        rule = yaml.safe_load(f)

    rule_id = rule.get('id', 'unknown')
    rule_title = rule.get('title', 'Untitled')
    logsource = rule.get('logsource', {})
    detection = rule.get('detection', {})
    test_scenarios = rule.get('test_scenarios', {})

    if not test_scenarios:
        print(f"⚠️  No test_scenarios in {rule_path.name}")
        return

    #create output directory for this rule
    rule_output_dir = output_dir / rule_path.stem
    rule_output_dir.mkdir(parents=True, exist_ok=True)

    #extract base fields from detection logic
    base_fields = extract_fields_from_detection(detection)

    #add example fields from test_scenarios if available
    example_fields = test_scenarios.get('example_log_fields', {})
    base_fields.update(example_fields)

    #generate true positive
    tp_scenario = test_scenarios.get('true_positive', '')
    if tp_scenario:
        tp_fields = base_fields.copy()
        tp_payload = generate_payload(logsource, tp_fields, 'true_positive')
        tp_payload['_scenario'] = 'true_positive'
        tp_payload['_description'] = tp_scenario
        tp_payload['_expected_detection'] = True

        tp_file = rule_output_dir / 'true_positive_01.json'
        with open(tp_file, 'w') as f:
            json.dump(tp_payload, f, indent=2)
        print(f"  ✓ Generated TP: {tp_file.name}")

    #generate false negative (evasion)
    fn_scenario = test_scenarios.get('false_negative', '')
    if fn_scenario:
        fn_fields = base_fields.copy()

        #modify fields to evade detection (based on filter_legitimate)
        if 'filter_legitimate' in detection and detection['filter_legitimate']:
            for filter_field, filter_value in detection['filter_legitimate'].items():
                base_field = filter_field.split('|')[0]
                if isinstance(filter_value, list) and filter_value:
                    fn_fields[base_field] = filter_value[0]
                elif filter_value:
                    fn_fields[base_field] = filter_value

        fn_payload = generate_payload(logsource, fn_fields, 'false_negative')
        fn_payload['_scenario'] = 'false_negative'
        fn_payload['_description'] = fn_scenario
        fn_payload['_expected_detection'] = False
        fn_payload['_note'] = 'Evasion technique - should NOT trigger alert but is malicious'

        fn_file = rule_output_dir / 'false_negative_01.json'
        with open(fn_file, 'w') as f:
            json.dump(fn_payload, f, indent=2)
        print(f"  ✓ Generated FN: {fn_file.name}")

    #generate false positive (legitimate)
    fp_scenario = test_scenarios.get('false_positive', '')
    if fp_scenario:
        fp_fields = base_fields.copy()

        #use filter_legitimate values to create legit activity
        if 'filter_legitimate' in detection and detection['filter_legitimate']:
            for filter_field, filter_value in detection['filter_legitimate'].items():
                base_field = filter_field.split('|')[0]
                if isinstance(filter_value, list) and filter_value:
                    fp_fields[base_field] = filter_value[0]
                elif filter_value:
                    fp_fields[base_field] = filter_value

        fp_payload = generate_payload(logsource, fp_fields, 'false_positive')
        fp_payload['_scenario'] = 'false_positive'
        fp_payload['_description'] = fp_scenario
        fp_payload['_expected_detection'] = False
        fp_payload['_note'] = 'Legitimate activity - should NOT trigger alert'

        fp_file = rule_output_dir / 'false_positive_01.json'
        with open(fp_file, 'w') as f:
            json.dump(fp_payload, f, indent=2)
        print(f"  ✓ Generated FP: {fp_file.name}")

    #generate true negative (normal activity)
    tn_scenario = test_scenarios.get('true_negative', '')
    if tn_scenario:
        tn_fields = {}

        #use completely different values to represent normal activity
        for field in base_fields:
            if field.endswith('.methodName'):
                tn_fields[field] = 'NormalOperation'
            elif field.endswith('.principalEmail'):
                tn_fields[field] = 'user@example.com'
            elif field.endswith('.code'):
                tn_fields[field] = 0
            else:
                tn_fields[field] = 'normal_value'

        tn_payload = generate_payload(logsource, tn_fields, 'true_negative')
        tn_payload['_scenario'] = 'true_negative'
        tn_payload['_description'] = tn_scenario
        tn_payload['_expected_detection'] = False
        tn_payload['_note'] = 'Normal activity - should NOT trigger alert'

        tn_file = rule_output_dir / 'true_negative_01.json'
        with open(tn_file, 'w') as f:
            json.dump(tn_payload, f, indent=2)
        print(f"  ✓ Generated TN: {tn_file.name}")

    print(f"✓ Test payloads generated for: {rule_title}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate test payloads from Sigma rules')
    parser.add_argument('rules_dir', nargs='?', default='generated/sigma_rules',
                       help='Directory containing Sigma rules')
    parser.add_argument('--output', '-o', default='generated/tests',
                       help='Output directory for test payloads')
    args = parser.parse_args()

    rules_dir = Path(args.rules_dir)
    output_dir = Path(args.output)

    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    rule_files = list(rules_dir.glob('*.yml')) + list(rules_dir.glob('*.yaml'))

    if not rule_files:
        print(f"ERROR: No Sigma rules found in {rules_dir}")
        return 1

    print(f"\n{'='*80}")
    print(f"GENERATING TEST PAYLOADS")
    print(f"{'='*80}\n")
    print(f"Rules directory: {rules_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Found {len(rule_files)} Sigma rule(s)\n")

    for rule_file in sorted(rule_files):
        print(f"\n[{rule_file.name}]")
        try:
            generate_test_payloads_for_rule(rule_file, output_dir)
        except Exception as e:
            print(f"  ✗ ERROR: {e}")

    print(f"\n{'='*80}")
    print(f"TEST PAYLOAD GENERATION COMPLETE")
    print(f"{'='*80}\n")
    print(f"Test payloads saved to: {output_dir}/")
    print(f"Each rule has: TP, FN, FP, TN payloads\n")

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
