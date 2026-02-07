# CI/CD Setup Guide

## Overview

This document explains how to set up and run the automated detection testing pipeline in GitHub Actions.

## Prerequisites

1. GitHub repository for this project
2. Google AI API key (for LLM judge - Phase 5)
3. Docker Desktop (for local testing - optional)

## GitHub Actions Workflows

### 1. Test Detection Rules (`.github/workflows/test-detections.yml`)

**Triggers:**
- Push to `main` branch (paths: `generated/**`, `scripts/**`)
- Pull request (paths: `generated/**`, `scripts/**`)
- Manual dispatch (`workflow_dispatch`)

**Jobs:**

#### Job 1: Unit Test
- Validates Sigma YAML syntax
- Checks Elasticsearch query compatibility
- Validates test payload JSON structure

**Tools:** pySigma, PyYAML

#### Job 2: Integration Test
- Deploys ephemeral Elasticsearch (GitHub Actions service)
- Converts Sigma → Elasticsearch queries
- Ingests 52 test payloads
- Runs detection queries
- Calculates TP/FP/TN/FN metrics
- Generates precision/recall/F1 scores

**Tools:** Elasticsearch 8.12.0, pySigma, Python

#### Job 3: Quality Gate
- Downloads integration test results
- Checks quality thresholds:
  - F1 Score ≥ 0.75 → PASS
  - F1 Score ≥ 0.60 → CONDITIONAL
  - F1 Score < 0.60 → FAIL

**Outcome:** Pass/fail status for deployment readiness

## GitHub Secrets Required

None required for integration testing (uses ephemeral Elasticsearch).

For Phase 5 (LLM Judge), you'll need:
- `GOOGLE_API_KEY` - Google AI API key for Gemini evaluation

## Running Tests Locally

### Option 1: Mock Integration Test (No Docker)

```bash
# Fast simulation without Docker
python scripts/integration_test_mock.py \
  --rules generated/sigma_rules \
  --tests generated/tests

# Output: generated/INTEGRATION_TEST_RESULTS.json
```

**Use case:** Quick validation, Docker unavailable

### Option 2: Real Integration Test (Docker)

```bash
# Start Elasticsearch container and run real tests
python scripts/integration_test_elk.py \
  --rules generated/sigma_rules \
  --tests generated/tests

# Automatically starts/stops Docker container
# Output: generated/INTEGRATION_TEST_RESULTS.json
```

**Use case:** Production-like validation

### Option 3: CI Integration Test (Pre-existing ES)

```bash
# Start Elasticsearch separately
docker run -d \
  --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms256m -Xmx256m" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0

# Run CI test script (assumes ES is already running)
python scripts/integration_test_ci.py \
  --rules generated/sigma_rules \
  --tests generated/tests \
  --es-url http://localhost:9200

# Cleanup
docker stop elasticsearch
docker rm elasticsearch
```

**Use case:** Testing GitHub Actions behavior locally

## Testing the GitHub Actions Workflow

### Step 1: Initialize Git Repository

```bash
cd adk-tide-generator

# Initialize if not already done
git init
git branch -M main
```

### Step 2: Create GitHub Repository

```bash
# Create repository on GitHub (via gh CLI)
gh repo create adk-tide-generator --public --source=. --remote=origin

# Or create manually at https://github.com/new
# Then add remote:
git remote add origin https://github.com/YOUR_USERNAME/adk-tide-generator.git
```

### Step 3: Commit and Push

```bash
# Stage all files
git add .

# Commit
git commit -m "Initial commit: Automated SIEM detection generation pipeline

- Phase 1: CTI analysis and TTP mapping
- Phase 2: Sigma rule generation (13 rules)
- Phase 3: Test payload generation (52 payloads)
- Phase 4: Integration testing with Elasticsearch
- GitHub Actions CI/CD for automated testing"

# Push to GitHub
git push -u origin main
```

### Step 4: Monitor Workflow Execution

```bash
# Watch workflow execution
gh run watch

# Or view on GitHub:
# https://github.com/YOUR_USERNAME/adk-tide-generator/actions
```

### Step 5: View Test Results

**In GitHub Actions Logs:**
1. Go to Actions tab
2. Click on latest workflow run
3. View "Integration Test with Elasticsearch" job
4. Expand step "Run Integration Tests" to see detailed output

**Download Artifacts:**
```bash
# List artifacts
gh run list --limit 1

# Download test results
gh run download --name integration-test-results
```

## Workflow Debugging

### Common Issues

#### Issue 1: Elasticsearch Service Not Ready

**Symptom:** `Elasticsearch not ready after 120s`

**Solution:**
- GitHub Actions health checks already configured
- Script waits up to 60s for ES to become ready
- If still fails, increase `health-retries` in workflow YAML

#### Issue 2: Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'pysigma'`

**Solution:**
- Check "Install Dependencies" step in workflow
- Ensure pip install runs before test script
- Verify requirements.txt is committed

