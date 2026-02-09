#!/usr/bin/env python3
"""refine detection rules based on integration test failures

reads test results, identifies failing rules, and invokes agent to refine queries
uses test case failures (FN/FP) as context for intelligent refinement
"""
import argparse
import json
import os
import sys
import yaml
from pathlib import Path
from datetime import datetime

#use gemini API directly for refinement
from google import genai
from google.genai import types

def analyze_test_failures(test_results: dict) -> list:
    """identify which rules need refinement based on test results

    returns list of rules with their failure context
    """
    failing_rules = []

    for rule_result in test_results.get('rule_results', []):
        rule_name = rule_result['rule_name']
        metrics = rule_result['metrics']

        #check if rule is underperforming
        precision = metrics.get('precision', 0)
        recall = metrics.get('recall', 0)

        #flag rules with recall < 70% (missing attacks)
        if recall < 0.70:
            failure_context = {
                'rule_name': rule_name,
                'current_metrics': metrics,
                'issue': 'LOW_RECALL',
                'false_negatives': [],
                'false_positives': [],
                'reason': f'Missing {metrics.get("FN", 0)} true positives (recall {recall:.1%} < 70%)'
            }

            #extract FN test cases
            for test in rule_result.get('test_cases', []):
                if test['expected'] == 'TP' and test['actual'] == 'NO_MATCH':
                    failure_context['false_negatives'].append({
                        'description': test['description'],
                        'log_sample': test.get('log_payload', {}),
                        'query': rule_result.get('query', '')
                    })
                elif test['expected'] == 'TN' and test['actual'] == 'MATCH':
                    failure_context['false_positives'].append({
                        'description': test['description'],
                        'log_sample': test.get('log_payload', {})
                    })

            failing_rules.append(failure_context)

        #also flag rules with precision < 60% (too many false alarms)
        elif precision < 0.60:
            failure_context = {
                'rule_name': rule_name,
                'current_metrics': metrics,
                'issue': 'LOW_PRECISION',
                'false_negatives': [],
                'false_positives': [],
                'reason': f'Too many false positives (precision {precision:.1%} < 60%)'
            }

            #extract FP test cases
            for test in rule_result.get('test_cases', []):
                if test['expected'] in ['TN', 'FP'] and test['actual'] == 'MATCH':
                    failure_context['false_positives'].append({
                        'description': test['description'],
                        'log_sample': test.get('log_payload', {})
                    })

            failing_rules.append(failure_context)

    return failing_rules

def create_refinement_prompt(failing_rules: list, cti_context: str) -> str:
    """create prompt for agent to refine failing rules"""

    prompt = f"""# Detection Rule Refinement Task

Your previous detection rules failed integration testing. Analyze the failures and generate REFINED rules.

## Original CTI Context
{cti_context[:2000]}...

## Test Failures Analysis

"""

    for failure in failing_rules:
        prompt += f"""### Rule: {failure['rule_name']}
**Issue:** {failure['issue']} - {failure['reason']}
**Current Metrics:** Precision {failure['current_metrics']['precision']:.1%} | Recall {failure['current_metrics']['recall']:.1%}

"""

        if failure['false_negatives']:
            prompt += "**False Negatives (missed attacks):**\n"
            for fn in failure['false_negatives'][:3]:  #limit to 3 examples
                prompt += f"- {fn['description']}\n"
                prompt += f"  Log fields: {list(fn['log_sample'].keys())}\n"
                prompt += f"  Current query: {fn['query']}\n"

        if failure['false_positives']:
            prompt += "**False Positives (benign activity flagged):**\n"
            for fp in failure['false_positives'][:3]:
                prompt += f"- {fp['description']}\n"
                prompt += f"  Log fields: {list(fp['log_sample'].keys())}\n"

        prompt += "\n"

    prompt += """## Refinement Instructions

For EACH failing rule:

1. **Analyze the root cause:**
   - Why did the query miss true positives? (field names, wildcards, logic)
   - Why did it match false positives? (filters too broad)

2. **Fix the Elasticsearch query:**
   - Ensure field names match the actual log schema (check log_sample keys)
   - Add missing field combinations
   - Tighten filters to reduce false positives
   - Use wildcards appropriately

3. **Update test cases if needed:**
   - Ensure test payloads have the correct field names
   - Make sure benign test cases are truly different from malicious ones

4. **Output refined rules** in the same YAML format as before

CRITICAL: Look at the actual log field names in the test samples. If the query references fields that don't exist in the logs, that's why it's failing.
"""

    return prompt

