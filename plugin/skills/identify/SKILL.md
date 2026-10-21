---
name: identify
description: Register this session's role with path_finder discovery (/path-finder:identify <role>). Use when the user says what role this session has or asks to identify the session.
argument-hint: <role>
allowed-tools: [Bash, AskUserQuestion]
---

Role given: `$ARGUMENTS`

If the role above is blank, ask the user with AskUserQuestion, one question: "What is this session's role?" Use the answer as `<role>`.

Then run exactly this, with `<role>` filled in:

```
pf() { if command -v path-finder >/dev/null 2>&1; then path-finder "$@"; else python3 "${CLAUDE_PLUGIN_ROOT}/../discovery/discover.py" "$@"; fi; }
pf identify --role "<role>" && pf self
```

Print the one JSON line that `self` returns. If the command exits non-zero, show its stderr line and stop.
