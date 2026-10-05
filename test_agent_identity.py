"""Run with: python -m unittest -v test_agent_identity"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / ".claude/hooks/agent_identity.py"
SPEC = importlib.util.spec_from_file_location("claudeskills_agent_identity", SCRIPT)
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / ("_identity_test_" + uuid.uuid4().hex)
        os.mkdir(self.base)
        self.session = "session-123"
        self.agent = "afc0a0f57130c8d35"
        self.parent = self.base / (self.session + ".jsonl")
        self.parent.write_text("", encoding="utf-8")
        self.child = self.base / self.session / "subagents" / ("agent-" + self.agent + ".jsonl")
        self.child.parent.mkdir(parents=True)
        self.payload = {
            "hook_event_name": "PostToolUse", "tool_name": "Agent", "tool_use_id": "tool-123",
            "session_id": self.session, "transcript_path": str(self.parent),
            "tool_input": {"subagent_type": "builder", "model": "sonnet", "prompt": "secret prompt"},
            "tool_response": {"agentId": self.agent, "resolvedModel": "claude-sonnet-5-5",
                              "isAsync": True, "status": "async_launched", "outputFile": "arbitrary-secret-path"},
        }

    def tearDown(self):
        self.assertEqual(self.base.parent.resolve(), ROOT)
        shutil.rmtree(self.base)

    def assistant(self, model="claude-sonnet-5-5", effort="medium", **changes):
        record = {"type": "assistant", "sessionId": self.session, "agentId": self.agent,
                  "message": {"model": model, "content": [{"type": "text", "text": "secret assistant text"}]}}
        if effort is not None:
            record["effort"] = effort
        record.update(changes)
        return record

    def write(self, *records):
        self.child.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    def collect(self):
        report = identity.collect(self.payload)
        self.assertNotIn("secret", json.dumps(report))
        self.assertNotIn("arbitrary", json.dumps(report))
        return report

    def test_native_launch_is_resolution_without_execution(self):
        report = self.collect()
        self.assertEqual(report["status"], "launch")
        self.assertEqual(report["evidenceStatus"], "verified")
        self.assertEqual(report["executionEvidence"], "not_observed")
        self.assertEqual(report["requestedModel"], "sonnet")
        self.assertEqual(report["resolvedModel"], "claude-sonnet-5-5")
        self.assertIsNone(report["resolvedEffort"])
        self.assertEqual(report["provenance"]["resolvedModel"], ["tool_response.resolvedModel"])

    def test_native_and_child_match(self):
        self.write(self.assistant(), self.assistant())
        report = self.collect()
        self.assertEqual(report["executionEvidence"], "observed")
        self.assertEqual(report["resolvedEffort"], "medium")
        self.assertEqual(report["evidenceStatus"], "verified")
        self.assertEqual(report["status"], "launch")

    def test_foreground_without_native_model_uses_exact_child(self):
        self.payload["tool_response"] = {"agentId": self.agent, "status": "completed"}
        self.write(self.assistant())
        report = self.collect()
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["resolvedModel"], "claude-sonnet-5-5")
        self.assertEqual(report["provenance"]["resolvedModel"], ["child.assistant.message.model"])

    def test_native_child_model_mismatch(self):
        self.write(self.assistant(model="claude-opus-5-5"))
        report = self.collect()
        self.assertEqual(report["evidenceStatus"], "conflict")
        self.assertIsNone(report["resolvedModel"])
        self.assertIsNone(report["resolvedEffort"])
        self.assertEqual(report["nativeResolvedModel"], "claude-sonnet-5-5")
        self.assertEqual(report["observedModels"], ["claude-opus-5-5"])

    def test_exact_requested_model_mismatch_is_reported(self):
        self.payload["tool_input"]["model"] = "claude-opus-5-5"
        self.write(self.assistant())
        report = self.collect()
        self.assertEqual(report["evidenceStatus"], "conflict")
        self.assertEqual(report["requestedModelCheck"], "mismatch")
        self.assertEqual(report["observedModels"], ["claude-sonnet-5-5"])

    def test_exact_requested_model_matches(self):
        self.payload["tool_input"]["model"] = "claude-sonnet-5-5"
        self.write(self.assistant())
        self.assertEqual(self.collect()["requestedModelCheck"], "match")

    def test_alias_resolution_not_inferred(self):
        self.write(self.assistant())
        self.assertEqual(self.collect()["requestedModelCheck"], "unverified")

    def test_mixed_models_conflict(self):
        self.write(self.assistant(), self.assistant(model="claude-opus-5-5"))
        self.assertEqual(self.collect()["evidenceStatus"], "conflict")

    def test_effort_missing_or_incomplete_is_not_inferred(self):
        for records in [(self.assistant(effort=None),), (self.assistant(), self.assistant(effort=None))]:
            with self.subTest(records=len(records)):
                self.write(*records)
                report = self.collect()
                self.assertIsNone(report["resolvedEffort"])
                self.assertIn("child_effort_incomplete", report["diagnostics"])

    def test_mixed_efforts_conflict(self):
        self.write(self.assistant(), self.assistant(effort="high"))
        self.assertEqual(self.collect()["evidenceStatus"], "conflict")

    def test_missing_child_model_is_unverified(self):
        self.write(self.assistant(model=None))
        self.assertEqual(self.collect()["evidenceStatus"], "unverified")

    def test_wrong_session_or_agent_conflict(self):
        for changes in [{"sessionId": "other-session"}, {"agentId": "other-agent"}]:
            with self.subTest(changes=changes):
                self.write(self.assistant(**changes))
                report = self.collect()
                self.assertEqual(report["evidenceStatus"], "conflict")
                self.assertIsNone(report["resolvedModel"])

    def test_missing_identity_is_unverified(self):
        self.write(self.assistant(agentId=None))
        report = self.collect()
        self.assertEqual(report["evidenceStatus"], "unverified")
        self.assertIsNone(report["resolvedEffort"])

    def test_malformed_transcript_does_not_leak_or_block(self):
        for data in ['{"secret":', "[]\n", "\xff"]:
            with self.subTest(data=data):
                self.child.write_bytes(data.encode("latin-1"))
                report = self.collect()
                self.assertEqual(report["evidenceStatus"], "unverified")

    def test_unreadable_transcript_is_unverified(self):
        with patch.object(identity, "_read_records", side_effect=PermissionError("secret path")):
            report = self.collect()
        self.assertEqual(report["evidenceStatus"], "unverified")

    def test_missing_model_never_uses_requested_alias(self):
        self.payload["tool_response"] = {"agentId": self.agent}
        report = self.collect()
        self.assertIsNone(report["resolvedModel"])
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(report["evidenceStatus"], "unverified")

    def test_invalid_id_never_reads_supplied_output_path(self):
        self.payload["tool_response"]["agentId"] = "../outside"
        with patch.object(identity, "_read_records") as reader:
            report = self.collect()
        reader.assert_not_called()
        self.assertIsNone(report["agentId"])
        self.assertEqual(report["evidenceStatus"], "unverified")

    def test_parent_path_must_match_session_and_be_absolute(self):
        for path in [str(self.base / "other.jsonl"), "session-123.jsonl"]:
            with self.subTest(path=path):
                self.payload["transcript_path"] = path
                with patch.object(identity, "_read_records") as reader:
                    report = self.collect()
                reader.assert_not_called()
                self.assertEqual(report["evidenceStatus"], "unverified")

    def test_junction_is_refused(self):
        with patch.object(identity.os.path, "isjunction", return_value=True, create=True):
            report = self.collect()
        self.assertIn("unsafe_transcript_path", report["diagnostics"])

    def test_transcript_limits(self):
        self.write(self.assistant(), self.assistant())
        for bound, value, diagnosis in [("MAX_BYTES", 1, "transcript_size_limit"),
                                        ("MAX_LINES", 1, "transcript_line_limit"),
                                        ("MAX_LINE_BYTES", 1, "transcript_line_size_limit")]:
            with self.subTest(bound=bound), patch.object(identity, bound, value):
                report = self.collect()
                self.assertEqual(report["evidenceStatus"], "unverified")
                self.assertIn(diagnosis, report["diagnostics"])

    def launch_records(self, agent=None, session=None):
        return [
            {"sessionId": session or self.session, "message": {"content": [
                {"type": "tool_use", "id": "launch-id", "name": "Agent",
                 "input": {"subagent_type": "builder", "model": "sonnet", "prompt": "secret prompt"}}]}},
            {"sessionId": session or self.session,
             "message": {"content": [{"type": "tool_result", "tool_use_id": "launch-id", "content": "secret text"}]},
             "toolUseResult": {"agentId": agent or self.agent, "resolvedModel": "claude-sonnet-5-5", "status": "async_launched"}},
        ]

    def task_output(self):
        self.payload.update(tool_name="TaskOutput", tool_input={"task_id": self.agent}, tool_response={"status": "completed"})

    def test_task_output_recovers_exact_launch_and_child(self):
        self.task_output()
        self.parent.write_text("".join(json.dumps(record) + "\n" for record in self.launch_records()), encoding="utf-8")
        self.write(self.assistant())
        report = self.collect()
        self.assertEqual(report["agentId"], self.agent)
        self.assertEqual(report["agentType"], "builder")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["evidenceStatus"], "verified")
        self.assertIn("parent.toolUseResult.resolvedModel", report["provenance"]["resolvedModel"])

    def test_task_output_does_not_substitute_other_agent(self):
        self.task_output()
        self.parent.write_text("".join(json.dumps(record) + "\n" for record in self.launch_records(agent="different-agent")), encoding="utf-8")
        self.write(self.assistant())
        self.assertIsNone(self.collect()["resolvedModel"])

    def test_task_output_missing_or_ambiguous_link_unverified(self):
        self.task_output()
        for records in [[], self.launch_records() * 2, self.launch_records(session="wrong-session")]:
            with self.subTest(count=len(records)):
                self.parent.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
                report = self.collect()
                self.assertEqual(report["evidenceStatus"], "unverified")
                self.assertIsNone(report["resolvedModel"])

    def test_task_output_opaque_task_id_mapping_is_unverified(self):
        self.task_output()
        self.payload["tool_input"]["task_id"] = "opaque-task-id"
        self.payload["tool_response"] = {"agentId": self.agent, "resolvedModel": "claude-sonnet-5-5"}
        self.write(self.assistant())
        report = self.collect()
        self.assertEqual(report["evidenceStatus"], "unverified")
        self.assertEqual(report["resolvedModel"], "claude-sonnet-5-5")
        self.assertIn("task_response_mapping_unestablished", report["diagnostics"])

    def test_task_output_native_response(self):
        self.task_output()
        self.payload["tool_response"] = {"agentId": self.agent, "resolvedModel": "claude-sonnet-5-5", "status": "completed"}
        self.write(self.assistant())
        self.assertEqual(self.collect()["evidenceStatus"], "verified")

    def test_response_json_string_supported(self):
        self.payload["tool_response"] = json.dumps(self.payload["tool_response"])
        self.assertEqual(self.collect()["evidenceStatus"], "verified")

    def test_hook_cli_stdin_and_fixture(self):
        self.write(self.assistant())
        fixture = self.base / "hook.json"
        fixture.write_text(json.dumps(self.payload), encoding="utf-8")
        for args in [[], ["--input", str(fixture)]]:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SCRIPT), *args],
                                        input=json.dumps(self.payload), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
                report = json.loads(output["hookSpecificOutput"]["additionalContext"])
                self.assertEqual(report["resolvedEffort"], "medium")
                self.assertEqual(result.stderr, "")

    def test_invalid_hook_input_exits_zero(self):
        for raw in ["{", "[]"]:
            with self.subTest(raw=raw):
                result = subprocess.run([sys.executable, str(SCRIPT)], input=raw, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                report = json.loads(json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
                self.assertEqual(report["evidenceStatus"], "unverified")

    def test_unrelated_tool_returns_no_context(self):
        self.payload["tool_name"] = "Read"
        self.assertIsNone(identity.collect(self.payload))

    def test_wiring(self):
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        for manifest, variable in [(plugin, "CLAUDE_PLUGIN_ROOT"), (settings, "CLAUDE_PROJECT_DIR")]:
            hook = manifest["hooks"]["PostToolUse"][0]
            self.assertEqual(hook["matcher"], "Agent|Task|TaskOutput")
            self.assertEqual(hook["hooks"][0]["command"], 'python "${' + variable + '}/.claude/hooks/agent_identity.py"')
        self.assertIn("SessionStart", plugin["hooks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
