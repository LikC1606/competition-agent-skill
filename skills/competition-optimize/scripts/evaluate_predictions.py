#!/usr/bin/env python3
"""Evaluate unweighted scalar CSV predictions on a declared local split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import pathlib
import platform
import sys
from typing import Any


METRIC_DIRECTIONS = {
    "rmse": "minimize",
    "mae": "minimize",
    "binary_log_loss": "minimize",
    "roc_auc": "maximize",
}
UNCHECKED_RULES = ["training_leakage", "training_provenance", "resource_limits", "competition_rules"]


class PredictionFailure(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def byte_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_hash(value: Any) -> str:
    return byte_hash(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True, allow_nan=False).encode("utf-8"))


def read_values(raw: bytes, id_column: str, value_column: str, source: str) -> dict[str, float]:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        columns = reader.fieldnames
        if (not columns or any(not column.strip() for column in columns)
                or len(set(columns)) != len(columns)):
            raise PredictionFailure("invalid_csv", f"{source}: missing, empty, or duplicate column names")
        if id_column not in columns or value_column not in columns:
            raise PredictionFailure("invalid_csv", f"{source}: requires {id_column!r} and {value_column!r}")
        values: dict[str, float] = {}
        for row_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise PredictionFailure("invalid_csv", f"{source}: wrong field count at row {row_number}")
            sample_id = row[id_column]
            if not sample_id.strip():
                raise PredictionFailure("invalid_id", f"{source}: empty ID at row {row_number}")
            if sample_id in values:
                raise PredictionFailure("invalid_id", f"{source}: duplicate ID at row {row_number}")
            try:
                value = float(row[value_column])
            except ValueError as exc:
                raise PredictionFailure("invalid_value", f"{source}: non-numeric value at row {row_number}") from exc
            if not math.isfinite(value):
                raise PredictionFailure("invalid_value", f"{source}: non-finite value at row {row_number}")
            values[sample_id] = value
        if not values:
            raise PredictionFailure("invalid_csv", f"{source}: contains no data rows")
        return values
    except (UnicodeDecodeError, csv.Error) as exc:
        raise PredictionFailure("invalid_csv", f"{source}: {exc}") from exc


def calculate_metric(metric: str, labels: list[float], predictions: list[float],
                     epsilon: float = 1e-15) -> float:
    if metric not in METRIC_DIRECTIONS:
        raise PredictionFailure("invalid_metric", f"Unsupported metric: {metric}")
    if not labels or len(labels) != len(predictions):
        raise PredictionFailure("invalid_score", "Labels and predictions must be non-empty and paired")
    if any(not math.isfinite(value) for value in labels + predictions):
        raise PredictionFailure("invalid_score", "Metric inputs must be finite")
    if not math.isfinite(epsilon) or not 0 < epsilon < 0.5:
        raise PredictionFailure("invalid_config", "Log-loss epsilon must be finite and between 0 and 0.5")
    count = len(labels)
    if metric in {"rmse", "mae"}:
        residuals = [abs(label - prediction) for label, prediction in zip(labels, predictions)]
        if any(not math.isfinite(value) for value in residuals):
            raise PredictionFailure("invalid_score", "Residual exceeds finite floating-point range")
        scale = max(residuals)
        # Scaling avoids overflowing when finite residuals are squared or summed.
        score = 0.0 if scale == 0 else scale * (
            math.sqrt(math.fsum((value / scale) ** 2 for value in residuals) / count)
            if metric == "rmse" else math.fsum(value / scale for value in residuals) / count
        )
    else:
        if any(label not in (0.0, 1.0) for label in labels):
            raise PredictionFailure("invalid_domain", "Binary metrics require labels encoded as 0 or 1")
        if metric == "binary_log_loss":
            if any(not 0 <= value <= 1 for value in predictions):
                raise PredictionFailure("invalid_domain", "Binary log loss requires probabilities in [0, 1]")
            clipped = [min(1 - epsilon, max(epsilon, value)) for value in predictions]
            if any(not 0 < value < 1 for value in clipped):
                raise PredictionFailure("invalid_config", "Epsilon is too small for finite log-loss clipping")
            score = math.fsum(-math.log(p) if label == 1 else -math.log1p(-p)
                              for label, p in zip(labels, clipped)) / count
        else:
            positive_count = sum(label == 1 for label in labels)
            negative_count = count - positive_count
            if not positive_count or not negative_count:
                raise PredictionFailure("invalid_domain", "ROC-AUC requires both positive and negative labels")
            ordered = sorted(zip(predictions, labels))
            negatives_before = 0
            twice_favorable = 0
            start = 0
            while start < count:
                end = start + 1
                while end < count and ordered[end][0] == ordered[start][0]:
                    end += 1
                positives = sum(label == 1 for _, label in ordered[start:end])
                negatives = end - start - positives
                twice_favorable += positives * (2 * negatives_before + negatives)
                negatives_before += negatives
                start = end
            score = twice_favorable / (2 * positive_count * negative_count)
    if not math.isfinite(score):
        raise PredictionFailure("invalid_score", "Computed score is not finite")
    return score


def evaluate(args: argparse.Namespace, output_dir: pathlib.Path) -> dict[str, Any]:
    if (not args.split_id.strip() or not args.id_column.strip()
            or not args.target_column.strip() or not args.prediction_column.strip()):
        raise PredictionFailure("invalid_config", "Split ID and column names must be non-empty")
    if args.id_column in {args.target_column, args.prediction_column}:
        raise PredictionFailure("invalid_config", "ID and numeric value columns must differ")
    truth_path = args.truth.expanduser().resolve(strict=True)
    prediction_path = args.predictions.expanduser().resolve(strict=True)
    if truth_path == prediction_path:
        raise PredictionFailure("invalid_input", "Truth and prediction artifacts must be separate files")
    truth_raw, prediction_raw = truth_path.read_bytes(), prediction_path.read_bytes()
    labels = read_values(truth_raw, args.id_column, args.target_column, "truth")
    predictions = read_values(prediction_raw, args.id_column, args.prediction_column, "predictions")
    if labels.keys() != predictions.keys():
        missing = len(labels.keys() - predictions.keys())
        extra = len(predictions.keys() - labels.keys())
        raise PredictionFailure("id_mismatch", f"Prediction IDs differ from truth: missing={missing}, extra={extra}")
    sample_ids = sorted(labels)
    score = calculate_metric(args.metric, [labels[key] for key in sample_ids],
                             [predictions[key] for key in sample_ids], args.log_loss_epsilon)
    parameters = {"epsilon": args.log_loss_epsilon} if args.metric == "binary_log_loss" else {}
    score_model = {
        "metric": args.metric,
        "direction": METRIC_DIRECTIONS[args.metric],
        "kind": args.score_kind,
        "aggregation": "unweighted over all aligned rows",
        "parameters": parameters,
    }
    config = {
        "stage": args.stage, "split_id": args.split_id,
        "truth_hash": byte_hash(truth_raw), "id_column": args.id_column,
        "target_column": args.target_column, "prediction_column": args.prediction_column,
        "score_model": score_model,
    }
    snapshot = output_dir / "predictions.csv"
    with snapshot.open("xb") as stream:
        stream.write(prediction_raw)
    return {
        "schema_version": 1,
        "adapter": "prediction_csv",
        "status": "success", "valid": True,
        "validity_scope": "prediction_artifact_and_metric_inputs",
        "checks": {"csv_schema": "passed", "unique_ids": "passed", "id_coverage": "passed",
                   "finite_values": "passed", "metric_domain": "passed"},
        "unchecked_rules": UNCHECKED_RULES,
        "candidate_hash": byte_hash(prediction_raw), "candidate_scope": "prediction_csv",
        "evaluator_hash": byte_hash(pathlib.Path(__file__).read_bytes()),
        "score_model_hash": object_hash(score_model),
        "score": {**score_model, "origin": "local", "value": score, "components": {}},
        "evaluation": {
            "stage": args.stage, "split_id": args.split_id, "split_hash": config["truth_hash"],
            "config_hash": object_hash(config), "configuration": config,
            "expected_cases": len(labels), "completed_cases": len(predictions),
            "seeds": [], "repetitions": 1,
            "runtime_environment": {"python": platform.python_version(), "system": platform.system()},
        },
        "inputs": {"truth": str(truth_path), "predictions": str(prediction_path)},
        "artifacts": [str(snapshot)], "error": None,
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, type=pathlib.Path)
    parser.add_argument("--predictions", required=True, type=pathlib.Path)
    parser.add_argument("--metric", required=True, choices=list(METRIC_DIRECTIONS))
    parser.add_argument("--stage", required=True, choices=["development", "confirmation"])
    parser.add_argument("--split-id", required=True, help="name of the frozen local validation split")
    parser.add_argument("--id-column", default="id")
    parser.add_argument("--target-column", default="target")
    parser.add_argument("--prediction-column", default="prediction")
    parser.add_argument("--score-kind", choices=["proxy", "official_metric"], default="proxy",
                        help="official_metric only after verifying this exact formula against the contest scorer")
    parser.add_argument("--log-loss-epsilon", type=float, default=1e-15)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path,
                        help="new directory under an existing parent; never overwrite prior runs")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    created = False
    try:
        output_dir.mkdir(exist_ok=False)
        created = True
        result = evaluate(args, output_dir)
    except (OSError, PredictionFailure, OverflowError, ValueError) as exc:
        result = {
            "schema_version": 1, "adapter": "prediction_csv", "status": "failed", "valid": False,
            "score": {"value": None},
            "error": {"type": exc.kind if isinstance(exc, PredictionFailure) else "invalid_input",
                      "message": str(exc)},
        }
    if created:
        try:
            with (output_dir / "result.json").open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        except OSError as exc:
            print(json.dumps({"status": "failed", "error": {"type": "output_failure", "message": str(exc)}},
                             ensure_ascii=False), file=sys.stderr)
            return 2
    summary = {key: result[key] for key in ["schema_version", "status", "valid", "score", "error"]}
    summary["result_file"] = str(output_dir / "result.json") if created else None
    if result["status"] == "success":
        summary["validity_scope"] = result["validity_scope"]
        summary["unchecked_rules"] = result["unchecked_rules"]
        summary["case_count"] = result["evaluation"]["completed_cases"]
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2),
          file=sys.stdout if result["status"] == "success" else sys.stderr)
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
