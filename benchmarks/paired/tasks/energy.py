"""Fixed causal energy-forecast task shared by both paired workflow versions.

The public task bundle snapshots the complete common tabular evaluator. Candidate
code is trusted local Python; the runner must isolate private/cache directories
and keep this evaluator read-only. This module is not a code sandbox.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

TASK_ID = "uci-appliances-next10m-v1"
PAGE_URL = "https://archive.ics.uci.edu/dataset/374/appliances+energy+prediction"
API_URL = "https://archive.ics.uci.edu/api/dataset?id=374"
DATA_URL = "https://archive.ics.uci.edu/static/public/374/appliances+energy+prediction.zip"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode"
ZIP_SHA256 = "2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a"
CSV_SHA256 = "2820bf712ad0275cb18b85a05250926100d8e65ebb9f4d2d016ca91ea152a25d"
CORE_FILES = ("tabular_training.py", "audit_data_split.py", "evaluate_predictions.py", "prediction_core.py")
SENSORS = [name for i in range(1, 10) for name in (f"T{i}", f"RH_{i}")]
FEATURES = ([f"{name}_lag1" for name in SENSORS] +
            ["appliances_lag1", "appliances_lag6", "appliances_lag144", "appliances_mean6", "appliances_mean144",
             "lights_lag1", "lights_lag6", "hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "weekend"])
FOLDS = (("2016-02-15", "2016-03-01"), ("2016-03-01", "2016-03-15"), ("2016-03-15", "2016-04-15"))
PUBLIC_END = datetime(2016, 4, 15)
PRIVATE_START = datetime(2016, 5, 1)
BASELINE = '''from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

def build_model(seed, task):
    if task != "regression":
        raise ValueError("This candidate supports regression only")
    return make_pipeline(StandardScaler(), Ridge(alpha=10.0))
'''


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def fetch_sources(cache: Path) -> dict:
    """Fetch official UCI bytes, pin data revisions, and preserve license evidence."""
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    sources = []
    for name, url in (("uci-page.html", PAGE_URL), ("uci-api.json", API_URL), ("uci-original.zip", DATA_URL)):
        path = cache / name
        if not path.exists():
            raw = urllib.request.urlopen(url, timeout=45).read()
            path.write_bytes(raw)
        raw = path.read_bytes()
        sources.append({"file": name, "url": url, "sha256": digest(raw), "bytes": len(raw)})
    if digest((cache / "uci-original.zip").read_bytes()) != ZIP_SHA256:
        raise ValueError("Official dataset ZIP changed; review the revision before using it")
    page = (cache / "uci-page.html").read_text()
    metadata = json.loads((cache / "uci-api.json").read_text())["data"]
    if LICENSE_URL not in page or "CC BY 4.0" not in page or metadata["uci_id"] != 374:
        raise ValueError("Official dataset identity/license evidence is missing")
    with zipfile.ZipFile(cache / "uci-original.zip") as package:
        raw = package.read("energydata_complete.csv")
    if digest(raw) != CSV_SHA256:
        raise ValueError("Official CSV changed; review the revision before using it")
    csv_path = cache / "energydata_complete.csv"
    if csv_path.exists() and csv_path.read_bytes() != raw:
        raise ValueError("Cached CSV differs from the official ZIP")
    if not csv_path.exists():
        csv_path.write_bytes(raw)
    return {"dataset": "UCI Appliances Energy Prediction", "uci_id": 374, "doi": "10.24432/C5VC8G",
            "attribution": "Candanedo, Luis. Appliances Energy Prediction [Dataset]. UCI Machine Learning Repository (2017).",
            "license": "CC BY 4.0", "license_url": LICENSE_URL, "sources": sources,
            "csv_sha256": CSV_SHA256, "csv_bytes": len(raw), "cache": str(cache)}


def _seconds(value: datetime) -> int:
    # Dataset timestamps have no timezone. This is a naive chronology coordinate,
    # not a claim that the recorded Belgian timestamps are UTC.
    return int((value - datetime(2016, 1, 1)).total_seconds())


def _examples(raw: bytes) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    dates = [datetime.fromisoformat(row["date"].strip()) for row in rows]
    if len(rows) != 19735 or any(b - a != timedelta(minutes=10) for a, b in zip(dates, dates[1:])):
        raise ValueError("Expected the pinned complete, ordered 10-minute dataset")
    appliances = [float(row["Appliances"]) for row in rows]
    examples = []
    for i in range(144, len(rows)):
        now = dates[i]
        previous = rows[i - 1]
        hour = now.hour + now.minute / 60
        values = [float(previous[name]) for name in SENSORS] + [
            appliances[i - 1], appliances[i - 6], appliances[i - 144],
            math.fsum(appliances[i - 6:i]) / 6, math.fsum(appliances[i - 144:i]) / 144,
            float(previous["lights"]), float(rows[i - 6]["lights"]),
            math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24),
            math.sin(2 * math.pi * now.weekday() / 7), math.cos(2 * math.pi * now.weekday() / 7),
            int(now.weekday() >= 5)]
        if not all(math.isfinite(value) for value in [*values, appliances[i]]):
            raise ValueError("Nonfinite source data")
        examples.append({"id": now.isoformat(), "prediction_time": _seconds(now),
                         "label_available_time": _seconds(now) + 600,
                         "target": appliances[i], **dict(zip(FEATURES, values))})
    return examples


def _csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _seal(root: Path, fields: dict) -> dict:
    manifest = {"schema_version": 1, **fields, "files": {
        str(path.relative_to(root)): digest(path.read_bytes()) for path in sorted(root.rglob("*")) if path.is_file()}}
    manifest["seal"] = digest(canonical(manifest))
    write_json(root / "manifest.json", manifest)
    return manifest


def _verify(root: Path, kind: str) -> dict:
    root = root.resolve()
    value = json.loads((root / "manifest.json").read_text())
    if value.get("kind") != kind or value.get("seal") != digest(canonical({k: v for k, v in value.items() if k != "seal"})):
        raise ValueError("Invalid task manifest")
    for name, expected in value["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes()) != expected:
            raise ValueError("Changed task input: " + name)
    return value


def prepare(cache: Path, output: Path) -> dict:
    sources = fetch_sources(cache)
    examples = _examples((cache / "energydata_complete.csv").read_bytes())
    development = [row for row in examples if row["prediction_time"] < _seconds(PUBLIC_END)]
    confirmation = [row for row in examples if row["prediction_time"] >= _seconds(PRIVATE_START)]
    folds = []
    for index, (left, right) in enumerate(FOLDS):
        start, end = _seconds(datetime.fromisoformat(left)), _seconds(datetime.fromisoformat(right))
        folds.append({"id": f"forward-{index}", "seed": 0,
                      "train_ids": [row["id"] for row in development if row["label_available_time"] <= start - 86400],
                      "validation_ids": [row["id"] for row in development if start <= row["prediction_time"] < end]})
    protocol = {"schema_version": 1, "task_id": TASK_ID, "task": "regression", "metric": "rmse", "score_kind": "proxy",
                "features": FEATURES, "split": {"kind": "time", "time_column": "prediction_time", "time_format": "number",
                "available_time_column": "label_available_time", "minimum_time_gap": 86400},
                "folds": folds, "expected_oof_ids": [key for fold in folds for key in fold["validation_ids"]]}
    output = output.resolve()
    output.mkdir()
    public, private = output / "public", output / "private"
    public.mkdir(); private.mkdir()
    _csv(public / "training.csv", ["id", "prediction_time", "label_available_time", "target", *FEATURES], development)
    _csv(private / "features.csv", ["id", "prediction_time", *FEATURES], confirmation)
    _csv(private / "truth.csv", ["id", "target"], confirmation)
    write_json(public / "protocol.json", protocol)
    write_json(public / "sources.json", {key: value for key, value in sources.items() if key != "cache"})
    (public / "candidate.py").write_text(BASELINE)
    (public / "task.py").write_bytes(Path(__file__).read_bytes())
    core_source = Path(__file__).resolve().parents[3] / "skills/competition-optimize/scripts"
    core = public / "adapter_core"
    core.mkdir()
    for name in CORE_FILES:
        (core / name).write_bytes((core_source / name).read_bytes())
    (public / "requirements.txt").write_bytes((core_source / "requirements-tabular.txt").read_bytes())
    (public / "TASK.md").write_text(_task_text(), encoding="utf-8")
    metadata = {"task_id": TASK_ID, "public_rows": len(development), "oof_rows": len(protocol["expected_oof_ids"]),
                "confirmation_rows": len(confirmation), "folds": [{"id": f["id"], "train": len(f["train_ids"]),
                "validation": len(f["validation_ids"])} for f in folds], "feature_count": len(FEATURES)}
    public_manifest = _seal(public, {"kind": "energy_public", "task_id": TASK_ID, "metadata": metadata})
    _seal(private, {"kind": "energy_private", "task_id": TASK_ID, "public_seal": public_manifest["seal"]})
    return {**metadata, "public": str(public), "private": str(private), "public_seal": public_manifest["seal"],
            "baseline_candidate": str(public / "candidate.py"), "sources": sources}


def _task_text() -> str:
    return f'''# Next-interval appliance energy forecast

Predict Appliances energy (Wh) for the next logged 10-minute interval, using only
completed earlier records. Minimize pooled development OOF RMSE. This is a derived
temporal benchmark, not the original paper's reported random-split experiment.

Public data end before 2016-04-15. Three expanding forward folds validate
2016-02-15–03-01, 03-01–03-15, and 03-15–04-15. Each fold has a 24-hour gap
after the latest training label becomes available. The final period starts
2016-05-01; its features and labels are private and must never guide selection.

Features contain prior-row home sensors/lights, appliance lags 1/6/144,
past-only rolling means 6/144, and known calendar variables. No same-row sensor,
light or appliance values, random rv columns, or interpolated airport weather
are inputs. For this benchmark, the previous logged interval is available at
prediction_time and the target becomes available 600 seconds later. This
availability convention is an explicit conservative task assumption; UCI does
not document production sensor/label release latency. Times are naive dataset
chronology coordinates, without an invented UTC offset. At confirmation,
lagged observed appliance values are legitimate rolling one-step history;
models stay fixed and are never refitted on confirmation labels.

Copy the provided candidate.py into your writable work directory, then edit
that single file defining build_model(seed, task), returning a sklearn
estimator/Pipeline. task is "regression"; X is a numeric ndarray whose column
order is protocol.json features. Put learned preprocessing inside the estimator.
The provided Ridge baseline is valid, intentionally simple, and actually fitted.
The frozen delivery rule is the equal-weight mean of the three fitted fold
models. Confirmation never trains a final full-data model or changes this rule.

Run: python task.py evaluate --public PUBLIC --candidate candidate.py --output NEW_RUN --seed 11

Each run keeps candidate.py, stable recipe.json, protocol/data snapshots,
fold models, fit.json, oof.csv, result.json and frozen/. Archive using the
returned archive.source (OOF CSV), archive.configuration (recipe.json), and
archive.result. Candidate source is inside recipe.json and candidate.py.

The adapter and training protocol are immutable shared infrastructure for both
workflow versions. All four common implementation files are copied into
adapter_core; execution does not import the live repository. These paired runs
compare the overall workflow, not a separate ablation of new ML tooling.
Only the public bundle belongs in the agent workspace; private data, raw UCI
cache and controller files must remain outside it. Do not retrieve the original
full dataset, access hidden data, alter the evaluator, or use previous final
scores for tuning. Python candidates are trusted code; directory separation
alone is not a security sandbox. The controller must enforce the evaluation
access policy and record any violation.

Source: Candanedo, Luis (2017), UCI Appliances Energy Prediction, DOI
10.24432/C5VC8G. License: CC BY 4.0 ({LICENSE_URL}).
Official data: {DATA_URL}
Official description: {PAGE_URL}
sources.json records official source and CSV hashes. Raw source data are not
included in this public bundle. All forecasts/features and splits above are
benchmark transformations, not claims made by the dataset creators.
'''


def _core(public: Path):
    sys.path.insert(0, str(public / "adapter_core"))
    import tabular_training
    if Path(tabular_training.__file__).resolve().parent != (public / "adapter_core").resolve():
        raise ValueError("Task must execute its snapshotted common adapter")
    return tabular_training


def _enrich_result(public: Path, source: Path, output: Path, stage: str, seed: int, elapsed: float) -> dict:
    manifest = _verify(public, "energy_public")
    value = json.loads(source.read_text())
    value.update(adapter="paired_energy", stage=stage, elapsed_seconds=elapsed,
                 evaluator_hash=digest(canonical({name: manifest["files"][name] for name in
                    ["task.py", *["adapter_core/" + name for name in CORE_FILES]]})),
                 workload_hash=digest(canonical({"task_id": TASK_ID, "public_seal": manifest["seal"], "stage": stage})))
    value["evaluation"].update(seeds=[seed], repetitions=1)
    value["training_provenance"] = {"task_id": TASK_ID, "public_seal": manifest["seal"],
                                    "kind": "actual_fold_training" if stage == "development" else "frozen_model_inference"}
    write_json(output / "result.json", value)
    return value


def _evaluate(public: Path, candidate: Path, out: Path, seed: int) -> dict:
    import time
    _verify(public, "energy_public")
    core = _core(public)
    spec = json.loads((public / "protocol.json").read_text())
    for fold in spec["folds"]:
        fold["seed"] = seed
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(dir=out.parent) as temporary:
        protocol = Path(temporary) / "protocol.json"
        write_json(protocol, spec)
        core.train(public / "training.csv", protocol, candidate, out)
    core.freeze(out, out / "frozen", "Equal-weight arithmetic mean of the three already-fitted forward-fold models")
    value = _enrich_result(public, out / "evaluation/result.json", out, "development", seed, time.perf_counter() - started)
    return {"status": "success", "task_id": TASK_ID, "score": value["score"], "result": str(out / "result.json"),
            "frozen_run": str(out / "frozen"), "archive": {"source": str(out / "oof.csv"),
            "configuration": str(out / "recipe.json"), "result": str(out / "result.json")}}


def _confirm(public: Path, private: Path, frozen_run: Path, out: Path, seed: int) -> dict:
    import time
    public_manifest = _verify(public, "energy_public")
    private_manifest = _verify(private, "energy_private")
    if private_manifest["public_seal"] != public_manifest["seal"]:
        raise ValueError("Private data do not belong to this public protocol")
    core = _core(public)
    frozen = frozen_run / "frozen" if (frozen_run / "frozen").is_dir() else frozen_run
    core.verified_manifest(frozen, "tabular_frozen")
    spec = json.loads((frozen / "protocol.json").read_text())
    expected = json.loads((public / "protocol.json").read_text())
    for fold in expected["folds"]:
        fold["seed"] = seed
    if spec != expected or digest((frozen / "training.csv").read_bytes()) != public_manifest["files"]["training.csv"]:
        raise ValueError("Frozen training protocol/data/seed differ from this task")
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    delivered = core.deliver(frozen, private / "features.csv", out, truth=private / "truth.csv")
    value = _enrich_result(public, out / "evaluation/result.json", out, "confirmation", seed, time.perf_counter() - started)
    return {**delivered, "task_id": TASK_ID, "score": value["score"], "result": str(out / "result.json"),
            "archive": {"source": str(out / "predictions.csv"), "configuration": str(frozen / "recipe.json"),
                        "result": str(out / "result.json")}}


def _worker(operation: str, public: Path, out: Path, seed: int, **paths) -> dict:
    public, out = public.resolve(), out.resolve()
    _verify(public, "energy_public")
    command = [sys.executable, "-B", str(public / "task.py"), "_" + operation,
               "--public", str(public), "--output", str(out), "--seed", str(seed)]
    for name, value in paths.items():
        command.extend(["--" + name.replace("_", "-"), str(value.resolve())])
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise ValueError(completed.stderr.strip() or completed.stdout.strip() or "Energy task execution failed")
    # Candidate fit methods may print diagnostics before the final JSON receipt.
    return json.loads(completed.stdout.splitlines()[-1])


def evaluate(public: Path, candidate: Path, out: Path, seed: int) -> dict:
    return _worker("evaluate", public, out, seed, candidate=candidate)


def confirm(public: Path, private: Path, frozen_run: Path, out: Path, seed: int) -> dict:
    return _worker("confirm", public, out, seed, private=private, frozen_run=frozen_run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("evaluate", "confirm", "_evaluate", "_confirm"))
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--private", type=Path)
    parser.add_argument("--frozen-run", type=Path)
    args = parser.parse_args()
    try:
        if args.operation.endswith("evaluate"):
            if args.candidate is None:
                raise ValueError("evaluate requires --candidate")
            action = _evaluate if args.operation.startswith("_") else evaluate
            result = action(args.public.resolve(), args.candidate.resolve(), args.output.resolve(), args.seed)
        else:
            if args.private is None or args.frozen_run is None:
                raise ValueError("confirm requires --private and --frozen-run")
            action = _confirm if args.operation.startswith("_") else confirm
            result = action(args.public.resolve(), args.private.resolve(), args.frozen_run.resolve(), args.output.resolve(), args.seed)
        print(json.dumps(result, allow_nan=False))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error": {"type": type(error).__name__, "message": str(error)}}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
