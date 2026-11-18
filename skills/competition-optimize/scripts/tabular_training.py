#!/usr/bin/env python3
"""Fit numeric tabular candidates, preserve OOF lineage, and deliver frozen models.

Candidates supply build_model(seed, task), returning a sklearn-compatible estimator.
Candidate code and model files are trusted local code, not sandboxed inputs.
"""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

from audit_data_split import number, timestamp
from evaluate_predictions import EvaluationSpec, evaluate, evaluator_fingerprint
from prediction_core import (byte_hash, object_hash, load_result, compare, scorer_fingerprint,
                             metric_backend, PredictionFailure)
from training_execution import (append_event, cost_report, execution_descriptor, fit_cost, proposal_binding,
                                verify_training_source)


class TrainingFailure(ValueError):
    pass


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json_text(value))
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path, columns: list[str], *, raw: bytes | None = None) -> tuple[list[str], dict[str, dict]]:
    text = (path.read_bytes() if raw is None else raw).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    header = reader.fieldnames
    if (not header or any(not name.strip() for name in header)
            or len(set(header)) != len(header) or not set(columns) <= set(header)):
        raise TrainingFailure("CSV requires distinct named columns: " + ", ".join(columns))
    rows = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise TrainingFailure("Malformed CSV row")
        key = row[columns[0]]
        if not key.strip() or key in rows:
            raise TrainingFailure("CSV IDs must be nonempty and unique")
        rows[key] = row
    if not rows:
        raise TrainingFailure("CSV is empty")
    return header, rows


def save_csv(path: Path, header: list[str], rows) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def environment() -> dict:
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {name: importlib.metadata.version(name) for name in
                         ["numpy", "scipy", "scikit-learn", "joblib", "threadpoolctl"]}}


def runtime():
    try:
        import numpy as np
        import joblib
        from threadpoolctl import threadpool_limits
    except ImportError as exc:
        raise TrainingFailure("Install the optional scripts/requirements-tabular.txt in an isolated environment") from exc
    return np, joblib, threadpool_limits


def unique_ids(value, label: str) -> list[str]:
    if (not isinstance(value, list) or not value
            or any(not isinstance(item, str) or not item for item in value)
            or len(set(value)) != len(value)):
        raise TrainingFailure(label + " must contain unique nonempty string IDs")
    return value


def validate_spec(spec: dict) -> None:
    if spec.get("schema_version") != 1 or not spec.get("task_id"):
        raise TrainingFailure("Expected schema_version=1 and task_id")
    if spec.get("task") not in {"regression", "binary"}:
        raise TrainingFailure("Only scalar regression and binary tasks are supported")
    allowed = {"rmse", "mae"} if spec["task"] == "regression" else {"binary_log_loss", "roc_auc", "accuracy"}
    if spec.get("metric") not in allowed:
        raise TrainingFailure("Metric does not match the declared task")
    threshold = spec.get("decision_threshold", 0.5)
    if type(threshold) not in {int, float} or not 0 < threshold < 1:
        raise TrainingFailure("decision_threshold must be between 0 and 1")
    relations = spec.get("relations", [])
    if not isinstance(relations, list):
        raise TrainingFailure("relations must be a list")
    for relation in relations:
        if (not isinstance(relation, dict) or not relation.get("column") or not relation.get("rationale")
                or relation.get("inference") not in {"new_groups", "known_groups", "mixed"}):
            raise TrainingFailure("Relations need column, inference (new_groups/known_groups/mixed), and rationale")
    features = unique_ids(spec.get("features"), "features")
    names = [spec.get(name, default) for name, default in
             [("id_column", "id"), ("target_column", "target"), ("prediction_column", "prediction")]]
    if any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != 3:
        raise TrainingFailure("ID, target and prediction columns must be distinct")
    if set(features) & set(names):
        raise TrainingFailure("Features cannot include ID, target or prediction columns")
    split = spec.get("split", {})
    if split.get("kind") not in {"iid", "group", "time", "group_time"}:
        raise TrainingFailure("Declare split.kind as iid, group, time or group_time")
    if "group" in split["kind"] and not split.get("group_column"):
        raise TrainingFailure("Group splitting requires group_column")
    if "time" in split["kind"]:
        if not split.get("time_column") or split.get("time_format") not in {"number", "iso8601"}:
            raise TrainingFailure("Time splitting requires time_column and time_format")
        if number(str(split.get("minimum_time_gap", "0"))) < 0:
            raise TrainingFailure("minimum_time_gap must be nonnegative")
    if spec.get("score_kind", "proxy") not in {"proxy", "official_metric"}:
        raise TrainingFailure("Unknown score_kind")
    unique_ids(spec.get("expected_oof_ids"), "expected_oof_ids")
    if not isinstance(spec.get("folds"), list) or not spec["folds"]:
        raise TrainingFailure("Declare at least one fold")


def protocol_folds(spec: dict) -> list[dict]:
    if not isinstance(spec, dict):
        raise TrainingFailure("Protocol must be a JSON object")
    validate_spec(spec)
    fold_ids = set()
    for fold in spec["folds"]:
        if (not isinstance(fold, dict) or not isinstance(fold.get("id"), str)
                or not fold["id"] or fold["id"] in fold_ids):
            raise TrainingFailure("Fold IDs must be nonempty and unique")
        if type(fold.get("seed")) is not int:
            raise TrainingFailure("Each fold requires an integer seed")
        unique_ids(fold.get("train_ids"), "train_ids")
        unique_ids(fold.get("validation_ids"), "validation_ids")
        fold_ids.add(fold["id"])
    return spec["folds"]


def check_fit_count(actual: int, expected: int | None) -> None:
    if expected is not None and (type(expected) is not int or expected != actual):
        raise TrainingFailure(f"Declared {expected} adapter fit calls; supplied protocols require {actual}. "
                              "Correct the plan or schedule fewer fits before training.")


