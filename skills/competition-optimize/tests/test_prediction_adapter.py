from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
evaluator = importlib.import_module("evaluate_predictions")
comparator = importlib.import_module("compare_prediction_results")


class PredictionMetricTests(unittest.TestCase):
    def test_regression_scores_match_hand_calculations_and_handle_large_residuals(self) -> None:
        truth, predictions = [10.0, 20.0, 30.0], [11.0, 22.0, 28.0]
        self.assertAlmostEqual(evaluator.calculate_metric("rmse", truth, predictions), math.sqrt(3))
        self.assertAlmostEqual(evaluator.calculate_metric("mae", truth, predictions), 5 / 3)
        self.assertEqual(evaluator.calculate_metric("rmse", [1e308, 1e308], [0, 0]), 1e308)
        self.assertEqual(evaluator.calculate_metric("mae", [1e308, 1e308], [0, 0]), 1e308)
        self.assertEqual(evaluator.calculate_metric("rmse", truth, truth), 0)

    def test_binary_log_loss_clipping_and_known_scores(self) -> None:
        self.assertAlmostEqual(evaluator.calculate_metric("binary_log_loss", [0, 1], [0.2, 0.8]), -math.log(0.8))
        self.assertAlmostEqual(evaluator.calculate_metric("binary_log_loss", [0, 1], [0, 1]), 0, places=12)
        self.assertAlmostEqual(evaluator.calculate_metric("binary_log_loss", [0, 1], [1, 0], 1e-4), -math.log(1e-4))

    def test_auc_matches_independent_pairwise_oracle_with_ties(self) -> None:
        rng = random.Random(721)
        for _ in range(40):
            truth = [0, 1] + [rng.randrange(2) for _ in range(8)]
            predictions = [rng.randrange(-2, 3) for _ in truth]
            positive = [pred for label, pred in zip(truth, predictions) if label == 1]
            negative = [pred for label, pred in zip(truth, predictions) if label == 0]
            expected = sum(1 if pos > neg else 0.5 if pos == neg else 0
                           for pos in positive for neg in negative) / (len(positive) * len(negative))
            self.assertAlmostEqual(evaluator.calculate_metric("roc_auc", truth, predictions), expected)
        self.assertEqual(evaluator.calculate_metric("roc_auc", [0, 1], [5, 5]), 0.5)
        self.assertEqual(evaluator.calculate_metric("roc_auc", [0, 1], [1, 0]), 0)

    def test_rejects_invalid_domains_non_finite_values_and_overflowing_residuals(self) -> None:
        cases = [
            ("roc_auc", [1, 1], [0.2, 0.9]),
            ("roc_auc", [0, 2], [0.2, 0.9]),
            ("binary_log_loss", [0, 1], [-0.1, 0.9]),
            ("binary_log_loss", [0, 1], [0.1, 1.1]),
            ("rmse", [1], [math.nan]),
            ("mae", [1], [math.inf]),
            ("rmse", [1e308], [-1e308]),
            ("mae", [], []),
        ]
        for metric, truth, predictions in cases:
            with self.subTest(metric=metric, predictions=predictions), self.assertRaises(evaluator.PredictionFailure):
                evaluator.calculate_metric(metric, truth, predictions)
        for epsilon in [0, -1, 0.5, math.nan, math.inf, 1e-100]:
            with self.subTest(epsilon=epsilon), self.assertRaises(evaluator.PredictionFailure):
                evaluator.calculate_metric("binary_log_loss", [0, 1], [0, 1], epsilon)


