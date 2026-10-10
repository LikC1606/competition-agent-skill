from __future__ import annotations

import copy
import csv
import importlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
analyzer = importlib.import_module("analyze_prediction_errors")
evaluator = importlib.import_module("evaluate_predictions")


class PredictionErrorAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.truth = self.root / "truth.csv"
        self.truth.write_text("id,target\n001,0\n1,0\na,0\nb,0\n", encoding="utf-8")
        self.slices = self.root / "slices.csv"
        self.slices.write_text("id,regime,device\nb,easy,B\na,easy,A\n1,hard,B\n001,hard,A\n", encoding="utf-8")
        self.sequence = 0
        self.baseline = self.evaluate("id,prediction\nb,1\na,1\n1,4\n001,4\n")
        self.candidate = self.evaluate("id,prediction\n1,0\n001,0\na,2\nb,2\n")

    def evaluate(self, predictions: str, *extra: str) -> Path:
        self.sequence += 1
        source = self.root / f"prediction-{self.sequence}.csv"
        source.write_text(predictions, encoding="utf-8")
        output = self.root / f"evaluation-{self.sequence}"
        output.mkdir()
        args = evaluator.make_parser().parse_args([
            "--truth", str(self.truth), "--predictions", str(source), "--metric", "rmse",
            "--stage", "development", "--split-id", "dev", "--output-dir", str(output), *extra,
        ])
        result = evaluator.evaluate(args, output)
        path = output / "result.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        return path

    def arguments(self, output: Path, *extra: str) -> list[str]:
        return ["--baseline", str(self.baseline), "--candidate", str(self.candidate), "--truth", str(self.truth),
                "--output-dir", str(output), *extra]

    def analyze(self, *extra: str) -> tuple[dict, Path]:
        self.sequence += 1
        output = self.root / f"analysis-{self.sequence}"
        output.mkdir()
        args = analyzer.make_parser().parse_args(self.arguments(output, *extra))
        return analyzer.analyze(args, output), output

    def test_total_gain_with_slice_regression_is_visible_and_matches_hand_calculations(self) -> None:
        report, output = self.analyze("--slices", str(self.slices), "--slice-column", "regime",
                                      "--slice-column", "device", "--top-k", "1")
        comparison = report["aggregate_comparison"]
        self.assertAlmostEqual(comparison["baseline"]["score"], math.sqrt(8.5))
        self.assertAlmostEqual(comparison["candidate"]["score"], math.sqrt(2))
        self.assertEqual(comparison["metric_preference"], "candidate")
        self.assertEqual(report["case_preference_counts"], {"candidate": 2, "baseline": 2, "tie": 0})
        regimes = {row["value"]: row for row in report["slices"] if row["column"] == "regime"}
        self.assertEqual(regimes["hard"]["objective_improvement"], 4)
        self.assertEqual(regimes["easy"]["objective_improvement"], -1)
        self.assertAlmostEqual(regimes["easy"]["baseline_error_share"], 1 / 17)
        self.assertEqual(regimes["easy"]["candidate_error_share"], 1)
        self.assertEqual(report["error_share_kind"], "squared_error")
        self.assertEqual(report["largest_regressions"][0]["id"], "a")
        self.assertEqual(report["largest_candidate_errors"][0]["id"], "a")
        with (output / "cases.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row["id"] for row in rows], ["001", "1", "a", "b"])
        self.assertEqual(rows[0]["slice:regime"], "hard")
        self.assertEqual((output / "baseline.csv").read_bytes(), (self.baseline.parent / "predictions.csv").read_bytes())
        self.assertEqual((output / "slices.csv").read_bytes(), self.slices.read_bytes())

    def test_mae_shares_use_absolute_loss_and_zero_errors_have_zero_shares(self) -> None:
        self.baseline = self.evaluate("id,prediction\n001,4\n1,4\na,1\nb,1\n", "--metric", "mae")
        self.candidate = self.evaluate("id,prediction\n001,0\n1,0\na,0\nb,0\n", "--metric", "mae")
        report, _ = self.analyze("--slices", str(self.slices), "--slice-column", "regime")
        regimes = {row["value"]: row for row in report["slices"]}
        self.assertEqual(report["error_share_kind"], "absolute_error")
        self.assertAlmostEqual(regimes["hard"]["baseline_error_share"], 0.8)
        self.assertEqual(regimes["hard"]["candidate_error_share"], 0)
        self.assertEqual(report["aggregate_comparison"]["candidate"]["score"], 0)

    def test_binary_log_loss_uses_evaluation_clipping_and_case_improvements(self) -> None:
        self.truth.write_text("id,target\n001,0\n1,1\na,0\nb,1\n", encoding="utf-8")
        self.baseline = self.evaluate("id,prediction\n001,0.5\n1,0.5\na,0.5\nb,0.5\n",
                                      "--metric", "binary_log_loss", "--log-loss-epsilon", "0.01")
        self.candidate = self.evaluate("id,prediction\n001,0\n1,1\na,1\nb,0\n",
                                       "--metric", "binary_log_loss", "--log-loss-epsilon", "0.01")
        report, _ = self.analyze("--slices", str(self.slices), "--slice-column", "regime")
        regimes = {row["value"]: row for row in report["slices"]}
        self.assertAlmostEqual(regimes["hard"]["candidate_score"], -math.log(0.99))
        self.assertAlmostEqual(regimes["easy"]["candidate_score"], -math.log(0.01))
        self.assertEqual(report["per_case_error_kind"], "clipped_log_loss")
        self.assertEqual(report["case_preference_counts"], {"baseline": 2, "candidate": 2, "tie": 0})
        self.assertAlmostEqual(report["largest_regressions"][0]["candidate_error"], -math.log(0.01))

    def test_auc_reports_group_metrics_without_inventing_per_row_losses(self) -> None:
        self.truth.write_text("id,target\n001,0\n1,0\na,1\nb,1\n", encoding="utf-8")
        self.baseline = self.evaluate("id,prediction\n001,1\n1,1\na,1\nb,1\n", "--metric", "roc_auc")
        self.candidate = self.evaluate("id,prediction\n001,0\n1,0\na,1\nb,1\n", "--metric", "roc_auc")
        report, output = self.analyze("--slices", str(self.slices), "--slice-column", "regime",
                                      "--slice-column", "device")
        self.assertEqual(report["aggregate_comparison"]["objective_improvement"], 0.5)
        self.assertIsNone(report["case_preference_counts"])
        self.assertIsNone(report["per_case_error_kind"])
        self.assertEqual(report["largest_regressions"], [])
        regimes = [row for row in report["slices"] if row["column"] == "regime"]
        devices = [row for row in report["slices"] if row["column"] == "device"]
        for row in regimes:
            self.assertIsNone(row["candidate_score"])
            self.assertEqual(row["unavailable_reason"], "roc_auc_requires_both_classes")
        for row in devices:
            self.assertEqual(row["candidate_score"], 1)
            self.assertEqual(row["baseline_score"], 0.5)
            self.assertIsNone(row["candidate_error_share"])
        with (output / "cases.csv").open(encoding="utf-8", newline="") as stream:
            self.assertTrue(all(row["candidate_error"] == "" for row in csv.DictReader(stream)))

    def test_large_residuals_can_be_diagnosed_without_squaring_overflow(self) -> None:
        self.baseline = self.evaluate("id,prediction\n001,1e308\n1,1e308\na,0\nb,0\n")
        self.candidate = self.evaluate("id,prediction\n001,0\n1,0\na,1e308\nb,1e308\n")
        report, _ = self.analyze("--slices", str(self.slices), "--slice-column", "regime")
        regimes = {row["value"]: row for row in report["slices"]}
        self.assertEqual(regimes["hard"]["baseline_error_share"], 1)
        self.assertEqual(regimes["easy"]["candidate_error_share"], 1)
        self.assertEqual(regimes["hard"]["objective_improvement"], 1e308)
        json.dumps(report, allow_nan=False)

    def test_rmse_regressions_rank_squared_loss_increase_rather_than_absolute_increase(self) -> None:
        self.baseline = self.evaluate("id,prediction\n001,100\n1,0\na,0\nb,0\n")
        self.candidate = self.evaluate("id,prediction\n001,101\n1,2\na,0\nb,0\n")
        report, _ = self.analyze("--top-k", "2")
        self.assertEqual([row["id"] for row in report["largest_regressions"]], ["001", "1"])
        self.assertEqual(report["squared_error_scale"], 101)
        first, second = report["largest_regressions"]
        self.assertEqual(first["error_improvement"], -1)
        self.assertEqual(second["error_improvement"], -2)
        self.assertAlmostEqual(first["scaled_squared_error_improvement"], -201 / 101 ** 2)
        self.assertAlmostEqual(second["scaled_squared_error_improvement"], -4 / 101 ** 2)

    def test_error_tolerance_changes_diagnostic_counts_only(self) -> None:
        report, _ = self.analyze("--error-tie-epsilon", "10")
        self.assertEqual(report["case_preference_counts"]["tie"], 4)
        self.assertEqual(report["largest_regressions"], [])
        self.assertEqual(report["aggregate_comparison"]["metric_preference"], "candidate")

    def test_exploratory_diagnostics_reject_confirmation_results(self) -> None:
        self.baseline = self.evaluate("id,prediction\n001,1\n1,1\na,1\nb,1\n", "--stage", "confirmation")
        self.candidate = self.evaluate("id,prediction\n001,0\n1,0\na,0\nb,0\n", "--stage", "confirmation")
        with self.assertRaisesRegex(analyzer.AnalysisFailure, "development evaluations"):
            self.analyze()

    def test_truth_changes_and_prediction_corruption_fail(self) -> None:
        original_truth = self.truth.read_bytes()
        self.truth.write_bytes(original_truth + b"\n")
        with self.assertRaisesRegex(analyzer.AnalysisFailure, "Truth bytes differ"):
            self.analyze()
        self.truth.write_bytes(original_truth)
        (self.candidate.parent / "predictions.csv").write_text("id,prediction\nx,0\n", encoding="utf-8")
        with self.assertRaisesRegex(analyzer.ComparisonFailure, "snapshot differs"):
            self.analyze()

    def test_changed_evaluator_or_score_records_require_reevaluation(self) -> None:
        original_before = json.loads(self.baseline.read_text(encoding="utf-8"))
        original_after = json.loads(self.candidate.read_text(encoding="utf-8"))
        before, after = copy.deepcopy(original_before), copy.deepcopy(original_after)
        before["evaluator_hash"] = after["evaluator_hash"] = "0" * 64
        self.baseline.write_text(json.dumps(before), encoding="utf-8")
        self.candidate.write_text(json.dumps(after), encoding="utf-8")
        with self.assertRaisesRegex(analyzer.AnalysisFailure, "installed prediction evaluator"):
            self.analyze()
        self.baseline.write_text(json.dumps(original_before), encoding="utf-8")
        original_after["score"]["value"] = 0.25
        self.candidate.write_text(json.dumps(original_after), encoding="utf-8")
        with self.assertRaisesRegex(analyzer.AnalysisFailure, "Recomputed score differs"):
            self.analyze()

    def test_mismatched_metric_split_and_stage_are_rejected(self) -> None:
        for extra in [("--metric", "mae"), ("--split-id", "other"), ("--stage", "confirmation")]:
            self.candidate = self.evaluate("id,prediction\n001,0\n1,0\na,0\nb,0\n", *extra)
            with self.subTest(extra=extra), self.assertRaises(analyzer.ComparisonFailure):
                self.analyze()

    def test_malformed_or_incomplete_slice_inputs_fail(self) -> None:
        cases = [
            "id,regime\n001,hard\n1,hard\na,easy\n",
            "id,regime\n001,hard\n1,hard\na,easy\nb,easy\nx,easy\n",
            "id,regime\n001,hard\n001,hard\na,easy\nb,easy\n",
            "id,regime\n001,hard\n1, \na,easy\nb,easy\n",
            "id,regime,regime\n001,hard,hard\n",
            "id,regime\n001,hard,extra\n",
            "id,regime\n001\n",
        ]
        for text in cases:
            self.slices.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(analyzer.AnalysisFailure):
                self.analyze("--slices", str(self.slices), "--slice-column", "regime")

    def test_invalid_configuration_and_high_cardinality_slices_fail(self) -> None:
        cases = [
            ("--top-k", "0"), ("--top-k", "101"), ("--max-groups", "0"),
            ("--error-tie-epsilon", "nan"), ("--error-tie-epsilon", "-1"),
            ("--slices", str(self.slices)), ("--slice-column", "regime"),
            ("--slices", str(self.slices), "--slice-column", "regime", "--slice-column", "regime"),
            ("--slices", str(self.slices), "--slice-column", "id"),
            ("--slices", str(self.slices), "--slice-column", "missing"),
            ("--slices", str(self.slices), "--slice-column", "regime", "--max-groups", "1"),
        ]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(analyzer.AnalysisFailure):
                self.analyze(*extra)

    def test_custom_columns_and_utf8_bom_slice_metadata_work(self) -> None:
        self.truth.write_text("sample,label\n001,0\n1,0\n", encoding="utf-8")
        columns = ["--id-column", "sample", "--target-column", "label", "--prediction-column", "estimate"]
        self.baseline = self.evaluate("sample,estimate\n001,2\n1,2\n", *columns)
        self.candidate = self.evaluate("sample,estimate\n1,0\n001,0\n", *columns)
        self.slices.write_bytes(b"\xef\xbb\xbfsample,regime\n1,small\n001,large\n")
        report, _ = self.analyze("--slices", str(self.slices), "--slice-column", "regime")
        self.assertEqual(report["case_count"], 2)
        self.assertEqual(len(report["slices"]), 2)

    def test_cli_writes_full_report_and_refuses_overwrite(self) -> None:
        output = self.root / "cli-analysis"
        command = [sys.executable, str(SCRIPT_DIR / "analyze_prediction_errors.py"),
                   *self.arguments(output, "--slices", str(self.slices), "--slice-column", "regime")]
        first = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(first.returncode, 0, first.stderr)
        report = json.loads((output / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["selection_scope"], "development_diagnostics_only")
        self.assertEqual(report["aggregate_comparison"]["metric_preference"], "candidate")
        before = (output / "report.json").read_bytes()
        second = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(second.returncode, 2)
        self.assertEqual((output / "report.json").read_bytes(), before)

    def test_cli_failure_records_reason_without_success_artifacts(self) -> None:
        self.truth.write_text("changed", encoding="utf-8")
        output = self.root / "failed-analysis"
        completed = subprocess.run([sys.executable, str(SCRIPT_DIR / "analyze_prediction_errors.py"),
                                    *self.arguments(output)], capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 2)
        report = json.loads((output / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertIn("Truth bytes differ", report["error"]["message"])
        self.assertFalse((output / "cases.csv").exists())


if __name__ == "__main__":
    unittest.main()
