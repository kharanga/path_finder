# Ready: V14 2026-10-20

## Done

Readable arrows and task hover, both in `viz/web.html`; the watcher is unchanged.

Arrows:

- `readOpacity(message, now)` replaces `flashRemaining`. A READ arrow is visible for `READ_LINGER_MS` = 30 s after `read_at`: full opacity at the read, easing to `READ_MUTED_OPACITY` = 0.55 over the first 3 s (the V5 flash), then muted at 0.55 with its label until the 30 s are up. PENDING and IN_INBOX are unchanged; FAILED stays until resolved; the ten-minute arrow horizon still applies.
- A reply on the reversed pair ends it early: `replyAfterRead(message)` finds the earliest message from the receiver back to the sender sent after `read_at`; from that message's `sent_at` the old arrow fades over `READ_FADE_MS` = 600 ms and is gone, while the reply arrow appears at once. One arrow per (from, to) pair still holds: a newer message on the same pair replaces the lingering one.
- Pod layout for the overlap window: while both directions are visible, the fading arrow takes the lower lane and the live one keeps the upper lane (`entry.lower`), instead of the key-order rule, so the new arrow never jumps; with two live arrows (both PENDING) key order still decides. `positionNodes(ring, lowerLane)` grows the pod graph (`cy + lift + LABEL_HEIGHT/2 + 6`, 185 px today) while any reversed pair is visible, so the lower label stays inside the graph and off the caption. Rings are unaffected.

Task panel:

- Hovering a card shows its full SPEC text inline, the same `.tfull` block the V9 click opens, via `.task:hover` CSS and a `hover` class kept in `hoveredTaskId` across re-renders (`mouseenter` / `mouseleave`); the title wraps too. It closes when the pointer leaves; click still pins it (`.open`). The text wraps inside the card (`pre-wrap`, `break-word`), the panel scrolls, nothing is clipped at the panel edge.

Files: `viz/web.html`.

## How to test

Round trip frozen at moments (spare port; 4780 is the manager's):

```
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
S=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $S --speed 0 --until 2026-10-08T04:31:15.000Z
python3 viz/watcher.py serve --port 4792 --no-log --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
```

Expected: at 15.000 (4 s after the builder read) the manager → builder arrow is still on the pod, muted, with its `second hello … ✓✓ Read` label; it would stay until 41.097. At 17.000 (reply sent 16.750) the reply `Second hi back … Pending` is drawn above, the old arrow is fading below inside a taller graph, and by 17.350 only the reply remains; at 17.700 the reply is read and starts its own 30 s. In the live replay (`--speed 1`) the same sequence plays in real time. Task panel: hover any card, the full text opens under it and wraps within the panel; move the pointer away, it closes; click, it stays open; hover another card while one is pinned, both show.

Checked here: harness `web_linger.json` (read → 1.0, +5 s 0.55 with label, +29 s 0.55, +31 s gone) and `web_linger_reply.json` (advance to 16.75, reply frame: old 0.55 on the lower lane, new PENDING above; +0.3 s old 0.50; +0.7 s old gone; reply read 1.0; +10 s 0.55); `web_hover.json` (`hover` class on enter, off on leave, `open` on click, hover another while pinned, kept across a render tick); `cdp_hover.mjs` in headless Chrome at 720 px: moving the pointer onto V9 makes `.tfull` `display: block` with the card at 468 px tall and its right edge inside the panel, moving away returns it to `none`; frames `webv14_a.png` (15.0), `webv14_b.png` (17.0), `webv14_c.png` (17.7) at 380 px; validator's `test_pod_labels_stay_inside_the_graph` passes.

Suite: `python3 -m pytest tests` → 340 passed, 9 failed, all expected pins in `tests/integration/test_web_render.py`: arrows that used to be gone 3 s after the read are now present (`test_read_clears…`, `test_reply_shows…`, `test_idle_notice_pulses…`, `test_round_ends…` expect `paths == []`), and the six/seven/ten geometry tests pin the set of visible arrow keys and label visibility, which now includes the lingering READ arrows.

## Requests

- Manager: nothing to restart; the page is served from the file.
- Validator: re-pin the 9; add the 30 s linger (visible at 29 s, gone at 31 s), the reversed-reply fade (old arrow 0.55 → 0 within 600 ms of the reply's `sent_at`, lower lane, graph grown, label inside), and the hover (`hover` class, `.tfull` shown, closes on leave, click pins) — my scratchpad has `web_linger.json`, `web_linger_reply.json`, `web_hover.json`, `cdp_hover.mjs`.
- Docs (user): plan §6 replace the 3 s flash with the 30 s linger and the reply rule; note the hover expansion.

## Blocked

Nothing.
