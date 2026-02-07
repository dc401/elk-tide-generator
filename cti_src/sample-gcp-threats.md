# GCP IAM Privilege Escalation Campaign - APT-Cloud-Hunter

## Executive Summary
Advanced threat actor APT-Cloud-Hunter has been observed targeting Google Cloud Platform (GCP) environments with sophisticated privilege escalation techniques focused on IAM service account abuse.

## Threat Actor Profile
- **Name:** APT-Cloud-Hunter
- **Aliases:** CloudStrike, GCP-Shadow
- **Motivation:** Espionage, data theft
- **Sophistication:** High
- **First Observed:** 2024-Q2
- **Targets:** Cloud-native organizations, SaaS providers, financial services

## Attack Chain

### 1. Initial Access (T1078.004 - Valid Accounts: Cloud Accounts)
- Compromised service account credentials via phishing or credential stuffing
- Exploited misconfigured Cloud Storage buckets containing service account keys
- Target: Low-privilege service accounts in development projects

### 2. Discovery (T1087.004 - Account Discovery: Cloud Account)
- Enumerate IAM policies: `gcloud projects get-iam-policy`
- List service accounts: `gcloud iam service-accounts list`
- Identify high-privilege service accounts with `roles/iam.serviceAccountTokenCreator`

### 3. Privilege Escalation (T1550.001 - Use Alternate Authentication Material)
**Primary TTP: Service Account Impersonation**
- Use `GenerateAccessToken` API to impersonate high-privilege service accounts
- Target accounts with `roles/owner`, `roles/editor`, or custom admin roles
- Bypass MFA by using service account tokens instead of user accounts

**GCP API Calls Observed:**
```
iam.serviceAccounts.getAccessToken
iam.serviceAccounts.implicitDelegation
iam.serviceAccounts.generateAccessToken
```

**Example Attack Command:**
```bash
gcloud iam service-accounts generate-access-token \
  highly-privileged-sa@project.iam.gserviceaccount.com \
  --impersonate-service-account=victim-sa@project.iam.gserviceaccount.com
```

### 4. Lateral Movement (T1021.007 - Cloud Services)
- Use elevated privileges to access other GCP projects
- Modify IAM policies to grant persistent access
- Create new service accounts as backdoors

### 5. Data Exfiltration (T1567.002 - Cloud Storage)
- Export BigQuery datasets to attacker-controlled Cloud Storage buckets
- Download sensitive files from Cloud Storage
- Exfiltrate data via Cloud Functions with outbound internet access

## Key Indicators of Compromise (IOCs)

### GCP Audit Log Patterns
1. **Unusual GenerateAccessToken API calls:**
   - `protoPayload.methodName: "GenerateAccessToken"`
   - `protoPayload.authenticationInfo.principalEmail` does NOT end with `.gserviceaccount.com`
   - Multiple calls within short timeframe (5+ within 10 minutes)

2. **Service Account Impersonation from External Users:**
   - User account (not service account) calling `iam.serviceAccounts.implicitDelegation`
   - Source IP outside normal GCP IP ranges
   - Off-hours activity (outside business hours)

3. **IAM Policy Modifications:**
   - `SetIamPolicy` calls adding `roles/iam.serviceAccountTokenCreator`
   - Binding modifications granting `roles/owner` to new principals
   - Policy changes from non-admin accounts

4. **Suspicious BigQuery Data Access:**
   - Large dataset exports (>10GB) to external storage
   - `bigquery.datasets.export` to non-organizational buckets
   - Unusual query patterns accessing sensitive tables

## Detection Opportunities

### High-Priority Detections

**1. External User Service Account Impersonation**
- **Log Source:** GCP Audit Logs (Admin Activity)
- **Detection Logic:**
  - `serviceName = "iam.googleapis.com"`
  - `methodName = "GenerateAccessToken"`
  - `authenticationInfo.principalEmail` NOT like `%@%.gserviceaccount.com`
- **False Positive Risk:** LOW (legitimate use rare)
- **Severity:** HIGH

