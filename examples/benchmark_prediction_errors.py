#!/usr/bin/env python3
"""Measure full and summary diagnostics, optionally against a trusted old analyzer."""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import pathlib
import platform
import statistics
import sys
import time
import tracemalloc


REPOSITORY = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY / "skills/competition-optimize/scripts"
sys.path.insert(0, str(SCRIPTS))
import analyze_prediction_errors as analyzer
import evaluate_predictions as evaluator


SEMANTIC_KEYS = ["aggregate_comparison", "case_count", "case_preference_counts", "squared_error_scale",
                 "per_case_error_kind", "error_share_kind", "largest_candidate_errors", "largest_regressions", "slices"]


def save(path: pathlib.Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, allow_nan=False, indent=2) + "\n")


def measure(module: object, args: argparse.Namespace, output: pathlib.Path, memory: bool = False) -> tuple[dict, dict]:
    output.mkdir()
    args.output_dir = output
    gc.collect()
    if memory:
        tracemalloc.start()
    started = time.perf_counter()
    report = module.analyze(args, output)
    save(output / "report.json", report)
    seconds = time.perf_counter() - started
    peak = tracemalloc.get_traced_memory()[1] if memory else None
    if memory:
        tracemalloc.stop()
    return report, {"seconds": seconds, "python_peak_bytes": peak,
                    "artifact_bytes": sum(path.stat().st_size for path in output.iterdir())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path, help="new directory outside repository")
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--metric", choices=list(evaluator.METRIC_DIRECTIONS), default="rmse")
    parser.add_argument("--reference", type=pathlib.Path,
                        help="optional trusted old analyzer, with its hash dependencies beside it; executes Python")
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    if output == REPOSITORY or REPOSITORY in output.parents or args.rows < 2:
        parser.error("Need at least two rows and an output directory outside the repository")
    full_module = analyzer
    if args.reference is not None:
        reference = args.reference.expanduser().resolve(strict=True)
        spec = importlib.util.spec_from_file_location("reference_error_analysis", reference)
        full_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(full_module)
    output.mkdir(exist_ok=False)
    setup_started = time.perf_counter()
    truth, before, after, slices = [output / name for name in ["truth.csv", "before.csv", "after.csv", "slices.csv"]]
    binary = args.metric in {"binary_log_loss", "roc_auc"}
    targets = [float(i % 2) if binary else i % 17 / 3 for i in range(args.rows)]
    before_values = [(.55 if value else .45) + (i % 5 - 2) / 10 if binary else value + (i % 5 - 2) / 7
                     for i, value in enumerate(targets)]
    after_values = [(.8 if value else .2) + (i % 7 - 3) / 50 if binary else value + (i % 7 - 3) / 11
                    for i, value in enumerate(targets)]
    for path, column, values in [(truth, "target", targets), (before, "prediction", before_values),
                                 (after, "prediction", after_values)]:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"id,{column}\n")
            for i, value in enumerate(values):
                stream.write(f"{i:06d},{value!r}\n")
    with slices.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("id,regime\n")
        for i in range(args.rows):
            stream.write(f"{i:06d},r{i % 8}\n")
    for name, path in [("baseline", before), ("candidate", after)]:
        directory = output / name
        directory.mkdir()
        evaluation_args = evaluator.make_parser().parse_args([
            "--truth", str(truth), "--predictions", str(path), "--metric", args.metric,
            "--stage", "development", "--split-id", "benchmark", "--output-dir", str(directory),
        ])
        save(directory / "result.json", evaluator.evaluate(evaluation_args, directory))
    setup_seconds = time.perf_counter() - setup_started
    common = ["--truth", str(truth), "--baseline", str(output / "baseline/result.json"),
              "--candidate", str(output / "candidate/result.json"), "--slices", str(slices),
              "--slice-column", "regime", "--output-dir", str(output / "placeholder")]
    timings = {"full": [], "summary": []}
    expected = None
    for repeat in range(3):
        modes = ["full", "summary"] if repeat % 2 == 0 else ["summary", "full"]
        directories = {}
        for mode in modes:
            directory = output / f"{mode}-{repeat}"
            diagnostic_args = analyzer.make_parser().parse_args([*common, *(["--summary-only"] if mode == "summary" else [])])
            report, measurement = measure(full_module if mode == "full" else analyzer, diagnostic_args, directory)
            signature = {key: report[key] for key in SEMANTIC_KEYS}
            if expected is None:
                expected = signature
            if signature != expected:
                raise RuntimeError("Diagnostic meaning differs between modes or repeats")
            directories[mode] = directory
            timings[mode].append(measurement)
        # The default full export remains byte-identical to the reference implementation.
        if args.reference is not None:
            new_full_args = analyzer.make_parser().parse_args(common)
            new_full, _ = measure(analyzer, new_full_args, output / f"new-full-{repeat}")
            if any(new_full[key] != expected[key] for key in SEMANTIC_KEYS):
                raise RuntimeError("Default full diagnostics differ from reference")
            for name in ["baseline.csv", "candidate.csv", "cases.csv", "slices.csv"]:
                if (output / f"new-full-{repeat}" / name).read_bytes() != (directories["full"] / name).read_bytes():
                    raise RuntimeError(f"Default export bytes differ: {name}")
    peaks = {}
    for mode in ["full", "summary"]:
        diagnostic_args = analyzer.make_parser().parse_args([*common, *(["--summary-only"] if mode == "summary" else [])])
        report, measured = measure(full_module if mode == "full" else analyzer, diagnostic_args,
                                   output / f"memory-{mode}", memory=True)
        if any(report[key] != expected[key] for key in SEMANTIC_KEYS):
            raise RuntimeError("Traced execution differs")
        peaks[mode] = measured["python_peak_bytes"]
    medians = {mode: statistics.median(row["seconds"] for row in values) for mode, values in timings.items()}
    result = {"rows": args.rows, "metric": args.metric, "timings": timings, "median_seconds": medians,
              "full_over_summary": medians["full"] / medians["summary"], "python_peak_bytes": peaks,
              "equivalent_diagnostics": True, "full_export_bytes_match_reference": True if args.reference else None,
              "setup_seconds": setup_seconds, "python": platform.python_version(), "system": platform.platform(),
              "analyzer_sha256": evaluator.byte_hash(pathlib.Path(analyzer.__file__).read_bytes()),
              "reference_sha256": evaluator.byte_hash(pathlib.Path(full_module.__file__).read_bytes()),
              "benchmark_sha256": evaluator.byte_hash(pathlib.Path(__file__).read_bytes()),
              "input_hashes": {path.name: evaluator.byte_hash(path.read_bytes()) for path in [truth, before, after, slices]},
              "scope": "One-process diagnostics including input verification, scoring, slicing and output writes; "
                       "Python allocation peaks are not process RSS. Fixture setup and Python startup excluded."}
    save(output / "benchmark.json", result)
    print(json.dumps(result, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
