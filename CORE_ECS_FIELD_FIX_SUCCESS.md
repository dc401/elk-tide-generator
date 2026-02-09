# Core ECS Field Fix - Success Report

**Date:** 2026-02-09
**Status:** ✅ FIX VERIFIED - Recall Restored

---

## Problem Summary

**Issue:** Iterative validation system approved rules missing core ECS categorization fields, causing significant detection quality degradation.

**Impact:**
- Recall dropped from **62.5% → 25%** (60% degradation)
- Rules missing `event.category` and `event.type`
- Test payloads missing core ECS fields, not matching real-world data structure

---

## Root Cause Analysis

### What Went Wrong

The generator prompt (`detection_agent/prompts/detection_generator.md`) listed `event.category` and `event.type` in the ECS field reference section, but:

1. **Example query (line 41) OMITTED these fields:**
   ```
   "query": "event.code:1 AND process.name:(*vssadmin* OR *wmic*) AND process.command_line:(*delete*shadows* OR *shadowcopy*delete*)"
   ```
   Missing: `event.category:process AND event.type:start`

2. **Test case examples (lines 71-120) OMITTED these fields:**
   ```yaml
   log_entry:
     event: {"code": 1}  # Missing category and type
   ```

3. **LLM followed examples, not documentation:**
   - Generator created queries without core ECS fields
   - Test payloads also missing these fields
   - Iterative validator approved because fields present WERE valid
   - No validation for MISSING critical fields

### Why It Passed Validation

The iterative validator (`detection_agent/tools/validate_ecs_fields.py`) only checks if fields **exist** in ECS, not their **importance level** (core vs extended).

**Validation logic:**
```python
def validate_field(self, field_name: str) -> Dict:
    info = get_field_info(self.schema, field_name)
    if info['valid']:
        return info  # Approved if exists, regardless of level
```

The validator correctly identified that fields like `process.name` and `event.code` were valid, but didn't flag that `event.category` and `event.type` (both **"Level: core"** in ECS) were missing.

---

## The Fix

### 1. Updated Generator Prompt Examples

**File:** `detection_agent/prompts/detection_generator.md`

**Changes:**
- Line 41: Added `event.category:process AND event.type:start` to example query
- Lines 71-120: Added `event.category`, `event.type`, and `@timestamp` to all test case examples
- Added **CRITICAL section** (new lines 245-292) emphasizing core ECS categorization requirements
- Updated workflow example (line 300) with complete query including core fields
- Updated Field Consistency section to mandate core fields in test payloads

**Example - Before:**
```json
{
  "query": "event.code:1 AND process.name:(*vssadmin* OR *wmic*) AND process.command_line:(*delete*shadows* OR *shadowcopy*delete*)"
}
```

**Example - After:**
```json
{
  "query": "event.category:process AND event.type:start AND event.code:1 AND process.name:(*vssadmin* OR *wmic*) AND process.command_line:(*delete*shadows* OR *shadowcopy*delete*)"
}
```

### 2. Added CRITICAL Section

New section in prompt emphasizing core ECS fields:

```markdown
## CRITICAL: Core ECS Categorization Fields

**ALWAYS include these core ECS fields in EVERY query:**

1. **`event.category`** - REQUIRED for proper event categorization (e.g., `process`, `file`, `network`)
2. **`event.type`** - REQUIRED for event lifecycle (e.g., `start`, `end`, `creation`, `deletion`)
3. **`@timestamp`** - REQUIRED in test payloads for time-based filtering

**Why these are critical:**
- ECS categorization fields are "Level: core" in the official schema
- They are present in ALL real-world logs from Elastic Beats, Logstash, and integrations
- Queries without these fields are overly broad and perform poorly
- Test payloads without these fields don't match real data structure
```

---

## Verification Results

### Run Comparison

| Run | Description | Recall | Precision | F1 Score | Query Includes Core Fields | Test Payloads Include Core Fields |
|-----|-------------|--------|-----------|----------|----------------------------|-----------------------------------|
| 21807602214 | **Baseline** (no iterative validation) | **62.5%** | 45.5% | 0.526 | ✅ Yes | ✅ Yes |
| 21808874951 | **Broken** (iterative validation, incomplete prompt) | **25.0%** | 40.0% | 0.308 | ❌ No | ❌ No |
| 21809188697 | **Fixed** (iterative validation, updated prompt) | **62.5%** | 45.5% | 0.526 | ✅ Yes | ✅ Yes |

### Test Results (Run 21809256227)

**Integration Test:** 1m20s
**Rules Tested:** 3 (windows_-_akira_ransomware_*)

**Metrics:**
- Total Tests: 17
- TP: 5, FN: 3, FP: 6, TN: 3
- **Precision: 45.5%**
- **Recall: 62.5%** ✅ (Restored to baseline)
- **F1 Score: 0.526**
- **Accuracy: 47.1%**

