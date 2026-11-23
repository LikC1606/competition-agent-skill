#!/usr/bin/env python3
"""Evidence retrieval and search signals for the unattended campaign driver.

Signals request strategy, execution or measurement review; they never promote
a candidate, prove a plateau or stop a campaign. Scores stay contract-scoped.
"""

from __future__ import annotations

import argparse
import pathlib
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Any, Mapping

import candidate_archive as archive_tools
from candidate_evidence import missing_saved_comparison_fields
from campaign_trials import delivered_trials, trial_history
from campaign_handoff import bound_packet

if TYPE_CHECKING:
    from campaign_policy import TurnPlan


HANDOFF_BYTES = 48 * 1024
DEFAULT_STAGNATION_WINDOW = 4
DEFAULT_SESSION_CHECKPOINTS = 8
DEFAULT_FAILURE_REVIEW_WINDOW = 3
DEFAULT_COMPARISON_REVIEW_WINDOW = 4


class CampaignEvidence:
    """One borrowed, accepted archive prefix and its request-local projections.

    Callers must not mutate records while this view is used. Policy signals do
    no file I/O; handoff verification reuses EvidenceReads only in this view.
    Create a new view after accepting another prefix or preparing another turn.
    """

    def __init__(self, records: list[dict[str, Any]], *,
                 comparisons: archive_tools.ComparisonEvidence | None = None) -> None:
        self.records = records
        self._provided_comparisons = comparisons
        self._continuities: dict[int, dict[str, Any]] = {}
        self._objectives: dict[str | None, tuple[dict[str, Any], dict[str, Any] | None]] = {}

    @cached_property
    def _comparisons(self) -> archive_tools.ComparisonEvidence:
        return (self._provided_comparisons if self._provided_comparisons is not None else
                archive_tools.ComparisonEvidence(self.records, eligible=observed_implementation))

    @cached_property
    def _index(self) -> dict[str, dict[str, Any]]:
        return archive_tools.candidate_index(self.records)

    @cached_property
    def _reads(self) -> archive_tools.EvidenceReads:
        return archive_tools.EvidenceReads()

    @cached_property
    def _progress(self) -> dict[str, Any]:
        return objective_progress(self.records, evidence=self._comparisons)

    @cached_property
    def _health(self) -> dict[str, Any]:
        return execution_health(self.records)

    @cached_property
    def _measurement_plan(self) -> dict[str, Any] | None:
        return archive_tools.measurement_plans.first_pending(self.records)

    @cached_property
    def _repeat_conflict(self) -> dict[str, Any] | None:
        anchor = self._progress["anchor_candidate"]
        return self._comparisons.for_candidate(anchor).ranking_conflict() if anchor else None

    @cached_property
    def _measurement_comparisons(self) -> dict[str, dict[str, Any]]:
        return {entry["plan_id"]: entry["comparison"] for entry in self.records if entry["event"] == "measurement_plan"}

    @cached_property
    def _measurement_signatures(self) -> set[str]:
        return {entry["conflict_signature"] for entry in self.records if entry["event"] == "measurement_plan"}

    @cached_property
    def _closed_proposals(self) -> set[str]:
        return {entry["proposal_id"] for entry in self.records
                if entry["event"] in {"candidate", "proposal_stop"} and entry.get("proposal_id")}

    @cached_property
    def _pending_proposals(self) -> dict[str, dict[str, Any]]:
        return {entry["proposal_id"]: entry for entry in self.records
                if entry["event"] == "proposal" and entry["proposal_id"] not in self._closed_proposals}

    def proposal_closed(self, proposal_id: str | None) -> bool:
        return proposal_id is not None and proposal_id in self._closed_proposals

    def proposal_pending(self, proposal_id: str) -> bool:
        return proposal_id in self._pending_proposals

    def pending_in_comparison(self, proposal_id: str | None, comparison: Mapping[str, Any] | None) -> bool:
        proposal = self._pending_proposals.get(proposal_id) if proposal_id else None
        return bool(proposal and comparison is not None and
                    self._index[proposal["parent_ids"][0]]["comparison"] == comparison)

    @cached_property
    def counts(self) -> dict[str, int]:
        candidates = [entry for entry in self.records if entry["event"] == "candidate"]
        identities = [executed_implementation(entry) for entry in candidates]
        proposals = {entry["proposal_id"] for entry in self.records if entry["event"] == "proposal"}
        return {
            "events": len(self.records), "candidates": len(candidates),
            "executed_implementations": len({identity for identity in identities if identity}),
            "evaluated_candidates": sum(bool(entry["result"].get("result_path") and
                                             entry["result"].get("execution_status")) for entry in candidates),
            "diagnostic_evaluations": sum(bool(entry["role"] == "diagnostic" and
                                                entry["result"].get("result_path") and
                                                entry["result"].get("execution_status")) for entry in candidates),
            "measurable_candidates": sum(archive_tools.measurable(entry) for entry in candidates),
            "proposals": len(proposals), "pending_proposals": len(self._pending_proposals),
        }

    def new_implementation_attempts(self, prefix_length: int, *,
                                    reads: archive_tools.EvidenceReads | None = None) -> int:
        """Count new development attempts in the suffix, irrespective of score.

        Raw execution accounting and score ranking keep their existing identity.
        Only this scheduler projection looks through a managed recipe's adapter
        hash; the recipe already excludes fold assignments and measurement seeds.
        """
        if not any(entry["event"] == "candidate" and entry["role"] == "development"
                   for entry in self.records[prefix_length:]):
            return 0
        reads = self._reads if reads is None else reads
        fingerprints: set[str] = set()
        recipes: set[str] = set()
        attempts = 0
        for position, entry in enumerate(self.records):
            fingerprint = executed_implementation(entry)
            if fingerprint is None or fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            recipe = _tabular_attempt_identity(entry, reads)
            new = recipe is None or recipe not in recipes
            if recipe is not None:
                recipes.add(recipe)
            if position >= prefix_length and entry["role"] == "development" and new:
                attempts += 1
        return attempts

    def signals(self, checkpoint: Mapping[str, Any] | None = None, *,
                objective_anchor: str | None = None) -> dict[str, Any]:
        position = checkpoint["distinct_observations"] if checkpoint else 0
        if position not in self._continuities:
            self._continuities[position] = comparison_continuity(self.records, checkpoint, evidence=self._comparisons)
        if objective_anchor not in self._objectives:
            progress = (self._progress if objective_anchor is None else
                        objective_progress(self.records, evidence=self._comparisons,
                                           objective_anchor=objective_anchor))
            anchor = progress["anchor_candidate"]
            conflict = (self._repeat_conflict if objective_anchor is None else
                        self._comparisons.for_candidate(anchor).ranking_conflict() if anchor else None)
            self._objectives[objective_anchor] = progress, conflict
        progress, conflict = self._objectives[objective_anchor]
        return {
            "objective_progress": progress, "execution_health": self._health,
            "comparison_continuity": self._continuities[position],
            "measurement_plan": self._measurement_plan, "repeat_conflict": conflict,
            "measurement_comparisons": self._measurement_comparisons,
            "measurement_signatures": self._measurement_signatures,
        }

    def validate_working_selection(self, selection: Mapping[str, Any], *,
                                   objective_anchor: str | None = None, require_eligibility: bool = False) -> None:
        """Bind an agent's choice to measured primary development evidence.

        Identity checks do not establish the scientific quality of its reason.
        The selection never changes the raw-score ranking.
        """
        entry = self._index.get(selection["candidate_id"])
        progress = self.signals(objective_anchor=objective_anchor)["objective_progress"]
        primary = progress["comparison"]
        if entry is not None and entry["role"] == "development" and primary is not None:
            comparison = entry["comparison"]
            differences = [
                f"{key} (missing)" if comparison.get(key) is None else key
                for key in sorted(primary.keys() | comparison.keys())
                if comparison.get(key) != primary.get(key)
            ]
            if differences:
                raise archive_tools.ArchiveFailure(
                    "working_selection_comparison_mismatch", f"Candidate {selection['candidate_id']} differs from the primary "
                    f"comparison: {', '.join(differences)}. Check the adapter result and record arguments "
                    "against the primary contract before recording a corrected observation.")
        if (entry is None or not observed_implementation(entry)
                or entry["comparison"] != primary):
            raise archive_tools.ArchiveFailure(
                "invalid_working_selection", "Working selection must name a measured development implementation "
                "under the primary comparison; retain the previous choice or correct the receipt")
        if require_eligibility:
            archive_tools.measurement_plans.validate_selection(entry, self.records, reads=self._reads)

    def selection_comparison_pair(self, request: Mapping[str, Any] | None,
                                  progress: Mapping[str, Any]) -> tuple[dict, dict] | None:
        if not request or request["comparison_key"] != progress["comparison_key"]:
            return None
        target = self._index.get(request["candidate_id"])
        if (target is None or not observed_implementation(target)
                or target["comparison"] == progress["comparison"] or not progress["best_candidate"]):
            return None
        # Prefer the actual proposal control when it belongs to the primary comparison.
        for parent_id in target["parent_ids"]:
            parent = self._index[parent_id]
            if parent["comparison"] == progress["comparison"] and observed_implementation(parent):
                return target, parent
        return target, self._index[progress["best_candidate"]]

    def selection_excluded(self, selection: Mapping[str, Any] | None) -> bool:
        return bool(selection and "score_invalidation" in self._index.get(selection["candidate_id"], {}))

    def with_strategy_reference(self, progress: dict[str, Any],
                                selection: Mapping[str, Any] | None) -> dict[str, Any]:
        """Expose stagnation relative to the first valid observation of the adopted implementation."""
        if not selection or selection["comparison_key"] != progress["comparison_key"]:
            return progress
        entry = self._index.get(selection["candidate_id"])
        if entry is None or not observed_implementation(entry) or entry["comparison"] != progress["comparison"]:
            return progress
        view = self._comparisons.for_candidate(entry["candidate_id"])
        identity = archive_tools.implementation_identity(entry)["fingerprint"]
        representative = view.observations[identity][0]
        position = view.representatives.index(representative)
        return {**progress, "strategy_review": {
            "reference_candidate": representative["candidate_id"],
            "basis": "working_selection",
            "implementations_since_reference": len(view.representatives) - position - 1,
        }}


