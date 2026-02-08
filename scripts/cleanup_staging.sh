#!/bin/bash
#cleanup old staging artifacts before fresh run

echo "Cleaning stale staging artifacts..."

#remove old session files
rm -f generated/iterative_session_*.json
echo "✓ Removed old session files"

#remove old quality reports (will be regenerated)
rm -f generated/STATIC_QUALITY_REPORT.json
rm -f generated/PASSING_RULE_IDS.json  
rm -f generated/ELK_QUERIES.json
rm -f generated/ELK_VALIDATION_REPORT.json
rm -f generated/INTEGRATION_TEST_RESULTS.json
echo "✓ Removed old quality reports"

#clean temporary folders
rm -rf generated/sigma_rules_filtered
rm -rf generated/all_rules_backup
rm -rf generated/tests_backup
echo "✓ Removed temporary folders"

echo "Staging cleanup complete!"
