"""Pure turn decisions for an unattended campaign.

The driver owns evidence acceptance, sealed requests, processes and persistence.
This module returns schema-v2 state updates without mutating its inputs. Work
selection and context lifetime are independent; a fresh context can keep working
on the same frozen measurement plan.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from candidate_evidence import ArchiveFailure
from campaign_search import (
    CampaignEvidence, comparison_review_due, current_research_state, execution_review_due,
    observed_implementation, review_due,
)

DISCOVER = (
    "Resolve one evidence gap for a mechanism under the current primary comparison. Inspect an original "
    "source, relevant code, or a falsifiable derivation that can change the design. Use existing evidence "
    "and tools. If ready, archive a proposal with its distinguishing change, expected observation, matched "
    "check and stop condition, and select it with next_proposal_id. Otherwise report the missing premise "
    "and the next check. Do not start new fits in this discovery step. A newly checked premise can be "
    "recorded as research_finding with the exact evidence and how it changes the design."
)


@dataclass(frozen=True)
class TurnPlan:
    updates: dict[str, Any]
    fresh_context: bool
    context_refresh_reason: str
    review_requests: dict[str, Any]
    driver_action: str | None = None


@dataclass(frozen=True)
class TurnOutcome:
    evidence: CampaignEvidence
    appended_events: list[dict[str, Any]]
    archive_delta: Mapping[str, int]
    receipt: Mapping[str, Any] | None
    now: float
    receipt_path: str | None = None
    finding_sha256: str | None = None
    local_delivery_hashes: Mapping[str, str] | None = None
    unmatched_selection: str | None = None


@dataclass(frozen=True)
class _Work:
    mode: str
    driver_action: str | None = None
    reason: str = ""
    reviews: dict[str, Any] = field(default_factory=dict)


def update_research_corrections(memory: Mapping[str, Any], origin: Mapping[str, Any],
                                reports: list[dict[str, Any]]) -> dict[str, Any]:
    corrections = copy.deepcopy(memory.get("research_corrections", {}))
    # Keep JSON keys stable even before a development comparison exists.
    current = corrections.setdefault(origin["comparison_key"] or "null", {})
    for report in reports:
        previous = current.get(report["key"])
        row = {**origin, "report": copy.deepcopy(report)}
        if previous and previous.get("receipt_path"):
            row["supersedes_receipt_path"] = previous["receipt_path"]
        current[report["key"]] = row
    return corrections


def archived_proposal_action(proposal_id: str) -> str:
    return (f"Review the archived outcome of proposal {json.dumps(proposal_id, ensure_ascii=False)} "
            "and choose the next development action.")


def missing_proposal_action(proposal_id: str, receipt_path: str | None) -> str:
    pointer = f" at {receipt_path}" if receipt_path else ""
    return (f"Review the design and evidence in the saved receipt{pointer}. "
            f"The requested proposal {json.dumps(proposal_id, ensure_ascii=False)} needs a pending archive "
            "record under the primary comparison before execution. Use candidate_archive.py propose "
            "for a supported design or select an existing matching pending proposal.")


def resolved_proposal_updates(memory: Mapping[str, Any], evidence: CampaignEvidence,
                              progress: Mapping[str, Any]) -> dict[str, Any]:
    """Reconcile selection and registration against the accepted archive."""
    updates: dict[str, Any] = {}
    selected = memory.get("next_proposal_id")
    if selected and not evidence.proposal_pending(selected):
        updates.update(next_proposal_id=None, next_action=archived_proposal_action(selected))
    research_id = (memory.get("research_state") or {}).get("proposal_id")
    registration = memory.get("proposal_registration")
    if registration:
        proposal_id = registration["proposal_id"]
        same_comparison = registration["comparison_key"] == progress["comparison_key"]
        if same_comparison and evidence.pending_in_comparison(proposal_id, progress["comparison"]):
            updates.update(proposal_registration=None, next_proposal_id=proposal_id, next_mode="execute")
        elif not same_comparison or evidence.proposal_pending(proposal_id) or evidence.proposal_closed(proposal_id):
            updates["proposal_registration"] = None
            if research_id == proposal_id:
                updates["research_state"] = None
            if (same_comparison and evidence.proposal_closed(proposal_id)
                    and memory.get("last_receipt_path") == registration["receipt_path"]):
                updates["next_action"] = archived_proposal_action(proposal_id)
    active_registration = updates.get("proposal_registration", registration)
    if (research_id and not evidence.proposal_pending(research_id)
            and research_id != (active_registration or {}).get("proposal_id")):
        updates["research_state"] = None
    return updates


def pending_local_delivery(memory: Mapping[str, Any], progress: Mapping[str, Any],
                           evidence: CampaignEvidence) -> Mapping[str, Any] | None:
    delivery = memory.get("local_delivery")
    selection = memory.get("working_selection")
    if (delivery and delivery["status"] == "requested" and selection
            and delivery["comparison_key"] == selection["comparison_key"] == progress["comparison_key"]
            and delivery["candidate_id"] == selection["candidate_id"] and not evidence.selection_excluded(selection)):
        return delivery
    return None


def has_completed_local_delivery(memory: Mapping[str, Any], candidate_id: str,
                                 comparison_key: str | None) -> bool:
    delivery = memory.get("local_delivery")
    return bool(delivery and delivery["status"] == "completed"
                and delivery["candidate_id"] == candidate_id
                and delivery["comparison_key"] == comparison_key)


def validate_local_delivery(memory: Mapping[str, Any], turn: Mapping[str, Any],
                            receipt: Mapping[str, Any], evidence: CampaignEvidence) -> Mapping[str, Any] | None:
    """Return the validated report if it changes the recorded local delivery."""
    report = receipt.get("local_delivery")
    delivering = turn["mode"] == "deliver"
    if report is None and not delivering:
        return None
    progress = evidence.signals(objective_anchor=memory.get("objective_anchor"))["objective_progress"]
    comparison_key = progress["comparison_key"]
    already_delivered = report and has_completed_local_delivery(memory, report["candidate_id"], comparison_key)
    if delivering:
        pending = pending_local_delivery(memory, progress, evidence)
        if (not pending or not report or report["status"] == "requested"
                or pending["candidate_id"] != report["candidate_id"]
                or report["candidate_id"] != turn.get("local_delivery_candidate_id")
                or any(key in receipt for key in ("working_selection", "next_proposal_id",
                                                  "research_state", "research_finding", "corrections"))):
            raise ArchiveFailure("invalid_local_delivery", "Delivery receipt must close the sealed local request "
                                 "without revising the working selection or research continuation")
    else:
        selection = receipt.get("working_selection", memory.get("working_selection"))
        if (receipt["status"] != "continue" or not selection
                or selection["candidate_id"] != report["candidate_id"]):
            raise ArchiveFailure("invalid_local_delivery", "Local delivery requests must name the adopted "
                                 "development candidate in a continuing receipt")
        if report["status"] != "requested" and not (
                report["status"] == "completed" and already_delivered
                and selection.get("comparison_key", comparison_key) == comparison_key):
            raise ArchiveFailure("invalid_local_delivery", "Only a sealed local delivery can record a new "
                                 "completion or blocker")
    evidence.validate_working_selection(report, objective_anchor=memory.get("objective_anchor"),
                                         require_eligibility=True)
    return None if already_delivered else report


class CampaignPolicy:
    """Decide from accepted history; applying returned updates belongs to callers."""

    def _work(self, memory: Mapping[str, Any], facts: Mapping[str, Any], evidence: CampaignEvidence) -> _Work:
        progress, health = facts["objective_progress"], facts["execution_health"]
        continuity, plan = facts["comparison_continuity"], facts["measurement_plan"]
        if health["needs_attention"]:
            if execution_review_due(health, memory["execution_review_checkpoint"], memory["failure_review_window"]):
                return _Work("repair", reason="execution_stagnation", reviews={"execution": {
                    key: health[key] for key in ("execution_attempts", "last_scored_candidate")}})
            return _Work("repair")
        if plan:
            if plan.get("rule_result", {}).get("state") == "unresolved":
                action = "Inspect the unresolved gate and record measure-stop with the concrete blocker."
            elif plan["complete"]:
                action = "Apply its frozen rule to the completed pairs and record the decision."
            else:
                action = "Complete its next unmatched run under the frozen protocol."
            return _Work("measure", f"Continue frozen measurement plan {plan['plan_id']}. {action}")
        delivery = pending_local_delivery(memory, progress, evidence)
        if delivery:
            return _Work("deliver", f"Complete the authorized local delivery of "
                         f"{json.dumps(delivery['candidate_id'], ensure_ascii=False)}. "
                         f"Accepted action: {json.dumps(delivery['detail'], ensure_ascii=False)}")
        selection_review = memory.get("selection_comparison")
        if pair := evidence.selection_comparison_pair(selection_review, progress):
            target, reference = (json.dumps(row["candidate_id"], ensure_ascii=False) for row in pair)
            return _Work("measure", f"Recover the primary comparison for {target} against {reference}. "
                         "Check the actual protocol before judging the proposed selection.",
                         "selection_comparison", {"selection_comparison": selection_review})
        if comparison_review_due(continuity, memory["comparison_review_window"]):
            return _Work("measure", (
                "Inspect the isolated contracts and remeasure a trusted reference and candidate under an existing "
                "legal common development contract; judge gains only after complete comparison identities match"),
                "comparison_isolation", {"comparison": {
                    "distinct_observations": continuity["distinct_observations"]}})
        conflict = facts["repeat_conflict"]
        if (conflict and conflict["signature"] not in facts["measurement_signatures"] and
                memory["repeat_review_checkpoints"].get(progress["comparison_key"]) != conflict["signature"]):
            return _Work("measure", (
                "Inspect the two implementations and the conflicting repeated result; predeclare a matched "
                "task-specific measurement protocol, then execute its next decision-changing observation"),
                "repeat_disagreement", {"repeat": {
                    "comparison_key": progress["comparison_key"], "signature": conflict["signature"]}})
        previous = memory["strategy_review_checkpoints"].get(progress["comparison_key"])
        research = current_research_state(memory, progress["comparison_key"])
        open_question = research and research["report"]["status"] == "open"
        if review_due(progress, previous, memory["stagnation_window"]):
            return _Work("rethink", (
                "Compare the historical raw-score best, the current working selection and recent implementations. "
                "Reassess the capability gap and compare a complete alternative with the strongest refinement. "
                "If a source could reverse the choice, name the bottleneck, the missing premise and the original "
                "evidence or alternate access path to inspect. Return the supported choice and its next action"),
                "objective_stagnation")
        registration = memory.get("proposal_registration")
        if registration:
            proposal = json.dumps(registration["proposal_id"], ensure_ascii=False)
            receipt = json.dumps(registration["receipt_path"], ensure_ascii=False)
            return _Work("register", f"Resolve registration of proposal {proposal} from the accepted receipt {receipt}. "
                         "Register it under the primary comparison if supported, or identify the specific gap.")
        if memory["next_mode"] == "rethink":
            return _Work("rethink", reason="research_review" if open_question else "strategy_review")
        proposal_id = memory.get("next_proposal_id")
        if evidence.pending_in_comparison(proposal_id, progress["comparison"]):
            return _Work("execute", (
                f"Execute selected primary proposal {json.dumps(proposal_id, ensure_ascii=False)}. "
                "Use candidate_archive.py trace --proposal-id to retrieve its declared change and comparison. "
                "Record a linked execution or stop the proposal with concrete evidence; do not substitute a memo, "
                "protocol conversion or delivery for this implementation."))
        if open_question or memory["next_mode"] in {"research", "execute", "register"}:
            return _Work("research", DISCOVER)
        # Repair and measurement are derived from current evidence, not durable
        # requests that survive after a failed invocation has resolved them.
        return _Work("work")

    def prepare(self, memory: Mapping[str, Any], evidence: CampaignEvidence) -> TurnPlan:
        """Stage a new turn; neither review nor exposure is acknowledged here."""
        facts = evidence.signals(memory["comparison_review_checkpoint"], objective_anchor=memory.get("objective_anchor"))
        resolved = resolved_proposal_updates(memory, evidence, facts["objective_progress"])
        memory = {**memory, **resolved} if resolved else memory
        facts["objective_progress"] = evidence.with_strategy_reference(
            facts["objective_progress"], memory.get("working_selection"))
        work = self._work(memory, facts, evidence)
        reason = work.reason
        if not reason:
            if (memory["session_id"] and memory["session_checkpoints"] and
                    memory["session_turns"] >= memory["session_checkpoints"]):
                reason = "scheduled_rotation"
            elif not memory["session_id"]:
                reason = "session_recovery" if memory["turn_number"] else "initial"
        updates = {**resolved, **{key: facts[key] for key in
                                ("objective_progress", "execution_health", "comparison_continuity")}}
        if (memory.get("selection_comparison")
                and not evidence.selection_comparison_pair(memory["selection_comparison"], facts["objective_progress"])):
            updates["selection_comparison"] = None
        if evidence.selection_excluded(memory.get("working_selection")):
            updates["working_selection"] = None
        delivery = memory.get("local_delivery")
        if delivery and delivery["status"] == "requested" and not pending_local_delivery(memory, facts["objective_progress"], evidence):
            updates["local_delivery"] = None
        updates["next_mode"] = work.mode
        if reason:
            updates.update(session_id=None, session_turns=0, context_refresh_reason=reason,
                           context_refreshes=memory["context_refreshes"] + bool(memory["turn_number"]))
        reviews = dict(work.reviews)
        progress = facts["objective_progress"]
        if work.mode == "rethink" and progress["best_candidate"]:
            reviews["strategy"] = {key: progress[key] for key in
                                   ("comparison_key", "best_candidate", "comparable_implementations")}
        return TurnPlan(updates, bool(reason), reason, reviews, work.driver_action)

    def accept(self, memory: Mapping[str, Any], turn: Mapping[str, Any],
               outcome: TurnOutcome) -> dict[str, Any]:
        """Account for accepted evidence separately from successful delivery.

        The driver classifies receipt success after validating the durable exit
        and archive. Failed invocations can contribute verified archive events,
        but cannot acknowledge any card or review from their sealed request.
        Time is supplied by the driver; this method performs no I/O.
        """
        facts = outcome.evidence.signals(memory["comparison_review_checkpoint"],
                                         objective_anchor=memory.get("objective_anchor"))
        updates = {key: facts[key] for key in
                   ("objective_progress", "execution_health", "comparison_continuity")}
        resolved = resolved_proposal_updates(memory, outcome.evidence, facts["objective_progress"])
        updates.update(resolved)
        if outcome.evidence.selection_excluded(memory.get("working_selection")):
            updates["working_selection"] = None
        idle = (0 if outcome.archive_delta["new_implementation_attempts"] > 0
                else memory["turns_without_implementation"] + 1)
        updates["turns_without_implementation"] = idle
        receipt = outcome.receipt
        if receipt is None:
            if outcome.unmatched_selection:
                request = {"candidate_id": outcome.unmatched_selection,
                           "comparison_key": facts["objective_progress"]["comparison_key"]}
                if outcome.evidence.selection_comparison_pair(request, facts["objective_progress"]):
                    updates["selection_comparison"] = request
            facts["objective_progress"] = updates["objective_progress"] = outcome.evidence.with_strategy_reference(
                facts["objective_progress"], memory.get("working_selection"))
            retry_memory = {**memory, **updates}
            if memory["failures"] + 1 >= 2:
                if not resolved.get("next_proposal_id"):
                    retry_memory["next_mode"] = "rethink"
                updates["session_id"] = None
            updates["next_mode"] = self._work(retry_memory, facts, outcome.evidence).mode
            return updates
        updates["session_turns"] = memory["session_turns"] + 1
        for sealed_key, memory_key, identifiers in (
                ("frontier_exposure", "frontier_exposures", "implementations"),
                ("pending_proposal_exposure", "pending_proposal_exposures", "proposals"),
                ("trial_exposure", "trial_exposures", "proposals"),
                ("learning_exposure", "learning_exposures", "candidates")):
            delivery = turn.get(sealed_key)
            if delivery and delivery[identifiers]:
                exposures = dict(memory[memory_key])
                seen = dict(exposures.get(delivery["comparison_key"], {}))
                seen.update({identity: turn["number"] for identity in delivery[identifiers]})
                exposures[delivery["comparison_key"]] = seen
                updates[memory_key] = exposures
        reviews = turn.get("review_checkpoints", {})
        reviewed_selection = bool(reviews.get("selection_comparison") and
                                  reviews["selection_comparison"] == memory.get("selection_comparison"))
        if reviewed_selection:
            updates["selection_comparison"] = None
        if "execution" in reviews:
            updates["execution_review_checkpoint"] = dict(reviews["execution"])
        if "strategy" in reviews:
            review = reviews["strategy"]
            updates["strategy_review_checkpoints"] = {
                **memory["strategy_review_checkpoints"], review["comparison_key"]: dict(review)}
        if "comparison" in reviews:
            updates["comparison_review_checkpoint"] = dict(reviews["comparison"])
            # Acknowledging the review changes the signal used by the preview.
            facts = outcome.evidence.signals(reviews["comparison"], objective_anchor=memory.get("objective_anchor"))
            updates["comparison_continuity"] = facts["comparison_continuity"]
        if "repeat" in reviews:
            review = reviews["repeat"]
            if review["signature"] in facts["measurement_signatures"]:
                updates["repeat_review_checkpoints"] = {
                    **memory["repeat_review_checkpoints"], review["comparison_key"]: review["signature"]}
        delivering = turn["mode"] == "deliver"
        updates.update(failures=0, retry_at=None, last_error="", recovery_needed=False,
                       last_summary=receipt["summary"], next_action=(memory["next_action"] if delivering
                                                                     else receipt["next_action"]),
                       last_agent_status=receipt["status"], next_mode="work", next_proposal_id=None)
        origin = {"turn": turn["number"], "receipt_path": outcome.receipt_path,
                  "comparison_key": ((turn.get("context", {}).get("objective_progress") or {}).get("comparison_key")
                                     or facts["objective_progress"]["comparison_key"]),
                  "assessment_kind": "agent_report"}
        requested = receipt.get("next_proposal_id")
        progress = facts["objective_progress"]
        primary_comparison = progress["comparison"]
        ready = outcome.evidence.pending_in_comparison(requested, primary_comparison)
        closed = outcome.evidence.proposal_closed(requested)
        foreign = bool(requested and not ready and outcome.evidence.proposal_pending(requested))
        registration = None
        if (requested and not (ready or closed or foreign) and outcome.receipt_path
                and progress["comparison_key"] and origin["comparison_key"] == progress["comparison_key"]
                and receipt["status"] == "continue" and turn["mode"] != "register"):
            registration = {"proposal_id": requested, "comparison_key": progress["comparison_key"],
                            "receipt_path": outcome.receipt_path}
        if requested or turn["mode"] == "register":
            updates["proposal_registration"] = registration
            prior = memory.get("proposal_registration")
            prior_research = memory.get("research_state") or {}
            if (prior and prior_research.get("proposal_id") == prior["proposal_id"]
                    and not outcome.evidence.pending_in_comparison(prior["proposal_id"], primary_comparison)
                    and (registration or {}).get("proposal_id") != prior["proposal_id"]):
                updates["research_state"] = None
        if closed:
            updates["next_action"] = archived_proposal_action(requested)
        elif foreign:
            updates["next_action"] = (
                f"Proposal {json.dumps(requested, ensure_ascii=False)} is pending under a different comparison. "
                "Select or register a proposal under the primary comparison.")
        elif requested and not (ready or registration) and turn["mode"] != "register":
            updates["next_action"] = missing_proposal_action(requested, outcome.receipt_path)
        if "research_state" in receipt:
            report = receipt["research_state"]
            updates["research_state"] = {**origin, "report": copy.deepcopy(report)} if report is not None else None
            if report and report["status"] == "open" and report["route"] == "implement":
                if closed:
                    updates["research_state"] = None
                elif ready or registration:
                    updates["research_state"]["proposal_id"] = requested
        if receipt.get("corrections"):
            updates["research_corrections"] = update_research_corrections(memory, origin, receipt["corrections"])
        continued = False
        research = updates.get("research_state")
        open_finding = (bool(outcome.finding_sha256) and turn["mode"] in {"rethink", "research", "register"}
                        and bool(receipt["next_action"].strip()) and research is not None
                        and research["report"]["status"] == "open"
                        and origin["comparison_key"] == facts["objective_progress"]["comparison_key"])
        # A research agent can report the checkpoint as complete while explicitly
        # leaving a cited finding and an open successor, or registering the requested proposal.
        continuing = receipt["status"] == "continue" or (
            receipt["status"] == "complete" and not memory.get("completion_check")
            and (open_finding or resolved.get("next_proposal_id")))
        if continuing and open_finding:
            key = origin["comparison_key"] or "null"
            history = memory.get("research_findings", {})
            seen = history.get(key, {})
            finding = receipt["research_finding"]
            premise = " ".join(finding["premise_id"].split()).casefold()
            corrected_here = any(row["key"] == finding["premise_id"] for row in receipt.get("corrections", []))
            if not corrected_here and premise not in seen and outcome.finding_sha256 not in seen.values():
                updates["research_findings"] = {**history, key: {**seen, premise: outcome.finding_sha256}}
                research["finding"] = {**finding, "evidence_sha256": outcome.finding_sha256}
                continued = True
        if "working_selection" in receipt:
            selection = receipt["working_selection"]
            if selection is not None:
                outcome.evidence.validate_working_selection(selection, objective_anchor=memory.get("objective_anchor"))
            updates["working_selection"] = ({**origin, **copy.deepcopy(selection),
                                              "comparison_key": facts["objective_progress"]["comparison_key"],
                                              "assessment_kind": "agent_selection_report"}
                                             if selection is not None else None)
        delivery = receipt.get("local_delivery")
        comparison_key = facts["objective_progress"]["comparison_key"]
        if delivery and not has_completed_local_delivery(memory, delivery["candidate_id"], comparison_key):
            updates["local_delivery"] = {
                **origin, **copy.deepcopy(delivery), "comparison_key": comparison_key,
                "assessment_kind": "agent_delivery_report",
                "evidence_sha256": dict(outcome.local_delivery_hashes or {}),
            }
        resolutions = [entry for entry in outcome.appended_events
                       if entry["event"] in {"measurement_decision", "measurement_stop"}]
        if resolutions:
            plans = facts["measurement_comparisons"]
            matched = [entry for entry in resolutions
                       if plans[entry["plan_id"]] == facts["objective_progress"]["comparison"]]
            if matched:
                updates["next_action"] = matched[-1]["next_action"]
        if delivering:
            chosen = resolved.get("next_proposal_id", memory.get("next_proposal_id"))
            if outcome.evidence.pending_in_comparison(chosen, primary_comparison):
                updates["next_proposal_id"] = chosen
            updates["next_mode"] = "research"
        elif not continuing or (not updates["next_action"].strip() and not resolved.get("next_proposal_id")):
            updates["next_mode"] = "rethink"
        else:
            chosen = requested
            if chosen is None and resolved.get("next_proposal_id"):
                chosen = resolved["next_proposal_id"]
            elif chosen is None and turn["mode"] in {"repair", "measure"}:
                chosen = memory.get("next_proposal_id")
            if (outcome.evidence.pending_in_comparison(chosen, primary_comparison)
                    and not (turn["mode"] == "execute" and chosen == memory.get("next_proposal_id"))):
                updates["next_proposal_id"] = chosen
            elif chosen or turn["mode"] in {"rethink", "research", "execute", "register"}:
                updates["next_mode"] = "research"
        measurement_progress = reviewed_selection or (
            turn["mode"] == "measure" and facts["comparison_continuity"]["distinct_observations"] >
            (turn.get("context", {}).get("comparison_continuity") or {}).get("distinct_observations", 0))
        measurement_progress |= any(entry["event"] == "measurement_stop" for entry in outcome.appended_events)
        if turn["mode"] == "measure":
            measurement_progress |= any(entry["event"] in {"measurement_plan", "measurement_decision"} or
                                        entry["event"] == "candidate" and
                                        entry["result"].get("measurement_plan_id") and observed_implementation(entry)
                                        for entry in outcome.appended_events)
        delivery_progress = "local_delivery" in updates
        pending_registration = updates.get("proposal_registration", memory.get("proposal_registration"))
        if idle >= 2 and not (measurement_progress or continued or delivery_progress
                              or updates["next_proposal_id"] or pending_registration):
            reviewed = turn["mode"] in {"rethink", "register"} or (
                turn["mode"] == "repair" and turn.get("fresh_context"))
            if updates["next_mode"] != "rethink":
                updates["next_mode"] = "research" if reviewed else "rethink"
            updates["retry_at"] = outcome.now + min(
                memory["retry_max_seconds"], memory["retry_base_seconds"] * max(1, idle - 1))
        refresh_requested = updates["next_mode"] == "rethink"
        facts["objective_progress"] = updates["objective_progress"] = outcome.evidence.with_strategy_reference(
            facts["objective_progress"], updates.get("working_selection", memory.get("working_selection")))
        preview = self._work({**memory, **updates}, facts, outcome.evidence)
        updates["next_mode"] = preview.mode
        if refresh_requested or preview.mode == "rethink":
            updates["session_id"] = None
        return updates
