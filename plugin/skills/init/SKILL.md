---
name: init
description: Create the empty agent-workspace placeholders (CLAUDE.md, SPEC.md, .claude/roles/, handoff/<builder>/) in the current folder with path-finder init (/path-finder:init <builder names>). Use when the user asks to scaffold, initialize, or lay out the workspace files before filling them in.
argument-hint: <builder names>
allowed-tools: [Bash, AskUserQuestion]
---

Builder names given: `$ARGUMENTS`

If the names above are blank, ask the user with AskUserQuestion, one question: "Which builders will this workspace have? Give one or more short names, each the folder or area it will own (for example api web)." Split the answer on spaces and commas into `<names>`.

Then run exactly this, with one `--builder` per name:

```
pf() { if command -v path-finder >/dev/null 2>&1; then path-finder "$@"; else (cd "${CLAUDE_PLUGIN_ROOT}/.." && python3 -m path_finder.cli "$@"); fi; }
pf init --root "$PWD" --builder <name1> --builder <name2>
```

Print the created and exists lines as they came out. If the command exits non-zero, show its output and stop.

End by telling the user: the files are empty placeholders; run your workspace-setup skill (setup-agent-workspace) now to fill them in.
