"""Own the ordering of sealed turn creation and accepted-outcome persistence.

The driver supplies process waiting and its completion verifier callback. Policy
and archive modules retain their facts; no second state or event store is added.
"""
from __future__ import annotations

import os
import pathlib
import time
import uuid
from dataclasses import replace
from typing import Any, Callable

from candidate_evidence import ArchiveFailure, canonical, sha256
from campaign_archive import CampaignArchive
from campaign_policy import CampaignPolicy, TurnOutcome, validate_local_delivery
from campaign_prompt import prompt_for_turn, prompt_for_receipt
from campaign_search import prepare_handoff
from campaign_state import append_event, check_control_files, save_state
from campaign_runtime import CampaignError, atomic_bytes, atomic_json, file_hash, job_directory, output_hashes, read_json
from codex_invocation import CodexInvocation
from campaign_workflow import freeze_workflow


def receipt_job(campaign: pathlib.Path, turn: dict[str, Any],
                invocation=None, snapshot=None) -> dict[str, Any]:
    """Seal one formatting-only fork; recovery reuses its exact launch intent."""
    source = job_directory(campaign, turn["number"])
    original = read_json(source / "exit.json")
    if original.get("token") != turn["token"] or original.get("outputs") != output_hashes(source):
        raise CampaignError("Original agent outcome identity changed before receipt delivery")
    if invocation is None:
        invocation = CodexInvocation.observe(source, original, quarantined=False)
    if not invocation.needs_receipt:
        raise CampaignError("Receipt delivery requires a successful invocation with a missing/invalid receipt")
    expected = {"number": turn["number"], "kind": "receipt", "workspace": turn["workspace"],
                "source_token": turn["token"], "source_outputs": original["outputs"],
                "started_unix": turn["started_unix"], "timeout_seconds": turn["timeout_seconds"],
                "command": CodexInvocation.receipt_command(turn, campaign, invocation.events["session_id"])}
    path = job_directory(campaign, turn["number"], "receipt") / "request.json"
    if path.exists():
        job = read_json(path)
        if any(job.get(key) != value for key, value in expected.items()):
            raise CampaignError("Durable receipt delivery request was modified")
    else:
        if snapshot is None:
            raise CampaignError("Receipt delivery archive identity is missing")
        job = {**expected, "token": uuid.uuid4().hex, "archive_snapshot": snapshot}
    return {**job, "prompt": prompt_for_receipt(turn, invocation.error)}


