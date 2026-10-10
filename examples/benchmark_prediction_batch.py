#!/usr/bin/env python3
"""Measure sequential CLI evaluation/comparison against the equivalent batch CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import platform
import statistics
import subprocess
import sys
import time


REPOSITORY = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY / "skills/competition-optimize/scripts"
sys.path.insert(0, str(SCRIPTS))
from compare_prediction_results import load_result


def command(script: str, arguments: list[object]) -> None:
    result = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *map(str, arguments)],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


def check_results(sequential: pathlib.Path, batch: pathlib.Path, names: list[str]) -> None:
    for name in names:
        before = load_result(sequential / name / "result.json")
        after = load_result(batch / "evaluations" / name / "result.json")
        for key in ["score", "candidate_hash", "evaluator_hash", "score_model_hash", "evaluation",
                    "checks", "validity_scope", "unchecked_rules"]:
            if before[key] != after[key]:
                raise RuntimeError(f"Batch evaluation differs: {name}/{key}")
        if name == names[0]:
            continue
        comparisons = [json.loads(path.read_text(encoding="utf-8")) for path in
                       [sequential / f"compare-{name}.json", batch / "comparisons" / f"{name}.json"]]
        for value in comparisons:
            for role in ["baseline", "candidate"]:
                value[role].pop("result")
        if comparisons[0] != comparisons[1]:
            raise RuntimeError(f"Batch comparison differs: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path, help="New directory outside the repository")
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    if output == REPOSITORY or REPOSITORY in output.parents:
        parser.error("Keep benchmark artifacts outside the repository")
    output.mkdir(exist_ok=False)
    cases = []
    for rows, candidate_count in [(1000, 4), (10000, 12)]:
        root = output / f"rows-{rows}-candidates-{candidate_count}"
        root.mkdir()
        truth = root / "truth.csv"
        truth.write_text("id,target\n" + "".join(f"{i:05d},{i % 13 / 2}\n" for i in range(rows)), encoding="utf-8")
        sources = {}
        for index in range(candidate_count):
            name, source = f"model-{index}", root / f"model-{index}.csv"
            source.write_text("id,prediction\n" + "".join(
                f"{i:05d},{i % 13 / 2 + (0.5 if index == 0 else ((i % 7) - 3) / (index + 2))!r}\n"
                for i in range(rows)), encoding="utf-8")
            sources[name] = source
        common = ["--truth", truth, "--metric", "rmse", "--stage", "development", "--split-id", root.name]
        timings = {"sequential": [], "batch": []}
        for repeat in range(3):
            sequential, batch = root / f"sequential-{repeat}", root / f"batch-{repeat}"
            order = ["sequential", "batch"] if repeat % 2 == 0 else ["batch", "sequential"]
            for mode in order:
                started = time.perf_counter()
                if mode == "sequential":
                    sequential.mkdir()
                    for name, source in sources.items():
                        command("evaluate_predictions.py", [*common, "--predictions", source,
                                                              "--output-dir", sequential / name])
                        if name != "model-0":
                            command("compare_prediction_results.py", [
                                "--baseline", sequential / "model-0/result.json",
                                "--candidate", sequential / name / "result.json",
                                "--output", sequential / f"compare-{name}.json",
                            ])
                else:
                    candidates = [value for name, source in sources.items() for value in ["--candidate", name, source]]
                    command("evaluate_prediction_batch.py", [*common, *candidates,
                                                               "--baseline", "model-0", "--output-dir", batch])
                timings[mode].append(time.perf_counter() - started)
            check_results(sequential, batch, list(sources))
        before, after = [statistics.median(timings[mode]) for mode in ["sequential", "batch"]]
        case = {"row_count": rows, "candidate_count": candidate_count,
                "sequential_seconds": before, "batch_seconds": after, "speedup": before / after,
                "sequential_processes": candidate_count * 2 - 1, "batch_processes": 1,
                "identical_scores_hashes_contracts_comparisons": True, "timings": timings}
        cases.append(case)
        print(json.dumps({key: value for key, value in case.items() if key != "timings"}), flush=True)
    report = {"python": platform.python_version(), "system": platform.platform(), "timing_repetitions": 3,
              "tool_hashes": {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest() for name in
                              ["evaluate_prediction_batch.py", "evaluate_predictions.py", "compare_prediction_results.py"]},
              "cases": cases, "scope": "CSV CLI evaluation/comparison including startup and artifacts; no training or agent search"}
    with (output / "benchmark.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
