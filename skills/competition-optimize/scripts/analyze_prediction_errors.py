#!/usr/bin/env python3
"""Diagnose paired development predictions by sample and optional categorical slices."""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys
from typing import Any

import evaluate_predictions as evaluator
from compare_prediction_results import ComparisonFailure
from prediction_evidence import EvidenceFailure, load_pair, read_categories


class AnalysisFailure(Exception):
    pass


def read_slices(raw: bytes, id_column: str, columns: list[str], sample_ids: set[str]) -> dict[str, dict[str, str]]:
    try:
        return read_categories(raw, id_column, columns, sample_ids)
    except EvidenceFailure as exc:
        raise AnalysisFailure(str(exc)) from exc


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
    try:
        pair = load_pair(args.baseline, args.candidate, args.truth)
    except EvidenceFailure as exc:
        raise AnalysisFailure(str(exc)) from exc
    comparison = pair.comparison
    if comparison["stage"] != "development":
        raise AnalysisFailure("Exploratory error analysis requires development evaluations")
    config, metric, epsilon = pair.configuration, pair.metric, pair.epsilon
    if config["id_column"] in columns:
        raise AnalysisFailure("ID column must differ from slice columns")
    sample_ids, truth, before, after = pair.sample_ids, pair.labels, pair.baseline, pair.candidate
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
    for name, raw in zip(["baseline.csv", "candidate.csv"], pair.prediction_bytes):
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
                                                for name in ["analyze_prediction_errors.py", "prediction_evidence.py", "evaluate_predictions.py",
                                                             "compare_prediction_results.py"]}),
        "inputs": {key: str(path) for key, path in pair.paths.items()},
        "input_hashes": pair.input_hashes,
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