class PredictionArtifactTests(unittest.TestCase):
    def test_csv_preserves_ids_and_accepts_utf8_bom(self) -> None:
        raw = "\ufeffid,target,extra\n001,2,ok\n1,3,ok\n".encode("utf-8")
        self.assertEqual(evaluator.read_values(raw, "id", "target", "truth"), {"001": 2, "1": 3})

    def test_rejects_duplicate_ids_columns_bad_values_and_malformed_rows(self) -> None:
        cases = [
            b"id,target\na,1\na,2\n", b"id,target\n ,1\n",
            b"id,target,target\na,1,2\n", b"id,target\na,1,extra\n",
            b"id,target\na\n", b"id,target\na,nan\n", b"id,target\na,true\n",
            b"id,target\n", b"id,score\na,1\n", b"id,target\na,inf\n",
        ]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(evaluator.PredictionFailure):
                evaluator.read_values(raw, "id", "target", "truth")


class PredictionWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.truth = self.root / "truth.csv"
        self.predictions = self.root / "candidate.csv"
        self.truth.write_text("id,target\na,10\nb,20\nc,30\n", encoding="utf-8")
        self.predictions.write_text("id,prediction\nc,30.5\na,10.5\nb,19.5\n", encoding="utf-8")
        self.sequence = 0

    def arguments(self, output: Path, *extra: str) -> list[str]:
        return ["--truth", str(self.truth), "--predictions", str(self.predictions),
                "--metric", "rmse", "--stage", "development", "--split-id", "frozen-dev",
                "--output-dir", str(output), *extra]

    def evaluate(self, *extra: str) -> dict:
        self.sequence += 1
        output = self.root / f"run-{self.sequence}"
        output.mkdir()
        args = evaluator.make_parser().parse_args(self.arguments(output, *extra))
        result = evaluator.evaluate(args, output)
        result_path = output / "result.json"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        return comparator.load_result(result_path)

    def test_id_alignment_snapshot_and_comparison_choose_lower_rmse(self) -> None:
        self.predictions.write_text("id,prediction\na,11\nb,22\nc,28\n", encoding="utf-8")
        baseline = self.evaluate()
        self.predictions.write_text("id,prediction\nc,30.5\na,10.5\nb,19.5\n", encoding="utf-8")
        candidate = self.evaluate()
        self.assertAlmostEqual(candidate["score"]["value"], 0.5)
        snapshot = Path(candidate["artifacts"][0]).read_bytes()
        self.assertEqual(hashlib.sha256(snapshot).hexdigest(), candidate["candidate_hash"])
        self.assertEqual(candidate["score"]["kind"], "proxy")
        self.assertIn("training_leakage", candidate["unchecked_rules"])
        comparison = comparator.compare(baseline, candidate, 1e-12)
        self.assertEqual(comparison["metric_preference"], "candidate")
        self.assertGreater(comparison["objective_improvement"], 0)
        self.assertLess(comparison["raw_score_delta"], 0)

    def test_comparison_chooses_higher_auc_and_handles_ties(self) -> None:
        self.truth.write_text("id,target\na,0\nb,1\nc,1\n", encoding="utf-8")
        self.predictions.write_text("id,prediction\na,0.9\nb,0.1\nc,0.2\n", encoding="utf-8")
        baseline = self.evaluate("--metric", "roc_auc")
        self.predictions.write_text("id,prediction\na,0.1\nb,0.9\nc,0.8\n", encoding="utf-8")
        candidate = self.evaluate("--metric", "roc_auc")
        self.assertEqual(comparator.compare(baseline, candidate, 0)["metric_preference"], "candidate")
        self.assertEqual(comparator.compare(candidate, candidate, 0)["metric_preference"], "tie")
        self.assertEqual(comparator.compare(candidate, baseline, 0)["metric_preference"], "baseline")
        self.assertEqual(comparator.compare(baseline, candidate, 1)["metric_preference"], "tie")

    def test_rejects_incomplete_or_extra_prediction_ids(self) -> None:
        for text in ["id,prediction\na,10\nb,20\n", "id,prediction\na,10\nb,20\nc,30\nx,0\n"]:
            self.predictions.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaisesRegex(evaluator.PredictionFailure, "IDs differ"):
                self.evaluate()

    def test_rejects_metric_stage_split_truth_and_score_kind_mismatches(self) -> None:
        baseline = self.evaluate()
        changes = [
            ("--metric", "mae"), ("--stage", "confirmation"),
            ("--split-id", "other-dev"), ("--score-kind", "official_metric"),
        ]
        for extra in changes:
            with self.subTest(extra=extra), self.assertRaises(comparator.ComparisonFailure):
                comparator.compare(baseline, self.evaluate(*extra), 0)
        self.truth.write_text("id,target\na,11\nb,20\nc,30\n", encoding="utf-8")
        with self.assertRaises(comparator.ComparisonFailure):
            comparator.compare(baseline, self.evaluate(), 0)

    def test_result_reader_rejects_partial_failed_or_inconsistent_metadata(self) -> None:
        original = self.evaluate()
        mutations = [
            lambda r: r.update(status="failed"),
            lambda r: r["evaluation"].update(completed_cases=2),
            lambda r: r["score"].update(value=True),
            lambda r: r["score"].update(value=math.nan),
            lambda r: r["score"].update(direction="maximize"),
            lambda r: r["evaluation"].update(split_hash="0" * 64),
            lambda r: r["evaluation"]["configuration"].update(split_id="edited"),
        ]
        path = self.root / "edited.json"
        for mutate in mutations:
            value = copy.deepcopy(original)
            mutate(value)
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(comparator.ComparisonFailure):
                comparator.load_result(path)

    def test_invalid_comparison_tolerances_are_rejected(self) -> None:
        result = self.evaluate()
        for epsilon in [-1, math.nan, math.inf]:
            with self.subTest(epsilon=epsilon), self.assertRaises(comparator.ComparisonFailure):
                comparator.compare(result, result, epsilon)

    def test_result_reader_rejects_changed_prediction_snapshot(self) -> None:
        result = self.evaluate()
        snapshot = Path(result["artifacts"][0])
        snapshot.write_text("id,prediction\na,0\nb,0\nc,0\n", encoding="utf-8")
        with self.assertRaisesRegex(comparator.ComparisonFailure, "snapshot differs"):
            comparator.load_result(snapshot.parent / "result.json")

    def test_cli_success_and_refusal_to_overwrite_previous_evaluation(self) -> None:
        output = self.root / "cli-run"
        command = [sys.executable, str(SCRIPT_DIR / "evaluate_predictions.py"), *self.arguments(output)]
        first = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertAlmostEqual(json.loads(first.stdout)["score"]["value"], 0.5)
        before = (output / "result.json").read_bytes()
        second = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(json.loads(second.stderr)["status"], "failed")
        self.assertEqual((output / "result.json").read_bytes(), before)

    def test_cli_failure_records_no_score_and_cannot_be_compared(self) -> None:
        self.predictions.write_text("id,prediction\na,10\n", encoding="utf-8")
        output = self.root / "invalid-run"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "evaluate_predictions.py"), *self.arguments(output)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(completed.returncode, 2)
        failed = json.loads((output / "result.json").read_text(encoding="utf-8"))
        self.assertIsNone(failed["score"]["value"])
        self.assertEqual(failed["error"]["type"], "id_mismatch")
        with self.assertRaises(comparator.ComparisonFailure):
            comparator.load_result(output / "result.json")

    def test_comparator_cli_records_comparison_and_preserves_existing_output(self) -> None:
        baseline = self.evaluate()
        candidate = self.evaluate()
        baseline_path = Path(baseline["artifacts"][0]).parent / "result.json"
        candidate_path = Path(candidate["artifacts"][0]).parent / "result.json"
        output = self.root / "comparison.json"
        command = [sys.executable, str(SCRIPT_DIR / "compare_prediction_results.py"),
                   "--baseline", str(baseline_path), "--candidate", str(candidate_path), "--output", str(output)]
        first = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["metric_preference"], "tie")
        before = output.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(second.returncode, 2)
        self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
