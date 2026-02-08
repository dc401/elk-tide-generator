#!/usr/bin/env python3
"""
Pre-Integration Validation Pipeline

Step 1: Lucene syntax validation (deterministic)
Step 2: YAML → JSON conversion + linting
Step 3: LLM schema validation with research

Prevents bad rules from reaching integration testing
"""

import asyncio
import json
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List

from google import genai
from google.genai import types


#lucene query parser for syntax validation
try:
    from luqum.parser import parser as lucene_parser
    LUCENE_AVAILABLE = True
except ImportError:
    LUCENE_AVAILABLE = False
    print("⚠ luqum not installed - skipping Lucene syntax validation")
    print("  Install: pip install luqum")


def validate_lucene_syntax(query: str) -> Dict:
    """step 1: deterministic lucene syntax check"""
    if not LUCENE_AVAILABLE:
        return {'valid': True, 'warning': 'luqum not available - install: pip install luqum'}

    try:
        tree = lucene_parser.parse(query)
        return {
            'valid': True,
            'tree': str(tree),
            'query_length': len(query),
            'operators_found': {
                'AND': query.count(' AND '),
                'OR': query.count(' OR '),
                'NOT': query.count(' NOT '),
                'wildcards': query.count('*')
            }
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'query': query,
            'error_type': type(e).__name__
        }


def convert_yaml_to_json(yaml_file: Path, json_output_dir: Path) -> Dict:
    """step 2: convert YAML to JSON with linting"""
    try:
        with open(yaml_file) as f:
            rule_data = yaml.safe_load(f)
        
        #validate required fields
        required = ['name', 'query', 'type', 'severity', 'risk_score']
        missing = [f for f in required if f not in rule_data]
        if missing:
            return {'valid': False, 'error': f'Missing fields: {missing}'}
        
        #convert to JSON
        json_output_dir.mkdir(parents=True, exist_ok=True)
        json_file = json_output_dir / f"{yaml_file.stem}.json"
        
        with open(json_file, 'w') as f:
            json.dump(rule_data, f, indent=2)
        
        #lint JSON (try to reload)
        with open(json_file) as f:
            json.load(f)  #will raise if invalid
        
        return {
            'valid': True,
            'json_file': str(json_file),
            'size_bytes': json_file.stat().st_size
        }
    
    except Exception as e:
        return {'valid': False, 'error': str(e)}


async def llm_schema_validator(
    rule_yaml_path: Path,
    rule_json_path: Path,
    client,
    model_name: str = 'gemini-2.5-pro'
) -> Dict:
    """step 3: LLM validates against official ES schema with research"""
    
    with open(rule_yaml_path) as f:
        rule_yaml = f.read()
    
    with open(rule_json_path) as f:
        rule_json = f.read()
    
    #prompt with research + ICL examples
    prompt = f"""You are an Elasticsearch Detection Rule expert. Validate this rule against the official Elasticsearch Detection Rule API schema.

## Rule to Validate

YAML:
```yaml
{rule_yaml}
```

JSON:
```json
{rule_json}
```

## Your Task

1. **Research** the official Elasticsearch Detection Rule API schema using Google Search
   - Search: "Elasticsearch Detection Rule API schema 8.12"
   - Verify required fields, data types, valid values
   - Check ECS field naming conventions

2. **Validate** against schema:
   - Required fields present?
   - Data types correct?
   - Query syntax valid for Elasticsearch?
   - ECS fields properly named?
   - MITRE ATT&CK references valid?

3. **Compare** to known good examples from elastic/detection-rules repo
   - Does structure match production rules?
   - Are threat mappings correct?
   - Are test cases structured properly?

## Known Good Example (ICL)

From elastic/detection-rules (Windows process creation):
```yaml
name: Suspicious Process Creation
type: query
query: "event.code:1 AND process.name:cmd.exe"
language: lucene
severity: medium
risk_score: 47
threat:
  - framework: "MITRE ATT&CK"
    tactic:
      id: TA0002
      name: Execution
    technique:
      - id: T1059
        name: Command and Scripting Interpreter
```

## Output YAML

```yaml
valid: true/false
schema_compliance:
  required_fields: pass/fail
  data_types: pass/fail
  query_syntax: pass/fail
  ecs_fields: pass/fail
  threat_mapping: pass/fail
issues:
  - list of problems found
warnings:
  - list of non-critical issues
research_references:
  - URLs consulted for validation
recommendation: APPROVE | FIX_REQUIRED
fixes_needed:
  - specific changes required
```

IMPORTANT: Research official docs before responding. Validate against actual ES 8.x schema, not assumptions.
"""

    config = types.GenerateContentConfig(
        temperature=0.1,  #low temp for deterministic validation
        system_instruction="You are a precise validator. Research official documentation before making judgments. Return structured YAML."
    )
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config
    )
    
    #parse YAML response
    try:
        result = yaml.safe_load(response.text)
        if isinstance(result, dict):
            return result
        #extract from markdown
        if '```yaml' in response.text:
            start = response.text.find('```yaml') + 7
            end = response.text.find('```', start)
            yaml_text = response.text[start:end].strip()
            return yaml.safe_load(yaml_text)
        return {'valid': False, 'error': 'Could not parse LLM response'}
    except Exception as e:
        return {'valid': False, 'error': f'Parse error: {e}', 'raw': response.text}


