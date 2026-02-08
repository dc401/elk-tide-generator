# Generated Artifacts Directory

This directory contains agent-generated detection rules and test artifacts.

**Note:** Most artifacts are gitignored to keep the repo clean. They are generated fresh by the agent during each run.

## Directory Structure

```
generated/
├── detection_rules/          # Generated Elasticsearch detection rules (YAML)
│   └── *.yml                 # One file per detection rule
│
├── tests/                    # Test payloads for each rule
│   └── {rule_id}/            # Test directory per rule
│       ├── true_positive_*.json
│       ├── false_negative_*.json
│       ├── false_positive_*.json
│       └── true_negative_*.json
│
├── staging/                  # Temporary validation artifacts
│   ├── json/                 # YAML → JSON conversions
│   └── refinement/           # Refinement attempt history
│
├── production_rules/         # Human-approved rules ready for deployment
│   └── *.yml                 # Rules that passed all quality gates + human review
│
├── cti_context.yml           # CTI analysis from agent
├── REFINEMENT_REPORT.json    # Pipeline-level refinement results
└── STATIC_QUALITY_REPORT.json # Validation quality scores
```

## What's Tracked in Git

- ✅ `generated/README.md` (this file)
- ✅ `generated/production_rules/README.md`
- ❌ All generated artifacts (ignored via .gitignore)

## Workflow

1. **Generate Rules:** Agent reads CTI from `cti_src/` → creates rules in `detection_rules/`
2. **Validation:** `scripts/validate_rules.py` validates rules → saves results
3. **Integration Testing:** `scripts/integration_test_ci.py` tests against Elasticsearch
4. **LLM Judge:** `scripts/run_llm_judge.py` evaluates based on test results
5. **Human Review:** Approved rules move to `production_rules/`
6. **Deployment:** Rules from `production_rules/` deploy to SIEM

## Usage

### Generate New Rules
```bash
python run_agent.py --interactive
```

### Validate Generated Rules
```bash
python scripts/validate_rules.py \
  --rules-dir generated/detection_rules \
  --project YOUR_GCP_PROJECT
```

### Integration Test
```bash
python scripts/integration_test_ci.py \
  --rules-dir generated/detection_rules \
  --project YOUR_GCP_PROJECT
```

### LLM Judge Evaluation
```bash
python scripts/run_llm_judge.py \
  --rules-dir generated/detection_rules \
  --test-results integration_test_results.yml \
  --project YOUR_GCP_PROJECT
```

## Cleanup

To remove all generated artifacts:
```bash
./scripts/cleanup_staging.sh
```

Or manually:
```bash
rm -rf generated/detection_rules/*
rm -rf generated/tests/*
rm -rf generated/staging/*
rm -f generated/*.json generated/*.yml
```
