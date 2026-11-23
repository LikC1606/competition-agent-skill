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
_RESEARCH_PROFILE = 'default_permissions="competition-research"'
_RESEARCH_NETWORK_OPTIONS = ("--config", _RESEARCH_PROFILE,
                             "--config", 'permissions.competition-research.extends=":workspace"',
                             "--config", "permissions.competition-research.network.enabled=true")
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
RESEARCH_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": ("Use with research_state to carry a decision-changing finding across checkpoints. "
                    "Describe the source behind a completed implementation in summary and evidence."),
    "properties": {key: _TEXT for key in ("premise_id", "observation", "design_effect", "evidence_path")},
    "required": ["premise_id", "observation", "design_effect", "evidence_path"],
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
SELECTION_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "properties": {**{key: _TEXT for key in ("candidate_id", "reason", "limitations")},
                   "evidence": _TEXTS},
    "required": ["candidate_id", "reason", "limitations", "evidence"],
    "additionalProperties": False,
}
LOCAL_DELIVERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidate_id": _TEXT,
        "status": {"type": "string", "enum": ["requested", "completed", "blocked"]},
        "detail": _TEXT,
        "evidence": {"type": "array", "items": _TEXT},
    },
    "required": ["candidate_id", "status", "detail", "evidence"],
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
        "research_finding": RESEARCH_FINDING_SCHEMA,
        "next_proposal_id": _TEXT,
        "working_selection": SELECTION_SCHEMA,
        "local_delivery": LOCAL_DELIVERY_SCHEMA,
        "corrections": {"type": "array", "items": {"anyOf": [CORRECTION_SCHEMA, WITHDRAWAL_SCHEMA]}},
    },
    "required": ["status", "summary", "next_action", "stop_reason", "evidence"],
    "additionalProperties": False,
}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _texts(value: Any, *, empty: bool = False) -> bool:
    return isinstance(value, list) and (empty or bool(value)) and all(_text(item) for item in value)


def correction_reports_valid(corrections: Any) -> bool:
    """Validate the shared correction transport for receipts and maintenance."""
    if not isinstance(corrections, list):
        return False
    keys = set()
    for item in corrections:
        if not isinstance(item, dict):
            return False
        schema = WITHDRAWAL_SCHEMA if item.get("status") == "withdrawn" else CORRECTION_SCHEMA
        if (set(item) != set(schema["required"])
                or any(not _text(item[key]) for key in schema["required"] if key != "evidence")
                or not _texts(item["evidence"]) or item["key"] in keys):
            return False
        keys.add(item["key"])
    return True


def research_state_valid(research: Any) -> bool:
    return (
        isinstance(research, dict) and set(research) == set(RESEARCH_SCHEMA["required"])
        and research["status"] in ("open", "resolved", "deferred")
        and research["route"] in ("source", "diagnostic", "evaluation", "implement")
        and _text(research["question"]) and _text(research["missing_evidence"])
        and _texts(research["alternatives"]) and _texts(research["evidence"], empty=True)
        and isinstance(research["answer_actions"], list) and bool(research["answer_actions"])
        and all(isinstance(item, dict) and set(item) == {"observation", "action"}
                and all(_text(value) for value in item.values()) for item in research["answer_actions"])
    )


def _decision_fields_valid(receipt: dict[str, Any]) -> bool:
    """Check transport shape, not the truth of an agent's interpretation."""
    if "next_proposal_id" in receipt and not _text(receipt["next_proposal_id"]):
        return False
    research = receipt.get("research_state")
    if research is not None and not research_state_valid(research):
        return False
    if "research_finding" in receipt:
        finding = receipt["research_finding"]
        if (not isinstance(finding, dict) or set(finding) != set(RESEARCH_FINDING_SCHEMA["required"])
                or not all(_text(value) for value in finding.values())):
            return False
    selection = receipt.get("working_selection")
    if selection is not None:
        if (not isinstance(selection, dict) or set(selection) != set(SELECTION_SCHEMA["required"])
                or any(not _text(selection[key]) for key in ("candidate_id", "reason", "limitations"))
                or not _texts(selection["evidence"])):
            return False
    if "local_delivery" in receipt:
        delivery = receipt["local_delivery"]
        if (not isinstance(delivery, dict) or set(delivery) != set(LOCAL_DELIVERY_SCHEMA["required"])
                or delivery["status"] not in ("requested", "completed", "blocked")
                or not _text(delivery["candidate_id"]) or not _text(delivery["detail"])
                or not _texts(delivery["evidence"], empty=delivery["status"] != "completed")):
            return False
    return correction_reports_valid(receipt.get("corrections", []))


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


