#!/usr/bin/env python3
"""Record immutable candidate evidence and route decisions for a competition run.

The archive is JSONL so a damaged or interrupted append never requires rewriting
older evidence.  This helper deliberately does not decide the official score:
adapters provide the objective value and validity evidence, while this script
enforces identity, duplicate detection, and an evidence-based explore/exploit
recommendation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import sys
from collections import defaultdict
from typing import Any


class ArchiveFailure(Exception):
    """A malformed archive or an unsafe archive mutation."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


STATUSES = {"incumbent", "runner_up", "promising", "rejected", "unresolved"}
DIRECTIONS = {"maximize", "minimize"}
KINDS = {"official_metric", "proxy", "unknown"}


def reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(raw: bytes, source: str) -> Any:
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object,
                           parse_constant=reject_constant)
        json.dumps(value, allow_nan=False)
        return value
    except (UnicodeError, ValueError, OverflowError, RecursionError) as exc:
        raise ArchiveFailure("invalid_json", f"{source}: {exc}") from exc


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def hash_path(path: pathlib.Path) -> str:
    """Hash a file or a deterministic directory listing."""
    path = path.expanduser().resolve(strict=True)
    if path.is_file():
        return sha256(path.read_bytes())
    if not path.is_dir():
        raise ArchiveFailure("invalid_artifact", f"Artifact is neither a file nor directory: {path}")
    members: list[dict[str, str]] = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            relative = item.relative_to(path).as_posix()
            members.append({"path": relative, "sha256": sha256(item.read_bytes())})
    return sha256(canonical({"kind": "directory", "members": members}))


def read_records(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if not path.is_file():
        raise ArchiveFailure("invalid_archive", f"Archive is not a file: {path}")
    records: list[dict[str, Any]] = []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ArchiveFailure("incomplete_event", "Archive ends without a newline; reconcile the interrupted write first")
    seen: set[str] = set()
    proposals: dict[str, dict[str, Any]] = {}
    closed: set[str] = set()
    for index, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        value = load_json(line, f"{path}:{index}")
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ArchiveFailure("invalid_archive", f"{path}:{index}: expected schema_version 1 object")
        if value.get("event") not in {"candidate", "decision", "proposal", "proposal_stop"}:
            raise ArchiveFailure("invalid_archive", f"{path}:{index}: unknown event")
        if value["event"] == "candidate":
            validate_candidate(value)
            candidate_id = value["candidate_id"]
            if candidate_id in seen or not set(value["parent_ids"]) <= seen:
                raise ArchiveFailure("invalid_archive", f"{path}:{index}: duplicate ID or unknown parent")
            if value.get("proposal_id") is not None:
                proposal_id = value["proposal_id"]
                if proposal_id not in proposals or proposal_id in closed:
                    raise ArchiveFailure("invalid_archive", "Candidate names an unknown or closed proposal")
                validate_successor(value, proposals[proposal_id], records)
                closed.add(proposal_id)
            seen.add(candidate_id)
        elif value["event"] == "proposal":
            validate_proposal(value, records)
            proposal_id = value["proposal_id"]
            if proposal_id in proposals:
                raise ArchiveFailure("invalid_archive", "Duplicate proposal ID")
            proposals[proposal_id] = value
        elif value["event"] == "proposal_stop":
            proposal_id = nonempty_text(value.get("proposal_id"), "proposal_id")
            nonempty_text(value.get("reason"), "reason")
            if proposal_id not in proposals or proposal_id in closed:
                raise ArchiveFailure("invalid_archive", "Stop names an unknown or closed proposal")
            closed.add(proposal_id)
        elif value.get("action") not in {"exploit", "explore", "diagnose"}:
            raise ArchiveFailure("invalid_archive", f"{path}:{index}: invalid route decision")
        records.append(value)
    return records


def nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArchiveFailure("invalid_candidate", f"{field} must be a non-empty string")
    return value.strip()


def finite_number(value: Any, field: str) -> float:
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))
    except OverflowError:
        valid = False
    if not valid:
        raise ArchiveFailure("invalid_candidate", f"{field} must be a finite number")
    return float(value)


def validate_candidate(value: dict[str, Any]) -> None:
    for field in ("candidate_id", "fingerprint", "route", "mechanism"):
        nonempty_text(value.get(field), field)
    if value.get("status") not in STATUSES or type(value.get("valid")) is not bool:
        raise ArchiveFailure("invalid_archive", "Candidate status/validity is malformed")
    parents = value.get("parent_ids")
    if (not isinstance(parents, list) or any(not isinstance(p, str) or not p for p in parents)
            or len(set(parents)) != len(parents)):
        raise ArchiveFailure("invalid_archive", "Candidate parents are malformed")
    for field in ("artifacts", "artifact_paths", "objective", "comparison", "result", "cost"):
        if not isinstance(value.get(field), dict):
            raise ArchiveFailure("invalid_archive", f"Candidate {field} must be an object")
    if (not value["artifacts"] or any(not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item)
                                      for item in value["artifacts"].values())
            or value["fingerprint"] != sha256(canonical(value["artifacts"]))):
        raise ArchiveFailure("invalid_archive", "Artifact hashes/fingerprint are malformed or inconsistent")
    if value.get("role") not in {"development", "confirmation"}:
        raise ArchiveFailure("invalid_archive", "Candidate role is malformed")
    if value["objective"].get("value") is not None:
        finite_number(value["objective"]["value"], "objective.value")
        if value["objective"].get("direction") not in DIRECTIONS:
            raise ArchiveFailure("invalid_archive", "A scalar score requires its direction")
    for key, field in [("direction", "direction"), ("objective_kind", "kind"), ("objective_name", "name")]:
        if value["comparison"].get(key) != value["objective"].get(field):
            raise ArchiveFailure("invalid_archive", "Objective metadata differs from its comparison identity")


