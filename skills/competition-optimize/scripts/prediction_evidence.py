#!/usr/bin/env python3
"""Verify prediction evidence and match saved tabular OOF without loading models."""

from __future__ import annotations

import argparse
import csv
import io
import json
import pathlib
import sys
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

import evaluate_predictions as evaluator
from prediction_core import PredictionFailure, compare, load_result


class EvidenceFailure(Exception):
    pass


@dataclass
class PredictionPair:
    paths: dict[str, pathlib.Path]
    input_hashes: dict[str, str]
    comparison: dict[str, Any]
    configuration: dict[str, Any]
    metric: str
    epsilon: float
    sample_ids: list[str]
    labels: list[float]
    baseline: list[float]
    candidate: list[float]
    prediction_bytes: list[bytes]


def _training_hashes(root: pathlib.Path, role: str, *,
                     kinds: tuple[str, ...] = ("tabular_training",)) -> dict[str, str]:
    manifest = json.loads((root / "manifest.json").read_bytes())
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or manifest.get("kind") not in kinds
            or manifest.get("seal") != evaluator.object_hash({k: v for k, v in manifest.items() if k != "seal"})):
        raise EvidenceFailure(f"{role} fold analysis requires a sealed manifest of kind {' or '.join(kinds)}")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise EvidenceFailure(f"{role} training manifest requires artifact hashes")
    return files


def _verified_folds(raw: bytes, files: dict[str, str], *, oof_hash: str, truth_hash: str,
                    sample_ids: Collection[str], role: str) -> tuple[dict[str, tuple[set[str], set[str]]], str]:
    digest = evaluator.byte_hash(raw)
    if files.get("fit.json") != digest:
        raise EvidenceFailure(f"{role} fit.json differs from its training manifest")
    if files.get("oof.csv") != oof_hash or files.get("truth.csv") != truth_hash:
        raise EvidenceFailure(f"{role} fit receipt belongs to different OOF predictions or truth")
    receipt = json.loads(raw)
    rows = receipt.get("folds") if isinstance(receipt, dict) else None
    if not isinstance(rows, list) or not rows:
        raise EvidenceFailure(f"{role} fit receipt must have nonempty folds")
    folds: dict[str, tuple[set[str], set[str]]] = {}
    covered: set[str] = set()
    for row in rows:
        name = row.get("fold_id") if isinstance(row, dict) else None
        if not isinstance(name, str) or not name.strip() or name in folds:
            raise EvidenceFailure(f"{role} fit receipt must have unique nonempty fold IDs")
        memberships = []
        for key in ("train_ids", "validation_ids"):
            ids = row.get(key)
            if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not i for i in ids)
                    or len(set(ids)) != len(ids)):
                raise EvidenceFailure(f"{role} fold {name!r} has invalid {key}")
            memberships.append(set(ids))
        train, validation = memberships
        if train & validation or covered & validation:
            raise EvidenceFailure(f"{role} fold {name!r} overlaps training with validation or duplicates OOF rows")
        folds[name] = train, validation
        covered.update(validation)
    if covered != set(sample_ids):
        raise EvidenceFailure(f"{role} validation folds must cover the evaluated IDs exactly once")
    return folds, digest


def load_fold_receipt(path: pathlib.Path, pair: PredictionPair, role: str
                      ) -> tuple[dict[str, tuple[set[str], set[str]]], pathlib.Path, str]:
    """Bind recorded fold membership to the OOF bytes already verified by load_pair."""
    path = path.expanduser().resolve(strict=True)
    if path.name != "fit.json":
        raise EvidenceFailure(f"{role} fold analysis requires a saved tabular training fit.json")
    files = _training_hashes(path.parent, role)
    folds, digest = _verified_folds(path.read_bytes(), files, oof_hash=pair.comparison[role]["candidate_hash"],
                                    truth_hash=pair.input_hashes["truth"], sample_ids=pair.sample_ids, role=role)
    return folds, path, digest


def fold_membership(folds: dict[str, tuple[set[str], set[str]]]) -> list[tuple[list[str], list[str]]]:
    """Pair each validation set with its training set, independent of names and order."""
    return sorted((sorted(validation), sorted(train)) for train, validation in folds.values())


