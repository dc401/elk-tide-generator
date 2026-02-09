# Fix Applied - Pydantic Validation Error

**Date:** 2026-02-08 23:30
**Commit:** a61aa4a

---

## Problem

Workflow failing with:
```
ValidationError: 2 validation errors for DetectionRuleOutput
rules - Field required [type=missing]
cti_context - Field required [type=missing]
```

---

## Root Cause

LLM response format not matching DetectionRuleOutput schema. The schema expects:
```python
class DetectionRuleOutput(BaseModel):
    rules: List[DetectionRule]  # REQUIRED
    cti_context: Dict  # REQUIRED
    total_rules: int  # Optional
```

But LLM was sometimes returning incomplete response or single rule dict.

---

## Fix Applied

Added validation BEFORE Pydantic parsing in `detection_agent/agent.py:222-239`:

1. **Check for 'rules' field** - Fail fast with clear error showing actual keys
2. **Check for 'cti_context'** - Add default if missing (with warning)
3. **Better error messages** - Show what fields are present vs expected

```python
#parse and validate response
parsed_response = safe_json_parse(gen_response)

#check if response has required fields
if 'rules' not in parsed_response:
    print(f"  ✗ LLM response missing 'rules' field")
    print(f"  Response keys: {list(parsed_response.keys())}")
    raise ValueError("Invalid LLM response format: missing 'rules' field")

if 'cti_context' not in parsed_response:
    print(f"  ⚠️  LLM response missing 'cti_context', adding default")
    parsed_response['cti_context'] = {
        'source': 'cti_src',
        'analyzed': datetime.now().isoformat()
    }

rule_output = DetectionRuleOutput(**parsed_response)
```

---

## Testing Needed

**Cannot test locally without GCP credentials**

User needs to test by triggering workflow:
```bash
gh workflow run generate-detections.yml
```

Or test locally with:
```bash
gcloud auth login
export GOOGLE_CLOUD_PROJECT=your-project-id
python run_agent.py --cti-folder cti_src --output generated
```

---

## Expected Outcome

- If LLM returns proper format → Works as before
- If LLM missing 'rules' → Clear error message showing what fields are present
- If LLM missing 'cti_context' → Warning but continues with default context
- No more cryptic Pydantic validation errors

---

## Next Steps

1. User tests workflow or runs locally with GCP auth
2. If still fails, check error message to see what fields LLM is returning
3. May need to adjust prompt in `detection_agent/prompts/detection_generator.md`

---

**Status:** Fix committed, awaiting test