def result_metadata(path: pathlib.Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    path = path.expanduser().resolve(strict=True)
    raw = path.read_bytes()
    value = load_json(raw, str(path))
    if not isinstance(value, dict):
        raise ArchiveFailure("invalid_result", "Result must be a JSON object")
    metadata: dict[str, Any] = {"result_path": str(path), "result_sha256": sha256(raw),
                               "execution_status": value.get("status"),
                               "validity_scope": value.get("validity_scope", "adapter_declared_checks"),
                               "unchecked_rules": value.get("unchecked_rules", ["training_and_hard_rule_provenance"])}
    for key in ("candidate_hash", "evaluator_hash", "workload_hash", "score_model_hash", "stage"):
        if key in value:
            metadata[key] = value[key]
    if isinstance(value.get("evaluation"), dict):
        for key in ("config_hash", "split_hash", "stage", "runtime_environment"):
            if key in value["evaluation"]:
                metadata[key] = value["evaluation"][key]
        evaluation = value["evaluation"]
        expected, completed = evaluation.get("expected_cases"), evaluation.get("completed_cases")
        if expected is not None and (type(expected) is not int or expected <= 0 or expected != completed):
            metadata["partial"] = True
    if isinstance(value.get("metrics"), dict) and value["metrics"].get("partial"):
        metadata["partial"] = True
    if "runtime_environment" in value:
        metadata["runtime_environment"] = value["runtime_environment"]
    if "valid" in value:
        metadata["valid"] = value["valid"]
    elif "correct" in value:
        metadata["valid"] = value["correct"]
    if metadata.get("valid") is not None and type(metadata["valid"]) is not bool:
        raise ArchiveFailure("invalid_result", "Result validity must be boolean or null")
    if value.get("status") != "success" or metadata.get("partial"):
        metadata["valid"] = False
    score = value.get("score")
    if isinstance(score, dict):
        if score.get("kind") is not None and score["kind"] not in KINDS:
            raise ArchiveFailure("invalid_result", "Unknown score kind")
        if score.get("direction") is not None and score["direction"] not in DIRECTIONS:
            raise ArchiveFailure("invalid_result", "Unknown score direction")
        metadata["objective_kind"] = score.get("kind", "unknown")
        metadata["objective_name"] = score.get("metric", score.get("aggregation"))
        metadata["components"] = score.get("components", {})
        if score.get("direction") in DIRECTIONS:
            metadata["objective_direction"] = score["direction"]
        if score.get("value") is not None:
            metadata["objective_value"] = finite_number(score["value"], "result.score.value")
    if isinstance(value.get("metrics"), dict):
        metadata["metric_summary"] = value["metrics"].get("summary", {})
    if value.get("elapsed_seconds") is not None:
        metadata["elapsed_seconds"] = finite_number(value["elapsed_seconds"], "result.elapsed_seconds")
    return metadata


def make_fingerprint(source: pathlib.Path | None, configuration: pathlib.Path | None,
                     result: dict[str, Any]) -> tuple[str, dict[str, str]]:
    artifacts: dict[str, str] = {}
    if source is not None:
        source = source.expanduser().resolve(strict=True)
        artifacts["source"] = hash_path(source)
        if source.is_file() and result.get("candidate_hash") and artifacts["source"] != result["candidate_hash"]:
            raise ArchiveFailure("source_result_mismatch", "Source bytes differ from the evaluated candidate_hash")
    if configuration is not None:
        artifacts["configuration"] = hash_path(configuration)
    if result.get("candidate_hash") and "source" not in artifacts:
        artifacts["source"] = nonempty_text(result["candidate_hash"], "result.candidate_hash")
    if not artifacts:
        raise ArchiveFailure("invalid_candidate", "Provide --source, --configuration, or a result with candidate_hash")
    return sha256(canonical(artifacts)), artifacts


def duplicate_matches(old: list[dict[str, Any]], fingerprint: str) -> list[str]:
    return [entry["candidate_id"] for entry in old
            if entry["event"] == "candidate" and entry["fingerprint"] == fingerprint]


def check_candidate(args: argparse.Namespace) -> dict[str, Any]:
    old = read_records(args.archive.expanduser().resolve())
    fingerprint, artifacts = make_fingerprint(args.source, args.configuration, {})
    # Training can be checked before prediction artifacts exist: compare exactly
    # the supplied artifact hashes, without pretending to check absent files.
    matches = [entry["candidate_id"] for entry in old if entry["event"] == "candidate"
               and all(entry["artifacts"].get(key) == value for key, value in artifacts.items())]
    if args.reuse_reason is not None:
        nonempty_text(args.reuse_reason, "reuse_reason")
    if matches and not args.reuse_reason:
        raise ArchiveFailure("duplicate_fingerprint", f"Same artifacts as {matches}; explain a necessary re-evaluation or change the implementation")
    return {"schema_version": 1, "status": "ready", "fingerprint": fingerprint,
            "artifacts": artifacts, "matches": matches, "reuse_reason": args.reuse_reason,
            "checked_scope": "Provided artifact hashes only; absent artifacts are not checked",
            "unchecked": ["semantic_near_duplicates", "candidate_validity", "budget"]}


def append_record(path: pathlib.Path, value: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n").encode("utf-8")
    # Use one writer per run. This is append-only, not a concurrent database.
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "ab", closefd=True) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def candidate_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {entry["candidate_id"]: entry for entry in records if entry["event"] == "candidate"}


def validate_proposal(value: dict[str, Any], records: list[dict[str, Any]]) -> None:
    for field in ("proposal_id", "route", "basis", "change", "expected_observation", "validation", "stop_condition"):
        nonempty_text(value.get(field), field)
    candidates = candidate_index(records)
    for field in ("parent_ids", "feedback_from"):
        ids = value.get(field)
        if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in candidates for i in ids)
                or len(set(ids)) != len(ids)):
            raise ArchiveFailure("invalid_proposal", f"{field} must name distinct archived candidates")
        if any(candidates[i]["role"] != "development" for i in ids):
            raise ArchiveFailure("confirmation_feedback", "Confirmation evidence cannot supply search parents or feedback")
    targets = value.get("code_targets")
    if not isinstance(targets, list) or not targets:
        raise ArchiveFailure("invalid_proposal", "Supply the concrete parent code/configuration files being changed")
    for target in targets:
        if (not isinstance(target, dict) or not isinstance(target.get("path"), str)
                or not pathlib.Path(target["path"]).is_absolute()
                or not isinstance(target.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", target["sha256"])):
            raise ArchiveFailure("invalid_proposal", "Code targets need absolute paths and SHA-256 hashes")


def verify_result(entry: dict[str, Any]) -> None:
    result = entry["result"]
    if result.get("result_path") and sha256(pathlib.Path(result["result_path"]).read_bytes()) != result["result_sha256"]:
        raise ArchiveFailure("result_changed", f"Result bytes changed for {entry['candidate_id']}")


def verify_artifacts(entry: dict[str, Any]) -> list[pathlib.Path]:
    roots = []
    for key, name in entry["artifact_paths"].items():
        path = pathlib.Path(name).resolve(strict=True)
        if hash_path(path) != entry["artifacts"][key]:
            raise ArchiveFailure("parent_artifact_changed", f"Archived artifact changed for {entry['candidate_id']}: {key}")
        roots.append(path)
    return roots


def propose_candidate(args: argparse.Namespace) -> dict[str, Any]:
    records = read_records(args.archive.expanduser().resolve())
    raw = args.proposal.expanduser().resolve(strict=True).read_bytes()
    proposal = load_json(raw, str(args.proposal))
    if not isinstance(proposal, dict):
        raise ArchiveFailure("invalid_proposal", "Proposal input must be an object")
    value = {key: proposal.get(key) for key in ("proposal_id", "parent_ids", "feedback_from", "route", "basis",
                                               "change", "expected_observation", "validation", "stop_condition")}
    targets = proposal.get("code_targets")
    if not isinstance(targets, list) or not targets or any(not isinstance(target, str) for target in targets):
        raise ArchiveFailure("invalid_proposal", "code_targets must be a non-empty list of parent file paths")
    value.update(schema_version=1, event="proposal", input_sha256=sha256(raw),
                 code_targets=[{"path": str(pathlib.Path(target).expanduser().resolve(strict=True)),
                                "sha256": hash_path(pathlib.Path(target))} for target in targets])
    validate_proposal(value, records)
    if any(entry["event"] == "proposal" and entry["proposal_id"] == value["proposal_id"] for entry in records):
        raise ArchiveFailure("duplicate_proposal_id", "Proposal ID already exists")
    value["recorded_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    candidates = candidate_index(records)
    parent_roots = []
    for candidate_id in set(value["parent_ids"] + value["feedback_from"]):
        entry = candidates[candidate_id]
        verify_result(entry)
        if candidate_id in value["parent_ids"]:
            parent_roots.extend(verify_artifacts(entry))
    for target in value["code_targets"]:
        path = pathlib.Path(target["path"])
        if not path.is_file() or not any(path == root or root.is_dir() and path.is_relative_to(root) for root in parent_roots):
            raise ArchiveFailure("unbound_code_target", "Code target must be a file in a verified parent artifact snapshot")
    append_record(args.archive, value)
    return value


def validate_successor(candidate: dict[str, Any], proposal: dict[str, Any], records: list[dict[str, Any]]) -> None:
    if (set(candidate["parent_ids"]) != set(proposal["parent_ids"]) or candidate["route"] != proposal["route"]
            or candidate["role"] != "development"):
        raise ArchiveFailure("proposal_mismatch", "Successor must use the proposal's parents and route in development")
    parents = candidate_index(records)
    if any(candidate["fingerprint"] == parents[i]["fingerprint"] for i in proposal["parent_ids"]):
        raise ArchiveFailure("unchanged_successor", "An unchanged measurement cannot fulfill an implementation proposal")
    configured = [parents[i] for i in proposal["parent_ids"] if "configuration" in parents[i]["artifacts"]]
    if configured and ("configuration" not in candidate["artifacts"] or
                       all(candidate["artifacts"]["configuration"] == parent["artifacts"]["configuration"] for parent in configured)):
        raise ArchiveFailure("unchanged_pipeline", "An implementation proposal requires changed code/recipe, not only new predictions")
    nonempty_text(candidate.get("feedback"), "successor.feedback")
    if candidate.get("prediction_status") not in {"supported", "contradicted", "unresolved"}:
        raise ArchiveFailure("missing_prediction_status", "Record whether the proposed observation was supported, contradicted or unresolved")
    result = candidate["result"]
    if not result.get("result_path") or result.get("execution_status") not in {"success", "failed"}:
        raise ArchiveFailure("missing_execution_evidence", "A proposal successor requires a completed adapter result")
    if any(entry["result"].get("result_sha256") == result["result_sha256"] for entry in parents.values()):
        raise ArchiveFailure("reused_execution_evidence", "An old result cannot complete a new implementation proposal")


def stop_proposal(args: argparse.Namespace) -> dict[str, Any]:
    records = read_records(args.archive)
    proposal_id = nonempty_text(args.proposal_id, "proposal_id")
    if not any(entry["event"] == "proposal" and entry["proposal_id"] == proposal_id for entry in records):
        raise ArchiveFailure("unknown_proposal", "No such proposal in this archive")
    if any(entry["event"] in {"candidate", "proposal_stop"} and entry.get("proposal_id") == proposal_id for entry in records):
        raise ArchiveFailure("closed_proposal", "Proposal already has an outcome")
    value = {"schema_version": 1, "event": "proposal_stop", "proposal_id": proposal_id,
             "reason": nonempty_text(args.reason, "reason"), "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    append_record(args.archive, value)
    return value


def evidence_summary(entry: dict[str, Any]) -> dict[str, Any]:
    result = entry["result"]
    return {"candidate_id": entry["candidate_id"], "valid": entry["valid"],
            "objective": entry["objective"], "feedback": entry["feedback"],
            "result_path": result.get("result_path"), "result_sha256": result.get("result_sha256"),
            "validity_scope": result.get("validity_scope")}


def iteration_trace(records: list[dict[str, Any]], recent: int | None = None) -> list[dict[str, Any]]:
    candidates = candidate_index(records)
    outcomes = {entry["proposal_id"]: entry for entry in records
                if entry["event"] in {"candidate", "proposal_stop"} and entry.get("proposal_id")}
    trace = []
    verified: set[str] = set()
    def verify(entry: dict[str, Any]) -> None:
        if entry["candidate_id"] not in verified:
            verify_result(entry)
            verify_artifacts(entry)
            verified.add(entry["candidate_id"])
    proposals = [entry for entry in records if entry["event"] == "proposal"]
    for proposal in proposals if recent is None else proposals[-recent:]:
        outcome = outcomes.get(proposal["proposal_id"])
        row = {key: proposal[key] for key in ("proposal_id", "parent_ids", "feedback_from", "route", "basis", "change", "expected_observation")}
        row["feedback_evidence"] = [evidence_summary(candidates[i]) for i in proposal["feedback_from"]]
        for candidate_id in proposal["feedback_from"]:
            verify(candidates[candidate_id])
        row["state"] = "pending"
        if outcome is not None and outcome["event"] == "proposal_stop":
            row.update(state="stopped", reason=outcome["reason"])
        elif outcome is not None:
            verify(outcome)
            row.update(state="evaluated_valid" if outcome["valid"] else "evaluation_failed_or_invalid",
                       candidate_id=outcome["candidate_id"], evidence=evidence_summary(outcome), objective=outcome["objective"],
                       feedback=outcome["feedback"], prediction_status=outcome["prediction_status"],
                       failure_mechanism=outcome["failure_mechanism"], cost=outcome["cost"])
            gains = {}
            for parent_id in proposal["parent_ids"]:
                parent = candidates[parent_id]
                verify(parent)
                if measurable(outcome) and measurable(parent) and outcome["comparison"] == parent["comparison"]:
                    delta = outcome["objective"]["value"] - parent["objective"]["value"]
                    gains[parent_id] = delta * (-1 if outcome["objective"]["direction"] == "minimize" else 1)
                else:
                    gains[parent_id] = None
            row["objective_gain_vs_parents"] = gains
        trace.append(row)
    return trace


def trace_report(args: argparse.Namespace) -> dict[str, Any]:
    if args.recent < 1:
        raise ArchiveFailure("invalid_config", "recent must be positive")
    records = read_records(args.archive)
    proposals = [entry for entry in records if entry["event"] == "proposal"]
    closed = {entry["proposal_id"] for entry in records
              if entry["event"] in {"candidate", "proposal_stop"} and entry.get("proposal_id")}
    trace = iteration_trace(records, None if args.all else args.recent)
    return {"schema_version": 1, "total_iterations": len(proposals),
            "omitted_iterations": len(proposals) - len(trace),
            "pending_proposals": [entry["proposal_id"] for entry in proposals if entry["proposal_id"] not in closed],
            "iterations": trace,
            "scope": "Linked code/result identities and adapter-declared checks; mechanism causality and promotion are not certified"}


def record_candidate(args: argparse.Namespace) -> dict[str, Any]:
    archive = args.archive.expanduser().resolve()
    old = read_records(archive)
    candidate_id = nonempty_text(args.candidate_id, "candidate_id")
    route = nonempty_text(args.route, "route")
    mechanism = nonempty_text(args.mechanism, "mechanism")
    status = args.status
    if args.reuse_reason is not None:
        nonempty_text(args.reuse_reason, "reuse_reason")
    result = result_metadata(args.result)
    fingerprint, artifacts = make_fingerprint(args.source, args.configuration, result)
    for previous in old:
        if previous.get("event") != "candidate":
            continue
        if previous.get("candidate_id") == candidate_id:
            raise ArchiveFailure("duplicate_candidate_id", f"Candidate ID already exists: {candidate_id}")
        if previous.get("fingerprint") == fingerprint and not args.reuse_reason:
            raise ArchiveFailure("duplicate_fingerprint",
                                 f"Candidate has the same source/configuration fingerprint as {previous.get('candidate_id')}")
    parents = [nonempty_text(parent, "parent") for parent in args.parent]
    if len(set(parents)) != len(parents):
        raise ArchiveFailure("invalid_candidate", "Duplicate parent IDs")
    known_ids = {entry["candidate_id"] for entry in old if entry["event"] == "candidate"}
    if not set(parents) <= known_ids:
        raise ArchiveFailure("unknown_parent", "Record or reconcile the parent candidates first")
    objective: dict[str, Any] = {}
    direction = args.objective_direction or result.get("objective_direction")
    value = args.objective_value
    if value is None and result.get("objective_value") is not None:
        value = result["objective_value"]
    if value is not None:
        objective["value"] = finite_number(value, "objective_value")
    if direction is not None:
        if direction not in DIRECTIONS:
            raise ArchiveFailure("invalid_candidate", "objective_direction must be maximize or minimize")
        objective["direction"] = direction
    if value is not None and direction is None:
        raise ArchiveFailure("invalid_candidate", "A scalar objective value requires an explicit direction")
    objective["kind"] = args.objective_kind or result.get("objective_kind", "unknown")
    objective["name"] = args.objective_name or result.get("objective_name")
    objective["components"] = result.get("components", {})
    for flag_value, key in [(args.objective_value, "objective_value"),
                            (args.objective_direction, "objective_direction"),
                            (args.objective_kind, "objective_kind"), (args.objective_name, "objective_name"),
                            (args.evaluator_hash, "evaluator_hash"), (args.stage, "stage"),
                            (args.workload_hash, "workload_hash" if "workload_hash" in result else "split_hash"),
                            (args.score_model_hash, "score_model_hash")]:
        if flag_value is not None and result.get(key) is not None and flag_value != result[key]:
            raise ArchiveFailure("result_override", f"Explicit {key} contradicts the evaluator result")
    validity = args.valid
    if validity is None and "valid" in result:
        validity = result["valid"]
    if validity is None:
        raise ArchiveFailure("invalid_candidate", "Provide --valid/--invalid or a result with valid/correct")
    if validity and result.get("valid") is False:
        raise ArchiveFailure("result_override", "Cannot declare a failed/partial/invalid result valid")
    if status in {"incumbent", "runner_up"} and not validity:
        raise ArchiveFailure("invalid_candidate", "Invalid candidates cannot be an incumbent or runner-up")
    role = args.role or ("confirmation" if result.get("stage") in {"confirmation", "test", "holdout"} else "development")
    if role == "development" and result.get("stage") in {"confirmation", "test", "holdout"}:
        raise ArchiveFailure("result_override", "Confirmation/test evidence cannot become development through a flag")
    comparison = {
        "evaluator_hash": args.evaluator_hash or result.get("evaluator_hash"),
        "workload_hash": args.workload_hash or result.get("workload_hash") or result.get("split_hash"),
        "score_model_hash": args.score_model_hash or result.get("score_model_hash"),
        "config_hash": result.get("config_hash"), "stage": args.stage or result.get("stage"),
        "runtime_environment": result.get("runtime_environment"),
        "objective_kind": objective["kind"], "objective_name": objective["name"],
        "direction": direction,
    }
    cost: Any = {"evaluation_elapsed_seconds": result["elapsed_seconds"]} if "elapsed_seconds" in result else {}
    if args.cost is not None:
        cost = load_json(args.cost.encode("utf-8"), "--cost")
        if not isinstance(cost, dict):
            raise ArchiveFailure("invalid_candidate", "--cost must be a JSON object")
    record: dict[str, Any] = {
        "schema_version": 1,
        "event": "candidate",
        "recorded_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "candidate_id": candidate_id,
        "parent_ids": parents,
        "fingerprint": fingerprint,
        "artifacts": artifacts,
        "artifact_paths": {key: str(path.expanduser().resolve()) for key, path in
                           [("source", args.source), ("configuration", args.configuration)] if path is not None},
        "route": route,
        "mechanism": mechanism,
        "status": status,
        "valid": bool(validity),
        "role": role,
        "comparison": comparison,
        "objective": objective,
        "cost": cost,
        "feedback": args.feedback or None,
        "failure_mechanism": args.failure or None,
        "reuse_reason": args.reuse_reason,
        "reused_from": duplicate_matches(old, fingerprint),
        "result": result,
    }
    if args.proposal_id is not None:
        proposal = next((entry for entry in old if entry["event"] == "proposal" and entry["proposal_id"] == args.proposal_id), None)
        if proposal is None:
            raise ArchiveFailure("unknown_proposal", "Record the implementation proposal before its successor")
        if any(entry["event"] in {"candidate", "proposal_stop"} and entry.get("proposal_id") == args.proposal_id for entry in old):
            raise ArchiveFailure("closed_proposal", "Proposal already has an outcome")
        record["proposal_id"] = args.proposal_id
        record["prediction_status"] = args.prediction_status
        validate_successor(record, proposal, old)
    validate_candidate(record)
    append_record(archive, record)
    return record


def measurable(entry: dict[str, Any]) -> bool:
    objective, context = entry["objective"], entry["comparison"]
    required = ("evaluator_hash", "workload_hash", "score_model_hash", "stage", "objective_name")
    return (entry["valid"] and entry["role"] == "development"
            and objective.get("value") is not None and objective.get("direction") in DIRECTIONS
            and objective.get("kind") in {"proxy", "official_metric"}
            and all(isinstance(context.get(key), str) and context[key] for key in required))


def route_decision(args: argparse.Namespace) -> dict[str, Any]:
    records = [record for record in read_records(args.archive.expanduser().resolve())
               if record.get("event") == "candidate"]
    if not records:
        raise ArchiveFailure("empty_archive", "Record a baseline before requesting a route decision")
    development = [entry for entry in records if entry["role"] == "development"]
    if not development:
        raise ArchiveFailure("no_development_evidence", "Confirmation evidence cannot guide new optimization")
    current_route = args.current_route or development[-1]["route"]
    current_route = nonempty_text(current_route, "current_route")
    route_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in development:
        route_entries[entry.get("route", "unknown")].append(entry)
    current = [entry for entry in route_entries.get(current_route, []) if entry["role"] == "development"]
    if not current:
        raise ArchiveFailure("unknown_route", f"No development candidates for route {current_route!r}")
    latest = current[-1]
    context = latest["comparison"]
    direction = latest["objective"].get("direction")
    if args.objective_direction and direction != args.objective_direction:
        raise ArchiveFailure("result_override", "Requested direction differs from the selected comparison")
    # Compare only complete, valid measurements in the latest evaluation regime.
    # A rebound below the route's best is not new progress; repeats do not add
    # distinct implementation evidence to the stagnation window.
    measured, seen = [], set()
    for entry in current:
        if measurable(entry) and entry["comparison"] == context and entry["fingerprint"] not in seen:
            measured.append(entry)
            seen.add(entry["fingerprint"])
    recent = measured[-args.recent:]
    progress: set[str] = set()
    best_value: float | None = None
    for entry in measured:
        score = entry["objective"]["value"] * (-1 if direction == "minimize" else 1)
        if best_value is not None and score > best_value + args.tie_epsilon:
            progress.add(entry["candidate_id"])
        best_value = score if best_value is None else max(best_value, score)
    recent_progress = [entry["candidate_id"] for entry in recent if entry["candidate_id"] in progress]
    unresolved = [entry for entry in current[-args.recent:]
                  if entry["comparison"] == context and entry["status"] in {"promising", "unresolved"}
                  and entry.get("feedback") and not any(entry["candidate_id"] in later["parent_ids"]
                                                       for later in current)]
    for entry in measured:
        verify_result(entry)
    if latest["valid"] is False:
        action = "diagnose"
        reason = "Latest candidate is invalid or incomplete; diagnose implementation/evaluation before judging its method."
    elif not measurable(latest):
        action = "diagnose"
        reason = "Comparable development evidence is insufficient; inspect code/history or gather the smallest decision-changing diagnostic."
    elif recent_progress or unresolved:
        action = "exploit"
        reason = "Route has a new historical best or a feedback-supported unresolved opportunity; propose a specific successor from its code and evidence."
    elif len(recent) < args.min_stagnant:
        action = "diagnose"
        reason = "Too few distinct comparable implementations to judge stagnation; inspect code/history for an actionable mechanism."
    else:
        action = "explore"
        reason = (f"The last {len(recent)} valid comparable candidates on {current_route!r} produced no "
                  "new historical best and have no feedback-supported unresolved opportunity; consider a materially different mechanism.")
    alternatives = []
    for route, entries in sorted(route_entries.items(), key=lambda item: (len(item[1]), item[0])):
        eligible = [entry for entry in entries if entry["role"] == "development" and entry["comparison"] == context]
        if route != current_route and eligible:
            alternatives.append({"route": route, "candidates": len(eligible),
                                 "latest_candidate": eligible[-1]["candidate_id"],
                                 "latest_status": eligible[-1]["status"]})
    decision = {
        "schema_version": 1,
        "event": "decision",
        "action": action,
        "current_route": current_route,
        "objective_direction": direction,
        "recent_valid_candidates": len(recent),
        "progress_candidates": recent_progress,
        "evidence_candidates": [entry["candidate_id"] for entry in recent],
        "comparison": context,
        "unresolved_candidates": [entry["candidate_id"] for entry in unresolved],
        "reason": reason,
        "alternative_routes": alternatives,
        "policy": {"recent": args.recent, "min_stagnant": args.min_stagnant, "tie_epsilon": args.tie_epsilon},
        "scope": "Advisory route review only; proxy progress is provisional. No promotion, budget or mechanism selection is automated.",
    }
    if args.output is not None:
        output = args.output.expanduser().resolve()
        if output.exists():
            raise ArchiveFailure("output_exists", f"Refusing to overwrite decision output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(decision, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        decision["output_file"] = str(output)
    if args.append:
        append_record(args.archive.expanduser().resolve(), decision)
    return decision


def summarize(args: argparse.Namespace) -> dict[str, Any]:
    records = read_records(args.archive.expanduser().resolve())
    candidates = [record for record in records if record.get("event") == "candidate"]
    routes: dict[str, dict[str, Any]] = {}
    for entry in candidates:
        route = entry.get("route", "unknown")
        summary = routes.setdefault(route, {"candidates": 0, "statuses": defaultdict(int), "latest": None})
        summary["candidates"] += 1
        summary["statuses"][entry.get("status", "unknown")] += 1
        summary["latest"] = entry["candidate_id"]
    return {"schema_version": 1, "candidate_count": len(candidates),
            "decision_count": sum(entry["event"] == "decision" for entry in records),
            "proposal_count": sum(entry["event"] == "proposal" for entry in records),
            "recent_candidates": [{key: entry[key] for key in ("candidate_id", "parent_ids", "fingerprint", "artifact_paths", "route", "status", "valid", "role", "objective", "comparison", "cost", "result", "feedback", "failure_mechanism")}
                                  for entry in candidates[-args.recent:]],
            "routes": {route: {"candidates": info["candidates"],
                               "statuses": dict(info["statuses"]), "latest": info["latest"]}
                       for route, info in sorted(routes.items())}}


def distinct_implementations(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use the first supplied observation of each fingerprint, not its luckiest repeat."""
    distinct, seen = [], set()
    for entry in entries:
        if entry["fingerprint"] not in seen:
            distinct.append(entry)
            seen.add(entry["fingerprint"])
    return distinct


def directed_score(entry: dict[str, Any]) -> float:
    return entry["objective"]["value"] * (-1 if entry["objective"]["direction"] == "minimize" else 1)


def optimization_brief(args: argparse.Namespace) -> dict[str, Any]:
    """Retrieve decision-relevant development evidence without another ledger/card."""
    if args.recent < 1 or args.routes < 1:
        raise ArchiveFailure("invalid_config", "recent and routes must be positive")
    records = read_records(args.archive.expanduser().resolve())
    index = candidate_index(records)
    if not index:
        raise ArchiveFailure("empty_archive", "Record a baseline before requesting optimization context")
    development = [entry for entry in index.values() if entry["role"] == "development"]
    if args.anchor is not None:
        if args.anchor not in index:
            raise ArchiveFailure("unknown_candidate", f"No archived candidate {args.anchor!r}")
        anchor = index[args.anchor]
        if anchor["role"] != "development":
            raise ArchiveFailure("confirmation_feedback", "Confirmation evidence cannot anchor optimization context")
    elif development:
        anchor = development[-1]
    else:
        raise ArchiveFailure("no_development_evidence", "Confirmation evidence cannot guide new optimization")
    context = anchor["comparison"]
    scoped = [entry for entry in development if entry["comparison"] == context]
    by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in scoped:
        by_route[entry["route"]].append(entry)
    measured = distinct_implementations([entry for entry in scoped if measurable(entry)])
    measured_ids = {entry["candidate_id"] for entry in measured}
    best = max(measured, key=directed_score) if measured else None
    route_bests = {}
    for route, entries in by_route.items():
        eligible = [entry for entry in entries if entry["candidate_id"] in measured_ids]
        route_bests[route] = max(eligible, key=directed_score) if eligible else None
    # The active route is always included. Alternatives are a factual score
    # ordering, not an effort quota or an automated choice of the next method.
    alternatives = sorted((route for route in by_route if route != anchor["route"]),
                          key=lambda route: (-directed_score(route_bests[route]) if route_bests[route] else math.inf, route))
    selected_routes = [anchor["route"]] + alternatives[:args.routes - 1]
    selected: dict[str, dict[str, Any]] = {}

    def include(entry: dict[str, Any] | None) -> str | None:
        if entry is None:
            return None
        selected[entry["candidate_id"]] = entry
        return entry["candidate_id"]

    include(anchor)
    include(best)
    recent = distinct_implementations(by_route[anchor["route"]])[-args.recent:]
    recent_ids = [include(entry) for entry in recent]
    superseded = {parent_id for child in scoped for parent_id in child["parent_ids"]
                  if parent_id in index and child["fingerprint"] != index[parent_id]["fingerprint"]}
    routes = []
    for route in selected_routes:
        entries = by_route[route]
        unresolved = next((entry for entry in reversed(entries)
                           if entry["status"] in {"promising", "unresolved"} and entry.get("feedback")
                           and entry["candidate_id"] not in superseded), None)
        failure = next((entry for entry in reversed(entries)
                        if not entry["valid"] or entry["status"] == "rejected" or entry.get("failure_mechanism")), None)
        routes.append({"route": route, "measurements": len(entries),
                       "distinct_implementations": len(distinct_implementations(entries)),
                       "best": include(route_bests[route]), "latest": include(entries[-1]),
                       "unresolved": include(unresolved), "latest_failure": include(failure)})
    closed = {entry["proposal_id"] for entry in records
              if entry["event"] in {"candidate", "proposal_stop"} and entry.get("proposal_id")}
    pending = [entry for entry in records if entry["event"] == "proposal" and entry["proposal_id"] not in closed]
    matching_pending = [entry for entry in pending
                        if all(index[i]["comparison"] == context for i in entry["parent_ids"] + entry["feedback_from"])]
    details = matching_pending[-args.recent:]
    for proposal in details:
        for candidate_id in proposal["parent_ids"] + proposal["feedback_from"]:
            include(index[candidate_id])
    cards = {}
    for candidate_id, entry in selected.items():
        verify_result(entry)
        verify_artifacts(entry)
        card = {key: entry.get(key) for key in ("parent_ids", "fingerprint", "artifact_paths", "route", "mechanism",
                                              "valid", "status", "objective", "cost", "feedback", "failure_mechanism",
                                              "proposal_id", "prediction_status", "reused_from")}
        result = entry["result"]
        card["result"] = {key: result.get(key) for key in ("result_path", "result_sha256", "execution_status",
                                                         "validity_scope", "unchecked_rules")}
        card["identity_checks"] = {"result_bytes": "checked" if result.get("result_path") else "not_recorded",
                                   "snapshot_bytes": "checked" if entry["artifact_paths"] else "not_recorded"}
        card["objective_gain_vs_best"] = (directed_score(entry) - directed_score(best)
                                          if best is not None and candidate_id in measured_ids else None)
        cards[candidate_id] = card
    checked_targets: set[tuple[str, str]] = set()
    for proposal in details:
        for target in proposal["code_targets"]:
            identity = (target["path"], target["sha256"])
            if identity not in checked_targets:
                if hash_path(pathlib.Path(target["path"])) != target["sha256"]:
                    raise ArchiveFailure("parent_artifact_changed", f"Pending code target changed: {target['path']}")
                checked_targets.add(identity)
    return {"schema_version": 1, "archive_path": str(args.archive.expanduser().resolve()),
            "anchor_candidate": anchor["candidate_id"], "comparison": context,
            "best_development": best["candidate_id"] if best else None,
            "recent_current": recent_ids, "routes": routes, "candidates": cards,
            "pending_proposals": [entry["proposal_id"] for entry in pending],
            "pending_details": [{key: entry[key] for key in ("proposal_id", "parent_ids", "feedback_from", "route",
                                                            "code_targets", "basis", "change", "expected_observation",
                                                            "validation", "stop_condition")} for entry in details],
            "omitted": {"routes": len(by_route) - len(routes), "current_comparison_candidates": len(scoped) - len(cards),
                        "other_development_comparisons": len(development) - len(scoped),
                        "pending_details": len(pending) - len(details)},
            "scope": "Development retrieval only; first valid observation per fingerprint ranks representatives. "
                     "Identity checks cover displayed evidence, not all history, score recomputation, causality or promotion. "
                     "Inspect relevant code and raw results before proposing the next implementation."}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check for exact artifact duplicates before evaluation")
    check.add_argument("--archive", type=pathlib.Path, required=True)
    check.add_argument("--source", type=pathlib.Path)
    check.add_argument("--configuration", type=pathlib.Path)
    check.add_argument("--reuse-reason", help="why an unchanged candidate needs another measurement")
    propose = sub.add_parser("propose", help="bind an agent-authored implementation proposal to code and feedback")
    propose.add_argument("--archive", type=pathlib.Path, required=True)
    propose.add_argument("--proposal", type=pathlib.Path, required=True)
    stop = sub.add_parser("stop", help="record why an unexecuted proposal was stopped")
    stop.add_argument("--archive", type=pathlib.Path, required=True)
    stop.add_argument("--proposal-id", required=True)
    stop.add_argument("--reason", required=True)
    trace = sub.add_parser("trace", help="show proposals and their actual evaluation outcomes")
    trace.add_argument("--archive", type=pathlib.Path, required=True)
    trace.add_argument("--recent", type=int, default=8, help="recent proposals to include; all pending IDs remain visible")
    trace.add_argument("--all", action="store_true", help="include every iteration when a complete audit is needed")
    brief = sub.add_parser("brief", help="retrieve matched best versions, recent failures, code paths and pending proposals")
    brief.add_argument("--archive", type=pathlib.Path, required=True)
    brief.add_argument("--anchor", help="development candidate defining the comparison; defaults to the latest development record")
    brief.add_argument("--routes", type=int, default=4, help="routes to show, including the active route")
    brief.add_argument("--recent", type=int, default=4, help="recent distinct active-route candidates and matching pending details")
    record = sub.add_parser("record", help="append one candidate evidence record")
    record.add_argument("--archive", type=pathlib.Path, required=True)
    record.add_argument("--candidate-id", required=True)
    record.add_argument("--proposal-id", help="implementation proposal this evaluated successor fulfills")
    record.add_argument("--prediction-status", choices=["supported", "contradicted", "unresolved"])
    record.add_argument("--parent", action="append", default=[])
    record.add_argument("--source", type=pathlib.Path)
    record.add_argument("--configuration", type=pathlib.Path)
    record.add_argument("--result", type=pathlib.Path)
    record.add_argument("--evaluator-hash")
    record.add_argument("--workload-hash")
    record.add_argument("--score-model-hash")
    record.add_argument("--stage")
    record.add_argument("--role", choices=["development", "confirmation"])
    record.add_argument("--reuse-reason", help="required for recording unchanged artifacts under a new measurement")
    record.add_argument("--route", required=True)
    record.add_argument("--mechanism", required=True)
    record.add_argument("--status", choices=sorted(STATUSES), required=True)
    validity = record.add_mutually_exclusive_group()
    validity.add_argument("--valid", dest="valid", action="store_true")
    validity.add_argument("--invalid", dest="valid", action="store_false")
    record.set_defaults(valid=None)
    record.add_argument("--objective-value", type=float)
    record.add_argument("--objective-direction", choices=sorted(DIRECTIONS))
    record.add_argument("--objective-kind", choices=sorted(KINDS))
    record.add_argument("--objective-name")
    record.add_argument("--cost", help="JSON object with measured resource costs")
    record.add_argument("--feedback")
    record.add_argument("--failure")
    decide = sub.add_parser("decide", help="recommend exploit or explore from archive evidence")
    decide.add_argument("--archive", type=pathlib.Path, required=True)
    decide.add_argument("--current-route")
    decide.add_argument("--objective-direction", choices=sorted(DIRECTIONS))
    decide.add_argument("--recent", type=int, default=4)
    decide.add_argument("--min-stagnant", type=int, default=2)
    decide.add_argument("--tie-epsilon", type=float, default=1e-12)
    decide.add_argument("--output", type=pathlib.Path)
    decide.add_argument("--append", action="store_true", help="append the decision event to the archive")
    show = sub.add_parser("summary", help="print a compact route/status summary")
    show.add_argument("--archive", type=pathlib.Path, required=True)
    show.add_argument("--recent", type=int, default=8, help="number of compact candidate records to show")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "check":
            result = check_candidate(args)
        elif args.command == "record":
            result = record_candidate(args)
        elif args.command == "propose":
            result = {"schema_version": 1, "status": "pending", "proposal": propose_candidate(args)}
        elif args.command == "stop":
            result = stop_proposal(args)
        elif args.command == "trace":
            result = trace_report(args)
        elif args.command == "brief":
            result = optimization_brief(args)
        elif args.command == "decide":
            if (args.recent < 2 or args.min_stagnant < 2 or args.min_stagnant > args.recent
                    or not math.isfinite(args.tie_epsilon) or args.tie_epsilon < 0):
                raise ArchiveFailure("invalid_config", "Require recent >= min-stagnant >= 2 and a finite non-negative tie-epsilon")
            result = route_decision(args)
        else:
            if args.recent < 1:
                raise ArchiveFailure("invalid_config", "recent must be positive")
            result = summarize(args)
    except (OSError, ArchiveFailure, TypeError, ValueError, KeyError, OverflowError) as exc:
        report = {"schema_version": 1, "status": "blocked",
                  "error": {"type": exc.kind if isinstance(exc, ArchiveFailure) else
                             "io_error" if isinstance(exc, OSError) else "invalid_input",
                             "message": str(exc)}}
        print(json.dumps(report, ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    result = ({"schema_version": 1, "status": "success", "candidate": result}
              if args.command == "record" else dict(result))
    result.setdefault("status", "success")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
