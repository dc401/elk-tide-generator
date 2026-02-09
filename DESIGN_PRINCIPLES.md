# Design Principles & Constraints

**CRITICAL: Read this file at the start of EVERY session before making changes**

This document defines hard constraints that must NEVER be violated during development or refinement.

---

## 1. Model Version Stability (NEVER CHANGE)

**Constraint:** Use ONLY Gemini 2.5 Pro and Gemini 2.5 Flash

**Rationale:**
- Proven stable performance in production (gcphunter reference)
- Consistent API behavior and rate limits
- Known retry/backoff configurations tested

**What NOT to do:**
- ❌ DO NOT upgrade to newer Gemini versions without explicit user approval
- ❌ DO NOT switch to Opus, Sonnet, or other model families
- ❌ DO NOT experiment with model parameters (temperature, top_k, etc.) without discussion

**What TO do:**
- ✅ Use `gemini-2.0-flash-exp` for fast operations (formatting, validation)
- ✅ Use `gemini-2.0-pro-exp` for complex reasoning (CTI analysis, detection generation)
- ✅ Maintain current retry configurations (AGGRESSIVE_RETRY_CONFIG, FLASH_RETRY_CONFIG)

**Where this is defined:**
- `detection_agent/agent.py` lines 30-40 (model definitions)
- `run_agent.py` environment setup

---

## 2. Dynamic CTI Source Support (NO STATIC VALIDATION)

**Constraint:** System MUST work with ANY CTI source without domain-specific hardcoding

**Rationale:**
- CTI sources are unpredictable (PDF, TXT, MD, DOCX from any vendor)
- Detections must support multiple platforms (GCP, AWS, Azure, Windows, Linux, etc.)
- Overly specific validation breaks when new threat actors or platforms appear

**What NOT to do:**
- ❌ DO NOT add static validation rules like "must contain GCP" or "must be Windows-only"
- ❌ DO NOT hardcode platform-specific field requirements in test validation
- ❌ DO NOT create separate workflows for different platforms (keep unified)
- ❌ DO NOT add domain-specific guardrails that assume specific log sources

**What TO do:**
- ✅ Keep prompts general with examples from multiple platforms
- ✅ Use ECS field validation (universal schema) not vendor-specific schemas
- ✅ Test with diverse CTI sources (cloud + endpoint + network)
- ✅ Allow detection_generator.md to handle platform differences dynamically

**Examples of GOOD practices:**
```markdown
# CORRECT: General guidance applicable to any platform
**Cloud fields (AWS/Azure/GCP):**
- event.action - Specific API call name (REQUIRED for cloud detections)

# WRONG: Platform-specific mandate
**GCP-specific requirements:**
- Must use google.compute.v1.* format
```

**Where this matters:**
- `detection_agent/prompts/detection_generator.md` (must stay platform-agnostic)
- `scripts/validate_*.py` (validate ECS compliance, not platform specifics)
- Test payload generation (must not assume single platform)

---

## 3. Sequential Testing & Race Condition Prevention

**Constraint:** Test ONE workflow change at a time, address race conditions explicitly

**Rationale:**
- Multiple simultaneous changes make failure analysis impossible
- GitHub Actions workflows can race if triggered simultaneously
- Difficult to attribute success/failure to specific changes

**What NOT to do:**
- ❌ DO NOT trigger multiple workflows in parallel during testing
- ❌ DO NOT make multiple prompt changes and test together
- ❌ DO NOT modify both detection generation AND test validation in same test cycle
- ❌ DO NOT commit multiple unrelated fixes without individual validation

**What TO do:**
- ✅ Test ONE change per workflow run (e.g., prompt fix → test → analyze)
- ✅ Wait for workflow completion before triggering next test
- ✅ If race condition suspected, add workflow concurrency controls
- ✅ Document which specific change is being tested in commit message

**Testing workflow:**
1. Make change (e.g., fix prompt)
2. Commit with clear description
3. Trigger SINGLE workflow
4. Monitor to completion
5. Analyze results
6. If success → proceed to next change
7. If failure → iterate on SAME change

