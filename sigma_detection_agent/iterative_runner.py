"""
Iterative agent runner with self-refinement and progress tracking

Each agent iterates 2-3 times on its own output before moving to next stage.
Progress bars show status in CI/CD environments.
"""

import asyncio
import json
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table

from google.adk.runners import InMemoryRunner
from google.genai import types

from sigma_detection_agent.agent import (
    cti_analyzer_agent,
    ttp_mapper_agent,
    sigma_generator_agent,
    sigma_formatter_agent,
    load_cti_files
)

console = Console()

#iteration config
CTI_ANALYSIS_ITERATIONS = 2  #refine CTI analysis 2 times
TTP_MAPPING_ITERATIONS = 2   #refine TTP mapping 2 times
SIGMA_GENERATION_ITERATIONS = 3  #refine Sigma rules 3 times

#context management
MAX_REFINEMENT_CHARS = 50000  #truncate outputs before refinement to save tokens
MAX_STATE_OUTPUT_CHARS = 100000  #max size for intermediate state storage

def extract_json_from_event(output: str) -> str:
    """extract JSON from ADK Event wrapper if present"""
    if not isinstance(output, str):
        return str(output)

    #check if wrapped in Event object - extract JSON content
    if 'Event(' in output and 'text=' in output:
        #try triple-quote format first: text="""..."""
        match = re.search(r'text="""(.+?)"""', output, re.DOTALL)
        if match:
            return match.group(1)
        #try single-quote format: text="..."
        match = re.search(r'text="(.+?)"', output, re.DOTALL)
        if match:
            return match.group(1)

    #if no Event wrapper found, return as-is
    return output

def truncate_for_refinement(text: str, max_chars: int = MAX_REFINEMENT_CHARS) -> str:
    """truncate large outputs to reduce token usage in refinement iterations"""
    if len(text) <= max_chars:
        return text

    #truncate but keep structure info
    truncated = text[:max_chars]
    char_count = len(text)
    token_estimate = char_count // 4

    return f"""{truncated}

[TRUNCATED - Original length: {char_count:,} chars (~{token_estimate:,} tokens)]
[Showing first {max_chars:,} chars for refinement context]"""

def prune_state_for_storage(state: Dict[str, Any]) -> Dict[str, Any]:
    """prune state to prevent context pollution between stages"""
    pruned = {}

    for key, value in state.items():
        if isinstance(value, str):
            #truncate large text fields
            if len(value) > MAX_STATE_OUTPUT_CHARS:
                char_count = len(value)
                token_estimate = char_count // 4
                pruned[key] = value[:MAX_STATE_OUTPUT_CHARS] + f"\n\n[TRUNCATED - {char_count:,} chars / ~{token_estimate:,} tokens]"
            else:
                pruned[key] = value
        else:
            pruned[key] = value

    return pruned

async def run_agent_with_iteration(
    agent,
    query: str,
    iterations: int,
    agent_name: str,
    progress: Progress,
    task_id
) -> str:
    """
    Run agent iteratively, refining output each time

    Args:
        agent: ADK agent to run
        query: Initial query
        iterations: Number of refinement iterations
        agent_name: Name for logging
        progress: Rich progress tracker
        task_id: Progress task ID

    Returns:
        Final refined output
    """
    runner = InMemoryRunner(agent=agent, app_name=f'{agent_name}-runner')

    current_query = query
    output = None

    for iteration in range(iterations):
        progress.update(task_id, description=f"[cyan]{agent_name}[/cyan] - Iteration {iteration + 1}/{iterations}")

        try:
            response = await runner.run_debug(current_query, verbose=False)

            #extract response
            if hasattr(response, 'text'):
                output = response.text
            elif hasattr(response, 'content'):
                output = str(response.content)
            else:
                output = str(response)

            #for next iteration, ask agent to refine (truncate to save tokens)
            if iteration < iterations - 1:
                truncated_output = truncate_for_refinement(output)
                current_query = f"""Review and refine your previous output:

{truncated_output}

INSTRUCTIONS:
1. Identify any gaps, errors, or areas for improvement
2. Add missing details or context
3. Improve clarity and accuracy
4. Output the REFINED version (not a critique)

Provide your improved output now:"""

            progress.update(task_id, advance=1)

        except Exception as e:
            console.print(f"[red]Error in {agent_name} iteration {iteration + 1}: {e}[/red]")
            if output is None:
                raise  #fail if no output at all
            break  #use last good output

    return output

