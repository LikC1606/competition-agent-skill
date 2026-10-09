from __future__ import annotations

import copy
import importlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
compare_results = importlib.import_module("compare_timeslot_results")


ENVIRONMENT = {
    "system": "TestOS",
    "release": "1",
    "machine": "test-machine",
    "processor": "test-cpu",
}


def row(n: int, q: int, seed: int, scenario: str, uniformity: float,
        stability: float, operation_ms: float, init_ms: float) -> dict:
    return {
        "N": n,
        "Q": q,
        "seed": seed,
        "scenario": scenario,
        "uniformity": uniformity,
        "stability": stability,
        "operation_ms": operation_ms,
        "init_ms": init_ms,
    }


def result(rows: list[dict] | None = None) -> dict:
    return {
        "schema_version": 2,
        "status": "success",
        "correct": True,
        "stage": "full",
        "candidate_hash": "a" * 64,
        "evaluator_hash": "e" * 64,
        "runtime_environment": copy.deepcopy(ENVIRONMENT),
        "metrics": {
            "rows": rows or [row(100, 1, 1, "steady", 0.5, 0.5, 10, 5)],
        },
    }


class CompareTimeslotResultsTests(unittest.TestCase):
    def compare(self, baseline: dict, candidate: dict) -> dict:
        return compare_results.compare(
            baseline, Path("baseline.json"), candidate, Path("candidate.json"),
        )

    def test_compares_paired_rows_and_summarizes_by_n_and_q(self) -> None:
        baseline = result([
            row(100, 1, 1, "steady", 0.5, 0.4, 10, 5),
            row(100, 1, 2, "steady", 0.4, 0.6, 0, 0),
            row(400, 10, 1, "churn", 0.8, 0.8, 30, 10),
        ])
        candidate = result([
            row(400, 10, 1, "churn", 0.8, 0.8, 33, 12),
            row(100, 1, 2, "steady", 0.3, 0.7, 0, 0),
            row(100, 1, 1, "steady", 0.6, 0.5, 8, 4),
        ])

        compared = self.compare(baseline, candidate)

        self.assertEqual(compared["workload_count"], 3)
        self.assertEqual([group["N"] for group in compared["by_workload_config"]], [100, 400])
        self.assertEqual(compared["by_workload_config"][0]["cases"], 2)
        self.assertAlmostEqual(compared["workloads"][0]["quality_proxy_delta"], 0.09)
        self.assertAlmostEqual(compared["workloads"][0]["operation_speedup_percent"], 20.0)
        self.assertIsNone(compared["workloads"][1]["operation_speedup_percent"])
        self.assertAlmostEqual(compared["summary"]["quality_proxy_delta"]["mean"], 0.07 / 3)

    def test_rejects_different_evaluator_environment_and_stage(self) -> None:
        mutations = [
            ("evaluator_hash", "different"),
            ("stage", "short"),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                candidate = result()
                candidate[field] = value
                with self.assertRaises(compare_results.ComparisonFailure):
                    self.compare(result(), candidate)

        candidate = result()
        candidate["runtime_environment"]["machine"] = "other-machine"
        with self.assertRaisesRegex(compare_results.ComparisonFailure, "runtime environments"):
            self.compare(result(), candidate)

    def test_rejects_unpaired_or_duplicate_workloads(self) -> None:
        baseline = result()
        candidate = result([row(100, 1, 2, "steady", 0.5, 0.5, 10, 5)])
        with self.assertRaisesRegex(compare_results.ComparisonFailure, "Workload sets differ"):
            self.compare(baseline, candidate)

        duplicate = row(100, 1, 1, "steady", 0.5, 0.5, 10, 5)
        with self.assertRaisesRegex(compare_results.ComparisonFailure, "Duplicate workload key"):
            self.compare(result([duplicate, copy.deepcopy(duplicate)]), result([duplicate]))

    def test_rejects_boolean_string_and_non_finite_metrics(self) -> None:
        invalid_values = [True, "0.5", math.inf, math.nan]
        for value in invalid_values:
            with self.subTest(value=repr(value)):
                invalid_row = row(100, 1, 1, "steady", 0.5, 0.5, 10, 5)
                invalid_row["uniformity"] = value
                with self.assertRaises(compare_results.ComparisonFailure):
                    self.compare(result([invalid_row]), result())

    def test_rejects_quality_outside_unit_interval_and_negative_time(self) -> None:
        for field, value in [("uniformity", 1.01), ("stability", -0.01), ("operation_ms", -1)]:
            with self.subTest(field=field):
                invalid_row = row(100, 1, 1, "steady", 0.5, 0.5, 10, 5)
                invalid_row[field] = value
                with self.assertRaises(compare_results.ComparisonFailure):
                    self.compare(result([invalid_row]), result())

    def test_load_result_rejects_failed_and_partial_results(self) -> None:
        for changes in [{"status": "failed"}, {"metrics": {"rows": [], "partial": True}}]:
            value = result()
            value.update(changes)
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "result.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(compare_results.ComparisonFailure):
                    compare_results.load_result(path)


if __name__ == "__main__":
    unittest.main()
