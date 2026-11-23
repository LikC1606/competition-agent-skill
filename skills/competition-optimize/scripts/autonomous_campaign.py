#!/usr/bin/env python3
"""Run an open-ended, resumable competition optimization campaign with Codex CLI.

Strategy belongs to the agent; scoring belongs to the task adapter. This driver
owns continuation, verified evidence, process recovery, and explicit stop rules.
Linux and Python 3.10+ are required. No third-party Python packages are needed.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, BinaryIO, Iterator

import candidate_archive as archive_tools
from campaign_archive import CampaignArchive
from campaign_policy import update_research_corrections
from campaign_prompt import prompt_for_turn
from codex_invocation import FINAL_SCHEMA, correction_reports_valid, research_state_valid
from campaign_state import (SCHEMA_VERSION, append_event, check_control_files, complete_state, read_state, save_state)
from turn_lifecycle import TurnLifecycle, materialize_request, receipt_job

# Compatibility entrypoint; turn creation is owned by the lifecycle module.
prepare_turn = TurnLifecycle.prepare
from campaign_search import (
    DEFAULT_COMPARISON_REVIEW_WINDOW, DEFAULT_FAILURE_REVIEW_WINDOW, DEFAULT_SESSION_CHECKPOINTS,
    DEFAULT_STAGNATION_WINDOW, current_research_state,
)
from campaign_runtime import (
    CampaignError, HEARTBEAT_SECONDS, POLL_SECONDS, WORKER_TOKEN, acquire_resources,
    atomic_bytes, atomic_json, exclusive_lock, file_hash, job_directory, lock_busy, output_hashes, owned_processes,
    process_alive, process_info, read_json, recorded_group, run_worker, terminate_owned,
    turn_directory, utc_now,
)


TERMINAL = {"complete", "blocked", "stopped_by_user", "limit_reached"}
LIMITS = ("max_turns", "max_tokens", "max_wall_seconds")
BACKGROUND_STARTUP_SECONDS = 5.0


def evidence_exists(evidence: list[str], state: dict[str, Any], campaign: pathlib.Path) -> bool:
    return bool(evidence) and all(
        pathlib.Path(name).exists() if pathlib.Path(name).is_absolute() else
        (pathlib.Path(state["workspace"]) / name).exists() or (campaign / name).exists()
        for name in evidence)


def completion_job(campaign: pathlib.Path, state: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    directory = job_directory(campaign, turn["number"], "completion")
    command = [sys.executable, state["completion_check"], "--workspace", state["workspace"],
               "--archive", state["archive"]]
    request = directory / "request.json"
    if request.exists():
        job = {**read_json(request), "prompt": ""}
        if (job.get("kind") != "completion" or job.get("number") != turn["number"] or
                job.get("command") != command or job.get("workspace") != state["workspace"]):
            raise CampaignError("Durable completion verifier request was modified")
    else:
        timeout = state["completion_timeout_seconds"]
        if state["max_wall_seconds"] is not None:
            timeout = min(timeout, max(0.1, state["created_unix"] +
                                      state["max_wall_seconds"] - time.time()))
        job = {"number": turn["number"], "kind": "completion", "token": uuid.uuid4().hex,
               "started_unix": time.time(), "workspace": state["workspace"], "command": command,
               "timeout_seconds": timeout, "prompt": ""}
    return job


def completion_check(campaign: pathlib.Path, state: dict[str, Any], turn: dict[str, Any],
                     resources: list[BinaryIO]) -> None:
    if not state["completion_check"]:
        return
    check_control_files(state)
    job = completion_job(campaign, state, turn)
    directory = job_directory(campaign, turn["number"], "completion")
    # The same durable worker/exec shim owns both kinds of job. A manager crash
    # adopts the verifier instead of launching a second one or leaving an orphan.
    await_job(campaign, state, job, resources)
    outcome = read_json(directory / "exit.json")
    if outcome.get("token") != job["token"] or outcome.get("outputs") != output_hashes(directory):
        raise CampaignError("Completion verifier outcome identity changed")
    stop = stop_request(campaign)
    if (stop and stop.get("immediate") or state["max_wall_seconds"] is not None and
            time.time() - state["created_unix"] >= state["max_wall_seconds"]):
        return  # Let the normal campaign stop/limit path retain the accepted candidate.
    if outcome["returncode"] != 0 or outcome.get("error") or outcome.get("survivors"):
        raise CampaignError(f"Configured completion verifier failed: {outcome.get('error') or outcome['returncode']}")
    check_control_files(state)
    try:
        result = read_json(directory / "events.jsonl")
        if (not isinstance(result, dict) or set(result) != {"complete", "reason", "evidence"} or
                type(result["complete"]) is not bool or not isinstance(result["reason"], str) or
                not isinstance(result["evidence"], list) or
                any(not isinstance(item, str) for item in result["evidence"])):
            raise ValueError("expected complete:boolean, reason:string, evidence:string[]")
    except (OSError, ValueError) as exc:
        raise CampaignError(f"Invalid completion verifier output: {exc}") from exc
    append_event(campaign, {"event": "completion_checked", "turn": turn["number"], "result": result,
                            "event_id": job["token"] + ":completion"})
    if result["complete"]:
        if (not result["reason"].strip() or not evidence_exists(result["evidence"], state, campaign) or
                not state["progress"]["executed_implementations"]):
            raise CampaignError("Completion verifier claimed success without executed implementation/evidence")
        CampaignArchive(pathlib.Path(state["archive"])).verified()
        state["status"] = "complete"
        state["stop_reason"] = result["reason"]


def heartbeat(campaign: pathlib.Path, state: dict[str, Any]) -> None:
    atomic_json(campaign / "manager.json", {**process_info(os.getpid()), "at": utc_now(),
                "turn": state["turn_number"], "status": state["status"], "retry_at": state["retry_at"],
                "generation": state["manager_generation"]})


def stop_request(campaign: pathlib.Path) -> dict[str, Any] | None:
    path = campaign / "stop.request.json"
    return read_json(path) if path.exists() else None


def request_stop(campaign: pathlib.Path, reason: str, immediate: bool) -> None:
    with (campaign / "stop-control.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        atomic_json(campaign / "stop.request.json", {"reason": reason, "immediate": immediate,
                    "at": utc_now(), "request_id": uuid.uuid4().hex})


def consume_resumed_stop(campaign: pathlib.Path, expected: str) -> None:
    # Share a short critical section with stop writers so a new stop cannot be
    # replaced between comparing the old request and removing it.
    with (campaign / "stop-control.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = campaign / "stop.request.json"
        if path.exists() and file_hash(path) == expected:
            path.unlink()


def await_turn(campaign: pathlib.Path, state: dict[str, Any],
               resources: list[BinaryIO] | None) -> list[BinaryIO]:
    turn = state["inflight"]
    if (job_directory(campaign, turn["number"], "completion") / "request.json").exists():
        # A verifier may own the inherited resource FDs after BOTH its worker and
        # manager died. Recover that job first: waiting for the original agent's
        # lock cannot enforce the verifier's deadline or cancel its process tree.
        resources = await_job(campaign, state, completion_job(campaign, state, turn), resources)
    if (job_directory(campaign, turn["number"], "receipt") / "request.json").exists():
        resources = await_job(campaign, state, receipt_job(campaign, turn), resources)
    return await_job(campaign, state, turn, resources)


def await_job(campaign: pathlib.Path, state: dict[str, Any], turn: dict[str, Any],
              resources: list[BinaryIO] | None) -> list[BinaryIO]:
    directory = materialize_request(campaign, turn)
    worker = None
    heartbeat_at = 0.0
    cleanup_at = 0.0
    while True:
        now = time.monotonic()
        if worker is not None:
            code = worker.poll()
            if code is not None and code > 0 and code != 75 and not (directory / "exit.json").exists():
                raise CampaignError(f"Turn worker could not persist an outcome (exit {code}); inspect worker.log")
        if now >= heartbeat_at:
            heartbeat(campaign, state)
            heartbeat_at = now + HEARTBEAT_SECONDS
        if resources is None:
            resources = acquire_resources(campaign, state)
        request = stop_request(campaign)
        timeout = turn["timeout_seconds"]
        expired = timeout is not None and time.time() - turn["started_unix"] >= timeout
        group = recorded_group(directory, turn["token"])
        if (request and request.get("immediate") or expired) and now >= cleanup_at:
            # This also works after a worker crash, when no one is polling the original CLI.
            atomic_json(directory / "cancel.request.json", {"token": turn["token"], "at": utc_now(),
                        "reason": "User requested immediate stop" if request and request.get("immediate")
                        else "Per-turn watchdog expired"})
            terminate_owned(turn["token"], group)
            cleanup_at = now + HEARTBEAT_SECONDS
        busy = lock_busy(directory / "execution.lock")
        if not busy:
            agents = owned_processes(turn["token"], group)
            if agents:
                # Orphan tool children might have closed the inherited lock descriptors.
                terminate_owned(turn["token"], group)
                time.sleep(POLL_SECONDS)
                continue
            if (directory / "exit.json").exists() and resources is not None:
                return resources
            workers = owned_processes(turn["token"], worker=True)
            if not workers and resources is not None:
                environment = {**os.environ, WORKER_TOKEN: turn["token"]}
                command = [sys.executable, str(pathlib.Path(__file__).resolve()), "_worker",
                           "--campaign", str(campaign), "--number", str(turn["number"]),
                           "--kind", turn.get("kind", "agent")]
                for stream in resources:
                    command += ["--resource-fd", str(stream.fileno())]
                with (directory / "worker.log").open("ab") as log:
                    worker = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                              stdout=log, stderr=log, env=environment,
                                              start_new_session=True,
                                              pass_fds=tuple(stream.fileno() for stream in resources))
        time.sleep(POLL_SECONDS)


def limit_reason(state: dict[str, Any]) -> str:
    if state["max_turns"] is not None and state["turn_number"] >= state["max_turns"]:
        return "Explicit max-turns limit reached"
    tokens = state["usage"].get("input_tokens", 0) + state["usage"].get("output_tokens", 0)
    if state["max_tokens"] is not None and tokens >= state["max_tokens"]:
        return "Explicit max-tokens limit reached (checked between invocations)"
    if (state["max_wall_seconds"] is not None and
            time.time() - state["created_unix"] >= state["max_wall_seconds"]):
        return "Explicit max-wall-seconds limit reached"
    return ""


def run_campaign(campaign: pathlib.Path, overrides: dict[str, Any] | None = None,
                 managed: bool = False, generation: str | None = None,
                 resume_stop_hash: str | None = None) -> dict[str, Any]:
    if not managed and lock_busy(campaign / "supervisor.lock"):
        raise CampaignError("Background supervisor is already running; use status or stop")
    try:
        leader = exclusive_lock(campaign / "runner.lock")
    except BlockingIOError as exc:
        raise CampaignError("Another campaign manager is already running") from exc
    resources = None
    state = read_state(campaign)
    try:
        state["manager_generation"] = generation or uuid.uuid4().hex
        check_control_files(state)
        verified = None
        if not state["inflight"]:
            verified = CampaignArchive(pathlib.Path(state["archive"])).verified(state["archive_snapshot"])
        elif overrides and "objective_anchor" in overrides:
            verified = CampaignArchive(pathlib.Path(state["archive"])).verified_prefix(state["archive_snapshot"])
        if overrides:
            if "objective_anchor" in overrides:
                state["objective_progress"] = verified.evidence.signals(
                    objective_anchor=overrides["objective_anchor"])["objective_progress"]
            state.update(overrides)
        if resume_stop_hash:
            # Only an explicit resume consumes the request observed at its entry.
            # A later stop, or a supervisor's crash recovery, retains its intent.
            consume_resumed_stop(campaign, resume_stop_hash)
        if state["status"] in TERMINAL:
            state["status"] = "running"
            state["stop_reason"] = ""
            state["retry_at"] = None
            # Preserve in-flight intent and recovery context across an explicit resume.
        save_state(campaign, state)
        resources = acquire_resources(campaign, state)
        heartbeat_at = 0.0
        while state["status"] == "running":
            try:
                if state["inflight"]:
                    resources = await_turn(campaign, state, resources)
                    TurnLifecycle.accept(campaign, state,
                                         lambda turn: completion_check(campaign, state, turn, resources))
                    continue
                request = stop_request(campaign)
                reason = limit_reason(state)
                if request or reason:
                    state["status"] = "stopped_by_user" if request else "limit_reached"
                    state["stop_reason"] = request["reason"] if request else reason
                    save_state(campaign, state)
                    append_event(campaign, {"event": state["status"], "reason": state["stop_reason"]})
                    break
                now = time.monotonic()
                if now >= heartbeat_at:
                    heartbeat(campaign, state)
                    heartbeat_at = now + HEARTBEAT_SECONDS
                if state["retry_at"] and time.time() < state["retry_at"]:
                    time.sleep(POLL_SECONDS)
                    continue
                check_control_files(state)
                prepare_turn(campaign, state)
            except KeyboardInterrupt:
                request_stop(campaign, "User interrupted foreground runner", True)
        heartbeat(campaign, state)
        return state
    except (CampaignError, archive_tools.ArchiveFailure, OSError, ValueError, KeyError) as exc:
        # Actual host/evidence failures are distinct from an agent saying it has no ideas.
        state["status"] = "blocked"
        state["stop_reason"] = str(exc)
        save_state(campaign, state)
        append_event(campaign, {"event": "driver_blocked", "error": str(exc)})
        heartbeat(campaign, state)
        return state
    finally:
        if resources:
            for stream in resources:
                stream.close()
        leader.close()


def new_campaign(args: argparse.Namespace) -> pathlib.Path:
    workspace = args.workspace.expanduser().resolve(strict=True)
    task = args.task_file.expanduser().resolve(strict=True)
    if not workspace.is_dir() or not task.is_file():
        raise CampaignError("Workspace must be a directory and task must be a file")
    if args.allow_network and args.sandbox != "workspace-write":
        raise CampaignError("--allow-network requires the workspace-write sandbox")
    binary = shutil.which(args.agent_bin)
    if binary is None:
        raise CampaignError(f"Agent executable not found: {args.agent_bin}")
    campaign = args.campaign.expanduser().resolve()
    if campaign.exists():
        raise CampaignError("Campaign directory already exists; use resume")
    archive = args.archive.expanduser().resolve()
    head = CampaignArchive(archive).verified()
    evidence, snapshot = head.evidence, head.snapshot
    signals = evidence.signals(objective_anchor=args.objective_anchor)
    protected = {}
    checker = None
    if args.completion_check:
        checker = str(args.completion_check.expanduser().resolve(strict=True))
        for path in [pathlib.Path(checker), *args.check_dependency]:
            path = path.expanduser().resolve(strict=True)
            protected[str(path)] = archive_tools.hash_path(path)
    elif args.check_dependency:
        raise CampaignError("check-dependency requires completion-check")
    campaign.mkdir(parents=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(task, campaign / "task.md")
    atomic_json(campaign / "receipt.schema.json", FINAL_SCHEMA)
    for path in (campaign / "task.md", campaign / "receipt.schema.json"):
        protected[str(path)] = file_hash(path)
    state: dict[str, Any] = complete_state({
        "schema_version": SCHEMA_VERSION, "campaign_id": uuid.uuid4().hex, "status": "running",
        "workspace": str(workspace), "archive": str(archive), "archive_snapshot": snapshot,
        "agent_bin": binary, "model": args.model, "sandbox": args.sandbox,
        "allow_network": args.allow_network,
        **{key: getattr(args, key) for key in LIMITS},
        "turn_timeout_seconds": args.turn_timeout_seconds, "turn_number": 0,
        "turns_without_implementation": 0, "failures": 0, "session_id": None, "inflight": None,
        "stagnation_window": args.stagnation_window, "session_checkpoints": args.session_checkpoints,

        "objective_progress": signals["objective_progress"],
        "objective_anchor": args.objective_anchor,
        "execution_health": signals["execution_health"],
        "failure_review_window": args.failure_review_window,
        "comparison_continuity": signals["comparison_continuity"],
        "comparison_review_window": args.comparison_review_window,
        "next_mode": "work", "recovery_needed": False, "last_summary": "",
        "next_action": "Establish or resume the credible baseline",
        "last_agent_status": None, "last_error": "", "retry_at": None,
        "retry_base_seconds": args.retry_base_seconds, "retry_max_seconds": args.retry_max_seconds,
        "stop_reason": "", "created_at": utc_now(), "created_unix": time.time(),
        "usage": {}, "agent_seconds": 0.0, "progress": evidence.counts,
        "completion_check": checker, "completion_timeout_seconds": args.completion_timeout_seconds,
        "protected_files": protected,
    })
    save_state(campaign, state)
    append_event(campaign, {"event": "campaign_created", "campaign_id": state["campaign_id"],
                            "workspace": str(workspace), "archive": str(archive),
                            "completion": "verifier" if checker else "open_ended"})
    return campaign


def supervise(campaign: pathlib.Path, overrides: dict[str, Any],
              resume_stop_hash: str | None = None) -> int:
    try:
        lock = exclusive_lock(campaign / "supervisor.lock")
    except BlockingIOError as exc:
        raise CampaignError("Another background supervisor is already running") from exc
    restarts = 0
    child = None
    child_generation = None
    adopted_generation = None
    entry_generation = read_state(campaign)["manager_generation"]
    adopted = False
    first = True
    retry_at = 0.0
    heartbeat_at = 0.0
    with lock:
        while True:
            state = read_state(campaign)
            now = time.monotonic()
            if now >= heartbeat_at:
                atomic_json(campaign / "supervisor.json", {**process_info(os.getpid()),
                            "at": utc_now(), "restarts": restarts,
                            "manager_generation": child_generation or adopted_generation})
                heartbeat_at = now + HEARTBEAT_SECONDS
            if child is not None:
                code = child.poll()
                if code is None:
                    time.sleep(POLL_SECONDS)
                    continue
                child = None
                state = read_state(campaign)
                if (state["manager_generation"] == child_generation and state["status"] in TERMINAL):
                    return 0 if state["status"] != "blocked" else 2
                child_generation = None
                restarts += 1
                retry_at = now + min(60, state["retry_base_seconds"] * 2 ** min(restarts - 1, 12))
                append_event(campaign, {"event": "manager_restart_scheduled",
                                        "restart": restarts, "exit_code": code})
            busy = lock_busy(campaign / "runner.lock")
            if busy:
                # If an earlier supervisor died, adopt its still-running manager.
                adopted = True
                if state["status"] == "running" or state["manager_generation"] != entry_generation:
                    if adopted_generation != state["manager_generation"]:
                        heartbeat_at = 0.0
                    adopted_generation = state["manager_generation"]
                first = False
                time.sleep(POLL_SECONDS)
                continue
            if adopted:
                state = read_state(campaign)
                if (state["status"] in TERMINAL and
                        (state["manager_generation"] == adopted_generation or
                         state["manager_generation"] != entry_generation)):
                    return 0 if state["status"] != "blocked" else 2
                adopted = False
                adopted_generation = None
            if now < retry_at:
                time.sleep(POLL_SECONDS)
                continue
            child_generation = uuid.uuid4().hex
            command = [sys.executable, str(pathlib.Path(__file__).resolve()), "_run",
                       "--campaign", str(campaign), "--generation", child_generation]
            if first:
                if resume_stop_hash:
                    command += ["--resume-stop-hash", resume_stop_hash]
                for key, value in overrides.items():
                    command += (["--clear-" + key.replace("_", "-")] if value is None else
                                ["--" + key.replace("_", "-"), str(value)])
            with (campaign / "manager.log").open("ab") as log:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            first = False
            heartbeat_at = 0.0
            time.sleep(POLL_SECONDS)


def manager_ready(state: dict[str, Any], manager: dict[str, Any] | None,
                  generation: str | None) -> bool:
    if not generation or state["manager_generation"] != generation:
        return False
    return state["status"] in TERMINAL or bool(
        manager and manager.get("generation") == generation and process_alive(manager))


def launch_background(campaign: pathlib.Path, overrides: dict[str, Any],
                      resume_stop_hash: str | None = None) -> dict[str, Any]:
    if lock_busy(campaign / "supervisor.lock"):
        raise CampaignError("Background supervisor is already running; use status or stop")
    if overrides and lock_busy(campaign / "runner.lock"):
        raise CampaignError("Cannot change limits while an existing manager is running")
    command = [sys.executable, str(pathlib.Path(__file__).resolve()), "_supervise",
               "--campaign", str(campaign)]
    if resume_stop_hash:
        command += ["--resume-stop-hash", resume_stop_hash]
    for key, value in overrides.items():
        command += (["--clear-" + key.replace("_", "-")] if value is None else
                    ["--" + key.replace("_", "-"), str(value)])
    with (campaign / "supervisor.log").open("ab") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
    deadline = time.monotonic() + BACKGROUND_STARTUP_SECONDS
    observed_supervisor = False
    while time.monotonic() < deadline:
        marker = campaign / "supervisor.json"
        if marker.exists() and read_json(marker).get("pid") == process.pid:
            observed_supervisor = True
            supervisor = read_json(marker)
            state = read_state(campaign)
            manager_path = campaign / "manager.json"
            manager = read_json(manager_path) if manager_path.exists() else None
            if manager_ready(state, manager, supervisor.get("manager_generation")):
                return state
        if process.poll() is not None:
            raise CampaignError(f"Could not start background supervisor; inspect {campaign / 'supervisor.log'}")
        time.sleep(POLL_SECONDS)
    if observed_supervisor and process.poll() is None:
        return read_state(campaign)  # public_status reports starting until this manager is ready.
    raise CampaignError("Background supervisor did not become ready; inspect supervisor.log before retrying")


def public_status(campaign: pathlib.Path, state: dict[str, Any]) -> dict[str, Any]:
    value = {key: state[key] for key in (
        "status", "turn_number", "session_id", "turns_without_implementation",
        "last_summary", "next_action", "stop_reason", "next_mode", "progress", "objective_anchor",
        "usage", "agent_seconds", "retry_at", "last_error", "objective_progress",
        "stagnation_window", "session_checkpoints", "session_turns", "context_refreshes",
        "context_refresh_reason", "execution_health", "failure_review_window",
        "comparison_continuity", "comparison_review_window", "workflow_provenance", *LIMITS)}
    value["unreported_usage_turns"] = state["unreported_usage_turns"]
    value["allow_network"] = state.get("allow_network", False)
    value["next_proposal_id"] = state.get("next_proposal_id")
    comparison_key = (state["objective_progress"] or {}).get("comparison_key")
    registration = state.get("proposal_registration")
    value["proposal_registration"] = registration if registration and registration["comparison_key"] == comparison_key else None
    selection_review = state.get("selection_comparison")
    value["selection_comparison"] = selection_review if selection_review and selection_review["comparison_key"] == comparison_key else None
    value["research_state"] = current_research_state(state, comparison_key)
    selection = state.get("working_selection")
    value["working_selection"] = selection if selection and selection["comparison_key"] == comparison_key else None
    delivery = state.get("local_delivery")
    value["local_delivery"] = delivery if delivery and delivery["comparison_key"] == comparison_key else None
    corrections = state.get("research_corrections", {}).get(comparison_key or "null", {})
    value["research_correction_keys"] = [key for key, row in corrections.items()
                                         if row["report"].get("status") != "withdrawn"]
    value["research_withdrawn_keys"] = [key for key, row in corrections.items()
                                       if row["report"].get("status") == "withdrawn"]
    value["frontier_exposed_implementations"] = len(state["frontier_exposures"].get(comparison_key, {}))
    value["pending_exposed_proposals"] = len(state["pending_proposal_exposures"].get(comparison_key, {}))
    value["trial_exposed_proposals"] = len(state["trial_exposures"].get(comparison_key, {}))
    value["learning_exposed_heads"] = len(state["learning_exposures"].get(comparison_key, {}))
    value["campaign"] = str(campaign)
    value["completion_mode"] = "verifier" if state["completion_check"] else "open_ended"
    for role in ("manager", "supervisor"):
        path = campaign / f"{role}.json"
        marker = read_json(path) if path.exists() else None
        value[role] = {**marker, "alive": process_alive(marker)} if marker else None
    supervisor = value["supervisor"]
    if (supervisor and supervisor["alive"] and "manager_generation" in supervisor and
            not manager_ready(state, value["manager"], supervisor["manager_generation"])):
        value["status"] = "starting"
    turn = state["inflight"]
    value["inflight"] = ({key: turn[key] for key in ("number", "token", "mode", "started_unix")}
                         if turn else None)
    if turn:
        value["inflight"].update({key: turn[key] for key in
                                  ("fresh_context", "context_refresh_reason", "context_sha256", "driver_action") if key in turn})
        directory = turn_directory(campaign, turn["number"])
        for name in ("worker", "agent", "heartbeat"):
            path = directory / f"{name}.json"
            value["inflight"][name] = read_json(path) if path.exists() else None
        for kind in ("receipt", "completion"):
            child = directory / kind
            if (child / "request.json").exists():
                value["inflight"][kind] = {
                    name: read_json(child / (name + ".json")) if (child / (name + ".json")).exists()
                    else None for name in ("worker", "agent", "heartbeat", "exit")}
    request = stop_request(campaign)
    value["stop_requested"] = request
    return value


@contextmanager
def stopped_checkpoint(campaign: pathlib.Path, action: str) -> Iterator[dict[str, Any]]:
    try:
        with exclusive_lock(campaign / "supervisor.lock"), exclusive_lock(campaign / "runner.lock"):
            state = read_state(campaign)
            if state["status"] != "stopped_by_user" or state["inflight"]:
                raise CampaignError(f"Stop the campaign at a completed turn before {action}")
            check_control_files(state)
            resources = acquire_resources(campaign, state)
            try:
                yield state
            finally:
                for stream in resources:
                    stream.close()
    except BlockingIOError as exc:
        raise CampaignError("Wait for the campaign manager and supervisor to stop") from exc


def accept_score_invalidations(campaign: pathlib.Path) -> dict[str, Any]:
    """Advance a normally stopped campaign to its reviewed correction events."""
    with stopped_checkpoint(campaign, "accepting score invalidations") as state:
        before = state["archive_snapshot"]
        head = CampaignArchive(pathlib.Path(state["archive"])).verified_score_invalidations(before)
        if head.snapshot == before:
            return state
        facts = head.evidence.signals(state["comparison_review_checkpoint"],
                                      objective_anchor=state.get("objective_anchor"))
        state.update({key: facts[key] for key in
                      ("objective_progress", "execution_health", "comparison_continuity")})
        if head.evidence.selection_excluded(state.get("working_selection")):
            state["working_selection"] = None
        state.update(archive_snapshot=head.snapshot, progress=head.evidence.counts)
        append_event(campaign, {"event": "score_invalidations_accepted",
                                "event_id": "score-invalidations:" + head.snapshot["sha256"],
                                "archive_before": before, "archive_after": head.snapshot})
        save_state(campaign, state)
        return state


def accept_research_corrections(campaign: pathlib.Path, report_path: pathlib.Path) -> dict[str, Any]:
    """Save a reviewed interpretation for the current comparison between turns."""
    with stopped_checkpoint(campaign, "accepting research corrections") as state:
        request = stop_request(campaign)
        if not request or request.get("immediate"):
            raise CampaignError("Research corrections require a normal stop at a completed turn")
        review = read_json(report_path)
        required = {"comparison_key", "corrections"}
        if not isinstance(review, dict) or not required <= set(review) <= required | {"research_state"}:
            raise CampaignError("Expected a review with comparison_key, corrections and an optional research_state")
        reports = review["corrections"]
        if not reports or not correction_reports_valid(reports):
            raise CampaignError("Expected a nonempty JSON array of distinct research corrections")
        comparison = (state["objective_progress"] or {}).get("comparison_key")
        if review["comparison_key"] != comparison:
            raise CampaignError("Research correction does not match the current development comparison")
        current = state["research_corrections"].get(comparison or "null", {})
        finding = (current_research_state(state, comparison) or {}).get("finding", {})
        for report in reports:
            key = report["key"]
            if report.get("status") == "withdrawn" and key not in current and key != finding.get("premise_id"):
                raise CampaignError(f"Cannot withdraw an unknown research correction in this comparison: {key}")
            if not evidence_exists(report["evidence"], state, campaign):
                raise CampaignError(f"Research correction evidence is missing: {key}")
        successor = review.get("research_state")
        if "research_state" in review:
            if not research_state_valid(successor) or successor["status"] != "open":
                raise CampaignError("A replacement research_state must describe an open evidence check")
            if not evidence_exists(successor["evidence"], state, campaign):
                raise CampaignError("Replacement research question evidence is missing")
        archive = CampaignArchive(pathlib.Path(state["archive"]))
        with archive.confirmed(state["archive_snapshot"]):
            raw = archive_tools.canonical({"turn": state["turn_number"], **review}) + b"\n"
            digest = archive_tools.sha256(raw)
            path = campaign / "maintenance" / "research-corrections" / f"{digest}.json"
            origin = {"turn": state["turn_number"], "comparison_key": comparison,
                      "receipt_path": str(path), "assessment_kind": "maintenance_audit"}
            corrections = update_research_corrections(state, origin, reports)
        if path.exists():
            if file_hash(path) != digest:
                raise CampaignError("Saved research correction was modified")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_bytes(path, raw)
        if all(current.get(row["key"], {}).get("receipt_path") == str(path) for row in reports):
            return state
        state.update(research_corrections=corrections, session_id=None, next_mode="rethink", next_proposal_id=None,
                     proposal_registration=None,
                     next_action="Reassess the proposed continuation using the reviewed research corrections. "
                                 "Choose the next action supported by the task and available evidence.")
        if successor:
            state.update(research_state={**origin, "report": successor}, next_mode="research",
                         next_action=successor["missing_evidence"])
        append_event(campaign, {"event": "research_corrections_accepted", "turn": state["turn_number"],
                                "event_id": "research-corrections:" + digest,
                                "comparison_key": comparison, "report_path": str(path), "report_sha256": digest})
        save_state(campaign, state)
        return state


def add_limits(command: argparse.ArgumentParser, clear: bool = False) -> None:
    for name in LIMITS:
        command.add_argument("--" + name.replace("_", "-"), type=int)
        if clear:
            command.add_argument("--clear-" + name.replace("_", "-"), action="store_true")


def add_search_policy(command: argparse.ArgumentParser, defaults: bool = False) -> None:
    command.add_argument("--objective-anchor", help="candidate ID identifying the primary development comparison contract")
    if not defaults:
        command.add_argument("--clear-objective-anchor", action="store_true",
                             help="restore automatic comparison selection")
    command.add_argument("--stagnation-window", type=int,
                         default=DEFAULT_STAGNATION_WINDOW if defaults else None,
                         help="new comparable implementations without a historical best before strategy review")
    command.add_argument("--session-checkpoints", type=int,
                         default=DEFAULT_SESSION_CHECKPOINTS if defaults else None,
                         help="successful checkpoints per context before rotation; 0 disables periodic rotation")
    command.add_argument("--failure-review-window", type=int,
                         default=DEFAULT_FAILURE_REVIEW_WINDOW if defaults else None,
                         help="unmeasured development executions before a fresh repair review; never stops work")
    command.add_argument("--comparison-review-window", type=int,
                         default=DEFAULT_COMPARISON_REVIEW_WINDOW if defaults else None,
                         help="new contracts still lacking another measured implementation before common-contract review")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="create and run an open-ended optimization campaign")
    start.add_argument("--workspace", type=pathlib.Path, required=True)
    start.add_argument("--campaign", type=pathlib.Path, required=True)
    start.add_argument("--task-file", type=pathlib.Path, required=True)
    start.add_argument("--archive", type=pathlib.Path, required=True)
    start.add_argument("--agent-bin", default="codex")
    start.add_argument("--model")
    start.add_argument("--sandbox", choices=["workspace-write", "read-only", "danger-full-access"],
                       default="workspace-write")
    start.add_argument("--allow-network", action="store_true",
                       help="enable authorized research network access in the native workspace profile")
    start.add_argument("--background", action="store_true", help="detach a manager-restarting supervisor")
    add_limits(start)
    start.add_argument("--turn-timeout-seconds", type=float, help="optional watchdog; no default turn timeout")
    start.add_argument("--retry-base-seconds", type=float, default=5.0)
    start.add_argument("--retry-max-seconds", type=float, default=300.0)
    start.add_argument("--completion-check", type=pathlib.Path, help="fixed Python task completion verifier")
    start.add_argument("--check-dependency", type=pathlib.Path, action="append", default=[])
    start.add_argument("--completion-timeout-seconds", type=float, default=60.0)
    add_search_policy(start, defaults=True)
    for name in ("resume", "status", "stop", "accept-score-invalidations", "accept-research-corrections",
                 "_run", "_supervise", "_worker"):
        command = sub.add_parser(name, help=argparse.SUPPRESS if name.startswith("_") else None)
        command.add_argument("--campaign", type=pathlib.Path, required=True)
        if name in {"resume", "_run", "_supervise"}:
            add_limits(command, clear=True)
            add_search_policy(command)
        if name == "_run":
            command.add_argument("--generation")
        if name in {"_run", "_supervise"}:
            command.add_argument("--resume-stop-hash")
        if name == "resume":
            command.add_argument("--background", action="store_true")
        if name == "stop":
            command.add_argument("--reason", default="User requested stop")
            command.add_argument("--now", action="store_true", help="cancel the active local invocation")
        if name == "accept-research-corrections":
            command.add_argument("--report", type=pathlib.Path, required=True, help="reviewed corrections JSON file")
        if name == "_worker":
            command.add_argument("--number", type=int, required=True)
            command.add_argument("--kind", choices=["agent", "completion", "receipt"], default="agent")
            command.add_argument("--resource-fd", type=int, action="append", default=[])
    return root


def limit_overrides(args: argparse.Namespace) -> dict[str, Any]:
    result = {}
    for key in LIMITS:
        value = getattr(args, key, None)
        clear = getattr(args, "clear_" + key, False)
        if value is not None and (value < 1 or clear):
            raise CampaignError(f"{key} must be positive and cannot be combined with its clear flag")
        if value is not None or clear:
            result[key] = None if clear else value
    for key, minimum in (("stagnation_window", 1), ("session_checkpoints", 0), ("failure_review_window", 1),
                         ("comparison_review_window", 1)):
        value = getattr(args, key, None)
        if value is not None:
            if value < minimum:
                raise CampaignError(f"{key} must be at least {minimum}")
            result[key] = value
    anchor = getattr(args, "objective_anchor", None)
    clear_anchor = getattr(args, "clear_objective_anchor", False)
    if anchor is not None and (not anchor.strip() or clear_anchor):
        raise CampaignError("objective-anchor must be nonempty and cannot be combined with its clear flag")
    if anchor is not None or clear_anchor:
        result["objective_anchor"] = None if clear_anchor else anchor
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        overrides = limit_overrides(args)
        if args.command == "start":
            for key in ("turn_timeout_seconds", "retry_base_seconds", "retry_max_seconds",
                        "completion_timeout_seconds"):
                value = getattr(args, key)
                if value is not None and (not 0 < value < float("inf")):
                    raise CampaignError(f"{key} must be finite and positive")
            if args.retry_max_seconds < args.retry_base_seconds:
                raise CampaignError("retry-max-seconds must be at least retry-base-seconds")
            campaign = new_campaign(args)
            state = launch_background(campaign, {}) if args.background else run_campaign(campaign)
        else:
            campaign = args.campaign.expanduser().resolve(strict=True)
            if args.command == "_worker":
                return run_worker(campaign, args.number, args.resource_fd, args.kind)
            if args.command == "_supervise":
                return supervise(campaign, overrides, args.resume_stop_hash)
            if args.command == "_run":
                state = run_campaign(campaign, overrides, managed=True, generation=args.generation,
                                     resume_stop_hash=args.resume_stop_hash)
            elif args.command == "status":
                state = read_state(campaign)
            elif args.command == "accept-score-invalidations":
                state = accept_score_invalidations(campaign)
            elif args.command == "accept-research-corrections":
                state = accept_research_corrections(campaign, args.report)
            elif args.command == "stop":
                state = read_state(campaign)
                if (state["status"] not in {"running", "blocked"} and
                        public_status(campaign, state)["status"] != "starting"):
                    raise CampaignError("Only a running, starting or blocked campaign can be stopped")
                request_stop(campaign, args.reason, args.now)
            else:
                stop_path = campaign / "stop.request.json"
                resume_stop_hash = file_hash(stop_path) if stop_path.exists() else None
                state = (launch_background(campaign, overrides, resume_stop_hash) if args.background else
                         run_campaign(campaign, overrides, resume_stop_hash=resume_stop_hash))
        report = public_status(campaign, state)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        status = state["status"] if args.command == "_run" else report["status"]
        return 2 if status == "blocked" and args.command not in {"status", "stop"} else 0
    except (CampaignError, archive_tools.ArchiveFailure, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
