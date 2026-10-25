---
name: mesh
description: List the live Claude Code sessions under the current folder with their roles and open the path_finder session web (/path-finder:mesh).
allowed-tools: [Bash]
---

Run exactly this:

```
pf() { if command -v path-finder >/dev/null 2>&1; then path-finder "$@"; else (cd "${CLAUDE_PLUGIN_ROOT}/.." && python3 -m path_finder.cli "$@"); fi; }
pf list --root "$PWD"
pf window --root "$PWD" | grep -o 'http://127\.0\.0\.1:[0-9]*/web' | tail -n 1
```

Print the session lines as they came out, then the URL on its own line. If any line has `"role": null`, add one sentence: that session has an auto-generated name, so its human should run `/rename <folder>_<role>` (or just `/rename <role>`) in it, where `<folder>` is this project folder's name; `path-finder identify --role <role>` is the explicit override. `window` picks the port itself: it reuses the watcher whose `/state` root is this folder, walking up from 4780, or starts one on the first silent port, so the URL is whatever its last line names, not always 4780.