def refine_rules(
    test_results_path: Path,
    rules_dir: Path,
    cti_dir: Path,
    output_dir: Path,
    region: str
):
    """invoke Gemini to refine failing rules"""

    print(f"Loading test results from {test_results_path}...")
    with open(test_results_path) as f:
        test_results = json.load(f)

    #analyze failures
    failing_rules = analyze_test_failures(test_results)

    if not failing_rules:
        print("✓ No rules need refinement (all passed thresholds)")
        return 0

    print(f"Found {len(failing_rules)} rules needing refinement:")
    for failure in failing_rules:
        print(f"  - {failure['rule_name']}: {failure['reason']}")

    #load original CTI context
    cti_files = list(cti_dir.glob('*.md')) + list(cti_dir.glob('*.txt'))
    cti_context = ""
    for cti_file in cti_files[:2]:  #limit to first 2 files
        cti_context += cti_file.read_text()[:5000] + "\n\n"

    #create refinement prompt
    refinement_prompt = create_refinement_prompt(failing_rules, cti_context)

    print(f"\nInvoking Gemini refinement (region: {region})...")
    print(f"Prompt length: {len(refinement_prompt)} chars")

    #setup client
    client = genai.Client(
        vertexai=True,
        project=os.environ['GOOGLE_CLOUD_PROJECT'],
        location=region
    )

    try:
        #call Gemini with refinement prompt
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=refinement_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
            )
        )

        response_text = response.text
        print(f"\nGot response ({len(response_text)} chars)")

        #extract YAML rules from response
        refined_count = 0
        for yaml_block in extract_yaml_blocks(response_text):
            try:
                rule_data = yaml.safe_load(yaml_block)
                if rule_data and 'name' in rule_data:
                    rule_name = rule_data['name'].replace(' ', '_').replace('-', '_').lower()
                    output_file = output_dir / f"{rule_name}.yml"

                    with open(output_file, 'w') as f:
                        f.write(yaml_block)

                    print(f"  ✓ Refined: {output_file.name}")
                    refined_count += 1
            except yaml.YAMLError as e:
                print(f"  ⚠️  Skipping invalid YAML block: {e}")
                continue

        if refined_count > 0:
            print(f"\n✓ Refined {refined_count} rules")
            return 0
        else:
            print("⚠️  No valid refined rules extracted from response")
            return 1

    except Exception as e:
        print(f"❌ Refinement failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def extract_yaml_blocks(text: str) -> list:
    """extract YAML code blocks from markdown response"""
    import re
    yaml_pattern = r'```(?:yaml)?\n(.*?)\n```'
    matches = re.findall(yaml_pattern, text, re.DOTALL)
    return matches if matches else [text]  #if no code blocks, treat entire response as YAML

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-results', required=True, help='Path to test_results.json')
    parser.add_argument('--rules-dir', required=True, help='Directory with current rules')
    parser.add_argument('--cti-dir', required=True, help='Directory with CTI source files')
    parser.add_argument('--output', required=True, help='Output directory for refined rules')
    parser.add_argument('--region', required=True, help='GCP region for Vertex AI')
    args = parser.parse_args()

    test_results_path = Path(args.test_results)
    rules_dir = Path(args.rules_dir)
    cti_dir = Path(args.cti_dir)
    output_dir = Path(args.output)

    if not test_results_path.exists():
        print(f"ERROR: Test results not found: {test_results_path}")
        return 1

    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        return 1

    if not cti_dir.exists():
        print(f"ERROR: CTI directory not found: {cti_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    return refine_rules(
        test_results_path,
        rules_dir,
        cti_dir,
        output_dir,
        args.region
    )

if __name__ == '__main__':
    sys.exit(main())
