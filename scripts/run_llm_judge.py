#!/usr/bin/env python3
"""
LLM Judge - Evaluate detection rules based on empirical ES test results

Makes deployment decision (APPROVE/CONDITIONAL/REJECT) based on:
- Actual precision/recall from ES integration tests
- TTP alignment with CTI intelligence
- Test coverage completeness
- False positive risk assessment
"""

import argparse
import yaml
import sys
from pathlib import Path
import os

#add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from google import genai
from google.genai import types


def load_integration_results(results_path: Path) -> dict:
    """load ES integration test results"""
    with open(results_path) as f:
        return yaml.safe_load(f)


def load_detection_rule(rule_path: Path) -> dict:
    """load individual detection rule"""
    with open(rule_path) as f:
        return yaml.safe_load(f)


def evaluate_rule_quality(rule_name: str, rule_data: dict, metrics: dict, client: genai.Client) -> dict:
    """use LLM to evaluate single rule based on empirical metrics"""

    #build evaluation prompt
    prompt = f"""You are a SIEM detection engineering expert evaluating a detection rule for production deployment.

# Rule to Evaluate

**Name:** {rule_data.get('name', 'Unknown')}
**Description:** {rule_data.get('description', 'N/A')}
**Severity:** {rule_data.get('severity', 'unknown')}
**Risk Score:** {rule_data.get('risk_score', 0)}

**Query:**
```
{rule_data.get('query', 'N/A')}
```

**MITRE ATT&CK Mapping:**
{yaml.dump(rule_data.get('threat', []), default_flow_style=False)}

**Test Cases Defined:** {len(rule_data.get('test_cases', []))}

# Empirical Test Results (from Elasticsearch)

These are ACTUAL results from deploying the rule to Elasticsearch and testing with embedded payloads:

**Precision:** {metrics.get('precision', 0):.2f} (TP / (TP + FP))
**Recall:** {metrics.get('recall', 0):.2f} (TP / (TP + FN))
**F1 Score:** {metrics.get('f1_score', 0):.2f}
**Pass Threshold:** {metrics.get('pass_threshold', False)}

**Test Results:**
- True Positives (TP): {metrics.get('tp_count', 0)} (malicious activity correctly detected)
- False Negatives (FN): {metrics.get('fn_count', 0)} (malicious activity missed)
- False Positives (FP): {metrics.get('fp_count', 0)} (normal activity incorrectly flagged)
- True Negatives (TN): {metrics.get('tn_count', 0)} (normal activity correctly ignored)

# Evaluation Criteria

Evaluate this rule on:

1. **TTP Alignment (0.0-1.0):** Does the rule actually detect the mapped MITRE technique based on TP results?
2. **Test Coverage (0.0-1.0):** Are edge cases covered? Did we test enough scenarios?
3. **False Positive Risk (LOW/MEDIUM/HIGH):** Based on actual FP count and query specificity
4. **Detection Quality (measured):** Precision ≥ 0.80 and Recall ≥ 0.70 thresholds met?
5. **Evasion Resistance (0.0-1.0):** Can attacker bypass easily? Do FN tests reveal weaknesses?

# Deployment Decision

Make ONE of these decisions:

- **APPROVE:** Rule meets all thresholds, ready for production
- **CONDITIONAL:** Rule is functional but has minor issues (document what to monitor)
- **REJECT:** Rule fails thresholds or has critical issues

# Output Format (YAML)

Respond with ONLY this YAML structure, no additional text:

```yaml
rule_name: "{rule_name}"
quality_score: 0.0  # overall score 0.0-1.0
deployment_decision: APPROVE  # APPROVE, CONDITIONAL, or REJECT
evaluation:
  ttp_alignment: 0.0
  test_coverage: 0.0
  fp_risk: LOW  # LOW, MEDIUM, or HIGH
  evasion_resistance: 0.0
  precision_met: true  # >= 0.80
  recall_met: true  # >= 0.70
reasoning:
  strengths:
    - "Specific strength observed"
  weaknesses:
    - "Specific weakness observed"
  recommendations:
    - "Actionable improvement"
```
"""

    #call Gemini Pro for evaluation
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,  #precise evaluation
            max_output_tokens=2048,
        )
    )

    #parse YAML response
    response_text = response.text.strip()
    if '```yaml' in response_text:
        response_text = response_text.split('```yaml')[1].split('```')[0].strip()
    elif '```' in response_text:
        response_text = response_text.split('```')[1].split('```')[0].strip()

    try:
        evaluation = yaml.safe_load(response_text)
        return evaluation
    except yaml.YAMLError as e:
        print(f"WARNING: Failed to parse LLM response for {rule_name}: {e}")
        print(f"Response: {response_text}")
        #return safe default
        return {
            'rule_name': rule_name,
            'quality_score': 0.0,
            'deployment_decision': 'REJECT',
            'evaluation': {
                'ttp_alignment': 0.0,
                'test_coverage': 0.0,
                'fp_risk': 'HIGH',
                'evasion_resistance': 0.0,
                'precision_met': False,
                'recall_met': False
            },
            'reasoning': {
                'strengths': [],
                'weaknesses': ['LLM evaluation failed to parse'],
                'recommendations': ['Re-evaluate manually']
            }
        }


