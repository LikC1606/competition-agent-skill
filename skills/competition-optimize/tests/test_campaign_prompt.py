from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from campaign_prompt import prompt_for_turn
from campaign_handoff import bound_packet
from candidate_evidence import canonical, sha256


class CampaignPromptTests(unittest.TestCase):
    def state(self, **changes):
        return {"next_mode": "work", "archive": "/tmp/test/archive.jsonl", "recovery_needed": False,
                "completion_check": None, "context_refresh_reason": "", "progress": {},
                "last_summary": "", "next_action": "Implement the next mechanism", **changes}

    def render(self, context=None, **changes):
        return prompt_for_turn(self.state(**changes), Path("/tmp/test/campaign"), 1, context or {})

    def test_empty_evidence_retains_obligations_without_unrelated_feature_manual(self):
        prompt = self.render()
        for obligation in ("actual user/resource limits", "No default", "matching contracts",
                           "confirmation outcomes", "Do not submit", "local child jobs", "next_action"):
            self.assertIn(obligation, prompt)
        for absent in ("scoped_learning", "resource_tradeoffs", "complementary_evidence", "measure-plan", "--baseline-fit"):
            self.assertNotIn(absent, prompt)
        self.assertLess(len(prompt.encode()), 4000)

    def test_feature_guidance_follows_delivered_cards_without_mutating_context(self):
        context = {"development_brief": {"resource_tradeoffs": {"selection": [{"candidate_id": "fast"}]},
                                         "scoped_learning": {"selection": []}}}
        original = copy.deepcopy(context)
        prompt = self.render(context)
        self.assertIn("Total evaluator time is not inferred candidate latency", prompt)
        self.assertNotIn("use learning_from", prompt)
        self.assertEqual(context, original)

    def test_repair_and_measurement_keep_distinct_executable_instructions(self):
        repair = self.render(next_mode="repair")
        measure = self.render({"measurement_plan": {"plan_id": "frozen"}}, next_mode="measure")
        self.assertIn("measure-stop", repair)
        self.assertNotIn("strategy review", repair)
        self.assertIn("measure-status", measure)
        self.assertIn("measurement_run_id", measure)
        self.assertIn("measure-decide", measure)

    def test_frozen_instruction_pointer_replaces_live_skill_pointer(self):
        prompt = self.render(instruction_snapshot={"skill_path": "/tmp/test/instructions/v1/SKILL.md"})
        self.assertIn("Read /tmp/test/instructions/v1/SKILL.md", prompt)
        self.assertNotIn("Read " + str(Path(__file__).resolve().parents[1] / "SKILL.md"), prompt)

    def test_only_the_supplied_effective_invocation_limit_is_delivered(self):
        context = {"development_brief": {"candidates": {}}}
        original = copy.deepcopy(context)
        state = self.state(turn_timeout_seconds=1000)
        prompt = prompt_for_turn(state, Path("/saved/campaign"), 1, context, timeout_seconds=23.125)
        self.assertIn("23.125 seconds from launch", prompt)
        self.assertNotIn("1000 seconds", prompt)
        self.assertNotIn("wall allowance", self.render(context))
        self.assertEqual(context, original)

    def test_research_delivers_the_whole_continuation_as_advice(self):
        action = "Inspect the saved perturbation record. " + "scope " * 450 + "Stop at the recorded controls."
        context = {"decision_context": {"research_state": {"report": {
            "status": "open", "route": "diagnostic", "question": "Wider unresolved research question",
            "missing_evidence": "Other checks for later checkpoints"}}},
            "development_brief": {"complementary_evidence": {"selection": [{"candidate_id": "a"}]}}}
        original = copy.deepcopy(context)
        prompt = self.render(context, next_mode="research", next_action=action)
        self.assertIn("Prior next_action (advice; check against task and evidence): " + json.dumps(action), prompt)
        self.assertNotIn(action, prompt.split("\n\n", 1)[0])
        self.assertNotIn("brief/trace", prompt)
        self.assertNotIn("execute a real combination", prompt)
        self.assertNotIn("run.load_model", prompt)
        self.assertEqual(json.loads(prompt.rstrip().splitlines()[-1]), original)
        self.assertEqual(context, original)

    def test_source_research_pivots_without_turning_into_a_local_refit(self):
        research_context = {"decision_context": {"research_state": {"report": {
            "status": "open", "route": "source", "question": "How is the specialist trained?"}}}}
        research = self.render(research_context, next_mode="research")
        execute = self.render(research_context, next_mode="execute")
        self.assertIn("pivot to another original", research)
        self.assertIn("Splitting pooled OOF again does not isolate it", research)
        self.assertIn("--baseline-fit and --candidate-fit", research)
        self.assertIn("pooled_oof_second_layer_boundary", research)
        self.assertNotIn("tabular_training.py recompose", research)
        self.assertNotIn("pivot to another original", execute)
        self.assertIn("before optional refits", execute)
        self.assertIn("fit only an added member", execute)
        self.assertIn("tabular_training.py recompose", execute)

    def test_current_correction_remains_complete_despite_an_oversized_previous_summary(self):
        correction = {"turn": 7, "receipt_path": "/saved/000007/message.json", "report": {
            "key": "mixture-response", "claim": "A response ratio is local to its measured intervention.",
            "conditions": "Only this development sample and change.",
            "limitations": "X" * 3000 + " No comparison identifies a universal multiplier.",
            "reopen_when": "A changed residual direction warrants a new mechanism.", "evidence": ["saved/report.json"]}}
        context = {"decision_context": {"research_state": None, "corrections": [correction]}}
        prompt = self.render(context, last_summary="Old unrestricted explanation. " * 200)
        packet = json.loads(prompt.rstrip().splitlines()[-1])
        self.assertEqual(packet["decision_context"]["corrections"][0], correction)

    def test_all_work_modes_retain_advice_and_actual_receipt_pointer(self):
        action = "Inspect only the saved controls. " + "control " * 400 + "Retain unresolved alternatives."
        pointer = "/saved/000007/receipt/message.json"
        for mode in ("work", "research", "rethink", "repair", "measure", "execute"):
            with self.subTest(mode=mode):
                prompt = self.render(next_mode=mode, next_action=action,
                                     last_summary="old finding " * 300, last_receipt_path=pointer)
                self.assertIn(json.dumps(action), prompt)
                self.assertNotIn(action, prompt.split("\n\n", 1)[0])
                self.assertIn(pointer, prompt)

    def test_delivery_scope_and_development_continuation_apply_in_every_mode(self):
        for mode in ("work", "research", "execute", "rethink", "measure", "repair", "deliver"):
            with self.subTest(mode=mode):
                prompt = self.render(next_mode=mode, next_action="Freeze models from the auxiliary protocol.")
                self.assertIn("Follow the task's delivery scope, including local drafts.", prompt)
                self.assertIn("does not qualify as a new primary best", prompt)
                self.assertIn("An unresolved permission question does not block authorized development.", prompt)

    def test_prompt_skips_draft_request_only_for_the_completed_working_selection(self):
        adopted = {"candidate_id": "adopted", "comparison_key": "primary"}
        completed = {**adopted, "status": "completed"}
        progress = {"comparison_key": "primary"}
        schedule = "Schedule an authorized local draft with local_delivery.status=requested"
        prompt = self.render(next_mode="research", objective_progress=progress,
                             working_selection=adopted, local_delivery=completed)
        self.assertNotIn(schedule, prompt)
        self.assertIn("The local draft for the current working selection is already recorded.", prompt)
        self.assertIn("Request a new draft only when adopting a different eligible candidate", prompt)
        for other in ({**completed, "candidate_id": "different"},
                      {**completed, "comparison_key": "old"},
                      {**completed, "status": "requested"}):
            with self.subTest(local_delivery=other):
                self.assertIn(schedule, self.render(next_mode="rethink", objective_progress=progress,
                                                    working_selection=adopted, local_delivery=other))

    def test_budget_retains_withdrawal_identity_without_reviving_its_previous_claim(self):
        row = {"turn": 8, "receipt_path": "/saved/000008/message.json",
               "supersedes_receipt_path": "/saved/000007/message.json", "report": {
                   "key": "population", "status": "withdrawn", "reason": "X" * 30000,
                   "evidence": ["source.json#/quantities/0"]}}
        packet = {"schema_version": 1, "archive_path": "/saved/archive.jsonl", "archive_snapshot": {},
                  "task_sha256": "t" * 64, "scope": "Development only", "decision_context": {
                      "scope": "Agent interpretations", "research_state": None, "corrections": [row]}}
        bounded = bound_packet(packet, budget=16384)
        pointer = bounded["decision_context"]["corrections"][0]
        self.assertIsNone(pointer["report"])
        self.assertEqual(pointer["report_status"], "withdrawn")
        self.assertEqual(pointer["report_key"], "population")
        self.assertEqual(pointer["receipt_path"], row["receipt_path"])
        self.assertEqual(pointer["supersedes_receipt_path"], row["supersedes_receipt_path"])

    def test_budget_omits_a_whole_report_with_a_recoverable_receipt_pointer(self):
        correction = {"turn": 7, "receipt_path": "/saved/000007/message.json", "report": {
            "key": "mixture-response", "claim": "X" * 30000,
            "conditions": "Only the measured intervention.", "limitations": "Not a universal multiplier.",
            "reopen_when": "Different interventions remain open.", "evidence": ["saved/result.json"]}}
        packet = {"schema_version": 1, "archive_path": "/saved/archive.jsonl", "archive_snapshot": {},
                  "task_sha256": "t" * 64, "scope": "Development only", "decision_context": {
                      "scope": "Conditional reports", "research_state": None, "corrections": [correction]}}
        original = copy.deepcopy(packet)
        bounded = bound_packet(packet, budget=16384)
        row = bounded["decision_context"]["corrections"][0]
        self.assertIsNone(row["report"])
        self.assertEqual(row["receipt_path"], correction["receipt_path"])
        self.assertEqual(row["report_key"], correction["report"]["key"])
        self.assertEqual(row["report_sha256"], sha256(canonical(correction["report"])))
        self.assertLessEqual(len(json.dumps(bounded).encode()) + 1, 16384)
        self.assertEqual(packet, original)

    def test_current_audit_batch_reaches_handoff_ahead_of_optional_routes(self):
        receipt = "/saved/campaign/maintenance/research-corrections/" + "a" * 64 + ".json"
        origin = {"turn": 8, "comparison_key": "c" * 64, "assessment_kind": "maintenance_audit",
                  "receipt_path": receipt, "supersedes_receipt_path": "/saved/000007/message.json"}
        keys = ["unisolated-gate", "cost", "seed-variance", "protocol-gap", "delivery-score"]
        reports = [{"key": keys[0], "status": "withdrawn", "reason": "An inner fit saw outer labels.",
                    "evidence": ["audit/gate.json"]}]
        reports.extend({"key": key, "claim": "Scoped observation. " * 250,
                        "conditions": "Matched development rows.", "limitations": "Applies to the cited protocol.",
                        "reopen_when": "Evidence changes the decision.", "evidence": ["audit/review.json"]}
                       for key in keys[1:])
        research = {"turn": 7, "receipt_path": "/saved/000007/message.json", "report": {
            "status": "open", "question": "Is a delivery refit justified by this score?"}}
        packet = {"schema_version": 1, "archive_path": "/saved/archive.jsonl", "archive_snapshot": {},
                  "task_sha256": "t" * 64, "scope": "Development only",
                  "objective_progress": {"best_candidate": "current-best"},
                  "working_selection": {"candidate_id": "adopted"},
                  "decision_context": {"scope": "Reviewed corrections", "research_state": research,
                                       "corrections": [{**origin, "report": report} for report in reports]},
                  "development_brief": {"best_development": "current-best",
                                        "candidates": {key: {"candidate_id": key, "mechanism": "Fitted tree. " * 8}
                                                       for key in ("current-best", "adopted")},
                                        "routes": [{"best": f"optional-{n}", "scope": "Route " * 100}
                                                   for n in range(30)]}}
        budget = 20 * 1024
        bounded = bound_packet(packet, budget=budget)
        rows = bounded["decision_context"]["corrections"]
        self.assertEqual([row["report"]["key"] if row["report"] else row["report_key"] for row in rows], keys)
        self.assertTrue(all(row["receipt_path"] == receipt for row in rows))
        question = bounded["decision_context"]["research_state"]
        self.assertIsNone(question["report"])
        self.assertEqual(question["receipt_path"], research["receipt_path"])
        self.assertEqual(bounded["objective_progress"]["best_candidate"], "current-best")
        self.assertEqual(set(bounded["development_brief"]["candidates"]), {"current-best", "adopted"})
        self.assertGreater(len(bounded["development_brief"]["routes"]), 0)
        self.assertLess(len(bounded["development_brief"]["routes"]), len(packet["development_brief"]["routes"]))
        self.assertLessEqual(len(json.dumps(bounded).encode()) + 1, budget)


if __name__ == "__main__":
    unittest.main()