def load_saved_oof_evidence(path: pathlib.Path) -> dict[str, Any]:
    """Verify saved scalar OOF, truth and fold membership without opening models."""
    path = path.expanduser().resolve(strict=True)
    if path.name != "oof.csv":
        raise EvidenceFailure("Select oof.csv in a sealed tabular training run or frozen copy")
    root = path.parent
    files = _training_hashes(root, str(path), kinds=("tabular_training", "tabular_frozen"))
    protocol_raw = (root / "protocol.json").read_bytes()
    if files.get("protocol.json") != evaluator.byte_hash(protocol_raw):
        raise EvidenceFailure("protocol.json differs from its training manifest")
    protocol = json.loads(protocol_raw)
    if not isinstance(protocol, dict):
        raise EvidenceFailure("Training protocol must be a JSON object")
    columns = [protocol.get(name, default) for name, default in
               [("id_column", "id"), ("target_column", "target"), ("prediction_column", "prediction")]]
    if any(not isinstance(name, str) or not name.strip() for name in columns) or len(set(columns)) != 3:
        raise EvidenceFailure("Training protocol requires distinct ID, target and prediction columns")
    id_column, target_column, prediction_column = columns
    truth_raw, oof_raw = (root / "truth.csv").read_bytes(), path.read_bytes()
    truth = evaluator.read_values(truth_raw, id_column, target_column, "truth")
    oof = evaluator.read_values(oof_raw, id_column, prediction_column, "OOF")
    if truth.keys() != oof.keys():
        raise EvidenceFailure("OOF IDs must match truth IDs exactly")
    truth_hash, oof_hash = evaluator.byte_hash(truth_raw), evaluator.byte_hash(oof_raw)
    folds, fit_hash = _verified_folds((root / "fit.json").read_bytes(), files, oof_hash=oof_hash,
                                     truth_hash=truth_hash, sample_ids=truth.keys(), role=str(path))
    return {"oof": str(path), "oof_sha256": oof_hash, "truth_sha256": truth_hash, "fit_sha256": fit_hash,
            "fold_membership_sha256": evaluator.object_hash(fold_membership(folds)), "fold_count": len(folds),
            "scored_rows": len(truth)}


def match_saved_oof(reference: pathlib.Path, candidates: list[pathlib.Path]) -> dict[str, Any]:
    """Group saved OOF by verified truth bytes and actual fold memberships."""
    control = load_saved_oof_evidence(reference)
    counts = dict.fromkeys(("matched", "different_folds", "different_truth", "unverified"), 0)
    rows = []
    for path in candidates:
        try:
            row = load_saved_oof_evidence(path)
            if row["truth_sha256"] != control["truth_sha256"]:
                row["status"] = "different_truth"
            elif row["fold_membership_sha256"] != control["fold_membership_sha256"]:
                row["status"] = "different_folds"
            else:
                row["status"] = "matched"
        except (EvidenceFailure, OSError, PredictionFailure, ValueError) as exc:
            row = {"oof": str(path.expanduser().absolute()), "status": "unverified", "reason": str(exc)}
        counts[row["status"]] += 1
        rows.append(row)
    return {"reference": control, "counts": counts, "candidates": rows}