#### Issue 3: Test Results Not Found

**Symptom:** `No test results file found`

**Solution:**
- Check integration test script completed successfully
- Verify `generated/` directory is committed
- Ensure test script writes to correct path

### Viewing Elasticsearch Logs (Local Debugging)

```bash
# View ES container logs
docker logs elasticsearch

# Follow logs in real-time
docker logs -f elasticsearch

# Check ES health
curl http://localhost:9200/_cluster/health?pretty
```

## Pull Request Workflow

When you create a PR that modifies rules or tests:

1. **Automatic Testing:** Workflow runs automatically
2. **Comment with Results:** Bot comments on PR with test metrics
3. **Quality Gate:** Checks if F1 score meets thresholds
4. **Review:** Human reviews PR + test results
5. **Merge:** Approved PRs trigger deployment (Phase 5+)

### Example PR Comment

```markdown
## Integration Test Results

**Overall Metrics:**
- Rules Tested: 13
- High-Quality Rules (F1 ≥ 0.90): 7 (53.8%)

**Detection Performance:**
- True Positives: 11
- False Positives: 8
- True Negatives: 31
- False Negatives: 2

**Quality Metrics:**
- Precision: 0.64
- Recall: 0.85
- F1 Score: 0.69

⚠️ **Quality CONDITIONAL** - Review needed before deployment

<details>
<summary>Per-Rule Results</summary>

| Rule | Level | TP | FP | TN | FN | Precision | Recall | F1 |
|------|-------|----|----|----|----|-----------|--------|------|
| GCP Service Account Impersonation | HIGH | 1 | 0 | 3 | 0 | 1.00 | 1.00 | 1.00 |
...

</details>
```

## Manual Workflow Triggers

### Trigger test-detections workflow manually:

```bash
# Via gh CLI
gh workflow run test-detections.yml

# Or via GitHub UI:
# Actions → Test Detection Rules → Run workflow
```

## Monitoring and Alerts

### GitHub Actions Notifications

- **Email:** Enabled by default for workflow failures
- **Slack:** Configure via GitHub Actions marketplace
- **Webhook:** Configure in repository settings

### Quality Metrics Tracking

Track metrics over time:

```bash
# Download all test results
mkdir -p metrics_history
gh run list --workflow=test-detections.yml --json conclusion,createdAt,databaseId | \
  jq -r '.[] | select(.conclusion == "success") | .databaseId' | \
  while read run_id; do
    gh run download $run_id --name integration-test-results --dir metrics_history/$run_id
  done

# Analyze trends
python scripts/analyze_metrics_trends.py metrics_history/
```

## Cost Optimization

### GitHub Actions Minutes

**Free tier:** 2,000 minutes/month
**Pro tier:** 3,000 minutes/month

**Estimated usage per test run:**
- Unit test: ~2 minutes
- Integration test: ~5 minutes
- Total: ~7 minutes per run

**Monthly estimate (10 runs/week):**
- ~40 runs/month × 7 minutes = 280 minutes/month
- Well within free tier limits

### Elasticsearch Resource Usage

**GitHub Actions service limits:**
- Memory: 256MB-512MB (configured in workflow)
- CPU: Shared runner resources
- No persistent storage (ephemeral)

**Optimization:**
- Container auto-destroyed after test
- No ongoing costs
- No persistent cloud infrastructure

## Next Steps

### Phase 5: LLM Judge Evaluation

After integration testing passes, run LLM judge:

```bash
# Set API key
export GOOGLE_API_KEY="your-api-key-here"

# Run LLM judge
python scripts/run_llm_judge.py \
  --rules generated/sigma_rules \
  --tests generated/tests \
  --results generated/INTEGRATION_TEST_RESULTS.json \
  --output generated/QUALITY_REPORT.json

# View quality report
cat generated/QUALITY_REPORT.json | jq '.summary'
```

### Phase 6: Production Deployment

Rules that pass LLM judge evaluation (quality ≥ 0.75) can be:

1. **Staged for Review:** Move to `staged_rules/` directory
2. **Human Approval:** Create PR for security team review
3. **SIEM Deployment:** Convert Sigma → SIEM-specific format:
   - Elasticsearch: Already compatible (Lucene queries)
   - Splunk: Use pySigma Splunk backend
   - Chronicle: Use pySigma Chronicle backend (YARA-L 2.0)
   - Sentinel: Use pySigma Sentinel backend (KQL)

## Reference

- **Integration Test Output:** `generated/INTEGRATION_TEST_RESULTS.json`
- **Quality Report:** `generated/QUALITY_REPORT.json` (Phase 5)
- **Workflow Logs:** GitHub Actions → Test Detection Rules
- **Sigma Specification:** https://github.com/SigmaHQ/sigma-specification
- **pySigma Documentation:** https://sigmahq-pysigma.readthedocs.io/

---

**Last Updated:** 2026-02-07
**Pipeline:** adk-tide-generator (Automated TIDE Generation with ADK)
