from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RUNNER = SCRIPTS / "autonomous_campaign.py"
PYTHON = "/usr/bin/python3"
sys.path.insert(0, str(SCRIPTS))
import campaign_runtime as runtime
import campaign_search as search
import autonomous_campaign as driver


FAKE_AGENT = r'''#!/usr/bin/python3
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.environ["FAKE_SCRIPTS"])
import candidate_archive as tools

campaign = pathlib.Path(os.environ["FAKE_CAMPAIGN"])
archive = pathlib.Path(os.environ["FAKE_ARCHIVE"])
workspace = pathlib.Path(os.environ["FAKE_WORKSPACE"])
scenario = os.environ.get("FAKE_SCENARIO", "")
if os.environ.get("COMPETITION_RECEIPT_ONLY") == "1":
    output = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
    origin = json.loads((output.parent.parent / "request.json").read_text())
    with (campaign / "fake-receipt-calls.jsonl").open("a") as stream:
        stream.write(json.dumps({"argv": sys.argv[1:], "prompt": sys.stdin.read()}) + "\n")
    print(json.dumps({"type": "thread.started", "thread_id": "receipt-fork"}), flush=True)
    (campaign / "fake-receipt-ready").write_text(str(os.getpid()))
    if scenario == "missing_receipt_hold":
        while not (campaign / "fake-receipt-release").exists():
            time.sleep(0.03)
    if scenario.startswith("missing_receipt"):
        receipt = {"status": "continue", "summary": "Delivered the already measured candidate; no new work.",
                   "next_action": "Inspect the saved candidate result", "stop_reason": "",
                   "evidence": [str(archive)], "research_state": {
                       "status": "open", "route": "diagnostic", "question": "Does the mechanism transfer?",
                       "alternatives": ["It transfers", "Transfer remains unknown"],
                       "missing_evidence": "Inspect the saved result before deciding.",
                       "answer_actions": [{"observation": "Insufficient controls", "action": "Retain uncertainty"}],
                       "evidence": [str(archive)]}}
        if scenario == "missing_receipt_invalid":
            receipt.pop("evidence")
        if scenario == "missing_receipt_archive_change":
            archive.write_bytes(archive.read_bytes() + b"\n")
        output.write_text(json.dumps(receipt))
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 1}}), flush=True)
    else:
        # Existing invalid-receipt fixtures also fail the one formatting repair;
        # ordinary recovery must still retain all unacknowledged deliveries.
        output.write_text("Still no valid receipt")
        print(json.dumps({"type": "turn.completed"}), flush=True)
    sys.exit(0)
counter = campaign / "fake-turn-count"
number = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(number))
prompt = sys.stdin.read()
orphan = campaign / "clean-child.pid"
orphan_alive = False
if orphan.exists():
    try:
        orphan_alive = pathlib.Path("/proc/" + orphan.read_text() + "/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        pass
with (campaign / "fake-calls.jsonl").open("a") as stream:
    stream.write(json.dumps({"number": number, "argv": sys.argv[1:], "prompt": prompt,
                            "previous_child_alive": orphan_alive}) + "\n")
thread = sys.argv[-2] if "resume" in sys.argv else "test-thread-" + str(number)
print(json.dumps({"type": "thread.started", "thread_id": thread}), flush=True)
(campaign / ("fake-ready-" + str(number))).write_text(str(os.getpid()))

if scenario == "auth":
    print(json.dumps({"type": "error", "message": "401 Unauthorized; please run codex login"}), flush=True)
    sys.exit(1)
if scenario == "bad_session" and number == 2:
    print(json.dumps({"type": "error", "message": "session not found"}), flush=True)
    sys.exit(1)
if scenario in {"review_once_429", "trial_failures"} and number == 1:
    print(json.dumps({"type": "error", "message": "429 Too Many Requests"}), flush=True)
    sys.exit(1)
if scenario == "comparison_retry_429" and number == 5:
    print(json.dumps({"type": "error", "message": "429 Too Many Requests"}), flush=True)
    sys.exit(1)
if scenario == "repeat_plan_rotation_429" and number == 3:
    print(json.dumps({"type": "error", "message": "429 Too Many Requests"}), flush=True)
    sys.exit(1)
if scenario == "clean_child_hold" and number == 1:
    child = subprocess.Popen([sys.executable, "-c",
        "import pathlib,time; pathlib.Path(" + repr(str(campaign / "clean-child-ready")) +
        ").write_text('ready'); time.sleep(300)"], env={}, close_fds=True)
    (campaign / "clean-child.pid").write_text(str(child.pid))
if (scenario in {"hold", "hang", "clean_child_hold", "reviewed_corrections"} and number == 1 or
        scenario == "hold_second" and number == 2):
    while not (campaign / "fake-release").exists():
        time.sleep(0.03)

if scenario in {"repeat_plan", "repeat_plan_interrupt", "repeat_plan_decision_interrupt", "repeat_plan_rotation_429", "repeat_plan_stop", "repeat_plan_stop_foreign",
                "repeat_plan_stop_interrupt"}:
    context_path = pathlib.Path(sys.argv[sys.argv.index("-o") + 1]).with_name("context.json")
    context = json.loads(context_path.read_text())
    if context.get("measurement_plan") is None and not any(
            entry["event"] == "measurement_plan" for entry in tools.read_records(archive)):
        conflict = context["repeat_conflict"]
        parent = tools.candidate_index(tools.read_records(archive))[conflict["leader_candidate"]]
        plan_path = workspace / "repeat-plan.json"
        plan_path.write_text(json.dumps({
            "plan_id": "paired-repeat", "conflict_signature": conflict["signature"],
            "comparison": parent["comparison"], "leader_candidate": conflict["leader_candidate"],
            "challenger_candidate": conflict["challenger_candidate"],
            "witness_candidate": conflict["witness_candidate"],
            "runs": [{"run_id": "paired-one", "seeds": [13] if scenario.startswith("repeat_plan_stop") else [41],
                      "repetitions": 1}],
            "decision_rule": "Compare the prespecified pair and report both raw scores before judging the ordering."
        }))
        tools.record_measurement_plan(tools.parser().parse_args([
            "measure-plan", "--archive", str(archive), "--plan", str(plan_path)]))
    else:
        records = tools.read_records(archive)
        plan = next(entry for entry in records if entry["event"] == "measurement_plan")
        status = tools.measurement_plans.status(plan, records)
        slot = next(((item, name) for item in status["runs"]
                     for name in ("leader", "challenger") if item[name] is None), None)
        if status["stop"] is not None:
            pass
        elif scenario.startswith("repeat_plan_stop") and status["attempts"]:
            stopped = subprocess.run([sys.executable, str(pathlib.Path(os.environ["FAKE_SCRIPTS"]) / "candidate_archive.py"),
                "measure-stop", "--archive", str(archive), "--plan-id", plan["plan_id"],
                "--reason", "Frozen leader raises RuntimeError on seed 13; changing the source cannot fill its slot.",
                "--next-action", "Implement a seed-safe successor and evaluate it as ordinary development."],
                capture_output=True, text=True, check=True)
            assert json.loads(stopped.stdout)["status"] == "stopped_unresolved"
            if scenario == "repeat_plan_stop_interrupt":
                print(json.dumps({"type": "error", "message": "simulated interruption after stop append"}), flush=True)
                sys.exit(1)
        elif slot is None:
            decision_path = workspace / "repeat-decision.json"
            decision_path.write_text(json.dumps({
                "plan_id": plan["plan_id"], "conclusion": "The paired result reverses the initial ordering",
                "reason": "Both prespecified runs are valid and the challenger scored higher in the pair.",
                "next_action": "Inspect the task's promotion and confirmation policy before choosing a successor."}))
            tools.record_measurement_decision(tools.parser().parse_args([
                "measure-decide", "--archive", str(archive), "--decision", str(decision_path)]))
            if scenario == "repeat_plan_decision_interrupt":
                print(json.dumps({"type": "error", "message": "simulated interruption after decision append"}), flush=True)
                sys.exit(1)
        else:
            item, name = slot
            source = workspace / "seed-repeat-runs" / ("leader.py" if name == "leader" else "challenger.py")
            score = 55 if name == "leader" else 65
            measured = subprocess.run([sys.executable, str(source)], capture_output=True,
                                      text=True, env={**os.environ, "REPEAT_SCORE": str(score),
                                                      "REPEAT_SEED": str(item["seeds"][0])})
            result_path = workspace / "seed-repeat-runs" / ("planned-" + str(number) + ".json")
            result_path.write_text(json.dumps({
                "status": "success" if measured.returncode == 0 else "failed",
                "valid": measured.returncode == 0, "candidate_hash": tools.hash_path(source),
                "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
                "score_model_hash": "synthetic-score-model-v1", "stage": "development",
                "evaluation": {"measurement_plan_id": plan["plan_id"],
                               "measurement_run_id": item["run_id"],
                               "seeds": item["seeds"], "repetitions": item["repetitions"]},
                "score": {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                          "value": int(measured.stdout) if measured.returncode == 0 else None},
                "error": measured.stderr,
            }))
            tools.record_candidate(tools.parser().parse_args([
                "record", "--archive", str(archive), "--candidate-id", "planned-" + str(number),
                "--source", str(source), "--result", str(result_path), "--route", "repeatability",
                "--mechanism", "prespecified paired measurement", "--status", "promising",
                "--reuse-reason", "Complete the frozen paired measurement protocol"]))
    if scenario == "repeat_plan_interrupt" and number == 1:
        print(json.dumps({"type": "error", "message": "simulated interruption after plan append"}), flush=True)
        sys.exit(1)

if scenario == "missing_proposal" and number == 2:
    request = json.loads(pathlib.Path(sys.argv[sys.argv.index("-o") + 1]).with_name("request.json").read_text())
    assert request["mode"] == "register" and 'proposal "refine"' in request["driver_action"]
    parent = tools.candidate_index(tools.read_records(archive))["candidate-1"]
    proposal = workspace / "refine.json"
    proposal.write_text(json.dumps({
        "proposal_id": "refine", "parent_ids": ["candidate-1"], "feedback_from": ["candidate-1"],
        "route": "synthetic", "code_targets": [parent["artifact_paths"]["source"]],
        "basis": "Compare the change to the archived control", "change": "Use a different representation",
        "expected_observation": "Higher matched score", "validation": "Reuse the fixed synthetic evaluator",
        "stop_condition": "Stop if this implementation does not score higher"}))
    tools.propose_candidate(tools.parser().parse_args([
        "propose", "--archive", str(archive), "--proposal", str(proposal)]))
    print(json.dumps({"type": "turn.failed", "error": {"message": "stream closed after registration"}}), flush=True)
    sys.exit(1)

if scenario not in {"no_progress", "research_no_progress", "research_finding", "repeat_plan", "repeat_plan_interrupt", "repeat_plan_decision_interrupt", "repeat_plan_rotation_429"} and not (
                                      scenario.startswith("local_delivery") and number != 1 or
                                      scenario.startswith("selected_proposal") and number != 4 or
                                      scenario.startswith("repeat_plan_stop") and number <= (2 if scenario == "repeat_plan_stop_foreign" else 3) or
                                      scenario == "comparison_retry_receipt" and number == 5 or
                                      scenario == "trial_failures" and number == 2):
    runs = workspace / "runs"
    runs.mkdir(exist_ok=True)
    source = runs / ("candidate-" + str(number) + ".py")
    value = (1 if scenario == "repeat" else
             100 - number if scenario == "regress" else
             100 if scenario == "diagnostic_failure" and number == 1 else
             100 - number if scenario == "diagnostic_failure" else number)
    if scenario == "comparison_pairing" and number == 5:
        # Re-evaluate an existing implementation on candidate-4's contract.
        # A legitimate measurement repair does not require changing its code.
        source = runs / "candidate-3.py"
    else:
        source.write_text("print(" + str(value) + ")\n")
    if (scenario == "diagnostic_ablations" and number <= 5 or
            scenario in {"diagnostic_only", "diagnostic_claim_complete"}):
        # Each program removes a real feature group from an otherwise valid
        # binary predictor. These weak probes identify feature contributions.
        omitted = None if scenario == "diagnostic_ablations" and number == 1 else (
            number - 2 if scenario == "diagnostic_ablations" else (number - 1) % 4)
        enabled = [index for index in range(4) if index != omitted]
        source.write_text("rows=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1],[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]\n"
                          "labels=[1,1,1,1,0,0,0,0]\nenabled=" + repr(enabled) + "\n"
                          "predictions=[int(any(row[i] for i in enabled)) for row in rows]\n"
                          "print(sum(prediction==label for prediction,label in zip(predictions,labels)))\n")
    failed = (scenario == "invalid_forever" and number > 1 or
              scenario == "recover_execution" and 2 <= number <= 4 or
              scenario == "diagnostic_failure" and number == 2)
    if failed:
        source.write_text("raise RuntimeError('candidate failed " + str(number) + "')\n")
    measured = subprocess.run([sys.executable, str(source)], capture_output=True, text=True)
    result_path = runs / ("result-" + str(number) + ".json")
    outcome = {
        "status": "failed" if failed else "success", "valid": not failed,
        "candidate_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
        "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
        "score_model_hash": "synthetic-score-model-v1",
        "stage": "development", "elapsed_seconds": 0.01,
    }
    if scenario.startswith("comparison_"):
        outcome["evaluation"] = {"config_hash": "config-" + str(
            4 if scenario == "comparison_pairing" and number == 5 else number)}
    if scenario == "repeat_plan_stop_foreign":
        outcome["evaluation"] = {"config_hash": "other-evaluation"}
    if scenario == "objective_smoke":
        outcome["stage"] = "smoke"
    if scenario == "selected_proposal_foreign":
        outcome["evaluation"] = {"config_hash": "candidate-recipe", "runtime_environment": {"notes": "different"}}
    if failed:
        outcome["error"] = {"type": "runtime_failure", "phase": "candidate_execution", "message": measured.stderr}
    elif scenario != "unscored_forever":
        outcome["score"] = {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                            "value": int(measured.stdout)}
    result_path.write_text(json.dumps(outcome))
    args = ["record", "--archive", str(archive), "--candidate-id", "candidate-" + str(number),
            "--source", str(source), "--result", str(result_path),
            "--route", "pending-1" if scenario.startswith("selected_proposal") else
                       "synthetic-" + str(number % 2) if scenario == "regress" else "synthetic",
            "--mechanism", "executed synthetic implementation", "--status", "promising"]
    diagnostic = (scenario == "diagnostic_ablations" and 2 <= number <= 5 or
                  scenario == "diagnostic_failure" and number == 2 or
                  scenario in {"diagnostic_only", "diagnostic_claim_complete"})
    if diagnostic:
        args += ["--role", "diagnostic", "--parent", "seed-best" if scenario in {
            "diagnostic_only", "diagnostic_claim_complete"} else "candidate-1",
                 "--feedback", "Diagnostic feature contribution or execution probe " + str(number) +
                 ": intentionally isolate a component; this is not a selectable candidate improvement."]
    if scenario == "repeat" and number > 1:
        args += ["--reuse-reason", "controlled repeated measurement"]
    if scenario == "comparison_pairing" and number == 5:
        args += ["--parent", "candidate-4", "--reuse-reason", "evaluate existing source on the frozen target contract"]
    if number > 1 and scenario in {"invalid_forever", "recover_execution", "unscored_forever"}:
        args += ["--parent", "candidate-" + str(number - 1)]
    if scenario.startswith("selected_proposal"):
        request = json.loads(pathlib.Path(sys.argv[sys.argv.index("-o") + 1]).with_name("request.json").read_text())
        assert request["mode"] == "execute" and 'proposal "p1"' in request["driver_action"]
        args += ["--parent", "seed-best", "--proposal-id", "p1", "--prediction-status",
                 "contradicted" if scenario == "selected_proposal" else "unresolved",
                 "--feedback", "The prototype produced a scored result."]
    if scenario == "missing_proposal" and number == 3:
        request = json.loads(pathlib.Path(sys.argv[sys.argv.index("-o") + 1]).with_name("request.json").read_text())
        assert request["mode"] == "execute" and 'proposal "refine"' in request["driver_action"]
        args += ["--parent", "candidate-1", "--proposal-id", "refine", "--prediction-status", "supported",
                 "--feedback", "Higher score under the original evaluation."]
    tools.record_candidate(tools.parser().parse_args(args))

    if scenario == "diagnostic_on_stagnation" and number == 1:
        probe = runs / "stagnation-diagnostic.py"
        probe.write_text("raise RuntimeError('diagnostic failed after ordinary regressions')\n")
        failed_probe = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
        assert failed_probe.returncode != 0
        probe_result = runs / "stagnation-diagnostic.json"
        probe_result.write_text(json.dumps({
            "status": "failed", "valid": False, "candidate_hash": tools.hash_path(probe),
            "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
            "score_model_hash": "synthetic-score-model-v1", "stage": "development",
            "error": {"type": "runtime_failure", "phase": "candidate_execution", "message": failed_probe.stderr}}))
        tools.record_candidate(tools.parser().parse_args([
            "record", "--archive", str(archive), "--candidate-id", "stagnation-diagnostic",
            "--source", str(probe), "--result", str(probe_result), "--role", "diagnostic",
            "--parent", "candidate-1", "--route", "diagnostic", "--mechanism", "failed diagnostic execution",
            "--status", "rejected"]))

if scenario == "fail_four" and number <= 4:
    print(json.dumps({"type": "error", "message": "429 Too Many Requests; transient backend failure"}), flush=True)
    sys.exit(1)
if scenario == "partial_archive" and number == 1:
    with archive.open("ab") as stream:
        stream.write(b'{"schema_version":1,"event":"candi')
if scenario == "tamper" and number == 2:
    archive.write_text(archive.read_text().replace("candidate-1", "candidate-x"))
if scenario == "checker_tamper":
    pathlib.Path(os.environ["FAKE_CHECKER"]).write_text("print('changed')\n")
if scenario == "context_tamper":
    output = pathlib.Path(sys.argv[sys.argv.index("-o") + 1])
    output.with_name("context.json").write_text('{"changed": true}\n')

status = ("complete" if scenario in {"claim_complete", "diagnostic_claim_complete"} else
          "blocked" if scenario == "claim_blocked" else "continue")
receipt = {"status": status, "summary": "evaluated candidate " + str(number),
           "next_action": "execute the next mechanism" if status == "continue" else "",
           "stop_reason": "no credible follow-up" if status != "continue" else "",
           "evidence": [] if scenario in {"no_progress", "research_no_progress"} else [str(archive)]}
if scenario in {"research_no_progress", "research_finding"}:
    receipt["next_action"] = "Require a guaranteed score before building any candidate."
    receipt["research_state"] = {
        "status": "open", "route": "source", "question": "Can a new representation transfer?",
        "alternatives": ["The available information supports a prototype", "A required input is unavailable"],
        "missing_evidence": "A verified description of the input.",
        "answer_actions": [{"observation": "Input is available", "action": "Build a bounded prototype"}],
        "evidence": [str(campaign / "task.md")]}
if scenario == "research_finding" and number in (2, 3):
    artifact = workspace / ("original.txt" if number == 2 else "duplicate.txt")
    artifact.write_text("Source: the existing encoder pools rare levels but erases category order.")
    receipt["next_action"] = "Trace which known category order is available in the input."
    receipt["research_state"]["evidence"] = [str(artifact)]
    receipt["research_finding"] = {
        "premise_id": "existing-pooling" if number == 2 else "renamed-pooling",
        "evidence_path": str(artifact),
        "observation": "The current encoder already pools rare levels.",
        "design_effect": "Check a representation that preserves available category order."}
if scenario.startswith("selected_proposal") and number == 3:
    receipt.update(summary="Selected an existing representation change after review.",
                   next_action="Check the proposed representation against the primary control.",
                   next_proposal_id="p1")
    receipt["research_state"] = {
        "status": "open", "route": "implement", "question": "Does the new representation improve the score?",
        "alternatives": ["New representation", "Current control"], "missing_evidence": "Matched evaluation.",
        "answer_actions": [{"observation": "Measures higher on the same contract", "action": "Review its gain."}],
        "evidence": [str(archive)]}
if scenario.startswith("selected_proposal") and number == 4:
    receipt["next_action"] = "Inspect which saved cases improved after the representation change."
    if scenario == "selected_proposal_foreign":
        receipt["working_selection"] = {
            "candidate_id": "candidate-4", "reason": "New best.",
            "limitations": "Development evidence only.", "evidence": [str(archive)]}
if scenario == "missing_proposal" and number == 1:
    receipt["next_proposal_id"] = "refine"
if scenario in {"working_selection", "descriptive_finding"} and number <= 2:
    receipt["working_selection"] = {
        "candidate_id": "candidate-1" if number == 1 else "unknown-candidate",
        "reason": "Selected under the task protocol.", "limitations": "Development evidence only.",
        "evidence": [str(archive)]}
if scenario == "descriptive_finding":
    receipt["research_finding"] = {
        "premise_id": "score-definition",
        "observation": "The evaluator maximizes the recorded objective.",
        "design_effect": "Compared the implementation on the same objective.",
        "evidence_path": str(archive)}
if scenario.startswith("local_delivery"):
    candidate, draft = "candidate-1", workspace / "local-draft.csv"
    if number == 1:
        receipt["next_action"] = "Investigate the saved research premise after local delivery."
        receipt["working_selection"] = {
            "candidate_id": candidate, "reason": "Selected on development.",
            "limitations": "No confirmation.", "evidence": [str(archive)]}
        receipt["research_state"] = {
            "status": "open", "route": "diagnostic", "question": "Which design helps?",
            "alternatives": ["A", "B"], "missing_evidence": "A later check.",
            "answer_actions": [{"observation": "Research remains", "action": "Investigate later"}], "evidence": []}
        receipt["local_delivery"] = {
            "candidate_id": candidate, "status": "requested", "detail": "Produce the local draft from saved models.",
            "evidence": []}
    else:
        if scenario != "local_delivery_missing" and not draft.exists():
            draft.write_text("id,prediction\n1,2\n")
        if scenario == "local_delivery_interrupted" and number == 2:
            print(json.dumps({"type": "turn.failed",
                              "error": {"message": "stream closed before response.completed"}}), flush=True)
            sys.exit(1)
        receipt["local_delivery"] = {
            "candidate_id": candidate, "status": "completed", "detail": "Checked the existing draft.",
            "evidence": [str(draft)]}
        receipt["next_action"] = "The local draft is ready."
if scenario == "reviewed_corrections" and number == 1:
    receipt["next_action"] = "Reuse the allegedly fold-honest fitted gate."
    receipt["corrections"] = [{
        "key": "gate", "claim": "The fitted gate is fold-honest.", "conditions": "Fixed folds.",
        "limitations": "No independent confirmation.", "reopen_when": "Review the fit lineage.",
        "evidence": [str(archive)]}]
if scenario == "correction_evidence":
    report = {"key": "direction", "claim": "The direction follows the stated objective.",
              "conditions": "Fixed evaluator.", "limitations": "Development only.",
              "reopen_when": "The scorer changes.", "evidence": [str(archive)]}
    research = {"status": "open", "route": "source", "question": "Which rule governs ties?",
                "alternatives": ["Secondary metric", "Stable case order"], "missing_evidence": "Inspect the official rules.",
                "answer_actions": [{"observation": "Secondary metric specifies ties", "action": "Preserve it in the scorer."}],
                "evidence": [str(archive)]}
    if number == 1:
        receipt["corrections"] = [report]
        receipt["research_state"] = research
    else:
        (workspace / "probe.txt").write_text("Run succeeded on the fixed fixture.\n")
        receipt["corrections"] = [
            {**report, "claim": "The direction is reversed.", "evidence": ["misplaced/probe.txt"]},
            {**report, "key": "probe", "evidence": ["probe.txt#observation", "https://example.com/rules#score"]},
        ]
        receipt["research_state"] = {**research, "question": "Can the scorer drop the tie rule?",
                                     "evidence": ["misplaced/rules.md#Tie"]}
if (scenario == "invalid_receipt" and number == 1 or
        scenario == "comparison_retry_receipt" and number == 5 or
        scenario == "trial_failures" and number == 2):
    receipt.pop("evidence")
if scenario == "selected_proposal_foreign" and number == 5:
    print(json.dumps({"type": "turn.failed", "error": {"message": "stream closed during comparison recovery"}}))
    sys.exit(1)
message = json.dumps(receipt)
if scenario.startswith("missing_receipt") and number == 1:
    message = "Composing the receipt and validating it against the supplied schema shape."
if scenario == "prose_receipt":
    message = "All work is recorded. Receipt follows.\n\n" + message
if scenario == "fenced_receipt":
    message = "All work is recorded. Receipt follows.\n\n```json\n" + json.dumps(receipt, indent=2) + "\n```\n"
pathlib.Path(sys.argv[sys.argv.index("-o") + 1]).write_text(message)
if scenario == "left_child":
    child = subprocess.Popen([sys.executable, "-c",
        "import pathlib,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "pathlib.Path(" + repr(str(campaign / "child-ready")) + ").write_text('ready'); time.sleep(300)"])
    (campaign / "child-pid").write_text(str(child.pid))
    while not (campaign / "child-ready").exists():
        time.sleep(0.01)
if not (scenario == "no_terminal" and number == 1):
    terminal = {"type": "turn.completed"}
    if not os.environ.get("FAKE_NO_USAGE"):
        terminal["usage"] = {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 2}
    print(json.dumps(terminal), flush=True)
if scenario == "receipt_then_fail" and number == 1:
    sys.exit(7)
'''

