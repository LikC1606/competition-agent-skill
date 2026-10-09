from __future__ import annotations

import csv
import importlib
import io
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
evaluate = importlib.import_module("evaluate_current_timeslot")


def metric_rows() -> list[dict[str, str]]:
    return [
        {
            "seed": "7",
            "scenario": scenario,
            "N": "400",
            "Q": "100",
            "uniformity": "0.5",
            "stability": "0.4",
            "operation_ms": "3.5",
            "init_ms": "1.25",
        }
        for scenario in evaluate.SCENARIOS
    ]


def csv_output(rows: list[dict[str, str]]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=evaluate.CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


class ParseRowsTests(unittest.TestCase):
    def test_accepts_complete_rows_for_the_requested_workload(self) -> None:
        parsed = evaluate.parse_rows(
            csv_output(metric_rows()), len(evaluate.SCENARIOS),
            {"seed": 7, "N": 400, "Q": 100},
        )

        self.assertEqual(len(parsed), len(evaluate.SCENARIOS))
        self.assertAlmostEqual(parsed[0]["quality_proxy"], 0.415)

    def test_rejects_rows_that_do_not_match_invocation_identity(self) -> None:
        for expected, message in [({"N": 10000}, "Expected N=10000"),
                                  ({"Q": 1000}, "Expected Q=1000")]:
            with self.subTest(expected=expected), self.assertRaisesRegex(evaluate.EvaluationFailure, message):
                evaluate.parse_rows(csv_output(metric_rows()), len(evaluate.SCENARIOS), expected)

    def test_rejects_missing_duplicate_or_unknown_scenarios(self) -> None:
        duplicate = metric_rows()
        duplicate[-1]["scenario"] = duplicate[0]["scenario"]
        unknown = metric_rows()
        unknown[-1]["scenario"] = "unknown"
        missing = metric_rows()[:-1]

        for rows in [duplicate, unknown, missing]:
            with self.subTest(scenarios=[row["scenario"] for row in rows]):
                with self.assertRaises(evaluate.EvaluationFailure):
                    evaluate.parse_rows(csv_output(rows), len(evaluate.SCENARIOS))

    def test_rejects_extra_csv_columns(self) -> None:
        lines = csv_output(metric_rows()).splitlines()
        lines[2] += ",unexpected"

        with self.assertRaisesRegex(evaluate.EvaluationFailure, "extra columns"):
            evaluate.parse_rows("\n".join(lines) + "\n", len(evaluate.SCENARIOS))

    def test_rejects_invalid_dimensions_quality_and_time(self) -> None:
        invalid_cases = [
            ("N", "0"),
            ("Q", "-1"),
            ("uniformity", "1.01"),
            ("stability", "-0.01"),
            ("operation_ms", "-1"),
            ("init_ms", "NaN"),
        ]
        for field, value in invalid_cases:
            with self.subTest(field=field, value=value):
                rows = metric_rows()
                rows[0][field] = value
                with self.assertRaises(evaluate.EvaluationFailure):
                    evaluate.parse_rows(csv_output(rows), len(evaluate.SCENARIOS))


if __name__ == "__main__":
    unittest.main()
