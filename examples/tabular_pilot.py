#!/usr/bin/env python3
"""Bounded, scripted integration pilot on two bundled sklearn datasets.

This is a workflow check, not an autonomous-agent benchmark or a contest runner.
All datasets, fitted models, predictions, and receipts stay in --output-dir.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.datasets import load_breast_cancer, load_diabetes
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import log_loss, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits


SEED = 1729
SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "skills/competition-optimize/scripts"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save_json(path: pathlib.Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def event(root: pathlib.Path, **fields: object) -> None:
    with (root / "trials.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), **fields},
                                allow_nan=False) + "\n")


def save_csv(path: pathlib.Path, header: list[str], rows: object) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def tool(root: pathlib.Path, name: str, arguments: list[object]) -> None:
    command = [sys.executable, "-X", "utf8", str(SCRIPTS / name), *map(str, arguments)]
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=120)
    event(root, event="tool", command=command, returncode=result.returncode,
          seconds=time.perf_counter() - started)
    if result.returncode:
        raise RuntimeError(f"{name} failed: {result.stderr or result.stdout}")


def evaluate(root: pathlib.Path, name: str, predictions: pathlib.Path, stage: str, metric: str) -> pathlib.Path:
    result_dir = root / "evaluations" / f"{stage}-{name}"
    tool(root, "evaluate_predictions.py", [
        "--truth", root / f"{stage}-truth.csv", "--predictions", predictions,
        "--metric", metric, "--stage", stage, "--split-id", f"{root.name}-seed-{SEED}-{stage}",
        "--score-kind", "proxy", "--output-dir", result_dir,
    ])
    with (root / f"{stage}-truth.csv").open(encoding="utf-8", newline="") as stream:
        truth = {row["id"]: float(row["target"]) for row in csv.DictReader(stream)}
    with (result_dir / "predictions.csv").open(encoding="utf-8", newline="") as stream:
        values = {row["id"]: float(row["prediction"]) for row in csv.DictReader(stream)}
    ids = sorted(truth)
    labels, predictions = [truth[key] for key in ids], [values[key] for key in ids]
    reference = (log_loss(labels, np.clip(predictions, 1e-15, 1 - 1e-15), labels=[0, 1])
                 if metric == "binary_log_loss" else root_mean_squared_error(labels, predictions))
    actual = read_json(result_dir / "result.json")["score"]["value"]
    if not math.isclose(actual, reference, rel_tol=1e-12, abs_tol=1e-12):
        raise RuntimeError(f"Independent sklearn metric mismatch: {actual} vs {reference}")
    save_json(result_dir / "sklearn-crosscheck.json", {"metric": metric, "adapter": actual,
                                                     "sklearn": float(reference), "passed": True})
    return result_dir / "result.json"


def compare(root: pathlib.Path, baseline: pathlib.Path, candidate: pathlib.Path, name: str) -> dict:
    output = root / "comparisons" / f"{name}.json"
    tool(root, "compare_prediction_results.py", [
        "--baseline", baseline, "--candidate", candidate, "--output", output,
    ])
    return read_json(output)


def models(binary: bool) -> dict:
    baseline = (make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=2000, tol=1e-6))
                if binary else make_pipeline(StandardScaler(), Ridge(alpha=1)))
    histogram = HistGradientBoostingClassifier if binary else HistGradientBoostingRegressor
    extra_trees = ExtraTreesClassifier if binary else ExtraTreesRegressor
    return {
        "baseline": baseline,
        "histogram": histogram(max_iter=120, learning_rate=0.05, max_leaf_nodes=7,
                               min_samples_leaf=15, l2_regularization=1,
                               early_stopping=False, random_state=SEED),
        "extra-trees": extra_trees(n_estimators=200, min_samples_leaf=3,
                                  max_features=1.0, n_jobs=1, random_state=SEED),
    }


def predict(model: object, features: np.ndarray, binary: bool) -> np.ndarray:
    if binary:
        positive_column = list(model.classes_).index(1)
        return model.predict_proba(features)[:, positive_column]
    return model.predict(features)


def model_config(model: object) -> dict:
    if hasattr(model, "steps"):
        return {name: {"class": type(step).__name__, "parameters": step.get_params(deep=False)}
                for name, step in model.steps}
    return {"class": type(model).__name__, "parameters": model.get_params(deep=False)}


def run_task(output: pathlib.Path, name: str, binary: bool) -> dict:
    started = time.perf_counter()
    root = output / name
    root.mkdir()
    for directory in ["candidates", "evaluations", "comparisons"]:
        (root / directory).mkdir()
    data = load_breast_cancer() if binary else load_diabetes(scaled=False)
    # Diabetes's default scaling uses all rows; raw features avoid that fit.
    features = np.asarray(data.data, dtype="<f8")
    target = np.asarray(data.target, dtype="<f8")
    indexes = np.arange(len(target))
    remaining, confirmation = train_test_split(indexes, test_size=0.2, random_state=SEED,
                                               stratify=target if binary else None)
    train, development = train_test_split(remaining, test_size=0.25, random_state=SEED + 1,
                                         stratify=target[remaining] if binary else None)
    if len(np.unique(features, axis=0)) != len(target):
        raise RuntimeError("Duplicate rows require another split policy")
    sample_id = lambda index: f"{int(index):04d}"
    split_ids = {stage: [sample_id(index) for index in sorted(values)] for stage, values in
                 [("train", train), ("development", development), ("confirmation", confirmation)]}
    save_json(root / "splits.json", split_ids)
    np.savez(root / "data.npz", features=features, target=target)
    save_csv(root / "development-truth.csv", ["id", "target"],
             [(sample_id(index), repr(float(target[index]))) for index in development])
    dataset_hash = digest(json.dumps(list(data.feature_names)).encode() + features.tobytes() + target.tobytes())
    contract = {
        "purpose": "scripted integration pilot; not autonomous-agent effectiveness",
        "dataset": name, "dataset_hash": dataset_hash,
        "feature_count": features.shape[1], "sample_count": len(target),
        "metric": "binary_log_loss" if binary else "rmse", "direction": "minimize", "score_kind": "proxy",
        "positive_class": "benign (sklearn label 1)" if binary else None,
        "split": {"seed": SEED, "development_seed": SEED + 1,
                  "method": "stratified random rows" if binary else "random rows",
                  "counts": {stage: len(ids) for stage, ids in split_ids.items()},
                  "split_hash": digest((root / "splits.json").read_bytes())},
        "budget": {"baseline_fits": 1, "challenger_trials": 3, "parallel_evaluations": False},
        "fitting": "Training rows only for all learned preprocessing and models; no confirmation refit",
        "confirmation": {
            "shortlist": "baseline plus lowest development-metric challenger; fixed before confirmation",
            "decision": "Accept challenger only if it improves both development and confirmation metrics",
            "sampling_unit": "row; assumes independent exchangeable patients, not a clinical validation claim",
            "bootstrap_samples": 1000, "seed": 0, "confidence_level": 0.95, "minimum_improvement": 0,
            "uncertainty_use": "Descriptive evidence; not an automatic statistical promotion gate",
        },
        "third_trial": "Equal blend of baseline and best tree if both win some development cases; no weight sweep",
    }
    save_json(root / "task-contract.json", contract)
    save_csv(root / "row-metadata.csv", ["id"], [(sample_id(index),) for index in indexes])
    tool(root, "audit_data_split.py", [
        "--splits", root / "splits.json", "--metadata", root / "row-metadata.csv",
        "--output", root / "split-audit.json",
    ])
    with (root / "research.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("# Fixed pilot hypotheses\n\n"
                     "Dataset provenance: sklearn's bundled loader and saved dataset-description.txt.\n"
                     "Regularized linear reference; shallow boosting and randomized trees test nonlinear signal.\n"
                     "A single equal blend tests complementary development errors; no weight sweep.\n"
                     "Reject by the full declared metric, then apply the sealed confirmation decision rule.\n"
                     "These hypotheses are scripted and do not establish autonomous skill effectiveness.\n")
    with (root / "dataset-description.txt").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(data.DESCR)
    metric = contract["metric"]
    development_results, scores, fit_receipts = {}, {}, {}
    estimators = models(binary)
    for model_name, model in estimators.items():
        candidate = root / "candidates" / model_name
        candidate.mkdir()
        hypothesis = ("Credible regularized linear baseline" if model_name == "baseline" else
                      "Shallow boosted trees may capture nonlinear interactions" if model_name == "histogram" else
                      "Averaged randomized trees may add nonlinear signal with different errors")
        event(root, event="planned", trial=model_name, parents=[] if model_name == "baseline" else ["baseline"],
              hypothesis=hypothesis, rejection_test="Matched full development metric and paired case errors",
              configuration=model_config(model), cost="One fit on training rows; one development evaluation")
        save_json(candidate / "configuration.json", model_config(model))
        fit_started = time.perf_counter()
        model.fit(features[train], target[train])
        fit_seconds = time.perf_counter() - fit_started
        if hasattr(model, "steps"):
            assert int(model.steps[0][1].n_samples_seen_) == len(train)
        joblib.dump(model, candidate / "model.joblib")
        dev_started = time.perf_counter()
        values = predict(model, features[development], binary)
        prediction_seconds = time.perf_counter() - dev_started
        save_csv(candidate / "development.csv", ["id", "prediction"],
                 [(sample_id(index), repr(float(value))) for index, value in zip(development, values)])
        fit_receipts[model_name] = {
            "model_hash": digest((candidate / "model.joblib").read_bytes()),
            "configuration_hash": digest((candidate / "configuration.json").read_bytes()),
            "train_id_hash": digest(json.dumps(split_ids["train"]).encode()),
            "split_audit_hash": digest((root / "split-audit.json").read_bytes()),
            "fit_seconds": fit_seconds, "development_prediction_seconds": prediction_seconds,
            "model_bytes": (candidate / "model.joblib").stat().st_size,
        }
        save_json(candidate / "fit.json", fit_receipts[model_name])
        result = evaluate(root, model_name, candidate / "development.csv", "development", metric)
        development_results[model_name] = result
        scores[model_name] = read_json(result)["score"]["value"]
        if model_name != "baseline":
            compare(root, development_results["baseline"], result, f"development-{model_name}")
        event(root, event="completed", trial=model_name, score=scores[model_name],
              result=str(result), fit=fit_receipts[model_name],
              remaining_challenger_trials=3 - (len(scores) - 1))

    tree_name = min(["histogram", "extra-trees"], key=scores.get)
    diagnostics = root / "comparisons" / "development-errors"
    tool(root, "analyze_prediction_errors.py", [
        "--baseline", development_results["baseline"], "--candidate", development_results[tree_name],
        "--truth", root / "development-truth.csv", "--output-dir", diagnostics,
    ])
    counts = read_json(diagnostics / "report.json")["case_preference_counts"]
    blend = root / "candidates" / "blend"
    if counts.get("baseline", 0) and counts.get("candidate", 0):
        event(root, event="planned", trial="blend", parents=["baseline", tree_name],
              hypothesis="Complementary held-out errors may improve an equal convex blend",
              evidence=counts, rejection_test="Full development metric must improve on the best individual",
              cost="One cached-prediction recipe; no weight search")
        tool(root, "blend_predictions.py", [
            "create", "--member", "baseline", development_results["baseline"],
            "--member", tree_name, development_results[tree_name],
            "--weights", 1, 1, "--output-dir", blend,
        ])
        development_results["blend"] = evaluate(root, "blend", blend / "predictions.csv", "development", metric)
        scores["blend"] = read_json(development_results["blend"])["score"]["value"]
        compare(root, development_results["baseline"], development_results["blend"], "development-blend")
        individual = min(estimators, key=scores.get)
        compare(root, development_results[individual], development_results["blend"], "development-blend-vs-best")
        event(root, event="completed", trial="blend", score=scores["blend"],
              result=str(development_results["blend"]), remaining_challenger_trials=0)

    challenger = min((name for name in scores if name != "baseline"), key=scores.get)
    shortlist = {"baseline": "baseline", "challenger": challenger, "development_scores": scores,
                 "development_eligible": scores[challenger] < scores["baseline"],
                 "decision_rule": contract["confirmation"]["decision"],
                 "recipe_hash": read_json(blend / "recipe.json")["recipe_hash"] if challenger == "blend" else None,
                 "model_hashes": {name: receipt["model_hash"] for name, receipt in fit_receipts.items()}}
    save_json(root / "shortlist.json", shortlist)
    event(root, event="shortlist_frozen", shortlist_hash=digest((root / "shortlist.json").read_bytes()))
    # Confirmation labels/predictions are used for scoring only after this point.
    save_csv(root / "confirmation-truth.csv", ["id", "target"],
             [(sample_id(index), repr(float(target[index]))) for index in confirmation])
    members = ["baseline", tree_name] if challenger == "blend" else sorted({"baseline", challenger})
    confirmation_receipts = {}
    for member in members:
        candidate = root / "candidates" / member
        assert digest((candidate / "model.joblib").read_bytes()) == shortlist["model_hashes"][member]
        loading_started = time.perf_counter()
        frozen_model = joblib.load(candidate / "model.joblib")
        loading_seconds = time.perf_counter() - loading_started
        prediction_started = time.perf_counter()
        values = predict(frozen_model, features[confirmation], binary)
        confirmation_receipts[member] = {"prediction_seconds": time.perf_counter() - prediction_started,
                                         "loading_seconds": loading_seconds,
                                         "model_hash": shortlist["model_hashes"][member]}
        save_csv(candidate / "confirmation.csv", ["id", "prediction"],
                 [(sample_id(index), repr(float(value))) for index, value in zip(confirmation, values)])
    baseline_result = evaluate(root, "baseline", root / "candidates/baseline/confirmation.csv", "confirmation", metric)
    challenger_predictions = root / "candidates" / challenger / "confirmation.csv"
    if challenger == "blend":
        tool(root, "blend_predictions.py", [
            "apply", "--recipe", blend / "recipe.json",
            "--member", "baseline", root / "candidates/baseline/confirmation.csv",
            "--member", tree_name, root / "candidates" / tree_name / "confirmation.csv",
            "--output-dir", root / "candidates/confirmation-blend",
        ])
        challenger_predictions = root / "candidates/confirmation-blend/predictions.csv"
    challenger_result = evaluate(root, challenger, challenger_predictions, "confirmation", metric)
    comparison = compare(root, baseline_result, challenger_result, "confirmation")
    uncertainty = root / "comparisons" / "confirmation-uncertainty"
    tool(root, "compare_prediction_uncertainty.py", [
        "--baseline", baseline_result, "--candidate", challenger_result,
        "--truth", root / "confirmation-truth.csv", "--resampling-unit", "row",
        "--bootstrap-samples", 1000, "--seed", 0, "--confidence-level", 0.95,
        "--minimum-improvement", 0, "--output-dir", uncertainty,
    ])
    accepted = shortlist["development_eligible"] and comparison["metric_preference"] == "candidate"
    summary = {
        "dataset": name, "dataset_hash": dataset_hash, "metric": metric, "score_kind": "proxy",
        "split_counts": contract["split"]["counts"], "development_scores": scores,
        "frozen_challenger": challenger, "confirmation": comparison,
        "uncertainty": read_json(uncertainty / "report.json")["uncertainty"],
        "selected": challenger if accepted else "baseline", "accepted": accepted,
        "shortlist_hash": digest((root / "shortlist.json").read_bytes()),
        "fits": fit_receipts, "confirmation_predictions": confirmation_receipts,
        "elapsed_seconds": time.perf_counter() - started,
        "limitations": "Two small random-row tasks; fixed scripted candidates and one training seed. "
                       "Not a causal skill evaluation, clinical validation, or evidence of leaderboard gain.",
    }
    save_json(root / "summary.json", summary)
    event(root, event="delivered", selected=summary["selected"], accepted=accepted,
          summary=str(root / "summary.json"))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True, help="New directory outside the repository")
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    repository = pathlib.Path(__file__).resolve().parents[1]
    if output == repository or repository in output.parents:
        parser.error("Keep pilot datasets and artifacts outside the repository")
    output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, output / "pilot-source.py")
    save_json(output / "environment.json", {
        "python": platform.python_version(), "system": platform.platform(),
        "numpy": np.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__,
        "joblib": joblib.__version__, "thread_limit": 1, "seed": SEED,
        "source_hash": digest((output / "pilot-source.py").read_bytes()),
        "tool_hashes": {path.name: digest(path.read_bytes()) for path in sorted(SCRIPTS.glob("*prediction*.py"))},
    })
    with threadpool_limits(limits=1):
        summaries = [run_task(output, "diabetes", False), run_task(output, "breast-cancer", True)]
    save_json(output / "summary.json", summaries)
    print(json.dumps([{"dataset": row["dataset"], "development": row["development_scores"],
                       "challenger": row["frozen_challenger"], "confirmation": {
                           "baseline": row["confirmation"]["baseline"]["score"],
                           "challenger": row["confirmation"]["candidate"]["score"]},
                       "selected": row["selected"], "seconds": row["elapsed_seconds"]}
                      for row in summaries], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
