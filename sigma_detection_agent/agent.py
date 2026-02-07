"""
sigma detection agent - main orchestration

converts CTI → Sigma detection rules → validated detections
"""

import os
import json
import asyncio
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

#google ADK imports
from google.genai import types
from google.genai.types import GenerateContentConfig
from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import InMemoryRunner

#import schemas
from sigma_detection_agent.schemas import (
    CTIAnalysisOutput,
    TTPMapping,
    TTPMappingOutput,
    SigmaRuleOutput,
    TestPayloadSet,
    TestValidationOutput,
    DetectionQualityReport
)

#import tools
from sigma_detection_agent.tools import load_cti_files

#environment setup
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'

#GCP configuration
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')

#retry configurations (adapted from gcphunter)
AGGRESSIVE_RETRY_CONFIG = types.HttpOptions(
    retry_options=types.HttpRetryOptions(
        initial_delay=15,
        attempts=6,
        exp_base=6,
        max_delay=92,
        http_status_codes=[429, 500, 503, 504]
    )
)

FLASH_RETRY_CONFIG = types.HttpOptions(
    retry_options=types.HttpRetryOptions(
        initial_delay=8,
        attempts=4,
        exp_base=3,
        max_delay=72,
        http_status_codes=[429, 500, 503, 504]
    )
)

#inter-agent delay to prevent quota bursting
INTER_AGENT_DELAY = 3.0  #3 seconds between agents

#================================
# Helper Functions
#================================

def safe_json_parse(state: dict, key: str, default=None):
    """safely parse JSON from state, handle errors"""
    try:
        value = state.get(key, default)
        if isinstance(value, str):
            return json.loads(value)
        return value
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Warning: Could not parse {key}: {e}")
        return default

def truncate_output(text: str, max_chars: int = 120000) -> str:
    """truncate large outputs to prevent context pollution"""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n[TRUNCATED - original length: {len(text)} chars]"
    return text

def prune_state(state: dict) -> dict:
    """remove large intermediate outputs to prevent context pollution"""
    pruned = {
        'cti_analysis': safe_json_parse(state, 'cti_analysis', {}),
        'ttp_mapping': safe_json_parse(state, 'ttp_mapping', {}),
        'detection_rules': safe_json_parse(state, 'detection_rules', {}),
        'test_payloads': safe_json_parse(state, 'test_payloads', {}),
        'quality_report': safe_json_parse(state, 'quality_report', {})
    }

    #truncate large text fields
    for key in pruned:
        if isinstance(pruned[key], str) and len(pruned[key]) > 50000:
            pruned[key] = pruned[key][:50000] + "\n[TRUNCATED]"

    return pruned

