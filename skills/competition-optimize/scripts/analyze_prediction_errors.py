#!/usr/bin/env python3
"""Diagnose paired development predictions by sample and optional categorical slices."""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import pathlib
import sys
from fractions import Fraction
from typing import Any

import evaluate_predictions as evaluator
from compare_prediction_results import ComparisonFailure
from prediction_core import metric_preference
from prediction_evidence import EvidenceFailure, PredictionPair, load_fold_receipt, load_pair, read_categories


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
    if metric == "accuracy":
        return [float(label != prediction) for label, prediction in zip(labels, predictions)]
    return evaluator.binary_log_losses(labels, predictions, epsilon).tolist()


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


def fold_diagnostics(pair: PredictionPair, folds: dict[str, tuple[set[str], set[str]]]) -> dict[str, Any]:
    indexes = {sample_id: index for index, sample_id in enumerate(pair.sample_ids)}
    producers = {sample_id: name for name, (_, ids) in folds.items() for sample_id in ids}
    rows, boundary = [], []
    counts = {"candidate": 0, "baseline": 0, "tie": 0, "unavailable": 0}
    for name, (training, validation) in sorted(folds.items()):
        held_out = sorted(indexes[i] for i in validation)
        scores = subset_scores(pair.metric, [pair.labels[i] for i in held_out], [pair.baseline[i] for i in held_out],
                               [pair.candidate[i] for i in held_out], pair.epsilon)
        improvement = scores["objective_improvement"]
        preference = "unavailable" if improvement is None else metric_preference(improvement, 0.0)
        counts[preference] += 1
        rows.append({"fold_id": name, "case_count": len(validation), "preference": preference, **scores})
        # Other folds supplied the OOF residuals for these outer training rows.
        residual_rows = training & producers.keys()
        sources = sorted({producers[i] for i in residual_rows})
        by_producer = {source: validation & folds[source][0] for source in sources}
        boundary.append({"fold_id": name, "held_out_labels": len(validation),
                         "training_rows_with_saved_oof": len(residual_rows),
                         "held_out_labels_seen_by_residual_producers": len(set().union(*by_producer.values())),
                         "held_out_labels_seen_by_producer_fold": {source: len(ids) for source, ids in by_producer.items()}})
    gains = [row["objective_improvement"] for row in rows if row["objective_improvement"] is not None]
    return {"metric": pair.metric, "direction": pair.comparison["direction"], "folds": rows,
            "fold_preference_counts": counts,
            "observed_objective_improvement_range": [min(gains), max(gains)] if gains else None,
            "scope": "Observed differences in the original metric's units on matched saved validation folds. "
                     "Positive improvement favors the candidate. Folds share training data; this is "
                     "descriptive dispersion, not an uncertainty estimate or promotion rule.",
            "pooled_oof_second_layer_boundary": {
                "status": ("held_out_label_overlap" if any(row["held_out_labels_seen_by_residual_producers"]
                                                           for row in boundary) else "no_recorded_label_overlap"),
                "folds": boundary,
                "scope": "Checks reusing pooled OOF predictions or residuals to fit a second layer on each "
                         "outer training partition. Overlap does not invalidate original OOF scores. "
                         "No recorded overlap does not certify upstream feature or selection lineage."}}


def blend_directions(metric: str, labels: list[float], baseline: list[float],
                     candidate: list[float]) -> dict[str, Any]:
    """Check convex-loss endpoint directions without choosing or scoring weights."""
    if metric not in {"rmse", "mae"}:
        return {"status": "unavailable", "reason": "unsupported_metric",
                "metric": metric, "recipe_evaluated": False}
    derivatives = {"baseline": Fraction(0), "candidate": Fraction(0)}
    for label, before, after in zip(labels, baseline, candidate):
        # Exact signs matter at cancellation and MAE kinks. Fractions of finite
        # parsed floats also avoid overflow when residuals/differences are squared.
        target = Fraction(label)
        r0, r1 = Fraction(before) - target, Fraction(after) - target
        delta = r1 - r0
        if metric == "rmse":
            # Ignore common positive 2/n: RMSE and MSE have the same minima.
            derivatives["baseline"] += r0 * delta
            derivatives["candidate"] -= r1 * delta
        else:
            derivatives["baseline"] += abs(delta) if r0 == 0 else delta if r0 > 0 else -delta
            derivatives["candidate"] += abs(delta) if r1 == 0 else -delta if r1 > 0 else delta
    signs = {name: "negative" if value < 0 else "positive" if value > 0 else "zero"
             for name, value in derivatives.items()}
    return {"status": "available", "metric": metric,
            "convex_loss": "mean_squared_error" if metric == "rmse" else "mean_absolute_error",
            "endpoint_inward_loss_derivative_sign": signs,
            "strict_gain_over_best_parent_possible": all(value < 0 for value in derivatives.values()),
            "minimizing_endpoints": [name for name, value in derivatives.items() if value >= 0],
            "recipe_evaluated": False,
            "calculation": "exact_rational_of_parsed_floats",
            "scope": "Ideal convex blends (1-w)*baseline + w*candidate, 0 <= w <= 1, on these "
                     "development rows only. Negative inward derivatives at both endpoints imply some "
                     "interior weight beats both parents; a non-negative endpoint derivative makes that "
                     "parent a minimum. No weight, candidate score, practical gain size, or independent "
                     "evidence is supplied. Evaluate any constructed recipe, including rounding, separately."}