def plan_cost(protocols: list[Path], expected_fit_calls: int | None = None) -> dict:
    """Count planned adapter fits from actual protocol files without loading data or candidates."""
    if not protocols:
        raise TrainingFailure("Supply at least one training protocol")
    requests = []
    for path in protocols:
        path = path.expanduser().resolve(strict=True)
        raw = path.read_bytes()
        count = len(protocol_folds(json.loads(raw)))
        requests.append({"protocol": str(path), "protocol_sha256": byte_hash(raw), "fit_calls": count})
    total = sum(request["fit_calls"] for request in requests)
    check_fit_count(total, expected_fit_calls)
    return {"status": "planned", "fit_calls": total, "requests": requests,
            "scope": "One adapter estimator.fit call per fold per requested new execution. "
                     "Excludes reuse, retries and nested estimator fits."}


def measurement_binding(archive: Path, plan_id: str, run_id: str, *, protocol: bytes,
                        folds: list[dict], recipe: dict) -> dict:
    from candidate_archive import candidate_index, measurement_plans, read_records

    records = read_records(archive.expanduser().resolve(strict=True))
    plan = next((row for row in records if row["event"] == "measurement_plan" and row["plan_id"] == plan_id), None)
    if plan is None:
        raise TrainingFailure("Record the measurement plan before training")
    view = measurement_plans.status(plan, records)
    if view["decision"] is not None or view["stop"] is not None or view["rule_result"]["state"] == "unresolved":
        raise TrainingFailure("Measurement plan is closed or unresolved; inspect measure-status before training")
    run = next((row for row in view["runs"] if row["run_id"] == run_id), None)
    if run is None or run.get("protocol_sha256") != byte_hash(protocol):
        raise TrainingFailure("The measurement run must bind these exact protocol bytes with protocol_sha256")
    fold_seeds = list(dict.fromkeys(fold["seed"] for fold in folds))
    if run["repetitions"] != 1 or run["seeds"] not in ([], fold_seeds):
        raise TrainingFailure("Managed measurement requires one repetition and seeds empty or equal to the protocol's ordered fold seeds")
    candidates = candidate_index(records)
    recipe_hash = byte_hash(json_text(recipe).encode("utf-8"))
    sides = [side for side in ("leader", "challenger")
             if candidates[plan[side + "_candidate"]]["artifacts"].get("configuration") == recipe_hash]
    if len(sides) != 1 or run[sides[0]] is not None:
        raise TrainingFailure("Recipe must match exactly one unfilled side of the frozen run")
    return {"measurement_plan_id": plan_id, "measurement_run_id": run_id,
            "seeds": run["seeds"], "repetitions": run["repetitions"], "plan_sha256": object_hash(plan)}


def metadata_columns(spec: dict, *, training: bool = True) -> list[str]:
    split = spec["split"]
    names = ["group_column", "time_column"] + (["available_time_column"] if training else [])
    return list(dict.fromkeys([split[name] for name in names if split.get(name)]
                             + [relation["column"] for relation in spec.get("relations", [])]))


def relation_preflight(spec: dict, rows: dict, inference_rows: dict | None) -> list[dict]:
    reports = []
    for relation in spec.get("relations", []):
        if inference_rows is None:
            raise TrainingFailure("Declared relations require --inference-data before fitting")
        column, expected = relation["column"], relation["inference"]
        if any(not row[column].strip() for row in [*rows.values(), *inference_rows.values()]):
            raise TrainingFailure("Relation group IDs must be nonempty: " + column)
        train_groups = {row[column] for row in rows.values()}
        def overlap(left, ids):
            return sum(left[key][column] in train_groups for key in ids) / len(ids)
        inference_fraction = overlap(inference_rows, list(inference_rows))
        fractions = []
        for fold in spec["folds"]:
            fit_groups = {rows[key][column] for key in fold["train_ids"]}
            fractions.append(sum(rows[key][column] in fit_groups for key in fold["validation_ids"])
                             / len(fold["validation_ids"]))
        if expected == "new_groups" and any(value != 0 for value in [inference_fraction, *fractions]):
            raise TrainingFailure("Relation requires new groups at inference and in every validation fold: " + column)
        if expected == "known_groups" and any(value != 1 for value in [inference_fraction, *fractions]):
            raise TrainingFailure("Relation requires known groups at inference and in every validation fold: " + column)
        reports.append({**relation, "inference_known_row_fraction": inference_fraction,
                        "validation_known_row_fractions": fractions})
    return reports


def check_boundary(spec: dict, left: dict, right: dict) -> None:
    if set(left) & set(right):
        raise TrainingFailure("Training and evaluation IDs overlap")
    split = spec["split"]
    if "group" in split["kind"]:
        column = split["group_column"]
        groups = [{row[column] for row in rows.values()} for rows in [left, right]]
        if "" in groups[0] | groups[1] or groups[0] & groups[1]:
            raise TrainingFailure("Training and evaluation groups overlap or are empty")
    if "time" in split["kind"]:
        column, form = split["time_column"], split["time_format"]
        available = split.get("available_time_column", column)
        latest = max(max(timestamp(row[column], form), timestamp(row[available], form))
                     for row in left.values())
        earliest = min(timestamp(row[column], form) for row in right.values())
        gap = number(str(split.get("minimum_time_gap", "0")))
        if earliest <= latest or earliest - latest < gap:
            raise TrainingFailure("Evaluation precedes training event/label availability or required time gap")


def matrix(np, rows: dict, ids: list[str], features: list[str]):
    values = np.array([[float(rows[key][feature]) for feature in features] for key in ids], dtype=float)
    if not np.isfinite(values).all():
        raise TrainingFailure("Features must be finite numeric values")
    return values


def predictions(np, model, values, task: str):
    if task == "binary":
        classes = list(model.classes_)
        if set(classes) != {0, 1}:
            raise TrainingFailure("Binary estimator must learn classes 0 and 1")
        result = np.asarray(model.predict_proba(values))[:, classes.index(1)]
    else:
        result = np.asarray(model.predict(values))
    return checked_predictions(np, result, len(values), task)