CHECKER = r'''import argparse
import json
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument("--workspace")
parser.add_argument("--archive")
args = parser.parse_args()
records = [json.loads(line) for line in pathlib.Path(args.archive).read_text().splitlines()]
complete = sum(entry["event"] == "candidate" for entry in records) >= 3
print(json.dumps({"complete": complete, "reason": "explicit three-experiment contract" if complete else "more work",
                  "evidence": [args.archive]}))
'''


HELD_CHECKER = r'''import json
import os
import pathlib
import subprocess
import sys
import time

campaign = pathlib.Path(os.environ["FAKE_CAMPAIGN"])
with (campaign / "checker-calls.jsonl").open("a") as stream:
    stream.write(json.dumps({"pid": os.getpid()}) + "\n")
child = None
if os.environ.get("FAKE_CHECKER_CHILD"):
    child = subprocess.Popen([sys.executable, "-c",
        "import pathlib,time; pathlib.Path(" + repr(str(campaign / "checker-child-ready")) +
        ").write_text('ready'); time.sleep(300)"], env={}, close_fds=True)
    (campaign / "checker-child.pid").write_text(str(child.pid))
    while not (campaign / "checker-child-ready").exists():
        time.sleep(0.01)
(campaign / "checker-ready").write_text(str(os.getpid()))
while not (campaign / "checker-release").exists():
    time.sleep(0.03)
if child is not None:
    child.terminate()
    child.wait(timeout=3)
print(json.dumps({"complete": True, "reason": "one measured implementation meets this test contract",
                  "evidence": [os.environ["FAKE_ARCHIVE"]]}))
'''


class AutonomousCampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.task = self.workspace / "task.md"
        self.task.write_text("Optimize this synthetic contest.\n", encoding="utf-8")
        self.campaign = self.root / "campaign"
        self.archive = self.workspace / "candidate-archive.jsonl"
        self.agent = self.root / "fake-codex"
        self.agent.write_text(FAKE_AGENT, encoding="utf-8")
        self.agent.chmod(0o755)
        self.environment = {**os.environ, "FAKE_CAMPAIGN": str(self.campaign),
                            "FAKE_ARCHIVE": str(self.archive), "FAKE_SCRIPTS": str(SCRIPTS),
                            "FAKE_WORKSPACE": str(self.workspace)}
        self.processes: list[subprocess.Popen] = []
        self.addCleanup(self.shutdown)

    def call(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([PYTHON, str(RUNNER), *args], capture_output=True,
                              text=True, env=self.environment, timeout=45)

    def start_args(self, *extra: str) -> list[str]:
        return ["start", "--workspace", str(self.workspace), "--campaign", str(self.campaign),
                "--task-file", str(self.task), "--archive", str(self.archive),
                "--agent-bin", str(self.agent), "--retry-base-seconds", "0.03",
                "--retry-max-seconds", "0.08", *extra]

    def start(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.call(*self.start_args(*extra))

    def start_process(self, *extra: str) -> subprocess.Popen:
        process = subprocess.Popen([PYTHON, str(RUNNER), *self.start_args(*extra)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env=self.environment)
        self.processes.append(process)
        return process

    def state(self) -> dict:
        return json.loads((self.campaign / "state.json").read_text())

    def calls(self) -> list[dict]:
        path = self.campaign / "fake-calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def events(self) -> list[dict]:
        return [json.loads(line) for line in (self.campaign / "events.jsonl").read_text().splitlines()]

    def test_working_selection_rejects_unknown_id_without_losing_measured_work_or_previous_choice(self) -> None:
        self.environment["FAKE_SCENARIO"] = "working_selection"
        result = self.start("--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.state()
        self.assertEqual(state["working_selection"]["candidate_id"], "candidate-1")
        self.assertEqual(state["objective_progress"]["best_candidate"], "candidate-3")
        self.assertEqual(state["progress"]["evaluated_candidates"], 3)
        interrupted = [event for event in self.events() if event["event"] == "turn_interrupted"]
        self.assertEqual(len(interrupted), 1)
        self.assertIn("Working selection must name a measured development implementation", interrupted[0]["error"])
        self.assertFalse(any(event["event"] == "unconfirmed_archive_quarantined" for event in self.events()))
        context = self.turn_context(3)
        self.assertEqual(context["working_selection"]["candidate_id"], "candidate-1")
        self.assertIn("candidate-1", context["development_brief"]["candidates"])
        status = driver.public_status(self.campaign, state)
        self.assertEqual(status["working_selection"]["candidate_id"], "candidate-1")

    def test_public_status_distinguishes_current_and_withdrawn_interpretations(self) -> None:
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.state()
        key = (state["objective_progress"] or {}).get("comparison_key") or "null"
        state["research_corrections"] = {
            key: {"current": {"report": {"key": "current", "claim": "Conditional finding"}},
                  "obsolete": {"report": {"key": "obsolete", "status": "withdrawn", "reason": "Bad premise"}}},
            "foreign": {"unrelated": {"report": {"key": "unrelated", "status": "withdrawn"}}}}
        status = driver.public_status(self.campaign, state)
        self.assertEqual(status["research_correction_keys"], ["current"])
        self.assertEqual(status["research_withdrawn_keys"], ["obsolete"])

    def test_failed_research_retains_its_selected_action_for_recovery(self) -> None:
        self.environment["FAKE_SCENARIO"] = "no_progress"
        first = self.start("--max-turns", "1")
        self.assertEqual(first.returncode, 0, first.stderr)
        state = self.state()
        action = "Inspect the existing controls; if absent, keep the transfer claim unknown."
        research = {"turn": 1, "receipt_path": str(self.campaign / "turns/000001/message.json"),
                    "comparison_key": state["objective_progress"]["comparison_key"],
                    "assessment_kind": "agent_report", "report": {
                        "status": "open", "route": "diagnostic", "question": "Is transfer identified?",
                        "alternatives": ["Controlled evidence exists", "Controls are unknown"],
                        "missing_evidence": "Inspect saved controls before any new measurement.",
                        "answer_actions": [{"observation": "No saved controls", "action": "Retain uncertainty"}],
                        "evidence": [str(self.task)]}}
        state.update(research_state=research, next_action=action, next_mode="research")
        driver.save_state(self.campaign, state)
        self.environment["FAKE_SCENARIO"] = "bad_session"
        failed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(failed.returncode, 0, failed.stderr)
        recovered = self.state()
        self.assertTrue(recovered["recovery_needed"])
        self.assertEqual(recovered["next_action"], action)
        self.assertEqual(recovered["research_state"], research)
        self.assertEqual(recovered["next_mode"], "research")
        self.assertEqual(recovered["session_turns"], state["session_turns"])
        request = json.loads((self.campaign / "turns/000002/request.json").read_text())
        self.assertEqual(request["mode"], "research")
        self.assertEqual(request["context"]["decision_context"]["research_state"]["report"], research["report"])

    def seed_open_branches(self, count: int = 5) -> list[dict]:
        """Run old, low-scoring implementations under the fake agent's contract."""
        runs = self.workspace / "seed-runs"
        runs.mkdir()
        entries = []
        for number in range(count + 1):
            is_best = number == count
            name = "seed-best" if is_best else "seed-open-" + str(number)
            source = runs / (name + ".py")
            source.write_text("print(" + str(1000 if is_best else 100 + number) + ")\n")
            measured = subprocess.run([PYTHON, str(source)], capture_output=True, text=True, check=True)
            result_path = runs / (name + ".json")
            result_path.write_text(json.dumps({
                "status": "success", "valid": True,
                "candidate_hash": runtime.file_hash(source),
                "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
                "score_model_hash": "synthetic-score-model-v1", "stage": "development",
                "elapsed_seconds": 0.01,
                "score": {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                          "value": int(measured.stdout)},
            }))
            arguments = ["record", "--archive", str(self.archive), "--candidate-id", name,
                         "--source", str(source), "--result", str(result_path),
                         "--route", name, "--mechanism", "executed archived branch",
                         "--status", "incumbent" if is_best else "promising"]
            if not is_best:
                arguments += ["--feedback", "Unresolved representation could support an informative successor"]
            entries.append(driver.archive_tools.record_candidate(driver.archive_tools.parser().parse_args(arguments)))
        return entries

    def test_explicit_objective_persists_and_can_be_changed_or_cleared_on_resume(self) -> None:
        self.seed_open_branches(1)
        self.environment["FAKE_SCENARIO"] = "objective_smoke"
        result = self.start("--objective-anchor", "seed-best", "--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["objective_anchor"], "seed-best")
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "seed-best")
        context = json.loads((self.campaign / "turns/000001/context.json").read_text())
        self.assertEqual(context["objective_progress"]["objective_anchor"], "seed-best")
        self.assertIn("--anchor seed-best", (self.campaign / "turns/000001/prompt.txt").read_text())

        result = self.call("resume", "--campaign", str(self.campaign),
                           "--objective-anchor", "candidate-1", "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["objective_anchor"], "candidate-1")
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "candidate-2")
        context = json.loads((self.campaign / "turns/000002/context.json").read_text())
        self.assertEqual(context["objective_progress"]["comparison"]["stage"], "smoke")

        result = self.call("resume", "--campaign", str(self.campaign),
                           "--clear-objective-anchor", "--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.state()["objective_anchor"])
        self.assertIsNone(self.state()["objective_progress"]["objective_anchor"])
        self.assertEqual(len(self.calls()), 3)

    def test_invalid_objective_anchor_is_rejected_before_agent_launch(self) -> None:
        self.seed_open_branches(1)
        result = self.start("--objective-anchor", "missing-candidate", "--max-turns", "1")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Objective anchor", result.stderr)
        self.assertFalse(self.campaign.exists())
        args = driver.parser().parse_args([
            "resume", "--campaign", str(self.campaign), "--objective-anchor", "seed-best",
            "--clear-objective-anchor"])
        with self.assertRaises(runtime.CampaignError):
            driver.limit_overrides(args)

    def test_invalid_objective_override_keeps_sealed_inflight_without_relaunch(self) -> None:
        self.seed_open_branches(1)
        args = driver.parser().parse_args(self.start_args("--objective-anchor", "seed-best"))
        driver.new_campaign(args)
        state = driver.read_state(self.campaign)
        driver.prepare_turn(self.campaign, state)
        sealed = deepcopy(state["inflight"])
        with self.archive.open("ab") as stream:
            stream.write(b'{"event":"unfinished')
        suffix = self.archive.read_bytes()
        with mock.patch.object(driver, "await_turn", side_effect=AssertionError("must not relaunch")):
            outcome = driver.run_campaign(self.campaign, {"objective_anchor": "missing-candidate"})
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn("Objective anchor", outcome["stop_reason"])
        self.assertEqual(outcome["objective_anchor"], "seed-best")
        self.assertEqual(outcome["inflight"], sealed)
        self.assertEqual(self.archive.read_bytes(), suffix)
        self.assertEqual(self.calls(), [])

    def seed_repeat_conflict(self, *, seed_failure: bool = False) -> None:
        runs = self.workspace / "seed-repeat-runs"
        runs.mkdir()
        sources = {name: runs / (name + ".py") for name in ("leader", "challenger")}
        sources["leader"].write_text("import os\n" + (
            "if os.environ.get('REPEAT_SEED') == '13':\n    raise RuntimeError('seed 13 is unsupported')\n"
            if seed_failure else "") + "print(int(os.environ['REPEAT_SCORE']))\n")
        sources["challenger"].write_text("import os\nprint(int(os.environ['REPEAT_SCORE']))\n# other recipe\n")
        for name, source_name, score in (("leader-first", "leader", 100),
                                         ("challenger-first", "challenger", 60),
                                         ("leader-repeat", "leader", 10),
                                         ("challenger-repeat", "challenger", 60)):
            source = sources[source_name]
            measured = subprocess.run([PYTHON, str(source)], capture_output=True, text=True,
                                      check=True, env={**os.environ, "REPEAT_SCORE": str(score)})
            result_path = runs / (name + ".json")
            result_path.write_text(json.dumps({
                "status": "success", "valid": True, "candidate_hash": runtime.file_hash(source),
                "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
                "score_model_hash": "synthetic-score-model-v1", "stage": "development",
                "score": {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                          "value": int(measured.stdout)},
            }))
            arguments = ["record", "--archive", str(self.archive), "--candidate-id", name,
                         "--source", str(source), "--result", str(result_path),
                         "--route", "repeatability", "--mechanism", "seeded measurement fixture",
                         "--status", "runner_up"]
            if name.endswith("repeat"):
                arguments += ["--reuse-reason", "independent score measurement"]
            driver.archive_tools.record_candidate(driver.archive_tools.parser().parse_args(arguments))

    def turn_context(self, number: int) -> dict:
        return json.loads((runtime.turn_directory(self.campaign, number) / "context.json").read_text())

    def freeze_repeat_plan(self, runs: int = 3) -> dict:
        records = driver.archive_tools.read_records(self.archive)
        leader = driver.archive_tools.candidate_index(records)["leader-first"]
        conflict = driver.archive_tools.ComparisonEvidence(
            records, eligible=search.observed_implementation).for_candidate("leader-first").ranking_conflict()
        plan = {"plan_id": "paired-repeat", "conflict_signature": conflict["signature"],
                "comparison": leader["comparison"], "leader_candidate": "leader-first",
                "challenger_candidate": "challenger-first", "witness_candidate": conflict["witness_candidate"],
                "runs": [{"run_id": "paired-" + str(number), "seeds": [41 + number], "repetitions": 1}
                         for number in range(runs)],
                "decision_rule": "Compare all prespecified pairs and preserve the raw scores."}
        path = self.workspace / "frozen-repeat-plan.json"
        path.write_text(json.dumps(plan))
        return driver.archive_tools.record_measurement_plan(driver.archive_tools.parser().parse_args([
            "measure-plan", "--archive", str(self.archive), "--plan", str(path)]))

    def seed_pending_proposals(self, count: int = 7) -> list[dict]:
        parent = self.seed_open_branches(0)[0]
        proposals = []
        for number in range(count):
            value = {"proposal_id": "p" + str(number), "parent_ids": [parent["candidate_id"]],
                     "feedback_from": [parent["candidate_id"]], "route": "pending-" + str(number),
                     "code_targets": [parent["artifact_paths"]["source"]],
                     "basis": "Verified incumbent implementation and same-contract measured result",
                     "change": "Implement distinct representation " + str(number),
                     "expected_observation": "Measure whether the representation removes residual error",
                     "validation": "Execute under the existing development contract",
                     "stop_condition": "Stop this proposal if its expected observation is contradicted"}
            path = self.workspace / (value["proposal_id"] + ".json")
            path.write_text(json.dumps(value))
            proposals.append(driver.archive_tools.propose_candidate(driver.archive_tools.parser().parse_args([
                "propose", "--archive", str(self.archive), "--proposal", str(path)])))
        return proposals

    def seed_completed_trials(self) -> dict[str, dict]:
        """Complete real proposals with one best-related branch and four old branches."""
        best = self.seed_open_branches(0)[0]
        runs = self.workspace / "completed-trials"
        runs.mkdir()

        def record(name: str, value: int, *, parent: str | None = None,
                   proposal_id: str | None = None) -> dict:
            source = runs / (name + ".py")
            source.write_text("print(" + str(value) + ")\n")
            measured = subprocess.run([PYTHON, str(source)], capture_output=True, text=True, check=True)
            result = runs / (name + ".json")
            result.write_text(json.dumps({
                "status": "success", "valid": True, "candidate_hash": runtime.file_hash(source),
                "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
                "score_model_hash": "synthetic-score-model-v1", "stage": "development",
                "elapsed_seconds": 0.01,
                "score": {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                          "value": int(measured.stdout)}}))
            arguments = ["record", "--archive", str(self.archive), "--candidate-id", name,
                         "--source", str(source), "--result", str(result), "--route", "trial-history",
                         "--mechanism", "executed completed proposal fixture", "--status", "runner_up",
                         "--feedback", "Self-reported historical feedback for " + name]
            if parent:
                arguments += ["--parent", parent]
            if proposal_id:
                arguments += ["--proposal-id", proposal_id, "--prediction-status", "contradicted"]
            return driver.archive_tools.record_candidate(driver.archive_tools.parser().parse_args(arguments))

        completed = {}
        for number in range(5):
            related = number == 4
            proposal_id = "trial-related" if related else "trial-global-" + str(number)
            parent = best if related else record("trial-parent-" + str(number), 100 + number)
            value = {"proposal_id": proposal_id, "parent_ids": [parent["candidate_id"]],
                     "feedback_from": [parent["candidate_id"]], "route": "trial-history",
                     "code_targets": [parent["artifact_paths"]["source"]],
                     "basis": "A previous implementation and its actual matching result",
                     "change": "Historical structural change for " + proposal_id,
                     "expected_observation": "Expected distinct observation for " + proposal_id,
                     "validation": "Execute unchanged development adapter contract",
                     "stop_condition": "Review observed behavior before repeating this exact proposal"}
            path = runs / (proposal_id + "-input.json")
            path.write_text(json.dumps(value))
            proposal = driver.archive_tools.propose_candidate(driver.archive_tools.parser().parse_args([
                "propose", "--archive", str(self.archive), "--proposal", str(path)]))
            outcome = record("trial-outcome-" + str(number), 900 if related else 200 + number,
                             parent=parent["candidate_id"], proposal_id=proposal_id)
            completed[proposal_id] = {"proposal": proposal, "outcome": outcome}
        return completed

    def seed_review_attempt(self, number: int, *, failed: bool, role: str = "development") -> dict:
        runs = self.workspace / "seed-runs"
        name = "seed-review-" + str(number)
        source = runs / (name + ".py")
        source.write_text("raise RuntimeError('seed failure " + str(number) + "')\n" if failed else
                          "print(" + str(999 - number) + ")\n")
        measured = subprocess.run([PYTHON, str(source)], capture_output=True, text=True)
        self.assertEqual(measured.returncode != 0, failed)
        result = {"status": "failed" if failed else "success", "valid": not failed,
                  "candidate_hash": runtime.file_hash(source), "evaluator_hash": "synthetic-evaluator-v1",
                  "workload_hash": "synthetic-workload-v1", "score_model_hash": "synthetic-score-model-v1",
                  "stage": "development", "elapsed_seconds": 0.01}
        if failed:
            result["error"] = {"type": "runtime_failure", "phase": "candidate_execution", "message": measured.stderr}
        else:
            result["score"] = {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                               "value": int(measured.stdout)}
        path = runs / (name + ".json")
        path.write_text(json.dumps(result))
        return driver.archive_tools.record_candidate(driver.archive_tools.parser().parse_args([
            "record", "--archive", str(self.archive), "--candidate-id", name,
            "--source", str(source), "--result", str(path), "--parent", "seed-best",
            "--route", "review", "--role", role, "--mechanism", "executed review checkpoint fixture",
            "--status", "rejected" if failed else "runner_up"]))

    def seed_isolated_comparisons_with_failed_tail(self) -> None:
        """Create four real singleton contracts, then an actual unscored crash."""
        runs = self.workspace / "seed-comparison-runs"
        runs.mkdir()
        parent = None
        for number in range(5):
            failed = number == 4
            name = "comparison-seed-" + str(number)
            source = runs / (name + ".py")
            source.write_text("raise RuntimeError('comparison seed failed')\n" if failed else
                              "print(" + str(number + 10) + ")\n")
            process = subprocess.run([PYTHON, str(source)], capture_output=True, text=True)
            self.assertEqual(process.returncode != 0, failed)
            outcome = {"status": "failed" if failed else "success", "valid": not failed,
                       "candidate_hash": runtime.file_hash(source),
                       "evaluator_hash": "synthetic-evaluator-v1", "workload_hash": "synthetic-workload-v1",
                       "score_model_hash": "synthetic-score-model-v1", "stage": "development",
                       "elapsed_seconds": 0.01, "evaluation": {"config_hash": "seed-config-" + str(number)}}
            if failed:
                outcome["error"] = {"type": "runtime_failure", "phase": "candidate_execution", "message": process.stderr}
            else:
                outcome["score"] = {"kind": "proxy", "metric": "synthetic-output", "direction": "maximize",
                                    "value": int(process.stdout)}
            path = runs / (name + ".json")
            path.write_text(json.dumps(outcome))
            arguments = ["record", "--archive", str(self.archive), "--candidate-id", name,
                         "--source", str(source), "--result", str(path), "--route", "isolated",
                         "--mechanism", "actual singleton comparison with failed execution tail",
                         "--status", "rejected" if failed else "runner_up"]
            if parent:
                arguments += ["--parent", parent]
            driver.archive_tools.record_candidate(driver.archive_tools.parser().parse_args(arguments))
            parent = name

    def assert_failed_comparison_review_retries(self, scenario: str) -> None:
        self.environment["FAKE_SCENARIO"] = scenario
        result = self.start("--max-turns", "5", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIsNone(self.state()["comparison_review_checkpoint"])
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 4)
        first = json.loads((runtime.turn_directory(self.campaign, 5) / "request.json").read_text())
        self.assertEqual(first["review_checkpoints"], {"comparison": {"distinct_observations": 4}})
        self.assertEqual((first["mode"], first["fresh_context"], first["context_refresh_reason"]),
                         ("measure", True, "comparison_isolation"))
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "6")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = json.loads((runtime.turn_directory(self.campaign, 6) / "request.json").read_text())
        self.assertEqual((second["mode"], second["fresh_context"], second["context_refresh_reason"]),
                         ("measure", True, "comparison_isolation"))
        self.assertEqual(second["review_checkpoints"], first["review_checkpoints"])
        self.assertEqual(self.turn_context(6)["comparison_recovery"], self.turn_context(5)["comparison_recovery"])
        self.assertNotIn("resume", self.calls()[5]["argv"])
        self.assertEqual(self.state()["comparison_review_checkpoint"], {"distinct_observations": 4})
        self.assertEqual(self.state()["usage"]["input_tokens"], 50 if scenario == "comparison_retry_429" else 60)

    def assert_unaccepted_pending_delivery_retries(self, scenario: str) -> None:
        self.seed_pending_proposals(1)
        self.environment["FAKE_SCENARIO"] = scenario
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["pending_proposal_exposures"], {})
        first = self.turn_context(1)["development_brief"]["pending_details"]
        self.assertEqual([item["proposal_id"] for item in first], ["p0"])
        self.assertIsNone(first[0]["last_exposed_turn"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.turn_context(2)["development_brief"]["pending_details"], first)
        comparison = self.state()["objective_progress"]["comparison_key"]
        self.assertEqual(self.state()["pending_proposal_exposures"], {comparison: {"p0": 2}})

    def assert_unaccepted_frontier_delivery_retries(self, scenario: str) -> None:
        entries = self.seed_open_branches(3)
        self.environment["FAKE_SCENARIO"] = scenario
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["frontier_exposures"], {})
        self.assertEqual(self.state()["session_turns"], 0)
        self.assertEqual(len([event for event in self.events() if event["event"] == "turn_interrupted"]), 1)
        first = self.turn_context(1)["development_brief"]["review_frontier"]["selection"]
        self.assertEqual([item["candidate_id"] for item in first], [entry["candidate_id"] for entry in entries[:2]])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = self.turn_context(2)["development_brief"]["review_frontier"]["selection"]
        self.assertEqual(second, first)
        comparison = self.state()["objective_progress"]["comparison_key"]
        self.assertEqual(self.state()["frontier_exposures"], {
            comparison: {entry["implementation"]["fingerprint"]: 2 for entry in entries[:2]}})

    def wait_for(self, predicate, timeout: float = 12) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.03)
        self.fail("Timed out waiting for campaign condition")

    def shutdown(self) -> None:
        if not (self.campaign / "state.json").exists():
            return
        runtime.atomic_json(self.campaign / "stop.request.json",
                            {"reason": "test cleanup", "immediate": True, "at": runtime.utc_now()})
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        state = self.state()
        directories = list(self.campaign.glob("turns/*/completion"))
        if state["inflight"]:
            directories.append(runtime.turn_directory(self.campaign, state["inflight"]["number"]))
        for directory in directories:
            request = directory / "request.json"
            if not request.exists():
                continue
            token = json.loads(request.read_text())["token"]
            group = runtime.recorded_group(directory, token)
            runtime.terminate_owned(token, group)
            for identity in runtime.owned_processes(token, worker=True):
                if runtime.process_alive(identity):
                    os.kill(identity["pid"], signal.SIGKILL)
        for role in ("supervisor", "manager"):
            path = self.campaign / (role + ".json")
            if path.exists():
                identity = json.loads(path.read_text())
                if identity["pid"] != os.getpid() and runtime.process_alive(identity):
                    os.kill(identity["pid"], signal.SIGTERM)
        # Detached processes may need a moment to release locks before temp cleanup.
        time.sleep(0.05)

    def test_open_ended_rejects_repeated_claims_of_completion(self) -> None:
        self.environment["FAKE_SCENARIO"] = "claim_complete"
        result = self.start("--max-turns", "12")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(state["status"], "limit_reached")
        self.assertEqual(state["turn_number"], 12)
        self.assertEqual(state["progress"]["executed_implementations"], 12)
        self.assertEqual(len(self.calls()), 12)
        self.assertNotIn("resume", self.calls()[1]["argv"])
        self.assertIn("fresh-context", self.calls()[1]["prompt"])

    def test_claimed_blocker_is_advisory_and_does_not_end_search(self) -> None:
        self.environment["FAKE_SCENARIO"] = "claim_blocked"
        result = self.start("--max-turns", "5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(len(self.calls()), 5)

    def test_turn_seals_instruction_resources_and_keeps_provenance_out_of_candidate_contract(self) -> None:
        self.seed_open_branches(2)
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        request = json.loads((self.campaign / "turns/000001/request.json").read_text())
        snapshot = request["instruction_snapshot"]
        root = Path(snapshot["skill_root"])
        self.assertEqual(request["workflow_provenance"], state["workflow_provenance"])
        self.assertIn(str(root / "SKILL.md"), self.calls()[0]["prompt"])
        self.assertIn(str(root / "scripts/candidate_archive.py"), self.calls()[0]["prompt"])
        self.assertEqual((root / "SKILL.md").read_bytes(), (SCRIPTS.parent / "SKILL.md").read_bytes())
        catalog = Path("references/cases-top10.tsv")
        self.assertEqual((root / catalog).read_bytes(), (SCRIPTS.parent / catalog).read_bytes())
        manifest = json.loads(Path(snapshot["manifest_path"]).read_text())
        self.assertEqual(manifest["files"][catalog.as_posix()], runtime.file_hash(root / catalog))
        self.assertEqual(state["protected_files"][str(root / catalog)], manifest["files"][catalog.as_posix()])
        provenance = request["workflow_provenance"]
        self.assertEqual(provenance["freezer_sha256"], manifest["files"]["scripts/campaign_workflow.py"])
        requirements = SCRIPTS / "requirements-tabular.txt"
        if requirements.exists():
            self.assertEqual((root / "scripts/requirements-tabular.txt").read_bytes(), requirements.read_bytes())
        comparison = request["context"]["objective_progress"]["comparison"]
        self.assertNotIn("workflow_provenance", comparison)
        reference = root / catalog
        reference.write_bytes(reference.read_bytes() + b"\n")
        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(resumed.returncode, 2, resumed.stderr + resumed.stdout)
        self.assertEqual(len(self.calls()), 1)
        self.assertIn(str(reference), self.state()["stop_reason"])

    def test_normal_turns_resume_the_exact_session_and_record_usage(self) -> None:
        result = self.start("--max-turns", "3", "--model", "mock-model")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        calls = self.calls()
        self.assertIn("-C", calls[0]["argv"])
        self.assertEqual(calls[1]["argv"][:2], ["exec", "resume"])
        self.assertIn("test-thread-1", calls[1]["argv"])
        self.assertIn("mock-model", calls[1]["argv"])
        self.assertEqual(self.state()["usage"], {
            "input_tokens": 30, "cached_input_tokens": 9, "output_tokens": 6})
        self.assertFalse(json.loads(result.stdout)["allow_network"])

    def test_authorized_network_uses_native_workspace_profile_across_resume(self) -> None:
        invalid = self.start("--allow-network", "--sandbox", "read-only", "--max-turns", "1")
        self.assertEqual(invalid.returncode, 2)
        self.assertFalse(self.campaign.exists())

        first = self.start("--allow-network", "--max-turns", "1")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(json.loads(first.stdout)["allow_network"])
        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        sealed, successor = [call["argv"] for call in self.calls()]
        self.assertEqual(successor[:2], ["exec", "resume"])
        self.assertIn("--add-dir", sealed)
        for command in (sealed, successor):
            self.assertNotIn("--sandbox", command)
            self.assertIn('default_permissions="competition-research"', command)
            self.assertIn('permissions.competition-research.extends=":workspace"', command)
            self.assertIn("permissions.competition-research.network.enabled=true", command)

    def test_work_accepts_cited_observation_without_fork_or_research_credit(self) -> None:
        self.environment["FAKE_SCENARIO"] = "descriptive_finding"
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(state["working_selection"]["candidate_id"], "candidate-1")
        self.assertIsNone(state["research_state"])
        self.assertEqual(state["research_findings"], {})
        completed = [row for row in self.events() if row["event"] == "turn_completed"]
        self.assertEqual(len(completed), 1)
        self.assertNotIn("research_finding_sha256", completed[0])
        self.assertFalse((self.campaign / "fake-receipt-calls.jsonl").exists())

    def test_missing_receipt_is_delivered_once_without_repeating_the_experiment(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(state["status"], "limit_reached")
        self.assertEqual(state["progress"]["evaluated_candidates"], 1)
        self.assertEqual(state["session_turns"], 1)
        self.assertEqual(state["session_id"], "test-thread-1")
        self.assertEqual(state["usage"]["input_tokens"], 15)
        self.assertEqual(state["usage"]["output_tokens"], 3)
        self.assertEqual(len(self.calls()), 1)
        delivery = [json.loads(row) for row in (self.campaign / "fake-receipt-calls.jsonl").read_text().splitlines()]
        self.assertEqual(len(delivery), 1)
        self.assertEqual(delivery[0]["argv"][:2], ["exec", "fork"])
        self.assertEqual(delivery[0]["argv"][-2:], ["test-thread-1", "-"])
        self.assertIn("No tool work is requested", delivery[0]["prompt"])
        original = runtime.turn_directory(self.campaign, 1)
        self.assertTrue((original / "message.json").read_text().startswith("Composing the receipt"))
        self.assertEqual(json.loads((original / "exit.json").read_text())["outputs"], runtime.output_hashes(original))
        self.assertEqual(state["research_state"]["receipt_path"], str(original / "receipt/message.json"))
        self.assertEqual(state["research_state"]["report"]["status"], "open")
        self.assertFalse(any(row["event"] == "turn_interrupted" for row in self.events()))
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.calls()[1]["argv"][-2:], ["test-thread-1", "-"])
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 2)

    def test_failed_receipt_delivery_falls_back_without_recursive_formatting_retries(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt_invalid"
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 1)
        self.assertEqual(self.state()["session_turns"], 0)
        self.assertTrue(self.state()["recovery_needed"])
        self.assertEqual(len((self.campaign / "fake-receipt-calls.jsonl").read_text().splitlines()), 1)
        self.assertEqual(len([row for row in self.events() if row["event"] == "turn_interrupted"]), 1)

    def test_archive_change_during_receipt_delivery_is_rejected_without_claiming_quarantine(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt_archive_change"
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 1)
        self.assertIn("Archive changed during receipt delivery", self.state()["last_error"])
        self.assertNotIn("quarantined", self.state()["last_error"])
        self.assertEqual(self.state()["session_turns"], 0)

    def test_token_limit_prevents_starting_receipt_delivery(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt"
        result = self.start("--max-tokens", "12")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 1)
        self.assertFalse((self.campaign / "fake-receipt-calls.jsonl").exists())

    def test_receipt_delivery_keeps_the_original_turn_deadline(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt_hold"
        result = self.start("--max-turns", "1", "--turn-timeout-seconds", "1.5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        original = runtime.turn_directory(self.campaign, 1)
        work = json.loads((original / "request.json").read_text())
        delivery = json.loads((original / "receipt/request.json").read_text())
        self.assertEqual(delivery["started_unix"], work["started_unix"])
        self.assertEqual(delivery["timeout_seconds"], work["timeout_seconds"])
        self.assertIn("watchdog expired", self.state()["last_error"])
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 1)
        self.assertEqual(len(self.calls()), 1)

    def test_provider_prose_receipts_accept_completed_work_without_retries(self) -> None:
        self.environment["FAKE_SCENARIO"] = "prose_receipt"
        result = self.start("--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(self.calls()), 3)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 3)
        completed = [e for e in self.events() if e["event"] == "turn_completed"]
        self.assertEqual(len(completed), 3)
        self.assertFalse(any(e["event"] == "turn_interrupted" for e in self.events()))
        message = self.campaign / "turns/000001/message.json"
        self.assertTrue(message.read_text().startswith("All work is recorded."))

    def test_distinct_but_worse_implementations_trigger_periodic_strategy_reviews(self) -> None:
        self.environment["FAKE_SCENARIO"] = "regress"
        result = self.start("--max-turns", "10", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        calls = self.calls()
        self.assertEqual([call["number"] for call in calls if "resume" not in call["argv"]], [1, 6, 10])
        state = self.state()
        self.assertEqual(state["status"], "limit_reached")
        self.assertEqual(state["progress"]["executed_implementations"], 10)
        self.assertEqual(state["turns_without_implementation"], 0)
        self.assertEqual(state["objective_progress"]["best_candidate"], "candidate-1")
        self.assertEqual(state["objective_progress"]["best_value"], 99)
        self.assertEqual(state["objective_progress"]["implementations_since_best"], 9)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["turn"] for event in prepared
                          if event["context_refresh_reason"] == "objective_stagnation"], [6, 10])
        context_path = self.campaign / "turns" / "000006" / "context.json"
        context = json.loads(context_path.read_text())
        self.assertIn(context_path.read_text().strip(), calls[5]["prompt"])
        self.assertEqual(context["development_brief"]["best_development"], "candidate-1")
        self.assertIn("candidate-1", context["development_brief"]["candidates"])
        self.assertEqual(context["objective_progress"]["comparable_implementations"], 5)
        self.assertEqual(context["archive_snapshot"], json.loads(
            context_path.with_name("request.json").read_text())["archive_before"])

    def test_context_rotation_preserves_improving_history_and_continuation(self) -> None:
        result = self.start("--max-turns", "6", "--session-checkpoints", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 3, 5])
        state = self.state()
        self.assertEqual(state["context_refreshes"], 2)
        self.assertEqual(state["session_turns"], 2)
        self.assertEqual(state["context_refresh_reason"], "scheduled_rotation")
        self.assertEqual(state["objective_progress"]["best_candidate"], "candidate-6")
        self.assertEqual(state["objective_progress"]["implementations_since_best"], 0)
        self.assertEqual(state["progress"]["executed_implementations"], 6)
        self.assertEqual(state["usage"]["input_tokens"], 60)
        for event in self.events():
            if event["event"] == "turn_prepared":
                self.assertEqual(event["mode"], "work")

    def test_review_frontier_rotates_old_low_score_branches_across_checkpoints_and_resume(self) -> None:
        entries = self.seed_open_branches()
        result = self.start("--max-turns", "2", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        contexts = [self.turn_context(number) for number in (1, 2, 3)]
        selections = [context["development_brief"]["review_frontier"]["selection"] for context in contexts]
        self.assertEqual([[item["candidate_id"] for item in selection] for selection in selections], [
            ["seed-open-0", "seed-open-1"], ["seed-open-2", "seed-open-3"], ["seed-open-4", "seed-open-0"]])
        self.assertEqual([[item["last_exposed_turn"] for item in selection] for selection in selections], [
            [None, None], [None, None], [None, 1]])
        for context, selection in zip(contexts, selections):
            brief = context["development_brief"]
            self.assertEqual(brief["best_development"], "seed-best")
            self.assertEqual(context["objective_progress"]["best_candidate"], "seed-best")
            self.assertEqual(brief["candidates"]["seed-best"]["objective"]["value"], 1000)
            for item in selection:
                card = brief["candidates"][item["candidate_id"]]
                self.assertEqual(card["implementation"]["fingerprint"], item["implementation_fingerprint"])
                self.assertEqual(card["identity_checks"], {"result_bytes": "checked", "snapshot_bytes": "checked"})
        self.assertNotIn("seed-open-0", [route["route"] for route in contexts[0]["development_brief"]["routes"]])
        state = self.state()
        comparison = state["objective_progress"]["comparison_key"]
        self.assertEqual(state["frontier_exposures"], {comparison: {
            entry["implementation"]["fingerprint"]: turn
            for entry, turn in zip(entries[:5], (3, 1, 2, 2, 3))}})
        self.assertEqual(state["objective_progress"]["best_value"], 1000)
        self.assertEqual(state["session_turns"], 3)
        self.assertEqual(len(self.calls()), 3)

    def test_review_frontier_nonzero_exit_does_not_consume_delivery(self) -> None:
        self.assert_unaccepted_frontier_delivery_retries("receipt_then_fail")

    def test_review_frontier_invalid_receipt_does_not_consume_delivery(self) -> None:
        self.assert_unaccepted_frontier_delivery_retries("invalid_receipt")

    def test_pending_proposals_rotate_after_success_with_durable_legacy_handoff(self) -> None:
        proposals = self.seed_pending_proposals()
        args = driver.parser().parse_args(self.start_args("--max-turns", "1", "--session-checkpoints", "0"))
        driver.new_campaign(args)
        legacy = self.state()
        legacy.pop("pending_proposal_exposures")
        runtime.atomic_json(self.campaign / "state.json", legacy)
        state = driver.read_state(self.campaign)
        self.assertEqual(state["pending_proposal_exposures"], {})
        driver.prepare_turn(self.campaign, state)
        turn = state["inflight"]
        self.assertEqual(turn["pending_proposal_exposure"]["proposals"], ["p0", "p1", "p2", "p3"])
        self.assertEqual(self.state()["pending_proposal_exposures"], {})
        directory = driver.materialize_request(self.campaign, turn)
        original = (directory / "context.json").read_bytes()
        (directory / "context.json").unlink()
        driver.materialize_request(self.campaign, driver.read_state(self.campaign)["inflight"])
        self.assertEqual((directory / "context.json").read_bytes(), original)
        self.assertEqual(self.state()["pending_proposal_exposures"], {})
        result = self.call("resume", "--campaign", str(self.campaign))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        comparison = self.state()["objective_progress"]["comparison_key"]
        self.assertEqual(self.state()["pending_proposal_exposures"], {
            comparison: {"p" + str(number): 1 for number in range(4)}})
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        contexts = [self.turn_context(number) for number in (1, 2)]
        self.assertEqual([[item["proposal_id"] for item in context["development_brief"]["pending_details"]]
                          for context in contexts], [["p0", "p1", "p2", "p3"], ["p4", "p5", "p6", "p0"]])
        for context in contexts:
            brief = context["development_brief"]
            self.assertEqual(brief["pending_proposals"], ["p" + str(number) for number in range(7)])
            self.assertEqual((brief["pending_summary"]["available"], brief["pending_summary"]["omitted"]), (7, 3))
            self.assertEqual(brief["pending_summary"]["selection_policy"], "least_recently_exposed")
            self.assertEqual(brief["best_development"], "seed-best")
            for detail in brief["pending_details"]:
                proposal = proposals[int(detail["proposal_id"][1:])]
                self.assertEqual(detail["input_sha256"], proposal["input_sha256"])
                self.assertEqual(detail["identity_checks"], {"code_targets": "checked"})
        self.assertEqual([item["last_exposed_turn"] for item in contexts[1]["development_brief"]["pending_details"]],
                         [None, None, None, 1])
        self.assertEqual(self.state()["pending_proposal_exposures"], {
            comparison: {"p" + str(number): 2 if number in {0, 4, 5, 6} else 1 for number in range(7)}})
        self.assertEqual(self.state()["objective_progress"]["best_value"], 1000)
        self.assertEqual(len(self.calls()), 2)

    def test_pending_nonzero_exit_does_not_consume_delivery(self) -> None:
        self.assert_unaccepted_pending_delivery_retries("receipt_then_fail")

    def test_pending_invalid_receipt_does_not_consume_delivery(self) -> None:
        self.assert_unaccepted_pending_delivery_retries("invalid_receipt")

    def test_completed_trials_keep_related_context_and_rotate_old_experiments_across_resume(self) -> None:
        completed = self.seed_completed_trials()
        prefix = self.archive.read_bytes()
        result = self.start("--max-turns", "2", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        contexts = [self.turn_context(number) for number in range(1, 5)]
        selections = [context["trial_history"]["selection"] for context in contexts]
        self.assertEqual([[item["proposal_id"] for item in selection] for selection in selections], [
            ["trial-related", "trial-global-" + str(number)] for number in range(4)])
        for turn, (context, selection) in enumerate(zip(contexts, selections), 1):
            history = context["trial_history"]
            self.assertEqual((history["available"], history["omitted"]), (5, 3))
            context_path = runtime.turn_directory(self.campaign, turn) / "context.json"
            self.assertIn(context_path.read_text().strip(), self.calls()[turn - 1]["prompt"])
            request = json.loads(context_path.with_name("request.json").read_text())
            self.assertEqual(runtime.file_hash(context_path), request["context_sha256"])
            self.assertLessEqual(context_path.stat().st_size, 48 * 1024)
            self.assertEqual(context["development_brief"]["pending_proposals"], [])
            for item in selection:
                original = completed[item["proposal_id"]]
                self.assertEqual(item["input_sha256"], original["proposal"]["input_sha256"])
                self.assertEqual(item["change"], original["proposal"]["change"])
                self.assertEqual(item["expected_observation"], original["proposal"]["expected_observation"])
                self.assertEqual(item["candidate_id"], original["outcome"]["candidate_id"])
                self.assertIn(original["outcome"]["feedback"], json.dumps(item, ensure_ascii=False))
                self.assertRegex(item["retrieval_sha256"], r"^[0-9a-f]{64}$")
                self.assertIn(item["retrieval_sha256"], self.calls()[turn - 1]["prompt"])
                self.assertIn(item["change"], self.calls()[turn - 1]["prompt"])
                self.assertIn(item["expected_observation"], self.calls()[turn - 1]["prompt"])
                for card in item["evidence"].values():
                    self.assertEqual(runtime.file_hash(Path(card["result"]["result_path"])),
                                     card["result"]["result_sha256"])
                    self.assertEqual(driver.archive_tools.hash_path(Path(card["artifact_paths"]["source"])),
                                     card["implementation"]["artifacts"]["source"])
                    self.assertEqual(card["identity_checks"], {
                        "result_bytes": "checked", "snapshot_bytes": "checked"})
            self.assertEqual(selection[0]["retrieval_reason"], "recent_related")
            self.assertEqual(selection[1]["retrieval_reason"], "least_recently_exposed")
            self.assertEqual(selection[0]["last_exposed_turn"], turn - 1 if turn > 1 else None)
            self.assertIsNone(selection[1]["last_exposed_turn"])
        comparison = contexts[0]["trial_history"]["comparison_key"]
        self.assertEqual(self.state()["trial_exposures"], {comparison: {
            "trial-related": 4, **{"trial-global-" + str(number): number + 1 for number in range(4)}}})
        self.assertTrue(self.archive.read_bytes().startswith(prefix))
        trace = driver.archive_tools.trace_report(driver.archive_tools.parser().parse_args([
            "trace", "--archive", str(self.archive), "--all"]))
        self.assertEqual(trace["pending_proposals"], [])
        self.assertEqual([row["state"] for row in trace["iterations"]], ["evaluated_valid"] * 5)

    def test_completed_trial_exposure_waits_for_success_after_429_and_invalid_receipt(self) -> None:
        self.seed_completed_trials()
        self.environment["FAKE_SCENARIO"] = "trial_failures"
        for number in range(1, 4):
            result = self.start("--max-turns", "1", "--session-checkpoints", "0") if number == 1 else self.call(
                "resume", "--campaign", str(self.campaign), "--max-turns", str(number))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            if number < 3:
                self.assertEqual(self.state()["trial_exposures"], {})
                self.assertEqual(self.state()["session_turns"], 0)
        selections = [self.turn_context(number)["trial_history"]["selection"] for number in (1, 2, 3)]
        self.assertEqual(selections[1], selections[0])
        self.assertEqual(selections[2], selections[0])
        comparison = self.turn_context(3)["trial_history"]["comparison_key"]
        self.assertEqual(self.state()["trial_exposures"], {comparison: {"trial-related": 3, "trial-global-0": 3}})
        self.assertEqual(len([event for event in self.events() if event["event"] == "turn_interrupted"]), 2)
        self.assertEqual(len([event for event in self.events() if event["event"] == "turn_completed"]), 1)

    def test_completed_trial_delivery_defaults_old_state_and_accepts_old_inflight_request(self) -> None:
        self.seed_completed_trials()
        args = driver.parser().parse_args(self.start_args("--max-turns", "1", "--session-checkpoints", "0"))
        driver.new_campaign(args)
        legacy = self.state()
        legacy.pop("trial_exposures")
        runtime.atomic_json(self.campaign / "state.json", legacy)
        state = driver.read_state(self.campaign)
        self.assertEqual(state["trial_exposures"], {})
        driver.prepare_turn(self.campaign, state)
        turn = state["inflight"]
        comparison = turn["context"]["trial_history"]["comparison_key"]
        self.assertEqual(turn["trial_exposure"], {
            "comparison_key": comparison, "proposals": ["trial-related", "trial-global-0"]})
        self.assertEqual(self.state()["trial_exposures"], {})
        # An old durable request has no exposure intent, so accepting its
        # successful receipt cannot manufacture a past delivery checkpoint.
        turn.pop("trial_exposure")
        driver.save_state(self.campaign, state)
        directory = driver.materialize_request(self.campaign, turn)
        original = (directory / "context.json").read_bytes()
        (directory / "context.json").unlink()
        driver.materialize_request(self.campaign, driver.read_state(self.campaign)["inflight"])
        self.assertEqual((directory / "context.json").read_bytes(), original)
        self.assertEqual(self.state()["trial_exposures"], {})
        result = self.call("resume", "--campaign", str(self.campaign))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["trial_exposures"], {})
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.turn_context(1)["trial_history"]["selection"],
                         self.turn_context(2)["trial_history"]["selection"])
        self.assertEqual(self.state()["trial_exposures"], {
            comparison: {"trial-related": 2, "trial-global-0": 2}})

    def test_four_low_score_diagnostic_ablations_do_not_consume_candidate_stagnation(self) -> None:
        self.environment["FAKE_SCENARIO"] = "diagnostic_ablations"
        result = self.start("--max-turns", "6", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared],
                         ["work", "work", "work", "rethink", "research", "rethink"])
        self.assertNotIn("objective_stagnation", [event["context_refresh_reason"] for event in prepared])
        context = self.turn_context(6)
        self.assertEqual(context["objective_progress"]["anchor_candidate"], "candidate-1")
        self.assertEqual(context["objective_progress"]["best_value"], 8)
        self.assertEqual(context["objective_progress"]["comparable_implementations"], 1)
        self.assertEqual(context["objective_progress"]["implementations_since_best"], 0)
        self.assertFalse(context["execution_health"]["needs_attention"])
        self.assertEqual(context["execution_health"]["execution_attempts"], 5)
        self.assertEqual(context["comparison_continuity"]["distinct_observations"], 1)
        brief = context["development_brief"]
        diagnostics = brief["diagnostic_evidence"]
        self.assertEqual((diagnostics["available"], diagnostics["omitted"]), (4, 2))
        self.assertEqual(len(diagnostics["selection"]), 2)
        self.assertTrue(set(diagnostics["selection"]) <= {"candidate-" + str(number) for number in range(2, 6)})
        for candidate_id in diagnostics["selection"]:
            card = brief["candidates"][candidate_id]
            self.assertEqual(card["role"], "diagnostic")
            self.assertEqual(card["objective"]["value"], 7)
            self.assertIsNone(card.get("objective_gain_vs_best"))
            self.assertIn("Diagnostic feature contribution", card["feedback"])
            self.assertEqual(runtime.file_hash(Path(card["result"]["result_path"])), card["result"]["result_sha256"])
            source = Path(card["artifact_paths"]["source"])
            self.assertEqual(driver.archive_tools.hash_path(source), card["implementation"]["artifacts"]["source"])
            self.assertIn("predictions=[int(any(row[i] for i in enabled))", source.read_text())
            self.assertIn(card["feedback"], self.calls()[5]["prompt"])
            self.assertIn(str(source), self.calls()[5]["prompt"])
        sealed = runtime.turn_directory(self.campaign, 6) / "context.json"
        self.assertIn(sealed.read_text().strip(), self.calls()[5]["prompt"])
        self.assertLessEqual(sealed.stat().st_size, 48 * 1024)
        state = self.state()
        self.assertEqual(state["progress"]["diagnostic_evaluations"], 4)
        self.assertEqual(state["progress"]["executed_implementations"], 6)
        self.assertEqual(state["objective_progress"]["comparable_implementations"], 2)
        self.assertEqual(state["objective_progress"]["implementations_since_best"], 1)

    def test_failed_diagnostic_takes_priority_over_existing_candidate_stagnation(self) -> None:
        self.seed_open_branches(0)
        for number in range(4):
            self.seed_review_attempt(number, failed=False)
        failed = self.seed_review_attempt(99, failed=True, role="diagnostic")
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.start("--max-turns", "1", "--session-checkpoints", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        first = json.loads((runtime.turn_directory(self.campaign, 1) / "request.json").read_text())
        self.assertEqual((first["mode"], first["context_refresh_reason"]), ("repair", "initial"))
        self.assertTrue(first["context"]["execution_health"]["needs_attention"])
        self.assertEqual(first["context"]["execution_recovery"]["target"]["candidate_id"], failed["candidate_id"])
        self.assertEqual(first["context"]["objective_progress"]["implementations_since_best"], 4)
        self.assertEqual(first["review_checkpoints"], {})
        self.assertEqual(self.state()["next_mode"], "repair")
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual((second["mode"], second["fresh_context"], second["context_refresh_reason"]),
                         ("repair", True, "scheduled_rotation"))
        self.assertEqual(second["review_checkpoints"], {})
        self.assertEqual(self.state()["next_mode"], "repair")
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        self.assertIn("candidate_execution", self.calls()[1]["prompt"])
        self.assertNotIn("fresh-context strategy review", self.calls()[1]["prompt"])

    def test_idle_repair_keeps_fresh_reviews_with_periodic_rotation_disabled(self) -> None:
        self.seed_open_branches(0)
        self.seed_review_attempt(99, failed=True, role="diagnostic")
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.start("--max-turns", "5", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["repair"] * 5)
        self.assertEqual([event["turn"] for event in prepared if event["fresh_context"]], [1, 3, 5])
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 3, 5])
        self.assertEqual(self.state()["turns_without_implementation"], 5)
        self.assertEqual(self.state()["next_mode"], "repair")
        self.assertTrue(self.state()["execution_health"]["needs_attention"])
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        self.assertIsNone(self.state()["execution_review_checkpoint"])
        self.assertNotIn("scheduled_rotation", [event["context_refresh_reason"] for event in prepared])

    def test_new_failed_diagnostic_defers_strategy_review_until_repair_succeeds(self) -> None:
        self.seed_open_branches(0)
        for number in range(3):
            self.seed_review_attempt(number, failed=False)
        self.environment["FAKE_SCENARIO"] = "diagnostic_on_stagnation"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(self.state()["execution_health"]["needs_attention"])
        self.assertEqual(self.state()["objective_progress"]["implementations_since_best"], 4)
        self.assertEqual(self.state()["next_mode"], "repair")
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        repair = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual(repair["mode"], "repair")
        self.assertNotIn("strategy", repair["review_checkpoints"])
        self.assertEqual(repair["context"]["execution_recovery"]["target"]["candidate_id"], "stagnation-diagnostic")
        self.assertFalse(self.state()["execution_health"]["needs_attention"])
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        third = json.loads((runtime.turn_directory(self.campaign, 3) / "request.json").read_text())
        self.assertEqual((third["mode"], third["fresh_context"], third["context_refresh_reason"]),
                         ("rethink", True, "objective_stagnation"))
        self.assertIsNone(third["context"]["execution_recovery"])
        self.assertEqual(third["review_checkpoints"]["strategy"]["comparable_implementations"], 6)
        self.assertEqual(len(self.state()["strategy_review_checkpoints"]), 1)
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "seed-best")

    def test_failed_diagnostic_enters_repair_while_real_candidate_regressions_still_trigger_review(self) -> None:
        self.environment["FAKE_SCENARIO"] = "diagnostic_failure"
        result = self.start("--max-turns", "7", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared],
                         ["work", "work", "repair", "work", "work", "work", "rethink"])
        self.assertEqual([event["turn"] for event in prepared
                          if event["context_refresh_reason"] == "objective_stagnation"], [7])
        repair = self.turn_context(3)
        self.assertTrue(repair["execution_health"]["needs_attention"])
        self.assertEqual(repair["objective_progress"]["anchor_candidate"], "candidate-1")
        self.assertEqual(repair["objective_progress"]["comparable_implementations"], 1)
        target = repair["execution_recovery"]["target"]
        self.assertEqual(target["candidate_id"], "candidate-2")
        self.assertEqual(target["diagnostic"]["error"]["phase"], "candidate_execution")
        self.assertIn("candidate failed 2", target["diagnostic"]["error"]["message"])
        self.assertEqual(runtime.file_hash(Path(target["result_path"])), target["result_sha256"])
        self.assertEqual(driver.archive_tools.hash_path(Path(target["artifact_paths"]["source"])),
                         target["implementation"]["artifacts"]["source"])
        self.assertIn("candidate failed 2", self.calls()[2]["prompt"])
        review = self.turn_context(7)
        self.assertEqual(review["objective_progress"]["comparable_implementations"], 5)
        self.assertEqual(review["objective_progress"]["implementations_since_best"], 4)
        self.assertFalse(review["execution_health"]["needs_attention"])
        self.assertEqual(self.state()["progress"]["diagnostic_evaluations"], 1)

    def test_diagnostics_skip_automatic_completion_but_candidates_and_explicit_requests_still_check(self) -> None:
        self.seed_open_branches(0)
        checker = self.workspace / "diagnostic-completion-check.py"
        checker.write_text(
            "import argparse,json,pathlib\n"
            "p=argparse.ArgumentParser(); p.add_argument('--workspace'); p.add_argument('--archive'); a=p.parse_args()\n"
            "path=pathlib.Path(a.workspace)/'completion-invocations.jsonl'\n"
            "with path.open('a') as f: f.write(json.dumps({'archive':a.archive})+'\\n')\n"
            "print(json.dumps({'complete':False,'reason':'fixture requests more work','evidence':[a.archive]}))\n")
        invocations = self.workspace / "completion-invocations.jsonl"
        self.environment["FAKE_SCENARIO"] = "diagnostic_only"
        result = self.start("--max-turns", "2", "--session-checkpoints", "0", "--completion-check", str(checker))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(invocations.exists())
        self.assertEqual(self.state()["progress"]["diagnostic_evaluations"], 2)
        self.environment["FAKE_SCENARIO"] = ""
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(invocations.read_text().splitlines()), 1)
        self.environment["FAKE_SCENARIO"] = "diagnostic_claim_complete"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(invocations.read_text().splitlines()), 2)
        self.assertEqual(self.state()["last_agent_status"], "complete")
        self.assertEqual(self.state()["progress"]["diagnostic_evaluations"], 3)
        self.assertEqual(self.state()["status"], "limit_reached")

    def test_failed_cli_cannot_consume_an_execution_review_before_successful_receipt(self) -> None:
        self.seed_open_branches(0)
        for number in range(3):
            self.seed_review_attempt(number, failed=True)
        self.environment["FAKE_SCENARIO"] = "review_once_429"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIsNone(self.state()["execution_review_checkpoint"])
        self.assertEqual(self.state()["execution_health"]["execution_attempts"], 4)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([(event["mode"], event["fresh_context"], event["context_refresh_reason"])
                          for event in prepared], [("repair", True, "execution_stagnation")] * 2)
        self.assertNotIn("resume", self.calls()[1]["argv"])
        self.assertEqual(self.state()["execution_review_checkpoint"], {
            "execution_attempts": 4, "last_scored_candidate": "seed-best"})
        for number in (1, 2):
            request = json.loads((runtime.turn_directory(self.campaign, number) / "request.json").read_text())
            self.assertEqual(request["review_checkpoints"], {"execution": {
                "execution_attempts": 4, "last_scored_candidate": "seed-best"}})
        self.assertEqual(self.state()["session_turns"], 1)

    def test_failed_cli_cannot_consume_an_objective_review_before_successful_receipt(self) -> None:
        self.seed_open_branches(0)
        self.seed_review_attempt(0, failed=False)
        self.environment["FAKE_SCENARIO"] = "review_once_429"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0", "--stagnation-window", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        comparison = self.state()["objective_progress"]["comparison_key"]
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([(event["mode"], event["fresh_context"], event["context_refresh_reason"])
                          for event in prepared], [("rethink", True, "objective_stagnation")] * 2)
        self.assertNotIn("resume", self.calls()[1]["argv"])
        self.assertEqual(self.state()["strategy_review_checkpoints"], {comparison: {
            "comparison_key": comparison, "best_candidate": "seed-best", "comparable_implementations": 2}})
        for number in (1, 2):
            request = json.loads((runtime.turn_directory(self.campaign, number) / "request.json").read_text())
            self.assertEqual(request["review_checkpoints"], {"strategy": {
                "comparison_key": comparison, "best_candidate": "seed-best", "comparable_implementations": 2}})

    def test_singleton_comparisons_request_measurement_after_four_valid_observations(self) -> None:
        self.environment["FAKE_SCENARIO"] = "comparison_drift"
        result = self.start("--max-turns", "6", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["work"] * 4 + ["measure", "work"])
        review = prepared[4]
        self.assertEqual((review["fresh_context"], review["context_refresh_reason"]),
                         (True, "comparison_isolation"))
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 5])
        context = self.turn_context(5)
        continuity = context["comparison_continuity"]
        self.assertEqual((continuity["distinct_observations"], continuity["unpaired_contracts"],
                          continuity["new_unpaired_contracts"]), (4, 4, 4))
        recovery = context["comparison_recovery"]
        self.assertEqual(recovery["target"]["candidate_id"], "candidate-4")
        self.assertEqual(recovery["reference"]["candidate_id"], "candidate-3")
        self.assertEqual(recovery["changed_fields"], ["config_hash"])
        for name in ("target", "reference"):
            card = recovery[name]
            self.assertEqual(runtime.file_hash(Path(card["result_path"])), card["result_sha256"])
            self.assertEqual(card["identity_checks"], {"result_bytes": "checked", "snapshot_bytes": "checked"})
            self.assertEqual(driver.archive_tools.hash_path(Path(card["artifact_paths"]["source"])),
                             card["implementation"]["artifacts"]["source"])
            self.assertNotIn("objective", card)
            self.assertNotIn("feedback", card)
            self.assertNotIn("cost", card)
        self.assertFalse(context["execution_health"]["needs_attention"])
        self.assertLessEqual(len(driver.archive_tools.canonical(context)) + 1, 48 * 1024)
        self.assertEqual(self.state()["comparison_review_window"], 4)
        self.assertEqual(self.state()["comparison_review_checkpoint"], {"distinct_observations": 4})
        self.assertEqual(self.state()["progress"]["executed_implementations"], 6)
        self.assertEqual(self.state()["turns_without_implementation"], 0)

    def test_repeat_conflict_review_remains_due_without_an_archived_plan(self) -> None:
        self.seed_repeat_conflict()
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 1) / "request.json").read_text())
        self.assertEqual((request["mode"], request["context_refresh_reason"]),
                         ("measure", "repeat_disagreement"))
        context = self.turn_context(1)
        self.assertTrue(search.delivered_repeat_conflict(context))
        self.assertEqual(context["objective_progress"]["best_candidate"], "leader-first")
        self.assertEqual(context["repeat_conflict"]["witness_candidate"], "leader-repeat")
        self.assertEqual(request["review_checkpoints"]["repeat"]["signature"],
                         context["repeat_conflict"]["signature"])
        self.assertIn("repeatability review", self.calls()[0]["prompt"])
        self.assertEqual(self.state()["repeat_review_checkpoints"], {})
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual(second["context_refresh_reason"], "repeat_disagreement")
        self.assertIn("repeat", second["review_checkpoints"])

    def test_interrupted_repeat_review_does_not_consume_its_checkpoint(self) -> None:
        self.seed_repeat_conflict()
        self.environment["FAKE_SCENARIO"] = "review_once_429"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["repeat_review_checkpoints"], {})
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual((second["mode"], second["context_refresh_reason"]),
                         ("measure", "repeat_disagreement"))
        self.assertIn("repeat", second["review_checkpoints"])
        self.assertEqual(self.state()["repeat_review_checkpoints"], {
            second["review_checkpoints"]["repeat"]["comparison_key"]:
                second["review_checkpoints"]["repeat"]["signature"]})
        self.assertEqual(driver.archive_tools.read_records(self.archive)[-1]["event"], "measurement_plan")

    def test_frozen_repeat_plan_survives_turns_and_closes_only_after_both_slots(self) -> None:
        self.seed_repeat_conflict()
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(records[-1]["event"], "measurement_plan")
        plan = records[-1]
        self.assertFalse(driver.archive_tools.measurement_plans.status(plan, records)["complete"])
        self.assertEqual(self.state()["repeat_review_checkpoints"][
            self.turn_context(1)["repeat_conflict"]["comparison_key"]], plan["conflict_signature"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual(second["mode"], "measure")
        self.assertEqual(second["context"]["measurement_plan"]["plan_id"], "paired-repeat")
        records = driver.archive_tools.read_records(self.archive)
        self.assertFalse(driver.archive_tools.measurement_plans.status(plan, records)["complete"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        paired = driver.archive_tools.measurement_plans.status(plan, records)
        self.assertTrue(paired["complete"])
        self.assertEqual((paired["runs"][0]["leader"]["value"], paired["runs"][0]["challenger"]["value"]),
                         (55, 65))
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "leader-first")
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        fourth = json.loads((runtime.turn_directory(self.campaign, 4) / "request.json").read_text())
        self.assertEqual(fourth["mode"], "measure")
        self.assertTrue(fourth["context"]["measurement_plan"]["pairs_complete"])
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(records[-1]["event"], "measurement_decision")
        self.assertIsNone(driver.archive_tools.measurement_plans.first_pending(records))
        self.assertEqual(self.state()["next_action"], records[-1]["next_action"])
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        fifth = json.loads((runtime.turn_directory(self.campaign, 5) / "request.json").read_text())
        self.assertNotEqual(fifth["context_refresh_reason"], "repeat_disagreement")
        self.assertNotEqual(fourth["context_refresh_reason"], "repeat_disagreement")
        self.assertIsNone(fifth["context"]["measurement_plan"])
        carried = fifth["context"]["measurement_decision"]
        self.assertEqual(carried["plan_id"], "paired-repeat")
        self.assertEqual(carried["evidence_sha256"], records[-1]["evidence_sha256"])
        self.assertEqual(carried["conclusion"], records[-1]["conclusion"])
        self.assertTrue(carried["comparison_matches_active"])
        self.assertEqual(fifth["context"]["objective_progress"]["best_candidate"], "leader-first")
        self.assertEqual(self.state()["next_action"], "execute the next mechanism")

    def test_frozen_plan_rotates_contexts_across_resume_without_losing_slots(self) -> None:
        self.seed_repeat_conflict()
        plan = self.freeze_repeat_plan()
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.start("--max-turns", "3", "--session-checkpoints", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        view = driver.archive_tools.measurement_plans.status(plan, records)
        self.assertEqual(len(view["attempts"]), 3)
        self.assertFalse(view["complete"])
        self.assertEqual(self.state()["session_turns"], 1)
        prefix = self.archive.read_bytes()
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "7")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["measure"] * 7)
        self.assertEqual([event["turn"] for event in prepared if event["fresh_context"]], [1, 3, 5, 7])
        self.assertEqual([event["context_refresh_reason"] for event in prepared if event["fresh_context"]],
                         ["initial", "scheduled_rotation", "scheduled_rotation", "scheduled_rotation"])
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 3, 5, 7])
        self.assertTrue(self.archive.read_bytes().startswith(prefix))
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(sum(entry["event"] == "measurement_plan" for entry in records), 1)
        view = driver.archive_tools.measurement_plans.status(plan, records)
        self.assertTrue(view["complete"])
        self.assertEqual(view["state"], "decided")
        self.assertEqual(len(view["attempts"]), 6)
        self.assertEqual(len({(entry["run_id"], entry["implementation"]) for entry in view["attempts"]}), 6)
        self.assertTrue(self.turn_context(7)["measurement_plan"]["pairs_complete"])
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "leader-first")

    def test_frozen_plan_defers_candidate_review_without_repeated_session_recovery(self) -> None:
        self.seed_repeat_conflict()
        plan = self.freeze_repeat_plan()
        self.seed_open_branches(0)
        for number in range(4):
            self.seed_review_attempt(number, failed=False)
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.start("--max-turns", "7", "--session-checkpoints", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["measure"] * 7)
        self.assertEqual([event["turn"] for event in prepared if event["fresh_context"]], [1, 3, 5, 7])
        self.assertEqual([event["context_refresh_reason"] for event in prepared if event["fresh_context"]],
                         ["initial", "scheduled_rotation", "scheduled_rotation", "scheduled_rotation"])
        self.assertEqual(self.state()["strategy_review_checkpoints"], {})
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(driver.archive_tools.measurement_plans.status(plan, records)["state"],
                         "decided")
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "8")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        eighth = json.loads((runtime.turn_directory(self.campaign, 8) / "request.json").read_text())
        self.assertEqual((eighth["mode"], eighth["context_refresh_reason"]), ("rethink", "objective_stagnation"))
        self.assertIsNone(eighth["context"]["measurement_plan"])
        self.assertEqual(len(self.state()["strategy_review_checkpoints"]), 1)

    def test_frozen_plan_can_disable_rotation_without_disabling_initial_context(self) -> None:
        self.seed_repeat_conflict()
        plan = self.freeze_repeat_plan()
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.start("--max-turns", "5", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["measure"] * 5)
        self.assertEqual([event["context_refresh_reason"] for event in prepared if event["fresh_context"]], ["initial"])
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1])
        self.assertEqual(self.state()["session_turns"], 5)
        view = driver.archive_tools.measurement_plans.status(
            plan, driver.archive_tools.read_records(self.archive))
        self.assertEqual(len(view["attempts"]), 5)
        self.assertFalse(view["complete"])

    def test_frozen_plan_recovers_missing_session_without_replanning(self) -> None:
        self.seed_repeat_conflict()
        plan = self.freeze_repeat_plan()
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        state["session_id"] = None
        runtime.atomic_json(self.campaign / "state.json", state)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual((request["mode"], request["fresh_context"], request["context_refresh_reason"]),
                         ("measure", True, "session_recovery"))
        self.assertNotIn("resume", self.calls()[1]["argv"])
        self.assertEqual(request["context"]["measurement_plan"]["plan_id"], plan["plan_id"])
        self.assertEqual(request["context"]["measurement_plan"]["remaining_slots"], 5)
        self.assertEqual(self.state()["session_turns"], 1)

    def test_frozen_plan_rotation_counts_successful_checkpoints_after_cli_failure(self) -> None:
        self.seed_repeat_conflict()
        plan = self.freeze_repeat_plan()
        self.environment["FAKE_SCENARIO"] = "repeat_plan_rotation_429"
        result = self.start("--max-turns", "3", "--session-checkpoints", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["session_turns"], 0)
        self.assertTrue(self.state()["recovery_needed"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "6")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["measure"] * 6)
        self.assertEqual([event["turn"] for event in prepared if event["fresh_context"]], [1, 3, 6])
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 3, 6])
        view = driver.archive_tools.measurement_plans.status(
            plan, driver.archive_tools.read_records(self.archive))
        self.assertEqual(len(view["attempts"]), 5)
        self.assertEqual(len({(entry["run_id"], entry["implementation"]) for entry in view["attempts"]}), 5)
        self.assertFalse(self.state()["recovery_needed"])
        self.assertEqual(self.state()["session_turns"], 1)

    def test_failed_frozen_plan_stops_then_repairs_and_resumes_ordinary_work(self) -> None:
        self.seed_repeat_conflict(seed_failure=True)
        self.environment["FAKE_SCENARIO"] = "repeat_plan_stop"
        result = self.start("--max-turns", "3", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        plan = next(entry for entry in records if entry["event"] == "measurement_plan")
        stopped = records[-1]
        self.assertEqual(stopped["event"], "measurement_stop")
        view = driver.archive_tools.measurement_plans.status(plan, records)
        self.assertEqual(view["state"], "stopped_unresolved")
        self.assertFalse(view["complete"])
        self.assertIsNone(view["decision"])
        self.assertEqual(view["attempts"][0]["execution_status"], "failed")
        self.assertEqual(self.state()["next_action"], stopped["next_action"])
        self.assertTrue(self.state()["execution_health"]["needs_attention"])
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "leader-first")
        frozen_prefix = self.archive.read_bytes()
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        requests = [json.loads((runtime.turn_directory(self.campaign, number) / "request.json").read_text())
                    for number in range(1, 6)]
        self.assertEqual([item["mode"] for item in requests], ["measure", "measure", "repair", "repair", "work"])
        carried = requests[3]["context"]["measurement_stop"]
        self.assertEqual(carried["reason"], stopped["reason"])
        self.assertEqual(carried["next_action"], stopped["next_action"])
        self.assertEqual(carried["evidence_sha256"], stopped["evidence_sha256"])
        self.assertEqual((carried["remaining_slots"], carried["attempts"], carried["failed_attempts"]), (2, 1, 1))
        self.assertTrue(carried["comparison_matches_active"])
        self.assertIsNone(requests[3]["context"]["measurement_plan"])
        self.assertIn("measure-stop", self.calls()[2]["prompt"])
        self.assertFalse(self.state()["execution_health"]["needs_attention"])
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "leader-first")
        records = driver.archive_tools.read_records(self.archive)
        self.assertIsNone(driver.archive_tools.measurement_plans.first_pending(records))
        self.assertEqual(sum(entry["event"] == "measurement_plan" for entry in records), 1)
        self.assertEqual(sum(entry["event"] == "measurement_stop" for entry in records), 1)
        self.assertNotIn("measurement_plan_id", driver.archive_tools.candidate_index(records)["candidate-4"]["result"])
        self.assertTrue(self.archive.read_bytes().startswith(frozen_prefix))
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "6")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        sixth = json.loads((runtime.turn_directory(self.campaign, 6) / "request.json").read_text())
        self.assertEqual(sixth["mode"], "work")
        self.assertNotEqual(sixth["context_refresh_reason"], "repeat_disagreement")
        self.assertEqual(sixth["context"]["measurement_stop"]["plan_id"], plan["plan_id"])
        self.assertEqual(self.state()["next_action"], "execute the next mechanism")

    def test_new_foreign_stop_does_not_override_current_receipt_action(self) -> None:
        self.seed_repeat_conflict(seed_failure=True)
        self.environment["FAKE_SCENARIO"] = "repeat_plan_stop_foreign"
        result = self.start("--max-turns", "3", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        stop = next(entry for entry in records if entry["event"] == "measurement_stop")
        self.assertEqual(self.state()["objective_progress"]["anchor_candidate"], "candidate-3")
        self.assertEqual(self.state()["next_action"], "execute the next mechanism")
        self.assertNotEqual(self.state()["next_action"], stop["next_action"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        carried = self.turn_context(4)["measurement_stop"]
        self.assertFalse(carried["comparison_matches_active"])
        self.assertEqual(carried["evidence_sha256"], stop["evidence_sha256"])
        self.assertIsNone(self.turn_context(4)["measurement_plan"])

    def test_stop_appended_before_interruption_resumes_without_reopening_plan(self) -> None:
        self.seed_repeat_conflict(seed_failure=True)
        self.environment["FAKE_SCENARIO"] = "repeat_plan_stop_interrupt"
        result = self.start("--max-turns", "3", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(records[-1]["event"], "measurement_stop")
        self.assertTrue(self.state()["recovery_needed"])
        self.assertTrue(self.state()["execution_health"]["needs_attention"])
        self.environment["FAKE_SCENARIO"] = "repeat_plan_stop"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        fourth = json.loads((runtime.turn_directory(self.campaign, 4) / "request.json").read_text())
        self.assertEqual(fourth["mode"], "repair")
        self.assertIsNone(fourth["context"]["measurement_plan"])
        self.assertEqual(fourth["context"]["measurement_stop"]["state"], "stopped_unresolved")
        self.assertEqual(self.turn_context(5)["execution_health"]["needs_attention"], False)
        self.assertFalse(self.state()["recovery_needed"])
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(sum(entry["event"] == "measurement_plan" for entry in records), 1)
        self.assertEqual(sum(entry["event"] == "measurement_stop" for entry in records), 1)

    def test_decision_appended_before_interruption_exits_measure_without_acknowledging_delivery(self) -> None:
        self.seed_repeat_conflict()
        self.environment["FAKE_SCENARIO"] = "repeat_plan_decision_interrupt"
        result = self.start("--max-turns", "3", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        before = self.state()
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(records[-1]["event"], "measurement_decision")
        self.assertIsNone(driver.archive_tools.measurement_plans.first_pending(records))
        self.assertTrue(state["recovery_needed"])
        self.assertFalse(state["execution_health"]["needs_attention"])
        self.assertEqual(state["next_mode"], "work")
        self.assertEqual(state["session_turns"], before["session_turns"])
        for key in ("frontier_exposures", "pending_proposal_exposures", "trial_exposures", "learning_exposures",
                    "strategy_review_checkpoints", "repeat_review_checkpoints"):
            self.assertEqual(state[key], before[key])
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        fifth = json.loads((runtime.turn_directory(self.campaign, 5) / "request.json").read_text())
        self.assertEqual(fifth["mode"], "work")
        self.assertIsNone(fifth["context"]["measurement_plan"])
        self.assertEqual(fifth["context"]["measurement_decision"]["evidence_sha256"], records[-1]["evidence_sha256"])
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(sum(entry["event"] == "measurement_decision" for entry in records), 1)

    def test_plan_appended_before_interruption_resumes_without_replanning(self) -> None:
        self.seed_repeat_conflict()
        self.environment["FAKE_SCENARIO"] = "repeat_plan_interrupt"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(records[-1]["event"], "measurement_plan")
        self.assertEqual(self.state()["repeat_review_checkpoints"], {})
        self.environment["FAKE_SCENARIO"] = "repeat_plan"
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        second = json.loads((runtime.turn_directory(self.campaign, 2) / "request.json").read_text())
        self.assertEqual(second["mode"], "measure")
        self.assertEqual(second["context"]["measurement_plan"]["plan_id"], "paired-repeat")
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(sum(entry["event"] == "measurement_plan" for entry in records), 1)
        self.assertEqual(records[-1]["result"]["measurement_plan_id"], "paired-repeat")

    def test_comparison_review_429_retry_preserves_required_fresh_diagnosis(self) -> None:
        self.assert_failed_comparison_review_retries("comparison_retry_429")

    def test_comparison_review_invalid_receipt_does_not_consume_diagnosis(self) -> None:
        self.assert_failed_comparison_review_retries("comparison_retry_receipt")

    def test_comparison_measurement_accepts_existing_code_on_the_frozen_contract(self) -> None:
        self.environment["FAKE_SCENARIO"] = "comparison_pairing"
        result = self.start("--max-turns", "5", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 5) / "request.json").read_text())
        self.assertEqual(request["mode"], "measure")
        records = driver.archive_tools.candidate_index(driver.archive_tools.read_records(self.archive))
        self.assertEqual(records["candidate-5"]["implementation"], records["candidate-3"]["implementation"])
        self.assertEqual(records["candidate-5"]["artifact_paths"], records["candidate-3"]["artifact_paths"])
        self.assertEqual(records["candidate-5"]["comparison"], records["candidate-4"]["comparison"])
        self.assertNotEqual(records["candidate-5"]["comparison"], records["candidate-3"]["comparison"])
        state = self.state()
        self.assertEqual(state["progress"]["evaluated_candidates"], 5)
        self.assertEqual(state["progress"]["executed_implementations"], 4)
        self.assertEqual(state["objective_progress"]["comparable_implementations"], 2)
        self.assertEqual(state["objective_progress"]["best_candidate"], "candidate-4")
        self.assertEqual(state["comparison_review_checkpoint"], {"distinct_observations": 4})
        self.assertEqual(state["usage"]["input_tokens"], 50)
        self.assertEqual(len(self.calls()), 5)

    def test_execution_repair_takes_priority_without_consuming_comparison_review(self) -> None:
        self.seed_isolated_comparisons_with_failed_tail()
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.start("--max-turns", "1", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 1) / "request.json").read_text())
        self.assertEqual(request["mode"], "repair")
        self.assertNotIn("comparison", request["review_checkpoints"])
        self.assertNotEqual(request["context_refresh_reason"], "comparison_isolation")
        self.assertTrue(self.state()["execution_health"]["needs_attention"])
        self.assertIsNone(self.state()["comparison_review_checkpoint"])

    def test_resume_adjusts_comparison_window_and_upgrades_prior_state(self) -> None:
        self.environment["FAKE_SCENARIO"] = "comparison_drift"
        result = self.start("--max-turns", "4", "--session-checkpoints", "0", "--comparison-review-window", "9")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        for key in ("comparison_continuity", "comparison_review_checkpoint", "comparison_review_window"):
            state.pop(key)
        runtime.atomic_json(self.campaign / "state.json", state)
        restored = driver.read_state(self.campaign)
        self.assertEqual(restored["comparison_review_window"], 4)
        self.assertIsNone(restored["comparison_review_checkpoint"])
        self.assertIsNone(restored["comparison_continuity"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "5",
                           "--comparison-review-window", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["comparison_review_window"], 2)
        self.assertEqual(self.state()["comparison_review_checkpoint"], {"distinct_observations": 4})
        self.assertEqual(self.state()["progress"]["executed_implementations"], 5)
        self.assertEqual(self.state()["usage"]["input_tokens"], 50)
        request = json.loads((runtime.turn_directory(self.campaign, 5) / "request.json").read_text())
        self.assertEqual((request["mode"], request["context_refresh_reason"]), ("measure", "comparison_isolation"))
        with self.assertRaises(driver.CampaignError):
            driver.limit_overrides(driver.parser().parse_args(self.start_args("--comparison-review-window", "0")))

    def test_failed_new_implementations_enter_repair_and_get_fresh_reviews(self) -> None:
        self.environment["FAKE_SCENARIO"] = "invalid_forever"
        result = self.start("--max-turns", "8", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["turn"] for event in prepared
                          if event["context_refresh_reason"] == "execution_stagnation"], [5, 8])
        self.assertEqual([event["mode"] for event in prepared], ["work", "work"] + ["repair"] * 6)
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 5, 8])
        state = self.state()
        self.assertEqual(state["status"], "limit_reached")
        self.assertEqual(state["turns_without_implementation"], 0)
        self.assertEqual(state["execution_health"]["attempts_without_observation"], 7)
        self.assertEqual(state["execution_health"]["last_scored_candidate"], "candidate-1")
        context = json.loads((self.campaign / "turns/000005/context.json").read_text())
        recovery = context["execution_recovery"]
        self.assertEqual(recovery["target"]["candidate_id"], "candidate-4")
        self.assertEqual(recovery["target"]["diagnostic"]["error"]["type"], "runtime_failure")
        self.assertIn("candidate failed 4", recovery["target"]["diagnostic"]["error"]["message"])
        self.assertEqual(recovery["reference"]["candidate_id"], "candidate-1")
        self.assertFalse(recovery["reference_comparison_matches"])
        self.assertNotIn("score", recovery["reference"])

    def test_measured_success_exits_repair_without_resetting_historical_accounting(self) -> None:
        self.environment["FAKE_SCENARIO"] = "recover_execution"
        result = self.start("--max-turns", "6", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [event for event in self.events() if event["event"] == "turn_prepared"]
        self.assertEqual([event["mode"] for event in prepared], ["work", "work", "repair", "repair", "repair", "work"])
        self.assertEqual(self.state()["execution_health"]["attempts_without_observation"], 0)
        self.assertEqual(self.state()["execution_health"]["execution_attempts"], 6)
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "candidate-6")
        self.assertEqual(self.state()["usage"]["input_tokens"], 60)
        context = json.loads((self.campaign / "turns/000006/context.json").read_text())
        self.assertIsNone(context["execution_recovery"])

    def test_successful_but_unscored_runs_request_measurement_recovery(self) -> None:
        self.environment["FAKE_SCENARIO"] = "unscored_forever"
        result = self.start("--max-turns", "4", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["execution_health"]["issue"], "unusable_objective")
        self.assertEqual(self.state()["objective_progress"]["comparable_implementations"], 0)
        context = json.loads((self.campaign / "turns/000004/context.json").read_text())
        self.assertEqual(context["execution_recovery"]["target"]["execution_status"], "success")
        self.assertIsNone(context["execution_recovery"]["target"]["diagnostic"]["error"])
        self.assertIsNone(context["execution_recovery"]["reference"])
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 4])

    def test_resume_adjusts_failure_review_window_and_upgrades_prior_state(self) -> None:
        self.environment["FAKE_SCENARIO"] = "invalid_forever"
        self.assertEqual(self.start("--max-turns", "3", "--session-checkpoints", "0").returncode, 0)
        state = self.state()
        for key in ("execution_health", "execution_review_checkpoint", "failure_review_window"):
            state.pop(key)
        runtime.atomic_json(self.campaign / "state.json", state)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "6",
                           "--failure-review-window", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["failure_review_window"], 2)
        self.assertEqual(self.state()["execution_health"]["execution_attempts"], 6)
        self.assertEqual(self.state()["usage"]["input_tokens"], 60)
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 4, 6])

    def test_default_rotation_uses_successful_checkpoints_without_token_usage(self) -> None:
        self.environment["FAKE_NO_USAGE"] = "1"
        result = self.start("--max-turns", "9")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 9])
        self.assertEqual(self.state()["usage"], {})
        self.assertEqual(self.state()["session_turns"], 1)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 9)

    def test_periodic_rotation_can_be_disabled_without_limiting_work(self) -> None:
        result = self.start("--max-turns", "10", "--session-checkpoints", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1])
        self.assertEqual(self.state()["context_refreshes"], 0)
        self.assertEqual(self.state()["session_turns"], 10)

    def test_resume_can_adjust_search_policy_without_resetting_history(self) -> None:
        self.assertEqual(self.start("--max-turns", "2", "--session-checkpoints", "0").returncode, 0)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4",
                           "--session-checkpoints", "2", "--stagnation-window", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual([call["number"] for call in self.calls() if "resume" not in call["argv"]], [1, 3])
        self.assertEqual(self.state()["progress"]["executed_implementations"], 4)
        self.assertEqual(self.state()["usage"]["input_tokens"], 40)
        self.assertEqual(self.state()["stagnation_window"], 3)

    def test_modified_persisted_context_blocks_acceptance(self) -> None:
        self.environment["FAKE_SCENARIO"] = "context_tamper"
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertIn("context was modified", self.state()["stop_reason"])
        self.assertEqual(len(self.calls()), 1)

    def test_recovery_materializes_the_original_context_without_repreparing(self) -> None:
        entries = self.seed_open_branches(3)
        args = driver.parser().parse_args(self.start_args("--max-turns", "1"))
        campaign = driver.new_campaign(args)
        previous_state = self.state()
        previous_state.pop("frontier_exposures")
        previous_state.pop("pending_proposal_exposures")
        runtime.atomic_json(campaign / "state.json", previous_state)
        state = driver.read_state(campaign)
        self.assertEqual(state["frontier_exposures"], {})
        self.assertEqual(state["pending_proposal_exposures"], {})
        driver.prepare_turn(campaign, state)
        turn = state["inflight"]
        # A pre-upgrade in-flight request has no pending or review intent.
        turn.pop("pending_proposal_exposure")
        turn.pop("review_checkpoints")
        driver.save_state(campaign, state)
        directory = runtime.turn_directory(campaign, 1)
        self.assertFalse(directory.exists())
        self.assertEqual(state["frontier_exposures"], {})
        self.assertEqual(self.state()["frontier_exposures"], {})
        fingerprints = [entry["implementation"]["fingerprint"] for entry in entries[:2]]
        self.assertEqual(turn["frontier_exposure"]["implementations"], fingerprints)
        driver.materialize_request(campaign, turn)
        original = (directory / "context.json").read_bytes()
        (directory / "context.json").unlink()
        driver.materialize_request(campaign, driver.read_state(campaign)["inflight"])
        self.assertEqual((directory / "context.json").read_bytes(), original)
        self.assertEqual(self.state()["frontier_exposures"], {})
        result = self.call("resume", "--campaign", str(campaign))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads((directory / "context.json").read_text()), turn["context"])
        self.assertEqual(runtime.file_hash(directory / "context.json"), turn["context_sha256"])
        self.assertEqual(self.state()["session_turns"], 1)
        self.assertEqual(self.state()["context_refreshes"], 0)
        self.assertEqual(self.state()["usage"]["input_tokens"], 10)
        self.assertEqual(self.state()["frontier_exposures"], {
            turn["frontier_exposure"]["comparison_key"]: {fingerprint: 1 for fingerprint in fingerprints}})
        self.assertEqual(len(self.calls()), 1)

    def test_prepared_frontier_exposure_requires_cards_surviving_packet_bounds(self) -> None:
        self.seed_open_branches(3)
        handoff = search.handoff_packet
        cases = ("missing_root", "unchecked_root", "missing_feedback", "missing_successor",
                 "truncated_artifact_path", "truncated_implementation", "truncated_feedback_result",
                 "truncated_successor_result", "truncated_reuse_history", "truncated_feedback_text")
        for case in cases:
            with self.subTest(case=case):
                campaign = self.root / ("bounded-" + case)
                args = driver.parser().parse_args(self.start_args("--max-turns", "1", "--campaign", str(campaign)))
                driver.new_campaign(args)
                state = driver.read_state(campaign)

                def bounded_packet(*args, **kwargs):
                    packet = handoff(*args, **kwargs)
                    brief = packet["development_brief"]
                    first, second = brief["review_frontier"]["selection"]
                    cards = brief["candidates"]
                    root_id = first["candidate_id"]
                    feedback_id, successor_id = root_id + "-feedback", root_id + "-successor"
                    # Use real, verified cards to isolate losses introduced by
                    # packet bounding, including aliases and successor evidence.
                    cards[feedback_id] = deepcopy(cards[root_id])
                    cards[successor_id] = deepcopy(cards[second["candidate_id"]])
                    first["feedback_candidate_id"] = feedback_id
                    first["latest_successor"] = successor_id
                    if case == "missing_root":
                        cards.pop(root_id)
                    elif case == "unchecked_root":
                        cards[root_id]["identity_checks"]["snapshot_bytes"] = "not_recorded"
                    elif case == "missing_feedback":
                        cards.pop(feedback_id)
                    elif case == "missing_successor":
                        cards.pop(successor_id)
                    else:
                        prefix = "/development_brief/candidates/"
                        if case == "truncated_artifact_path":
                            cards[root_id]["artifact_paths"]["source"] = "partial-path…"
                            field = root_id + "/artifact_paths/source"
                        elif case == "truncated_implementation":
                            cards[root_id]["implementation"]["artifacts"]["source"] = "partial-hash…"
                            field = root_id + "/implementation/artifacts/source"
                        elif case == "truncated_feedback_result":
                            cards[feedback_id]["result"]["result_path"] = "partial-path…"
                            field = feedback_id + "/result/result_path"
                        elif case == "truncated_successor_result":
                            cards[successor_id]["result"]["result_path"] = "partial-path…"
                            field = successor_id + "/result/result_path"
                        elif case == "truncated_reuse_history":
                            cards[root_id]["reused_implementation_from"] = ["older repeats omitted"]
                            field = root_id + "/reused_implementation_from"
                        else:
                            cards[feedback_id]["feedback"] = "Partial observation…"
                            field = feedback_id + "/feedback"
                        packet["truncated_fields"][prefix + field] = 1
                    return packet

                with mock.patch.object(search, "handoff_packet", side_effect=bounded_packet):
                    driver.prepare_turn(campaign, state)
                selection = state["inflight"]["context"]["development_brief"]["review_frontier"]["selection"]
                self.assertEqual(len(selection), 2)
                expected = selection if case in {"truncated_reuse_history", "truncated_feedback_text"} else selection[1:]
                self.assertEqual(state["inflight"]["frontier_exposure"]["implementations"],
                                 [item["implementation_fingerprint"] for item in expected])
                self.assertEqual(driver.read_state(campaign)["frontier_exposures"], {})

    def test_prepared_pending_exposure_requires_complete_targets_and_reference_cards(self) -> None:
        self.seed_pending_proposals(1)
        handoff = search.handoff_packet
        for case in ("missing_reference", "truncated_reference", "truncated_target", "unchecked_targets", "truncated_basis"):
            with self.subTest(case=case):
                campaign = self.root / ("pending-bounded-" + case)
                args = driver.parser().parse_args(self.start_args("--max-turns", "1", "--campaign", str(campaign)))
                driver.new_campaign(args)
                state = driver.read_state(campaign)

                def bounded_packet(*args, **kwargs):
                    packet = handoff(*args, **kwargs)
                    brief = packet["development_brief"]
                    detail = brief["pending_details"][0]
                    if case == "missing_reference":
                        brief["candidates"].pop("seed-best")
                    elif case == "unchecked_targets":
                        detail["identity_checks"]["code_targets"] = "not_recorded"
                    else:
                        if case == "truncated_reference":
                            brief["candidates"]["seed-best"]["artifact_paths"]["source"] = "partial-path…"
                            field = "/development_brief/candidates/seed-best/artifact_paths/source"
                        elif case == "truncated_target":
                            detail["code_targets"][0]["path"] = "partial-path…"
                            field = "/development_brief/pending_details/0/code_targets/0/path"
                        else:
                            detail["basis"] = "Partial explanation…"
                            field = "/development_brief/pending_details/0/basis"
                        packet["truncated_fields"][field] = 1
                    return packet

                with mock.patch.object(search, "handoff_packet", side_effect=bounded_packet):
                    driver.prepare_turn(campaign, state)
                self.assertEqual(state["inflight"]["pending_proposal_exposure"]["proposals"],
                                 ["p0"] if case == "truncated_basis" else [])
                self.assertEqual(driver.read_state(campaign)["pending_proposal_exposures"], {})

    def test_no_progress_rotates_context_without_scheduling_an_unspecified_implementation(self) -> None:
        self.environment["FAKE_SCENARIO"] = "no_progress"
        result = self.start("--max-turns", "6")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(state["turns_without_implementation"], 6)
        self.assertEqual(state["progress"]["executed_implementations"], 0)
        self.assertNotIn("resume", self.calls()[2]["argv"])
        self.assertIn("Resolve one evidence gap", self.calls()[3]["prompt"])
        self.assertNotIn("execute", [row["mode"] for row in self.events() if row["event"] == "turn_prepared"])

    def test_memo_only_review_continues_research_under_the_current_comparison(self) -> None:
        self.environment["FAKE_SCENARIO"] = "research_no_progress"
        result = self.start("--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        prepared = [row for row in self.events() if row["event"] == "turn_prepared"]
        self.assertEqual([row["mode"] for row in prepared], ["work", "research", "rethink", "research"])
        path = runtime.turn_directory(self.campaign, 4)
        request = json.loads((path / "request.json").read_text())
        self.assertIn("Resolve one evidence gap", request["driver_action"])
        self.assertEqual(request["context"]["decision_context"]["research_state"]["report"]["status"], "open")
        prompt = self.calls()[3]["prompt"]
        self.assertLess(prompt.index(request["driver_action"]), prompt.index("Prior next_action (advice;"))
        self.assertNotIn("guaranteed score", request["driver_action"])
        self.assertEqual(self.state()["next_action"], "Require a guaranteed score before building any candidate.")
        self.assertEqual(self.state()["progress"]["executed_implementations"], 0)

    def test_review_selection_survives_resume_and_links_the_executed_proposal(self) -> None:
        self.seed_pending_proposals(2)
        self.environment["FAKE_SCENARIO"] = "selected_proposal"
        first = self.start("--max-turns", "3")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        selection = self.state()
        self.assertEqual(selection["next_proposal_id"], "p1")
        self.assertEqual(selection["research_state"]["proposal_id"], "p1")
        self.assertEqual(self.state()["progress"]["pending_proposals"], 2)
        self.assertEqual([row["mode"] for row in self.events() if row["event"] == "turn_prepared"],
                         ["work", "work", "rethink"])

        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 4) / "request.json").read_text())
        self.assertEqual(request["mode"], "execute")
        self.assertIn('proposal "p1"', request["driver_action"])
        self.assertIn(request["driver_action"], self.calls()[3]["prompt"])
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual(records[-1]["event"], "candidate", self.state()["last_error"])
        self.assertEqual(records[-1]["proposal_id"], "p1")
        self.assertEqual(records[-1]["candidate_id"], "candidate-4")
        self.assertEqual(self.state()["progress"]["pending_proposals"], 1)
        self.assertIsNone(self.state()["next_proposal_id"])

        # Old managers cleared the selected ID after execution but could retain
        # an unlinked implementation report with evidence that still exists.
        restored = self.state()
        self.assertIsNone(restored["research_state"])
        legacy_report = selection["research_state"]
        legacy_report.pop("proposal_id")
        restored["research_state"] = legacy_report
        original_action = restored["next_action"]
        raw_receipt = Path(legacy_report["receipt_path"])
        sealed = raw_receipt.read_bytes()
        driver.TurnLifecycle.prepare(self.campaign, restored)
        self.assertIsNone(self.state()["research_state"])
        self.assertEqual(self.state()["next_action"], original_action)
        self.assertIsNone(self.state()["inflight"]["context"].get("decision_context"))
        self.assertEqual(raw_receipt.read_bytes(), sealed)

    def test_off_contract_proposal_result_is_archived_without_changing_objective_or_adoption(self) -> None:
        self.seed_pending_proposals(2)
        self.environment["FAKE_SCENARIO"] = "selected_proposal_foreign"
        run = self.start("--max-turns", "4")
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        state = self.state()
        records = driver.archive_tools.read_records(self.archive)
        self.assertEqual((records[-1]["candidate_id"], records[-1]["proposal_id"]), ("candidate-4", "p1"))
        self.assertEqual(state["objective_progress"]["best_candidate"], "seed-best")
        self.assertIsNone(state["working_selection"])
        self.assertEqual(state["failures"], 1)
        self.assertIn("differs from the primary comparison: config_hash, runtime_environment", state["last_error"])
        self.assertEqual(state["progress"]["pending_proposals"], 1)
        self.assertEqual(state["next_mode"], "measure")
        self.assertLess(state["comparison_continuity"]["new_unpaired_contracts"], state["comparison_review_window"])

        prefix = self.archive.read_bytes()
        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "5")
        self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 5) / "request.json").read_text())
        self.assertEqual((request["mode"], request["context_refresh_reason"]), ("measure", "selection_comparison"))
        recovery = request["context"]["comparison_recovery"]
        self.assertEqual(recovery["target"]["candidate_id"], "candidate-4")
        self.assertEqual(recovery["reference"]["candidate_id"], records[-1]["parent_ids"][0])
        self.assertEqual(recovery["changed_fields"], ["config_hash", "runtime_environment"])
        self.assertNotIn("development_brief", request["context"])
        self.assertEqual(self.archive.read_bytes(), prefix)
        self.assertEqual(self.state()["selection_comparison"], state["selection_comparison"])
        self.assertEqual(self.state()["next_mode"], "measure")

        recovered = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "6")
        self.assertEqual(recovered.returncode, 0, recovered.stderr + recovered.stdout)
        self.assertEqual(self.turn_context(6)["comparison_recovery"], recovery)
        self.assertEqual(self.archive.read_bytes(), prefix)
        self.assertIsNone(self.state()["selection_comparison"])
        self.assertIsNone(self.state()["working_selection"])

        switched = self.call("resume", "--campaign", str(self.campaign), "--objective-anchor", "candidate-4")
        self.assertEqual(switched.returncode, 0, switched.stderr + switched.stdout)
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "candidate-4")
        self.assertIsNone(self.state()["working_selection"])

    def test_legacy_receipt_recovers_registration_and_dispatches_after_a_stream_failure(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_proposal"
        first = self.start("--max-turns", "1")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        legacy = self.state()
        origin = Path(legacy["proposal_registration"]["receipt_path"])
        original_receipt = origin.read_bytes()
        self.assertEqual(legacy["next_mode"], "register")
        self.assertEqual(legacy["progress"]["proposals"], 0)
        before = self.archive.read_bytes()
        legacy.pop("proposal_registration")
        legacy["next_mode"] = "rethink"
        driver.save_state(self.campaign, legacy)

        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
        interrupted = self.state()
        self.assertEqual(interrupted["next_proposal_id"], "refine", interrupted["last_error"])
        self.assertEqual(interrupted["progress"]["evaluated_candidates"], 1)
        register = runtime.turn_directory(self.campaign, 2)
        self.assertEqual(runtime.read_json(register / "exit.json")["returncode"], 1)
        request = runtime.read_json(register / "request.json")
        self.assertEqual(request["mode"], "register")
        self.assertIn(str(origin), request["driver_action"])

        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "3")
        self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
        request = runtime.read_json(runtime.turn_directory(self.campaign, 3) / "request.json")
        self.assertEqual(request["mode"], "execute")
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], "candidate-3")
        self.assertEqual(driver.archive_tools.read_records(self.archive)[-1]["proposal_id"], "refine")
        self.assertIsNone(self.state()["proposal_registration"])
        self.assertEqual(self.archive.read_bytes()[:len(before)], before)
        self.assertEqual(origin.read_bytes(), original_receipt)

    def test_authorized_local_delivery_survives_stream_failure_and_precedes_research(self) -> None:
        self.task.write_text("Synthetic contest. Produce local drafts from saved models only.\n")
        self.environment["FAKE_SCENARIO"] = "local_delivery_interrupted"
        first = self.start("--max-turns", "2")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        interrupted = self.state()
        self.assertEqual(interrupted["local_delivery"]["status"], "requested")
        self.assertEqual(interrupted["next_mode"], "deliver")
        self.assertIn("stream closed before response.completed", interrupted["last_error"])
        draft = self.workspace / "local-draft.csv"
        first_write = draft.stat()

        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "3")
        self.assertEqual(resumed.returncode, 0, resumed.stderr + resumed.stdout)
        request = json.loads((runtime.turn_directory(self.campaign, 3) / "request.json").read_text())
        self.assertEqual(request["local_delivery_candidate_id"], "candidate-1")
        self.assertIn("freeze/predict", self.calls()[2]["prompt"])
        self.assertIn("inspect and validate existing output", self.calls()[2]["prompt"])
        self.assertEqual(draft.stat().st_mtime_ns, first_write.st_mtime_ns)
        self.assertEqual([row["mode"] for row in self.events() if row["event"] == "turn_prepared"],
                         ["work", "deliver", "deliver"])
        state = self.state()
        self.assertEqual(state["working_selection"]["candidate_id"], "candidate-1")
        self.assertEqual(state["local_delivery"]["status"], "completed")
        self.assertEqual(state["local_delivery"]["evidence_sha256"], {str(draft): runtime.file_hash(draft)})
        self.assertEqual(state["next_action"], interrupted["next_action"])
        self.assertEqual(state["research_state"], interrupted["research_state"])
        self.assertEqual(state["next_mode"], "research")
        self.assertEqual(len(driver.archive_tools.read_records(self.archive)), 1)

    def test_delivery_completion_without_artifact_does_not_clear_request(self) -> None:
        self.task.write_text("Synthetic contest. Produce local drafts from saved models only.\n")
        self.environment["FAKE_SCENARIO"] = "local_delivery_missing"
        result = self.start("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(state["local_delivery"]["status"], "requested")
        self.assertIn("Delivery evidence must be a nonempty local artifact", state["last_error"])
        self.assertEqual(state["next_mode"], "deliver")

    def test_missing_research_evidence_preserves_the_previous_report_and_measured_candidate(self) -> None:
        self.environment["FAKE_SCENARIO"] = "correction_evidence"
        result = self.start("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        key = state["objective_progress"]["comparison_key"]
        reports = state["research_corrections"][key]
        self.assertEqual(reports["direction"]["turn"], 1)
        self.assertEqual(reports["probe"]["turn"], 2)
        event = next(row for row in self.events() if row["event"] == "turn_completed" and row["turn"] == 2)
        self.assertEqual(event["research_corrections_missing_evidence"], {"direction": ["misplaced/probe.txt"]})
        self.assertEqual(event["research_state_missing_evidence"], ["misplaced/rules.md#Tie"])
        self.assertEqual(state["research_state"]["turn"], 1)
        raw_receipt = json.loads(Path(event["receipt_path"]).read_text())
        self.assertEqual(raw_receipt["corrections"][0]["claim"], "The direction is reversed.")
        self.assertEqual(raw_receipt["research_state"]["question"], "Can the scorer drop the tie rule?")
        self.assertEqual(event["receipt"], raw_receipt)
        self.assertEqual(state["objective_progress"]["best_candidate"], "candidate-2")

    def test_real_finding_keeps_research_across_resume_but_a_copied_artifact_does_not(self) -> None:
        self.environment["FAKE_SCENARIO"] = "research_finding"
        first = self.start("--max-turns", "2", "--session-checkpoints", "0")
        self.assertEqual(first.returncode, 0, first.stderr)
        state = self.state()
        self.assertEqual(state["turns_without_implementation"], 2)
        self.assertEqual(state["next_mode"], "research")
        finding = state["research_state"]["finding"]
        self.assertEqual(finding["evidence_sha256"], runtime.file_hash(self.workspace / "original.txt"))
        self.assertEqual(state["research_findings"], {"null": {"existing-pooling": finding["evidence_sha256"]}})

        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        prepared = [row for row in self.events() if row["event"] == "turn_prepared"]
        self.assertEqual([row["mode"] for row in prepared], ["work", "research", "research", "rethink"])
        self.assertEqual(self.turn_context(3)["decision_context"]["research_state"]["finding"], finding)
        delivered = [row["turn"] for row in self.events() if "research_finding_sha256" in row]
        self.assertEqual(delivered, [2])
        self.assertEqual(self.state()["turns_without_implementation"], 4)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 0)

    def test_repeated_measurements_do_not_reset_implementation_stagnation(self) -> None:
        self.environment["FAKE_SCENARIO"] = "repeat"
        result = self.start("--max-turns", "5")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 5)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        self.assertEqual(self.state()["turns_without_implementation"], 4)

    def test_four_transient_failures_retry_instead_of_stopping_after_three(self) -> None:
        self.environment["FAKE_SCENARIO"] = "fail_four"
        result = self.start("--max-turns", "6")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(self.state()["progress"]["executed_implementations"], 6)
        self.assertEqual(len([event for event in self.events()
                              if event["event"] == "turn_interrupted"]), 4)
        calls = self.calls()
        self.assertIn("Recover already-produced artifacts", calls[4]["prompt"])
        self.assertNotIn("resume", calls[4]["argv"])
        for turn in ("000001", "000004"):
            self.assertIn(str(self.campaign / "turns" / turn), calls[4]["prompt"])
        self.assertNotIn("Recover already-produced artifacts", calls[5]["prompt"])

    def test_actual_auth_failure_is_a_concrete_blocker(self) -> None:
        self.environment["FAKE_SCENARIO"] = "auth"
        result = self.start()
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertEqual(len(self.calls()), 1)

    def test_invalid_saved_session_recovers_with_fresh_context(self) -> None:
        self.environment["FAKE_SCENARIO"] = "bad_session"
        result = self.start("--max-turns", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("resume", self.calls()[1]["argv"])
        self.assertNotIn("resume", self.calls()[2]["argv"])

    def test_receipt_without_terminal_event_is_not_accepted(self) -> None:
        self.environment["FAKE_SCENARIO"] = "no_terminal"
        result = self.start("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        interrupted = [event for event in self.events() if event["event"] == "turn_interrupted"]
        self.assertEqual(len(interrupted), 1)
        self.assertIn("terminal event", interrupted[0]["error"])
        self.assertIn("preceding invocation was interrupted", self.calls()[1]["prompt"])

    def test_fenced_receipts_continue_without_false_recovery_or_repeated_execution(self) -> None:
        self.environment["FAKE_SCENARIO"] = "fenced_receipt"
        result = self.start("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(state["progress"]["executed_implementations"], 2)
        self.assertEqual(state["failures"], 0)
        self.assertFalse(state["recovery_needed"])
        self.assertEqual(len(self.calls()), 2)
        self.assertIn("resume", self.calls()[1]["argv"])
        self.assertNotIn("preceding invocation was interrupted", self.calls()[1]["prompt"])
        self.assertEqual(len([event for event in self.events() if event["event"] == "turn_completed"]), 2)
        self.assertFalse([event for event in self.events() if event["event"] == "turn_interrupted"])
        for number in (1, 2):
            directory = self.campaign / "turns" / f"{number:06}"
            message = directory / "message.json"
            self.assertTrue(message.read_text().startswith("All work is recorded."))
            self.assertTrue(message.read_text().endswith("\n```\n"))
            exit_record = json.loads((directory / "exit.json").read_text())
            self.assertEqual(exit_record["outputs"]["message.json"], runtime.file_hash(message))

    def test_receipt_and_terminal_event_do_not_override_nonzero_exit(self) -> None:
        self.environment["FAKE_SCENARIO"] = "receipt_then_fail"
        result = self.start("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        interrupted = [event for event in self.events() if event["event"] == "turn_interrupted"]
        self.assertEqual(len(interrupted), 1)
        self.assertIn("code 7", interrupted[0]["error"])

    def test_explicit_completion_requires_the_fixed_verifier(self) -> None:
        checker = self.root / "checker.py"
        checker.write_text(CHECKER)
        self.environment["FAKE_SCENARIO"] = "claim_complete"
        result = self.start("--completion-check", str(checker))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "complete")
        self.assertEqual(self.state()["turn_number"], 3)

    def test_modified_completion_verifier_cannot_declare_success(self) -> None:
        checker = self.root / "checker.py"
        checker.write_text(CHECKER)
        self.environment.update(FAKE_SCENARIO="checker_tamper", FAKE_CHECKER=str(checker))
        result = self.start("--completion-check", str(checker), "--max-turns", "2")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertIn("identity changed", self.state()["stop_reason"])
        self.assertEqual(len(self.calls()), 1)

    def test_manager_crash_adopts_receipt_delivery_without_repeating_work_or_counting_twice(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt_hold"
        process = self.start_process("--max-turns", "1")
        self.wait_for(lambda: (self.campaign / "fake-receipt-ready").exists())
        status = json.loads(self.call("status", "--campaign", str(self.campaign)).stdout)
        self.assertIsNotNone(status["inflight"]["receipt"]["agent"])
        process.kill()
        process.wait(timeout=5)
        resumed = subprocess.Popen([PYTHON, str(RUNNER), "resume", "--campaign", str(self.campaign)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.environment)
        self.processes.append(resumed)
        self.wait_for(lambda: runtime.lock_busy(self.campaign / "runner.lock"))
        (self.campaign / "fake-receipt-release").touch()
        self.assertEqual(resumed.wait(timeout=12), 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len((self.campaign / "fake-receipt-calls.jsonl").read_text().splitlines()), 1)
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 1)
        self.assertEqual(self.state()["usage"]["input_tokens"], 15)
        self.assertEqual(self.state()["session_turns"], 1)

    def test_immediate_stop_cancels_receipt_delivery_and_preserves_the_completed_experiment(self) -> None:
        self.environment["FAKE_SCENARIO"] = "missing_receipt_hold"
        process = self.start_process("--max-turns", "1")
        self.wait_for(lambda: (self.campaign / "fake-receipt-ready").exists())
        pid = int((self.campaign / "fake-receipt-ready").read_text())
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign), "--now").returncode, 0)
        self.assertEqual(process.wait(timeout=12), 0)
        self.assertEqual(self.state()["status"], "stopped_by_user")
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 1)
        self.assertIsNone(runtime.process_info(pid))
        self.assertTrue(self.state()["recovery_needed"])

    def test_manager_crash_adopts_the_completion_verifier_without_replaying_either_job(self) -> None:
        checker = self.root / "checker.py"
        checker.write_text(HELD_CHECKER)
        process = self.start_process("--completion-check", str(checker), "--max-turns", "1")
        self.wait_for(lambda: (self.campaign / "checker-ready").exists())
        process.kill()
        process.wait(timeout=5)
        resumed = subprocess.Popen([PYTHON, str(RUNNER), "resume", "--campaign", str(self.campaign)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.environment)
        self.processes.append(resumed)
        time.sleep(0.4)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len((self.campaign / "checker-calls.jsonl").read_text().splitlines()), 1)
        (self.campaign / "checker-release").touch()
        self.assertEqual(resumed.wait(timeout=12), 0)
        state = self.state()
        self.assertEqual(state["status"], "complete")
        self.assertEqual(state["progress"]["executed_implementations"], 1)
        self.assertEqual(state["usage"]["input_tokens"], 10)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len((self.campaign / "checker-calls.jsonl").read_text().splitlines()), 1)

    def test_stop_now_cancels_a_completion_verifier_and_its_clean_environment_child(self) -> None:
        checker = self.root / "checker.py"
        checker.write_text(HELD_CHECKER)
        self.environment["FAKE_CHECKER_CHILD"] = "1"
        process = self.start_process("--completion-check", str(checker))
        self.wait_for(lambda: (self.campaign / "checker-ready").exists())
        checker_pid = int((self.campaign / "checker-ready").read_text())
        child_pid = int((self.campaign / "checker-child.pid").read_text())
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign), "--now").returncode, 0)
        self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(self.state()["status"], "stopped_by_user")
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        self.assertIsNone(runtime.process_info(checker_pid))
        self.assertIsNone(runtime.process_info(child_pid))
        self.assertEqual(len(self.calls()), 1)
        outcome = json.loads((self.campaign / "turns/000001/completion/exit.json").read_text())
        self.assertIn("immediate stop", outcome["error"])
        self.assertNotIn("child processes still running", outcome["error"])

    def test_completion_verifier_timeout_reclaims_its_child_and_cannot_confirm_success(self) -> None:
        checker = self.root / "checker.py"
        checker.write_text(HELD_CHECKER)
        self.environment["FAKE_CHECKER_CHILD"] = "1"
        result = self.start("--completion-check", str(checker), "--completion-timeout-seconds", "0.8")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertIn("verifier failed", self.state()["stop_reason"])
        self.assertIn("watchdog", self.state()["stop_reason"])
        self.assertIsNone(runtime.process_info(int((self.campaign / "checker-child.pid").read_text())))
        self.assertEqual(len(self.calls()), 1)

    def crash_completion_owners(self, timeout: str) -> tuple[int, int]:
        checker = self.root / "checker.py"
        checker.write_text(HELD_CHECKER)
        self.environment["FAKE_CHECKER_CHILD"] = "1"
        process = self.start_process("--completion-check", str(checker),
                                     "--completion-timeout-seconds", timeout)
        self.wait_for(lambda: (self.campaign / "checker-ready").exists())
        directory = self.campaign / "turns/000001/completion"
        worker = json.loads((directory / "worker.json").read_text())
        os.kill(worker["pid"], signal.SIGKILL)
        process.kill()
        process.wait(timeout=5)
        return (int((self.campaign / "checker-ready").read_text()),
                int((self.campaign / "checker-child.pid").read_text()))

    def test_verifier_worker_and_manager_crash_does_not_disable_its_deadline(self) -> None:
        checker_pid, child_pid = self.crash_completion_owners("1.5")
        result = self.call("resume", "--campaign", str(self.campaign))
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertIn("watchdog", self.state()["stop_reason"])
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        self.assertEqual(self.state()["usage"]["input_tokens"], 10)
        self.assertIsNone(runtime.process_info(checker_pid))
        self.assertIsNone(runtime.process_info(child_pid))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len((self.campaign / "checker-calls.jsonl").read_text().splitlines()), 1)

    def test_verifier_worker_and_manager_crash_does_not_disable_immediate_stop(self) -> None:
        checker_pid, child_pid = self.crash_completion_owners("60")
        resumed = subprocess.Popen([PYTHON, str(RUNNER), "resume", "--campaign", str(self.campaign)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.environment)
        self.processes.append(resumed)
        self.wait_for(lambda: (self.campaign / "manager.json").exists() and
                      json.loads((self.campaign / "manager.json").read_text())["pid"] == resumed.pid)
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign), "--now").returncode, 0)
        self.assertEqual(resumed.wait(timeout=10), 0)
        self.assertEqual(self.state()["status"], "stopped_by_user")
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        self.assertIsNone(runtime.process_info(checker_pid))
        self.assertIsNone(runtime.process_info(child_pid))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len((self.campaign / "checker-calls.jsonl").read_text().splitlines()), 1)

    def test_partial_append_is_preserved_and_reconciled_without_deadlock(self) -> None:
        self.environment["FAKE_SCENARIO"] = "partial_archive"
        result = self.start("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        quarantine = list((self.campaign / "turns" / "000001").glob("quarantined-archive-*.bin"))
        self.assertEqual(len(quarantine), 1)
        self.assertTrue(quarantine[0].read_bytes().endswith(b'"event":"candi'))
        records = [json.loads(line) for line in self.archive.read_text().splitlines()]
        self.assertEqual([entry["candidate_id"] for entry in records], ["candidate-2"])
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        self.assertIn("quarantined suffixes", self.calls()[1]["prompt"])

    def test_confirmed_archive_mutation_blocks_further_launches(self) -> None:
        self.environment["FAKE_SCENARIO"] = "tamper"
        result = self.start("--max-turns", "5")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("history was edited", self.state()["stop_reason"])
        self.assertEqual(len(self.calls()), 2)

    def test_archive_changes_outside_a_turn_are_not_silently_adopted(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        self.archive.write_text(self.archive.read_text().replace("candidate-1", "candidate-x"))
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 2)
        self.assertIn("changed outside a campaign turn", self.state()["stop_reason"])
        self.assertEqual(len(self.calls()), 1)

    def test_explicit_turn_limit_can_be_extended_without_resetting_history(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "4")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["turn_number"], 4)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 4)

    def test_token_limit_uses_actual_cli_usage_and_is_checked_between_turns(self) -> None:
        result = self.start("--max-tokens", "25")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["turn_number"], 3)
        self.assertIn("max-tokens", self.state()["stop_reason"])

    def test_stop_now_cancels_a_hung_invocation(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hang"
        process = self.start_process()
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        agent_pid = int((self.campaign / "fake-ready-1").read_text())
        result = self.call("stop", "--campaign", str(self.campaign), "--now")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(self.state()["status"], "stopped_by_user")
        self.assertIsNone(runtime.process_info(agent_pid))
        self.assertEqual(len(self.calls()), 1)

    def test_graceful_stop_finishes_current_turn_and_can_resume(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hold"
        process = self.start_process()
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign)).returncode, 0)
        self.assertIsNone(process.poll())
        (self.campaign / "fake-release").touch()
        self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual(self.state()["status"], "stopped_by_user")
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(self.calls()), 2)
        self.assertFalse((self.campaign / "stop.request.json").exists())

    def test_stopped_campaign_accepts_only_a_bound_score_correction_and_resumes(self) -> None:
        isolated = self.seed_open_branches(count=1)
        self.environment["FAKE_SCENARIO"] = "hold"
        process = self.start_process()
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        active = self.call("accept-score-invalidations", "--campaign", str(self.campaign))
        self.assertNotEqual(active.returncode, 0)
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign)).returncode, 0)
        (self.campaign / "fake-release").touch()
        self.assertEqual(process.wait(timeout=10), 0)
        sealed = self.campaign / "turns" / "000001" / "request.json"
        request = sealed.read_bytes()
        prefix = self.archive.read_bytes()
        evidence = self.workspace / "development-audit.txt"
        evidence.write_text("The highest recorded score used the scored partition in fit.\n")
        leader = isolated[-1]
        self.assertEqual(self.state()["objective_progress"]["best_candidate"], leader["candidate_id"])
        api = driver.archive_tools
        api.invalidate_score(api.parser().parse_args([
            "invalidate-score", "--archive", str(self.archive), "--candidate-id", leader["candidate_id"],
            "--result-sha256", leader["result"]["result_sha256"], "--reason", "Found fit overlap",
            "--evidence", str(evidence)]))
        excluded = self.call("accept-score-invalidations", "--campaign", str(self.campaign))
        self.assertEqual(excluded.returncode, 0, excluded.stderr)
        self.assertEqual(self.state()["progress"]["evaluated_candidates"], 3)
        self.assertNotEqual(self.state()["objective_progress"]["best_candidate"], leader["candidate_id"])
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sealed.read_bytes(), request)
        self.assertTrue(self.archive.read_bytes().startswith(prefix))
        brief = self.turn_context(2)["development_brief"]
        self.assertNotEqual(brief["best_development"], leader["candidate_id"])
        self.assertIn("score_invalidation", brief["candidates"][leader["candidate_id"]])

    def test_reviewed_withdrawal_reaches_the_next_request_without_editing_history(self) -> None:
        self.environment["FAKE_SCENARIO"] = "reviewed_corrections"
        process = self.start_process()
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        review_path = self.workspace / "review.json"
        command = ("accept-research-corrections", "--campaign", str(self.campaign), "--report", str(review_path))
        active = self.call(*command)
        self.assertIn("Wait for the campaign manager and supervisor to stop", active.stderr)
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign)).returncode, 0)
        (self.campaign / "fake-release").touch()
        self.assertEqual(process.wait(timeout=10), 0)
        before = self.state()
        key = before["objective_progress"]["comparison_key"]
        old = before["research_corrections"][key]["gate"]
        request = self.campaign / "turns" / "000001" / "request.json"
        sealed = {path: path.read_bytes() for path in (request, Path(old["receipt_path"]))}
        archive_bytes = self.archive.read_bytes()
        withdrawal = {"key": "gate", "status": "withdrawn", "reason": "Other folds saw the scored labels.",
                      "evidence": [str(self.task)]}
        review = {"comparison_key": key, "corrections": [withdrawal]}
        review_path.write_text(json.dumps({**review, "comparison_key": "different-comparison"}))
        self.assertIn("does not match the current development comparison", self.call(*command).stderr)
        review_path.write_text(json.dumps(review))
        self.archive.write_bytes(archive_bytes + b"\n")
        self.assertIn("Candidate archive changed outside a campaign turn", self.call(*command).stderr)
        self.assertEqual(self.state(), before)
        self.archive.write_bytes(archive_bytes)

        accepted = self.call(*command)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["research_withdrawn_keys"], ["gate"])
        state = self.state()
        for field in ("turn_number", "archive_snapshot", "objective_progress", "working_selection", "progress"):
            self.assertEqual(state[field], before[field], field)
        self.assertEqual(self.archive.read_bytes(), archive_bytes)
        row = state["research_corrections"][key]["gate"]
        self.assertEqual(row["report"], withdrawal)
        self.assertEqual(row["supersedes_receipt_path"], old["receipt_path"])
        pointer = Path(row["receipt_path"])
        self.assertEqual(json.loads(pointer.read_text()), {**review, "turn": 1})
        self.assertEqual(runtime.file_hash(pointer), pointer.stem)
        self.assertEqual(self.call(*command).returncode, 0)
        audits = [event for event in self.events() if event["event"] == "research_corrections_accepted"]
        self.assertEqual([audit["report_sha256"] for audit in audits], [pointer.stem])
        self.assertEqual(state["next_mode"], "rethink")

        replacement = {
            "status": "open", "route": "source", "question": "Which representation preserves temporal order?",
            "alternatives": ["A fold-local transform", "The available inputs cannot support one"],
            "missing_evidence": "Read the task's inference boundary before designing the transform.",
            "answer_actions": [{"observation": "The feature is available", "action": "Propose a matched contrast."}],
            "evidence": [str(self.task)]}
        reviewed = {**review, "research_state": replacement}
        review_path.write_text(json.dumps(reviewed))
        accepted = self.call(*command)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        state = self.state()
        self.assertEqual(state["next_mode"], "research")
        self.assertEqual(state["next_action"], replacement["missing_evidence"])
        row = state["research_corrections"][key]["gate"]
        self.assertEqual(json.loads(Path(row["receipt_path"]).read_text()), {**reviewed, "turn": 1})
        review_path.unlink()

        resumed = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual({path: path.read_bytes() for path in sealed}, sealed)
        self.assertIn(row, self.turn_context(2)["decision_context"]["corrections"])
        self.assertEqual(self.turn_context(2)["decision_context"]["research_state"]["report"], replacement)
        self.assertIn(replacement["missing_evidence"], self.calls()[1]["prompt"])
        self.assertNotIn("Reuse the allegedly fold-honest fitted gate.", self.calls()[1]["prompt"])

    def test_watchdog_recovers_a_stuck_turn_without_an_implicit_campaign_stop(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hang"
        result = self.start("--max-turns", "2", "--turn-timeout-seconds", "0.6")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)

    def blocked_campaign_with_stop(self) -> bytes:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        prefix = self.archive.read_bytes()
        task = self.campaign / "task.md"
        original = task.read_bytes()
        task.write_text("modified task")
        self.assertEqual(self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2").returncode, 2)
        self.assertEqual(self.state()["status"], "blocked")
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign), "--now").returncode, 0)
        task.write_bytes(original)
        return prefix

    def test_explicit_resume_clears_a_blocked_campaigns_old_stop_once(self) -> None:
        prefix = self.blocked_campaign_with_stop()
        result = self.call("resume", "--campaign", str(self.campaign), "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 2)
        self.assertTrue(self.archive.read_bytes().startswith(prefix))
        self.assertFalse((self.campaign / "stop.request.json").exists())

    def test_child_ignoring_term_is_killed_even_after_its_leader_exits(self) -> None:
        self.environment["FAKE_SCENARIO"] = "left_child"
        result = self.start("--max-turns", "1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        pid = int((self.campaign / "child-pid").read_text())
        self.assertIsNone(runtime.process_info(pid))
        self.assertTrue(self.state()["recovery_needed"])

    def test_manager_crash_adopts_the_existing_worker_without_relaunching(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hold"
        process = self.start_process("--max-turns", "2")
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        context = self.campaign / "turns" / "000001" / "context.json"
        sealed = context.read_bytes()
        process.kill()
        process.wait(timeout=5)
        resumed = subprocess.Popen([PYTHON, str(RUNNER), "resume", "--campaign", str(self.campaign)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.environment)
        self.processes.append(resumed)
        time.sleep(0.3)
        self.assertEqual(len(self.calls()), 1)
        (self.campaign / "fake-release").touch()
        self.assertEqual(resumed.wait(timeout=12), 0)
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 2)
        self.assertEqual(context.read_bytes(), sealed)
        self.assertEqual(self.state()["session_turns"], 2)
        self.assertEqual(self.state()["usage"]["input_tokens"], 20)

    def test_worker_crash_without_pid_marker_cannot_launch_a_duplicate_agent(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hold"
        process = self.start_process("--max-turns", "1")
        directory = self.campaign / "turns" / "000001"
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists() and
                      (directory / "worker.json").exists())
        worker = json.loads((directory / "worker.json").read_text())
        os.kill(worker["pid"], signal.SIGKILL)
        (directory / "agent.json").unlink(missing_ok=True)
        process.kill()
        process.wait(timeout=5)
        resumed = subprocess.Popen([PYTHON, str(RUNNER), "resume", "--campaign", str(self.campaign)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.environment)
        self.processes.append(resumed)
        time.sleep(0.3)
        self.assertEqual(len(self.calls()), 1)
        (self.campaign / "fake-release").touch()
        self.assertEqual(resumed.wait(timeout=12), 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertTrue(self.state()["recovery_needed"])
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)

    def test_crashed_worker_and_leader_cannot_leave_a_clean_environment_child_running(self) -> None:
        self.environment["FAKE_SCENARIO"] = "clean_child_hold"
        process = self.start_process("--max-turns", "2")
        directory = self.campaign / "turns" / "000001"
        self.wait_for(lambda: (self.campaign / "clean-child-ready").exists() and
                      (directory / "agent.json").exists())
        worker = json.loads((directory / "worker.json").read_text())
        agent = json.loads((directory / "agent.json").read_text())
        child_pid = int((self.campaign / "clean-child.pid").read_text())
        os.kill(worker["pid"], signal.SIGKILL)
        os.kill(agent["pid"], signal.SIGKILL)
        process.kill()
        process.wait(timeout=5)
        self.assertIsNotNone(runtime.process_info(child_pid))
        other = self.root / "other-campaign"
        args = self.start_args("--max-turns", "1")
        args[args.index("--campaign") + 1] = str(other)
        args[args.index("--archive") + 1] = str(self.workspace / "other-archive.jsonl")
        conflict = self.call(*args)
        self.assertEqual(conflict.returncode, 2, conflict.stderr + conflict.stdout)
        self.assertIn("unreconciled in-flight owner", conflict.stdout)
        result = self.call("resume", "--campaign", str(self.campaign))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIsNone(runtime.process_info(child_pid))
        self.assertEqual(len(self.calls()), 2)
        self.assertFalse(self.calls()[1]["previous_child_alive"])

    def test_durable_success_after_manager_crash_is_consumed_without_replay(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        directory = self.campaign / "turns" / "000001"
        state = self.state()
        request = json.loads((directory / "request.json").read_text())
        request["prompt"] = (directory / "prompt.txt").read_text()
        state.update(status="running", inflight=request, archive_snapshot=request["archive_before"],
                     progress={key: 0 for key in state["progress"]}, usage={}, agent_seconds=0, session_turns=0)
        runtime.atomic_json(self.campaign / "state.json", state)
        result = self.call("resume", "--campaign", str(self.campaign))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)
        self.assertEqual(self.state()["usage"]["input_tokens"], 10)
        self.assertEqual(self.state()["session_turns"], 1)

    def test_two_campaigns_cannot_mutate_the_same_canonical_workspace(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hold"
        process = self.start_process("--max-turns", "1")
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        other = self.root / "other-campaign"
        args = self.start_args("--max-turns", "1")
        args[args.index("--campaign") + 1] = str(other)
        args[args.index("--archive") + 1] = str(self.workspace / "other-archive.jsonl")
        result = self.call(*args)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("already owned", result.stdout)
        self.assertEqual(len(self.calls()), 1)
        (self.campaign / "fake-release").touch()
        self.assertEqual(process.wait(timeout=10), 0)

    def test_background_supervisor_restarts_a_killed_manager(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hold"
        result = self.start("--background", "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists() and
                      (self.campaign / "manager.json").exists())
        manager = json.loads((self.campaign / "manager.json").read_text())
        os.kill(manager["pid"], signal.SIGKILL)
        self.wait_for(lambda: json.loads((self.campaign / "manager.json").read_text())["pid"] != manager["pid"])
        self.assertEqual(len(self.calls()), 1)
        (self.campaign / "fake-release").touch()
        self.wait_for(lambda: self.state()["status"] == "limit_reached")
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 2)

    def delayed_background_resume(self, *extra: str) -> tuple[Path, subprocess.CompletedProcess[str]]:
        release = self.campaign / "manager-initialization-release"
        waiting = self.campaign / "manager-initialization-waiting"
        wrapper = self.root / "delayed-background.py"
        shim = ("import os,pathlib,sys,time; "
                f"pathlib.Path({str(waiting)!r}).touch(); "
                f"\nwhile not pathlib.Path({str(release)!r}).exists(): time.sleep(0.02)"
                "\nos.execv(sys.argv[1],sys.argv[1:])")
        wrapper.write_text(
            "import pathlib,sys\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "import autonomous_campaign as campaign\n"
            "original=campaign.subprocess.Popen\n"
            "def delayed(command, **kwargs):\n"
            "    if '_supervise' in command:\n"
            f"        command=[{PYTHON!r}, {str(wrapper)!r}, *command[2:]]\n"
            f"    elif '_run' in command and not pathlib.Path({str(release)!r}).exists():\n"
            f"        command=[{PYTHON!r}, '-c', {shim!r}, *command]\n"
            "    return original(command, **kwargs)\n"
            "campaign.subprocess.Popen=delayed\n"
            "campaign.BACKGROUND_STARTUP_SECONDS=0.6\n"
            "raise SystemExit(campaign.main())\n")
        result = subprocess.run([PYTHON, str(wrapper), "resume", "--campaign", str(self.campaign),
                                 "--background", *extra], capture_output=True, text=True,
                                env=self.environment, timeout=10)
        self.wait_for(waiting.exists)
        return release, result

    def test_background_launch_reports_starting_until_the_new_manager_is_ready(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        old_generation = self.state()["manager_generation"]
        self.environment["FAKE_SCENARIO"] = "hold_second"
        release, result = self.delayed_background_resume("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "starting")
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(self.state()["manager_generation"], old_generation)
        self.assertEqual(json.loads(self.call("status", "--campaign", str(self.campaign)).stdout)["status"], "starting")
        self.assertEqual(len(self.calls()), 1)
        release.touch()
        self.wait_for(lambda: (self.campaign / "fake-ready-2").exists())
        report = json.loads(self.call("status", "--campaign", str(self.campaign)).stdout)
        self.assertEqual(report["status"], "running")
        self.assertNotEqual(report["manager"]["generation"], old_generation)
        self.assertEqual(report["manager"]["generation"], report["supervisor"]["manager_generation"])
        (self.campaign / "fake-release").touch()
        self.wait_for(lambda: self.state()["status"] == "limit_reached")
        self.assertEqual(len(self.calls()), 2)

    def test_stop_issued_during_background_initialization_is_not_consumed_by_resume(self) -> None:
        self.blocked_campaign_with_stop()
        old_stop = json.loads((self.campaign / "stop.request.json").read_text())
        release, result = self.delayed_background_resume("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "starting")
        stopped = self.call("stop", "--campaign", str(self.campaign), "--now")
        self.assertEqual(stopped.returncode, 0, stopped.stderr + stopped.stdout)
        new_stop = json.loads((self.campaign / "stop.request.json").read_text())
        self.assertEqual(old_stop["reason"], new_stop["reason"])
        self.assertNotEqual(old_stop["request_id"], new_stop["request_id"])
        release.touch()
        self.wait_for(lambda: self.state()["status"] == "stopped_by_user")
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(json.loads((self.campaign / "stop.request.json").read_text()), new_stop)

    def test_initializing_resume_can_be_stopped_while_saved_state_is_at_limit(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        release, result = self.delayed_background_resume("--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "starting")
        stopped = self.call("stop", "--campaign", str(self.campaign), "--now")
        self.assertEqual(stopped.returncode, 0, stopped.stderr + stopped.stdout)
        release.touch()
        self.wait_for(lambda: self.state()["status"] == "stopped_by_user")
        self.assertEqual(len(self.calls()), 1)

    def test_background_resume_clears_a_blocked_campaigns_old_stop_once(self) -> None:
        prefix = self.blocked_campaign_with_stop()
        result = self.call("resume", "--campaign", str(self.campaign), "--background", "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(json.loads(result.stdout)["status"], {"running", "limit_reached"})
        self.wait_for(lambda: self.state()["status"] == "limit_reached")
        self.assertEqual(len(self.calls()), 2)
        self.assertTrue(self.archive.read_bytes().startswith(prefix))
        self.assertFalse((self.campaign / "stop.request.json").exists())

    def test_background_startup_returns_a_new_initialization_blocker(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        old_generation = self.state()["manager_generation"]
        (self.campaign / "task.md").write_text("changed task")
        result = self.call("resume", "--campaign", str(self.campaign), "--background", "--max-turns", "2")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("identity changed", report["stop_reason"])
        self.assertNotEqual(report["manager"]["generation"], old_generation)
        self.assertEqual(report["manager"]["generation"], self.state()["manager_generation"])
        self.assertEqual(len(self.calls()), 1)

    def test_supervisor_crash_recovery_preserves_a_pending_graceful_stop(self) -> None:
        self.environment["FAKE_SCENARIO"] = "hold"
        result = self.start("--background", "--max-turns", "2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.wait_for(lambda: (self.campaign / "fake-ready-1").exists())
        manager = json.loads((self.campaign / "manager.json").read_text())
        self.assertEqual(self.call("stop", "--campaign", str(self.campaign)).returncode, 0)
        request = (self.campaign / "stop.request.json").read_bytes()
        os.kill(manager["pid"], signal.SIGKILL)
        self.wait_for(lambda: json.loads((self.campaign / "manager.json").read_text())["pid"] != manager["pid"])
        self.assertEqual((self.campaign / "stop.request.json").read_bytes(), request)
        (self.campaign / "fake-release").touch()
        self.wait_for(lambda: self.state()["status"] == "stopped_by_user")
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.state()["progress"]["executed_implementations"], 1)

    def test_background_resume_waits_for_new_manager_initialization_before_accepting_terminal_state(self) -> None:
        self.assertEqual(self.start("--max-turns", "1").returncode, 0)
        self.environment["FAKE_SCENARIO"] = "hold_second"
        release = self.campaign / "manager-initialization-release"
        waiting = self.campaign / "manager-initialization-waiting"
        wrapper = self.root / "slow-supervisor.py"
        shim = ("import os,pathlib,sys,time; "
                f"pathlib.Path({str(waiting)!r}).touch(); "
                f"\nwhile not pathlib.Path({str(release)!r}).exists(): time.sleep(0.02)"
                "\nos.execv(sys.argv[1],sys.argv[1:])")
        wrapper.write_text(
            "import pathlib,sys\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "import autonomous_campaign as campaign\n"
            "original=campaign.subprocess.Popen\n"
            "def delayed(command, **kwargs):\n"
            f"    if '_run' in command and not pathlib.Path({str(release)!r}).exists():\n"
            f"        command=[{PYTHON!r}, '-c', {shim!r}, *command]\n"
            "    return original(command, **kwargs)\n"
            "campaign.subprocess.Popen=delayed\n"
            f"raise SystemExit(campaign.supervise(pathlib.Path({str(self.campaign)!r}), {{'max_turns':3}}))\n")
        supervisor = subprocess.Popen([PYTHON, str(wrapper)], env=self.environment,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(supervisor)
        self.wait_for(waiting.exists)
        time.sleep(0.5)
        self.assertIsNone(supervisor.poll())
        self.assertTrue(runtime.lock_busy(self.campaign / "supervisor.lock"))
        release.touch()
        self.wait_for(lambda: (self.campaign / "fake-ready-2").exists())
        manager = json.loads((self.campaign / "manager.json").read_text())
        os.kill(manager["pid"], signal.SIGKILL)
        self.wait_for(lambda: json.loads((self.campaign / "manager.json").read_text())["pid"] != manager["pid"])
        self.assertEqual(len(self.calls()), 2)
        (self.campaign / "fake-release").touch()
        self.assertEqual(supervisor.wait(timeout=12), 0)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual(len(self.calls()), 3)


if __name__ == "__main__":
    unittest.main()
