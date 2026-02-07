#!/bin/bash
#setup-github-secrets.sh - configure GitHub secrets for CI/CD
#
#what this does:
# 1. reads service account key from ~/sigma-detection-sa-key.json
# 2. sets GCP_SA_KEY secret (base64 encoded)
# 3. sets GCP_PROJECT_ID secret
# 4. validates secrets are configured
#
#prerequisites:
# - gh CLI installed and authenticated
# - ran ./scripts/setup-gcp.sh first
#
#usage:
#   chmod +x scripts/setup-github-secrets.sh
#   ./scripts/setup-github-secrets.sh

set -e

echo "================================"
echo "GitHub Secrets Setup"
echo "================================"
echo ""

#check prerequisites
if ! command -v gh &> /dev/null; then
    echo "ERROR: gh CLI not found"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

echo "✓ gh CLI found"

#check authentication
echo ""
echo "Checking GitHub authentication..."
if ! gh auth status &> /dev/null; then
    echo "Not authenticated. Running gh auth login..."
    gh auth login
fi

echo "✓ Authenticated to GitHub"

#check for service account key (interactive path)
echo ""
echo "Locating service account key..."

#default location
DEFAULT_KEY_FILE="$HOME/sigma-detection-sa-key.json"

if [ -f "$DEFAULT_KEY_FILE" ]; then
    echo "Found key at default location: $DEFAULT_KEY_FILE"
    read -p "Use this key? (y/n): " USE_DEFAULT

    if [ "$USE_DEFAULT" = "y" ]; then
        KEY_FILE="$DEFAULT_KEY_FILE"
    else
        read -p "Enter path to service account key JSON: " KEY_FILE
    fi
else
    echo "No key found at default location: $DEFAULT_KEY_FILE"
    read -p "Enter path to service account key JSON: " KEY_FILE
fi

#validate key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "ERROR: Key file not found: $KEY_FILE"
    echo ""
    echo "Options:"
    echo "  1. Run ./scripts/setup-gcp.sh to create key"
    echo "  2. Provide correct path to existing key"
    exit 1
fi

#validate it's valid JSON
if ! cat "$KEY_FILE" | python3 -m json.tool > /dev/null 2>&1; then
    echo "ERROR: Invalid JSON in key file: $KEY_FILE"
    exit 1
fi

echo "✓ Found service account key: $KEY_FILE"

#extract project ID from key file
PROJECT_ID=$(cat "$KEY_FILE" | grep -o '"project_id": "[^"]*' | cut -d'"' -f4)

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: Could not extract project_id from $KEY_FILE"
    exit 1
fi

echo "✓ Project ID: $PROJECT_ID"

#get repo (interactive with auto-detection)
echo ""
echo "Detecting GitHub repository..."
DETECTED_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")

if [ -n "$DETECTED_REPO" ]; then
    echo "Detected repository: $DETECTED_REPO"
    read -p "Use this repository? (y/n): " USE_DETECTED

    if [ "$USE_DETECTED" = "y" ]; then
        REPO="$DETECTED_REPO"
    else
        read -p "Enter repository (format: owner/repo): " REPO
    fi
else
    echo "No repository auto-detected"
    read -p "Enter repository (format: owner/repo): " REPO
fi

#validate repo format
if [[ ! "$REPO" =~ ^[^/]+/[^/]+$ ]]; then
    echo "ERROR: Invalid repository format. Use: owner/repo"
    echo "Example: anthropics/sigma-detection-agent"
    exit 1
fi

echo "✓ Repository: $REPO"

#confirm setup
echo ""
echo "Will configure secrets for: $REPO"
echo "  GCP_SA_KEY: <service account JSON>"
echo "  GCP_PROJECT_ID: $PROJECT_ID"
echo ""
read -p "Continue? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ]; then
    echo "Exiting..."
    exit 0
fi

#set GCP_SA_KEY secret
echo ""
echo "Setting GCP_SA_KEY secret..."

#read key file and set as secret
cat "$KEY_FILE" | gh secret set GCP_SA_KEY --repo="$REPO"

echo "✓ GCP_SA_KEY secret set"

#set GCP_PROJECT_ID secret
echo ""
echo "Setting GCP_PROJECT_ID secret..."

echo "$PROJECT_ID" | gh secret set GCP_PROJECT_ID --repo="$REPO"

echo "✓ GCP_PROJECT_ID secret set"

#validate secrets are set
echo ""
echo "Validating secrets..."

SECRETS=$(gh secret list --repo="$REPO" --json name -q '.[].name')

if echo "$SECRETS" | grep -q "GCP_SA_KEY"; then
    echo "  ✓ GCP_SA_KEY configured"
else
    echo "  ✗ GCP_SA_KEY not found"
fi

if echo "$SECRETS" | grep -q "GCP_PROJECT_ID"; then
    echo "  ✓ GCP_PROJECT_ID configured"
else
    echo "  ✗ GCP_PROJECT_ID not found"
fi

#summary
echo ""
echo "================================"
echo "GitHub Secrets Setup Complete!"
echo "================================"
echo ""
echo "Repository: $REPO"
echo "Secrets configured:"
echo "  - GCP_SA_KEY"
echo "  - GCP_PROJECT_ID"
echo ""
echo "Next steps:"
echo "  1. Create .env for local dev: cp .env.example .env"
echo "  2. Update .env with project ID: $PROJECT_ID"
echo "  3. Run validation: ./scripts/validate-setup.sh"
echo "  4. Test workflow: gh workflow run test-cti-loading.yml"
echo ""
echo "View secrets: gh secret list --repo=$REPO"