def save_session_results(state: dict, output_dir: str = "session_results"):
    """save session results with quality report"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = output_path / f"detection_session_{timestamp}.json"

    #prune state before saving
    pruned_state = prune_state(state)

    with open(session_file, 'w') as f:
        json.dump(pruned_state, f, indent=2)

    print(f"\nSession results saved to: {session_file}")
    return session_file

#================================
# Load External Prompts
#================================

def load_prompt(prompt_name: str) -> str:
    """load external prompt from prompts/ directory"""
    prompt_path = Path(__file__).parent / 'prompts' / prompt_name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text()

#load all prompts
CTI_ANALYZER_PROMPT = load_prompt('cti_analyzer_prompt.md')
TTP_MAPPER_PROMPT = load_prompt('ttp_mapper_prompt.md')
SIGMA_GENERATOR_PROMPT = load_prompt('sigma_generator_prompt.md')
SIGMA_FORMATTER_PROMPT = load_prompt('sigma_formatter_prompt.md')

#================================
# Agent Definitions
#================================

# ------ CTI Analysis Workflow Agents ------

cti_analyzer_agent = Agent(
    model='gemini-2.5-pro',
    name='cti_analyzer',
    instruction=CTI_ANALYZER_PROMPT,
    output_schema=CTIAnalysisOutput,
    generate_content_config=GenerateContentConfig(http_options=AGGRESSIVE_RETRY_CONFIG)
)

ttp_mapper_agent = Agent(
    model='gemini-2.5-pro',
    name='ttp_mapper',
    instruction=TTP_MAPPER_PROMPT,
    output_schema=TTPMappingOutput,
    generate_content_config=GenerateContentConfig(http_options=AGGRESSIVE_RETRY_CONFIG)
)

# ------ Sigma Generation Workflow Agents ------

sigma_generator_agent = Agent(
    model='gemini-2.5-pro',
    name='sigma_generator',
    instruction=SIGMA_GENERATOR_PROMPT,
    output_schema=SigmaRuleOutput,
    generate_content_config=GenerateContentConfig(http_options=AGGRESSIVE_RETRY_CONFIG)
)

sigma_formatter_agent = Agent(
    model='gemini-2.5-flash',
    name='sigma_formatter',
    instruction=SIGMA_FORMATTER_PROMPT,
    output_schema=SigmaRuleOutput,
    generate_content_config=GenerateContentConfig(http_options=FLASH_RETRY_CONFIG)
)

# ------ Test Generation Workflow Agents ------

payload_generator_agent = Agent(
    model='gemini-2.5-pro',
    name='payload_generator',
    instruction="""
    You are a security testing expert specializing in GCP audit logs.

    Generate test payloads for each Sigma rule:
    - True Positives (TP): malicious activity that should alert
    - False Negatives (FN): evasion techniques that bypass detection
    - False Positives (FP): benign activity that might false alarm
    - True Negatives (TN): normal activity that shouldn't alert

    Output as TestPayloadSet schema.
    """,
    output_schema=TestPayloadSet,
    generate_content_config=GenerateContentConfig(http_options=AGGRESSIVE_RETRY_CONFIG)
)

payload_formatter_agent = Agent(
    model='gemini-2.5-flash',
    name='payload_formatter',
    instruction="""
    You are a JSON formatting expert.

    Format test payloads as valid JSON matching GCP audit log structure.
    Ensure all required fields are present.

    Output as TestPayloadSet schema.
    """,
    output_schema=TestPayloadSet,
    generate_content_config=GenerateContentConfig(http_options=FLASH_RETRY_CONFIG)
)

test_validator_agent = Agent(
    model='gemini-2.5-flash',
    name='test_validator',
    instruction="""
    You are a GCP audit log schema validation expert.

    Validate test payloads match actual GCP audit log schema.
    Check for required fields, correct data types, realistic values.

    Output as TestValidationOutput schema.
    """,
    output_schema=TestValidationOutput,
    generate_content_config=GenerateContentConfig(http_options=FLASH_RETRY_CONFIG)
)

# ------ Deployment Workflow Agents ------

cicd_generator_agent = Agent(
    model='gemini-2.5-flash',
    name='cicd_generator',
    instruction="""
    You are a GitHub Actions CI/CD expert.

    Generate GitHub Actions workflow YAML for detection testing and deployment.
    Include unit tests, integration tests, and deployment steps.
    """,
    generate_content_config=GenerateContentConfig(http_options=FLASH_RETRY_CONFIG)
)

llm_judge_agent = Agent(
    model='gemini-2.5-pro',
    name='llm_judge',
    instruction="""
    You are a detection engineering quality expert.

    Evaluate detection rules based on ACTUAL test results from ELK integration tests.

    Score based on:
    - TTP alignment (does rule detect the mapped technique)
    - Test coverage (are edge cases covered)
    - False positive risk (based on actual FP count)
    - Evasion resistance (did FN tests reveal weaknesses)
    - Empirical metrics (precision ≥ 0.80, recall ≥ 0.70)

    Output as DetectionQualityReport schema.
    """,
    output_schema=DetectionQualityReport,
    generate_content_config=GenerateContentConfig(http_options=AGGRESSIVE_RETRY_CONFIG)
)

#================================
# Sequential Workflows
#================================

cti_analysis_workflow = SequentialAgent(
    name='cti_analysis_workflow',
    sub_agents=[
        cti_analyzer_agent,
        ttp_mapper_agent
    ]
)

sigma_generation_workflow = SequentialAgent(
    name='sigma_generation_workflow',
    sub_agents=[
        sigma_generator_agent,
        sigma_formatter_agent
    ]
)

test_generation_workflow = SequentialAgent(
    name='test_generation_workflow',
    sub_agents=[
        payload_generator_agent,
        payload_formatter_agent,
        test_validator_agent
    ]
)

deployment_workflow = SequentialAgent(
    name='deployment_workflow',
    sub_agents=[
        cicd_generator_agent,
        llm_judge_agent
    ]
)

#================================
# Root Agent
#================================

root_agent = SequentialAgent(
    name='sigma_detection_root',
    sub_agents=[
        cti_analysis_workflow,
        sigma_generation_workflow,
        test_generation_workflow,
        deployment_workflow
    ]
)

#================================
# Main Execution
#================================

async def run_sigma_detection_agent(
    cti_folder: str = "cti_src",
    output_dir: str = "generated",
    max_retries: int = 3
):
    """
    main execution function for sigma detection agent

    Args:
        cti_folder: path to CTI files
        output_dir: where to save generated rules
        max_retries: session retry attempts
    """

    #load CTI files
    print(f"Loading CTI files from: {cti_folder}")
    cti_data = load_cti_files(cti_folder)

    if cti_data['files_loaded'] == 0:
        print(f"ERROR: No CTI files loaded from {cti_folder}")
        return None

    print(f"Loaded {cti_data['files_loaded']} CTI files")
    print(cti_data['text_content'][:500])  #preview

    #initial state
    initial_state = {
        'cti_content': cti_data['text_content'],
        'cti_files_loaded': cti_data['files_loaded'],
        'output_dir': output_dir
    }

    #session retry loop (handles quota exhaustion)
    for attempt in range(max_retries):
        try:
            print(f"\nStarting detection generation (attempt {attempt + 1}/{max_retries})...")

            runner = InMemoryRunner(agent=root_agent, app_name='sigma-detection-agent')

            #use run_debug for simpler execution
            query = f"""Analyze the following CTI content and generate Sigma detection rules:

