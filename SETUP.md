# Quick Setup Guide - Sigma Detection Agent

This guide provides a copy-paste bootstrap process to get the detection agent running in 15 minutes.

## Prerequisites

- macOS or Linux terminal
- GitHub account with repo admin access
- GCP account with billing enabled
- `gcloud` CLI installed ([install guide](https://cloud.google.com/sdk/docs/install))
- `gh` CLI installed ([install guide](https://cli.github.com/))

## What You'll Need to Provide

The scripts are **fully interactive** and will ask you for:

1. **GCP Project:**
   - Option to auto-generate project ID (e.g., `sigma-detection-a4b2c3`)
   - Or specify your own (e.g., `my-detection-project`)
   - Or use existing project

2. **GitHub Repository:**
   - Auto-detects current repo
   - Or you can specify: `owner/repo` format

3. **Service Account Key Location:**
   - Default: `~/sigma-detection-sa-key.json`
   - Or custom path you choose

See **[BOOTSTRAP_EXAMPLE.md](BOOTSTRAP_EXAMPLE.md)** for exact interactive prompts you'll see.

## Setup Steps

### Step 1: Fork/Clone Repository

```bash
#clone this repo
git clone <your-repo-url>
cd adk-tide-generator

#or if forking, use your fork URL
```

### Step 2: Run GCP Bootstrap Script

This script automates ALL GCP setup (project, APIs, service account, permissions):

```bash
#make script executable
chmod +x scripts/setup-gcp.sh

#run bootstrap (interactive - will prompt for project ID)
./scripts/setup-gcp.sh

#expected output:
# ✓ Created project
# ✓ Enabled APIs
# ✓ Created service account
# ✓ Granted permissions
# ✓ Downloaded key to ~/sigma-detection-sa-key.json
```

**What it does:**
- Creates GCP project (or uses existing)
- Enables Vertex AI and Generative AI APIs
- Creates service account with least-privilege permissions
- Downloads service account key to `~/sigma-detection-sa-key.json`
- Validates setup

### Step 3: Run GitHub Secrets Bootstrap Script

This script configures GitHub Secrets for CI/CD:

```bash
#authenticate to GitHub
gh auth login

#make script executable
chmod +x scripts/setup-github-secrets.sh

#run bootstrap (reads from GCP setup)
./scripts/setup-github-secrets.sh

#expected output:
# ✓ Set GCP_SA_KEY secret
# ✓ Set GCP_PROJECT_ID secret
# ✓ Secrets configured for CI/CD
```

**What it does:**
- Reads service account key from `~/sigma-detection-sa-key.json`
- Sets `GCP_SA_KEY` GitHub secret (base64 encoded JSON)
- Sets `GCP_PROJECT_ID` GitHub secret
- Validates secrets are set

### Step 4: Setup Local Development Environment

```bash
#create virtual environment
python3.11 -m venv venv
source venv/bin/activate

#install dependencies
pip install -r requirements.txt

#create .env file
cp .env.example .env

#edit .env with your values
nano .env
```

**Update .env:**
```bash
GOOGLE_CLOUD_PROJECT=your-actual-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/Users/yourname/sigma-detection-sa-key.json
GOOGLE_GENAI_USE_VERTEXAI=true
```

### Step 5: Validate Setup

```bash
#run validation script
./scripts/validate-setup.sh

#expected output:
# ✓ GCP project exists
# ✓ APIs enabled
# ✓ Service account configured
# ✓ Local .env configured
# ✓ Python dependencies installed
# ✓ GitHub secrets set
# ✓ CTI folder exists
# ✓ All systems ready!
```

### Step 6: Test CTI Loading

```bash
#test with sample CTI file
python run_agent.py --test-cti

#expected output:
# Loading CTI files from: cti_src
# Loaded 1 CTI files (~XXX tokens)
# ✓ CTI loading successful!
# Phase 1 (Foundation) validation: PASSED
```

### Step 7: Push to GitHub and Test Workflow

```bash
#commit changes
git add .
git commit -m "Initial setup complete"
git push origin main

#trigger test workflow
gh workflow run test-cti-loading.yml

#watch workflow
gh run watch

#expected: workflow completes successfully
```

## Quick Reference

### Local Development

```bash
#activate venv
source venv/bin/activate

#test CTI loading
python run_agent.py --test-cti

#run agent (Phase 2+)
python run_agent.py --interactive
```

### GitHub Actions

```bash
#list workflows
gh workflow list

#trigger workflow
gh workflow run generate-detections.yml

#view runs
gh run list

#view specific run
gh run view RUN_ID
```

### GCP Management

```bash
#check quota
gcloud services list --enabled | grep aiplatform

#view audit logs
gcloud logging read "protoPayload.serviceName=aiplatform.googleapis.com" \
  --limit 10 \
  --format json

#rotate service account key (every 90 days)
./scripts/rotate-sa-key.sh
```

## Troubleshooting

### GCP Setup Fails

**Error:** "Project already exists"

**Fix:** Script will detect and use existing project. Just confirm when prompted.

**Error:** "Billing not enabled"

**Fix:**
```bash
#enable billing in GCP console
open "https://console.cloud.google.com/billing"
```

### GitHub Secrets Setup Fails

**Error:** "gh not authenticated"

**Fix:**
```bash
gh auth login
#follow prompts
```

**Error:** "Repository not found"

**Fix:**
```bash
#set correct repo
gh repo set-default USER/REPO
```

### Validation Fails

**Error:** "Service account key not found"

**Fix:**
```bash
#re-run GCP setup
./scripts/setup-gcp.sh

#verify key exists
ls -l ~/sigma-detection-sa-key.json
```

### Python Dependencies Fail

**Error:** "No module named 'google.genai'"

**Fix:**
```bash
#ensure venv activated
source venv/bin/activate

#reinstall
pip install -r requirements.txt --force-reinstall
```

## Architecture Decision: Why Scripts?

**Scripts automate:**
1. GCP project creation (5 min manual → 30s automated)
2. API enablement (3 min manual → 10s automated)
3. Service account setup (10 min manual → 30s automated)
4. GitHub secrets (5 min manual → 20s automated)

**Total time saved:** ~20 minutes per setup

**Idempotent:** Scripts can be run multiple times safely

## Next Steps After Setup

1. **Add your CTI files:**
   ```bash
   cp your-threat-intel.pdf cti_src/
   ```

2. **Review sample CTI:**
   ```bash
   cat cti_src/sample-gcp-threats.md
   ```

3. **Proceed to Phase 2:**
   - Create agent prompts
   - Implement Sigma generation
   - See RUNNING_NOTES.md for progress

## Support

- **Setup Issues:** Review troubleshooting section above
- **Script Errors:** Check script output and logs
- **GCP Errors:** Review GCP console audit logs
- **GitHub Errors:** Check Actions tab in GitHub

## Security Notes

- ✅ Service account keys stored locally only (`~/sigma-detection-sa-key.json`)
- ✅ GitHub secrets encrypted at rest
- ✅ `.env` file not committed to repo (in .gitignore)
- ✅ Least-privilege permissions (aiplatform.user, generativelanguage.user only)
- ⚠️ Rotate service account keys every 90 days (use `./scripts/rotate-sa-key.sh`)
