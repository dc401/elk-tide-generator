# TTP Intent Validator - Test Results

**Date:** 2026-02-08
**Status:** ✅ TESTED & OPERATIONAL

---

## Executive Summary

The TTP Intent Validator successfully validated 17 test cases across 3 production detection rules, achieving an **88% pass rate** with high confidence. Most importantly, it **detected 2 invalid test cases**, proving its effectiveness at catching circular logic and unrealistic attack simulations.

---

## Test Results

### Overall Metrics
| Metric | Value | Status |
|--------|-------|--------|
| **Total Test Cases** | 17 | |
| **Valid Test Cases** | 15 (88%) | ✅ PASS |
| **Invalid Test Cases** | 2 (12%) | ✅ **CAUGHT!** |
| **Errors** | 0 | ✅ PASS |
| **Confidence Level** | High (17/17) | ✅ PASS |

### Rules Validated
1. **Windows - Akira Ransomware Note Creation** (5 test cases)
   - ✓ 2 TP (True Positives)
   - ✓ 1 FN (False Negative)
   - ✗ 1 FP (False Positive) - **INVALID DETECTED**
   - ✓ 1 TN (True Negative)

2. **Windows - Akira Ransomware Service Stop or Disable** (6 test cases)
   - ✓ 3 TP (all valid)
   - ✓ 1 FN (valid)
   - ✓ 1 FP (valid)
   - ✓ 1 TN (valid)

3. **Windows - Akira Ransomware Shadow Copy Deletion** (6 test cases)
   - ✗ 1 TP - **INVALID DETECTED** (wmic interactive mode)
   - ✓ 2 TP (other TPs valid)
   - ✓ 1 FN (valid)
   - ✓ 1 FP (valid)
   - ✓ 1 TN (valid)

---

## Invalid Test Cases Found (Proof of Effectiveness)

### Issue #1: Invalid False Positive Test Case
**Rule:** Windows - Akira Ransomware Note Creation
**Test:** FP - Legitimate file creation with 'akira' in name

**Problem:**
- Test case claims to be a False Positive (benign event that triggers alert)
- Detection query: `file.name:(*akira_readme.txt OR *akira_readme.html)`
- Test payload file name: `akira_project_notes.txt`
- **The payload does NOT match the detection pattern!**

**Validator Finding:**
> "The test case is invalid as a False Positive because it would not be detected by the rule. The purpose of an FP test is to find a benign event that *is* detected. This log would be correctly ignored."

**Impact:** This is actually a **True Negative** (TN), not a False Positive. The test case misrepresents the detection effectiveness.

**Recommendation:**
- Re-classify as True Negative, OR
- Create a valid FP with file name like `my_project_akira_readme.txt` (matches pattern but is benign)
- However, the high specificity of the pattern makes a plausible FP scenario very unlikely (good rule design!)

---

### Issue #2: Operationally Unrealistic True Positive
**Rule:** Windows - Akira Ransomware Shadow Copy Deletion
**Test:** TP - Malicious wmic shadow copy deletion

**Problem:**
- Test payload command: `wmic shadowcopy delete`
- This command is **interactive** and pauses for user confirmation (Y/N)
- Automated ransomware would NEVER use an interactive command that could hang execution

**Validator Finding:**
> "The primary issue is the command's interactive nature. When run as is, 'wmic shadowcopy delete' will pause and wait for user input, which is counter-productive for an automated ransomware script."

**Research Sources:**
- MITRE ATT&CK T1490 procedure examples
- Microsoft documentation (confirms interactive behavior)
- CISA Advisory AA22-249A (Vice Society ransomware)
- The DFIR Report: Conti uses `wmic.exe shadowcopy delete /nointeractive`

**Impact:** This is **circular logic** - the test payload was simplified to match detection keywords (`shadowcopy`, `delete`) without reflecting operational reality.

**Recommendation:**
```bash
# Current (INVALID):
wmic shadowcopy delete

# Recommended (REALISTIC):
wmic shadowcopy delete /nointeractive
```

**Real-World Example from Conti Ransomware:**
```bash
wmic.exe shadowcopy delete /nointeractive
```

---

## Validation Methodology

For each test case, the validator performed 5 checks:

1. **Command Syntax Realism**
   - Are flags actual flags for this tool?
   - Is syntax valid for the OS/tool?
   - Do flags match documented malware behavior?

2. **TTP Alignment**
   - Does the log entry represent the MITRE technique?
   - Would this command achieve the stated objective?
   - Is the attack vector realistic?

3. **Field Value Realism**
   - Are file paths realistic for the OS?
   - Are process names correctly formatted?
   - Are timestamps, user contexts plausible?

4. **Evasion Technique Validity** (FN cases only)
   - Would this technique actually bypass detection?
   - Is the evasion method documented in real attacks?
   - Is the explanation accurate?

5. **Research-Backed Evidence**
   - Can we find real-world examples?
   - Do threat reports mention this syntax?
   - Does MITRE ATT&CK have procedure examples?

---

## Example Detailed Validation Output

### Invalid WMIC Test Case Analysis