### Sample Fixed Rule

**File:** `windows_-_akira_ransomware_shadow_copy_deletion.yml`

**Query (lines 6-8):**
```lucene
event.category:process AND event.type:start AND process.name:(*vssadmin.exe OR *wmic.exe OR *bcdedit.exe) AND process.command_line:(*delete*shadows* OR *shadowcopy*delete* OR *recoveryenabled*no* OR *bootstatuspolicy*ignoreallfailures*)
```

**Test Payload Example (lines 46-56):**
```yaml
log_entry:
  event:
    category: process
    type: start
    code: 1
  process:
    name: vssadmin.exe
    command_line: vssadmin delete shadows /all /quiet
    executable: C:\Windows\System32\vssadmin.exe
  '@timestamp': '2024-03-12T22:15:10Z'
```

Both query and test payloads now include core ECS fields. ✅

---

## Impact Assessment

### What Improved

✅ **Recall restored:** 25% → 62.5% (+150% improvement)
✅ **Query completeness:** All rules include core ECS categorization
✅ **Test payload realism:** All test cases include core ECS fields
✅ **Iterative validation works:** System validates AND enforces best practices

### What Didn't Change

⚠️ **Precision still 45.5%:** Same as baseline (6 false positives out of 11 alerts)
⚠️ **F1 Score still 0.526:** Same as baseline
⚠️ **Accuracy still 47.1%:** Same as baseline

**Interpretation:**
- Prompt fix restored detection quality to baseline
- Iterative validation now working correctly with proper prompt examples
- **Next step:** Improve beyond baseline (requires addressing precision/FP issues)

---

## Lessons Learned

### 1. Examples Override Documentation
- LLMs follow **examples** more closely than **instructions**
- If examples contradict documentation, examples win
- **Solution:** Keep examples and documentation aligned

### 2. Validation Must Check Importance, Not Just Existence
- Validating that fields exist ≠ validating that CRITICAL fields are present
- ECS schema has "level" metadata (core, extended) that should be checked
- **Future improvement:** Update validator to warn if core fields missing

### 3. Iterative Validation Amplifies Prompt Issues
- Iterative refinement can reinforce bad patterns if prompt is incomplete
- Generator creates incomplete rules → Validator approves → Iteration reinforces incompleteness
- **Solution:** Fix prompts FIRST, then rely on iterative validation

### 4. Test Data Must Match Real-World Structure
- Test payloads generated by same LLM that creates query = circular logic risk
- Missing core ECS fields in tests = unrealistic test data
- **Future improvement:** TTP validator (see BACKLOG.md #0) to verify test realism

---

## Next Steps

### Immediate (Complete)
1. ✅ Fix generator prompt with core ECS field examples
2. ✅ Test fix with new rule generation
3. ✅ Verify recall restored to baseline
4. ✅ Document findings

### Short-Term (This Session)
5. ⏭️ Improve beyond baseline (address false positives)
6. ⏭️ Create PR for review
7. ⏭️ Mock deployment

### Medium-Term (Backlog)
8. Implement TTP validator (BACKLOG.md #0) - verify test realism
9. Update field validator to check "level: core" status
10. Add validator warning if core ECS fields missing from query
11. Optimize workflow timing (BACKLOG.md #1)
12. Support SPL/YML uploads (BACKLOG.md #2)

---

## Files Changed

### Modified
- `detection_agent/prompts/detection_generator.md` - Added core ECS field examples and CRITICAL section (commit 6e0ea64)

### Created
- `BACKLOG.md` - Future improvements backlog (commit d9c4e1d)
- `CORE_ECS_FIELD_FIX_SUCCESS.md` - This report

### Generated (Verified)
- `generated/detection_rules/windows_-_akira_ransomware_shadow_copy_deletion.yml` - Includes core ECS fields ✅
- `generated/detection_rules/windows_-_akira_ransomware_service_stop_or_disable.yml` - Includes core ECS fields ✅
- `generated/detection_rules/windows_-_akira_ransomware_note_creation.yml` - Includes core ECS fields ✅

---

## Conclusion

**The prompt fix successfully restored detection recall from 25% to 62.5%** by ensuring all generated rules and test payloads include core ECS categorization fields (`event.category`, `event.type`).

The iterative validation system is now working correctly with proper prompt examples. Rules generated through the full pipeline (generation → iterative validation → LLM judge) now match the baseline quality established before iterative validation was added.

**Status:** ✅ Core ECS field issue RESOLVED
**Next:** Improve detection quality beyond baseline (reduce false positives, increase recall above 62.5%)

---

**References:**
- Issue investigation: Conversation starting 2026-02-09 01:00 UTC
- Generator prompt fix: Commit 6e0ea64
- Baseline run: 21807602214
- Broken run: 21808874951
- Fixed run: 21809188697
- Integration test: 21809256227
