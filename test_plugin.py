"""Run with: python test_plugin.py"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROLES = ["architect", "builder", "researcher", "runner", "scout"]
# Champs de frontmatter qu'un agent de plugin voit ignorés.
IGNORED = ("hooks", "mcpServers", "permissionMode")


if __name__ == "__main__":
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    assert manifest["name"] == marketplace["name"] == marketplace["plugins"][0]["name"] == "claudeskills"
    assert marketplace["plugins"][0]["source"] == "./"

    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]), "release version required"
    entry = marketplace["plugins"][0]
    assert "version" not in entry, "keep plugin.json as the only version source"
    settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    for config, variable in [(manifest, "CLAUDE_PLUGIN_ROOT"), (settings, "CLAUDE_PROJECT_DIR")]:
        hook = config["hooks"]["PostToolUse"][0]
        assert hook["matcher"] == "Agent|Task|TaskOutput"
        command = hook["hooks"][0]["command"]
        assert command == 'python "${' + variable + '}/.claude/hooks/agent_identity.py"'
        assert (ROOT / ".claude/hooks/agent_identity.py").is_file()

    agents = [ROOT / path for path in manifest["agents"]]
    assert sorted(path.stem for path in agents) == ROLES, manifest["agents"]
    assert sorted(path.stem for path in (ROOT / ".claude/agents").glob("*.md")) == ROLES
    for path in agents:
        head = path.read_text(encoding="utf-8").split("---")[1]
        assert not re.search(rf"^({'|'.join(IGNORED)}):", head, re.M), f"{path.name}: champ ignoré par le plugin"
    assert (ROOT / manifest["skills"] / "quota-orchestrator/SKILL.md").is_file()

    hook = manifest["hooks"]["SessionStart"][0]
    assert {"startup", "resume", "clear", "compact"} <= set(hook["matcher"].split("|"))
    target = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"]+)", hook["hooks"][0]["command"]).group(1)
    assert (ROOT / target).samefile(ROOT / "CLAUDE.md"), target

    print("PASS: manifestes, cinq rôles, skill, version unique et hooks SessionStart/PostToolUse.")
