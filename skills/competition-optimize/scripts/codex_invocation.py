"""Codex CLI command and result semantics behind one local invocation seam.

The process runtime owns launches and crash adoption. This adapter interprets
Codex events/receipts; accepted experiment evidence remains independent.
"""
from __future__ import annotations

import errno
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any
from campaign_runtime import CampaignError, turn_directory

_TEXT = {"type": "string", "minLength": 1}
_TEXTS = {"type": "array", "items": _TEXT, "minItems": 1}
RESEARCH_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {
        "status": {"type": "string", "enum": ["open", "resolved", "deferred"]},
        "route": {"type": "string", "enum": ["source", "diagnostic", "evaluation", "implement"]},
        "question": _TEXT,
        "alternatives": _TEXTS,
        "missing_evidence": _TEXT,
        "answer_actions": {"type": "array", "minItems": 1, "items": {
            "type": "object", "properties": {"observation": _TEXT, "action": _TEXT},
            "required": ["observation", "action"], "additionalProperties": False}},
        "evidence": {"type": "array", "items": _TEXT},
    },
    "required": ["status", "route", "question", "alternatives", "missing_evidence", "answer_actions", "evidence"],
    "additionalProperties": False,
}
CORRECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {**{key: _TEXT for key in ("key", "claim", "conditions", "limitations", "reopen_when")},
                   "evidence": _TEXTS},
    "required": ["key", "claim", "conditions", "limitations", "reopen_when", "evidence"],
    "additionalProperties": False,
}
WITHDRAWAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"key": _TEXT, "status": {"type": "string", "const": "withdrawn"},
                   "reason": _TEXT, "evidence": _TEXTS},
    "required": ["key", "status", "reason", "evidence"],
    "additionalProperties": False,
}

FINAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["continue", "complete", "blocked"]},
        "summary": {"type": "string"},
        "next_action": {"type": "string"},
        "stop_reason": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "research_state": RESEARCH_SCHEMA,
        "corrections": {"type": "array", "items": {"anyOf": [CORRECTION_SCHEMA, WITHDRAWAL_SCHEMA]}},
    },
    "required": ["status", "summary", "next_action", "stop_reason", "evidence"],
    "additionalProperties": False,
}


def _decision_fields_valid(receipt: dict[str, Any]) -> bool:
    """Check transport shape, not the truth of an agent's interpretation."""
    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def texts(value, *, empty=False):
        return isinstance(value, list) and (empty or bool(value)) and all(text(item) for item in value)

    research = receipt.get("research_state")
    if research is not None:
        if (not isinstance(research, dict) or set(research) != set(RESEARCH_SCHEMA["required"])
                or research["status"] not in ("open", "resolved", "deferred")
                or research["route"] not in ("source", "diagnostic", "evaluation", "implement")
                or not text(research["question"]) or not text(research["missing_evidence"])
                or not texts(research["alternatives"]) or not texts(research["evidence"], empty=True)
                or not isinstance(research["answer_actions"], list) or not research["answer_actions"]):
            return False
        for item in research["answer_actions"]:
            if (not isinstance(item, dict) or set(item) != {"observation", "action"}
                    or not all(text(value) for value in item.values())):
                return False
    corrections = receipt.get("corrections", [])
    if not isinstance(corrections, list):
        return False
    keys = set()
    for item in corrections:
        if not isinstance(item, dict):
            return False
        schema = WITHDRAWAL_SCHEMA if item.get("status") == "withdrawn" else CORRECTION_SCHEMA
        if (set(item) != set(schema["required"])
                or any(not text(item[key]) for key in schema["required"] if key != "evidence")
                or not texts(item["evidence"]) or item["key"] in keys):
            return False
        keys.add(item["key"])
    return True


def _parse_events(path: pathlib.Path) -> dict[str, Any]:
    result: dict[str, Any] = {"session_id": None, "terminal": None, "usage": {}, "errors": []}
    if not path.exists():
        return result
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            kind = event.get("type")
            if kind == "thread.started" and isinstance(event.get("thread_id"), str):
                result["session_id"] = event["thread_id"]
            if kind in {"turn.completed", "turn.failed"}:
                result["terminal"] = kind
            if kind == "turn.completed" and isinstance(event.get("usage"), dict):
                for key, value in event["usage"].items():
                    if type(value) is int and value >= 0:
                        result["usage"][key] = result["usage"].get(key, 0) + value
            if kind in {"error", "turn.failed"}:
                result["errors"].append(json.dumps(event, ensure_ascii=False))
    return result