def executed_implementation(entry: dict[str, Any]) -> str | None:
    if entry["event"] != "candidate" or entry["role"] not in archive_tools.DEVELOPMENT_ROLES:
        return None
    result = entry["result"]
    if not result.get("result_path") or not result.get("execution_status"):
        return None
    identity = archive_tools.implementation_identity(entry)
    if identity["scope"] in archive_tools.OUTPUT_ONLY_SCOPES:
        return None
    if not set(identity["artifacts"]) <= entry["artifact_paths"].keys():
        return None
    return identity["fingerprint"]


def _tabular_attempt_identity(entry: dict[str, Any], reads: archive_tools.EvidenceReads) -> str | None:
    if not archive_tools.prediction_result(entry["result"]):
        return None
    name = entry["artifact_paths"].get("configuration")
    if not name or pathlib.Path(name).name != "recipe.json":
        return None
    try:
        raw = reads.read_bytes(pathlib.Path(name))
        if archive_tools.sha256(raw) != entry["artifacts"]["configuration"]:
            return None
        recipe = archive_tools.load_json(raw, name)
    except (archive_tools.ArchiveFailure, OSError):
        # Unavailable or opaque historical snapshots still have a raw identity.
        return None
    if (not isinstance(recipe, dict) or recipe.get("schema_version") != 1
            or not all(isinstance(recipe.get(key), str) and recipe[key]
                       for key in ("adapter_hash", "candidate_source", "training_data_sha256"))
            or not isinstance(recipe.get("features"), list) or not isinstance(recipe.get("prediction_rule"), dict)):
        return None
    return archive_tools.sha256(archive_tools.canonical({key: value for key, value in recipe.items()
                                                         if key != "adapter_hash"}))


