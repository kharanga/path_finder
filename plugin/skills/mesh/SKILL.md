---
name: mesh
description: List the live Claude Code sessions under the current folder with their roles and open the path_finder session web (/path-finder:mesh).
allowed-tools: [Bash]
---

Run exactly this:

```
pf() { if command -v path-finder >/dev/null 2>&1; then path-finder "$@"; else (cd "${CLAUDE_PLUGIN_ROOT}/.." && python3 -m path_finder.cli "$@"); fi; }
pf list --root "$PWD"
curl -s -m 1 http://127.0.0.1:4780/state >/dev/null || pf window --root "$PWD"
echo "http://127.0.0.1:4780/web"
```

Print the session lines as they came out, then the URL on its own line.
