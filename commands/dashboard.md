---
description: Start the live Claude Code sessions dashboard and print its URL
argument-hint: "[demo|stop]"
allowed-tools: Bash
---

Manage the cc-dashboard server. The plugin root is `${CLAUDE_PLUGIN_ROOT}`. The argument is `$ARGUMENTS` (empty, `demo`, or `stop`).

Steps:

1. If the argument is `stop`: run `pkill -f "webhook/server.js" ; echo stopped` and report the result. Done.
2. Otherwise check whether something already listens on port 4747: `lsof -nP -iTCP:4747 -sTCP:LISTEN -t`. If it prints a PID, the dashboard is already running; tell the user to open http://127.0.0.1:4747/ and stop.
3. Otherwise start the server in the background and detach it so it outlives this turn:
   - with no argument: `nohup node "${CLAUDE_PLUGIN_ROOT}/webhook/server.js" > /tmp/cc-dashboard-server.log 2>&1 &`
   - with `demo`: `nohup node "${CLAUDE_PLUGIN_ROOT}/webhook/server.js" --demo > /tmp/cc-dashboard-server.log 2>&1 &`
   Then wait one second and run `cat /tmp/cc-dashboard-server.log`.
4. Report the dashboard URL printed in the log (default http://127.0.0.1:4747/), the events file it tails, and that `/dashboard stop` stops it. If the log shows `EADDRINUSE` or no URL, show the log contents instead.

Never run the server in the foreground and never change files in the plugin directory.