def observed_implementation(entry: dict[str, Any]) -> bool:
    # Explicit archive flags may describe a known score, but they cannot invent
    # a measured gain when the adapter result contains no objective.
    if entry["event"] != "candidate" or entry["role"] != "development":
        return False
    return archive_tools._observed_snapshot(entry, archive_tools.implementation_identity(entry))


def objective_progress(records: list[dict[str, Any]], *,
                       evidence: archive_tools.ComparisonEvidence | None = None,
                       objective_anchor: str | None = None) -> dict[str, Any]:
    reference = None
    context = None
    if objective_anchor is not None:
        reference = next((entry for entry in records if entry["event"] == "candidate" and
                          entry["candidate_id"] == objective_anchor), None)
        if reference is None or (not observed_implementation(reference) and "score_invalidation" not in reference):
            raise archive_tools.ArchiveFailure(
                "invalid_objective_anchor", "Objective anchor must name a valid scored development implementation")
        context = reference["comparison"]
    development = [entry for entry in records if entry["event"] == "candidate"
                   and entry["role"] == "development" and "score_invalidation" not in entry]
    if context is None and development:
        # A proposal is dispatched under its first parent's comparison. Keep
        # off-contract results as evidence without letting them choose a new objective.
        controls = {entry["proposal_id"]: entry["parent_ids"][0]
                    for entry in records if entry["event"] == "proposal"}
        candidates = archive_tools.candidate_index(records) if controls else {}
        context = development[-1]["comparison"]  # Bootstrap if no other development record exists.
        for entry in reversed(development):
            control = controls.get(entry.get("proposal_id"))
            if control is None or candidates[control]["comparison"] == entry["comparison"]:
                context = entry["comparison"]
                break
    # A pinned reference still identifies its contract after its score is excluded.
    anchor = next((entry for entry in reversed(development) if entry["comparison"] == context), reference)
    if anchor is None:
        return {"comparison_key": None, "comparison": None, "anchor_candidate": None,
                "objective_anchor": objective_anchor,
                "best_candidate": None, "best_value": None, "comparable_implementations": 0,
                "implementations_since_best": 0, "latest_eligible": False,
                "nonimproving_candidates": [], "improvement_candidates": []}
    evidence = evidence or archive_tools.ComparisonEvidence(records, eligible=observed_implementation)
    measured = evidence.for_candidate(anchor["candidate_id"]).representatives
    best = None
    best_position = 0
    improvements = []
    for position, entry in enumerate(measured):
        if best is None or archive_tools.directed_score(entry) > archive_tools.directed_score(best):
            if best is not None:
                improvements.append(entry["candidate_id"])
            best, best_position = entry, position
    return {"comparison_key": archive_tools.sha256(archive_tools.canonical(context)),
            "comparison": context, "anchor_candidate": anchor["candidate_id"],
            "objective_anchor": objective_anchor,
            "best_candidate": best["candidate_id"] if best else None,
            "best_value": best["objective"]["value"] if best else None,
            "best_archive_status": best["status"] if best else None,
            "scope": "Historical eligible raw-score progress, not adoption or independent confirmation. "
                     "Nonimproving means no new raw best; a working selection may still improve its own control.",
            "comparable_implementations": len(measured),
            "implementations_since_best": len(measured) - best_position - 1 if best else 0,
            "latest_eligible": observed_implementation(anchor),
            "nonimproving_candidates": [entry["candidate_id"] for entry in measured[best_position + 1:]][-8:],
            "improvement_candidates": improvements[-8:]}


def review_due(progress: dict[str, Any], previous: dict[str, Any] | None, window: int) -> bool:
    """Count new implementations since the strategy reference and last review.

    Without a working selection, fall back to historical raw-score progress.
    A review is a context boundary, never an experiment allowance.
    """
    strategy = progress.get("strategy_review")
    since_reference = (strategy["implementations_since_reference"] if strategy else
                       progress["implementations_since_best"])
    if (not progress["latest_eligible"] or not progress["best_candidate"] or
            since_reference < window):
        return False
    if (previous and previous["comparison_key"] == progress["comparison_key"]
            and (strategy or previous["best_candidate"] == progress["best_candidate"])):
        return progress["comparable_implementations"] - previous["comparable_implementations"] >= window
    return True


