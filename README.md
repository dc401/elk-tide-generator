# Sigma Detection Agent - Automated SIEM Detection Engineering

Production-ready automated detection engineering solution that converts CTI intelligence → TTP-based Sigma detection rules with comprehensive testing and validation.

## Features

- **Universal Sigma Format:** Detection rules work with any SIEM (ELK, Splunk, Chronicle, Sentinel, QRadar)
- **Automated Testing:** Unit tests (pySigma) + integration tests (ephemeral ELK)
- **LLM Quality Judge:** Empirical evaluation based on actual test results
- **Human-in-the-Loop:** Automated staging → PR → human review → deployment
- **GitHub-Only Infrastructure:** No persistent cloud resources required
- **Security Hardened:** Input validation, output sanitization, attack detection

## Architecture

```
CTI Files → ADK Agent Pipeline → Sigma Rules + Test Payloads
                                        ↓
                    Unit Testing (pySigma validation)
                                        ↓
                    Integration Testing (ephemeral ELK)
                                        ↓
                    LLM Judge Evaluation → Pass/Fail
                                        ↓
                    Staged Rules → Human Review → Production
```

## Prerequisites

- Python 3.11+ (3.12 or 3.13 recommended)
- GCP account with Vertex AI enabled
- Docker (for local ELK testing)
- GitHub account (for CI/CD)
- git CLI
- gcloud CLI ([installation guide](https://cloud.google.com/sdk/docs/install))

## Quick Setup (All Platforms)

### Option 1: Automated Bootstrap (Recommended)

The bootstrap script automates GCP and GitHub setup. Works on macOS, Linux, and Windows (Git Bash/WSL).

```bash
#clone and navigate to project
cd adk-tide-generator

#run bootstrap (interactive - will prompt for inputs)
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

The script will:
1. Create/use GCP project
2. Enable Vertex AI APIs
3. Create service account with minimal permissions
4. Upload credentials to GitHub secrets
5. Create .env file
6. Test the setup

**Note:** On Windows, use Git Bash or WSL to run the script.

### Option 2: Manual Setup (Cross-Platform)

#### Step 1: Clone Repository

```bash
#clone repo
cd adk-tide-generator
```

#### Step 2: Create Virtual Environment

**macOS/Linux:**
```bash
#create venv
python3 -m venv venv

#activate venv
source venv/bin/activate

#upgrade pip
pip install --upgrade pip

#install dependencies
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
#create venv
python -m venv venv

#activate venv
.\venv\Scripts\Activate.ps1

#if you get execution policy error, run:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

#upgrade pip
python -m pip install --upgrade pip

#install dependencies
pip install -r requirements.txt
```

**Windows (Command Prompt):**
```cmd
REM create venv
python -m venv venv

REM activate venv
venv\Scripts\activate.bat

REM upgrade pip
python -m pip install --upgrade pip

REM install dependencies
pip install -r requirements.txt
```

#### Step 3: Verify Installation

**All platforms:**
```bash
#test CTI loading (validates Phase 1)
python run_agent.py --test-cti
```

Expected output:
```
✓ CTI loading successful!
Phase 1 (Foundation) validation: PASSED
```

## GCP Setup Instructions

### 1. Create GCP Project

```bash
#set project ID
export PROJECT_ID="your-detection-engineering-project"

#create project
gcloud projects create $PROJECT_ID --name="Detection Engineering"

#set as active project
gcloud config set project $PROJECT_ID

#enable billing (required for Vertex AI)
#visit: https://console.cloud.google.com/billing
```

### 2. Enable Required APIs

```bash
#enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

#enable Generative AI API
gcloud services enable generativelanguage.googleapis.com

#enable IAM API
gcloud services enable iam.googleapis.com

#verify APIs enabled
gcloud services list --enabled | grep -E "(aiplatform|generativelanguage)"
```

### 3. Create Service Account

```bash
#create service account
gcloud iam service-accounts create sigma-detection-agent \
    --display-name="Sigma Detection Agent" \
    --description="Service account for automated detection engineering"

#get service account email
export SA_EMAIL="sigma-detection-agent@${PROJECT_ID}.iam.gserviceaccount.com"

#grant required permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/generativelanguage.user"

#create and download key
gcloud iam service-accounts keys create ~/sigma-detection-sa-key.json \
    --iam-account=$SA_EMAIL

#secure the key file
chmod 600 ~/sigma-detection-sa-key.json

echo "Service account key saved to: ~/sigma-detection-sa-key.json"
```

### 4. Verify Permissions

```bash
#check service account permissions
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${SA_EMAIL}"

#expected output should include:
# - roles/aiplatform.user
# - roles/generativelanguage.user
```

### 5. Set Quota Limits (Important for Free Tier)

Visit [GCP Quotas Page](https://console.cloud.google.com/iam-admin/quotas) and verify:

- **Gemini Pro (2.5):** 2 requests/minute (default)
- **Gemini Flash (2.5):** 10 requests/minute (default)
- **Total tokens:** 1M context window per request

Our agent uses aggressive throttling to stay well below these limits.

## Installation

### 1. Clone Repository

```bash
git clone <your-repo>
cd chapter-16
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  #on macOS/Linux
#venv\Scripts\activate  #on Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

#verify installation
python -c "import google.genai; import pysigma; print('Dependencies OK')"
```

### 4. Configure Environment

```bash
#copy example env file
cp .env.example .env

#edit .env with your values
nano .env
```

**Required .env values:**

```bash
#GCP configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sigma-detection-sa-key.json

#use Vertex AI (required)
GOOGLE_GENAI_USE_VERTEXAI=true
```

### 5. Verify GCP Authentication

```bash
#test authentication
python -c "
from google.genai import Client
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(
    vertexai=True,
    project=os.getenv('GOOGLE_CLOUD_PROJECT'),
    location=os.getenv('GOOGLE_CLOUD_LOCATION')
)

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='Say hello'
)

print('Authentication successful!')
print(response.text)
"
```

Expected output: `Hello!` or similar greeting

## Testing the Setup

After running bootstrap scripts, validate everything works:

```bash
#activate virtual environment
source venv/bin/activate

#test CTI loading (Phase 1 validation)
python run_agent.py --test-cti

#expected output:
# Loading CTI files from: sigma_detection_agent/cti_src
# Loaded 1 CTI files (~XXX tokens)
# ✓ CTI loading successful!
# Phase 1 (Foundation) validation: PASSED
```

## Working with CTI Files

### 1. Add CTI Files

Place your threat intelligence files in the CTI source folder:

```bash
#create sample CTI file
cat > sigma_detection_agent/cti_src/sample-threat.md << 'EOF'
# GCP IAM Privilege Escalation Campaign

## Threat Actor
APT-Cloud-Hunter - sophisticated threat actor targeting cloud environments

## Attack Chain
1. Initial access via compromised service account credentials
2. Reconnaissance of IAM policies and service accounts
3. Privilege escalation using service account impersonation
4. Lateral movement to high-value GCP projects
5. Data exfiltration from Cloud Storage and BigQuery

## TTPs
- T1550.001: Use Alternate Authentication Material (Service Account Tokens)
- T1078.004: Valid Accounts (Cloud Accounts)
- T1087.004: Account Discovery (Cloud Account)

## Indicators
- Unusual GenerateAccessToken API calls from external users
- Service account impersonation from non-service principals
- Multiple failed IAM policy modifications
EOF
```

### 2. Run Agent (Coming in Phase 2)

```bash
#interactive mode
python run_agent.py --interactive

#automated mode
python run_agent.py --mode all --output-dir generated/
```

### 3. Review Generated Rules

```bash
#view generated sigma rules
ls generated/sigma_rules/

#view test payloads
ls generated/tests/

#check quality report
cat session_results/latest_quality_report.json
```

## Testing

### Unit Tests (Fast - Seconds)

```bash
#test pydantic schemas
python -c "
from sigma_detection_agent.schemas import SigmaRule, CTIAnalysisOutput
print('Schemas imported successfully')
"

#test CTI loader
python -c "
from sigma_detection_agent.tools import load_cti_files
result = load_cti_files('sigma_detection_agent/cti_src')
print(f'Loaded {result[\"files_loaded\"]} files')
"
```

### Integration Tests (Requires Docker)

```bash
#coming in Phase 5
python scripts/integration_test_elk.py
```

## Project Structure

```
.
├── sigma_detection_agent/          #main agent package
│   ├── agent.py                    #root agent + workflows
│   ├── prompts/                    #external prompt files
│   ├── schemas/                    #pydantic models
│   ├── tools/                      #custom tools
│   └── cti_src/                    #CTI input files (user places here)
│
├── generated/                      #agent output (draft rules)
│   ├── sigma_rules/                #generated sigma YAML
│   ├── tests/                      #test payloads (TP/FN/FP/TN)
│   └── .github/workflows/          #auto-generated CI/CD
│
├── staged_rules/                   #rules that PASSED LLM judge
│   ├── *.yml                       #staged rules with UID
│   ├── *_metadata.json             #quality scores + metrics
│   └── tests/                      #test payloads for staged rules
│
├── production_rules/               #human-approved rules
│   └── *.yml                       #deployed to SIEM
│
├── scripts/                        #testing automation
│   ├── unit_test_sigma.py
│   ├── integration_test_elk.py
│   ├── run_llm_judge.py
│   └── stage_passing_rules.py
│
├── docker/                         #ELK stack for integration testing
│   └── docker-compose.yml
│
└── .github/workflows/              #CI/CD workflows
    ├── generate-detections.yml
    ├── test-detections.yml
    └── mock-deploy.yml
```

## Workflow: CTI → Production Detections

1. **Generate Rules:** Place CTI files → run agent → generates Sigma rules + tests
2. **Unit Testing:** pySigma validates syntax, logic, MITRE mappings
3. **Integration Testing:** Ephemeral ELK deploys rules, ingests test data, measures results
4. **LLM Judge:** Evaluates rules based on actual metrics (precision ≥ 0.80, recall ≥ 0.70)
5. **Staging:** Passing rules → `staged_rules/` → auto-create PR
6. **Human Review:** Security engineer reviews PR, checks quality report
7. **Approval:** Merge PR → mock deployment → `production_rules/`
8. **SIEM Deploy:** Convert Sigma → your SIEM format, deploy to production

## Security Features

- **Input Validation:** File size limits, path traversal protection, allowed file types
- **Content Sanitization:** Strips prompt injection patterns from CTI files
- **Output Validation:** Detects malicious/nonsensical Sigma rules, stops build on critical issues
- **Rate Limiting:** Aggressive throttling (3s delays) to prevent GCP quota exhaustion
- **Attack Detection:** Monitors for overly broad rules (DoS risk), prompt injection artifacts

## Troubleshooting

### "ResourceExhausted: 429 Quota exceeded"

**Cause:** Hit Gemini API rate limits (2 RPM for Pro, 10 RPM for Flash)

**Fix:**
```bash
#agent has built-in exponential backoff, just wait
#or reduce CTI file count/size

#check current quotas
gcloud services list --enabled | grep aiplatform
```

### "Authentication failed"

**Cause:** Invalid service account key or permissions

**Fix:**
```bash
#verify credentials file exists
ls -l $GOOGLE_APPLICATION_CREDENTIALS

#re-authenticate
gcloud auth application-default login

#verify service account has correct roles
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount"
```

### "CTI folder not found"

**Cause:** No CTI files in `sigma_detection_agent/cti_src/`

**Fix:**
```bash
#place CTI files in correct location
ls sigma_detection_agent/cti_src/

#supported formats: .txt, .md, .pdf, .docx
```

### "ModuleNotFoundError: No module named 'google_adk'" or "google.adk"

**Cause:** Incorrect venv setup or wrong import path

**Fix:**

**1. Verify you're in the venv:**
```bash
#macOS/Linux
which python  #should show path to venv/bin/python

#Windows
where python  #should show path to venv\Scripts\python.exe
```

**2. Check if google-adk is installed:**
```bash
pip list | grep google-adk
```

**3. If not installed, reinstall:**
```bash
pip install -r requirements.txt
```

**4. If project directory itself became a venv (has bin/, lib/, pyvenv.cfg):**
```bash
#deactivate if in venv
deactivate  #or close terminal

#remove venv files from project root
rm -rf bin/ lib/ include/ pyvenv.cfg share/

#create proper nested venv
python3 -m venv venv

#activate it
source venv/bin/activate  #macOS/Linux
#or
.\venv\Scripts\Activate.ps1  #Windows PowerShell

#install dependencies
pip install -r requirements.txt
```

### Windows-Specific Issues

**PowerShell Execution Policy Error:**
```powershell
#if you get "cannot be loaded because running scripts is disabled"
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

#then retry activation
.\venv\Scripts\Activate.ps1
```

**Git Bash path issues:**
```bash
#if paths don't work in Git Bash, use forward slashes
python run_agent.py --test-cti

#or use winpty for interactive scripts
winpty ./scripts/bootstrap.sh
```

**Windows Terminal vs Command Prompt:**
- Prefer Windows Terminal or PowerShell for better Unicode support
- Command Prompt may not render progress indicators correctly

### macOS-Specific Issues

**Python version conflicts:**
```bash
#if you have multiple Python versions
python3 --version  #should be 3.11+

#explicitly use python3.11, 3.12, or 3.13
python3.13 -m venv venv
```

**Xcode Command Line Tools (if missing):**
```bash
#required for some dependencies
xcode-select --install
```

### Linux-Specific Issues

**Missing Python venv module:**
```bash
#ubuntu/debian
sudo apt-get install python3-venv python3-dev

#fedora/rhel
sudo dnf install python3-devel

#arch
sudo pacman -S python-virtualenv
```

**Permission denied on scripts:**
```bash
#make bootstrap script executable
chmod +x scripts/bootstrap.sh
```

## Development Roadmap

- [x] **Phase 1:** Foundation (schemas, CTI loading)
- [ ] **Phase 2:** Sigma generation (CTI → Sigma rules)
- [ ] **Phase 3:** Test generation (TP/FN/FP/TN payloads)
- [ ] **Phase 4:** Unit testing (pySigma validation)
- [ ] **Phase 5:** ELK integration (ephemeral testing)
- [ ] **Phase 6:** LLM judge (quality evaluation)
- [ ] **Phase 7:** CI/CD (GitHub Actions)
- [ ] **Phase 8:** CLI & polish
- [ ] **Phase 9:** Documentation
- [ ] **Phase 10:** Final testing

Current status: **Phase 1 in progress** (see RUNNING_NOTES.md)

## Contributing

This is a reference implementation for Chapter 16. For production use:

1. Customize prompts for your threat model
2. Adjust quality thresholds (precision/recall)
3. Add SIEM-specific converters (Splunk SPL, Chronicle YARA-L, etc.)
4. Implement persistent SIEM deployment (replace mock_deploy.py)

## References

- **Sigma Rules:** https://github.com/SigmaHQ/sigma
- **pySigma:** https://github.com/SigmaHQ/pySigma
- **Gemini API:** https://ai.google.dev/gemini-api/docs
- **MITRE ATT&CK:** https://attack.mitre.org/
- **GCP Audit Logs:** https://cloud.google.com/logging/docs/audit

## License

MIT License - see LICENSE file

## Support

For issues or questions:
- Create GitHub issue
- Review RUNNING_NOTES.md for implementation status
- Check troubleshooting section above
