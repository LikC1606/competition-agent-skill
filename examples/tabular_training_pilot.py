#!/usr/bin/env python3
"""Real OOF -> frozen confirmation -> sample-aligned CSV integration exercise."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.model_selection import KFold, train_test_split
from sklearn.metrics import root_mean_squared_error

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/competition-optimize/scripts"
sys.path.insert(0, str(SCRIPTS))
from tabular_training import train, freeze, deliver, save_csv, write_json, csv_rows
from prediction_core import compare, load_result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    root.mkdir()
    data = load_diabetes(scaled=False)  # Default global scaling would cross folds.
    development, holdout = train_test_split(np.arange(len(data.target)), test_size=0.2, random_state=1729)
    features = [f"x{i}" for i in range(data.data.shape[1])]
    save_csv(root / "training.csv", ["id", *features, "target"],
             [(str(i), *map(float, data.data[i]), float(data.target[i])) for i in development])
    save_csv(root / "confirmation-features.csv", ["id", *features],
             [(str(i), *map(float, data.data[i])) for i in holdout])
    # Holdout labels are prepared here as a fixture; the selection below only reads OOF results.
    save_csv(root / "confirmation-truth.csv", ["id", "target"],
             [(str(i), float(data.target[i])) for i in holdout])
    save_csv(root / "sample.csv", ["id", "prediction"], [(str(i), 0) for i in reversed(holdout)])
    protocol = {"schema_version": 1, "task_id": "diabetes-raw-3fold-v1", "task": "regression",
                "metric": "rmse", "score_kind": "proxy", "features": features, "split": {"kind": "iid"},
                "expected_oof_ids": list(map(str, development)), "folds": []}
    for index, (fit, valid) in enumerate(KFold(3, shuffle=True, random_state=1729).split(development)):
        protocol["folds"].append({"id": str(index), "seed": 1729 + index,
                                  "train_ids": list(map(str, development[fit])),
                                  "validation_ids": list(map(str, development[valid]))})
    write_json(root / "folds.json", protocol)
    (root / "baseline.py").write_text(
        "from sklearn.pipeline import make_pipeline\nfrom sklearn.preprocessing import StandardScaler\n"
        "from sklearn.linear_model import Ridge\ndef build_model(seed, task):\n"
        "    return make_pipeline(StandardScaler(), Ridge(alpha=1))\n")
    (root / "challenger.py").write_text(
        "from sklearn.ensemble import ExtraTreesRegressor\ndef build_model(seed, task):\n"
        "    return ExtraTreesRegressor(n_estimators=80, min_samples_leaf=3, random_state=seed, n_jobs=1)\n")
    results = {}
    for name in ["baseline", "challenger"]:
        train(root / "training.csv", root / "folds.json", root / (name + ".py"), root / name)
        results[name] = load_result(root / name / "evaluation/result.json")
        truth_rows = csv_rows(root / name / "truth.csv", ["id", "target"])[1]
        predicted_rows = csv_rows(root / name / "oof.csv", ["id", "prediction"])[1]
        reference = root_mean_squared_error([float(row["target"]) for row in truth_rows.values()],
                                           [float(predicted_rows[key]["prediction"]) for key in truth_rows])
        if not np.isclose(reference, results[name]["score"]["value"], rtol=1e-12, atol=1e-12):
            raise RuntimeError("Independent sklearn OOF metric differs")
    comparison = compare(results["baseline"], results["challenger"], 0.0)
    write_json(root / "comparison.json", comparison)
    selected = min(results, key=lambda name: results[name]["score"]["value"])
    freeze(root / selected, root / "frozen",
           "Choose the lowest development pooled OOF RMSE (baseline on ties); report its independent confirmation "
           "without changing selection. This is a workflow exercise, not a deploy/contest acceptance gate.")
    confirmation = deliver(root / "frozen", root / "confirmation-features.csv", root / "confirmation",
                           truth=root / "confirmation-truth.csv")
    delivery = deliver(root / "frozen", root / "confirmation-features.csv", root / "final",
                       sample_submission=root / "sample.csv")
    summary = {"scope": "scripted local integration; no autonomous effect claim", "selected": selected,
               "development_rmse": {name: result["score"]["value"] for name, result in results.items()},
               "confirmation_rmse": confirmation["score"]["value"], "final_rows": delivery["row_count"],
               "frozen_seal": delivery["frozen_seal"], "independent_oof_metric_check": "passed"}
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