def influence_diagnostics(metric: str, labels: list[float], baseline: list[float],
                          candidate: list[float], sample_ids: list[str],
                          max_removals: int = 5) -> dict[str, Any]:
    """Find a smallest sign-changing deletion for a fixed pair, in either direction."""
    if metric != "rmse":
        return {"status": "unavailable", "reason": "unsupported_metric", "metric": metric}
    if max_removals < 1:
        raise AnalysisFailure("Influence max removals must be positive")
    changes = []
    for label, before, after in zip(labels, baseline, candidate):
        target = Fraction(label)
        changes.append((Fraction(after) - target) ** 2 - (Fraction(before) - target) ** 2)
    total = sum(changes, Fraction(0))
    direction = 1 if total > 0 else -1 if total < 0 else 0
    limit = min(max_removals, len(labels) - 1)  # Never score an empty population.
    report = {
        "status": "available", "metric": metric,
        "loss_direction": "candidate_worse" if direction > 0 else
                          "candidate_better" if direction < 0 else "tied",
        "max_removals": max_removals, "effective_max_removals": limit,
        "minimum_removals_to_tie_or_reverse": None, "minimum_witness_ids": [],
        "max_removal_loss_share": None, "max_removal_ids": [], "max_removal_scores": None,
        "calculation": "exact_rational_of_parsed_floats",
        "scope": "Adversarial deletion sensitivity of these fixed development predictions. "
                 "No refitting, sampling uncertainty, minimum effect size, promotion rule or "
                 "mechanism-family conclusion follows from this diagnostic."
    }
    if direction == 0:
        return report
    ordered = sorted(range(len(labels)), key=lambda i: (-direction * changes[i], sample_ids[i]))[:limit]
    removed = Fraction(0)
    for count, index in enumerate(ordered, 1):
        removed += direction * changes[index]
        if removed >= abs(total) and report["minimum_removals_to_tie_or_reverse"] is None:
            report["minimum_removals_to_tie_or_reverse"] = count
            report["minimum_witness_ids"] = [sample_ids[i] for i in ordered[:count]]
    try:
        report["max_removal_loss_share"] = float(removed / abs(total))
    except OverflowError:
        report["loss_share_unavailable_reason"] = "ratio_exceeds_float_range"
    report["max_removal_ids"] = [sample_ids[i] for i in ordered]
    excluded = set(ordered)
    remaining = [i for i in range(len(labels)) if i not in excluded]
    report["max_removal_scores"] = subset_scores(
        metric, [labels[i] for i in remaining], [baseline[i] for i in remaining],
        [candidate[i] for i in remaining], 1e-15)
    return report