def checked_predictions(np, result, count: int, task: str):
    result = np.asarray(result)
    if result.shape != (count,) or not np.isfinite(result).all():
        raise TrainingFailure("Estimator must produce one finite scalar per row")
    if task == "binary" and ((result < 0).any() or (result > 1).any()):
        raise TrainingFailure("Binary predictions must be probabilities")
    return result


def decision_values(np, values, spec: dict):
    # Threshold once, after averaging probabilities for frozen multi-fold inference.
    return (values >= spec.get("decision_threshold", 0.5)).astype(int) if spec["metric"] == "accuracy" else values


def artifact_hashes(root: Path) -> dict:
    return {str(path.relative_to(root)): byte_hash(path.read_bytes()) for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "manifest.json" and "__pycache__" not in path.parts}


def verified_manifest(root: Path, kind: str) -> dict:
    manifest = read_json(root / "manifest.json")
    if manifest.get("kind") != kind or manifest.get("seal") != object_hash({
            key: value for key, value in manifest.items() if key != "seal"}):
        raise TrainingFailure("Invalid manifest or seal")
    for name, expected in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or byte_hash(path.read_bytes()) != expected:
            raise TrainingFailure("Artifact changed: " + name)
    return manifest


def seal(root: Path, fields: dict) -> dict:
    manifest = {"schema_version": 1, **fields, "files": artifact_hashes(root)}
    manifest["seal"] = object_hash(manifest)
    write_json(root / "manifest.json", manifest)
    return manifest


