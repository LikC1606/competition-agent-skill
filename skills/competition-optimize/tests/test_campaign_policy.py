from __future__ import annotations

import copy
import importlib
import json
from dataclasses import replace
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
archive = importlib.import_module("candidate_archive")
search = importlib.import_module("campaign_search")
policy = importlib.import_module("campaign_policy")
search_fixtures = importlib.import_module("test_campaign_search")
measurement_fixtures = importlib.import_module("test_measurement_plans")
from campaign_state import complete_state


class CampaignPolicyTests(unittest.TestCase):
    # Reuse archive fixtures without collecting the original test methods.
    setUp = search_fixtures.CampaignSearchTests.setUp
    record = search_fixtures.CampaignSearchTests.record
    records = search_fixtures.CampaignSearchTests.records
    propose = search_fixtures.CampaignSearchTests.propose

    @staticmethod
    def memory(**updates) -> dict:
        memory = {
            "next_mode": "work", "next_action": "Implement the next informative successor",
            "session_id": "existing-session", "session_turns": 0,
            "session_checkpoints": 2, "turn_number": 1,
            "context_refreshes": 0, "context_refresh_reason": "",
            "execution_review_checkpoint": None, "failure_review_window": 3,
            "strategy_review_checkpoints": {}, "comparison_review_checkpoint": None,
            "comparison_review_window": 4, "repeat_review_checkpoints": {},
            "stagnation_window": 4, "frontier_exposures": {},
            "pending_proposal_exposures": {}, "trial_exposures": {},
            "learning_exposures": {}, "turns_without_implementation": 0,
            "retry_base_seconds": 1.0, "retry_max_seconds": 8.0,
            "failures": 0, "retry_at": None, "last_error": "", "recovery_needed": False,
        }
        return {**memory, **updates}

    def receipt(self, next_action: str = "Implement a distinct successor", *, path=None) -> dict:
        return {"status": "continue", "summary": "Reviewed accepted evidence",
                "next_action": next_action, "stop_reason": "", "evidence": [str(path or self.path)]}

    def outcome(self, before: list[dict], after: list[dict], receipt: dict | None):
        self.assertEqual(after[:len(before)], before)
        evidence = search.CampaignEvidence(after)
        previous = search.CampaignEvidence(before).counts
        delta = {key: count - previous[key] for key, count in evidence.counts.items()}
        delta["new_implementation_attempts"] = evidence.new_implementation_attempts(len(before))
        return policy.TurnOutcome(evidence=evidence, appended_events=after[len(before):],
                                  archive_delta=delta, receipt=receipt, now=100.0)

    def measurement_fixture(self):
        fixture = measurement_fixtures.MeasurementPlanTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_prepare_and_accept_leave_borrowed_inputs_unchanged(self) -> None:
        baseline = self.record("baseline", 100)
        records = self.records()
        evidence = search.CampaignEvidence(records)
        progress = evidence.signals()["objective_progress"]
        key = progress["comparison_key"]
        identity = archive.implementation_identity(baseline)["fingerprint"]
        memory = self.memory(session_turns=2,
                             frontier_exposures={key: {"previous-delivery": 2}},
                             strategy_review_checkpoints={"older-contract": {"best_candidate": "old"}})
        turn = {"number": 7, "mode": "work", "fresh_context": False,
                "frontier_exposure": {"comparison_key": key, "implementations": [identity]},
                "review_checkpoints": {"strategy": {
                    name: progress[name] for name in
                    ("comparison_key", "best_candidate", "comparable_implementations")}}}
        outcome = self.outcome(records, records, self.receipt())
        original = copy.deepcopy((memory, turn, records, outcome.receipt, outcome.archive_delta))

        planned = policy.CampaignPolicy().prepare(memory, evidence)
        accepted = policy.CampaignPolicy().accept(memory, turn, outcome)

        self.assertTrue(planned.fresh_context)
        self.assertEqual(accepted["frontier_exposures"][key], {"previous-delivery": 2, identity: 7})
        self.assertEqual((memory, turn, records, outcome.receipt, outcome.archive_delta), original)

    @staticmethod
    def research_report():
        return {"status": "open", "route": "source", "question": "Is group history deployable?",
                "alternatives": ["Known entities", "Unseen entities"],
                "missing_evidence": "Read official inference conditions.",
                "answer_actions": [{"observation": "Entities are unseen", "action": "Use feature-only structure."}],
                "evidence": []}

    def test_question_and_pure_correction_survive_recovery_without_new_candidate(self) -> None:
        self.record("baseline", 100)
        records = self.records()
        original_archive = self.path.read_bytes()
        evidence = search.CampaignEvidence(records)
        progress = evidence.signals()["objective_progress"]
        correction = {"key": "history-transfer", "claim": "Gain is limited to the tested overlap.",
                      "conditions": "This recorded development split.", "limitations": "Test overlap is unknown.",
                      "reopen_when": "Official inference rules establish availability.", "evidence": [str(self.path)]}
        receipt = {**self.receipt("Try another setting"), "research_state": self.research_report(),
                   "corrections": [correction]}
        memory = self.memory(archive=str(self.path), archive_snapshot={"sha256": "a" * 64, "size": 1})
        turn = {"number": 7, "mode": "work", "context": {"objective_progress": progress}}
        outcome = replace(self.outcome(records, records, receipt), receipt_path="/saved/turns/000007/message.json")
        accepted = policy.CampaignPolicy().accept(memory, turn, outcome)
        self.assertEqual(accepted["turns_without_implementation"], 1)
        self.assertEqual(accepted["next_mode"], "research")
        restored = complete_state(json.loads(json.dumps({**memory, **accepted})))
        planned = policy.CampaignPolicy().prepare(restored, evidence)
        self.assertNotIn("next_action", planned.updates)
        self.assertEqual(restored["next_action"], receipt["next_action"])
        handoff = search.prepare_handoff(restored, planned, evidence, "t" * 64)
        decision = handoff.packet["decision_context"]
        self.assertEqual(decision["research_state"]["report"], receipt["research_state"])
        self.assertEqual(decision["corrections"][0]["report"], correction)
        self.assertEqual(decision["corrections"][0]["receipt_path"], outcome.receipt_path)
        self.assertEqual(self.path.read_bytes(), original_archive)
        # Omission retains the state; explicit null resolves its routing effect.
        omitted = policy.CampaignPolicy().accept(restored, turn, self.outcome(records, records, self.receipt()))
        self.assertNotIn("research_state", omitted)
        cleared = policy.CampaignPolicy().accept(restored, turn, self.outcome(
            records, records, {**self.receipt(), "research_state": None}))
        self.assertIsNone(cleared["research_state"])

    def test_research_cannot_override_repairs_frozen_measurement_or_another_contract(self) -> None:
        fixture = self.measurement_fixture()
        fixture.plan()
        evidence = search.CampaignEvidence(archive.read_records(fixture.path))
        key = evidence.signals()["objective_progress"]["comparison_key"]
        research = {"report": self.research_report(), "comparison_key": key, "turn": 1,
                    "receipt_path": "/saved/receipt.json", "assessment_kind": "agent_report"}
        planned = policy.CampaignPolicy().prepare(self.memory(research_state=research, next_mode="execute"), evidence)
        self.assertEqual(planned.updates["next_mode"], "measure")
        self.record("baseline", 100)
        evidence = search.CampaignEvidence(self.records())
        self.assertEqual(policy.CampaignPolicy().prepare(
            self.memory(research_state=research), evidence).updates["next_mode"], "work")
        research["comparison_key"] = evidence.signals()["objective_progress"]["comparison_key"]
        self.record("broken", None, valid=False, status="rejected", parent="baseline")
        self.assertEqual(policy.CampaignPolicy().prepare(
            self.memory(research_state=research, next_mode="execute"),
            search.CampaignEvidence(self.records())).updates["next_mode"], "repair")

    def test_stagnation_refresh_retains_the_concrete_open_research_action(self) -> None:
        self.record("raw-best", 100)
        for n in range(4):
            self.record(f"refinement-{n}", 90 - n)
        view = search.CampaignEvidence(self.records())
        research = {"report": self.research_report(),
                    "comparison_key": view.signals()["objective_progress"]["comparison_key"]}
        action = "Read the matching original implementation to resolve deployable group information."
        planned = policy.CampaignPolicy().prepare(self.memory(research_state=research, next_action=action), view)
        self.assertEqual(planned.context_refresh_reason, "objective_stagnation")
        self.assertEqual(planned.updates["next_mode"], "rethink")
        self.assertNotIn("next_action", planned.updates)
        self.assertIn("compare a complete alternative", planned.driver_action)
        self.assertNotIn(action, planned.driver_action)

    def test_working_choice_survives_recovery_without_redefining_raw_best(self) -> None:
        self.record("raw-best", 100, status="unresolved")
        self.record("working", 95, parent="raw-best")
        records = self.records()
        memory = self.memory(archive=str(self.path), archive_snapshot={"size": 1, "sha256": "a" * 64})
        choice = {"candidate_id": "working", "reason": "Retained under the declared selection protocol.",
                  "limitations": "The lower-ranked raw best remains unresolved.", "evidence": [str(self.path)]}
        turn = {"number": 2, "mode": "work"}
        updates = policy.CampaignPolicy().accept(memory, turn, self.outcome(
            records, records, {**self.receipt(), "working_selection": choice}))
        restored = complete_state(json.loads(json.dumps({**memory, **updates})))
        view = search.CampaignEvidence(records)
        packet = search.prepare_handoff(restored, policy.CampaignPolicy().prepare(restored, view), view, "t" * 64).packet
        self.assertEqual(packet["working_selection"]["candidate_id"], "working")
        self.assertEqual(packet["working_selection"]["limitations"], choice["limitations"])
        self.assertEqual(packet["objective_progress"]["best_candidate"], "raw-best")
        self.assertEqual(packet["objective_progress"]["best_archive_status"], "unresolved")
        self.assertIn("working", packet["development_brief"]["candidates"])
        working_card = packet["development_brief"]["candidates"]["working"]
        self.assertEqual(working_card["status"], "runner_up")
        self.assertEqual(working_card["artifact_paths"], self.entries["working"]["artifact_paths"])
        self.assertEqual(working_card["result"]["result_path"], self.entries["working"]["result"]["result_path"])
        self.assertEqual(working_card["identity_checks"], {"result_bytes": "checked", "snapshot_bytes": "checked"})
        omitted = policy.CampaignPolicy().accept(restored, turn, self.outcome(records, records, self.receipt()))
        self.assertNotIn("working_selection", omitted)
        cleared = policy.CampaignPolicy().accept(restored, turn, self.outcome(
            records, records, {**self.receipt(), "working_selection": None}))
        self.assertIsNone(cleared["working_selection"])

    def test_unadopted_raw_best_does_not_postpone_strategy_review(self) -> None:
        self.record("adopted", 100)
        records = self.records()
        driver = policy.CampaignPolicy()
        choice = {"candidate_id": "adopted", "reason": "Passed the declared comparison.",
                  "limitations": "Development data only.", "evidence": [str(self.path)]}
        adopted = {**self.receipt(), "working_selection": choice}
        memory = self.memory()
        memory.update(driver.accept(memory, {"number": 1, "mode": "work"},
                                    self.outcome([], records, adopted)))
        for n in range(3):
            self.record(f"refinement-{n}", 90 - n, parent="adopted")
        previous = self.records()
        self.record("raw-best", 100.1, parent="adopted", status="rejected")
        records = self.records()
        memory.update(driver.accept(memory, {"number": 5, "mode": "work"},
                                    self.outcome(previous, records, adopted)))
        view = search.CampaignEvidence(records)
        planned = driver.prepare(memory, view)
        self.assertEqual(memory["next_mode"], "rethink")
        self.assertEqual(planned.context_refresh_reason, "objective_stagnation")
        progress = planned.updates["objective_progress"]
        self.assertEqual(progress["best_candidate"], "raw-best")
        self.assertEqual(progress["implementations_since_best"], 0)
        self.assertEqual(progress["strategy_review"]["reference_candidate"], "adopted")
        self.assertEqual(progress["strategy_review"]["implementations_since_reference"], 4)

        # A successful review starts a new window even if the raw best changes again.
        turn = {"number": 6, "mode": "rethink", "review_checkpoints": planned.review_requests}
        memory.update(driver.accept(memory, turn, self.outcome(records, records, self.receipt())))
        self.record("another-raw-best", 100.2, parent="adopted", status="rejected")
        self.assertNotEqual(driver.prepare(memory, search.CampaignEvidence(self.records())).context_refresh_reason,
                            "objective_stagnation")

    def test_new_adoption_moves_review_reference_but_its_repeat_does_not(self) -> None:
        self.record("control", 100)
        records = self.records()
        driver = policy.CampaignPolicy()
        choice = {"candidate_id": "adopted", "reason": "Passed the declared comparison.",
                  "limitations": "Development data only.", "evidence": [str(self.path)]}
        memory = self.memory(stagnation_window=2)
        receipt = {**self.receipt(), "working_selection": {**choice, "candidate_id": "control"}}
        memory.update(driver.accept(memory, {"number": 1, "mode": "work"},
                                    self.outcome([], records, receipt)))
        self.record("try-1", 98, parent="control")
        previous = self.records()
        self.record("adopted", 101, parent="control")
        records = self.records()
        memory.update(driver.accept(memory, {"number": 3, "mode": "work"},
                                    self.outcome(previous, records, {**self.receipt(), "working_selection": choice})))
        self.record("weak-1", 80, parent="adopted")
        view = search.CampaignEvidence(self.records())
        self.assertNotEqual(driver.prepare(memory, view).context_refresh_reason, "objective_stagnation")
        self.record("weak-2", 81, parent="adopted")
        previous = self.records()
        self.record("adopted-again", 102, reuse="adopted")
        records = self.records()
        receipt = {**self.receipt(), "working_selection": {**choice, "candidate_id": "adopted-again"}}
        memory.update(driver.accept(memory, {"number": 6, "mode": "work"},
                                    self.outcome(previous, records, receipt)))
        planned = driver.prepare(memory, search.CampaignEvidence(records))
        self.assertEqual(planned.context_refresh_reason, "objective_stagnation")
        self.assertEqual(planned.updates["objective_progress"]["strategy_review"]["reference_candidate"], "adopted")

    def test_selection_cannot_name_confirmation_unknown_or_foreign_contract(self) -> None:
        self.record("primary", 100)
        self.record("foreign", 99, comparison={"config_hash": "foreign-contract"})
        self.record("confirmation", 101, role="confirmation")
        view = search.CampaignEvidence(self.records())
        for candidate in ("foreign", "confirmation", "unknown"):
            with self.subTest(candidate=candidate), self.assertRaises(archive.ArchiveFailure):
                view.validate_working_selection({"candidate_id": candidate}, objective_anchor="primary")

    def test_failed_receipt_does_not_acknowledge_or_erase_research(self) -> None:
        self.record("baseline", 100)
        records = self.records()
        evidence = search.CampaignEvidence(records)
        research = {"report": self.research_report(),
                    "comparison_key": evidence.signals()["objective_progress"]["comparison_key"]}
        memory = self.memory(research_state=research)
        original = copy.deepcopy(memory)
        updates = policy.CampaignPolicy().accept(memory, {"number": 2, "mode": "research"},
                                               self.outcome(records, records, None))
        self.assertNotIn("research_state", updates)
        self.assertNotIn("research_corrections", updates)
        self.assertEqual(memory, original)

    def test_initial_research_correction_round_trips_before_any_candidate_exists(self) -> None:
        records = []
        evidence = search.CampaignEvidence(records)
        memory = self.memory(archive=str(self.path), archive_snapshot={"sha256": "a" * 64, "size": 0})
        correction = {"key": "discovery-result", "claim": "The inspected cache has metadata leads.",
                      "conditions": "This exact query and page.", "limitations": "Bodies have not been read.",
                      "reopen_when": "A source read establishes the mechanism.", "evidence": ["saved/source.json"]}
        receipt = {**self.receipt(), "research_state": self.research_report(), "corrections": [correction]}
        outcome = replace(self.outcome(records, records, receipt), receipt_path="/saved/000001/message.json")
        updates = policy.CampaignPolicy().accept(memory, {"number": 1, "mode": "work"}, outcome)
        restored = complete_state(json.loads(json.dumps({**memory, **updates})))
        plan = policy.CampaignPolicy().prepare(restored, evidence)
        handoff = search.prepare_handoff(restored, plan, evidence, "t" * 64)
        self.assertIsNone(handoff.packet["objective_progress"]["comparison_key"])
        self.assertEqual(handoff.packet["decision_context"]["corrections"][0]["report"], correction)
        self.assertEqual(handoff.packet["decision_context"]["research_state"]["report"], receipt["research_state"])
        self.assertEqual(plan.updates["next_mode"], "research")

    def test_small_checkpoint_survives_rotation_without_expanding_to_the_evidence_backlog(self) -> None:
        self.record("baseline", 100)
        records = self.records()
        evidence = search.CampaignEvidence(records)
        report = {**self.research_report(),
                  "missing_evidence": "Inference inputs, cost measurements and a matched mechanism control."}
        memory = self.memory(archive=str(self.path), archive_snapshot={"sha256": "a" * 64, "size": 1},
                             session_turns=2)
        action = "Read the permitted inference inputs."
        outcome = self.outcome(records, records, {**self.receipt(action), "research_state": report})
        memory.update(policy.CampaignPolicy().accept(memory, {"number": 3, "mode": "research"}, outcome))
        restored = complete_state(json.loads(json.dumps(memory)))
        plan = policy.CampaignPolicy().prepare(restored, evidence)
        self.assertTrue(plan.fresh_context)
        self.assertEqual(plan.updates["next_mode"], "research")
        self.assertEqual(action, restored["next_action"])
        self.assertNotIn("next_action", plan.updates)
        packet = search.prepare_handoff(restored, plan, evidence, "t" * 64).packet
        self.assertEqual(packet["decision_context"]["research_state"]["report"], report)
        self.assertEqual(restored["turns_without_implementation"], 1)
        # Completing this check does not resolve the broader question or count as execution.
        successor = {**report, "evidence": ["rules/inputs.md"]}
        next_action = "Inspect the saved cost record."
        next_updates = policy.CampaignPolicy().accept(restored, {"number": 4, "mode": "research"},
            self.outcome(records, records, {**self.receipt(next_action), "research_state": successor}))
        next_plan = policy.CampaignPolicy().prepare({**restored, **next_updates}, evidence)
        self.assertEqual(next_action, next_updates["next_action"])
        self.assertEqual(next_plan.updates["next_mode"], "rethink")
        self.assertEqual(next_updates["research_state"]["report"]["status"], "open")
        self.assertEqual(next_updates["turns_without_implementation"], 2)

    def test_withdrawal_replaces_old_premise_across_json_recovery_and_can_be_revised(self) -> None:
        self.record("baseline", 100)
        records = self.records()
        evidence = search.CampaignEvidence(records)
        old = {"key": "population", "claim": "The source count is the training size.",
               "conditions": "Assumed populations match.", "limitations": "Not checked.",
               "reopen_when": "Original metadata is inspected.", "evidence": ["old/note.md"]}
        memory = self.memory(archive=str(self.path), archive_snapshot={"sha256": "a" * 64, "size": 1})
        origin = replace(self.outcome(records, records, {**self.receipt(), "corrections": [old]}),
                         receipt_path="/saved/000001/message.json")
        memory.update(policy.CampaignPolicy().accept(memory, {"number": 1, "mode": "work"}, origin))
        old_state = copy.deepcopy(memory)
        withdrawal = {"key": "population", "status": "withdrawn", "reason": "The populations differ.",
                      "evidence": ["source.json#/quantities/0"]}
        outcome = replace(self.outcome(records, records, {**self.receipt(), "corrections": [withdrawal]}),
                          receipt_path="/saved/000002/message.json")
        updates = policy.CampaignPolicy().accept(memory, {"number": 2, "mode": "research"}, outcome)
        self.assertEqual(memory, old_state)
        restored = complete_state(json.loads(json.dumps({**memory, **updates})))
        plan = policy.CampaignPolicy().prepare(restored, evidence)
        packet = search.prepare_handoff(restored, plan, evidence, "t" * 64).packet
        rows = packet["decision_context"]["corrections"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["report"], withdrawal)
        self.assertEqual(rows[0]["supersedes_receipt_path"], origin.receipt_path)
        self.assertNotIn(old["claim"], json.dumps(packet["decision_context"]))
        self.assertEqual(restored["turns_without_implementation"], 2)
        failed = policy.CampaignPolicy().accept(restored, {"number": 3, "mode": "research"},
                                               self.outcome(records, records, None))
        self.assertNotIn("research_corrections", failed)
        revised = {**old, "claim": "Training size is established by the dataset manifest.",
                   "conditions": "Only the identified dataset.", "evidence": ["dataset/manifest.json"]}
        revised_outcome = replace(self.outcome(records, records, {**self.receipt(), "corrections": [revised]}),
                                  receipt_path="/saved/000004/message.json")
        newer = policy.CampaignPolicy().accept(restored, {"number": 4, "mode": "research"}, revised_outcome)
        key = evidence.signals()["objective_progress"]["comparison_key"]
        row = newer["research_corrections"][key]["population"]
        self.assertEqual(row["report"], revised)
        self.assertEqual(row["supersedes_receipt_path"], outcome.receipt_path)
        self.assertEqual(self.records(), records)

    def test_withdrawn_finding_no_longer_drives_the_inherited_question(self) -> None:
        self.record("baseline", 100)
        records = self.records()
        evidence = search.CampaignEvidence(records)
        memory = self.memory(archive=str(self.path), archive_snapshot={"sha256": "a" * 64, "size": 1})
        report = {**self.research_report(), "evidence": [str(self.path)]}
        finding = {"premise_id": "selector-inert", "observation": "The feature block returns zero.",
                   "design_effect": "Repair the block.", "evidence_path": str(self.path)}
        accepted = replace(self.outcome(records, records, {**self.receipt("Repair the block."),
                           "research_state": report, "research_finding": finding}), finding_sha256="f" * 64)
        driver = policy.CampaignPolicy()
        memory.update(driver.accept(memory, {"number": 1, "mode": "research"}, accepted))
        plan = driver.prepare(memory, evidence)
        self.assertEqual(search.prepare_handoff(memory, plan, evidence, "t" * 64).packet[
            "decision_context"]["research_state"]["finding"]["premise_id"], finding["premise_id"])

        withdrawal = {"key": finding["premise_id"], "status": "withdrawn",
                      "reason": "The real selector passes a different input.", "evidence": [str(self.path)]}
        corrected = self.outcome(records, records, {**self.receipt("Consider a different hypothesis."),
                                 "corrections": [withdrawal]})
        restored = complete_state(json.loads(json.dumps({
            **memory, **driver.accept(memory, {"number": 2, "mode": "work"}, corrected)})))
        plan = driver.prepare(restored, evidence)
        decision = search.prepare_handoff(restored, plan, evidence, "t" * 64).packet["decision_context"]
        self.assertEqual(plan.updates["next_mode"], "rethink")
        # Without the scheduled review, the withdrawn finding no longer supplies
        # an open question that would route ordinary work into research.
        ordinary = driver.prepare({**restored, "next_mode": "work"}, evidence)
        self.assertEqual(ordinary.updates["next_mode"], "work")
        self.assertIsNone(decision["research_state"])
        self.assertEqual(decision["corrections"][0]["report"], withdrawal)
        self.assertEqual(restored["research_state"]["finding"]["premise_id"], finding["premise_id"])
        self.assertEqual(self.records(), records)

    def test_pending_measurement_keeps_its_work_across_context_rotation(self) -> None:
        fixture = self.measurement_fixture()
        frozen = fixture.plan()
        evidence = search.CampaignEvidence(archive.read_records(fixture.path))
        for session_id, turn_number, reason in (
                ("existing-session", 3, "scheduled_rotation"),
                (None, 3, "session_recovery"), (None, 0, "initial")):
            with self.subTest(reason=reason):
                memory = self.memory(session_id=session_id, session_turns=2, turn_number=turn_number)
                planned = policy.CampaignPolicy().prepare(memory, evidence)
                self.assertEqual(planned.updates["next_mode"], "measure")
                self.assertIn(frozen["plan_id"], planned.driver_action)
                self.assertTrue(planned.fresh_context)
                self.assertEqual(planned.context_refresh_reason, reason)
                self.assertIsNone(planned.updates["session_id"])
                self.assertEqual(planned.updates["session_turns"], 0)
                self.assertEqual(planned.review_requests, {})
                self.assertNotIn("repeat_review_checkpoints", planned.updates)

    def test_strategy_review_requires_an_open_primary_proposal_to_schedule_execution(self) -> None:
        self.record("baseline", 100)
        self.record("auxiliary", 100, comparison={"stage": "smoke"})
        self.propose("primary", "baseline")
        self.propose("foreign", "auxiliary")
        self.propose("stopped", "baseline")
        archive.stop_proposal(archive.parser().parse_args(
            ["stop", "--archive", str(self.path), "--proposal-id", "stopped", "--reason", "Inputs unavailable"]))
        records = self.records()
        report = {**self.research_report(), "route": "implement"}
        receipt = {**self.receipt(), "research_state": report}
        memory = self.memory(objective_anchor="baseline", turns_without_implementation=4)
        policy_driver = policy.CampaignPolicy()
        for chosen in (None, "absent", "foreign", "stopped", "primary"):
            with self.subTest(chosen=chosen):
                delivered = {**receipt, "next_proposal_id": chosen} if chosen else receipt
                outcome = self.outcome(records, records, delivered)
                updates = policy_driver.accept(memory, {"number": 2, "mode": "rethink"}, outcome)
                ready = chosen == "primary"
                self.assertEqual(updates["next_mode"], "execute" if ready else "research")
                self.assertEqual(updates["next_proposal_id"], "primary" if ready else None)
                self.assertEqual(updates["research_state"]["report"], report)
                planned = policy_driver.prepare({**memory, **updates}, outcome.evidence)
                if ready:
                    self.assertIn('proposal "primary"', planned.driver_action)
                    empty = policy_driver.accept({**memory, **updates}, {"number": 3, "mode": "execute"}, outcome)
                    self.assertIsNone(empty["next_proposal_id"])
                    self.assertNotEqual(empty["next_mode"], "execute")
                else:
                    self.assertIn("one evidence gap", planned.driver_action)

    def test_execute_hands_off_a_replacement_after_stopping_the_original(self) -> None:
        self.record("baseline", 100)
        self.propose("original", "baseline")
        before = self.records()
        memory = self.memory(objective_anchor="baseline", next_mode="execute", next_proposal_id="original")
        reason = "The real feature caller disproves the selector defect."
        archive.stop_proposal(archive.parser().parse_args(
            ["stop", "--archive", str(self.path), "--proposal-id", "original", "--reason", reason]))
        self.propose("narrowed", "baseline")
        receipt = {**self.receipt("Evaluate the replacement intervention."), "next_proposal_id": "narrowed"}
        outcome = self.outcome(before, self.records(), receipt)
        driver = policy.CampaignPolicy()
        updates = driver.accept(memory, {"number": 2, "mode": "execute"}, outcome)
        plan = driver.prepare({**memory, **updates}, outcome.evidence)
        self.assertEqual(plan.updates["next_mode"], "execute")
        self.assertIn('proposal "narrowed"', plan.driver_action)
        self.assertEqual(outcome.archive_delta["new_implementation_attempts"], 0)
        old = archive.iteration_trace(self.records(), proposal_id="original")[0]
        self.assertEqual((old["state"], old["reason"]), ("stopped", reason))
        self.assertNotIn("objective_gain_vs_parents", old)

    def test_pinned_objective_survives_policy_accept_and_prepared_handoff(self) -> None:
        self.record("primary", 100)
        for number in range(4):
            self.record(f"regression-{number}", 90 - number)
        self.propose("primary-pending", "primary")
        before = self.records()
        memory = self.memory(objective_anchor="primary", archive=str(self.path),
                             archive_snapshot={"sha256": "a" * 64, "size": 1})
        self.record("smoke-base", 1000, comparison={"stage": "smoke"})
        self.record("smoke-next", 999, comparison={"stage": "smoke"})
        view = search.CampaignEvidence(self.records())
        planned = policy.CampaignPolicy().prepare(memory, view)
        handoff = search.prepare_handoff(memory, planned, view, "t" * 64)

        self.assertEqual(planned.context_refresh_reason, "objective_stagnation")
        self.assertEqual(planned.updates["objective_progress"]["best_candidate"], "primary")
        self.assertEqual(handoff.packet["development_brief"]["pending_proposals"], ["primary-pending"])
        self.assertEqual(handoff.packet["objective_progress"]["objective_anchor"], "primary")
        turn = {"number": 2, "mode": planned.updates["next_mode"], **handoff.delivery}
        accepted = policy.CampaignPolicy().accept(
            {**memory, **planned.updates}, turn, self.outcome(before, self.records(), self.receipt()))
        self.assertEqual(accepted["objective_progress"], planned.updates["objective_progress"])

        self.record("smoke-failed", None, valid=False, status="rejected", comparison={"stage": "smoke"})
        failed = policy.CampaignPolicy().prepare(
            {**memory, **planned.updates, **accepted}, search.CampaignEvidence(self.records()))
        self.assertEqual(failed.updates["next_mode"], "repair")
        self.assertEqual(failed.updates["objective_progress"]["best_candidate"], "primary")
        self.assertEqual(failed.updates["execution_health"]["anchor_candidate"], "smoke-failed")

    def test_review_confirmation_recomputes_continuity_without_acknowledging_new_evidence(self) -> None:
        for number in range(4):
            self.record(f"isolated-{number}", comparison={"config_hash": f"contract-{number}"})
        before = self.records()
        memory = self.memory(turn_number=12)
        staged = policy.CampaignPolicy().prepare(memory, search.CampaignEvidence(before))
        self.assertEqual(staged.context_refresh_reason, "comparison_isolation")
        self.assertNotIn("comparison_review_checkpoint", staged.updates)
        sealed_key = staged.updates["objective_progress"]["comparison_key"]
        identity = archive.implementation_identity(before[-1])["fingerprint"]
        turn = {"number": 11, "mode": "measure", "review_checkpoints": staged.review_requests,
                "context": {"comparison_continuity": staged.updates["comparison_continuity"]},
                "frontier_exposure": {"comparison_key": sealed_key, "implementations": [identity]}}
        memory.update(staged.updates)
        self.record("appended-during-review", comparison={"config_hash": "contract-4"})

        accepted = policy.CampaignPolicy().accept(
            memory, turn, self.outcome(before, self.records(), self.receipt()))

        continuity = accepted["comparison_continuity"]
        self.assertEqual(accepted["comparison_review_checkpoint"], {"distinct_observations": 4})
        self.assertEqual((continuity["distinct_observations"], continuity["reviewed_observations"],
                          continuity["new_unpaired_contracts"]), (5, 4, 1))
        self.assertEqual(accepted["next_mode"], "work")
        active_key = accepted["objective_progress"]["comparison_key"]
        self.assertNotEqual(active_key, sealed_key)
        self.assertEqual(accepted["frontier_exposures"], {sealed_key: {identity: 11}})
        self.assertEqual(policy.CampaignPolicy().prepare(
            {**memory, **accepted}, search.CampaignEvidence(self.records())).updates["next_mode"], "work")

    def test_failed_delivery_keeps_diagnostic_repair_without_resetting_idle_or_acknowledging_requests(self) -> None:
        baseline = self.record("baseline", 100)
        for number in range(4):
            self.record(f"nonimproving-{number}", 90 - number)
        before = self.records()
        memory = self.memory(session_turns=1, failures=2, recovery_needed=True,
                             turns_without_implementation=3)
        staged = policy.CampaignPolicy().prepare(memory, search.CampaignEvidence(before))
        self.assertEqual(staged.updates["next_mode"], "rethink")
        memory.update(staged.updates)
        turn = {"number": 4, "mode": "rethink", "review_checkpoints": staged.review_requests,
                "frontier_exposure": {
                    "comparison_key": staged.updates["objective_progress"]["comparison_key"],
                    "implementations": [archive.implementation_identity(baseline)["fingerprint"]]}}
        self.record("failed-diagnostic", None, valid=False, status="rejected", role="diagnostic", parent="baseline")

        accepted = policy.CampaignPolicy().accept(memory, turn, self.outcome(before, self.records(), None))

        self.assertTrue(accepted["execution_health"]["needs_attention"])
        self.assertEqual(accepted["execution_health"]["anchor_candidate"], "failed-diagnostic")
        self.assertEqual(accepted["objective_progress"]["best_candidate"], "baseline")
        self.assertEqual(accepted["objective_progress"]["comparable_implementations"], 5)
        self.assertEqual(accepted["turns_without_implementation"], 4)
        self.assertEqual(accepted["next_mode"], "repair")
        self.assertIsNone(accepted["session_id"])
        for key in ("session_turns", "frontier_exposures", "pending_proposal_exposures", "trial_exposures",
                    "learning_exposures", "execution_review_checkpoint", "strategy_review_checkpoints",
                    "comparison_review_checkpoint", "repeat_review_checkpoints", "failures", "recovery_needed"):
            self.assertNotIn(key, accepted)

    def test_diagnostics_and_protocol_refits_do_not_reset_implementation_idle(self) -> None:
        recipe = {"schema_version": 1, "task": "regression", "features": ["x"],
                  "id_column": "id", "target_column": "y", "candidate_source": "def build_model(seed, task): ...\n",
                  "training_data_sha256": "a" * 64, "prediction_rule": {"operation": "mean"},
                  "environment": {"python": "3.13"}, "adapter_hash": "b" * 64}
        self.record("baseline", 100, scope="prediction_csv", recipe=recipe)
        before = self.records()
        self.record("same-recipe-refit", 101, scope="prediction_csv", recipe=recipe, parent="baseline",
                    comparison={"config_hash": "ten-fold"})
        self.record("adapter-rebuild", 102, scope="prediction_csv", parent="baseline",
                    recipe={**recipe, "adapter_hash": "c" * 64}, comparison={"config_hash": "eight-fold"})
        self.record("diagnostic", 110, role="diagnostic", parent="baseline", status="unresolved")
        after = self.records()
        memory = self.memory(objective_anchor="baseline", turns_without_implementation=1)
        turn = {"number": 2, "mode": "work"}
        outcome = self.outcome(before, after, self.receipt())
        accepted = policy.CampaignPolicy().accept(memory, turn, outcome)

        self.assertEqual(outcome.archive_delta["executed_implementations"], 2)
        self.assertEqual(outcome.archive_delta["diagnostic_evaluations"], 1)
        self.assertEqual(outcome.archive_delta["new_implementation_attempts"], 0)
        self.assertEqual(accepted["objective_progress"]["best_candidate"], "baseline")
        self.assertEqual(accepted["turns_without_implementation"], 2)
        self.assertEqual(accepted["next_mode"], "rethink")

        self.record("feature-change", 95, scope="prediction_csv", parent="baseline",
                    recipe={**recipe, "adapter_hash": "c" * 64, "features": ["x", "z"]})
        successor = self.outcome(after, self.records(), self.receipt())
        next_updates = policy.CampaignPolicy().accept({**memory, **accepted}, {"number": 3, "mode": "rethink"},
                                                       successor)
        self.assertEqual(successor.archive_delta["new_implementation_attempts"], 1)
        self.assertEqual(next_updates["turns_without_implementation"], 0)
        self.assertEqual(next_updates["objective_progress"]["best_candidate"], "baseline")

    def test_healthy_plan_closure_returns_to_work_even_when_cli_delivery_fails(self) -> None:
        fixture = self.measurement_fixture()
        fixture.finish_plan()
        after = archive.read_records(fixture.path)
        before = after[:-1]
        self.assertEqual(after[-1]["event"], "measurement_decision")
        memory = self.memory(next_mode="measure", session_turns=1)
        staged = policy.CampaignPolicy().prepare(memory, search.CampaignEvidence(before))
        self.assertEqual(staged.updates["next_mode"], "measure")
        memory.update(staged.updates)
        turn = {"number": 3, "mode": "measure", "review_checkpoints": {},
                "context": {"comparison_continuity": staged.updates["comparison_continuity"]}}

        accepted = policy.CampaignPolicy().accept(memory, turn, self.outcome(before, after, None))

        self.assertFalse(accepted["execution_health"]["needs_attention"])
        self.assertEqual(accepted["next_mode"], "work")
        self.assertNotIn("session_turns", accepted)
        self.assertEqual(accepted["objective_progress"], staged.updates["objective_progress"])
        self.assertEqual(policy.CampaignPolicy().prepare(
            {**memory, **accepted}, search.CampaignEvidence(after)).updates["next_mode"], "work")

    def test_legacy_sealed_turns_need_no_optional_delivery_or_context_fields(self) -> None:
        self.record("baseline", 100)
        records = self.records()
        for mode, expected in (("measure", "work"), ("repair", "rethink"), ("rethink", "research")):
            with self.subTest(mode=mode):
                memory = self.memory(session_turns=1, turns_without_implementation=1)
                turn = {"number": 2, "mode": mode}
                accepted = policy.CampaignPolicy().accept(
                    memory, turn, self.outcome(records, records, self.receipt()))
                self.assertEqual(accepted["session_turns"], 2)
                self.assertEqual(accepted["next_mode"], expected)
                self.assertEqual(accepted["retry_at"], None if mode == "measure" else 101.0)
                for key in ("frontier_exposures", "pending_proposal_exposures", "trial_exposures",
                            "learning_exposures", "execution_review_checkpoint", "strategy_review_checkpoints",
                            "comparison_review_checkpoint", "repeat_review_checkpoints"):
                    self.assertNotIn(key, accepted)

    def test_historical_measurement_resolutions_do_not_replace_current_action(self) -> None:
        for event in ("measurement_decision", "measurement_stop"):
            with self.subTest(event=event):
                fixture = self.measurement_fixture()
                if event == "measurement_decision":
                    resolution = fixture.finish_plan()
                else:
                    fixture.plan()
                    resolution = fixture.stop()
                records = archive.read_records(fixture.path)
                current_action = "Implement the newly selected structural improvement"
                self.assertNotEqual(current_action, resolution["next_action"])
                accepted = policy.CampaignPolicy().accept(
                    self.memory(), {"number": 3, "mode": "work"},
                    self.outcome(records, records, self.receipt(current_action, path=fixture.path)))
                self.assertEqual(accepted["next_action"], current_action)
                self.assertEqual(accepted["next_mode"], "work")

    def test_new_resolution_controls_action_only_for_the_post_turn_active_comparison(self) -> None:
        for change_contract in (False, True):
            with self.subTest(change_contract=change_contract):
                fixture = self.measurement_fixture()
                resolution = fixture.finish_plan()
                before = archive.read_records(fixture.path)[:-1]
                if change_contract:
                    fixture.record("new-active-contract", "other", 120, config_hash="different-contract")
                after = archive.read_records(fixture.path)
                current_action = "Continue the current contract with a complete implementation"
                accepted = policy.CampaignPolicy().accept(
                    self.memory(), {"number": 3, "mode": "work"},
                    self.outcome(before, after, self.receipt(current_action, path=fixture.path)))
                self.assertEqual(accepted["next_action"],
                                 current_action if change_contract else resolution["next_action"])
                self.assertEqual(accepted["next_mode"], "work")


if __name__ == "__main__":
    unittest.main()