def analyze(args: argparse.Namespace, output_dir: pathlib.Path) -> dict[str, Any]:
    if (not 1 <= args.top_k <= 100 or args.max_groups < 1
            or not math.isfinite(args.error_tie_epsilon) or args.error_tie_epsilon < 0):
        raise AnalysisFailure("Top-k must be 1-100, max-groups positive, and error tie epsilon finite/non-negative")
    if bool(args.slices) != bool(args.slice_column):
        raise AnalysisFailure("Provide both --slices and at least one --slice-column, or neither")
    if bool(args.baseline_fit) != bool(args.candidate_fit):
        raise AnalysisFailure("Provide both --baseline-fit and --candidate-fit, or neither")
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
    fold_report = None
    fold_inputs, fold_hashes = {}, {}
    if args.baseline_fit:
        try:
            matched, before_fit, before_hash = load_fold_receipt(args.baseline_fit, pair, "baseline")
            other, after_fit, after_hash = load_fold_receipt(args.candidate_fit, pair, "candidate")
        except EvidenceFailure as exc:
            raise AnalysisFailure(str(exc)) from exc
        if matched != other:
            raise AnalysisFailure("Baseline and candidate fit receipts have different training or validation assignments")
        fold_report = fold_diagnostics(pair, matched)
        fold_inputs = {"baseline_fit": str(before_fit), "candidate_fit": str(after_fit)}
        fold_hashes = {"baseline_fit": before_hash, "candidate_fit": after_hash}
    slices_raw = None
    slices: dict[str, dict[str, str]] = {}
    if args.slices:
        slices_raw = args.slices.expanduser().resolve(strict=True).read_bytes()
        slices = read_slices(slices_raw, config["id_column"], columns, set(sample_ids))
    before_errors, after_errors = local_errors(metric, truth, before, epsilon), local_errors(metric, truth, after, epsilon)
    before_shares = error_shares(before_errors, metric == "rmse") if before_errors is not None else None
    after_shares = error_shares(after_errors, metric == "rmse") if after_errors is not None else None
    check_blend = getattr(args, "check_blend_direction", False)
    blend_report = blend_directions(metric, truth, before, after) if check_blend else None
    check_influence = getattr(args, "check_influence", False)
    influence_limit = getattr(args, "influence_max_removals", 5)
    influence_report = influence_diagnostics(metric, truth, before, after, sample_ids,
                                             influence_limit) if check_influence else None
    squared_error_scale = max(max(before_errors), max(after_errors)) if metric == "rmse" else None
    counts = {"baseline": 0, "candidate": 0, "tie": 0} if before_errors is not None else None

    def case_preference(index: int) -> str:
        improvement = before_errors[index] - after_errors[index]
        return ("tie" if abs(improvement) <= args.error_tie_epsilon
                else "candidate" if improvement > 0 else "baseline")

    def squared_improvement(index: int) -> float | None:
        if squared_error_scale is None:
            return None
        if squared_error_scale == 0:
            return 0.0
        scaled_before = before_errors[index] / squared_error_scale
        scaled_after = after_errors[index] / squared_error_scale
        return (scaled_before - scaled_after) * (scaled_before + scaled_after)

    def case_row(index: int) -> dict[str, Any]:
        sample_id = sample_ids[index]
        improvement, preference = None, None
        if before_errors is not None:
            improvement = before_errors[index] - after_errors[index]
            preference = case_preference(index)
        return {"id": sample_id, "target": truth[index], "baseline_prediction": before[index],
                "candidate_prediction": after[index],
                "baseline_error": before_errors[index] if before_errors is not None else None,
                "candidate_error": after_errors[index] if after_errors is not None else None,
                "error_improvement": improvement, "case_preference": preference,
                "scaled_squared_error_improvement": squared_improvement(index),
                "baseline_error_share": before_shares[index] if before_shares is not None else None,
                "candidate_error_share": after_shares[index] if after_shares is not None else None,
                "slices": slices.get(sample_id, {})}

    if counts is not None:
        for index in range(len(sample_ids)):
            counts[case_preference(index)] += 1
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
                                  if metric in {"roc_auc", "binary_log_loss", "accuracy"} else None,
                                  "baseline_error_share": math.fsum(before_shares[i] for i in indexes)
                                  if before_shares is not None else None,
                                  "candidate_error_share": math.fsum(after_shares[i] for i in indexes)
                                  if after_shares is not None else None})
    worst, regressions = [], []
    if after_errors is not None:
        worst_indexes = heapq.nsmallest(args.top_k, range(len(sample_ids)),
                                       key=lambda index: (-after_errors[index], sample_ids[index]))
        regression_indexes = heapq.nsmallest(
            args.top_k, (index for index in range(len(sample_ids)) if case_preference(index) == "baseline"),
            key=lambda index: (squared_improvement(index) if metric == "rmse" else
                               before_errors[index] - after_errors[index], sample_ids[index]))
        worst = [case_row(index) for index in worst_indexes]
        regressions = [case_row(index) for index in regression_indexes]
    summary_only = getattr(args, "summary_only", False)
    artifacts = []
    if not summary_only:
        for name, raw in zip(["baseline.csv", "candidate.csv"], pair.prediction_bytes):
            with (output_dir / name).open("xb") as stream:
                stream.write(raw)
        if slices_raw is not None:
            with (output_dir / "slices.csv").open("xb") as stream:
                stream.write(slices_raw)
        fields = [key for key in case_row(0) if key != "slices"] + [f"slice:{column}" for column in columns]
        with (output_dir / "cases.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for index in range(len(sample_ids)):
                row = case_row(index)
                writer.writerow({**{key: value for key, value in row.items() if key != "slices"},
                                 **{f"slice:{column}": row["slices"][column] for column in columns}})
        artifacts = [str(output_dir / name) for name in
                     ["baseline.csv", "candidate.csv", "cases.csv", *(["slices.csv"] if slices_raw else [])]]
    diagnostic_config = {"top_k": args.top_k, "error_tie_epsilon": args.error_tie_epsilon,
                         "slice_columns": columns, "max_groups": args.max_groups,
                         "slice_hash": evaluator.byte_hash(slices_raw) if slices_raw is not None else None}
    if check_blend:
        diagnostic_config["check_blend_direction"] = True
    if check_influence:
        diagnostic_config.update(check_influence=True, influence_max_removals=influence_limit)
    if fold_report is not None:
        diagnostic_config["fold_hashes"] = fold_hashes
    inputs = {**{key: str(path) for key, path in pair.paths.items()}, **fold_inputs}
    input_hashes = {**pair.input_hashes, **fold_hashes}
    if summary_only:
        diagnostic_config["output_mode"] = "summary"
        if slices_raw is not None:
            inputs["slices"] = str(args.slices.expanduser().resolve(strict=True))
            input_hashes["slices"] = evaluator.byte_hash(slices_raw)
    return {
        "schema_version": 1, "adapter": "prediction_error_analysis", "status": "success",
        "selection_scope": "development_diagnostics_only", "aggregate_comparison": comparison,
        "case_count": len(sample_ids), "case_preference_counts": counts,
        "squared_error_scale": squared_error_scale,
        "per_case_error_kind": None if metric == "roc_auc" else
        "zero_one_error" if metric == "accuracy" else
        "clipped_log_loss" if metric == "binary_log_loss" else "absolute_error",
        "error_share_kind": None if metric == "roc_auc" else "squared_error" if metric == "rmse" else
        "zero_one_error" if metric == "accuracy" else
        "clipped_log_loss" if metric == "binary_log_loss" else "absolute_error",
        "largest_candidate_errors": worst, "largest_regressions": regressions, "slices": slice_results,
        **({"blend_direction": blend_report} if check_blend else {}),
        **({"influence": influence_report} if check_influence else {}),
        **({"fold_comparison": fold_report} if fold_report is not None else {}),
        "configuration": diagnostic_config, "config_hash": evaluator.object_hash(diagnostic_config),
        "analyzer_hash": evaluator.object_hash({name: evaluator.byte_hash(pathlib.Path(__file__).with_name(name).read_bytes())
                                                for name in ["analyze_prediction_errors.py", "prediction_evidence.py", "evaluate_predictions.py",
                                                             "compare_prediction_results.py"]}),
        "inputs": inputs, "input_hashes": input_hashes, "artifacts": artifacts,
        "note": "Slices and case counts diagnose hypotheses, not official aggregation or causality. "
                "ROC-AUC has no independent per-row loss; single-class slices have unavailable AUC."
                + (" Summary mode references original evidence; retain those files for reuse and reproduction."
                   if summary_only else ""),
        "error": None,
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["baseline", "candidate", "truth", "output-dir"]:
        parser.add_argument(f"--{name}", required=True, type=pathlib.Path)
    parser.add_argument("--slices", type=pathlib.Path, help="optional full-split ID/categorical metadata CSV")
    parser.add_argument("--slice-column", action="append", help="categorical column to diagnose; repeat for separate slices")
    parser.add_argument("--baseline-fit", type=pathlib.Path, help="baseline's sealed tabular training fit.json")
    parser.add_argument("--candidate-fit", type=pathlib.Path, help="candidate's sealed tabular training fit.json")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-groups", type=int, default=100)
    parser.add_argument("--error-tie-epsilon", type=float, default=1e-12)
    parser.add_argument("--summary-only", action="store_true",
                        help="same diagnostic scores/top cases; skip full cases CSV and copied input snapshots")
    parser.add_argument("--check-blend-direction", action="store_true",
                        help="RMSE/MAE convex-loss endpoint signs; no weight search or recipe score")
    parser.add_argument("--check-influence", action="store_true",
                        help="RMSE sign sensitivity to deleting rows; no refitting or promotion gate")
    parser.add_argument("--influence-max-removals", type=int, default=5,
                        help="maximum rows for the optional influence diagnostic (default: 5)")
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
