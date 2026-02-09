# Workflow Status Analysis

**Date:** 2026-02-08 18:45
**Status:** 🔍 INVESTIGATING

---

## Recent "Failed" Workflow Runs

### Why They Show as Failed (but aren't actual failures)

**Run 21806654041 - integration-test.yml (push trigger)**
- Triggered by: push event (commit 0930fee)
- Duration: 0s
- Conclusion: failure
- **Reason:** Workflow has condition `if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}`
- **Explanation:** When triggered by push, condition evaluates to false, no jobs run, GitHub marks as "failure"
- **Expected:** This is correct behavior - integration tests should only run after generate-detections succeeds or manual trigger

**Run 21806653894 & 21806595052 - cleanup-stale-artifacts.yml (push trigger)**
- Triggered by: push events
- Duration: 0s each
- Conclusion: failure
- **Reason:** Workflow should ONLY trigger on schedule (cron) or workflow_dispatch, NOT on push
- **Problem:** GitHub is somehow triggering this workflow on push events despite the on: clause
- **Investigation needed:** This should not happen - workflow file specifies:
  ```yaml
  on:
    schedule:
      - cron: '0 2 * * 0'
    workflow_dispatch:
  ```

---

## Current Active Test

**Run 21806722229 - generate-detections.yml**
- Status: IN PROGRESS (step 7/12)
- Trigger: workflow_dispatch (manual)
- Expected flow:
  1. Generate rules → create artifact
  2. Integration-test.yml triggers automatically (workflow_run)
  3. Tests rules against native ES
  4. Uploads test results

---

## Next Steps

1. **Wait for generate-detections to complete**
   - Should finish in ~2-3 minutes
   - Will create detection-rules artifact

2. **Monitor integration-test auto-trigger**
   - Should start automatically when generate-detections succeeds
   - Will test the workflow_run trigger

3. **Investigate cleanup-stale-artifacts false triggers**
   - Why is it being triggered by push events?
   - GitHub Actions bug or workflow file issue?

---

## User Feedback to Address

> "remember that the cleanup job can still exit 0 as non failed if it didn't find anything to delete i.e. from last clean up vs. an actual error where there was some sort of protection/lock as well"

**Current behavior:**
- Cleanup workflow already handles "nothing to clean" case:
  ```bash
  if git diff --quiet && git diff --cached --quiet; then
    echo "No stale artifacts to clean"
    echo "changes=false" >> $GITHUB_OUTPUT
  ```
- This exits 0 (success) when nothing to clean

**Issue:**
- The "failures" aren't from the cleanup logic itself
- They're from GitHub triggering the workflow on push (when it shouldn't)
- The workflow never actually runs, so it can't reach the cleanup logic

---

**Status:** Monitoring generate-detections run, will update when complete
