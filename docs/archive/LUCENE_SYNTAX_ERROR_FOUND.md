# Lucene Syntax Error Found - 2026-02-08 18:50

## Discovery

Local validation with luqum caught a Lucene syntax error that would have failed in Elasticsearch.

## Error Details

**Rule:** akira_ransomware_-_service_stop_for_defense_evasion.yml

**Error:**
```
Invalid Lucene syntax: Illegal character '/y*)) OR ...' at position 92
```

**Problematic Query:**
```lucene
event.code:1 AND ( (process.name:(*net.exe* OR *net1.exe*) AND process.command_line:(*stop* /y*)) OR ...
```

**Issue:** The forward slash `/` in `/y*` is an illegal character in Lucene query syntax.

## Impact

- **Without local validation:** Would have wasted CI minutes deploying to Elasticsearch and failing
- **With local validation:** Caught before CI run, can fix immediately

## Root Cause

LLM (Gemini Flash) generated a Lucene query with unescaped special characters. The command-line parameter `/y` (Windows "yes" flag) needs to be:
1. Escaped: `\/y*`, OR
2. Quoted: `"/y"`, OR
3. Pattern-matched: `*\/y*`

## Correct Query

**Option 1: Escape the slash**
```lucene
event.code:1 AND ( (process.name:(*net.exe* OR *net1.exe*) AND process.command_line:(*stop* \\\/y*)) ...
```

**Option 2: Use wildcard pattern**
```lucene
event.code:1 AND ( (process.name:(*net.exe* OR *net1.exe*) AND process.command_line:(*stop* AND *y*)) ...
```

**Option 3: Simplify (recommended)**
```lucene
event.code:1 AND process.name:(*net.exe* OR *net1.exe*) AND process.command_line:(*stop* AND *y*)
```

## Validation Results

**Before fix:**
```
Total: 3 rules
Valid: 2
Invalid: 1  <-- service_stop_for_defense_evasion.yml
```

**After fix:** (pending)

## Lesson Learned

✅ **Local validation with luqum is critical** - catches syntax errors before CI
✅ **Lucene special characters need escaping:** `/`, `\`, `+`, `-`, `&&`, `||`, `!`, `(`, `)`, `{`, `}`, `[`, `]`, `^`, `"`, `~`, `*`, `?`, `:`, ` `

## Fix Applied

**Commit:** defa064

**Changes:**
- Added Lucene special character escaping guidance to `detection_agent/prompts/detection_generator.md`
- Explicit warning: **DO NOT use literal slashes or special chars** in command-line patterns
- Examples of correct vs wrong patterns:
  - ✅ CORRECT: `*stop* AND *y*` (wildcard around parameters)
  - ❌ WRONG: `*stop* /y*` (literal `/` causes parse error)
  - ✅ CORRECT: `*quiet*`, `*all*`, `*force*` (Windows flags wildcarded)

## Next Steps

1. ✅ Fix Lucene syntax guidance in prompt - DONE
2. Push commit and re-run generate-detections workflow
3. Validate new rules locally with luqum
4. Proceed to integration testing once rules are clean

---

**Status:** Fix committed (defa064), ready to re-run workflow
