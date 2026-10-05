#!/usr/bin/env python3
"""Report bounded, observed Claude subagent identity to the calling PostToolUse hook.

The local JSONL transcript format is an observation, not a stable public API.
No settings, role defaults, assistant text, or supplied outputFile paths are used.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys


MAX_BYTES = 2 * 1024 * 1024
MAX_LINE_BYTES = 256 * 1024
MAX_LINES = 4000
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
TOOLS = {"Agent", "Task", "TaskOutput"}


def _text(value):
    return value if isinstance(value, str) and value.strip() else None


def _object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and len(value) <= MAX_LINE_BYTES:
        try:
            decoded = json.loads(value)
            return decoded if isinstance(decoded, dict) else {}
        except (ValueError, TypeError):
            pass
    return {}


def _safe_path(path):
    # resolve() alone would silently follow a symlink or Windows junction.
    for current in (path, *path.parents):
        if current.is_symlink() or getattr(os.path, "isjunction", lambda _: False)(current):
            raise ValueError("unsafe_transcript_path")
    return path


def _read_records(path):
    _safe_path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("transcript_size_limit")
    records = []
    total_bytes = 0
    with path.open("rb") as stream:
        for number in range(MAX_LINES + 1):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            total_bytes += len(line)
            if total_bytes > MAX_BYTES:
                raise ValueError("transcript_size_limit")
            if number == MAX_LINES:
                raise ValueError("transcript_line_limit")
            if len(line) > MAX_LINE_BYTES:
                raise ValueError("transcript_line_size_limit")
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("transcript_record_not_object")
            records.append(record)
    return records


def _parent_path(payload):
    session = payload.get("session_id")
    transcript = payload.get("transcript_path")
    if not isinstance(session, str) or not IDENTIFIER.fullmatch(session):
        raise ValueError("missing_or_invalid_session_id")
    if not isinstance(transcript, str) or not transcript:
        raise ValueError("missing_transcript_path")
    path = Path(transcript)
    if not path.is_absolute() or path.name != session + ".jsonl":
        raise ValueError("transcript_session_path_mismatch")
    return _safe_path(path), session


def _launch_for_task(records, task_id, session):
    matches = []
    for record in records:
        result = _object(record.get("toolUseResult"))
        if result.get("agentId") != task_id:
            continue
        if record.get("sessionId") != session:
            raise ValueError("parent_session_mismatch")
        message = _object(record.get("message"))
        content = message.get("content", [])
        result_ids = {item.get("tool_use_id") for item in content
                      if isinstance(item, dict) and item.get("type") == "tool_result"} if isinstance(content, list) else set()
        launches = []
        for source in records:
            for item in _object(source.get("message")).get("content", []):
                if (isinstance(item, dict) and item.get("type") == "tool_use"
                        and item.get("id") in result_ids and item.get("name") in {"Agent", "Task"}):
                    if source.get("sessionId") != session:
                        raise ValueError("parent_session_mismatch")
                    launches.append(_object(item.get("input")))
        if len(launches) != 1:
            raise ValueError("task_launch_not_uniquely_linked")
        matches.append((result, launches[0]))
    if len(matches) != 1:
        raise ValueError("task_launch_not_uniquely_linked")
    return matches[0]


def collect(payload):
    tool = payload.get("tool_name")
    if tool not in TOOLS:
        return None
    supplied = _object(payload.get("tool_input"))
    response = _object(payload.get("tool_response"))
    report = {
        "source": "claudeskills agent identity", "toolUseId": _text(payload.get("tool_use_id")),
        "agentId": None, "agentType": _text(supplied.get("subagent_type")),
        "requestedModel": _text(supplied.get("model")), "resolvedModel": None,
        "nativeResolvedModel": None, "observedModels": [], "observedEfforts": [],
        "requestedModelCheck": "unverified",
        "resolvedEffort": None, "status": "unknown", "evidenceStatus": "unverified",
        "executionEvidence": "not_observed", "provenance": {"resolvedModel": [], "resolvedEffort": []},
        "diagnostics": [],
    }
    diagnostics = report["diagnostics"]
    conflict = False
    incomplete = False
    native = response
    agent_id = _text(response.get("agentId"))
    if tool == "TaskOutput":
        task_id = _text(supplied.get("task_id"))
        if agent_id and task_id and agent_id != task_id:
            # Task IDs can be opaque; inequality alone is not contradictory
            # agent evidence. This local schema cannot establish that mapping.
            diagnostics.append("task_response_mapping_unestablished")
            incomplete = True
        elif not agent_id and task_id:
            try:
                parent, session = _parent_path(payload)
                native, launch_input = _launch_for_task(_read_records(parent), task_id, session)
                agent_id = native["agentId"]
                report["agentType"] = _text(launch_input.get("subagent_type"))
                report["requestedModel"] = _text(launch_input.get("model"))
                if _text(native.get("resolvedModel")):
                    report["provenance"]["resolvedModel"].append("parent.toolUseResult.resolvedModel")
            except (OSError, ValueError, TypeError):
                diagnostics.append("task_output_launch_evidence_unavailable")
                incomplete = True
        elif not agent_id:
            diagnostics.append("task_output_agent_id_unavailable")
            incomplete = True
    if agent_id and IDENTIFIER.fullmatch(agent_id):
        report["agentId"] = agent_id
    else:
        diagnostics.append("missing_or_invalid_agent_id")
        incomplete = True
        agent_id = None

    native_model = _text(native.get("resolvedModel"))
    report["nativeResolvedModel"] = native_model
    if native_model:
        report["resolvedModel"] = native_model
        if not report["provenance"]["resolvedModel"]:
            report["provenance"]["resolvedModel"].append("tool_response.resolvedModel")
    if response.get("status") in {"completed", "complete"}:
        report["status"] = "completed"
    elif tool != "TaskOutput" and (response.get("status") == "async_launched" or response.get("isAsync") is True):
        report["status"] = "launch"

    if agent_id:
        try:
            parent, session = _parent_path(payload)
            child = parent.parent / session / "subagents" / ("agent-" + agent_id + ".jsonl")
            records = _read_records(child)
            assistants = []
            for record in records:
                if not record.get("sessionId") or not record.get("agentId"):
                    diagnostics.append("child_identity_incomplete")
                    incomplete = True
                    assistants = []
                    break
                if record.get("sessionId") != session or record.get("agentId") != agent_id:
                    diagnostics.append("child_session_or_agent_mismatch")
                    conflict = True
                    break
                if record.get("type") == "assistant":
                    assistants.append(record)
            if not conflict and assistants:
                models = {_text(_object(record.get("message")).get("model")) for record in assistants}
                efforts = {_text(record.get("effort")) for record in assistants}
                report["observedModels"] = sorted(models - {None})
                report["observedEfforts"] = sorted(efforts - {None})
                if len(models - {None}) > 1 or (native_model and models - {None, native_model}):
                    diagnostics.append("model_evidence_conflict")
                    conflict = True
                elif None in models:
                    diagnostics.append("child_model_incomplete")
                    incomplete = True
                else:
                    report["resolvedModel"] = next(iter(models))
                    report["provenance"]["resolvedModel"].append("child.assistant.message.model")
                    report["executionEvidence"] = "observed"
                if len(efforts - {None}) > 1:
                    diagnostics.append("effort_evidence_conflict")
                    conflict = True
                elif None in efforts:
                    diagnostics.append("child_effort_incomplete")
                else:
                    report["resolvedEffort"] = next(iter(efforts))
                    report["provenance"]["resolvedEffort"].append("child.assistant.effort")
            elif not conflict:
                diagnostics.append("child_execution_not_observed")
        except FileNotFoundError:
            diagnostics.append("child_transcript_missing")
        except (OSError, ValueError, TypeError) as exc:
            diagnostics.append(str(exc) if isinstance(exc, ValueError) and not isinstance(exc, (json.JSONDecodeError, UnicodeError))
                               else "child_transcript_unreadable_or_invalid")
            incomplete = True

    requested = report["requestedModel"]
    # Compare only a concrete model ID, never infer how an alias resolves.
    candidates = set(report["observedModels"])
    if native_model:
        candidates.add(native_model)
    if requested and requested.startswith("claude-") and candidates:
        if candidates == {requested}:
            report["requestedModelCheck"] = "match"
        else:
            report["requestedModelCheck"] = "mismatch"
            diagnostics.append("requested_model_mismatch")
            conflict = True
    if conflict:
        report["resolvedModel"] = report["resolvedEffort"] = None
        report["evidenceStatus"] = "conflict"
        report["executionEvidence"] = "conflict"
    elif report["resolvedModel"] and not incomplete:
        report["evidenceStatus"] = "verified"
    if not report["resolvedModel"] and not conflict:
        diagnostics.append("resolved_model_unavailable")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="read a hook JSON fixture instead of stdin")
    args = parser.parse_args()
    try:
        if args.input:
            with args.input.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
        else:
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("input_size_limit")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("input_not_object")
        report = collect(payload)
        output = {} if report is None else {"hookSpecificOutput": {
            "hookEventName": "PostToolUse", "additionalContext": json.dumps(report, separators=(",", ":"), ensure_ascii=True)}}
    except (OSError, ValueError, TypeError, RecursionError):
        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
                  '{"source":"claudeskills agent identity","resolvedModel":null,"resolvedEffort":null,"status":"unknown","evidenceStatus":"unverified","diagnostics":["invalid_hook_input"]}'}}
    print(json.dumps(output, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
