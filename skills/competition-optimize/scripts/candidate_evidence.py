"""Pure candidate identities and contract-scoped observation comparisons.

No archive, CLI or evidence file is read here. Records are borrowed by the
comparison view and must remain unchanged for that view's lifetime. Observation
eligibility describes archived evidence, not a new verification or promotion.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


class ArchiveFailure(Exception):
    """A malformed archive or an unsafe archive mutation."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


DEVELOPMENT_ROLES = {"development", "diagnostic"}
DIRECTIONS = {"maximize", "minimize"}
KINDS = {"official_metric", "proxy", "unknown"}
PIPELINE_SCOPES = {"training_pipeline", "execution_pipeline"}
OUTPUT_ONLY_SCOPES = {"prediction_artifact_only", "generated_artifact_only"}


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


def nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArchiveFailure("invalid_candidate", f"{field} must be a non-empty string")
    return value.strip()


def implementation_identity(entry: dict[str, Any]) -> dict[str, Any]:
    """Keep stochastic prediction bytes separate from the snapshotted recipe."""
    result, artifacts = entry["result"], entry["artifacts"]
    prediction = (result.get("candidate_scope") == "prediction_csv" or
                  result.get("candidate_scope") is None and
                  result.get("validity_scope") == "prediction_artifact_and_metric_inputs")
    generated = result.get("candidate_scope") == "generated_artifact"
    if (prediction or generated) and "configuration" in artifacts:
        scope = "training_pipeline" if prediction else "execution_pipeline"
        identity_artifacts = {"configuration": artifacts["configuration"]}
    else:
        scope = "prediction_artifact_only" if prediction else "generated_artifact_only" if generated else "evaluated_artifacts"
        identity_artifacts = dict(artifacts)
    value = {"scope": scope, "artifacts": identity_artifacts}
    # Both output contracts identify the same executable recipe. Changing the
    # scope label must not turn its next measurement into a new implementation.
    fingerprint_value = {**value, "scope": "training_pipeline" if scope in PIPELINE_SCOPES else scope}
    return {**value, "fingerprint": sha256(canonical(fingerprint_value))}


def candidate_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {entry["candidate_id"]: entry for entry in records if entry["event"] == "candidate"}


def measurable(entry: dict[str, Any], *, include_diagnostics: bool = False) -> bool:
    objective, context = entry["objective"], entry["comparison"]
    required = ("evaluator_hash", "workload_hash", "score_model_hash", "stage", "objective_name")
    roles = DEVELOPMENT_ROLES if include_diagnostics else {"development"}
    return (entry["valid"] and entry["role"] in roles
            and objective.get("value") is not None and objective.get("direction") in DIRECTIONS
            and objective.get("kind") in {"proxy", "official_metric"}
            and all(isinstance(context.get(key), str) and context[key] for key in required))


def directed_score(entry: dict[str, Any]) -> float:
    return entry["objective"]["value"] * (-1 if entry["objective"]["direction"] == "minimize" else 1)


def executed_snapshot(entry: dict[str, Any], identity: dict[str, Any]) -> bool:
    """A claimed parent link or output file alone is not an implementation run."""
    result = entry["result"]
    return bool(entry["role"] in DEVELOPMENT_ROLES and result.get("result_path")
                and result.get("result_sha256") and result.get("execution_status")
                and identity["scope"] not in OUTPUT_ONLY_SCOPES
                and set(identity["artifacts"]) <= entry["artifact_paths"].keys())


def observed_snapshot(entry: dict[str, Any], identity: dict[str, Any], *,
                       include_diagnostics: bool = False) -> bool:
    result, objective = entry["result"], entry["objective"]
    return bool(executed_snapshot(entry, identity) and measurable(entry, include_diagnostics=include_diagnostics)
                and result.get("execution_status") == "success" and not result.get("partial")
                and result.get("valid") is not False and all(
                    result.get(result_key) == objective.get(objective_key)
                    for result_key, objective_key in (
                        ("objective_value", "value"), ("objective_direction", "direction"),
                        ("objective_kind", "kind"), ("objective_name", "name"))))