class SavedTabularRun:
    """Read trusted sealed models without mixing different candidates' Python globals.

    This single-threaded analysis interface does not fit or re-save estimators.
    """

    def __init__(self, root: Path, *, kind: str | None = None):
        self.root = root.expanduser().resolve()
        actual_kind = read_json(self.root / "manifest.json").get("kind")
        if actual_kind not in {"tabular_training", "tabular_frozen"} or kind not in {None, actual_kind}:
            raise TrainingFailure("Expected a sealed tabular training or frozen run")
        self.manifest = verified_manifest(self.root, actual_kind)
        self.protocol = read_json(self.root / "protocol.json")
        self.fit = read_json(self.root / "fit.json")
        if environment() != self.fit["environment"]:
            raise TrainingFailure("Saved models require the recorded Python/platform/package environment")
        self._module = None
        self._namespace = "competition_saved_" + uuid.uuid4().hex

    def _bytes(self, name: str) -> bytes:
        expected = self.manifest["files"].get(name)
        path = (self.root / name).resolve()
        if expected is None or not path.is_relative_to(self.root):
            raise TrainingFailure("Model or source is outside the sealed run: " + name)
        raw = path.read_bytes()
        if byte_hash(raw) != expected:
            raise TrainingFailure("Artifact changed: " + name)
        return raw

    def load_model(self, fold_id: str):
        fold = next((item for item in self.fit["folds"] if item["fold_id"] == fold_id), None)
        if fold is None:
            raise TrainingFailure("Unknown saved fold ID: " + str(fold_id))
        # Recheck the selected bytes before any candidate import or unpickling.
        source, model_bytes = self._bytes("candidate.py"), self._bytes(fold["model"])
        _, joblib, _ = runtime()
        missing = object()
        previous = sys.modules.get("competition_candidate", missing)
        try:
            if self._module is None:
                spec = importlib.util.spec_from_file_location(self._namespace, self.root / "candidate.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules[self._namespace] = module
                sys.modules["competition_candidate"] = module
                try:
                    # Execute the verified source itself, without a potentially stale pyc.
                    exec(compile(source, str(self.root / "candidate.py"), "exec"), module.__dict__)
                except BaseException:
                    sys.modules.pop(self._namespace, None)
                    raise
                self._module = module
            sys.modules["competition_candidate"] = self._module
            return joblib.load(io.BytesIO(model_bytes))
        finally:
            if previous is missing:
                sys.modules.pop("competition_candidate", None)
            else:
                sys.modules["competition_candidate"] = previous


def score(spec: dict, truth: Path, predicted: Path, stage: str, root: Path, split_hash: str) -> dict:
    root.mkdir()
    result = evaluate(EvaluationSpec(truth=truth, predictions=predicted, metric=spec["metric"],
                      stage=stage, split_id=spec["task_id"] + ":" + split_hash,
                      id_column=spec.get("id_column", "id"), target_column=spec.get("target_column", "target"),
                      prediction_column=spec.get("prediction_column", "prediction"),
                      score_kind=spec.get("score_kind", "proxy"), case_profile=spec["metric"] != "roc_auc"), root)
    write_json(root / "result.json", result)
    return result


def recompose(control: Path, member: Path, composition: Path, output: Path, *, control_atol: float = 0) -> dict:
    """Score a declared addition using two sealed fold-model runs; no adapter fits."""
    started = time.perf_counter()
    np, _, limits = runtime()
    if not np.isfinite(control_atol) or control_atol < 0:
        raise TrainingFailure("Control tolerance must be finite and nonnegative")
    if output.exists():
        raise FileExistsError("Recomposition output already exists: " + str(output))
    base = SavedTabularRun(control, kind="tabular_training")
    added = SavedTabularRun(member, kind="tabular_training")
    spec = base.protocol
    if base.fit["cost"]["execution_id"] == added.fit["cost"]["execution_id"]:
        raise TrainingFailure("Use a separate trained member, not a copy of the control execution")
    if any(base.manifest["files"].get(name) != added.manifest["files"].get(name)
           for name in ("training.csv", "inference.csv")):
        raise TrainingFailure("Saved runs must use matching training and inference data")
    if ({k: v for k, v in spec.items() if k != "features"} !=
            {k: v for k, v in added.protocol.items() if k != "features"}):
        raise TrainingFailure("Saved runs must match protocols apart from feature columns, including fold IDs, row order and seeds")
    identifier, column = spec.get("id_column", "id"), spec.get("prediction_column", "prediction")
    features = list(dict.fromkeys(base.protocol["features"] + added.protocol["features"]))
    _, rows = csv_rows(base.root / "training.csv", [identifier, *features], raw=base._bytes("training.csv"))
    _, recorded = csv_rows(base.root / "oof.csv", [identifier, column], raw=base._bytes("oof.csv"))
    source = composition.read_bytes()
    namespace = {"__name__": "competition_composition", "__file__": str(composition)}
    exec(compile(source, str(composition), "exec"), namespace)
    predict_fold = namespace.get("predict_fold")
    if not callable(predict_fold):
        raise TrainingFailure("Composition must define predict_fold(control, member, x_fit, x_score, "
                              "member_x_fit, member_x_score, *, include_member)")
    oof, comparisons = {}, []
    with limits(limits=1):
        for fold in spec["folds"]:
            fold_id, train_ids, valid_ids = fold["id"], fold["train_ids"], fold["validation_ids"]
            model = base.load_model(fold_id)
            x_fit = matrix(np, rows, train_ids, spec["features"])
            x_score = matrix(np, rows, valid_ids, spec["features"])
            new_model = added.load_model(fold_id)
            member_x_fit = matrix(np, rows, train_ids, added.protocol["features"])
            member_x_score = matrix(np, rows, valid_ids, added.protocol["features"])

            def composed(include_member):
                values = predict_fold(model, new_model, x_fit, x_score, member_x_fit, member_x_score,
                                      include_member=include_member)
                return checked_predictions(np, values, len(valid_ids), spec["task"])

            unthresholded = composed(False)
            reproduced = decision_values(np, unthresholded, spec)
            saved = np.array([float(recorded[key][column]) for key in valid_ids])
            error = float(np.max(np.abs(reproduced - saved)))
            if spec["metric"] == "accuracy":
                probabilities = predictions(np, model, x_score, spec["task"])
                error = max(error, float(np.max(np.abs(unthresholded - probabilities))))
            if not np.isfinite(error) or error > control_atol:
                raise TrainingFailure(f"Control reproduction failed on fold {fold_id}: max absolute error {error:.17g} "
                                      f"exceeds {control_atol:.17g}")
            values = decision_values(np, composed(True), spec)
            oof.update(zip(valid_ids, map(float, values)))
            comparisons.append({"fold_id": fold_id, "control_max_abs_error": error,
                                "changed_cases": int(np.count_nonzero(values != reproduced))})
    truth = base._bytes("truth.csv")
    output.mkdir()
    (output / "composition.py").write_bytes(source)
    write_json(output / "recipe.json", {"schema_version": 1, "kind": "tabular_recomposition",
               "composition_source": source.decode("utf-8-sig"),
               "control_recipe_sha256": byte_hash(base._bytes("recipe.json")),
               "member_recipe_sha256": byte_hash(added._bytes("recipe.json"))})
    save_csv(output / "oof.csv", [identifier, column], [(key, repr(oof[key])) for key in spec["expected_oof_ids"]])
    (output / "truth.csv").write_bytes(truth)
    result = score(spec, output / "truth.csv", output / "oof.csv", "development", output / "evaluation",
                   base.manifest["protocol_hash"])
    report = {"new_fit_calls": 0, "recomposition_seconds": time.perf_counter() - started,
              "inputs": {name: {"run": str(run.root), "seal": run.manifest["seal"], "originating_cost": run.fit["cost"]}
                         for name, run in (("control", base), ("member", added))},
              "control_atol": control_atol, "folds": comparisons,
              "scope": "Development predictions. No adapter fits during recomposition; arbitrary composition code and "
                       "its information flow are not certified."}
    write_json(output / "recomposition.json", report)
    manifest = seal(output, {"kind": "tabular_recomposition", "task_id": spec["task_id"],
                            "score": result["score"], "protocol_hash": base.manifest["protocol_hash"]})
    return {"status": "success", "manifest": str(output / "manifest.json"), "seal": manifest["seal"],
            "result": str(output / "evaluation/result.json"), "score": result["score"], **report}


def train(data: Path, protocol: Path, candidate: Path, output: Path, *, archive: Path | None = None,
          proposal_id: str | None = None, inference_data: Path | None = None,
          retry_reason: str | None = None, expected_fit_calls: int | None = None,
          measurement_archive: Path | None = None, measurement_plan_id: str | None = None,
          measurement_run_id: str | None = None) -> dict:
    data, protocol, candidate, output = [path.expanduser().resolve()
                                         for path in [data, protocol, candidate, output]]
    archive = archive.expanduser().resolve() if archive is not None else None
    inference_data = inference_data.expanduser().resolve() if inference_data is not None else None
    workflow_started = time.perf_counter()
    protocol_raw = protocol.read_bytes()
    spec = json.loads(protocol_raw)
    folds = protocol_folds(spec)
    check_fit_count(len(folds), expected_fit_calls)
    measuring = any(value is not None for value in (measurement_archive, measurement_plan_id, measurement_run_id))
    if measuring and (not all((measurement_archive, measurement_plan_id, measurement_run_id)) or expected_fit_calls is None):
        raise TrainingFailure("Managed measurement needs its archive, plan ID, run ID and expected fit count")
    np, joblib, limits = runtime()
    inputs = {"training.csv": data.read_bytes(), "protocol.json": protocol_raw,
              "candidate.py": candidate.read_bytes()}
    identifier, target = spec.get("id_column", "id"), spec.get("target_column", "target")
    _, rows = csv_rows(data, [identifier, target, *spec["features"], *metadata_columns(spec)], raw=inputs["training.csv"])
    used, evaluated = set(), set()
    for fold in folds:
        training, validation = fold["train_ids"], fold["validation_ids"]
        if not set(training + validation) <= rows.keys() or evaluated & set(validation):
            raise TrainingFailure("Fold references unknown IDs or duplicates OOF coverage")
        check_boundary(spec, {key: rows[key] for key in training}, {key: rows[key] for key in validation})
        used.update(training + validation)
        evaluated.update(validation)
    if used != rows.keys() or evaluated != set(spec["expected_oof_ids"]):
        raise TrainingFailure("Dataset or declared OOF coverage is incomplete")
    if spec["split"]["kind"] in {"iid", "group"} and evaluated != rows.keys():
        raise TrainingFailure("Non-temporal OOF must cover every training data row exactly once")
    matrix(np, rows, list(rows), spec["features"])
    for fold in folds:
        labels = np.array([float(rows[key][target]) for key in fold["train_ids"]])
        if not np.isfinite(labels).all() or (spec["task"] == "binary" and set(labels) != {0, 1}):
            raise TrainingFailure("Training labels must be finite; binary folds require both 0 and 1")
    inference_rows = None
    if inference_data is not None:
        inputs["inference.csv"] = inference_data.read_bytes()
        _, inference_rows = csv_rows(inference_data, [identifier, *metadata_columns(spec, training=False)],
                                     raw=inputs["inference.csv"])
        check_boundary(spec, rows, inference_rows)
    relation_report = relation_preflight(spec, rows, inference_rows)
    execution_environment = environment()
    adapter_hash = object_hash({name: byte_hash(Path(__file__).with_name(name).read_bytes()) for name in
                               ["tabular_training.py", "training_execution.py", "audit_data_split.py"]})
    # Stable implementation identity excludes output bytes, timing and fold measurement seeds.
    recipe = {"schema_version": 1, "task": spec["task"], "features": spec["features"],
              "id_column": identifier, "target_column": target,
              "candidate_source": inputs["candidate.py"].decode("utf-8-sig"),
              "training_data_sha256": byte_hash(inputs["training.csv"]),
              "prediction_rule": ({"operation": "mean_probability_then_greater_equal",
                                   "threshold": spec.get("decision_threshold", 0.5)}
                                  if spec["metric"] == "accuracy" else {"operation": "mean"}),
              "environment": execution_environment, "adapter_hash": adapter_hash}
    identity = {"inputs": {name: byte_hash(raw) for name, raw in inputs.items()},
                "environment": execution_environment, "adapter_hash": adapter_hash,
                "evaluator_hash": evaluator_fingerprint()}
    if measuring:
        measurement = measurement_binding(measurement_archive, measurement_plan_id, measurement_run_id,
                                          protocol=protocol_raw, folds=folds, recipe=recipe)
        identity["measurement"] = measurement
    identity_hash = object_hash(identity)
    binding = proposal_binding(archive, proposal_id, allow_closed=True)
    if retry_reason is not None and not retry_reason.strip():
        raise TrainingFailure("An intentional repeat requires a nonempty retry reason")
    # Sibling directories are the normal runs area. Never silently repeat an exact
    # request after interruption or because its output directory was renamed.
    matching = []
    for launch_path in sorted(output.parent.glob("*/execution.json")):
        if read_json(launch_path).get("identity_hash") == identity_hash:
            manifest_path = launch_path.parent / "manifest.json"
            if manifest_path.exists() and read_json(manifest_path).get("kind") != "tabular_training":
                continue
            matching.append(launch_path.parent)
    if output.exists() and output not in matching:
        raise FileExistsError("Training output already exists: " + str(output))
    matching.sort(key=lambda path: path.resolve() != output.resolve())
    if retry_reason is None and matching:
        for previous in matching:
            if not (previous / "manifest.json").exists():
                continue
            manifest = verified_manifest(previous, "tabular_training")
            previous_binding = read_json(previous / "execution.json")["proposal"]
            if any(previous_binding.get(key) != binding.get(key)
                   for key in ["status", "proposal_id", "proposal_sha256"]):
                raise TrainingFailure("Matching execution has different proposal provenance; reuse it as historical "
                                      "evidence or give an explicit --retry-reason for a new measurement")
            if previous.resolve() != output.resolve():
                output.mkdir()
                for name in [*manifest["files"], "manifest.json"]:
                    destination = output / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(previous / name, destination)
            return {"status": "success", "manifest": str(output / "manifest.json"), "seal": manifest["seal"],
                    "result": str(output / "evaluation/result.json"), "score": manifest["score"],
                    "reused_from": str(previous), "new_fit_calls": 0, "originating_cost": fit_cost(previous)}
        raise TrainingFailure("Matching incomplete execution exists; inspect its fit-events.jsonl. "
                              "Use --retry-reason for an intentional new attempt")
    binding = proposal_binding(archive, proposal_id)
    # All learned preprocessing is fitted within the estimator's fit call on these rows.
    output.mkdir()
    for name, raw in inputs.items():
        (output / name).write_bytes(raw)
    write_json(output / "recipe.json", recipe)
    launch = {"schema_version": 1, "execution_id": uuid.uuid4().hex,
              **identity, "identity_hash": identity_hash, "proposal": binding,
              "retry_reason": retry_reason, "previous_attempts": [str(path) for path in matching],
              "relations": relation_report}
    write_json(output / "execution.json", launch)
    journal = output / "fit-events.jsonl"
    append_event(journal, {"event": "run_started", "execution_id": launch["execution_id"]})
    module_spec = importlib.util.spec_from_file_location("competition_candidate", output / "candidate.py")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    oof, receipts = {}, []
    (output / "models").mkdir()
    with limits(limits=1):
        for index, fold in enumerate(folds):
            train_ids, valid_ids = fold["train_ids"], fold["validation_ids"]
            features = matrix(np, rows, train_ids, spec["features"])
            labels = np.array([float(rows[key][target]) for key in train_ids])
            model = module.build_model(fold["seed"], spec["task"])
            append_event(journal, {"event": "fit_started", "fold_id": fold["id"], "seed": fold["seed"]})
            started = time.perf_counter()
            try:
                model.fit(features, labels)
            except BaseException as exc:
                append_event(journal, {"event": "fit_failed", "fold_id": fold["id"],
                                      "fit_seconds": time.perf_counter() - started,
                                      "error_type": type(exc).__name__, "message": str(exc)})
                raise
            fitting = time.perf_counter() - started
            append_event(journal, {"event": "fit_completed", "fold_id": fold["id"], "fit_seconds": fitting})
            started = time.perf_counter()
            values = predictions(np, model, matrix(np, rows, valid_ids, spec["features"]), spec["task"])
            inference = time.perf_counter() - started
            oof.update(zip(valid_ids, map(float, decision_values(np, values, spec))))
            model_name = f"models/fold-{index}.joblib"
            joblib.dump(model, output / model_name)
            receipts.append({"fold_id": fold["id"], "seed": fold["seed"], "train_ids": train_ids,
                             "validation_ids": valid_ids, "train_id_hash": object_hash(train_ids),
                             "validation_id_hash": object_hash(valid_ids), "model": model_name,
                             "fit_seconds": fitting, "prediction_seconds": inference,
                             "model_bytes": (output / model_name).stat().st_size})
    ordered = spec["expected_oof_ids"]
    save_csv(output / "oof.csv", [identifier, spec.get("prediction_column", "prediction")],
             [(key, repr(oof[key])) for key in ordered])
    save_csv(output / "truth.csv", [identifier, target], [(key, rows[key][target]) for key in ordered])
    result = score(spec, output / "truth.csv", output / "oof.csv", "development", output / "evaluation",
                   object_hash(spec))
    if measuring:
        result["evaluation"].update({name: value for name, value in measurement.items() if name != "plan_sha256"})
    append_event(journal, {"event": "run_completed", "elapsed_seconds": time.perf_counter() - workflow_started})
    result["training_execution"] = execution_descriptor(output)
    # Bind the completed fitting receipt before sealing this new result.
    (output / "evaluation/result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    write_json(output / "fit.json", {"folds": receipts, "environment": execution_environment,
               "adapter_hash": adapter_hash, "preprocessing_scope": "estimator.fit(training_rows)",
               "cost": result["training_execution"]["cost"],
               "oof_aggregation": "one prediction per declared row; pooled unweighted metric",
               "inference_recipe": ("arithmetic mean of fold probabilities, then fixed decision_threshold"
                                    if spec["metric"] == "accuracy" else
                                    "arithmetic mean of all fitted fold model predictions"),
               "unchecked": ["arbitrary_candidate_code_access", "upstream_feature_leakage", "competition_rules",
                             "prior_confirmation_exposure", "resource_limits"]})
    manifest = seal(output, {"kind": "tabular_training", "task_id": spec["task_id"],
                            "score": result["score"], "protocol_hash": object_hash(spec)})
    return {"status": "success", "manifest": str(output / "manifest.json"), "seal": manifest["seal"],
            "result": str(output / "evaluation/result.json"), "score": result["score"],
            "new_fit_calls": len(receipts), "cost": result["training_execution"]["cost"]}


