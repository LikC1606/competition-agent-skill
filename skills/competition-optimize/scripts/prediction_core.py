"""Prediction metrics, CSV validation and comparable saved-result evidence.

No command-line module is imported here. The evaluator, paired diagnostics and
comparison CLI share this interface; saved schemas remain version 1.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import io
import json
import math
import pathlib
import re
from typing import Any, Callable


METRIC_DIRECTIONS = {
    "rmse": "minimize",
    "mae": "minimize",
    "binary_log_loss": "minimize",
    "roc_auc": "maximize",
    "accuracy": "maximize",
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


def scorer_fingerprint(directory: pathlib.Path, backend: dict[str, str] | None = None) -> str:
    """Read scorer identity without executing it; None retains legacy identities."""
    sources = {name: byte_hash((directory / name).read_bytes())
               for name in ["evaluate_predictions.py", "prediction_core.py"]}
    return object_hash(sources if backend is None else {"sources": sources, "metric_backend": backend})


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


def metric_backend() -> dict[str, str]:
    """Bind numerical dependencies without loading them for archive-only reads."""
    try:
        return {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn")}
    except importlib.metadata.PackageNotFoundError as exc:
        raise PredictionFailure("missing_dependency", "Scoring requires the task's numeric environment; "
                                "see scripts/requirements-tabular.txt") from exc


def binary_log_losses(labels: list[float], predictions: list[float], epsilon: float):
    """Use SciPy's Bernoulli terms with the declared, rather than dtype, clipping."""
    import numpy as np
    from scipy.special import xlogy, xlog1py

    clipped = np.clip(np.asarray(predictions, dtype=float), epsilon, 1 - epsilon)
    if np.any(clipped <= 0) or np.any(clipped >= 1):
        raise PredictionFailure("invalid_config", "Epsilon is too small for finite log-loss clipping")
    truth = np.asarray(labels, dtype=float)
    return -(xlogy(truth, clipped) + xlog1py(1 - truth, -clipped))


def prepare_metric(metric: str, labels: Any, predictions: Any,
                   epsilon: float = 1e-15) -> Callable[..., float]:
    """Validate once; return a scorer for all rows or repeated row indices.

    Cache row losses and AUC score groups for paired/group bootstrap draws.
    Numerical imports remain lazy so archive-only reads need no ML environment.
    """
    if metric not in METRIC_DIRECTIONS:
        raise PredictionFailure("invalid_metric", f"Unsupported metric: {metric}")
    if not math.isfinite(epsilon) or not 0 < epsilon < 0.5:
        raise PredictionFailure("invalid_config", "Log-loss epsilon must be finite and between 0 and 0.5")
    try:
        import numpy as np
        from sklearn import metrics
    except ImportError as exc:
        raise PredictionFailure("missing_dependency", "Scoring requires the task's numeric environment; "
                                "see scripts/requirements-tabular.txt") from exc
    try:
        truth = np.asarray(labels, dtype=float)
        predicted = np.asarray(predictions, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PredictionFailure("invalid_score", "Metric inputs must be one-dimensional numeric sequences") from exc
    if (truth.ndim != 1 or predicted.ndim != 1 or truth.size == 0
            or truth.size != predicted.size):
        raise PredictionFailure("invalid_score", "Labels and predictions must be non-empty, one-dimensional and paired")
    if not np.all(np.isfinite(truth)) or not np.all(np.isfinite(predicted)):
        raise PredictionFailure("invalid_score", "Metric inputs must be finite")
    if metric in {"rmse", "mae"}:
        with np.errstate(over="ignore"):
            losses = np.abs(truth - predicted)
        if not np.all(np.isfinite(losses)):
            raise PredictionFailure("invalid_score", "Residual exceeds finite floating-point range")
    else:
        if not np.all((truth == 0) | (truth == 1)):
            raise PredictionFailure("invalid_domain", "Binary metrics require labels encoded as 0 or 1")
        if metric == "accuracy":
            if not np.all((predicted == 0) | (predicted == 1)):
                raise PredictionFailure("invalid_domain", "Binary accuracy requires hard predictions encoded as 0 or 1")
            losses = truth == predicted
        elif metric == "binary_log_loss":
            if not np.all((predicted >= 0) & (predicted <= 1)):
                raise PredictionFailure("invalid_domain", "Binary log loss requires probabilities in [0, 1]")
            losses = binary_log_losses(truth, predicted, epsilon)
        else:
            if not np.any(truth == 0) or not np.any(truth == 1):
                raise PredictionFailure("invalid_domain", "ROC-AUC requires both positive and negative labels")
            # Sort score groups once; draws change their class multiplicities.
            groups, inverse = np.unique(predicted, return_inverse=True)

    def score(indices=None) -> float:
        selected = slice(None) if indices is None else np.asarray(indices)
        if metric == "roc_auc":
            counts = np.bincount(inverse[selected], minlength=len(groups))
            positive = np.bincount(inverse[selected], weights=truth[selected], minlength=len(groups))
            tps = np.r_[0.0, np.cumsum(positive[::-1])]
            fps = np.r_[0.0, np.cumsum((counts - positive)[::-1])]
            if tps[-1] == 0 or fps[-1] == 0:
                raise PredictionFailure("invalid_domain", "ROC-AUC requires both positive and negative labels")
            result = metrics.auc(fps / fps[-1], tps / tps[-1])
        else:
            values = losses[selected]
            if metric in {"rmse", "mae"}:
                # Scale each draw: tiny residuals survive when an extreme row is absent.
                scale = values.max()
                scorer = metrics.root_mean_squared_error if metric == "rmse" else metrics.mean_absolute_error
                result = 0.0 if scale == 0 else scale * scorer(np.zeros(values.size), values / scale)
            else:
                result = values.mean()
        if not math.isfinite(result):
            raise PredictionFailure("invalid_score", "Computed score is not finite")
        return float(result)

    return score


def calculate_metric(metric: str, labels: Any, predictions: Any, epsilon: float = 1e-15) -> float:
    return prepare_metric(metric, labels, predictions, epsilon)()


class ComparisonFailure(Exception):
    pass


def metric_preference(improvement: float, epsilon: float) -> str:
    return "tie" if abs(improvement) <= epsilon else "candidate" if improvement > 0 else "baseline"


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
    if number < 0 or (metric in {"roc_auc", "accuracy"} and number > 1):
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
    return {
        "schema_version": 1, "status": "success",
        "selection_scope": "local_metric_only_pending_other_rule_checks",
        "metric": score["metric"], "direction": score["direction"], "score_kind": score["kind"],
        "stage": baseline["evaluation"]["stage"], "split_hash": baseline["evaluation"]["split_hash"],
        "evaluator_hash": baseline["evaluator_hash"], "score_model_hash": baseline["score_model_hash"],
        "baseline": {"candidate_hash": baseline["candidate_hash"], "score": score["value"]},
        "candidate": {"candidate_hash": candidate["candidate_hash"], "score": candidate["score"]["value"]},
        "raw_score_delta": delta, "objective_improvement": improvement,
        "metric_preference": metric_preference(improvement, epsilon), "tie_epsilon": epsilon,
        "unchecked_rules": sorted(set(UNCHECKED_RULES) | set(baseline.get("unchecked_rules", []))
                                  | set(candidate.get("unchecked_rules", []))),
        "note": "This compares deterministic local scores; it does not establish training repeatability or final-test gain.",
    }
