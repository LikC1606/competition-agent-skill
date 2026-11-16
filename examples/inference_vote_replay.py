#!/usr/bin/env python3
"""Exercise cached-answer replay with synthetic cases; no model or timing experiment."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "skills/competition-optimize/scripts"
sys.path.insert(0, str(SCRIPTS))
import replay_inference_votes as replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path, help="new directory")
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    patterns = [
        ("solved", "A", ["A", "A", "A", "B", "C"]),
        ("selection-gap", "right", ["wrong", "right", "wrong", "wrong", None]),
        ("generation-gap", "right", ["wrong"] * 5),
        ("format-failures", "right", [None] * 5),
    ]
    cases = [{"id": name, "target": target,
              "samples": [{"id": str(index), "answer": answer,
                           "status": "completed" if answer is not None else "invalid"}
                          for index, answer in enumerate(answers)]}
             for name, target, answers in patterns]
    trace = {"schema_version": 1, "stage": "development",
             "generation": {"kind": "synthetic_fixture",
                            "recipe_sha256": replay.evidence.sha256(pathlib.Path(__file__).read_bytes()),
                            "workload_sha256": replay.evidence.sha256(replay.evidence.canonical(cases)),
                            "answer_parser_sha256": replay.evidence.sha256(b"synthetic exact-string answers")},
             "cases": cases}
    cache = output / "trace.json"
    cache.write_text(json.dumps(trace, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    report = replay.analyze(argparse.Namespace(trace=cache, max_samples=5))
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    print(json.dumps({"scope": "synthetic_fixture_only", "case_count": report["case_count"],
                      "answers_unchanged": report["answers_unchanged"],
                      "skipped_sample_slots": report["skipped_sample_slots"],
                      "measured_wall_time_savings": None, "output_dir": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
