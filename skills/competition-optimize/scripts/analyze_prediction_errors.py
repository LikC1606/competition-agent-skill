#!/usr/bin/env python3
"""Diagnose paired development predictions by sample and optional categorical slices."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import pathlib
import sys
from typing import Any

import evaluate_predictions as evaluator
from compare_prediction_results import ComparisonFailure, compare, load_result


class AnalysisFailure(Exception):
    pass


def read_slices(raw: bytes, id_column: str, columns: list[str], sample_ids: set[str]) -> dict[str, dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        fields = reader.fieldnames
        if (not fields or any(not field.strip() for field in fields) or len(set(fields)) != len(fields)
                or any(column not in fields for column in [id_column, *columns])):
            raise AnalysisFailure("Slice CSV needs unique column names and the requested ID/slice columns")
        rows: dict[str, dict[str, str]] = {}
        for row_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise AnalysisFailure(f"Slice CSV has a wrong field count at row {row_number}")
            sample_id = row[id_column]
            if not sample_id.strip() or sample_id in rows:
                raise AnalysisFailure(f"Slice CSV has an empty or duplicate ID at row {row_number}")
            if any(not row[column].strip() for column in columns):
                raise AnalysisFailure(f"Slice values must be non-empty at row {row_number}")
            rows[sample_id] = {column: row[column] for column in columns}
        if rows.keys() != sample_ids:
            raise AnalysisFailure("Slice IDs must exactly match the evaluated split")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise AnalysisFailure(f"Invalid slice CSV: {exc}") from exc


def local_errors(metric: str, labels: list[float], predictions: list[float], epsilon: float) -> list[float] | None:
    if metric == "roc_auc":
        return None
    if metric in {"rmse", "mae"}:
        return [abs(label - prediction) for label, prediction in zip(labels, predictions)]
    clipped = [min(1 - epsilon, max(epsilon, value)) for value in predictions]
    return [-math.log(p) if label == 1 else -math.log1p(-p) for label, p in zip(labels, clipped)]


def error_shares(errors: list[float], squared: bool) -> list[float]:
    scale = max(errors)
    if scale == 0:
        return [0.0] * len(errors)
    mass = [(error / scale) ** 2 if squared else error / scale for error in errors]
    total = math.fsum(mass)
    return [value / total for value in mass]


def subset_scores(metric: str, labels: list[float], baseline: list[float], candidate: list[float],
                  epsilon: float) -> dict[str, Any]:
    if metric == "roc_auc" and len(set(labels)) < 2:
        return {"baseline_score": None, "candidate_score": None, "objective_improvement": None,
                "unavailable_reason": "roc_auc_requires_both_classes"}
    before = evaluator.calculate_metric(metric, labels, baseline, epsilon)
    after = evaluator.calculate_metric(metric, labels, candidate, epsilon)
    improvement = after - before if evaluator.METRIC_DIRECTIONS[metric] == "maximize" else before - after
    return {"baseline_score": before, "candidate_score": after, "objective_improvement": improvement,
            "unavailable_reason": None}


def analyze(args: argparse.Namespace, output_dir: pathlib.Path) -> dict[str, Any]:
    if (not 1 <= args.top_k <= 100 or args.max_groups < 1
            or not math.isfinite(args.error_tie_epsilon) or args.error_tie_epsilon < 0):
        raise AnalysisFailure("Top-k must be 1-100, max-groups positive, and error tie epsilon finite/non-negative")
    if bool(args.slices) != bool(args.slice_column):
        raise AnalysisFailure("Provide both --slices and at least one --slice-column, or neither")
    columns = args.slice_column or []
    if len(set(columns)) != len(columns) or any(not column.strip() for column in columns):
        raise AnalysisFailure("Requested slice columns must be unique and non-empty")
    baseline_path = args.baseline.expanduser().resolve(strict=True)
    candidate_path = args.candidate.expanduser().resolve(strict=True)
    baseline_result, candidate_result = load_result(baseline_path), load_result(candidate_path)
    comparison = compare(baseline_result, candidate_result, 0)
    if comparison["stage"] != "development":
        raise AnalysisFailure("Exploratory error analysis requires development evaluations")
    if baseline_result["evaluator_hash"] != evaluator.byte_hash(pathlib.Path(evaluator.__file__).read_bytes()):
        raise AnalysisFailure("Reevaluate both candidates with the installed prediction evaluator before analysis")
    config = baseline_result["evaluation"]["configuration"]
    for key in ["id_column", "target_column", "prediction_column"]:
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise AnalysisFailure("Evaluation must declare non-empty CSV columns")
    if config["id_column"] in {config["target_column"], config["prediction_column"], *columns}:
        raise AnalysisFailure("ID column must differ from numeric value and slice columns")
    metric = baseline_result["score"]["metric"]
    model = config["score_model"]
    parameters = model.get("parameters")
    if (model.get("aggregation") != "unweighted over all aligned rows" or not isinstance(parameters, dict)
            or set(parameters) != ({"epsilon"} if metric == "binary_log_loss" else set())):
        raise AnalysisFailure("Unsupported prediction score formula or parameters")
    epsilon = parameters.get("epsilon", 1e-15)
    if type(epsilon) not in {int, float}:
        raise AnalysisFailure("Log-loss epsilon must be a number")
    truth_path = args.truth.expanduser().resolve(strict=True)
    truth_raw = truth_path.read_bytes()
    if evaluator.byte_hash(truth_raw) != baseline_result["evaluation"]["split_hash"]:
        raise AnalysisFailure("Truth bytes differ from the evaluated split")
    raw_predictions = []
    for path, result in [(baseline_path, baseline_result), (candidate_path, candidate_result)]:
        raw = (path.parent / "predictions.csv").read_bytes()
        if evaluator.byte_hash(raw) != result["candidate_hash"]:
            raise AnalysisFailure("Prediction snapshot changed during analysis")
        raw_predictions.append(raw)
    labels = evaluator.read_values(truth_raw, config["id_column"], config["target_column"], "truth")
    predictions = [evaluator.read_values(raw, config["id_column"], config["prediction_column"], role)
                   for raw, role in zip(raw_predictions, ["baseline", "candidate"])]
    if any(values.keys() != labels.keys() for values in predictions):
        raise AnalysisFailure("Prediction IDs differ from the evaluated truth")
    if len(labels) != baseline_result["evaluation"]["completed_cases"]:
        raise AnalysisFailure("Prediction row count differs from the evaluation")
    sample_ids = sorted(labels)
    truth = [labels[key] for key in sample_ids]
    before, after = [[values[key] for key in sample_ids] for values in predictions]
    overall = subset_scores(metric, truth, before, after, epsilon)
    for result, key in [(baseline_result, "baseline_score"), (candidate_result, "candidate_score")]:
        if overall[key] != result["score"]["value"]:
            raise AnalysisFailure("Recomputed score differs from its evaluation record")
    slices_raw = None
    slices: dict[str, dict[str, str]] = {}
    if args.slices:
        slices_raw = args.slices.expanduser().resolve(strict=True).read_bytes()
        slices = read_slices(slices_raw, config["id_column"], columns, set(sample_ids))
    before_errors, after_errors = local_errors(metric, truth, before, epsilon), local_errors(metric, truth, after, epsilon)
    before_shares = error_shares(before_errors, metric == "rmse") if before_errors is not None else None
    after_shares = error_shares(after_errors, metric == "rmse") if after_errors is not None else None
    squared_error_scale = max(max(before_errors), max(after_errors)) if metric == "rmse" else None
    rows = []
    counts = {"baseline": 0, "candidate": 0, "tie": 0} if before_errors is not None else None
    for index, sample_id in enumerate(sample_ids):
        improvement, preference = None, None
        squared_improvement = None
        if before_errors is not None:
            improvement = before_errors[index] - after_errors[index]
            preference = ("tie" if abs(improvement) <= args.error_tie_epsilon
                          else "candidate" if improvement > 0 else "baseline")
            counts[preference] += 1
        if squared_error_scale is not None:
            if squared_error_scale == 0:
                squared_improvement = 0.0
            else:
                scaled_before = before_errors[index] / squared_error_scale
                scaled_after = after_errors[index] / squared_error_scale
                squared_improvement = (scaled_before - scaled_after) * (scaled_before + scaled_after)
        rows.append({"id": sample_id, "target": truth[index], "baseline_prediction": before[index],
                     "candidate_prediction": after[index],
                     "baseline_error": before_errors[index] if before_errors is not None else None,
                     "candidate_error": after_errors[index] if after_errors is not None else None,
                     "error_improvement": improvement, "case_preference": preference,
                     "scaled_squared_error_improvement": squared_improvement,
                     "baseline_error_share": before_shares[index] if before_shares is not None else None,
                     "candidate_error_share": after_shares[index] if after_shares is not None else None,
                     "slices": slices.get(sample_id, {})})
    slice_results = []
    for column in columns:
        groups: dict[str, list[int]] = {}
        for index, sample_id in enumerate(sample_ids):
            groups.setdefault(slices[sample_id][column], []).append(index)
        if len(groups) > args.max_groups:
            raise AnalysisFailure(f"Slice column {column!r} exceeds --max-groups; use categorical regimes")
        for group, indexes in sorted(groups.items()):
            group_truth = [truth[index] for index in indexes]
            scores = subset_scores(metric, group_truth, [before[index] for index in indexes],
                                   [after[index] for index in indexes], epsilon)
            slice_results.append({"column": column, "value": group, "case_count": len(indexes), **scores,
                                  "positive_count": sum(label == 1 for label in group_truth)
                                  if metric in {"roc_auc", "binary_log_loss"} else None,
                                  "baseline_error_share": math.fsum(before_shares[i] for i in indexes)
                                  if before_shares is not None else None,
                                  "candidate_error_share": math.fsum(after_shares[i] for i in indexes)
                                  if after_shares is not None else None})
    worst, regressions = [], []
    if after_errors is not None:
        worst = sorted(rows, key=lambda row: (-row["candidate_error"], row["id"]))[:args.top_k]
        regression_key = "scaled_squared_error_improvement" if metric == "rmse" else "error_improvement"
        regressions = sorted((row for row in rows if row["case_preference"] == "baseline"),
                             key=lambda row: (row[regression_key], row["id"]))[:args.top_k]
    for name, raw in zip(["baseline.csv", "candidate.csv"], raw_predictions):
        with (output_dir / name).open("xb") as stream:
            stream.write(raw)
    if slices_raw is not None:
        with (output_dir / "slices.csv").open("xb") as stream:
            stream.write(slices_raw)
    fields = [key for key in rows[0] if key != "slices"] + [f"slice:{column}" for column in columns]
    with (output_dir / "cases.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({**{key: value for key, value in row.items() if key != "slices"},
                             **{f"slice:{column}": row["slices"][column] for column in columns}})
    diagnostic_config = {"top_k": args.top_k, "error_tie_epsilon": args.error_tie_epsilon,
                         "slice_columns": columns, "max_groups": args.max_groups,
                         "slice_hash": evaluator.byte_hash(slices_raw) if slices_raw is not None else None}
    return {
        "schema_version": 1, "adapter": "prediction_error_analysis", "status": "success",
        "selection_scope": "development_diagnostics_only", "aggregate_comparison": comparison,
        "case_count": len(rows), "case_preference_counts": counts,
        "squared_error_scale": squared_error_scale,
        "per_case_error_kind": None if metric == "roc_auc" else
        "clipped_log_loss" if metric == "binary_log_loss" else "absolute_error",
        "error_share_kind": None if metric == "roc_auc" else "squared_error" if metric == "rmse" else
        "clipped_log_loss" if metric == "binary_log_loss" else "absolute_error",
        "largest_candidate_errors": worst, "largest_regressions": regressions, "slices": slice_results,
        "configuration": diagnostic_config, "config_hash": evaluator.object_hash(diagnostic_config),
        "analyzer_hash": evaluator.object_hash({name: evaluator.byte_hash(pathlib.Path(__file__).with_name(name).read_bytes())
                                                for name in ["analyze_prediction_errors.py", "evaluate_predictions.py",
                                                             "compare_prediction_results.py"]}),
        "inputs": {"baseline": str(baseline_path), "candidate": str(candidate_path), "truth": str(truth_path)},
        "input_hashes": {"baseline_result": evaluator.byte_hash(baseline_path.read_bytes()),
                         "candidate_result": evaluator.byte_hash(candidate_path.read_bytes()),
                         "truth": evaluator.byte_hash(truth_raw)},
        "artifacts": [str(output_dir / name) for name in
                      ["baseline.csv", "candidate.csv", "cases.csv", *(["slices.csv"] if slices_raw else [])]],
        "note": "Slices and case counts diagnose hypotheses, not official aggregation or causality. "
                "ROC-AUC has no independent per-row loss; single-class slices have unavailable AUC.",
        "error": None,
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["baseline", "candidate", "truth", "output-dir"]:
        parser.add_argument(f"--{name}", required=True, type=pathlib.Path)
    parser.add_argument("--slices", type=pathlib.Path, help="optional full-split ID/categorical metadata CSV")
    parser.add_argument("--slice-column", action="append", help="categorical column to diagnose; repeat for separate slices")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-groups", type=int, default=100)
    parser.add_argument("--error-tie-epsilon", type=float, default=1e-12)
    return parser


def main() -> int:
    args = make_parser().parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    created = False
    try:
        output_dir.mkdir(exist_ok=False)
        created = True
        result = analyze(args, output_dir)
    except (OSError, AnalysisFailure, ComparisonFailure, evaluator.PredictionFailure,
            ValueError, TypeError, KeyError, OverflowError) as exc:
        result = {"schema_version": 1, "adapter": "prediction_error_analysis", "status": "failed",
                  "error": {"type": "analysis_invalid", "message": str(exc)}}
    if created:
        try:
            with (output_dir / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        except OSError as exc:
            print(json.dumps({"status": "failed", "error": {"type": "output_failure", "message": str(exc)}},
                             ensure_ascii=False), file=sys.stderr)
            return 2
    print(json.dumps({"status": result["status"], "report": str(output_dir / "report.json") if created else None,
                      "case_count": result.get("case_count"), "error": result["error"]}, ensure_ascii=False),
          file=sys.stdout if result["status"] == "success" else sys.stderr)
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
