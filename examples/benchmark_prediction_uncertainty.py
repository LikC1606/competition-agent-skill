#!/usr/bin/env python3
"""Compare bootstrap cost/results with a saved, trusted earlier script version."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import platform
import random
import statistics
import sys
import time


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "skills/competition-optimize/scripts"
sys.path.insert(0, str(SCRIPTS))
import compare_prediction_uncertainty as current


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=pathlib.Path,
                        help="Trusted earlier compare_prediction_uncertainty.py; imported as Python code")
    parser.add_argument("--output", required=True, type=pathlib.Path, help="New JSON receipt")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    spec = importlib.util.spec_from_file_location("reference_bootstrap", args.reference)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    rng = random.Random(8301)
    count, samples, timing_repetitions = 1000, 1000, 3
    labels = [index % 2 for index in range(count)]
    baseline = [round(rng.random(), 2) for _ in labels]
    candidate = [round(rng.random(), 2) for _ in labels]
    groups, start = [], 0
    while start < count:
        end = min(count, start + [1, 3, 7, 11][len(groups) % 4])
        groups.append(list(range(start, end)))
        start = end
    results = []
    for unit_name, units in [("row", [[i] for i in range(count)]), ("group", groups)]:
        for metric in current.evaluator.METRIC_DIRECTIONS:
            timings = {"reference": [], "current": []}
            for repeat in range(timing_repetitions):
                outputs = {}
                # Alternate order to reduce a consistent warm-up advantage.
                order = [("reference", reference), ("current", current)]
                if repeat % 2:
                    order.reverse()
                for name, engine in order:
                    started = time.perf_counter()
                    outputs[name] = engine.bootstrap(metric, labels, baseline, candidate, units, samples,
                                                     29, 1e-15, 2_000_000)
                    timings[name].append(time.perf_counter() - started)
                if outputs["reference"] != outputs["current"]:
                    raise RuntimeError(f"Bootstrap output differs: {unit_name}/{metric}")
            before, after = [statistics.median(timings[name]) for name in ["reference", "current"]]
            receipt = {"metric": metric, "sampling_unit": unit_name, "identical_outputs": True,
                       "reference_seconds": before, "current_seconds": after, "speedup": before / after,
                       "timings": timings, "row_draws": outputs["current"][1],
                       "bootstrap_hash": hashlib.sha256(json.dumps(outputs["current"], sort_keys=True,
                                                                   allow_nan=False).encode()).hexdigest()}
            results.append(receipt)
            print(json.dumps({key: value for key, value in receipt.items() if key not in {"timings", "bootstrap_hash"}}),
                  flush=True)
    report = {"python": platform.python_version(), "system": platform.platform(),
              "row_count": count, "bootstrap_samples": samples, "timing_repetitions": timing_repetitions,
              "data_seed": 8301, "bootstrap_seed": 29,
              "reference_hash": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
              "current_hash": hashlib.sha256(pathlib.Path(current.__file__).read_bytes()).hexdigest(),
              "results": results,
              "scope": "In-process bootstrap only; excludes CLI startup, CSV parsing, and training"}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
