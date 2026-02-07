# GitHub Secrets Configuration for CI/CD

This document explains how to configure GitHub Secrets for automated detection generation workflows.

## Overview

**Local Development vs CI/CD:**

| Environment | Configuration Method | File/Location |
|-------------|---------------------|---------------|
| **Local Development** | `.env` file | Not committed to repo |
| **GitHub Actions** | GitHub Secrets | Injected as env vars |

## Required GitHub Secrets

### 1. GCP Service Account Key (Critical)

**Secret Name:** `GCP_SA_KEY`

**Value:** JSON content of your service account key file

**How to Set:**

```bash
#get your service account key content
cat ~/sigma-detection-sa-key.json | pbcopy  #macOS - copies to clipboard
#or
cat ~/sigma-detection-sa-key.json           #view content

#then add to GitHub:
#1. Go to your repo → Settings → Secrets and variables → Actions
#2. Click "New repository secret"
#3. Name: GCP_SA_KEY
#4. Value: Paste the entire JSON content
#5. Click "Add secret"
```

**⚠️ Security Notes:**
- Never commit this key to the repository
- Rotate keys periodically (every 90 days recommended)
- Use least-privilege permissions (aiplatform.user, generativelanguage.user only)
- Consider using Workload Identity Federation for enhanced security

### 2. GCP Project ID

**Secret Name:** `GCP_PROJECT_ID`

**Value:** Your GCP project ID (e.g., `my-detection-project`)

**How to Set:**

```bash
#find your project ID
gcloud config get-value project

#add to GitHub secrets as GCP_PROJECT_ID
```

### 3. GitHub Token (Optional)

**Secret Name:** `GITHUB_TOKEN`

**Value:** Automatically provided by GitHub Actions (no setup needed)

**Note:** GitHub automatically creates a `GITHUB_TOKEN` for each workflow run. You don't need to manually set this.

## GitHub Actions Workflow Configuration

In your workflow files (`.github/workflows/*.yml`), inject secrets as environment variables:

```yaml
name: Generate Detection Rules
on:
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Run Detection Agent
        env:
          GOOGLE_CLOUD_PROJECT: ${{ secrets.GCP_PROJECT_ID }}
          GOOGLE_CLOUD_LOCATION: us-central1
          GOOGLE_GENAI_USE_VERTEXAI: true
        run: |
          pip install -r requirements.txt
          python run_agent.py --cti-folder sigma_detection_agent/cti_src
```

## How It Works

1. **GitHub Actions workflow starts**
2. **google-github-actions/auth@v2** writes service account key to temp file
3. **Sets `GOOGLE_APPLICATION_CREDENTIALS`** env var automatically
4. **Your agent reads from environment variables** (not .env file)
5. **Authenticates to GCP** using credentials
6. **Workflow completes, temp files cleaned up**

## Local Development Setup

For local development, use `.env` file instead:

```bash
#copy example
cp .env.example .env

#edit with your values
nano .env

#agent automatically loads .env via python-dotenv
python run_agent.py --test-cti
```

## Verifying Secrets Are Set

```bash
#check if secrets are configured (doesn't show values)
gh secret list

#expected output:
# GCP_SA_KEY      Updated 2024-01-15
# GCP_PROJECT_ID  Updated 2024-01-15
```

## Security Best Practices

### 1. Principle of Least Privilege

Service account should have ONLY these roles:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sigma-detection-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sigma-detection-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/generativelanguage.user"
```

**Do NOT grant:**
- `roles/owner`
- `roles/editor`
- `roles/iam.serviceAccountKeyAdmin`

### 2. Key Rotation

```bash
#rotate service account keys every 90 days
#delete old key
gcloud iam service-accounts keys list \
  --iam-account=sigma-detection-agent@${PROJECT_ID}.iam.gserviceaccount.com

gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=sigma-detection-agent@${PROJECT_ID}.iam.gserviceaccount.com

#create new key
gcloud iam service-accounts keys create ~/new-key.json \
  --iam-account=sigma-detection-agent@${PROJECT_ID}.iam.gserviceaccount.com

#update GitHub secret with new key content
```

### 3. Environment Separation

Use separate GCP projects for different environments:

```yaml
#.github/workflows/generate-detections.yml
jobs:
  dev:
    env:
      GOOGLE_CLOUD_PROJECT: ${{ secrets.GCP_PROJECT_ID_DEV }}

  prod:
    env:
      GOOGLE_CLOUD_PROJECT: ${{ secrets.GCP_PROJECT_ID_PROD }}
```

### 4. Audit Logging

Enable GCP audit logs to track agent API usage:

```bash
#check audit logs
gcloud logging read "protoPayload.serviceName=aiplatform.googleapis.com" \
  --limit 50 \
  --format json
```

## Troubleshooting

### "Authentication failed" in GitHub Actions

**Cause:** Invalid or missing `GCP_SA_KEY` secret

**Fix:**
1. Verify secret exists: `gh secret list`
2. Check secret content is valid JSON
3. Ensure service account has correct permissions

### "Project not found"

**Cause:** Wrong `GCP_PROJECT_ID` or project doesn't exist

**Fix:**
```bash
#verify project exists
gcloud projects describe $PROJECT_ID

#update GitHub secret
gh secret set GCP_PROJECT_ID -b "correct-project-id"
```

### "Quota exceeded" in workflows

**Cause:** Hit Gemini API rate limits (2 RPM for Pro)

**Fix:**
- Agent has built-in exponential backoff
- Reduce CTI file count/size
- Stagger workflow runs (don't run concurrently)

## Advanced: Workload Identity Federation (Recommended)

Instead of service account keys, use Workload Identity Federation (keyless authentication):

```yaml
#.github/workflows/generate-detections.yml
- name: Authenticate to GCP
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github-provider'
    service_account: 'sigma-detection-agent@PROJECT_ID.iam.gserviceaccount.com'
```

**Benefits:**
- No service account keys to manage
- Automatic rotation
- Better security posture

**Setup Guide:** https://github.com/google-github-actions/auth#setup

## Quick Reference

| Secret | Required | Purpose |
|--------|----------|---------|
| `GCP_SA_KEY` | ✅ Yes | Service account JSON key |
| `GCP_PROJECT_ID` | ✅ Yes | GCP project ID |
| `GITHUB_TOKEN` | ❌ Auto | GitHub API access (auto-created) |

## Support

For issues:
- Check GitHub Actions logs: `https://github.com/USER/REPO/actions`
- Review troubleshooting section above
- Verify secrets are set: `gh secret list`