**Where this matters:**
- `.github/workflows/*.yml` (check for concurrency groups)
- Testing strategy (one variable at a time)
- Commit discipline (atomic changes)

---

## 4. Code Simplicity & Intent Preservation

**Constraint:** Keep code simple and practical, don't drift from original design

**Rationale:**
- Over-engineering reduces maintainability
- User's CLAUDE.md emphasizes simplicity and functionality first
- Features should solve real problems, not theoretical ones

**What NOT to do:**
- ❌ DO NOT add abstraction layers without clear benefit
- ❌ DO NOT introduce new dependencies for minor convenience
- ❌ DO NOT refactor working code without user request
- ❌ DO NOT add features beyond original scope (scope creep)
- ❌ DO NOT prioritize "best practices" over simplicity

**What TO do:**
- ✅ Prefer built-in libraries over external dependencies
- ✅ Keep functions simple and single-purpose
- ✅ Document why complex code exists (with comments)
- ✅ Question whether new feature aligns with original intent
- ✅ Optimize for readability over performance (unless performance critical)

**Examples of drift to AVOID:**
```python
# WRONG: Over-engineered
class ConfigManager:
    def __init__(self):
        self.config_loader = ConfigLoader()
        self.validator = ConfigValidator()
    def load(self):
        raw = self.config_loader.load()
        return self.validator.validate(raw)

# RIGHT: Simple and direct
def load_config(path: Path) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)
```

**Where this matters:**
- All Python modules (prefer functions over classes when practical)
- Tool implementations (simple, focused tools)
- Workflow definitions (avoid complex bash gymnastics)

---

## Original Design Intent (Reference)

**Core Mission:** Automated CTI → Elasticsearch Detection Rules with quality validation

**Key Features (DO NOT REMOVE):**
1. Multi-file CTI ingestion (PDF, TXT, MD, DOCX)
2. Elasticsearch detection rule generation (Lucene query format)
3. Automated test payload generation (TP/FN/FP/TN)
4. Integration testing with ephemeral Elasticsearch
5. Quality-driven refinement with metrics (precision/recall)
6. Human-in-the-loop via PR review

**Non-Goals (DO NOT ADD):**
- SIEM deployment automation (mock only)
- Real-time threat intelligence feeds
- Machine learning models for detection
- Complex orchestration beyond linear workflow

---

## How to Use This File

**At session start:**
1. Read this entire file
2. Review recent commits to understand current state
3. Check QUALITY_ANALYSIS.md and PROGRESS_SUMMARY.md for context
4. Before making ANY architectural change, verify it aligns with these principles

**During development:**
1. If tempted to change models → STOP, re-read principle #1
2. If adding platform-specific validation → STOP, re-read principle #2
3. If triggering multiple tests → STOP, re-read principle #3
4. If adding complexity → STOP, re-read principle #4

**Session handoff:**
1. Update PROGRESS_SUMMARY.md with what changed
2. Update QUALITY_ANALYSIS.md if test results changed
3. Commit with clear messages explaining WHY changes were made
4. Push so next session has clean slate

---

## Violation Detection

**If you catch yourself:**
- Considering Claude Opus/Sonnet → VIOLATION of #1
- Adding GCP-specific validation → VIOLATION of #2
- Running 3 workflows simultaneously → VIOLATION of #3
- Creating abstract base classes → VIOLATION of #4

**Recovery:**
1. Stop immediately
2. Revert changes
3. Re-read relevant principle
4. Ask user for clarification if needed

---

## Amendment Process

**These principles can only be changed by explicit user request.**

If user says: "let's upgrade to Gemini Pro 3.0" → OK to change principle #1
If user says: "let's add a ValidationManager class" → OK to violate principle #4

Otherwise: **FOLLOW THESE PRINCIPLES STRICTLY**

---

**Last Updated:** 2026-02-09
**Approved By:** User (dc401)