{cti_data['text_content']}

Output directory: {output_dir}
"""

            print("\n" + "="*80)
            print("Running ADK Agent Pipeline with run_debug...")
            print("="*80)

            response = await runner.run_debug(
                query,
                verbose=True
            )

            #extract response content
            if hasattr(response, 'text'):
                result_text = response.text
            elif hasattr(response, 'content'):
                result_text = str(response.content)
            else:
                result_text = str(response)

            #update state with response
            initial_state['agent_response'] = result_text

            #success - save results
            print("\n✓ Detection generation complete!")
            session_file = save_session_results(initial_state, "session_results")

            return {
                'success': True,
                'state': initial_state,
                'response': result_text,
                'session_file': str(session_file)
            }

        except Exception as e:
            error_type = type(e).__name__

            #check if quota exhausted
            if 'ResourceExhausted' in error_type or '429' in str(e):
                if attempt == max_retries - 1:
                    print(f"\n✗ Failed after {max_retries} attempts: {e}")
                    raise

                #exponential backoff
                delay = min(20.0 * (2 ** attempt), 120.0)  #20s, 40s, 80s max
                jitter = random.uniform(0, delay * 0.1)
                wait_time = delay + jitter

                print(f"\n⚠ Rate limited: {e}")
                print(f"Retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
            else:
                #other error - fail immediately
                print(f"\n✗ Unexpected error: {e}")
                raise

    #should not reach here
    return None

#================================
# CLI Entry Point (for testing)
#================================

async def main():
    """test entry point"""
    result = await run_sigma_detection_agent(
        cti_folder="cti_src",
        output_dir="generated"
    )

    if result and result['success']:
        print("\n✓ Success!")
        print(f"Session file: {result['session_file']}")
    else:
        print("\n✗ Failed")

if __name__ == '__main__':
    asyncio.run(main())
