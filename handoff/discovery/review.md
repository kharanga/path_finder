# Review: P2 round 2 2026-10-21

PASS

Round 1 item: the README's keep-install now matches a real marketplace. `.claude-plugin/marketplace.json` at the checkout root names the marketplace `path_finder` with one plugin, `path-finder`, source `./plugin`; `claude plugin validate .` and `claude plugin validate plugin` both pass; `claude plugin marketplace add /Users/khangnguyen/Documents/path_finder` registered it (`Successfully added marketplace: path_finder (declared in user settings)`), `claude plugin marketplace list` showed `path_finder` with the folder source, and `claude plugin marketplace remove path_finder` took it out again, leaving no `path_finder` reference in `~/.claude/settings.json`. `claude plugin install` was not run (the manager's instruction: it enables the plugin in the user's settings).

Round 1 (FAIL) item for the record: plugin/README.md keep-install pointed at a checkout with no marketplace manifest.

## Verified against SPEC P2

- `claude plugin validate plugin` → `Validation passed` (Claude Code 2.1.305), with the two directory-submission notes (no icon, no LICENSE) that do not change the result.
- Manifest: `plugin/.claude-plugin/plugin.json` names `path-finder` 0.1.0 with description, author and keywords; no `hooks`, `agents`, `mcpServers` or `commands` keys, no `hooks/` folder; two skills under `plugin/skills/`.
- Trial session: `claude --plugin-dir plugin -p "List every skill … path-finder"` printed exactly `path-finder:identify` and `path-finder:mesh`.
- `/path-finder:identify builder` headless with `--allowedTools Bash`: once with no `path-finder` on PATH (the `discover.py` fallback) and once with the P1 scratch venv on PATH (the CLI branch). Each run printed the `self` JSON line with role and label `builder` and wrote `discovery/identity/<its pid>.json` (96818, 97118) for that headless session; the validator's own identity file was not touched (role `validator`, verified after), and the next `discover.py list` dropped the dead sessions' files. With no role argument the headless session reported that AskUserQuestion is not available non-interactively and ran nothing (no Bash call, no file); the interactive prompt itself cannot be exercised with `-p`, the skill text asks the one question the SPEC names.
- `/path-finder:mesh` headless while the manager's 4780 watcher answered: printed the five live sessions under the checkout (the four team sessions plus itself, unidentified) and `http://127.0.0.1:4780/web`; no window started. The `window` branch was verified under P1.
- Both skill snippets run under `zsh -c` and `bash -c` with `CLAUDE_PLUGIN_ROOT=<checkout>/plugin` through the fallback branch: `pf self` prints this session's line via `discover.py`; `pf list --root "$PWD"` through `python3 -m path_finder.cli` prints the four sessions; the curl probe skips `window` while 4780 answers.
- README: the trial line `claude --plugin-dir plugin`, the keep-install lines with the manifest's location, the hooks paragraph, and the CLI note are present.

## Tests

- `tests/unit/test_plugin_files.py`: manifest name and absent hook/agent/server keys, the two skills and their frontmatter, the identify snippet (AskUserQuestion, `identify --role` then `self`, the `discover.py` fallback), the mesh snippet (`list --root "$PWD"`, the 4780 probe before `window`, the URL), the README's install lines and hooks paragraph.
- `tests/unit/test_plugin_files.py` also pins the marketplace manifest (name, plugin, source) against the README's install lines.
- `python3 -m pytest tests` → 401 passed.

## Notes

- The headless trial sessions appear briefly on the live 4780 page as unidentified `path-finder-NN` nodes and vanish when the watcher drops their registry entries.
- For a public directory submission the validator also wants an icon and a repository LICENSE; the user's choice, as ready.md says.
