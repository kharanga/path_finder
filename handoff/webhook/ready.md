# Ready: W1 verify hook behavior (re-review), W2 runtime manifest (PASS)

## Done

- W1 live test complete. Catch-all installed by the manager at 06:01Z; 57 records captured across four sessions by 06:05Z. This session sent one `SendMessage` with `notify_when_idle: true` to `path-finder-e5`, the recipient's `UserPromptSubmit` and later `Stop` both appeared in the log.
- `SPEC.md` §6: all four W-U findings filled in with quoted evidence, plus observed extra fields and two notes for the manager (`Notification` fires on permission prompts; `~/.claude/sessions/<pid>.json` `status` can back up a missed `Stop`).
- `docs/webhook/hooks.md`: raw input shape table rewritten from the observed records.
- `webhook/hooks/capture-raw.js`: entry point guarded with `import.meta.url === pathToFileURL(process.argv[1]).href`, per review note 1. A bare import no longer reads stdin or writes a record.
- Drafts present but not part of this handoff: `webhook/hooks/dashboard-hook.js` (W3), `webhook/schema.js`, `webhook/state.js`, `webhook/liveness.js`, `webhook/tail.js`, `webhook/server.js` (W5), `webhook/fake.js` (W4). Not started per the manager's rule; review them when their task IDs are assigned.

## How to test

Findings check:

```
cd /Users/khangnguyen/Documents/path_finder
sed -n '/^Findings:/,/^Open design questions/p' SPEC.md
```

Expected: W-U1 to W-U4 each have a finding with timestamps or quoted record fragments.

Raw log cross-check, redacted summary only, no values:

```
python3 -c "
import json
for line in open('/tmp/cc-dashboard-raw.jsonl'):
    r=json.loads(line); k=r['input'].get('kept',{})
    claude=[a['pid'] for a in r['ancestors'] if 'claude' in a['command']]
    print(r['captured_at'][11:19], claude[:1], k.get('hook_event_name'), k.get('tool_name',''), k.get('tool_input',{}).get('to',''))
"
```

Expected: a `PostToolUse SendMessage path-finder-e5` line for PID 52134 at 06:03:57, a `UserPromptSubmit` for PID 40707 at 06:04:10, a `Stop` for PID 40707 at 06:04:57, and no line containing prompt or message text.

Import guard:

```
cd /Users/khangnguyen/Documents/path_finder
wc -l /tmp/cc-dashboard-raw.jsonl
node -e 'import("./webhook/hooks/capture-raw.js").then(m => console.log(Object.keys(m).length, "exports"))' < /dev/null
wc -l /tmp/cc-dashboard-raw.jsonl
```

Expected: `8 exports` and the two line counts differ only by hooks other sessions fired in between, never by a record whose `argv` is empty and whose `cwd` is this repo at the same second. Cleaner: set `CC_DASHBOARD_RAW_LOG=/tmp/guard-test.jsonl` for the import and confirm that file is not created.

## Requests

1. Manager: W1 is done, so the catch-all can come out of `~/.claude/settings.json`. Two options. Remove all nine hook entries now, which stops the roughly 35 ms per tool call overhead in every session. Or leave it until W3 is assigned and swap it for the real snippet in one edit. The log is redacted either way. I recommend swapping at W3 to save you an edit, and I will delete `/tmp/cc-dashboard-raw.jsonl` when told.
2. Manager: `npm install` in `webhook/` creates `webhook/package-lock.json` even with zero dependencies (review note 2). Please add `webhook/package-lock.json` to `.gitignore`, or drop the `npm install` step from `CLAUDE.md` since nothing is fetched.
3. Manager, for M3: two states exist that §3 does not model, a session waiting on a permission prompt (`Notification` hook, ListAgents shows `waiting`) and a missed `Stop` after a user interrupt. Options are in §6 W-U4. Decide whether W3 should emit a fifth state or whether W5 should poll `~/.claude/sessions/<pid>.json` `status`.
4. Manager: the W5 contract now says static files from `frontend/` are served. Acknowledged; the draft server does not do that yet and will when W5 is assigned.

## Blocked

Empty.
