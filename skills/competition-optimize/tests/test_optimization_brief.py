from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
archive = importlib.import_module("candidate_archive")


class OptimizationBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "archive.jsonl"
        self.records: dict[str, dict] = {}

    def record(self, name: str, score: float | None = 1.0, route: str = "current",
               status: str = "runner_up", valid: bool = True, parent: str | None = None,
               role: str = "development", direction: str = "maximize", feedback: str = "",
               failure: str = "", comparison: dict | None = None, reuse: str | None = None,
               result: bool = True) -> dict:
        folder = self.root / name
        folder.mkdir()
        source = folder / "solution.py"
        source.write_text(f"def solve(): return {name!r}\n", encoding="utf-8")
        if reuse:
            source.write_bytes(Path(self.records[reuse]["artifact_paths"]["source"]).read_bytes())
        result_path = folder / "result.json"
        receipt = {"status": "success" if valid else "failed", "valid": valid,
                   "candidate_hash": archive.hash_path(source), "evaluator_hash": "e" * 64,
                   "workload_hash": "w" * 64, "score_model_hash": "m" * 64,
                   "stage": "full", "score": {"kind": "official_metric" if score is not None else "unknown",
                                               "metric": "score", "direction": direction, "value": score,
                                               "components": {"quality": 0.8, "runtime": 2.0}},
                   "elapsed_seconds": 2.0,
                   "evaluation": {"config_hash": "c" * 64, "runtime_environment": {"python": "fixture"}}}
        for key, value in (comparison or {}).items():
            if key in {"config_hash", "runtime_environment"}:
                receipt["evaluation"][key] = value
            else:
                receipt[key] = value
        result_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        arguments = ["record", "--archive", str(self.path), "--candidate-id", name,
                     "--source", str(source), "--route", route, "--status", status,
                     "--mechanism", f"implementation-{name}"]
        if result:
            arguments += ["--result", str(result_path)]
        else:
            arguments += ["--valid", "--objective-value", str(score), "--objective-direction", direction,
                          "--objective-kind", "official_metric", "--objective-name", "score", "--stage", "full",
                          "--evaluator-hash", "e" * 64, "--workload-hash", "w" * 64, "--score-model-hash", "m" * 64]
        if parent:
            arguments += ["--parent", parent]
        if role:
            arguments += ["--role", role]
        if feedback:
            arguments += ["--feedback", feedback]
        if failure:
            arguments += ["--failure", failure]
        if reuse:
            arguments += ["--reuse-reason", "necessary repeated measurement"]
        entry = archive.record_candidate(archive.parser().parse_args(arguments))
        self.records[name] = entry
        return entry

    def brief(self, *arguments: str) -> dict:
        return archive.optimization_brief(archive.parser().parse_args(["brief", "--archive", str(self.path), *arguments]))

    def propose(self, name: str, parent: str) -> None:
        value = {"proposal_id": name, "parent_ids": [parent], "feedback_from": [parent],
                 "route": "next", "code_targets": [self.records[parent]["artifact_paths"]["source"]],
                 "basis": "Measured failure and inspected implementation", "change": "Replace the representation",
                 "expected_observation": "Lower residual error", "validation": "Same development evaluator",
                 "stop_condition": "Reserve or contradicted hypothesis"}
        path = self.root / (name + ".json")
        path.write_text(json.dumps(value), encoding="utf-8")
        archive.propose_candidate(archive.parser().parse_args(["propose", "--archive", str(self.path), "--proposal", str(path)]))

    def test_best_representatives_survive_weak_recent_history(self) -> None:
        self.record("best-current", 10, status="incumbent")
        self.record("alternative-best", 12, route="alternative")
        for number in range(8):
            self.record(f"weak-{number}", 2 + number / 10, status="rejected", feedback="No useful gain",
                        failure="Local change leaves the representation unchanged")
        value = self.brief("--recent", "2")
        self.assertEqual(value["best_development"], "alternative-best")
        self.assertEqual(value["routes"][0]["best"], "best-current")
        self.assertEqual(value["recent_current"], ["weak-6", "weak-7"])
        self.assertIn("best-current", value["candidates"])
        self.assertNotIn("weak-0", value["candidates"])
        self.assertEqual(value["candidates"]["weak-7"]["objective_gain_vs_best"], -9.3)
        self.assertIn("representation", value["candidates"]["weak-7"]["failure_mechanism"])

    def test_alternatives_rank_by_matched_objective_not_trial_count(self) -> None:
        self.record("few-weak", 9, "few", direction="minimize")
        self.record("many-best", 1, "many", direction="minimize")
        for number in range(5):
            self.record(f"many-{number}", 5, "many", direction="minimize")
        self.record("current", 4, direction="minimize")
        value = self.brief("--routes", "2")
        self.assertEqual([route["route"] for route in value["routes"]], ["current", "many"])
        self.assertEqual(value["best_development"], "many-best")
        self.assertEqual(value["omitted"]["routes"], 1)

    def test_each_comparison_dependency_is_scoped(self) -> None:
        self.record("anchor", 1)
        for number, comparison in enumerate([{"evaluator_hash": "other"}, {"workload_hash": "other"},
                                             {"score_model_hash": "other"}, {"stage": "short"},
                                             {"config_hash": "other"}, {"runtime_environment": {"python": "other"}}]):
            self.record(f"foreign-{number}", 100, route=f"foreign-{number}", comparison=comparison)
        value = self.brief("--anchor", "anchor")
        self.assertEqual(value["best_development"], "anchor")
        self.assertEqual(set(value["candidates"]), {"anchor"})
        self.assertEqual(value["omitted"]["other_development_comparisons"], 6)

    def test_confirmation_neither_changes_brief_nor_requires_artifacts(self) -> None:
        self.record("baseline", 1)
        before = self.brief()
        confirmation = self.record("confirmation", 100, route="confirmation-only", role="confirmation")
        Path(confirmation["artifact_paths"]["source"]).unlink()
        Path(confirmation["result"]["result_path"]).unlink()
        self.assertEqual(self.brief(), before)
        with self.assertRaises(archive.ArchiveFailure) as caught:
            self.brief("--anchor", "confirmation")
        self.assertEqual(caught.exception.kind, "confirmation_feedback")

    def test_invalid_latest_keeps_previous_best_and_failure_feedback(self) -> None:
        self.record("valid", 3)
        self.record("broken", 100, status="rejected", valid=False,
                    feedback="Implementation failed before the full comparison", failure="Decoder violates capacity")
        value = self.brief()
        self.assertEqual(value["anchor_candidate"], "broken")
        self.assertEqual(value["best_development"], "valid")
        self.assertEqual(value["routes"][0]["latest_failure"], "broken")
        self.assertIsNone(value["candidates"]["broken"]["objective_gain_vs_best"])

    def test_unknown_score_preserves_components_without_ranking(self) -> None:
        self.record("unknown", None)
        value = self.brief()
        self.assertIsNone(value["best_development"])
        self.assertIsNone(value["routes"][0]["best"])
        self.assertEqual(value["candidates"]["unknown"]["objective"]["components"], {"quality": 0.8, "runtime": 2.0})

    def test_changed_selected_result_or_snapshot_blocks_reuse(self) -> None:
        entry = self.record("candidate", 3)
        for field, kind in [("result", "result_changed"), ("source", "parent_artifact_changed")]:
            path = Path(entry["result"]["result_path"] if field == "result" else entry["artifact_paths"]["source"])
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(field=field), self.assertRaises(archive.ArchiveFailure) as caught:
                self.brief()
            self.assertEqual(caught.exception.kind, kind)
            path.write_bytes(original)

    def test_old_unselected_artifact_is_not_rehashed_or_loaded(self) -> None:
        old = self.record("old-low", 1)
        self.record("best", 10)
        for number in range(6):
            self.record(f"later-{number}", 5)
        Path(old["artifact_paths"]["source"]).unlink()
        Path(old["result"]["result_path"]).unlink()
        with mock.patch.object(archive, "verify_result", wraps=archive.verify_result) as results, \
                mock.patch.object(archive, "verify_artifacts", wraps=archive.verify_artifacts) as snapshots:
            value = self.brief("--recent", "2")
        displayed = set(value["candidates"])
        self.assertEqual(results.call_count, len(displayed))
        self.assertEqual(snapshots.call_count, len(displayed))
        self.assertNotIn("old-low", displayed)

    def test_pending_details_recover_code_and_feedback_without_duplicate_cards(self) -> None:
        self.record("parent", 1, feedback="Remaining nonlinear residuals")
        self.propose("p0", "parent")
        self.propose("p1", "parent")
        self.propose("p2", "parent")
        value = self.brief("--recent", "2")
        self.assertEqual(value["pending_proposals"], ["p0", "p1", "p2"])
        self.assertEqual([p["proposal_id"] for p in value["pending_details"]], ["p1", "p2"])
        self.assertEqual(value["pending_details"][0]["code_targets"][0]["path"], self.records["parent"]["artifact_paths"]["source"])
        self.assertEqual(set(value["candidates"]), {"parent"})
        self.assertEqual(value["omitted"]["pending_details"], 1)
        archive.stop_proposal(archive.parser().parse_args(["stop", "--archive", str(self.path), "--proposal-id", "p1",
                                                          "--reason", "Superseded proposal"]))
        self.assertEqual(self.brief()["pending_proposals"], ["p0", "p2"])

    def test_pending_other_comparison_remains_visible_without_its_scores(self) -> None:
        self.record("old-parent", 100, comparison={"workload_hash": "old"})
        self.propose("old-pending", "old-parent")
        self.record("new-parent", 1)
        self.propose("new-pending", "new-parent")
        value = self.brief()
        self.assertEqual(value["pending_proposals"], ["old-pending", "new-pending"])
        self.assertEqual([p["proposal_id"] for p in value["pending_details"]], ["new-pending"])
        self.assertNotIn("old-parent", value["candidates"])

    def test_different_route_successor_supersedes_old_unresolved_opportunity(self) -> None:
        self.record("promising", 1, status="promising", feedback="Needs a complete decoder")
        self.record("successor", 2, route="different", parent="promising")
        value = self.brief("--anchor", "promising")
        self.assertIsNone(value["routes"][0]["unresolved"])

    def test_repetitions_do_not_add_implementations_or_select_lucky_best(self) -> None:
        self.record("baseline", 2)
        self.record("repeat", 100, reuse="baseline", parent="baseline")
        value = self.brief()
        self.assertEqual(value["best_development"], "baseline")
        self.assertEqual(value["routes"][0]["distinct_implementations"], 1)
        self.assertEqual(value["routes"][0]["measurements"], 2)
        self.assertEqual(value["recent_current"], ["baseline"])
        self.assertEqual(value["candidates"]["repeat"]["reused_from"], ["baseline"])

    def test_renaming_route_does_not_turn_repetition_into_a_best_representative(self) -> None:
        self.record("baseline", 2)
        self.record("repeat-renamed", 100, route="renamed", reuse="baseline")
        value = self.brief()
        self.assertEqual(value["best_development"], "baseline")
        self.assertIsNone(value["routes"][0]["best"])
        self.assertIsNone(value["candidates"]["repeat-renamed"]["objective_gain_vs_best"])

    def test_legacy_unchecked_result_is_labeled_without_inventing_verification(self) -> None:
        self.record("legacy", 1, result=False)
        value = self.brief()["candidates"]["legacy"]
        self.assertEqual(value["identity_checks"]["result_bytes"], "not_recorded")
        self.assertEqual(value["identity_checks"]["snapshot_bytes"], "checked")

    def test_cli_rejects_bad_limits_empty_archive_and_unknown_anchor(self) -> None:
        for extra, error in [([], "empty_archive"), (["--recent", "0"], "invalid_config"),
                             (["--routes", "0"], "invalid_config")]:
            with self.subTest(extra=extra):
                run = subprocess.run([sys.executable, str(SCRIPTS / "candidate_archive.py"), "brief",
                                      "--archive", str(self.path), *extra], capture_output=True, text=True, timeout=15)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(json.loads(run.stderr)["error"]["type"], error)
        self.record("baseline", 1)
        with self.assertRaises(archive.ArchiveFailure) as caught:
            self.brief("--anchor", "missing")
        self.assertEqual(caught.exception.kind, "unknown_candidate")

    def test_brief_does_not_mutate_archive_or_evaluation_files(self) -> None:
        self.record("baseline", 1)
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.brief()
        self.assertEqual({path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}, before)


if __name__ == "__main__":
    unittest.main()
