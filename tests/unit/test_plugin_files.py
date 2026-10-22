import json
import re
import tomllib

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


def test_plugin_readme_says_where_the_data_lives():
    text = (PLUGIN / "README.md").read_text(encoding="utf-8")
    section = text.split("## Where the data lives")[1].split("\n## ")[0]
    assert "`$PATH_FINDER_HOME`" in section and "`~/.path_finder`" in section and "`pyproject.toml`" in section
    assert "`path-finder --help` prints the directory in use" in section


def test_root_readme_gives_the_install_lines_for_users_and_developers():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "pipx install git+https://github.com/" in text and "pipx install path_finder-0.2.0-py3-none-any.whl" in text
    assert "claude plugin marketplace add " in text and "claude plugin install path-finder@path_finder" in text and "claude --plugin-dir plugin" in text
    assert "path-finder identify --role" in text and "path-finder list" in text and "path-finder window" in text
    assert "## Where the data lives" in text and "`$PATH_FINDER_HOME`" in text and "`~/.path_finder`" in text
    assert "pip install -e ." in text and "pytest tests" in text and "pip wheel . --no-deps" in text


def test_pyproject_builds_with_hatchling_and_vendors_the_eight_files():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["build-system"]["build-backend"] == "hatchling.build" and project["project"]["version"] == "0.2.0"
    assert project["project"]["readme"] == "README.md" and project["project"]["scripts"] == {"path-finder": "path_finder.cli:main"}
    wheel = project["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["path_finder"]
    vendored_discovery = {f"discovery/{name}.py": f"path_finder/_vendor/discovery/{name}.py" for name in ("discover", "paths", "processes", "registry", "identity")}
    assert wheel["force-include"] == {**vendored_discovery, "viz/watcher.py": "path_finder/_vendor/viz/watcher.py",
        "viz/web.html": "path_finder/_vendor/viz/web.html", "viz/index.html": "path_finder/_vendor/viz/index.html"}
    sdist = set(project["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])
    assert {*vendored_discovery, "viz/watcher.py", "viz/web.html", "viz/index.html", "pyproject.toml", "README.md", "path_finder/**"} <= sdist
    for source in wheel["force-include"]:
        assert (REPO_ROOT / source).is_file(), source