def materialize_request(campaign: pathlib.Path, turn: dict[str, Any]) -> pathlib.Path:
    directory = job_directory(campaign, turn["number"], turn.get("kind", "agent"))
    directory.mkdir(parents=True, exist_ok=True)
    if "context" in turn:
        raw = canonical(turn["context"]) + b"\n"
        if sha256(raw) != turn["context_sha256"]:
            raise CampaignError("Durable turn context identity changed")
        context = directory / "context.json"
        if context.exists() and context.read_bytes() != raw:
            raise CampaignError("Durable turn context was modified")
        if not context.exists():
            atomic_bytes(context, raw)
    request = {key: value for key, value in turn.items() if key != "prompt"}
    path = directory / "request.json"
    if path.exists():
        if read_json(path) != request:
            raise CampaignError("Durable turn request was modified")
    else:
        atomic_json(path, request)
    prompt = directory / "prompt.txt"
    if prompt.exists() and prompt.read_text() != turn["prompt"]:
        raise CampaignError("Durable turn prompt was modified")
    if not prompt.exists():
        temporary = directory / ("prompt." + uuid.uuid4().hex + ".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(turn["prompt"])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, prompt)
    return directory


def retry_later(state: dict[str, Any], error: str) -> None:
    state["failures"] += 1
    delay = min(state["retry_max_seconds"],
                state["retry_base_seconds"] * 2 ** min(state["failures"] - 1, 16))
    state["retry_at"] = time.time() + delay
    state["last_error"] = error
    state["recovery_needed"] = True
    # Recovery has its own instructions in the next prompt. Keep the previous
    # continuation suggestion separate from the recovery obligation.


def local_evidence_hash(campaign: pathlib.Path, state: dict[str, Any], reference: str) -> str | None:
    workspace = pathlib.Path(state["workspace"]).resolve()
    archive = pathlib.Path(state["archive"]).resolve()
    try:
        path = (workspace / reference).resolve(strict=True)
        if (path != archive and not path.is_relative_to(campaign)
                and (path.is_relative_to(workspace) or path.is_relative_to(archive.parent))
                and path.is_file() and path.stat().st_size):
            return file_hash(path)
    except (OSError, RuntimeError, ValueError):
        return None
    return None


class TurnLifecycle:
    """One persistence authority for a prepared turn and its accepted outcome."""

    @staticmethod
    def prepare(campaign: pathlib.Path, state: dict[str, Any]) -> None:
        accepted_state = state
        state = dict(state)
        number = state["turn_number"] + 1
        snapshot, protected, provenance = freeze_workflow(campaign, pathlib.Path(__file__).resolve().parent.parent, state)
        state.update(instruction_snapshot=snapshot, workflow_provenance=provenance,
                     protected_files={**state["protected_files"], **protected})
        archive = CampaignArchive(pathlib.Path(state["archive"]))
        with archive.confirmed(state["archive_snapshot"]) as evidence:
            prepared = CampaignPolicy().prepare(state, evidence)
            state.update(prepared.updates)
            fresh, reason = prepared.fresh_context, prepared.context_refresh_reason
            handoff = prepare_handoff(state, prepared, evidence, state["protected_files"][str(campaign / "task.md")])
            context = handoff.packet
        timeout = state["turn_timeout_seconds"]
        if state["max_wall_seconds"] is not None:
            left = max(0.1, state["created_unix"] + state["max_wall_seconds"] - time.time())
            timeout = left if timeout is None else min(timeout, left)
        turn = {"number": number, "token": uuid.uuid4().hex, "started_unix": time.time(),
                "archive_before": state["archive_snapshot"], "mode": state["next_mode"],
                "workspace": state["workspace"], "command": CodexInvocation.command(state, campaign, number),
                "timeout_seconds": timeout, "context": context,
                "context_sha256": sha256(canonical(context) + b"\n"),
                "fresh_context": fresh, "context_refresh_reason": reason,
                "driver_action": prepared.driver_action,
                "instruction_snapshot": snapshot, "workflow_provenance": provenance,
                **handoff.delivery,
                "prompt": prompt_for_turn(state, campaign, number, context,
                                          driver_action=prepared.driver_action, timeout_seconds=timeout)}
        if turn["mode"] == "deliver":
            turn["local_delivery_candidate_id"] = state["local_delivery"]["candidate_id"]
        state["turn_number"] = number
        state["inflight"] = turn
        # Persist intent before creating files or processes. Resume can materialize missing files.
        accepted_state.update(state)
        save_state(campaign, state)
        append_event(campaign, {"event": "turn_prepared", "turn": number, "token": turn["token"],
                                "mode": turn["mode"], "session_id": state["session_id"],
                                "fresh_context": fresh, "context_refresh_reason": reason,
                "instruction_snapshot": snapshot, "workflow_provenance": provenance,
                                **{key: state[key] for key in ("objective_progress", "execution_health", "comparison_continuity")},
                                "frontier_exposure": turn["frontier_exposure"],
                                "pending_proposal_exposure": turn["pending_proposal_exposure"],
                                "trial_exposure": turn["trial_exposure"],
                                "learning_exposure": turn["learning_exposure"],
                                "review_checkpoints": turn["review_checkpoints"],
                                "context_sha256": turn["context_sha256"]})

    @staticmethod
    def accept(campaign: pathlib.Path, state: dict[str, Any],
               verify_completion: Callable[[dict[str, Any]], None]) -> None:
        turn = state["inflight"]
        directory = materialize_request(campaign, turn)
        result = read_json(directory / "exit.json")
        if result.get("token") != turn["token"]:
            raise CampaignError("Exit record does not belong to the in-flight turn")
        if result.get("outputs") != output_hashes(directory):
            raise CampaignError("Agent output changed after its durable exit record")
        check_control_files(state)
        received = CampaignArchive(pathlib.Path(state["archive"])).receive(
            turn["archive_before"], token=turn["token"], directory=directory)
        if received.quarantine_event is not None:
            append_event(campaign, {**received.quarantine_event, "turn": turn["number"], "token": turn["token"]})
        delta, quarantined, evidence = received.delta, received.quarantined, received.evidence
        state.update(archive_snapshot=received.snapshot, progress=evidence.counts)
        invocation = CodexInvocation.observe(directory, result, quarantined=quarantined)
        original_invocation = invocation
        delivery = job_directory(campaign, turn["number"], "receipt")
        # Do not give a formatting repair a new resource allowance. Its worker
        # also retains the original turn deadline and immediate-stop handling.
        observed_tokens = sum(invocation.events["usage"].get(key, 0) + state["usage"].get(key, 0)
                              for key in ("input_tokens", "output_tokens"))
        limited = (state["max_tokens"] is not None and observed_tokens >= state["max_tokens"] or
                   state["max_wall_seconds"] is not None and
                   time.time() >= state["created_unix"] + state["max_wall_seconds"] or
                   turn["timeout_seconds"] is not None and
                   time.time() >= turn["started_unix"] + turn["timeout_seconds"])
        if invocation.needs_receipt and not (delivery / "request.json").exists() and not limited:
            job = receipt_job(campaign, turn, invocation, received.snapshot)
            materialize_request(campaign, job)
            append_event(campaign, {"event": "receipt_delivery_prepared", "turn": turn["number"],
                                    "token": job["token"], "source_token": turn["token"],
                                    "error": invocation.error})
            save_state(campaign, state)
            return
        invocations = [(invocation, result)]
        receipt_path = directory / "message.json"
        if (delivery / "request.json").exists():
            job = receipt_job(campaign, turn, original_invocation)
            materialize_request(campaign, job)
            delivered = read_json(delivery / "exit.json")
            if delivered.get("token") != job["token"] or delivered.get("outputs") != output_hashes(delivery):
                raise CampaignError("Receipt delivery outcome identity changed")
            invocation = CodexInvocation.observe(delivery, delivered, quarantined=quarantined)
            if received.snapshot != job["archive_snapshot"]:
                error = "Archive changed during receipt delivery; reconcile its artifacts"
                invocation = replace(invocation, receipt=None, needs_receipt=False,
                                     error=f"{invocation.error}; {error}" if invocation.error else error)
            invocations.append((invocation, delivered))
            receipt_path = delivery / "message.json"
        events = original_invocation.events
        usage: dict[str, int] = {}
        for observed, finished in invocations:
            for key, value in observed.events["usage"].items():
                usage[key] = usage.get(key, 0) + value
                state["usage"][key] = state["usage"].get(key, 0) + value
            if observed.events["terminal"] != "turn.completed":
                state["unreported_usage_turns"] += 1
            state["agent_seconds"] += finished["elapsed_seconds"]
        # The delivery fork is disposable. Resume tool work from the original
        # session, keeping its provider settings and research context intact.
        if events["session_id"]:
            state["session_id"] = events["session_id"]
        state["inflight"] = None
        error, receipt = invocation.error, invocation.receipt
        delivery_hashes = {}
        if receipt:
            try:
                if receipt.get("working_selection") is not None:
                    evidence.validate_working_selection(receipt["working_selection"],
                                                         objective_anchor=state.get("objective_anchor"),
                                                         require_eligibility=True)
                validate_local_delivery(state, turn, receipt, evidence)
                if turn["mode"] == "deliver" and received.appended_events:
                    raise ArchiveFailure("invalid_local_delivery", "Local delivery cannot append development events")
                delivery = receipt.get("local_delivery")
                if delivery and delivery["status"] == "completed":
                    for path in delivery["evidence"]:
                        digest = local_evidence_hash(campaign, state, path)
                        if digest is None:
                            raise ArchiveFailure("invalid_local_delivery", "Delivery evidence must be a nonempty local artifact")
                        delivery_hashes[path] = digest
            except ArchiveFailure as exc:
                error, receipt, delivery_hashes = str(exc), None, {}
        # New archive evidence is accepted even if invocation delivery failed.
        finding = receipt.get("research_finding") if receipt and turn["mode"] in {"research", "rethink"} else None
        finding_hash = local_evidence_hash(campaign, state, finding["evidence_path"]) if finding else None
        outcome = TurnOutcome(evidence, received.appended_events, delta, receipt, time.time(),
                              receipt_path=str(receipt_path), finding_sha256=finding_hash,
                              local_delivery_hashes=delivery_hashes)
        updates = CampaignPolicy().accept(state, turn, outcome)
        state.update(updates)
        if receipt is None:
            retry_later(state, error)
            state["last_summary"] = f"Turn {turn['number']} interrupted: {error}"
            if invocation.reset_session:
                state["session_id"] = None
            if invocation.blocked:
                state["status"] = "blocked"
                state["stop_reason"] = (
                    "Observed CLI authentication/configuration or host dependency failure; inspect this turn's logs")
            event = {"event": "turn_interrupted", "error": error}
        else:
            event = {"event": "turn_completed", "receipt": receipt}
            if "research_findings" in updates:
                event["research_finding_sha256"] = finding_hash
            state["last_receipt_path"] = str(receipt_path)
            if (delta["evaluated_candidates"] > delta["diagnostic_evaluations"]
                    or receipt["status"] == "complete"):
                verify_completion(turn)
        append_event(campaign, {**event, "turn": turn["number"], "token": turn["token"],
                                "event_id": turn["token"] + ":outcome", "archive_delta": delta,
                                "usage": usage, "next_mode": state["next_mode"],
                                "receipt_path": str(receipt_path),
                                "objective_progress": state["objective_progress"],
                                "execution_health": state["execution_health"],
                                "comparison_continuity": state["comparison_continuity"]})
        save_state(campaign, state)