async def validate_rule_pipeline(
    yaml_file: Path,
    staging_dir: Path,
    client
) -> Dict:
    """full validation pipeline for single rule"""
    
    rule_name = yaml_file.stem
    print(f"\n[Validate] {rule_name}")
    
    results = {
        'rule_name': rule_name,
        'yaml_file': str(yaml_file),
        'step1_lucene': {},
        'step2_conversion': {},
        'step3_schema': {},
        'overall_pass': False
    }
    
    #load rule
    with open(yaml_file) as f:
        rule_data = yaml.safe_load(f)
    
    #step 1: lucene syntax
    print("  [1/3] Lucene syntax check...")
    print(f"    Query: {rule_data['query'][:80]}...")
    lucene_result = validate_lucene_syntax(rule_data['query'])
    results['step1_lucene'] = lucene_result

    if not lucene_result['valid']:
        print(f"    ✗ FAIL: {lucene_result.get('error')}")
        print(f"    Error Type: {lucene_result.get('error_type')}")
        print(f"    Query: {lucene_result.get('query')}")
        return results

    print("    ✓ PASS")
    if 'operators_found' in lucene_result:
        ops = lucene_result['operators_found']
        print(f"    Operators: AND={ops['AND']}, OR={ops['OR']}, NOT={ops['NOT']}, wildcards={ops['wildcards']}")
    
    #step 2: YAML → JSON conversion
    print("  [2/3] YAML → JSON conversion...")
    json_dir = staging_dir / 'json'
    conversion_result = convert_yaml_to_json(yaml_file, json_dir)
    results['step2_conversion'] = conversion_result
    
    if not conversion_result['valid']:
        print(f"    ✗ FAIL: {conversion_result.get('error')}")
        return results
    print(f"    ✓ PASS ({conversion_result['size_bytes']} bytes)")
    
    #step 3: LLM schema validation
    print("  [3/3] LLM schema validation (with research)...")
    print("    Calling Gemini Pro to validate against ES schema...")
    schema_result = await llm_schema_validator(
        yaml_file,
        Path(conversion_result['json_file']),
        client
    )
    results['step3_schema'] = schema_result

    if not schema_result.get('valid', False):
        print(f"    ✗ FAIL - Schema validation failed")
        if 'issues' in schema_result:
            print("    Issues found:")
            for issue in schema_result['issues']:
                print(f"      - {issue}")
        if 'schema_compliance' in schema_result:
            print("    Schema compliance:")
            for check, result in schema_result['schema_compliance'].items():
                status = "✓" if result == "pass" else "✗"
                print(f"      {status} {check}: {result}")
        if 'fixes_needed' in schema_result and schema_result['fixes_needed']:
            print("    Fixes needed:")
            for fix in schema_result['fixes_needed']:
                print(f"      → {fix}")
        return results

    print("    ✓ PASS - Schema validation successful")

    #show schema compliance details
    if 'schema_compliance' in schema_result:
        print("    Schema compliance:")
        for check, result in schema_result['schema_compliance'].items():
            print(f"      ✓ {check}: {result}")

    #check for warnings
    if 'warnings' in schema_result and schema_result['warnings']:
        print("    ⚠ Warnings:")
        for warning in schema_result['warnings']:
            print(f"      - {warning}")

    #show research references
    if 'research_references' in schema_result and schema_result['research_references']:
        print("    Research references:")
        for ref in schema_result['research_references'][:3]:  #show first 3
            print(f"      - {ref}")
    
    results['overall_pass'] = True
    return results


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Pre-Integration Validation Pipeline')
    parser.add_argument('--rules-dir', default='generated/detection_rules')
    parser.add_argument('--staging-dir', default='generated/staging')
    parser.add_argument('--output', default='validation_report.yml')
    parser.add_argument('--project', help='GCP project ID')
    parser.add_argument('--location', default='global')
    
    args = parser.parse_args()
    
    #setup
    project_id = args.project or os.environ.get('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print("ERROR: GCP project ID required")
        sys.exit(1)
    
    rules_dir = Path(args.rules_dir)
    staging_dir = Path(args.staging_dir)
    
    if not rules_dir.exists():
        print(f"ERROR: {rules_dir} not found")
        sys.exit(1)
    
    #setup Vertex AI
    os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=args.location
    )
    
    print(f"\n{'='*80}")
    print("PRE-INTEGRATION VALIDATION PIPELINE")
    print(f"{'='*80}")
    
    #validate all rules
    yaml_files = list(rules_dir.glob("*.yml"))
    print(f"\nFound {len(yaml_files)} rules to validate")
    
    all_results = []
    for yaml_file in yaml_files:
        result = await validate_rule_pipeline(yaml_file, staging_dir, client)
        all_results.append(result)
    
    #summary
    passed = sum(1 for r in all_results if r['overall_pass'])
    failed = len(all_results) - passed
    
    report = {
        'timestamp': Path.cwd().name,
        'summary': {
            'total_rules': len(all_results),
            'passed': passed,
            'failed': failed
        },
        'results': all_results
    }
    
    #save report
    with open(args.output, 'w') as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total: {len(all_results)}")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {failed}")
    print(f"\nReport: {args.output}")
    
    if failed > 0:
        print(f"\n⚠ {failed} rule(s) failed validation")
        sys.exit(1)
    
    print("\n✓ All rules passed validation")


if __name__ == '__main__':
    asyncio.run(main())