def make_deployment_decision(evaluations: list) -> str:
    """aggregate individual evaluations into overall decision"""
    if not evaluations:
        return 'REJECT'

    approved = [e for e in evaluations if e['deployment_decision'] == 'APPROVE']

    total = len(evaluations)
    approved_pct = len(approved) / total

    #deployment decision logic
    if approved_pct >= 0.75:  #75%+ approved
        return 'APPROVE'
    elif approved_pct >= 0.50:  #50-75% approved
        return 'CONDITIONAL'
    else:
        return 'REJECT'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration-results', required=True, help='Integration test results YAML')
    parser.add_argument('--rules-dir', required=True, help='Detection rules directory')
    parser.add_argument('--output', default='llm_judge_report.yml', help='Output report path')
    parser.add_argument('--project', help='GCP project ID')
    parser.add_argument('--location', default='global', help='GCP location')

    args = parser.parse_args()

    print("\n" + "="*80)
    print("LLM JUDGE - DEPLOYMENT DECISION")
    print("="*80 + "\n")

    #load integration test results
    integration_results = load_integration_results(Path(args.integration_results))
    metrics = integration_results.get('metrics', {})

    if not metrics:
        print("ERROR: No metrics found in integration results")
        sys.exit(1)

    print(f"Loaded integration results: {len(metrics)} rules tested\n")

    #setup Gemini client
    project_id = args.project or os.environ.get('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print("ERROR: No GCP project ID")
        print("Set via --project or GOOGLE_CLOUD_PROJECT env var")
        sys.exit(1)

    os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=args.location
    )

    print(f"Gemini Pro evaluation enabled (project: {project_id})\n")

    #evaluate each rule
    evaluations = []
    rules_dir = Path(args.rules_dir)

    for rule_file in sorted(rules_dir.glob('*.yml')):
        rule_name = rule_file.stem

        if rule_name not in metrics:
            print(f"WARNING: No metrics for {rule_name}, skipping")
            continue

        print(f"Evaluating: {rule_name}")

        rule_data = load_detection_rule(rule_file)
        rule_metrics = metrics[rule_name]

        evaluation = evaluate_rule_quality(rule_name, rule_data, rule_metrics, client)
        evaluations.append(evaluation)

        print(f"  Quality: {evaluation['quality_score']:.2f}")
        print(f"  Decision: {evaluation['deployment_decision']}")
        print()

    #make overall deployment decision
    overall_decision = make_deployment_decision(evaluations)

    #build report
    summary = {
        'total_rules': len(evaluations),
        'rules_approved': len([e for e in evaluations if e['deployment_decision'] == 'APPROVE']),
        'rules_conditional': len([e for e in evaluations if e['deployment_decision'] == 'CONDITIONAL']),
        'rules_rejected': len([e for e in evaluations if e['deployment_decision'] == 'REJECT']),
        'average_quality_score': sum(e['quality_score'] for e in evaluations) / len(evaluations) if evaluations else 0.0
    }

    report = {
        'timestamp': integration_results.get('timestamp'),
        'deployment_decision': overall_decision,
        'summary': summary,
        'evaluations': evaluations
    }

    #save report
    with open(args.output, 'w') as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False)

    print("="*80)
    print(f"Decision: {overall_decision}")
    print(f"Approved: {summary['rules_approved']}/{summary['total_rules']}")
    print(f"Average Quality: {summary['average_quality_score']:.2f}")
    print("="*80)
    print(f"\nReport saved to {args.output}")

    #exit code based on decision
    if overall_decision == 'REJECT':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
