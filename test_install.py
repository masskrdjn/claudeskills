"""Run with: python test_install.py"""

import importlib.util
import json
import subprocess
import sys
import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "install.py"
EXPECTED = [
    Path("CLAUDE.md"),
    Path(".claude/settings.json"),
    *(Path(".claude/agents") / name for name in ("architect.md", "builder.md", "researcher.md", "runner.md", "scout.md")),
    Path(".claude/skills/quota-orchestrator/SKILL.md"),
    Path(".claude/hooks/agent_identity.py"),
]


@contextmanager
def workspace_directory():
    # Ordinary mkdir avoids Windows fixture ACLs inherited from mkdtemp's 0700.
    path = ROOT / ("_install_test_" + uuid.uuid4().hex)
    os.mkdir(path)
    try:
        yield path
    finally:
        assert path.parent.resolve() == ROOT
        shutil.rmtree(path)


def run(target, *args, success=True):
    result = subprocess.run([sys.executable, str(SCRIPT), *args, str(target)], capture_output=True, text=True)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    return result


def snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


if __name__ == "__main__":
    with workspace_directory() as temporary:
        base = Path(temporary)

        empty = base / "empty"
        empty.mkdir()
        run(empty)
        assert all((empty / path).is_file() for path in EXPECTED)
        assert "claudeskills:routing:start" in (empty / "CLAUDE.md").read_text(encoding="utf-8")
        assert not (empty / "README.md").exists()
        first = snapshot(empty)
        run(empty)
        assert snapshot(empty) == first

        existing = base / "existing"
        (existing / ".claude/agents").mkdir(parents=True)
        original_instructions = "# user rules\n"
        custom_hook = {"type": "command", "command": "echo custom"}
        custom_entry = {"matcher": "Agent|Task|TaskOutput", "hooks": [custom_hook]}
        other_entry = {"matcher": "Read", "hooks": [{"type": "command", "command": "echo read"}]}
        original_settings = {"effortLevel": "low", "custom": 7, "permissions": {"allow": ["Bash(ls:*)"]},
                             "hooks": {"PostToolUse": [custom_entry, other_entry],
                                       "SessionStart": [{"hooks": [{"type": "command", "command": "echo start"}]}]}}
        (existing / "CLAUDE.md").write_text(original_instructions, encoding="utf-8")
        (existing / ".claude/settings.json").write_text(json.dumps(original_settings, indent=2), encoding="utf-8")
        custom_agent = existing / ".claude/agents/scout.md"
        custom_agent.write_text("local scout\n", encoding="utf-8")
        result = run(existing)
        merged_instructions = (existing / "CLAUDE.md").read_text(encoding="utf-8")
        merged_settings = json.loads((existing / ".claude/settings.json").read_text(encoding="utf-8"))
        assert merged_instructions.startswith(original_instructions)
        assert merged_instructions.count("claudeskills:routing:start") == 1
        assert merged_settings["effortLevel"] == "low" and merged_settings["custom"] == 7
        assert merged_settings["permissions"]["allow"] == ["Bash(ls:*)"]
        assert merged_settings["permissions"]["deny"] and merged_settings["modelSettings"]
        hooks = merged_settings["hooks"]["PostToolUse"]
        assert len(hooks) == 2 and hooks[0]["hooks"][0] == custom_hook and hooks[1] == other_entry
        assert len(hooks[0]["hooks"]) == 2 and "agent_identity.py" in hooks[0]["hooks"][1]["command"]
        assert merged_settings["hooks"]["SessionStart"] == original_settings["hooks"]["SessionStart"]
        assert "effortLevel conservé" in result.stderr
        assert custom_agent.read_text(encoding="utf-8") == "local scout\n"
        assert "préservé avec avertissement" in result.stdout
        assert list((existing / ".claudeskills-backup").glob("*/CLAUDE.md"))
        before = snapshot(existing)
        second = run(existing)
        assert "bloc claudeskills existant" not in second.stderr
        after = snapshot(existing)
        assert after == before, {
            "added": sorted(map(str, after.keys() - before.keys())),
            "changed": sorted(str(path) for path in after.keys() & before.keys() if after[path] != before[path]),
        }

        dry = base / "dry"
        dry.mkdir()
        run(dry, "--dry-run")
        assert snapshot(dry) == {}

        invalid = base / "invalid"
        (invalid / ".claude").mkdir(parents=True)
        (invalid / ".claude/settings.json").write_text('{"broken":', encoding="utf-8")
        run(invalid, success=False)
        assert set(snapshot(invalid)) == {Path(".claude/settings.json")}

        linked_target = base / "linked-target"
        linked_source = base / "linked-source"
        linked_source.mkdir()
        try:
            linked_target.symlink_to(linked_source, target_is_directory=True)
        except OSError:
            pass
        else:
            run(linked_target, success=False)
            assert snapshot(linked_source) == {}

        spec = importlib.util.spec_from_file_location("claudeskills_installer", SCRIPT)
        installer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = installer
        spec.loader.exec_module(installer)
        rollback = base / "rollback"
        rollback.mkdir()
        actions, _, _ = installer.plan(rollback)
        real_write = installer._write
        calls = 0

        def fail_second(path, content, replace):
            global calls
            calls += 1
            if calls == 2:
                raise OSError("simulated")
            real_write(path, content, replace)

        with patch.object(installer, "_write", fail_second):
            try:
                installer.apply(rollback, actions)
            except OSError:
                pass
            else:
                raise AssertionError("rollback failure was not raised")
        assert not any((rollback / path).exists() for path in EXPECTED)
        assert list(rollback.iterdir()) == []

    print("PASS: empty install incl. identity hook, preserving hook merge, conflicts, idempotence, dry-run, invalid JSON, symlink refusal (when supported), rollback.")