**2. Excessive Service Account Token Generation**
- **Log Source:** GCP Audit Logs (Admin Activity)
- **Detection Logic:**
  - Count `GenerateAccessToken` calls per principal
  - Threshold: >5 calls in 10 minutes
  - Group by `authenticationInfo.principalEmail`
- **False Positive Risk:** MEDIUM (CI/CD pipelines may trigger)
- **Severity:** MEDIUM

**3. Off-Hours IAM Policy Modifications**
- **Log Source:** GCP Audit Logs (Admin Activity)
- **Detection Logic:**
  - `methodName = "SetIamPolicy"`
  - Timestamp outside business hours (e.g., 00:00-06:00 UTC)
  - Excludes automated service accounts
- **False Positive Risk:** MEDIUM (on-call engineers, global teams)
- **Severity:** HIGH

**4. Service Account Privilege Escalation**
- **Log Source:** GCP Audit Logs (Admin Activity)
- **Detection Logic:**
  - `methodName = "SetIamPolicy"`
  - `request.policy.bindings` contains `roles/iam.serviceAccountTokenCreator`
  - `request.policy.bindings` contains `roles/owner` OR `roles/editor`
- **False Positive Risk:** LOW
- **Severity:** CRITICAL

## Defensive Recommendations

1. **IAM Policy Hardening:**
   - Restrict `roles/iam.serviceAccountTokenCreator` to trusted principals only
   - Implement organization policy constraint: `iam.disableServiceAccountKeyCreation`
   - Use short-lived tokens (Workload Identity Federation)

2. **Monitoring & Alerting:**
   - Enable Cloud Audit Logs for all GCP services
   - Forward logs to SIEM (Chronicle, Splunk, ELK)
   - Implement detections outlined above

3. **Access Controls:**
   - Enforce VPC Service Controls to restrict service account usage
   - Require MFA for all human users
   - Separate dev/staging/prod projects with strict IAM boundaries

## MITRE ATT&CK Mapping

| Tactic | Technique | ID | GCP Context |
|--------|-----------|-----|-------------|
| Initial Access | Valid Accounts: Cloud Accounts | T1078.004 | Compromised service account credentials |
| Discovery | Account Discovery: Cloud Account | T1087.004 | Enumerate IAM policies and service accounts |
| Privilege Escalation | Use Alternate Authentication Material | T1550.001 | Service account impersonation via GenerateAccessToken |
| Persistence | Account Manipulation | T1098.001 | Create backdoor service accounts |
| Lateral Movement | Remote Services: Cloud Services | T1021.007 | Access other GCP projects |
| Exfiltration | Transfer Data to Cloud Account | T1537 | Export BigQuery data to attacker-controlled storage |

## References
- [GCP IAM Service Account Documentation](https://cloud.google.com/iam/docs/service-accounts)
- [GCP Audit Logs Reference](https://cloud.google.com/logging/docs/audit)
- [MITRE ATT&CK for Cloud](https://attack.mitre.org/matrices/enterprise/cloud/)
- [Service Account Impersonation Best Practices](https://cloud.google.com/iam/docs/impersonating-service-accounts)

## Appendix: Sample GCP Audit Log

```json
{
  "protoPayload": {
    "serviceName": "iam.googleapis.com",
    "methodName": "GenerateAccessToken",
    "authenticationInfo": {
      "principalEmail": "attacker@external-domain.com"
    },
    "requestMetadata": {
      "callerIp": "203.0.113.42"
    },
    "request": {
      "name": "projects/-/serviceAccounts/admin-sa@victim-project.iam.gserviceaccount.com",
      "delegates": [],
      "scope": ["https://www.googleapis.com/auth/cloud-platform"]
    },
    "response": {
      "accessToken": "[REDACTED]",
      "expireTime": "2024-12-25T13:00:00Z"
    }
  },
  "resource": {
    "type": "service_account",
    "labels": {
      "project_id": "victim-project",
      "unique_id": "112233445566778899"
    }
  },
  "timestamp": "2024-12-25T12:00:00Z",
  "severity": "NOTICE"
}
```

---

**Report Date:** 2024-12-25  
**Analyst:** Threat Intelligence Team  
**Classification:** CONFIDENTIAL
