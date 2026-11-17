#!/usr/bin/env python3
"""Compare bootstrap cost/results with a saved, trusted earlier script version."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import pathlib
import platform
import random
import statistics
import sys
import time
from unittest.mock import patch


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "skills/competition-optimize/scripts"
sys.path.insert(0, str(SCRIPTS))
import compare_prediction_uncertainty as current


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=pathlib.Path,
                        help="Trusted earlier compare_prediction_uncertainty.py; imported as Python code")
    parser.add_argument("--output", required=True, type=pathlib.Path, help="New JSON receipt")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--timing-repetitions", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    if args.rows < 2 or not 100 <= args.samples <= 10000 or args.timing_repetitions < 1:
        parser.error("Need at least two rows, 100-10000 samples and positive timing repetitions")
    args.reference = args.reference.resolve(strict=True)
    spec = importlib.util.spec_from_file_location("reference_bootstrap", args.reference)
    reference = importlib.util.module_from_spec(spec)
    # Import the reference's own scorer dependencies, not the current scorer.
    with patch.dict(sys.modules), patch.object(sys, "path", [str(args.reference.parent), *sys.path]):
        for name, module in list(sys.modules.items()):
            source = getattr(module, "__file__", None)
            if source and pathlib.Path(source).resolve().parent == SCRIPTS:
                sys.modules.pop(name)
        spec.loader.exec_module(reference)
    rng = random.Random(8301)
    count, samples, timing_repetitions = args.rows, args.samples, args.timing_repetitions
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
            before_values, after_values = (([int(p >= 0.5) for p in values] for values in [baseline, candidate])
                                           if metric == "accuracy" else (baseline, candidate))
            for engine in (reference, current):
                engine.evaluator.calculate_metric(metric, labels, before_values)
            timings = {"reference": [], "current": []}
            max_difference = 0.0
            for repeat in range(timing_repetitions):
                outputs = {}
                # Alternate order to reduce a consistent warm-up advantage.
                order = [("reference", reference), ("current", current)]
                if repeat % 2:
                    order.reverse()
                for name, engine in order:
                    started = time.perf_counter()
                    outputs[name] = engine.bootstrap(metric, labels, before_values, after_values, units, samples,
                                                     29, 1e-15, count * samples * 2)
                    timings[name].append(time.perf_counter() - started)
                if (outputs["reference"][1] != outputs["current"][1]
                        or len(outputs["reference"][0]) != len(outputs["current"][0])):
                    raise RuntimeError(f"Bootstrap draws differ: {unit_name}/{metric}")
                for left, right in zip(outputs["reference"][0], outputs["current"][0], strict=True):
                    for key in left:
                        if key in {"baseline_score", "candidate_score", "objective_improvement"} and left[key] is not None:
                            max_difference = max(max_difference, abs(left[key] - right[key]))
                            equivalent = math.isclose(left[key], right[key], rel_tol=1e-13, abs_tol=1e-14)
                        else:
                            equivalent = left[key] == right[key]
                        if not equivalent:
                            raise RuntimeError(f"Bootstrap output differs: {unit_name}/{metric}/{key}")
            before, after = [statistics.median(timings[name]) for name in ["reference", "current"]]
            receipt = {"metric": metric, "sampling_unit": unit_name, "equivalent_outputs": True,
                       "max_absolute_score_difference": max_difference,
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
              "reference_scorer": str(pathlib.Path(reference.evaluator.__file__).resolve()),
              "score_tolerance": {"relative": 1e-13, "absolute": 1e-14},
              "results": results,
              "scope": "In-process bootstrap only; excludes CLI startup, CSV parsing, and training"}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
