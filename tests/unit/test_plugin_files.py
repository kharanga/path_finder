import json
import re

from conftest import REPO_ROOT

PLUGIN = REPO_ROOT / "plugin"


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    assert match, path
    fields = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in fields.items()}, match.group(2)


def test_manifest_names_the_plugin_and_declares_no_hooks_agents_or_servers():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "path-finder" and manifest["version"] and manifest["description"]
    assert not ({"hooks", "agents", "mcpServers", "commands"} & set(manifest))
    assert not (PLUGIN / "hooks").exists() and not (PLUGIN / "hooks.json").exists()
    assert sorted(p.name for p in (PLUGIN / "skills").iterdir()) == ["identify", "mesh"]


def test_identify_skill_asks_for_the_role_then_runs_identify_and_self():
    fields, body = frontmatter(PLUGIN / "skills" / "identify" / "SKILL.md")
    assert fields["name"] == "identify" and fields["argument-hint"] == "<role>" and fields["allowed-tools"] == "[Bash, AskUserQuestion]"
    assert "$ARGUMENTS" in body and "AskUserQuestion" in body and "What is this session's role?" in body
    assert 'identify --role "<role>" && pf self' in body
    assert 'command -v path-finder' in body and '"${CLAUDE_PLUGIN_ROOT}/../discovery/discover.py"' in body


def test_mesh_skill_lists_sessions_starts_the_window_only_when_4780_is_silent_and_prints_the_url():
    fields, body = frontmatter(PLUGIN / "skills" / "mesh" / "SKILL.md")
    assert fields["name"] == "mesh" and fields["allowed-tools"] == "[Bash]"
    assert 'pf list --root "$PWD"' in body
    assert 'curl -s -m 1 http://127.0.0.1:4780/state >/dev/null || pf window --root "$PWD"' in body
    assert 'echo "http://127.0.0.1:4780/web"' in body
    assert 'python3 -m path_finder.cli' in body


def test_readme_gives_both_install_lines_and_says_hooks_are_absent():
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert "claude --plugin-dir plugin" in readme and "claude plugin install" in readme and "marketplace" in readme
    assert "Hooks are deliberately absent" in readme


def test_marketplace_manifest_at_the_checkout_root_lists_the_plugin_the_readme_installs():
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "path_finder"
    assert [(plugin["name"], plugin["source"]) for plugin in manifest["plugins"]] == [("path-finder", "./plugin")]
    assert (REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json").is_file()
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    assert "claude plugin marketplace add /Users/khangnguyen/Documents/path_finder" in readme
    assert "claude plugin install path-finder@path_finder" in readme and ".claude-plugin/marketplace.json" in readme