def rescore(run: Path, evaluator: Path, reference: Path, output: Path) -> dict:
    """Score sealed OOF with a pinned saved evaluator; never import candidate code or fit."""
    run, evaluator, reference, output = [path.expanduser().resolve()
                                         for path in (run, evaluator, reference, output)]
    original_path = run / "evaluation/result.json"
    original, expected = load_result(original_path), load_result(reference)
    if original["evaluation"]["stage"] != "development" or expected["evaluation"]["stage"] != "development":
        raise TrainingFailure("Rescore accepts development training results and references only")
    if (original["evaluation"]["configuration"] != expected["evaluation"]["configuration"] or
            original["score_model_hash"] != expected["score_model_hash"]):
        raise TrainingFailure("Reference scoring inputs differ from the sealed training protocol")
    descriptor = original.get("training_execution")
    if not isinstance(descriptor, dict):
        raise TrainingFailure("Rescore requires an original managed training receipt")
    verify_training_source(original_path, descriptor)
    if (byte_hash((run / "oof.csv").read_bytes()) != original["candidate_hash"] or
            byte_hash((run / "truth.csv").read_bytes()) != original["evaluation"]["split_hash"]):
        raise TrainingFailure("Sealed OOF or truth differs from the original result")
    if evaluator.name != "evaluate_predictions.py":
        raise TrainingFailure("Select the saved evaluate_predictions.py and its sibling prediction_core.py")
    scorer = {name: evaluator.with_name(name).read_bytes() for name in
              ["evaluate_predictions.py", "prediction_core.py"]}
    backend = expected["evaluation"].get("runtime_environment", {}).get("metric_backend")
    if backend is not None:
        try:
            installed = metric_backend()
        except PredictionFailure as exc:
            raise TrainingFailure(str(exc)) from exc
        if backend != installed:
            raise TrainingFailure("Saved evaluator requires the reference numeric dependency versions")
    if scorer_fingerprint(evaluator.parent, backend) != expected["evaluator_hash"]:
        raise TrainingFailure("Saved evaluator does not match the reference evaluator hash")
    output.mkdir()
    (output / "scorer").mkdir()
    for name, raw in scorer.items():
        (output / "scorer" / name).write_bytes(raw)
    write_json(output / "reference-result.json", expected)
    config = original["evaluation"]["configuration"]
    model = config["score_model"]
    command = [sys.executable, "-B", str(output / "scorer/evaluate_predictions.py"),
               "--truth", str(run / "truth.csv"), "--predictions", str(run / "oof.csv"),
               "--stage", config["stage"], "--split-id", config["split_id"],
               "--metric", model["metric"], "--score-kind", model["kind"],
               "--id-column", config["id_column"], "--target-column", config["target_column"],
               "--prediction-column", config["prediction_column"],
               "--output-dir", str(output / "evaluation")]
    if model["metric"] == "binary_log_loss":
        command += ["--log-loss-epsilon", str(model["parameters"]["epsilon"])]
    if "case_profile" in original:
        command.append("--case-profile")
    outcome = subprocess.run(command, capture_output=True, text=True)
    (output / "scorer.stdout").write_text(outcome.stdout)
    (output / "scorer.stderr").write_text(outcome.stderr)
    if outcome.returncode:
        raise TrainingFailure("Saved evaluator failed; inspect " + str(output / "scorer.stderr"))
    result_path = output / "evaluation/result.json"
    result = load_result(result_path)
    compare(expected, result, 0)
    if result["evaluation"] != expected["evaluation"] or result["candidate_hash"] != original["candidate_hash"]:
        raise TrainingFailure("Rescore differs from the pinned reference contract or original predictions")
    result["training_execution"] = {**descriptor, "rescore": {
        "source_run": str(run), "source_manifest_sha256": byte_hash((run / "manifest.json").read_bytes()),
        "source_result_sha256": byte_hash(original_path.read_bytes())}}
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    manifest = seal(output, {"kind": "tabular_rescore", "new_fit_calls": 0})
    return {"status": "success", "result": str(result_path), "manifest": str(output / "manifest.json"),
            "seal": manifest["seal"], "new_fit_calls": 0, "evaluator_hash": result["evaluator_hash"],
            "configuration": str(run / "recipe.json"), "score": result["score"],
            "originating_cost": descriptor["cost"]}


