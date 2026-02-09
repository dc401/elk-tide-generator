# Archived Workflows

This directory contains deprecated workflows that are no longer actively used.

## Archived Workflows

### llm-judge.yml
**Archived:** 2026-02-09
**Reason:** LLM judge functionality is now integrated directly in the main detection agent (`run_agent.py` and `detection_agent/agent.py`). The separate workflow is no longer needed.

**Functionality Moved To:**
- `detection_agent/agent.py` - Stage 3: LLM Judge evaluation
- `scripts/run_llm_judge.py` - Standalone LLM judge script (for manual testing)

**Replacement:** Use the `end-to-end-test.yml` master orchestration workflow which includes integrated LLM judge evaluation.

---

## Active Workflows (For Reference)

**Master Orchestration:**
- `end-to-end-test.yml` - Complete pipeline testing (generation → integration → TTP validation → summary)

**Component Workflows:**
- `generate-detections.yml` - Rule generation from CTI
- `integration-test-simple.yml` - Integration testing with Docker Elasticsearch
- `mock-deploy.yml` - Mock SIEM deployment on PR merge

**Utility Workflows:**
- `cleanup-stale-artifacts.yml` - Weekly artifact cleanup
