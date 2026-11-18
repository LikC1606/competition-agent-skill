from __future__ import annotations

import json
import copy
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codex_invocation import CodexInvocation


class CodexInvocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.message = self.directory / "message.json"
        self.events = self.directory / "events.jsonl"
        self.events.write_text(json.dumps({"type": "turn.completed"}) + "\n")
        self.receipt = {"status": "continue", "summary": "Measured the candidate",
                        "next_action": "Inspect the paired result", "stop_reason": "",
                        "evidence": ["runs/candidate/result.json"]}

    def observe(self, **result):
        return CodexInvocation.observe(self.directory, {"returncode": 0, **result}, quarantined=False)

    def test_receipt_delivery_is_only_for_successful_work_with_a_saved_session(self):
        self.events.write_text(json.dumps({"type": "thread.started", "thread_id": "work-session"}) +
                               "\n" + json.dumps({"type": "turn.completed"}) + "\n")
        self.message.write_text("Composing the receipt now.")
        self.assertTrue(self.observe().needs_receipt)
        for result in ({"returncode": 7}, {"error": "watchdog expired"}):
            self.assertFalse(self.observe(**result).needs_receipt)
        self.assertFalse(CodexInvocation.observe(self.directory, {"returncode": 0},
                                                quarantined=True).needs_receipt)
        self.message.write_text(json.dumps(self.receipt))
        self.assertFalse(self.observe().needs_receipt)
        self.message.unlink()
        self.events.write_text(json.dumps({"type": "turn.completed"}) + "\n")
        self.assertFalse(self.observe().needs_receipt)

    def test_receipt_delivery_forks_exact_work_session_with_frozen_schema_and_model(self):
        turn = {"number": 4, "command": ["bound-deepseek", "exec", "--model", "deepseek-flash"],
                "instruction_snapshot": {"receipt_schema_path": "/frozen/receipt.schema.json"}}
        command = CodexInvocation.receipt_command(turn, self.directory, "work-session")
        self.assertEqual(command[:3], ["bound-deepseek", "exec", "fork"])
        self.assertEqual(command[-2:], ["work-session", "-"])
        self.assertEqual(command[command.index("--model") + 1], "deepseek-flash")
        self.assertEqual(command[command.index("--output-schema") + 1], "/frozen/receipt.schema.json")
        self.assertEqual(Path(command[command.index("-o") + 1]),
                         self.directory / "turns/000004/receipt/message.json")

    @unittest.skipUnless(shutil.which("bash") and shutil.which("head"), "Requires Bash and head")
    def test_fresh_and_resumed_commands_preserve_pipeline_failure_using_native_bash(self):
        state = {"model": "deepseek-flash", "agent_bin": "codex", "session_id": None,
                 "next_mode": "improve", "workspace": str(self.directory),
                 "archive": str(self.directory / "archive.jsonl"), "sandbox": "workspace-write"}
        cases = [("raise RuntimeError('failed producer')", 1),
                 ("print('completed')", 0), ("print('Traceback is ordinary output')", 0)]
        for session in (None, "existing-session"):
            command = CodexInvocation.command({**state, "session_id": session}, self.directory, 1)
            key, value = command[command.index("--config") + 1].split("=", 1)
            self.assertEqual(key, "shell_environment_policy.set.SHELLOPTS")
            environment = {**os.environ, "SHELLOPTS": json.loads(value)}
            for source, expected in cases:
                with self.subTest(session=session, source=source):
                    pipeline = f"{shlex.quote(sys.executable)} -c {shlex.quote(source)} 2>&1 | head -60"
                    result = subprocess.run(["bash", "-lc", pipeline], env=environment,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, expected, result.stderr)

    def test_terminal_receipt_accepts_provider_preamble_without_changing_raw_output(self):
        for prefix in ("", "All work is recorded. Receipt follows.\n\n",
                       "Everything is consistent: 40 candidates, 41 proposals.\n\n"):
            with self.subTest(prefix=prefix):
                raw = (prefix + json.dumps(self.receipt) + "\n").encode()
                self.message.write_bytes(raw)
                outcome = self.observe()
                self.assertEqual(outcome.receipt, self.receipt)
                self.assertEqual(outcome.error, "")
                self.assertEqual(self.message.read_bytes(), raw)

    def test_optional_decision_state_and_standalone_correction_keep_their_boundaries(self):
        receipt = {**self.receipt, "research_state": {
            "status": "open", "route": "source", "question": "Is group history deployable?",
            "alternatives": ["Known entities", "Unseen entities"],
            "missing_evidence": "Read official inference conditions.",
            "answer_actions": [{"observation": "Entities are unseen", "action": "Use feature-only structure."}],
            "evidence": []}, "corrections": [{
                "key": "group-history", "claim": "The gain is conditional.",
                "conditions": "Only the tested development overlap.", "limitations": "Test overlap is unknown.",
                "reopen_when": "Official conditions establish labelled peers.", "evidence": ["runs/result.json"]}]}
        self.message.write_text(json.dumps(receipt))
        self.assertEqual(self.observe().receipt, receipt)
        for change in (lambda x: x["research_state"].update(status="proved"),
                       lambda x: x["research_state"].update(alternatives=[]),
                       lambda x: x["research_state"].update(answer_actions=[{"observation": "yes"}]),
                       lambda x: x["corrections"][0].update(limitations=" "),
                       lambda x: x["corrections"][0].update(evidence=[]),
                       lambda x: x["corrections"].append(copy.deepcopy(x["corrections"][0]))):
            value = copy.deepcopy(receipt)
            change(value)
            self.message.write_text(json.dumps(value))
            self.assertIsNone(self.observe().receipt)
        self.message.write_text(json.dumps({**self.receipt, "research_state": None, "corrections": []}))
        self.assertIsNotNone(self.observe().receipt)

    def test_working_selection_is_optional_but_requires_a_scoped_reason_and_evidence(self):
        selection = {"candidate_id": "measured", "reason": "Preferred under the declared comparison.",
                     "limitations": "Development evidence only.", "evidence": ["runs/measured/result.json"]}
        for value in (selection, None):
            receipt = {**self.receipt, "working_selection": value}
            self.message.write_text(json.dumps(receipt))
            self.assertEqual(self.observe().receipt, receipt)
        for value in ({**selection, "evidence": []}, {**selection, "limitations": ""},
                      {**selection, "value": 999}, "measured"):
            self.message.write_text(json.dumps({**self.receipt, "working_selection": value}))
            self.assertIsNone(self.observe().receipt)

    def test_explicit_withdrawal_needs_a_reason_and_evidence_without_a_replacement_claim(self):
        withdrawal = {"key": "population-size", "status": "withdrawn",
                      "reason": "The count describes source entries; training size is unknown.",
                      "evidence": ["saved/source.json#/quantities/0"]}
        receipt = {**self.receipt, "corrections": [withdrawal]}
        self.message.write_text(json.dumps(receipt))
        self.assertEqual(self.observe().receipt, receipt)
        for change in (lambda x: x["corrections"][0].update(status="verified"),
                       lambda x: x["corrections"][0].update(reason=" "),
                       lambda x: x["corrections"][0].update(evidence=[]),
                       lambda x: x["corrections"][0].update(claim="Unsupported replacement"),
                       lambda x: x["corrections"].append(copy.deepcopy(x["corrections"][0]))):
            variant = copy.deepcopy(receipt)
            change(variant)
            self.message.write_text(json.dumps(variant))
            self.assertIsNone(self.observe().receipt)

    def test_incomplete_ambiguous_and_nonterminal_json_is_rejected(self):
        valid = json.dumps(self.receipt)
        for message in ("Receipt follows.\n" + valid[:-1], valid + "\n" + valid,
                        "Receipt follows.\n{}\n" + valid,
                        "Receipt follows.\n" + valid + "\nDone.",
                        "[]\n" + valid, "[" + valid + "]", "No receipt"):
            with self.subTest(message=message):
                self.message.write_text(message)
                outcome = self.observe()
                self.assertIsNone(outcome.receipt)
                self.assertTrue(outcome.error)

    def test_terminal_fenced_receipt_accepts_provider_wrappers_without_changing_raw_output(self):
        receipt = {**self.receipt, "summary": "完成比较；原文包含 ``` 和 {符号}，保持不变"}
        body = json.dumps(receipt, indent=2, ensure_ascii=False)
        variants = [("", "```json", "```"), ("Receipt follows.\n\n", "```json", "```"),
                    ("Receipt follows.\n", "```", "```"), ("", "~~~json", "~~~"),
                    ("", "````JSON", "`````"), ("", "  ``` json  ", "  ```  ")]
        for prefix, opening, closing in variants:
            with self.subTest(opening=opening, prefix=prefix):
                raw = (prefix + opening + "\n" + body + "\n" + closing + "\n").encode()
                self.message.write_bytes(raw)
                outcome = self.observe()
                self.assertEqual(outcome.receipt, receipt)
                self.assertEqual(outcome.error, "")
                self.assertEqual(self.message.read_bytes(), raw)

    def test_fence_does_not_hide_incomplete_multiple_or_nonterminal_objects(self):
        body = json.dumps(self.receipt, indent=2)
        fenced = "```json\n" + body + "\n```"
        variants = ["```json\n" + body, "```json\n" + body[:-1] + "\n```",
                    "```json\n" + body + "\n~~~", "````json\n" + body + "\n```",
                    fenced + "\nDone.", fenced + "\n" + fenced,
                    "Receipt follows.\n{}\n" + fenced, body + "\n" + fenced,
                    "```json\n" + body + "\n" + body + "\n```",
                    "```python\n" + body + "\n```", "[]\n" + fenced]
        for message in variants:
            with self.subTest(message=message):
                self.message.write_text(message)
                outcome = self.observe()
                self.assertIsNone(outcome.receipt)
                self.assertTrue(outcome.error)

    def test_fenced_receipt_keeps_schema_and_invocation_requirements(self):
        body = json.dumps(self.receipt)
        self.message.write_text("```json\n" + body + "\n```\n")
        for result in [{"returncode": 7}, {"error": "worker cleanup failed"}]:
            with self.subTest(result=result):
                outcome = self.observe(**result)
                self.assertIsNone(outcome.receipt)
                self.assertTrue(outcome.error)
        self.events.write_text(json.dumps({"type": "turn.failed"}) + "\n")
        self.assertIsNone(self.observe().receipt)
        self.events.write_text(json.dumps({"type": "turn.completed"}) + "\n")
        outcome = CodexInvocation.observe(self.directory, {"returncode": 0}, quarantined=True)
        self.assertIsNone(outcome.receipt)
        self.assertIn("quarantined", outcome.error)
        for value in [{**self.receipt, "status": "success"}, {**self.receipt, "extra": "unexpected"},
                      {**self.receipt, "evidence": [7]}, [], {}]:
            with self.subTest(value=value):
                self.message.write_text("```json\n" + json.dumps(value) + "\n```\n")
                self.assertIsNone(self.observe().receipt)

    def test_preamble_does_not_bypass_receipt_schema(self):
        variants = [[], {}, {**self.receipt, "extra": "unexpected"},
                    {**self.receipt, "status": []}, {**self.receipt, "status": "success"},
                    {**self.receipt, "summary": None}, {**self.receipt, "evidence": [7]}]
        missing = dict(self.receipt)
        missing.pop("evidence")
        variants.append(missing)
        for receipt in variants:
            with self.subTest(receipt=receipt):
                self.message.write_text("Receipt follows.\n" + json.dumps(receipt))
                outcome = self.observe()
                self.assertIsNone(outcome.receipt)
                self.assertTrue(outcome.error)

    def test_preamble_does_not_override_process_failure_or_runtime_error(self):
        self.message.write_text("Receipt follows.\n" + json.dumps(self.receipt))
        for result in ({"returncode": 7}, {"error": "worker cleanup failed"}):
            with self.subTest(result=result):
                outcome = self.observe(**result)
                self.assertIsNone(outcome.receipt)
                self.assertTrue(outcome.error)

    def test_preamble_requires_successful_terminal_and_reconciled_archive(self):
        self.message.write_text("Receipt follows.\n" + json.dumps(self.receipt))
        for terminal in (None, "turn.failed"):
            with self.subTest(terminal=terminal):
                self.events.write_text(json.dumps({"type": terminal}) + "\n")
                outcome = self.observe()
                self.assertIsNone(outcome.receipt)
                self.assertIn("terminal event", outcome.error)
        self.events.write_text(json.dumps({"type": "turn.completed"}) + "\n")
        outcome = CodexInvocation.observe(self.directory, {"returncode": 0}, quarantined=True)
        self.assertIsNone(outcome.receipt)
        self.assertIn("quarantined", outcome.error)


if __name__ == "__main__":
    unittest.main()
