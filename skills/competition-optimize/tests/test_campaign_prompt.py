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
        for absent in ("scoped_learning", "resource_tradeoffs", "complementary_evidence", "measure-plan"):
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

    def test_research_delivers_the_whole_selected_action_before_background(self):
        action = "Inspect the saved perturbation record. " + "scope " * 450 + "Stop at the recorded controls."
        context = {"decision_context": {"research_state": {"report": {
            "status": "open", "route": "diagnostic", "question": "Wider unresolved research question",
            "missing_evidence": "Other checks for later checkpoints"}}},
            "development_brief": {"complementary_evidence": {"selection": [{"candidate_id": "a"}]}}}
        original = copy.deepcopy(context)
        prompt = self.render(context, next_mode="research", next_action=action)
        self.assertIn(json.dumps(action), prompt.split("\n\n", 1)[0])
        self.assertNotIn("brief/trace", prompt)
        self.assertNotIn("execute a real combination", prompt)
        self.assertNotIn("run.load_model", prompt)
        self.assertEqual(json.loads(prompt.rstrip().splitlines()[-1]), original)
        self.assertEqual(context, original)

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


if __name__ == "__main__":
    unittest.main()