async def run_iterative_pipeline(cti_folder: str, output_dir: str) -> Dict[str, Any]:
    """
    Run full detection pipeline with iterative refinement

    Each stage iterates 2-3 times before moving forward.
    Shows progress in CI/CD-friendly format.
    """
    console.print(Panel.fit(
        "[bold cyan]Sigma Detection Agent - Iterative Pipeline[/bold cyan]\n"
        "Each agent refines its output 2-3 times for quality",
        border_style="cyan"
    ))

    #load CTI files
    console.print("\n[yellow]Loading CTI files...[/yellow]")
    cti_data = load_cti_files(cti_folder)

    if cti_data['files_loaded'] == 0:
        console.print(f"[red]ERROR: No CTI files loaded from {cti_folder}[/red]")
        return {'success': False, 'error': 'No CTI files'}

    #show CTI summary
    cti_table = Table(title="CTI Files Loaded")
    cti_table.add_column("Metric", style="cyan")
    cti_table.add_column("Value", style="green")
    cti_table.add_row("Files Loaded", str(cti_data['files_loaded']))
    cti_table.add_row("Total Tokens (approx)", f"~{len(cti_data['text_content']) // 4:,}")
    console.print(cti_table)

    #initialize state
    state = {
        'cti_content': cti_data['text_content'],
        'timestamp': datetime.now().isoformat()
    }

    #progress tracker
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:

        # === STAGE 1: CTI Analysis (2 iterations) ===
        task1 = progress.add_task(
            "[cyan]CTI Analysis[/cyan]",
            total=CTI_ANALYSIS_ITERATIONS
        )

        cti_query = f"""Analyze the following CTI intelligence files and extract structured threat information:

{cti_data['text_content']}

Extract and structure:
- Threat actors, groups, aliases
- Attack objectives and motivations
- Attack vectors and initial access methods
- TTPs (techniques, tactics, procedures) - in plain language
- Target platforms, services, and APIs (cloud, on-prem, endpoints, etc.)
- Key indicators of compromise (IOCs)
- Research references and documentation links

Output as structured CTIAnalysisOutput JSON."""

        cti_analysis_output = await run_agent_with_iteration(
            cti_analyzer_agent,
            cti_query,
            CTI_ANALYSIS_ITERATIONS,
            "CTI Analyzer",
            progress,
            task1
        )

        state['cti_analysis'] = cti_analysis_output
        console.print("[green]✓ CTI Analysis complete[/green]")

        # === STAGE 2: TTP Mapping (2 iterations) ===
        task2 = progress.add_task(
            "[cyan]TTP Mapping[/cyan]",
            total=TTP_MAPPING_ITERATIONS
        )

        #truncate CTI analysis for next stage to save tokens
        cti_for_ttp = truncate_for_refinement(cti_analysis_output, max_chars=30000)

        ttp_query = f"""Based on the CTI analysis, map extracted TTPs to MITRE ATT&CK framework:

CTI Analysis:
{cti_for_ttp}

Map each TTP to:
- Exact MITRE ATT&CK technique ID (e.g., T1550.001)
- Tactic name
- Platform-specific manifestation and context (based on CTI target environment)
- Detectability and priority (HIGH/MEDIUM/LOW)
- Evidence from CTI supporting this mapping

Output as structured TTPMappingOutput JSON."""

        ttp_mapping_output = await run_agent_with_iteration(
            ttp_mapper_agent,
            ttp_query,
            TTP_MAPPING_ITERATIONS,
            "TTP Mapper",
            progress,
            task2
        )

        state['ttp_mapping'] = ttp_mapping_output
        console.print("[green]✓ TTP Mapping complete[/green]")

        # === STAGE 3: Sigma Generation (3 iterations) ===
        task3 = progress.add_task(
            "[cyan]Sigma Rule Generation[/cyan]",
            total=SIGMA_GENERATION_ITERATIONS
        )

        #truncate TTP mapping for Sigma generation (keep full context)
        ttp_for_sigma = truncate_for_refinement(ttp_mapping_output, max_chars=40000)

        sigma_query = f"""Generate production-ready Sigma detection rules for the mapped TTPs:

TTP Mapping:
{ttp_for_sigma}

Original CTI Context:
{cti_data['text_content'][:10000]}...

Generate Sigma rules that:
1. Accurately detect each mapped TTP in the target environment from CTI
2. Use correct log field names for the identified log source (cloud audit, OS events, app logs, etc.)
3. Include robust false positive filtering
4. Provide comprehensive test scenarios (TP/FN/FP/TN)
5. Follow Sigma YAML specification exactly

Output as structured SigmaRuleOutput JSON with complete YAML rules."""

        sigma_rules_output = await run_agent_with_iteration(
            sigma_generator_agent,
            sigma_query,
            SIGMA_GENERATION_ITERATIONS,
            "Sigma Generator",
            progress,
            task3
        )

        state['sigma_rules'] = sigma_rules_output
        console.print("[green]✓ Sigma Rules generated[/green]")

        # === STAGE 4: YAML Formatting (1 iteration) ===
        task4 = progress.add_task(
            "[cyan]YAML Formatting[/cyan]",
            total=1
        )

        #truncate sigma rules for formatting stage (keep most of it)
        sigma_for_format = truncate_for_refinement(sigma_rules_output, max_chars=60000)

        format_query = f"""Validate and format the Sigma rules for correct YAML syntax:

Generated Rules:
{sigma_for_format}

Ensure:
1. Valid YAML syntax (proper indentation, quotes, escaping)
2. All required Sigma fields present
3. Log field names match the logsource specification
4. No syntax errors

Output as structured SigmaRuleOutput JSON with validated YAML."""

        formatted_output = await run_agent_with_iteration(
            sigma_formatter_agent,
            format_query,
            1,
            "YAML Formatter",
            progress,
            task4
        )

        state['formatted_rules'] = formatted_output
        console.print("[green]✓ YAML Formatting complete[/green]")

    #save results (prune large outputs to reduce file size)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    #prune state to keep session file manageable
    pruned_state = prune_state_for_storage(state)

    session_file = output_path / f"iterative_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(session_file, 'w') as f:
        json.dump(pruned_state, f, indent=2)

    console.print(f"\n[green]✓ Session saved to: {session_file}[/green]")

    #parse and save Sigma rules as individual YAML files
    try:
        #extract JSON from ADK Event wrapper and parse
        clean_output = extract_json_from_event(formatted_output)
        rules_data = json.loads(clean_output) if isinstance(clean_output, str) else clean_output

        if not (isinstance(rules_data, dict) and 'rules' in rules_data):
            raise ValueError("No rules found in formatted output")

        #create sigma_rules directory
        sigma_dir = output_path / 'sigma_rules'
        sigma_dir.mkdir(exist_ok=True)

        #save each rule as .yml file
        for idx, rule in enumerate(rules_data['rules'], 1):
            #sanitize filename
            rule_id = rule.get('id', f'rule_{idx}')
            rule_title = rule.get('title', 'Untitled Rule')
            safe_title = "".join(c for c in rule_title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_').lower()[:50]

            #write YAML file
            rule_file = sigma_dir / f"{safe_title}_{rule_id[:8]}.yml"
            yaml_content = yaml.dump(rule, default_flow_style=False, sort_keys=False, allow_unicode=True)
            rule_file.write_text(yaml_content)

        #report success
        rule_count = len(rules_data['rules'])
        console.print(f"[green]✓ Saved {rule_count} Sigma rules to {sigma_dir}/[/green]")

        #show sample files
        sample_files = list(sigma_dir.glob('*.yml'))[:3]
        if sample_files:
            console.print("[cyan]Sample files:[/cyan]")
            for f in sample_files:
                console.print(f"  - {f.name}")
            if rule_count > 3:
                console.print(f"  ... and {rule_count - 3} more")

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        console.print(f"[yellow]⚠ Could not save Sigma rules as files: {e}[/yellow]")
        console.print("[yellow]  Rules are available in session JSON file[/yellow]")

    return {
        'success': True,
        'state': state,
        'session_file': str(session_file),
        'cti_files_loaded': cti_data['files_loaded']
    }