def read_receipt(path: pathlib.Path, *, mode: str | None = None) -> dict[str, Any]:
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
    if finding := receipt.get("research_finding"):
        research = receipt.get("research_state")
        evidence_path = finding["evidence_path"]
        if research is None:
            # The implementation can cite a finding without scheduling another research checkpoint.
            if mode in {"work", "execute"} and evidence_path in receipt["evidence"]:
                return receipt
            raise CampaignError("Final receipt with research_finding requires research_state")
        if evidence_path not in research["evidence"]:
            if evidence_path not in receipt["evidence"]:
                raise CampaignError("Include research_finding.evidence_path in research_state.evidence or top-level evidence")
            # Recover the cross-reference already declared in the raw receipt.
            research["evidence"].append(evidence_path)
    return receipt


@dataclass(frozen=True)
class InvocationOutcome:
    events: dict[str, Any]
    receipt: dict[str, Any] | None
    error: str
    reset_session: bool
    blocked: bool
    needs_receipt: bool = False


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
        # A named permissions profile and the legacy --sandbox switch are two
        # different selectors. Keep the workspace filesystem profile when opting into network access.
        sandbox_options = ["--sandbox", state["sandbox"]]
        if state.get("allow_network"):
            common += _RESEARCH_NETWORK_OPTIONS
            sandbox_options = []
        if state["session_id"] and state["next_mode"] != "rethink":
            return [state["agent_bin"], "exec", "resume", "--skip-git-repo-check",
                    *common, state["session_id"], "-"]
        command = [state["agent_bin"], "exec", "-C", state["workspace"], "--skip-git-repo-check",
                   *sandbox_options, *common]
        for directory in sorted({str(campaign), str(pathlib.Path(state["archive"]).parent)}):
            if directory != state["workspace"]:
                command += ["--add-dir", directory]
        return [*command, "-"]

    @staticmethod
    def receipt_command(turn: dict[str, Any], campaign: pathlib.Path, session_id: str) -> list[str]:
        schema = (turn.get("instruction_snapshot") or {}).get(
            "receipt_schema_path", str(campaign / "receipt.schema.json"))
        message = turn_directory(campaign, turn["number"]) / "receipt" / "message.json"
        command = [turn["command"][0], "exec", "fork", "--skip-git-repo-check", "--json",
                   "--output-schema", schema, "-o", str(message),
                   "--config", 'shell_environment_policy.set.SHELLOPTS="pipefail"']
        if "--model" in turn["command"]:
            command += ["--model", turn["command"][turn["command"].index("--model") + 1]]
        if _RESEARCH_PROFILE in turn["command"]:
            command += _RESEARCH_NETWORK_OPTIONS
        return [*command, session_id, "-"]

    @staticmethod
    def observe(directory: pathlib.Path, result: dict[str, Any], *, quarantined: bool,
                mode: str | None = None) -> InvocationOutcome:
        events = _parse_events(directory / "events.jsonl")
        error = result.get("error", "")
        receipt = None
        needs_receipt = False
        try:
            if result["returncode"] != 0:
                if not error and any("stream closed before response.completed" in event for event in events["errors"]):
                    error = "Provider stream closed before response.completed"
                elif not error and events["errors"]:
                    error = "CLI reported an error; see events.jsonl"
                raise CampaignError(f"Agent process exited with code {result['returncode']}" +
                                    (f"; {error}" if error else ""))
            if error:
                raise CampaignError(error)
            if events["terminal"] != "turn.completed":
                raise CampaignError("CLI did not record a successful turn.completed terminal event")
            if quarantined:
                raise CampaignError("Unconfirmed archive suffix quarantined; reconcile its artifacts")
            needs_receipt = True
            receipt = read_receipt(directory / "message.json", mode=mode)
            needs_receipt = False
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
        return InvocationOutcome(events, receipt, error, reset_session, blocked,
                                 needs_receipt and bool(events["session_id"]) and not blocked)