def load_pair(baseline: pathlib.Path, candidate: pathlib.Path, truth: pathlib.Path) -> PredictionPair:
    paths = {role: path.expanduser().resolve(strict=True)
             for role, path in [("baseline", baseline), ("candidate", candidate), ("truth", truth)]}
    result_bytes = [paths[role].read_bytes() for role in ["baseline", "candidate"]]
    results = [load_result(paths[role]) for role in ["baseline", "candidate"]]
    comparison = compare(*results, 0)
    if results[0]["evaluator_hash"] != evaluator.evaluator_fingerprint():
        raise EvidenceFailure(
            "Analysis requires results from the installed prediction evaluator. "
            "If the saved predictions and truth still apply, score both CSVs with evaluate_predictions.py "
            "under one shared protocol and pass the two new result.json files."
        )
    config = results[0]["evaluation"]["configuration"]
    for key in ["id_column", "target_column", "prediction_column"]:
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise EvidenceFailure("Evaluation must declare non-empty CSV columns")
    if config["id_column"] in {config["target_column"], config["prediction_column"]}:
        raise EvidenceFailure("ID column must differ from numeric value columns")
    metric = results[0]["score"]["metric"]
    model = config["score_model"]
    parameters = model.get("parameters")
    if (model.get("aggregation") != "unweighted over all aligned rows" or not isinstance(parameters, dict)
            or set(parameters) != ({"epsilon"} if metric == "binary_log_loss" else set())):
        raise EvidenceFailure("Unsupported prediction score formula or parameters")
    epsilon = parameters.get("epsilon", 1e-15)
    if type(epsilon) not in {int, float}:
        raise EvidenceFailure("Log-loss epsilon must be a number")
    truth_raw = paths["truth"].read_bytes()
    if evaluator.byte_hash(truth_raw) != results[0]["evaluation"]["split_hash"]:
        raise EvidenceFailure("Truth bytes differ from the evaluated split")
    prediction_bytes = []
    for role, result, original in zip(["baseline", "candidate"], results, result_bytes):
        if paths[role].read_bytes() != original:
            raise EvidenceFailure("Evaluation record changed while reading evidence")
        raw = (paths[role].parent / "predictions.csv").read_bytes()
        if evaluator.byte_hash(raw) != result["candidate_hash"]:
            raise EvidenceFailure("Prediction snapshot changed while reading evidence")
        prediction_bytes.append(raw)
    labels = evaluator.read_values(truth_raw, config["id_column"], config["target_column"], "truth")
    predictions = [evaluator.read_values(raw, config["id_column"], config["prediction_column"], role)
                   for raw, role in zip(prediction_bytes, ["baseline", "candidate"])]
    if any(values.keys() != labels.keys() for values in predictions):
        raise EvidenceFailure("Prediction IDs differ from the evaluated truth")
    if len(labels) != results[0]["evaluation"]["completed_cases"]:
        raise EvidenceFailure("Prediction row count differs from the evaluation")
    sample_ids = sorted(labels)
    ordered_truth = [labels[key] for key in sample_ids]
    before, after = [[values[key] for key in sample_ids] for values in predictions]
    for result, values in zip(results, [before, after]):
        if evaluator.calculate_metric(metric, ordered_truth, values, epsilon) != result["score"]["value"]:
            raise EvidenceFailure("Recomputed score differs from its evaluation record")
    hashes = {"baseline_result": evaluator.byte_hash(result_bytes[0]),
              "candidate_result": evaluator.byte_hash(result_bytes[1]), "truth": evaluator.byte_hash(truth_raw)}
    return PredictionPair(paths, hashes, comparison, config, metric, epsilon, sample_ids,
                          ordered_truth, before, after, prediction_bytes)


def read_categories(raw: bytes, id_column: str, columns: list[str], sample_ids: set[str]) -> dict[str, dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        fields = reader.fieldnames
        if (not fields or any(not field.strip() for field in fields) or len(set(fields)) != len(fields)
                or any(column not in fields for column in [id_column, *columns])):
            raise EvidenceFailure("Metadata CSV needs unique column names and the requested ID/category columns")
        rows: dict[str, dict[str, str]] = {}
        for row_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise EvidenceFailure(f"Metadata CSV has a wrong field count at row {row_number}")
            sample_id = row[id_column]
            if not sample_id.strip() or sample_id in rows:
                raise EvidenceFailure(f"Metadata CSV has an empty or duplicate ID at row {row_number}")
            if any(not row[column].strip() for column in columns):
                raise EvidenceFailure(f"Category values must be non-empty at row {row_number}")
            rows[sample_id] = {column: row[column] for column in columns}
        if rows.keys() != sample_ids:
            raise EvidenceFailure("Metadata IDs must exactly match the evaluated split")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise EvidenceFailure(f"Invalid metadata CSV: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=pathlib.Path, required=True, help="Sealed reference oof.csv")
    parser.add_argument("candidates", type=pathlib.Path, nargs="+", help="Saved oof.csv paths to check")
    args = parser.parse_args()
    try:
        report = match_saved_oof(args.reference, args.candidates)
    except (EvidenceFailure, OSError, PredictionFailure, ValueError) as exc:
        print(json.dumps({"status": "failed", "reference": str(args.reference), "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
