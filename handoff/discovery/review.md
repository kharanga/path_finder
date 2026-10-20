# Review: D4 2026-10-20

PASS

## Verified against SPEC D4

- `python3 discovery/discover.py ui` exits 2 with argparse `invalid choice: 'ui' (choose from identify, self, list, done)`.
- `identify --role ""` and `identify --role "   "` exit 2 with `role is blank: pass the role your human entered, for example --role manager` on stderr and nothing on stdout; `discovery/identity/` is untouched (my own identity file unchanged, `self` still exits 0). The check happens before `own_session`, so it also holds outside a Claude session.
- `discovery/index.html` deleted, `discovery/` holds only `discover.py`, `identity/`, `sessions.json`, `sessions.json.lock`. `.gitignore` no longer lists `discovery/ui.log` or `discovery/ui.pid`. No `ui`, `UI_`, `time`, or `urllib` left in `discover.py`.
- Port 4780 is served by `viz/watcher.py serve` (not started by me, untouched), so the handover dependency holds.

## Tests

- `tests/conftest.py`: the two `UI_LOG` and `UI_PID` monkeypatch lines removed; no ui test existed, so nothing else dropped.
- `tests/unit/test_discover.py`: `ui` added to the rejected-commands list; new `test_command_identify_blank_role_exits_2_and_writes_nothing` (three blank variants, asserts `own_session` is never consulted and no identity or directory file appears), `test_command_identify_stores_the_role_stripped`, `test_module_has_no_ui_leftovers`.
- `tests/integration/test_discovery_cli.py`: `test_ui_is_rejected_by_argparse`, `test_identify_with_blank_role_exits_2_and_writes_nothing` (two variants, directory listing identical before and after).
- `python3 -m pytest tests` → 246 passed.

## Notes

- `.claude/roles/discovery-builder.md` line 27 still lists `ui` and `ui --stop` as in D2. Manager item.
- `docs/plan-visualization.md` line 8 still introduces the work as extending the `discover.py ui` page; lines 51 and 127 already record the retirement. User item, cosmetic.
- `viz/watcher.py` keeps `discovery/` as a static fallback root (`STATIC_DIRS`), so `sessions.json` and `identity/*.json` are still reachable over HTTP on 4780. The D2 page used `sessions.json` that way; with the page gone it may be unneeded. For the viz-builder to decide, not a D4 failure.
- `git status` shows `handoff/viz/ui-frames.png` renamed to `docs/ui-frames.png`, and untracked `viz/web.html`, `handoff/viz/v7-animation.html`, `handoff/viz/v7-styles.html`: V7 work in flight, not reviewed here.
