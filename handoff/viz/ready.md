# Ready: V4 2026-10-08

## Done

- `viz/index.html`: the D2 capsule page extended per plan §6. Each capsule shows the label (role fallback, then name), a status pill (Working in green, Idle in grey; the capsule border turns green while working), an inbox badge at the top right when `inbox` > 0, a last-message line (`last_text`, one line, truncated at 90 characters with the full text as a tooltip), and a watching line ("👁 watching <label>" for every PID in `watching`, resolved to that session's label; a bare name shows as is). Unidentified sessions keep the dashed amber border. Capsules are grouped by folder as in D2, each carries `id="session-<pid>"` and `data-pid` for V5's connectors, and `main` is positioned for an SVG overlay.
- Data flow: `GET ./state` on load, then `EventSource("./events")`; the first frame is the snapshot, later frames are applied as deltas (`session`, `session_removed`, `message`; a message whose `pending_key` differs from its `key` replaces the pending row). The header shows session, identified, and working counts, the last change time, and "live" or "reconnecting"; while reconnecting the page polls `/state` every 2 s. Renders are coalesced to one per animation frame.
- `discovery/index.html` is left in place: the 4780 server the user told us not to stop serves it, and the watcher serves `viz/` first, so the viz page wins on any port the watcher owns. Delete the discovery copy at the port handover (Requests).
- `watcher.py replay --fixture PID=PATH ... --out-dir DIR [--speed N] [--max-gap S] [--until ISO]`: writes the fixtures' lines into fresh `DIR/<pid>.jsonl` files in timestamp order, pausing by the real gaps divided by `--speed` (0 writes everything at once, `--max-gap` caps a pause), stopping before the first line after `--until`. With `serve --fixture` tailing those files, this drives the page through the round trip without live sessions and can freeze it at any frame.

Files: `viz/index.html` (new), `viz/watcher.py`. Nothing else touched.

## How to test

Overnight acceptance (no live sessions, spare port):

```
R=$(mktemp -d); : > $R/32813.jsonl; : > $R/33993.jsonl
python3 viz/watcher.py serve --port 4797 --fixture 32813=$R/32813.jsonl --fixture 33993=$R/33993.jsonl &
sleep 1; curl -s -N http://127.0.0.1:4797/events > $R/events.txt &
python3 viz/watcher.py replay --fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl --out-dir $R --speed 10 --max-gap 0.5
sleep 1; kill %1 %2
python3 -c "
import json,sys
fr=[json.loads(f[5:]) for f in open('$R/events.txt').read().split('\n\n') if f.startswith('data:')]
ss=[f for f in fr if f['event']=='session']
need=('pid','label','role','name','cwd','status','inbox','last_text','watching')
print(len(fr), 'frames;', all(all(k in f for k in need) for f in ss), 'all fields;', sorted({f['status'] for f in ss}), sorted({f['inbox'] for f in ss}), sum(bool(f['watching']) for f in ss), 'watching frames')"
```

Expected: `25 frames; True all fields; ['IDLE', 'WORKING'] [0, 1] 8 watching frames`. Sampling `/state` during the replay shows the frames in order: (1) both IDLE, inbox 0, no last line; (2) 32813 WORKING, last line "second hello to fake-session-builder", watching [33993]; (3) 33993 inbox 1; (4) 33993 WORKING, last line "Hi again from fake-session-manager…", inbox 0; then 32813 reads the reply, the idle notice clears its watching, both end IDLE.

Freeze frame 3 and look at the page (any browser, or headless Chrome):

```
R=$(mktemp -d); : > $R/32813.jsonl; : > $R/33993.jsonl
python3 viz/watcher.py serve --port 4797 --fixture 32813=$R/32813.jsonl --fixture 33993=$R/33993.jsonl &
sleep 1; python3 viz/watcher.py replay --fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl --out-dir $R --speed 0 --until 2026-10-08T04:31:11.000Z
open http://127.0.0.1:4797/
```

Expected on the page: "fake manager" with a green WORKING pill, last line "second hello to fake-session-builder", "👁 watching fake builder"; "fake builder" IDLE with a pink badge "1" and no last line; header "2 sessions, 2 identified, 1 working … live". Verified here with headless Chrome (`--headless=new --timeout=4000 --screenshot`; the Claude in Chrome extension was not connected). Replaying without `--until` ends with both IDLE, badge gone, watching gone, last lines "Hi again from fake-session-builder…" and "Second hi back to fake-session-manager".

Suite: `python3 -m pytest tests` → 164 passed in 5.77s.

Morning live check (deferred by the user): stop the D2 server, run `python3 viz/watcher.py serve --root fake_session` on 4780, open the page, send one message with `notify_when_idle` between the fake sessions, compare with frames 1 to 4.

## Requests

- Port handover (manager): `python3 discovery/discover.py ui --stop`, then `python3 viz/watcher.py serve` on 4780, then delete `discovery/index.html` (viz-builder can do the delete once told; the role allows touching `discovery/` only for this move). Until then both copies exist and the watcher prefers `viz/`.
- Discovery-builder: `discover.py ui` should start `viz/watcher.py serve` instead of `http.server`, or be retired. Its health check keeps working either way.
- Validator: `replay` is new and untested on your side; `entries_in_time_order` carries untimestamped lines (`agent-name`) at the timestamp of the previous line in the same file.
- Plan §6 and SPEC name nine UI flow frames; no such document exists in the repo. The frames used here are derived from §6 and the round-trip timeline and are listed above under expected output. If the user has the frames, add them to `docs/`.

## Blocked

Nothing. The Claude in Chrome extension is not connected tonight, so the visual check used headless Chrome instead.