def submission_spec(spec: dict, column: str | None = None, inverse_transform: str = "identity") -> dict:
    identifier = spec.get("id_column", "id")
    column = spec.get("prediction_column", "prediction") if column is None else column
    if not isinstance(column, str) or not column.strip() or column == identifier:
        raise TrainingFailure("Submission column must be nonempty and distinct from the ID column")
    if inverse_transform not in {"identity", "exp", "expm1"}:
        raise TrainingFailure("Submission inverse transform must be identity, exp or expm1")
    if spec["task"] != "regression" and inverse_transform != "identity":
        raise TrainingFailure("Submission inverse transforms apply only to regression")
    return {"id_column": identifier, "prediction_column": column, "inverse_transform": inverse_transform}


def freeze(run: Path, output: Path, decision_rule: str, *, submission_column: str | None = None,
           inverse_transform: str = "identity") -> dict:
    manifest = verified_manifest(run, "tabular_training")
    if not decision_rule.strip():
        raise TrainingFailure("Freeze a delivery decision rule before confirmation")
    submission = submission_spec(read_json(run / "protocol.json"), submission_column, inverse_transform)
    output.mkdir()
    for name, expected in manifest["files"].items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (run / name).read_bytes()
        if byte_hash(raw) != expected:
            raise TrainingFailure("Training artifact changed while freezing: " + name)
        destination.write_bytes(raw)
    frozen = seal(output, {"kind": "tabular_frozen", "training_seal": manifest["seal"],
                          "decision_rule": decision_rule, "protocol_hash": manifest["protocol_hash"],
                          "submission": submission})
    return {"status": "frozen", "manifest": str(output / "manifest.json"), "seal": frozen["seal"],
            "submission": submission}