@dataclass(frozen=True)
class ComparisonView:
    comparison: dict[str, Any]
    entries: tuple[dict[str, Any], ...]
    representatives: tuple[dict[str, Any], ...]
    observations: dict[str, tuple[dict[str, Any], ...]]

    def first_profiles(self, field: str) -> list[dict[str, Any]]:
        """First eligible profile of each implementation, in archive order."""
        first = [next((entry for entry in group if field in entry["result"] and
                       observed_snapshot(entry, implementation_identity(entry))), None)
                 for group in self.observations.values()]
        return [entry for entry in first if entry is not None]

    def ranking_conflict(self) -> dict[str, Any] | None:
        """Find an actual repeat reversing the first-observation ordering.

        This is a measurement-review hint, never a new score or promotion rule.
        An alias of the same result file is not another measurement.
        """
        if len(self.representatives) < 2:
            return None
        leader = max(self.representatives, key=directed_score)

        def runs(group: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
            seen: set[tuple[str, str]] = set()
            unique = []
            for entry in group:
                result = entry["result"]
                reference = (result.get("result_path"), result.get("result_sha256"))
                if not all(reference):
                    continue
                if reference not in seen:
                    seen.add(reference)
                    unique.append(entry)
            return unique

        by_first = {group[0]["candidate_id"]: group for group in self.observations.values()}
        leader_group = by_first[leader["candidate_id"]]
        leader_runs = runs(leader_group)
        for challenger in sorted((entry for entry in self.representatives if entry is not leader),
                                 key=directed_score, reverse=True):
            challenger_group = by_first[challenger["candidate_id"]]
            challenger_runs = runs(challenger_group)
            witness = next((entry for entry in leader_runs[1:]
                            if directed_score(entry) < directed_score(challenger)), None)
            reason = "leader_repeat_below_challenger_first"
            if witness is None:
                witness = next((entry for entry in challenger_runs[1:]
                                if directed_score(entry) > directed_score(leader)), None)
                reason = "challenger_repeat_above_leader_first"
            if witness is None:
                continue
            identity = {"comparison_key": sha256(canonical(self.comparison)),
                        "leader_candidate": leader["candidate_id"],
                        "challenger_candidate": challenger["candidate_id"], "reason": reason}
            return {**identity, "signature": sha256(canonical(identity)),
                    "witness_candidate": witness["candidate_id"],
                    "leader_first_value": leader["objective"]["value"],
                    "challenger_first_value": challenger["objective"]["value"],
                    "witness_value": witness["objective"]["value"],
                    "leader_measurements": len(leader_runs),
                    "challenger_measurements": len(challenger_runs),
                    "scope": "Repeated development scores reverse first-observation ordering under one "
                             "complete comparison. This requests a frozen task-specific remeasurement "
                             "protocol; it is not an uncertainty estimate or automatic promotion."}
        return None


class ComparisonEvidence:
    """Project ordered development observations once for one archive prefix.

    The caller supplies its existing eligibility rule. Records are borrowed and
    must not be mutated while this in-memory view is in use. Construction is
    linear in the supplied records; no file I/O or persistent cache occurs.
    Only development candidates enter the view. A missing or non-development
    anchor raises unknown_candidate rather than choosing a different contract.
    """

    def __init__(self, records: list[dict[str, Any]], *,
                 eligible: Callable[[dict[str, Any]], bool]) -> None:
        self._candidates: dict[str, dict[str, Any]] = {}
        self._entries: dict[bytes, list[dict[str, Any]]] = defaultdict(list)
        self._groups: dict[bytes, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
        self._first: list[tuple[bytes, str, dict[str, Any]]] = []
        for entry in records:
            if entry.get("event") != "candidate" or entry.get("role") != "development":
                continue
            self._candidates[entry["candidate_id"]] = entry
            comparison = canonical(entry["comparison"])
            self._entries[comparison].append(entry)
            if not eligible(entry):
                continue
            fingerprint = implementation_identity(entry)["fingerprint"]
            groups = self._groups[comparison]
            if fingerprint not in groups:
                groups[fingerprint] = []
                self._first.append((comparison, fingerprint, entry))
            groups[fingerprint].append(entry)

    def for_candidate(self, candidate_id: str) -> ComparisonView:
        try:
            comparison = self._candidates[candidate_id]["comparison"]
        except KeyError as exc:
            raise ArchiveFailure("unknown_candidate", f"No development candidate {candidate_id!r}") from exc
        key = canonical(comparison)
        groups = self._groups.get(key, {})
        return ComparisonView(comparison, tuple(self._entries[key]),
                              tuple(group[0] for group in groups.values()),
                              {fingerprint: tuple(group) for fingerprint, group in groups.items()})

    def first_observations(self) -> tuple[tuple[bytes, str, dict[str, Any]], ...]:
        """One observed implementation per complete comparison, in archive order."""
        return tuple(self._first)