```json
{
  "validation_result": "INVALID",
  "confidence": "high",
  "checks": {
    "command_syntax": {
      "valid": false,
      "details": "The command 'wmic shadowcopy delete' is syntactically valid but functionally incomplete for an automated attack. By default, this command is interactive and prompts the user for confirmation (Y/N) for each shadow copy it finds."
    },
    "ttp_alignment": {
      "valid": true,
      "details": "The command's objective, deleting shadow copies, is a textbook example of T1490 (Inhibit System Recovery)."
    },
    "field_realism": {
      "valid": true,
      "details": "The process name 'wmic.exe', its executable path 'C:\\Windows\\System32\\wbem\\wmic.exe', and the execution context as 'SYSTEM' user are all highly realistic."
    },
    "research_backed": {
      "valid": false,
      "details": "While MITRE and threat reports confirm the use of 'wmic' for shadow copy deletion, they consistently show attackers using non-interactive versions. Real-world examples almost always include the '/nointeractive' flag."
    }
  },
  "research_sources": [
    "https://attack.mitre.org/techniques/T1490/",
    "https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/cc771459(v=ws.11)",
    "https://www.cisa.gov/news-events/cybersecurity-advisories/aa22-249a",
    "https://thedfirreport.com/2021/08/01/conti-leaks-and-a-new-log4j-chain/"
  ],
  "recommendations": "To improve realism, the test payload should be updated to a non-interactive and commonly observed variant. A much better and more realistic command would be `wmic shadowcopy delete /nointeractive`.",
  "real_world_example": "A more realistic command line used by threat actors like Conti is: `wmic.exe shadowcopy delete /nointeractive`"
}
```

---

## Key Success Metrics

### What This Proves

✅ **Circular Logic Detection:** Caught test payload designed to match query keywords without operational realism
✅ **Research-Backed Validation:** Used MITRE ATT&CK, threat intel reports, tool documentation to verify commands
✅ **High Confidence:** All 17 validations returned high confidence scores
✅ **Zero Errors:** No API failures, authentication issues, or validation errors
✅ **Detailed Analysis:** Each validation includes 5 checks, research sources, and actionable recommendations

### What We Prevented

❌ **False Confidence in Detections:** Invalid test cases would give false sense of detection effectiveness
❌ **Poor Test Coverage:** Unrealistic payloads don't represent real attack behavior
❌ **Wasted Analyst Time:** Invalid FPs/FNs mislead tuning efforts

---

## Next Steps

### Immediate (Current Session)
1. ✅ TTP validator tested and operational
2. ✅ Invalid test cases documented
3. ⏭️ **Fix invalid test cases** in production rules (optional - demonstrates pipeline improvement)

### Short-Term (Next Session)
4. **Integrate into main pipeline:**
   - Add TTP validation after step 3.5 (iterative validation)
   - If payload validation fails → regenerate with feedback
   - Only proceed to integration testing with valid payloads

5. **Update GitHub workflows:**
   - Add TTP validation step to `generate-detections.yml`
   - Fail build if critical issues detected
   - Store validation results as artifacts

### Medium-Term (Backlog)
6. **Automated test payload refinement:**
   - Use validator recommendations to regenerate invalid payloads
   - Retry validation until all pass or max iterations reached
   - Track refinement history in metadata

7. **Expand validation coverage:**
   - Add validation for more TTP types (T1003, T1055, T1059, etc.)
   - Build library of validated real-world attack patterns
   - Community contribution of validated payloads

---

## Technical Details

### Tools Used
- **Model:** Gemini 2.5 Pro (via Vertex AI)
- **Temperature:** 0.0 (deterministic validation)
- **Modalities:** TEXT only
- **Thinking Mode:** Not supported via Vertex AI (removed from config)

### Files
- **Validator Tool:** `detection_agent/tools/ttp_intent_validator.py`
- **Validation Prompt:** `detection_agent/prompts/ttp_validator_prompt.md` (296 lines)
- **Test Script:** `scripts/test_ttp_validator.py`
- **Demo Script:** `scripts/demo_ttp_validation.py` (no API calls)
- **Results:** `ttp_validation_results.json` (detailed findings)

### Performance
- **Total Validation Time:** ~2-3 minutes for 17 test cases
- **API Calls:** 17 (one per test case)
- **Rate Limiting:** 3-second delay between batches of 2
- **Cost:** Minimal (Pro model, short responses)

---

## Conclusion

The TTP Intent Validator successfully demonstrated its ability to:

1. **Detect circular logic** where test payloads are artificially designed to match detection queries
2. **Validate operational realism** by cross-referencing with MITRE ATT&CK, threat reports, and tool documentation
3. **Provide actionable recommendations** backed by real-world threat intelligence
4. **Maintain high confidence** in validation decisions with detailed research sources

**Backlog #0 Status:** ✅ COMPLETE - Ready for pipeline integration

The validator is now operational and can be integrated into the main detection generation pipeline to ensure all test payloads accurately represent real-world attack behavior.

---

**Next Action:** Integrate TTP validator into `detection_agent/agent.py` after step 3.5 (iterative validation) with regeneration loop for invalid payloads.