def comparison_continuity(records: list[dict[str, Any]],
                          previous: dict[str, Any] | None = None, *,
                          evidence: archive_tools.ComparisonEvidence | None = None) -> dict[str, Any]:
    """Find development contracts still lacking a second measured implementation.

    Count first valid (complete comparison, implementation) observations, not
    scores or result files. A stable smoke contract cannot erase an isolated
    full evaluation; remeasuring another implementation under that full
    contract can. The checkpoint marks evidence handed off, not work resolved.
    """
    seen = set()
    paired = set()
    unpaired = {}
    checkpoint = previous["distinct_observations"] if previous else 0
    evidence = evidence or archive_tools.ComparisonEvidence(records, eligible=observed_implementation)
    for comparison_bytes, identity, entry in evidence.first_observations():
        comparison = archive_tools.sha256(comparison_bytes)
        pair = (comparison, identity)
        seen.add(pair)
        if comparison in unpaired:
            del unpaired[comparison]
            paired.add(comparison)
        elif comparison not in paired:
            unpaired[comparison] = (len(seen), entry["candidate_id"])
    pending = list(unpaired.values())  # First observation order; never score order.
    return {"distinct_observations": len(seen), "paired_contracts": len(paired),
            "unpaired_contracts": len(pending),
            "new_unpaired_contracts": sum(position > checkpoint for position, _ in pending),
            "reviewed_observations": checkpoint,
            "latest_unpaired_candidate": pending[-1][1] if pending else None,
            "recent_unpaired_candidates": [candidate_id for _, candidate_id in pending[-8:]],
            "scope": "First valid scored development observations by complete contract and implementation. "
                     "Unpaired contracts lack another measured implementation; this can be legitimate exploration. "
                     "New means first observed after the last successful measurement-review handoff. "
                     "No cross-contract score comparison, promotion or stopping judgement."}


def comparison_review_due(continuity: dict[str, Any], window: int) -> bool:
    return continuity["new_unpaired_contracts"] >= window


def comparison_recovery(records: list[dict[str, Any]], continuity: dict[str, Any], *,
                        reads: archive_tools.EvidenceReads | None = None) -> dict[str, Any] | None:
    reads = archive_tools.EvidenceReads() if reads is None else reads
    if not continuity["latest_unpaired_candidate"]:
        return None
    index = archive_tools.candidate_index(records)
    target = index[continuity["latest_unpaired_candidate"]]
    identity = executed_implementation(target)
    parents = list(target["parent_ids"])
    visited = set()
    reference = None
    position = 0
    while position < len(parents):
        candidate_id = parents[position]
        position += 1
        if candidate_id in visited:
            continue
        visited.add(candidate_id)
        entry = index[candidate_id]
        if entry["role"] not in archive_tools.DEVELOPMENT_ROLES:
            continue
        if observed_implementation(entry) and executed_implementation(entry) != identity:
            reference = entry
            break
        parents.extend(entry["parent_ids"])
    relationship = "different_implementation_ancestor" if reference else "earlier_development_observation"
    if reference is None:
        for entry in records:
            if entry["event"] != "candidate":
                continue
            if entry["candidate_id"] == target["candidate_id"]:
                break
            if observed_implementation(entry) and executed_implementation(entry) != identity:
                reference = entry

    examples = [index[candidate_id] for candidate_id in continuity["recent_unpaired_candidates"][-4:]]
    return comparison_recovery_cards(target, reference, relationship, examples,
                                     continuity["unpaired_contracts"] - len(examples), reads)


def comparison_recovery_cards(target: dict, reference: dict | None, relationship: str,
                              examples: list[dict], omitted: int,
                              reads: archive_tools.EvidenceReads) -> dict[str, Any]:
    def card(entry: dict[str, Any], *, compact: bool = False) -> dict[str, Any]:
        archive_tools.verify_result(entry, reads=reads)
        archive_tools.verify_artifacts(entry, reads=reads)
        implementation = archive_tools.implementation_identity(entry)
        result = {"candidate_id": entry["candidate_id"],
                  "implementation_fingerprint": implementation["fingerprint"],
                  "comparison_sha256": archive_tools.sha256(archive_tools.canonical(entry["comparison"])),
                  "result_path": entry["result"]["result_path"],
                  "result_sha256": entry["result"]["result_sha256"],
                  "identity_checks": {"result_bytes": "checked", "snapshot_bytes": "checked"}}
        if not compact:
            result.update(implementation=implementation, artifact_paths=entry["artifact_paths"],
                          comparison=entry["comparison"], requires_revalidation=True)
        return result

    return {"target": card(target), "reference": card(reference) if reference else None,
            "reference_relationship": relationship if reference else None,
            "changed_fields": (sorted(key for key in target["comparison"].keys() | reference["comparison"].keys()
                                      if target["comparison"].get(key) != reference["comparison"].get(key))
                               if reference else []),
            "unpaired_examples": [card(entry, compact=True) for entry in examples],
            "examples_omitted": omitted,
            "scope": "Identity and retrieval evidence only; no cross-contract scores or feedback. "
                     "Inspect changed fields and the fixed task, then select an existing legal common development "
                     "contract and measure a trusted reference and candidate under it. Reuse source snapshots "
                     "and record genuine new results with a reuse reason when appropriate. Compare only within "
                     "the complete matching contract. Do not alter the fixed evaluator or use confirmation feedback."}