def _parse_receipt(path: pathlib.Path) -> dict[str, Any]:
    """Accept one terminal receipt, including a provider's prose preamble.

    Some tool-capable providers cannot use CLI schema decoding. Keep their raw
    output intact and tolerate leading prose and a complete JSON code fence,
    never a partial receipt or other material after its JSON object.
    """
    try:
        message = path.read_text(encoding="utf-8").strip()
        start = message.find("{")
        opening = re.search(r"(?m)^[ \t]*(?P<fence>`{3,}|~{3,})(?:[ \t]*json)?[ \t]*\r?\n[ \t\r\n]*\Z",
                            message[:start] if start > 0 else "", re.IGNORECASE)
        if opening is not None:
            closing = re.search(r"\r?\n[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*\Z", message)
            fence = opening["fence"]
            if (closing is None or closing["fence"][0] != fence[0]
                    or len(closing["fence"]) < len(fence)):
                raise ValueError("Final receipt JSON fence is not properly closed")
            # Keep the preamble so earlier objects cannot be hidden by the wrapper.
            message = message[:opening.start()] + message[start:closing.start()]
        try:
            receipt = json.loads(message)
        except json.JSONDecodeError as exc:
            start = message.find("{")
            if exc.pos != 0 or start <= 0:
                raise
            receipt = json.loads(message[start:])
    except (OSError, ValueError) as exc:
        raise CampaignError(f"No valid final receipt: {exc}") from exc
    if (not isinstance(receipt, dict) or not set(FINAL_SCHEMA["required"]) <= set(receipt) or
            not set(receipt) <= set(FINAL_SCHEMA["properties"]) or
            not isinstance(receipt["status"], str) or
            receipt["status"] not in {"continue", "complete", "blocked"} or
            any(not isinstance(receipt[key], str) for key in ("summary", "next_action", "stop_reason")) or
            not isinstance(receipt["evidence"], list) or
            any(not isinstance(item, str) for item in receipt["evidence"]) or
            not _decision_fields_valid(receipt)):
        raise CampaignError("Final receipt does not match the campaign schema")
    return receipt


@dataclass(frozen=True)
class InvocationOutcome:
    events: dict[str, Any]
    receipt: dict[str, Any] | None
    error: str
    reset_session: bool
    blocked: bool


class CodexInvocation:
    """Build the command and classify its durable result without launching it."""

    @staticmethod
    def command(state: dict[str, Any], campaign: pathlib.Path, number: int) -> list[str]:
        message = str(turn_directory(campaign, number) / "message.json")
        schema = (state.get("instruction_snapshot") or {}).get("receipt_schema_path", str(campaign / "receipt.schema.json"))
        common = ["--json", "--output-schema", schema, "-o", message,
                  "--config", 'shell_environment_policy.set.SHELLOPTS="pipefail"']
        if state["model"]:
            common += ["--model", state["model"]]
        if state["session_id"] and state["next_mode"] != "rethink":
            return [state["agent_bin"], "exec", "resume", "--skip-git-repo-check",
                    *common, state["session_id"], "-"]
        command = [state["agent_bin"], "exec", "-C", state["workspace"], "--skip-git-repo-check",
                   "--sandbox", state["sandbox"], *common]
        for directory in sorted({str(campaign), str(pathlib.Path(state["archive"]).parent)}):
            if directory != state["workspace"]:
                command += ["--add-dir", directory]
        return [*command, "-"]

    @staticmethod
    def observe(directory: pathlib.Path, result: dict[str, Any], *, quarantined: bool) -> InvocationOutcome:
        events = _parse_events(directory / "events.jsonl")
        error = result.get("error", "")
        receipt = None
        try:
            if result["returncode"] != 0:
                raise CampaignError(f"Agent process exited with code {result['returncode']}; {error}")
            if error:
                raise CampaignError(error)
            if events["terminal"] != "turn.completed":
                raise CampaignError("CLI did not record a successful turn.completed terminal event")
            if quarantined:
                raise CampaignError("Unconfirmed archive suffix quarantined; reconcile its artifacts")
            receipt = _parse_receipt(directory / "message.json")
        except CampaignError as exc:
            error = str(exc)
        reset_session = blocked = False
        if receipt is None:
            diagnostics = "\n".join(events["errors"])
            stderr = directory / "stderr.log"
            if stderr.exists():
                diagnostics += stderr.read_text(errors="replace")[-16000:]
            low = diagnostics.lower()
            reset_session = any(text in low for text in (
                "session not found", "no saved session", "could not find session", "failed to load session", "rollout not found"))
            auth = any(text in low for text in (
                "not logged in", "authentication required", "invalid_api_key", "incorrect api key",
                "unauthorized: 401", "401 unauthorized", "please run codex login"))
            configuration = any(text in low for text in (
                "unexpected argument", "unrecognized option", "unknown option", "unsupported model"))
            blocked = bool(auth or configuration or result.get("survivors") or
                           result.get("launch_errno") in {errno.ENOENT, errno.EACCES, errno.ENOSPC, errno.EROFS})
        return InvocationOutcome(events, receipt, error, reset_session, blocked)