def deliver(frozen: Path, data: Path, output: Path, *, truth: Path | None = None,
            sample_submission: Path | None = None) -> dict:
    if output.exists():
        raise FileExistsError("Delivery output already exists: " + str(output))
    np, _, limits = runtime()
    saved = SavedTabularRun(frozen, kind="tabular_frozen")
    manifest, spec, receipt = saved.manifest, saved.protocol, saved.fit
    identifier, column = spec.get("id_column", "id"), spec.get("prediction_column", "prediction")
    # Historical frozen runs have no submission declaration and retain identity output.
    submission = manifest.get("submission", submission_spec(spec))
    submission_column = submission["prediction_column"]
    inverse_transform = submission["inverse_transform"]
    _, training = csv_rows(frozen / "training.csv", [identifier, *metadata_columns(spec)])
    _, rows = csv_rows(data, [identifier, *spec["features"], *metadata_columns(spec, training=False)])
    check_boundary(spec, training, rows)
    relation_preflight(spec, training, rows)
    ids = list(rows)
    boolean_submission = False
    sample_raw = None
    if sample_submission is not None:
        sample_raw = sample_submission.read_bytes()
        header, sample = csv_rows(sample_submission, [identifier, submission_column], raw=sample_raw)
        if header != [identifier, submission_column] or sample.keys() != rows.keys():
            raise TrainingFailure("Sample submission must have exact ID/prediction columns and matching IDs")
        ids = list(sample)
        boolean_submission = (spec["metric"] == "accuracy"
                              and {row[submission_column] for row in sample.values()} <= {"True", "False"})
    started = time.perf_counter()
    with limits(limits=1):
        features = matrix(np, rows, ids, spec["features"])
        values = np.zeros(len(ids))
        for fold in receipt["folds"]:
            model = saved.load_model(fold["fold_id"])
            values += predictions(np, model, features, spec["task"]) / len(receipt["folds"])
        values = decision_values(np, values, spec)
    if not np.isfinite(values).all():
        raise TrainingFailure("Averaged predictions must be finite")
    submission_values = values
    if sample_submission is not None and inverse_transform != "identity":
        # Apply the sealed inverse once, after averaging in the model's target space.
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            submission_values = getattr(np, inverse_transform)(values)
        if (not np.isfinite(submission_values).all()
                or (inverse_transform == "exp" and (submission_values <= 0).any())):
            raise TrainingFailure("Submission inverse transform produced non-finite values or underflow")
    output.mkdir()
    raw_prediction_path = output / "predictions.csv"
    save_csv(raw_prediction_path, [identifier, column],
             [(key, repr(float(value))) for key, value in zip(ids, values)])
    submission_path = None
    if sample_submission is not None:
        submission_path = output / "submission.csv"
        save_csv(submission_path, [identifier, submission_column],
                 [(key, str(bool(value)) if boolean_submission else repr(float(value)))
                  for key, value in zip(ids, submission_values)])
    prediction_path = submission_path or raw_prediction_path
    report = {"status": "success", "frozen_seal": manifest["seal"], "decision_rule": manifest["decision_rule"],
              "data_hash": byte_hash(data.read_bytes()), "prediction_hash": byte_hash(prediction_path.read_bytes()),
              "prediction_path": str(prediction_path.resolve()),
              "raw_prediction_path": str(raw_prediction_path.resolve()),
              "raw_prediction_hash": byte_hash(raw_prediction_path.read_bytes()),
              "submission": submission,
              "submission_path": str(submission_path.resolve()) if submission_path else None,
              "submission_hash": byte_hash(submission_path.read_bytes()) if submission_path else None,
              "prediction_seconds": time.perf_counter() - started, "row_count": len(ids),
              "prediction_encoding": "boolean" if boolean_submission else "numeric",
              "sample_submission_hash": byte_hash(sample_raw) if sample_raw is not None else None}
    if truth is not None:
        # Confirmation is first read here, after frozen model selection and inference.
        result = score(spec, truth, raw_prediction_path, "confirmation", output / "evaluation",
                       manifest["protocol_hash"] + ":confirmation")
        report["score"] = result["score"]
    write_json(output / "delivery.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    fit = commands.add_parser("train")
    for name in ["data", "protocol", "candidate"]:
        fit.add_argument("--" + name, type=Path, required=True)
    fit.add_argument("--archive", type=Path)
    fit.add_argument("--proposal-id")
    fit.add_argument("--inference-data", type=Path, help="Unlabeled inference CSV for relation availability checks")
    fit.add_argument("--retry-reason", help="Explicit intentional repeat, including after an interrupted fit")
    fit.add_argument("--expected-fit-calls", type=int, help="Reject a protocol with a different number of folds before fitting")
    fit.add_argument("--measurement-archive", type=Path, help="Archive containing the frozen paired run")
    fit.add_argument("--measurement-plan-id")
    fit.add_argument("--measurement-run-id")
    plan = commands.add_parser("plan-cost", help="Count prospective fits from the exact protocol files; zero fits")
    plan.add_argument("--protocol", type=Path, action="append", required=True,
                      help="Repeat once for every planned new execution")
    plan.add_argument("--expected-fit-calls", type=int, help="Reject a mismatch with the total declared fit count")
    costs = commands.add_parser("cost")
    costs.add_argument("--run", type=Path, action="append", required=True,
                       help="Repeat for all attempts/copies; each execution is counted once")
    rescoring = commands.add_parser("rescore", help="Reuse sealed OOF with a saved reference evaluator; zero fits")
    for name in ["run", "evaluator", "reference-result"]:
        rescoring.add_argument("--" + name, type=Path, required=True)
    recomposing = commands.add_parser("recompose", help="Reuse a sealed control and separately trained member on matched folds")
    for name in ["control", "member", "composition"]:
        recomposing.add_argument("--" + name, type=Path, required=True)
    recomposing.add_argument("--control-atol", type=float, default=0,
                             help="Declared absolute reproduction tolerance; defaults to exact")
    frozen = commands.add_parser("freeze")
    frozen.add_argument("--run", type=Path, required=True)
    frozen.add_argument("--decision-rule", required=True)
    frozen.add_argument("--submission-column", help="Official target column; defaults to the protocol prediction column")
    frozen.add_argument("--inverse-transform", choices=["identity", "exp", "expm1"], default="identity",
                        help="Sealed submission-only inverse of the model target; confirmation keeps the original scale")
    for command in ["confirm", "predict"]:
        p = commands.add_parser(command)
        p.add_argument("--frozen", type=Path, required=True)
        p.add_argument("--data", type=Path, required=True)
        p.add_argument("--truth" if command == "confirm" else "--sample-submission", type=Path, required=True)
    for p in [fit, rescoring, recomposing, frozen, *[commands.choices[name] for name in ["confirm", "predict"]]]:
        p.add_argument("--output-dir", type=Path, required=True, help="New directory; parent must exist")
    args = parser.parse_args()
    try:
        if args.operation == "train":
            report = train(args.data, args.protocol, args.candidate, args.output_dir, archive=args.archive,
                           proposal_id=args.proposal_id, inference_data=args.inference_data, retry_reason=args.retry_reason,
                           expected_fit_calls=args.expected_fit_calls, measurement_archive=args.measurement_archive,
                           measurement_plan_id=args.measurement_plan_id, measurement_run_id=args.measurement_run_id)
        elif args.operation == "plan-cost":
            report = plan_cost(args.protocol, args.expected_fit_calls)
        elif args.operation == "cost":
            report = cost_report(args.run)
        elif args.operation == "rescore":
            report = rescore(args.run, args.evaluator, args.reference_result, args.output_dir)
        elif args.operation == "recompose":
            report = recompose(args.control, args.member, args.composition, args.output_dir,
                               control_atol=args.control_atol)
        elif args.operation == "freeze":
            report = freeze(args.run, args.output_dir, args.decision_rule,
                            submission_column=args.submission_column, inverse_transform=args.inverse_transform)
        else:
            report = deliver(args.frozen, args.data, args.output_dir,
                             truth=getattr(args, "truth", None), sample_submission=getattr(args, "sample_submission", None))
        print(json.dumps(report, allow_nan=False, indent=2))
        return 0
    except Exception as exc:
        # Estimator errors are failures too; never emit a successful fit receipt for them.
        print(json.dumps({"status": "failed", "error": {"type": type(exc).__name__, "message": str(exc)}}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
