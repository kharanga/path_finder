---
name: declare-role
description: Declare or change this session's role label (manager, validator, webhook-builder, reviewer, anything short) so it appears under this session's body on the cc-dashboard. Use when the user says what role this session has, asks to label or tag the session, or invokes /declare-role.
allowed-tools: Bash
---

Label this Claude Code session with a role on the live sessions dashboard.

Run exactly one command, replacing `<role>` with the role the user gave (1 to 40 characters: letters, digits, spaces, `_`, `-`). If the user gave no role, ask for one first.

```
node "${CLAUDE_PLUGIN_ROOT}/webhook/declare-role.js" "<role>"
```

Outcomes:

- Exit 0 with no output: the role is recorded. Tell the user in one line that the dashboard now shows the role under this session, and that it is remembered for future sessions started in this folder.
- Exit 1 with one line on stderr: show that line. `usage:` means the role text is invalid. `no claude process found` or `no registry entry` means the command did not run inside a Claude Code session. `cannot write` means `~/.claude/dashboard/` is not writable.

Do not edit any file yourself; the script writes the event and the saved role.
