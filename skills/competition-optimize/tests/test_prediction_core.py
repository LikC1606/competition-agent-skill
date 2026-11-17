from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
evaluator = importlib.import_module("evaluate_predictions")
core = importlib.import_module("prediction_core")
batch = importlib.import_module("evaluate_prediction_batch")


class PredictionCoreTests(unittest.TestCase):
    def test_metrics_accept_lists_tuples_and_numpy_arrays_with_library_scores(self):
        import numpy as np
        from sklearn import metrics

        labels, values = [0, 1, 1, 0], [0.1, 0.9, 0.4, 0.4]
        cases = [("rmse", values, metrics.root_mean_squared_error(labels, values)),
                 ("mae", values, metrics.mean_absolute_error(labels, values)),
                 ("binary_log_loss", values, metrics.log_loss(labels, values)),
                 ("roc_auc", values, metrics.roc_auc_score(labels, values)),
                 ("accuracy", [0, 1, 0, 0], 0.75)]
        for metric, predictions, expected in cases:
            for container in (list, tuple, np.asarray):
                with self.subTest(metric=metric, container=container):
                    self.assertAlmostEqual(core.calculate_metric(metric, container(labels), container(predictions)),
                                           expected, places=14)

    def test_invalid_array_shapes_values_and_pairing_raise_prediction_failure(self):
        import numpy as np

        for labels, predictions in [(np.array([]), np.array([])),
                                    (np.array([1, 2]), np.array([1])),
                                    (np.array([[1, 2]]), np.array([[1, 2]])),
                                    ([[1], [2, 3]], [1, 2]), (1, 1),
                                    (np.array([1, np.nan]), [1, 2]),
                                    ([1, 2], np.array([1, np.inf])), (["bad"], [1])]:
            with self.subTest(labels=labels, predictions=predictions):
                with self.assertRaises(core.PredictionFailure) as raised:
                    core.calculate_metric("rmse", labels, predictions)
                self.assertEqual(raised.exception.kind, "invalid_score")

    def test_accuracy_requires_hard_binary_decisions(self):
        self.assertEqual(core.calculate_metric("accuracy", [0, 1, 1, 0], [0, 0, 1, 0]), 0.75)
        self.assertEqual(core.calculate_metric("accuracy", [1, 1], [1, 1]), 1)
        for labels, predictions in [([0, 1], [0.1, 0.8]), ([0, 2], [0, 1])]:
            with self.assertRaises(core.PredictionFailure):
                core.calculate_metric("accuracy", labels, predictions)

    def test_accuracy_case_profile_and_result_domain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth, predictions = root / "truth.csv", root / "predictions-source.csv"
            truth.write_text("id,target\na,0\nb,1\nc,1\n")
            predictions.write_text("id,prediction\nc,1\na,0\nb,0\n")
            result = evaluator.evaluate(evaluator.EvaluationSpec(
                truth, predictions, "accuracy", "development", "fixture", case_profile=True), root)
            path = root / "result.json"
            path.write_text(json.dumps(result))
            self.assertEqual(core.load_result(path)["score"]["value"], 2 / 3)
            self.assertEqual(result["case_profile"], {"metric": "zero_one_error", "direction": "minimize",
                                                     "cases": {"a": 0, "b": 1, "c": 0}})
            result["score"]["value"] = 1.5
            path.write_text(json.dumps(result))
            with self.assertRaisesRegex(core.ComparisonFailure, "outside"):
                core.load_result(path)

    def test_core_and_evidence_import_without_loading_comparison_cli(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "import prediction_core, prediction_evidence; "
                "assert 'compare_prediction_results' not in sys.modules; "
                "assert not {'numpy', 'sklearn', 'scipy'} & sys.modules.keys()")
        process = subprocess.run([sys.executable, "-B", "-c", code, str(SCRIPTS)],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_extracted_scorer_changes_invalidate_installed_evidence(self):
        original = Path.read_bytes
        before = evaluator.evaluator_fingerprint()

        def changed(path):
            data = original(path)
            return data + b"\n# changed scorer\n" if path.name == "prediction_core.py" else data

        with patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(before, evaluator.evaluator_fingerprint())

    def test_numeric_dependency_change_invalidates_evaluator_identity(self):
        original = core.importlib.metadata.version
        before = evaluator.evaluator_fingerprint()
        with patch.object(core.importlib.metadata, "version", side_effect=lambda name:
                          "different-version" if name == "scikit-learn" else original(name)):
            self.assertNotEqual(before, evaluator.evaluator_fingerprint())

    def test_typed_evaluation_and_batch_keep_identical_case_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth, prediction = root / "truth.csv", root / "prediction.csv"
            truth.write_text("id,target\na,1\nb,3\n")
            prediction.write_text("id,prediction\nb,4\na,1\n")
            single, group = root / "single", root / "batch"
            single.mkdir()
            group.mkdir()
            spec = evaluator.EvaluationSpec(truth, prediction, "rmse", "development",
                                            "same-split", case_profile=True)
            result = evaluator.evaluate(spec, single)
            (single / "result.json").write_text(json.dumps(result))
            loaded = core.load_result(single / "result.json")
            args = batch.make_parser().parse_args([
                "--truth", str(truth), "--candidate", "one", str(prediction),
                "--metric", "rmse", "--stage", "development", "--split-id", "same-split",
                "--case-profile", "--output-dir", str(group)])
            report = batch.run_batch(args, group, batch.validate_candidates(args.candidate, None))
            combined = core.load_result(Path(report["candidates"][0]["result"]))
            self.assertEqual(loaded["case_profile"], combined["case_profile"])
            self.assertEqual(core.compare(loaded, combined, 0)["metric_preference"], "tie")


if __name__ == "__main__":
    unittest.main()