def execution_health(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay operational failures without assigning them an objective score.

    Early failures often have no metric/evaluator identity, so full comparison
    buckets would disconnect a failed run from its preceding successful run.
    This chronological signal compares no scores and ignores confirmation.
    """
    def observed(entry: dict[str, Any]) -> bool:
        return archive_tools._observed_snapshot(entry, archive_tools.implementation_identity(entry),
                                                include_diagnostics=True)

    attempts = {}
    for entry in records:
        identity = executed_implementation(entry)
        if identity is None or "score_invalidation" in entry:
            continue
        result = entry["result"]
        reference = (identity, result["result_path"], result.get("result_sha256"))
        previous = attempts.get(reference)
        if previous is None or (observed(entry) and not observed(previous)):
            # A metadata repair completes the original attempt in place.
            attempts[reference] = entry
    anchor = next(reversed(attempts.values()), None)
    last_scored = None
    tail = []
    for entry in reversed(attempts.values()):
        if observed(entry):
            last_scored = entry["candidate_id"]
            break
        tail.append(entry["candidate_id"])
    issue = None
    if tail:
        result = anchor["result"]
        issue = ("failed_or_invalid_execution" if not anchor["valid"] or result.get("valid") is False
                 or result.get("execution_status") != "success" or result.get("partial")
                 else "unusable_objective")
    return {"anchor_candidate": anchor["candidate_id"] if anchor else None,
            "execution_attempts": len(attempts), "attempts_without_observation": len(tail),
            "last_scored_candidate": last_scored, "needs_attention": bool(tail), "issue": issue,
            "recent_unmeasured_candidates": list(reversed(tail[:8])),
            "scope": "Chronological development and diagnostic execution health only; contracts may differ. "
                     "No objective ranking or causal judgement; one attempt per result reference."}


def execution_review_due(health: dict[str, Any], previous: dict[str, Any] | None, window: int) -> bool:
    if not health["needs_attention"] or health["attempts_without_observation"] < window:
        return False
    if previous and previous["last_scored_candidate"] == health["last_scored_candidate"]:
        return health["execution_attempts"] - previous["execution_attempts"] >= window
    return True


def recovery_evidence(records: list[dict[str, Any]], health: dict[str, Any], *,
                      reads: archive_tools.EvidenceReads | None = None) -> dict[str, Any] | None:
    reads = archive_tools.EvidenceReads() if reads is None else reads
    if not health["needs_attention"]:
        return None
    index = archive_tools.candidate_index(records)
    anchor = index[health["anchor_candidate"]]
    # Search the actual development lineage; a confirmation ancestor cannot
    # become a source of repair feedback or a parent selection hint.
    parents = list(anchor["parent_ids"])
    visited = set()
    reference = None
    position = 0
    while position < len(parents):
        candidate_id = parents[position]
        position += 1
        if candidate_id in visited:
            continue
        visited.add(candidate_id)
        entry = index[candidate_id]
        if entry["role"] not in archive_tools.DEVELOPMENT_ROLES:
            continue
        if observed_implementation(entry):
            reference = entry
            break
        parents.extend(entry["parent_ids"])
    relationship = "scored_ancestor" if reference else "earlier_development_observation"
    if reference is None:
        reference = next((entry for entry in reversed(records) if observed_implementation(entry)), None)

    def card(entry: dict[str, Any]) -> dict[str, Any]:
        archive_tools.verify_result(entry, reads=reads)
        archive_tools.verify_artifacts(entry, reads=reads)
        result = entry["result"]
        raw = reads.read_bytes(pathlib.Path(result["result_path"]))
        if archive_tools.sha256(raw) != result["result_sha256"]:
            raise archive_tools.ArchiveFailure("result_changed", "Recovery result changed while reading")
        value = archive_tools.load_json(raw, result["result_path"])
        error = value.get("error")
        diagnostic = {"error": ({key: error.get(key) if isinstance(error.get(key), str) else None
                                  for key in ("type", "phase", "message")}
                                  if isinstance(error, dict) else error if isinstance(error, str) else None),
                      "partial": bool(result.get("partial")),
                      "artifacts": [item for item in value.get("artifacts", []) if isinstance(item, str)]
                                   if isinstance(value.get("artifacts"), list) else []}
        if missing := missing_saved_comparison_fields(entry):
            diagnostic["missing_comparison_fields"] = missing
            if (entry["role"] == "development" and not entry.get("proposal_id")
                    and not result.get("training_execution") and not archive_tools.prediction_result(result)
                    and result.get("objective_name") and result.get("objective_direction")):
                diagnostic["record_metadata"] = {key: entry[key] for key in ("route", "mechanism", "status")}
        return {"candidate_id": entry["candidate_id"], "role": entry["role"], "parent_ids": entry["parent_ids"],
                "implementation": archive_tools.implementation_identity(entry),
                "artifact_paths": entry["artifact_paths"], "comparison": entry["comparison"],
                "result_path": result["result_path"], "result_sha256": result["result_sha256"],
                "execution_status": result["execution_status"], "diagnostic": diagnostic,
                "identity_checks": {"result_bytes": "checked", "snapshot_bytes": "checked"}}

    return {"target": card(anchor), "reference": card(reference) if reference else None,
            "reference_relationship": relationship if reference else None,
            "reference_comparison_matches": reference["comparison"] == anchor["comparison"] if reference else None,
            "scope": "Inspect actual error/phase and cited logs before choosing the responsible code or environment. "
                     "An unscored run is not evidence against its algorithm. A reference under another contract "
                     "must be revalidated; do not modify the fixed evaluator to make a candidate pass."}


def delivered_exposures(packet: dict[str, Any]) -> dict[str, list[str]]:
    """A bounded hint counts as delivered only with its full evidence identity.

    Feedback prose and reuse history may be shortened. Original code/result
    pointers, proposal targets and referenced IDs must remain recoverable.
    """
    brief = packet.get("development_brief") or {}
    cards = brief.get("candidates", {})
    references = brief.get("pending_references", {})
    omissions = packet.get("truncated_fields", {})

    def complete_field(prefix: str) -> bool:
        return not any(path == prefix or path.startswith(prefix + "/") for path in omissions)

    def complete_card(candidate_id: str, *, unmeasured: bool = False) -> bool:
        collection = "candidates" if candidate_id in cards else "pending_references"
        if collection == "pending_references" and not unmeasured:
            return False
        card = (cards if collection == "candidates" else references).get(candidate_id, {})
        identity, result = card.get("implementation", {}), card.get("result", {})
        expected = {"result_bytes": "checked" if result.get("result_path") else "not_recorded",
                    "snapshot_bytes": "checked" if card.get("artifact_paths") else "not_recorded"}
        if (not identity.get("fingerprint") or not identity.get("artifacts")
                or card.get("identity_checks") != expected
                or bool(result.get("result_path")) != bool(result.get("result_sha256"))
                or not all(complete_field(f"/development_brief/{collection}/{candidate_id}/{key}")
                           for key in ("artifact_paths", "implementation", "result"))):
            return False
        return unmeasured or expected == {"result_bytes": "checked", "snapshot_bytes": "checked"}

    implementations = []
    for item in brief.get("review_frontier", {}).get("selection", []):
        fingerprint = item["implementation_fingerprint"]
        roots = {item["candidate_id"], item.get("feedback_candidate_id", item["candidate_id"])}
        required = roots | ({item["latest_successor"]} if item.get("latest_successor") else set())
        if (all(complete_card(candidate_id) for candidate_id in required)
                and all(cards[candidate_id]["implementation"]["fingerprint"] == fingerprint for candidate_id in roots)):
            implementations.append(fingerprint)

    proposals = []
    for position, item in enumerate(brief.get("pending_details", [])):
        prefix = f"/development_brief/pending_details/{position}"
        try:
            archive_tools.validate_construction_targets(item)
            checks = archive_tools.proposal_identity_checks(item)
        except archive_tools.ArchiveFailure:
            continue
        if (item.get("identity_checks") != checks
                or not item.get("proposal_id")
                or not all(complete_field(f"{prefix}/{key}")
                           for key in ("proposal_id", "input_sha256", "parent_ids", "feedback_from", "code_targets", "construction_mode", "learning_from"))):
            continue
        required = set(item["parent_ids"] + item["feedback_from"] + item.get("learning_from", []))
        if all(complete_card(candidate_id, unmeasured=True) for candidate_id in required):
            proposals.append(item["proposal_id"])
    return {"implementations": implementations, "proposals": proposals}


def _comparison_review_identity(packet: dict[str, Any]) -> dict[str, Any]:
    recovery = packet["comparison_recovery"]
    result = {"archive_path": packet["archive_path"], "changed_fields": recovery["changed_fields"]}
    for name in ("target", "reference"):
        card = recovery[name]
        result[name] = ({key: card.get(key) for key in
                         ("candidate_id", "implementation_fingerprint", "comparison_sha256", "result_path",
                          "result_sha256", "identity_checks")} if card else None)
    return result


def delivered_comparison_review(packet: dict[str, Any]) -> bool:
    """Do not consume a review whose recovery pointers were lost to bounding."""
    recovery = packet.get("comparison_recovery")
    if not recovery or not recovery.get("target"):
        return False
    if not isinstance(packet.get("archive_path"), str) or not isinstance(recovery.get("changed_fields"), list):
        return False
    for name in ("target", "reference"):
        card = recovery.get(name)
        if card is None and name == "reference":
            continue
        for key in ("candidate_id", "implementation_fingerprint", "comparison_sha256", "result_path", "result_sha256"):
            if not isinstance(card.get(key), str) or not card[key]:
                return False
        if card.get("identity_checks") != {"result_bytes": "checked", "snapshot_bytes": "checked"}:
            return False
    # The bounded omission index may merge paths after 64 entries. Compare the
    # actual retrieval material with its pre-bounding digest instead of treating
    # absence from that index as proof that every critical pointer survived.
    return recovery.get("retrieval_sha256") == archive_tools.sha256(
        archive_tools.canonical(_comparison_review_identity(packet)))


def _repeat_conflict_identity(packet: dict[str, Any]) -> dict[str, Any]:
    conflict = packet["repeat_conflict"]
    result = {"archive_path": packet["archive_path"], "signature": conflict["signature"],
              "comparison_key": conflict["comparison_key"], "reason": conflict["reason"]}
    for name in ("leader", "challenger", "witness"):
        result[name] = {key: conflict["cards"][name].get(key) for key in
                        ("candidate_id", "implementation_fingerprint", "comparison_sha256",
                         "result_path", "result_sha256", "identity_checks")}
    return result


def delivered_repeat_conflict(packet: dict[str, Any]) -> bool:
    """Only a complete, verified conflict card can consume its review."""
    conflict = packet.get("repeat_conflict")
    if not isinstance(conflict, dict) or not isinstance(conflict.get("cards"), dict):
        return False
    if any(not isinstance(conflict.get(key), str) or not conflict[key] for key in
           ("signature", "comparison_key", "reason")):
        return False
    try:
        for name in ("leader", "challenger", "witness"):
            card = conflict["cards"][name]
            if not isinstance(card, dict):
                return False
            if any(not isinstance(card.get(key), str) or not card[key] for key in
                   ("candidate_id", "implementation_fingerprint", "comparison_sha256",
                    "result_path", "result_sha256")):
                return False
            if card.get("identity_checks") != {"result_bytes": "checked", "snapshot_bytes": "checked"}:
                return False
        return conflict.get("retrieval_sha256") == archive_tools.sha256(
            archive_tools.canonical(_repeat_conflict_identity(packet)))
    except (KeyError, TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Handoff:
    packet: dict[str, Any]
    delivery: dict[str, Any]


def current_research_state(memory: Mapping[str, Any], comparison_key: str | None) -> dict[str, Any] | None:
    research = memory.get("research_state")
    if not research or research["comparison_key"] != comparison_key:
        return None
    finding = research.get("finding")
    if finding:
        corrections = memory.get("research_corrections", {}).get(comparison_key or "null", {})
        replacement = corrections.get(finding["premise_id"])
        if replacement and replacement["turn"] >= research["turn"]:
            # The question's proposed actions may still depend on this finding.
            # Keep the old receipt for history and use the keyed correction instead.
            return None
    return research


def prepare_handoff(memory: Mapping[str, Any], prepared: TurnPlan, view: CampaignEvidence,
                    task_sha256: str) -> Handoff:
    """Prepare bounded evidence and its schema-v2 delivery intent together.

    Only complete cards remaining in the final packet are offered for later
    acknowledgment. Persisting or rendering a packet does not acknowledge it.
    """
    facts = view.signals(memory["comparison_review_checkpoint"], objective_anchor=memory.get("objective_anchor"))
    key = facts["objective_progress"]["comparison_key"]
    research = current_research_state(memory, key)
    corrections = sorted(memory.get("research_corrections", {}).get(key or "null", {}).values(),
                         key=lambda row: (-row["turn"], row["report"]["key"]))
    selection = memory.get("working_selection")
    if selection and selection["comparison_key"] != key:
        selection = None
    decision_context = ({"research_state": research, "corrections": corrections,
                         "scope": "Agent interpretations and maintenance audits under the current development comparison. "
                                  "A status=withdrawn report retracts that key; do not reuse its older claim. "
                                  "Other corrections supersede the same key in older receipts, not sealed observations. "
                                  "Recheck source entities and premises before relying on a report; "
                                  "conditions, limitations and reopening evidence do not prove causality."}
                        if research or corrections else None)
    packet = handoff_packet(
        pathlib.Path(memory["archive"]), view.records, memory["archive_snapshot"], task_sha256,
        progress=prepared.updates["objective_progress"], health=facts["execution_health"],
        continuity=facts["comparison_continuity"], _view=view,
        measurement_plan=facts["measurement_plan"], mode=prepared.updates["next_mode"],
        selection_pair=view.selection_comparison_pair(prepared.review_requests.get("selection_comparison"),
                                                      prepared.updates["objective_progress"]),
        decision_context=decision_context,
        working_selection=selection,
        frontier_seen=memory["frontier_exposures"].get(key, {}),
        pending_seen=memory["pending_proposal_exposures"].get(key, {}),
        trial_seen=memory["trial_exposures"].get(key, {}),
        learning_seen=memory["learning_exposures"].get(key, {}))
    exposed = delivered_exposures(packet)
    reviews = dict(prepared.review_requests)
    if "comparison" in reviews and not delivered_comparison_review(packet):
        reviews.pop("comparison")
    if "selection_comparison" in reviews and not delivered_comparison_review(packet):
        reviews.pop("selection_comparison")
    if "repeat" in reviews and not delivered_repeat_conflict(packet):
        reviews.pop("repeat")
    return Handoff(packet, {
        "frontier_exposure": {"comparison_key": key, "implementations": exposed["implementations"]},
        "pending_proposal_exposure": {"comparison_key": key, "proposals": exposed["proposals"]},
        "trial_exposure": {"comparison_key": key, "proposals": delivered_trials(packet)},
        "learning_exposure": {"comparison_key": key,
                              "candidates": archive_tools.scoped_learning.delivered(packet)},
        "review_checkpoints": reviews,
    })


def handoff_packet(archive: pathlib.Path, records: list[dict[str, Any]],
                   snapshot: dict[str, Any], task_sha256: str, *,
                   progress: dict[str, Any] | None = None,
                   health: dict[str, Any] | None = None,
                   continuity: dict[str, Any] | None = None,
                   frontier_seen: dict[str, int] | None = None,
                   pending_seen: dict[str, int] | None = None,
                   trial_seen: dict[str, int] | None = None,
                   learning_seen: dict[str, int] | None = None,
                   evidence: archive_tools.ComparisonEvidence | None = None,
                   measurement_plan: dict[str, Any] | None = None,
                   selection_pair: tuple[dict, dict] | None = None,
                   decision_context: dict[str, Any] | None = None,
                   working_selection: dict[str, Any] | None = None,
                   _view: CampaignEvidence | None = None, mode: str = "work") -> dict[str, Any]:
    view = _view if _view is not None else CampaignEvidence(records, comparisons=evidence)
    reads, evidence = view._reads, view._comparisons
    if progress is None:
        progress = view._progress
    if health is None:
        health = view._health
    if continuity is None:
        continuity = view.signals()["comparison_continuity"]
    if measurement_plan is None:
        measurement_plan = view._measurement_plan
    if selection_pair is not None:
        target, reference = selection_pair
        recovery = comparison_recovery_cards(target, reference, "primary_development_reference", [], 0, reads)
        packet = {"schema_version": 1, "archive_path": str(archive), "archive_snapshot": snapshot,
                  "task_sha256": task_sha256, "objective_progress": progress,
                  "comparison_continuity": continuity, "comparison_recovery": recovery,
                  "working_selection": working_selection,
                  "scope": "Recover one missing primary comparison for a requested working selection."}
        recovery["retrieval_sha256"] = archive_tools.sha256(archive_tools.canonical(_comparison_review_identity(packet)))
        return bound_packet(packet, budget=HANDOFF_BYTES, mode=mode)
    execution_recovery = recovery_evidence(records, health, reads=reads)
    target = (execution_recovery or {}).get("target") or {}
    if mode == "repair" and measurement_plan is None and target.get("diagnostic", {}).get("record_metadata"):
        # A saved score needs its comparison bindings. Keep other proposals,
        # strategy cards and their exposure accounting for the next checkpoint.
        packet = {"schema_version": 1, "archive_path": str(archive), "archive_snapshot": snapshot,
                  "task_sha256": task_sha256, "objective_progress": progress, "execution_health": health,
                  "execution_recovery": {**execution_recovery, "reference": None,
                                         "reference_relationship": None, "reference_comparison_matches": None},
                  "scope": "Recover comparison metadata for the saved development result."}
        return bound_packet(packet, budget=HANDOFF_BYTES, mode=mode)
    index = view._index
    repeat_conflict = None
    if progress["anchor_candidate"]:
        repeat_conflict = (view._repeat_conflict if progress["anchor_candidate"] == view._progress["anchor_candidate"] else
                           evidence.for_candidate(progress["anchor_candidate"]).ranking_conflict())
        if repeat_conflict:
            repeat_conflict = dict(repeat_conflict)
            cards = {}
            for name in ("leader", "challenger", "witness"):
                entry = index[repeat_conflict[name + "_candidate"]]
                archive_tools.verify_result(entry, reads=reads)
                archive_tools.verify_artifacts(entry, reads=reads)
                cards[name] = {"candidate_id": entry["candidate_id"],
                               "implementation_fingerprint": archive_tools.implementation_identity(entry)["fingerprint"],
                               "comparison_sha256": archive_tools.sha256(archive_tools.canonical(entry["comparison"])),
                               "result_path": entry["result"]["result_path"],
                               "result_sha256": entry["result"]["result_sha256"],
                               "identity_checks": {"result_bytes": "checked", "snapshot_bytes": "checked"}}
            repeat_conflict["cards"] = cards
    related = {identity for candidate_id in (progress["anchor_candidate"], progress["best_candidate"],
                                            (working_selection or {}).get("candidate_id"))
               if candidate_id and (identity := executed_implementation(index[candidate_id]))}
    brief = None
    if progress["anchor_candidate"]:
        if working_selection:
            view.validate_working_selection(working_selection, objective_anchor=progress.get("objective_anchor"))
        brief = archive_tools.EvidenceSnapshot._from_views(
            archive, records, rankable=observed_implementation, reads=reads, comparisons=evidence).brief(
                archive_tools.BriefQuery(anchor=progress["anchor_candidate"], recent=4, routes=4, frontier=2,
                                         frontier_seen=frontier_seen, pending_seen=pending_seen,
                                         learning_seen={} if learning_seen is None else learning_seen,
                                         include_candidates=((working_selection["candidate_id"],)
                                                             if working_selection else ())))
        brief["scope"] += " Best representatives in this packet additionally require a scored adapter result and code/recipe snapshot."
        # Other comparison contracts remain in the archive for reconciliation;
        # they must not become the new session's active proposal list.
        brief["pending_proposals"] = brief.pop("matched_pending_proposals")
        # Preserve parent-relative observations without turning explanations into
        # universal rules. Cross-contract parents cannot supply a signed gain.
        for candidate_id, card in brief["candidates"].items():
            entry = index[candidate_id]
            gains = {}
            for parent_id in entry["parent_ids"]:
                parent = index[parent_id]
                gains[parent_id] = (archive_tools.directed_score(entry) - archive_tools.directed_score(parent)
                                    if observed_implementation(entry) and observed_implementation(parent)
                                    and parent["comparison"] == entry["comparison"] else None)
            card["objective_gain_vs_parents"] = gains
            card["feedback_scope"] = "Agent observations for this implementation and comparison; causal claims unverified"
    packet = {"schema_version": 1, "archive_path": str(archive), "archive_snapshot": snapshot,
              "task_sha256": task_sha256, "objective_progress": progress,
              "execution_health": health, "execution_recovery": execution_recovery,
              "comparison_continuity": continuity,
              "comparison_recovery": comparison_recovery(records, continuity, reads=reads),
              "repeat_conflict": repeat_conflict,
              "measurement_plan": ({"plan_id": measurement_plan["plan_id"],
                                    "conflict_signature": measurement_plan["conflict_signature"],
                                    "comparison_key": archive_tools.sha256(archive_tools.canonical(measurement_plan["comparison"])),
                                    "remaining_slots": sum(item[name] is None for item in measurement_plan["runs"]
                                                           for name in ("leader", "challenger")),
                                    "pairs_complete": measurement_plan["complete"],
                                    "rule_state": measurement_plan["rule_result"]["state"],
                                    "next_run_id": next((item["run_id"] for item in measurement_plan["runs"]
                                                         if item["leader"] is None or item["challenger"] is None), None),
                                    "scope": "Read the full frozen protocol and paired outcomes with candidate_archive.py "
                                             "measure-status --archive PATH --plan-id ID."}
                                   if measurement_plan else None),
              "measurement_decision": archive_tools.measurement_plans.latest_decision(
                  records, progress["comparison"], reads=reads),
              "measurement_stop": archive_tools.measurement_plans.latest_stop(
                  records, progress["comparison"], reads=reads),
              "trial_history": trial_history(archive, records, progress["comparison"], related, seen=trial_seen, reads=reads),
              "development_brief": brief,
              "working_selection": working_selection,
              "scope": "Matched development evidence only. Best scores are observations, not certified promotion. "
                       "Read the cited code/results for the next decision. Truncated fields are retrieval hints, "
                       "not complete identifiers or executable paths. Confirmation scores never guide the next proposal."}
    if packet["comparison_recovery"]:
        packet["comparison_recovery"]["retrieval_sha256"] = archive_tools.sha256(
            archive_tools.canonical(_comparison_review_identity(packet)))
    if repeat_conflict:
        repeat_conflict["retrieval_sha256"] = archive_tools.sha256(
            archive_tools.canonical(_repeat_conflict_identity(packet)))
    exclusions = {entry["score_invalidation"]["candidate_id"]
                  for entry in index.values() if "score_invalidation" in entry
                  and entry["comparison"] == progress["comparison"]}
    if exclusions:
        packet["score_invalidations"] = [entry for entry in records
                                         if entry["event"] == "score_invalidation"
                                         and entry["candidate_id"] in exclusions][-2:][::-1]
    if decision_context:
        packet["decision_context"] = decision_context
    return bound_packet(packet, budget=HANDOFF_BYTES, mode=mode)
