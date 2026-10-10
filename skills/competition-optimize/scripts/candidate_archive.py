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
    for index, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        value = load_json(line, f"{path}:{index}")
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ArchiveFailure("invalid_archive", f"{path}:{index}: expected schema_version 1 object")
        if value.get("event") not in {"candidate", "decision"}:
            raise ArchiveFailure("invalid_archive", f"{path}:{index}: unknown event")
        if value["event"] == "candidate":
            validate_candidate(value)
            candidate_id = value["candidate_id"]
            if candidate_id in seen or not set(value["parent_ids"]) <= seen:
                raise ArchiveFailure("invalid_archive", f"{path}:{index}: duplicate ID or unknown parent")
            seen.add(candidate_id)
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
        result = entry["result"]
        if result.get("result_path") and sha256(pathlib.Path(result["result_path"]).read_bytes()) != result["result_sha256"]:
            raise ArchiveFailure("result_changed", f"Result bytes changed for {entry['candidate_id']}")
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
            "decision_count": len(records) - len(candidates),
            "recent_candidates": [{key: entry[key] for key in ("candidate_id", "parent_ids", "fingerprint", "artifact_paths", "route", "status", "valid", "role", "objective", "comparison", "cost", "result", "feedback", "failure_mechanism")}
                                  for entry in candidates[-args.recent:]],
            "routes": {route: {"candidates": info["candidates"],
                               "statuses": dict(info["statuses"]), "latest": info["latest"]}
                       for route, info in sorted(routes.items())}}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check for exact artifact duplicates before evaluation")
    check.add_argument("--archive", type=pathlib.Path, required=True)
    check.add_argument("--source", type=pathlib.Path)
    check.add_argument("--configuration", type=pathlib.Path)
    check.add_argument("--reuse-reason", help="why an unchanged candidate needs another measurement")
    record = sub.add_parser("record", help="append one candidate evidence record")
    record.add_argument("--archive", type=pathlib.Path, required=True)
    record.add_argument("--candidate-id", required=True)
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
