#!/usr/bin/env python3
"""Compare local prediction scores under the same split and metric contract."""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
from typing import Any

from evaluate_predictions import METRIC_DIRECTIONS, UNCHECKED_RULES, byte_hash, object_hash


class ComparisonFailure(Exception):
    pass


def load_result(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ComparisonFailure(f"Cannot read result {path}: {exc}") from exc
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ComparisonFailure("Unsupported prediction result schema")
    if value.get("adapter") != "prediction_csv" or value.get("status") != "success" or value.get("valid") is not True:
        raise ComparisonFailure("Result is not a successful prediction evaluation")
    if value.get("validity_scope") != "prediction_artifact_and_metric_inputs":
        raise ComparisonFailure("Unexpected validity scope")
    checks = value.get("checks")
    if not isinstance(checks, dict) or any(checks.get(key) != "passed" for key in
            ["csv_schema", "unique_ids", "id_coverage", "finite_values", "metric_domain"]):
        raise ComparisonFailure("Required prediction checks did not pass")
    unchecked = value.get("unchecked_rules")
    if not isinstance(unchecked, list) or any(not isinstance(rule, str) for rule in unchecked):
        raise ComparisonFailure("Malformed unchecked-rule metadata")
    for key in ["candidate_hash", "evaluator_hash", "score_model_hash"]:
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise ComparisonFailure(f"Missing or malformed {key}")
    score, evaluation = value.get("score"), value.get("evaluation")
    if not isinstance(score, dict) or not isinstance(evaluation, dict):
        raise ComparisonFailure("Missing score or evaluation metadata")
    metric = score.get("metric")
    if not isinstance(metric, str) or metric not in METRIC_DIRECTIONS:
        raise ComparisonFailure("Unknown metric")
    if score.get("direction") != METRIC_DIRECTIONS[metric] or score.get("origin") != "local":
        raise ComparisonFailure("Metric direction or score origin is inconsistent")
    if score.get("kind") not in {"proxy", "official_metric"}:
        raise ComparisonFailure("Unsupported score kind")
    number = score.get("value")
    if type(number) not in {int, float} or not math.isfinite(number):
        raise ComparisonFailure("Score must be a finite JSON number")
    if number < 0 or (metric == "roc_auc" and number > 1):
        raise ComparisonFailure("Score is outside the metric domain")
    expected, completed = evaluation.get("expected_cases"), evaluation.get("completed_cases")
    if type(expected) is not int or type(completed) is not int or expected < 1 or completed != expected:
        raise ComparisonFailure("Evaluation does not cover the complete split")
    if evaluation.get("stage") not in {"development", "confirmation"}:
        raise ComparisonFailure("Unexpected evaluation stage")
    config = evaluation.get("configuration")
    if not isinstance(config, dict):
        raise ComparisonFailure("Missing evaluation configuration")
    model = config.get("score_model")
    if not isinstance(model, dict) or object_hash(model) != value["score_model_hash"]:
        raise ComparisonFailure("Score model metadata does not match its hash")
    if any(score.get(key) != model.get(key) for key in ["metric", "direction", "kind", "aggregation", "parameters"]):
        raise ComparisonFailure("Score metadata differs from the score model")
    if object_hash(config) != evaluation.get("config_hash"):
        raise ComparisonFailure("Evaluation configuration does not match its hash")
    if any(evaluation.get(key) != config.get(key) for key in ["stage", "split_id"]):
        raise ComparisonFailure("Evaluation stage or split differs from its configuration")
    if evaluation.get("split_hash") != config.get("truth_hash"):
        raise ComparisonFailure("Split hash differs from the truth hash")
    if not isinstance(evaluation.get("split_hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", evaluation["split_hash"]):
        raise ComparisonFailure("Missing or malformed split hash")
    try:
        snapshot = (path.parent / "predictions.csv").read_bytes()
    except OSError as exc:
        raise ComparisonFailure(f"Cannot read the saved prediction snapshot: {exc}") from exc
    if byte_hash(snapshot) != value["candidate_hash"]:
        raise ComparisonFailure("Saved prediction snapshot differs from the evaluated candidate")
    return value


def compare(baseline: dict[str, Any], candidate: dict[str, Any], epsilon: float) -> dict[str, Any]:
    if not math.isfinite(epsilon) or epsilon < 0:
        raise ComparisonFailure("Tie epsilon must be finite and non-negative")
    for key in ["evaluator_hash", "score_model_hash"]:
        if baseline[key] != candidate[key]:
            raise ComparisonFailure(f"Cannot compare different {key}")
    for key in ["stage", "split_id", "split_hash", "config_hash", "expected_cases", "completed_cases"]:
        if baseline["evaluation"][key] != candidate["evaluation"][key]:
            raise ComparisonFailure(f"Cannot compare different {key}")
    score = baseline["score"]
    delta = candidate["score"]["value"] - score["value"]
    improvement = delta if score["direction"] == "maximize" else -delta
    if not math.isfinite(improvement):
        raise ComparisonFailure("Score difference is not finite")
    preference = "tie" if abs(improvement) <= epsilon else "candidate" if improvement > 0 else "baseline"
    return {
        "schema_version": 1, "status": "success",
        "selection_scope": "local_metric_only_pending_other_rule_checks",
        "metric": score["metric"], "direction": score["direction"], "score_kind": score["kind"],
        "stage": baseline["evaluation"]["stage"], "split_hash": baseline["evaluation"]["split_hash"],
        "evaluator_hash": baseline["evaluator_hash"], "score_model_hash": baseline["score_model_hash"],
        "baseline": {"candidate_hash": baseline["candidate_hash"], "score": score["value"]},
        "candidate": {"candidate_hash": candidate["candidate_hash"], "score": candidate["score"]["value"]},
        "raw_score_delta": delta, "objective_improvement": improvement,
        "metric_preference": preference, "tie_epsilon": epsilon,
        "unchecked_rules": sorted(set(UNCHECKED_RULES) | set(baseline.get("unchecked_rules", []))
                                  | set(candidate.get("unchecked_rules", []))),
        "note": "This compares deterministic local scores; it does not establish training repeatability or final-test gain.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=pathlib.Path)
    parser.add_argument("--candidate", required=True, type=pathlib.Path)
    parser.add_argument("--tie-epsilon", type=float, default=1e-12)
    parser.add_argument("--output", type=pathlib.Path, help="optional new comparison JSON; never overwrite")
    args = parser.parse_args()
    try:
        baseline_path = args.baseline.expanduser().resolve(strict=True)
        candidate_path = args.candidate.expanduser().resolve(strict=True)
        result = compare(load_result(baseline_path), load_result(candidate_path), args.tie_epsilon)
        result["baseline"]["result"] = str(baseline_path)
        result["candidate"]["result"] = str(candidate_path)
        if args.output is not None:
            with args.output.expanduser().open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    except (OSError, ComparisonFailure, ValueError, TypeError, OverflowError) as exc:
        print(json.dumps({"status": "failed", "error": {"type": "comparison_invalid", "message": str(exc)}},
                         ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
