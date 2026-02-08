# Stage 3 Progress - Integration Testing & LLM Judge Workflows

**Started:** 2026-02-08 18:00
**Status:** 🚧 IN PROGRESS

---

## Objective

Implement remaining backlog items from Stage 2:
1. Integration testing workflow (GitHub Actions)
2. LLM judge workflow (deployment decisions)
3. Context management optimization

---

## Completed Tasks

### ✅ Integration Testing Workflow Created

**File:** `.github/workflows/integration-test.yml`
**Created:** 2026-02-08 18:00

**Features:**
- Triggers automatically after `generate-detections.yml` succeeds
- Downloads generated rules artifact from previous workflow
- Installs native Elasticsearch (via apt, no Docker)
- Runs `scripts/integration_test_ci.py` with Gemini Pro refinement enabled
- Calculates precision/recall/F1 metrics per rule
- Auto-refines failing rules using Gemini Pro
- Commits refined rules back to repo
- Uploads detailed test results as artifacts
- Fails build if rules don't meet thresholds

**Workflow Steps:**
1. Download artifacts (detection rules from generator)
2. Setup Python + dependencies
3. Authenticate to GCP (for Gemini refinement)
4. Install ES dependencies
5. Run integration tests with refinement
6. Parse results (total/passed/failed/refined counts)
7. Generate markdown test report
8. Upload results as artifacts
9. Commit refined rules (if any)
10. Report success/failure

**Thresholds:**
- Precision: ≥ 0.80
- Recall: ≥ 0.70
- Rules below threshold trigger automatic refinement

**Test Environment:**
- Ubuntu latest runner
- Native Elasticsearch (via apt)
- Python 3.11
- Gemini Pro for refinement
- 30-minute timeout

---

## In Progress

### 🚧 Testing Integration Workflow

**Next Steps:**
1. Trigger integration test workflow manually
2. Verify ES installation works in GitHub runner
3. Check test results and refinement process
4. Validate artifact uploads

**Expected Output:**
- `integration_test_results.yml` artifact
- `test_report.md` summary
- Refined rules committed (if needed)

---

## Pending Tasks

### High Priority

1. **LLM Judge Workflow**
   - Create `.github/workflows/llm-judge.yml`
   - Read ES integration test results
   - Evaluate rules empirically (based on actual metrics)
   - Make deployment decision (APPROVE/CONDITIONAL/REJECT)
   - Trigger refinement on REFINE decision
   - Move approved rules to staged_rules/

2. **Test Integration Workflow**
   - Manual trigger test
   - Verify ES deployment
   - Check refinement logic
   - Validate artifact creation

### Medium Priority

3. **Context Management Optimization**
   - Track token usage between agent stages
   - Implement state pruning strategy
   - Prevent context pollution
   - Document in CONTEXT_MANAGEMENT.md

4. **Bootstrap Script Enhancement**
   - Update `scripts/bootstrap.sh`
   - Add ES-native setup instructions
   - Remove any Sigma references
   - Add validation testing steps

### Low Priority

5. **Documentation Updates**
   - Update README.md with GitHub Actions workflows
   - Create DEPLOYMENT_GUIDE.md
   - Add troubleshooting section
   - Document refinement process

---

## Technical Notes

### Integration Test Workflow Design

**Artifact Chain:**
```
generate-detections.yml → detection-rules artifact
                                    ↓
integration-test.yml downloads artifact → tests rules → integration-test-results artifact
                                                              ↓
llm-judge.yml downloads results → evaluates → staged rules (PR creation)
```

**Refinement Logic:**
- Each rule tested against embedded test cases (TP/FN/FP/TN)
- Metrics calculated from actual ES query results
- Rules failing thresholds auto-refined by Gemini Pro
- Refined rules replace originals in generated/detection_rules/
- Max 3 refinement iterations per rule

**Why Native ES:**
- No Docker overhead in GitHub runners
- Faster startup (apt vs container pull)
- Simpler cleanup (no container management)
- User explicitly requested: "didn't you find it easier just to use the ubuntu package"

---

## Success Criteria

### Integration Testing
- [ ] Workflow triggers after generation completes
- [ ] ES installs and starts successfully
- [ ] Rules tested against embedded payloads
- [ ] Metrics calculated correctly (precision/recall)
- [ ] Refinement triggers on failures
- [ ] Refined rules committed to repo
- [ ] Artifacts uploaded successfully

### LLM Judge
- [ ] Reads integration test results
- [ ] Evaluates based on empirical metrics
- [ ] Makes deployment decision
- [ ] Moves approved rules to staged_rules/
- [ ] Creates PR for human review

### Overall
- [ ] Full pipeline: CTI → Rules → Tests → Refinement → Judge → PR
- [ ] No manual intervention needed until PR review
- [ ] All workflows complete within GitHub runner limits
- [ ] Clean artifact management (30-day retention)

---

## Commits This Session

```
(pending - workflow created but not yet committed)
```

---

## Next Immediate Steps

1. Commit integration-test.yml workflow
2. Trigger manual test run
3. Monitor workflow execution
4. Debug any ES installation issues
5. Verify refinement process works
6. Proceed to LLM judge workflow creation

---

**Status:** Integration testing workflow created, ready for testing
**Blocker:** None
**ETA:** Integration test validation (30 min), LLM judge (1 hour)
