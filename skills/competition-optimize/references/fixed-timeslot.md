# Fixed Timeslot Adapter

Use this reference for the Huawei Cloud fixed-timeslot C++ case. Invoke the bundled adapter by absolute path. Set `COMPETITION_ROOT` to the directory containing `solution.h` and `tests/`, or pass it explicitly. `CXX` selects the compiler; the default is `g++`.

```powershell
python <skill-dir>/scripts/evaluate_current_timeslot.py `
  --candidate <candidate.cpp> `
  --stage smoke `
  --competition-root <competition-root> `
  --output-dir <new-run-dir>
```

Stages are `smoke` (one small correctness run), `short` (N 100/400/10000, Q 1/10/100, five seeds), `full` (N 400/10000, Q 1000, five seeds and nine scenarios), and `package` (static-rule scan plus exact ZIP verification). Use a new output directory outside the competition `tests/` tree. Stdout gives a compact JSON summary and `result.json` is the source of truth. Compile and per-process timeout default to 60 seconds and can be set with `--timeout`. Failed evaluations may retain partial metrics for diagnosis; only successful complete short/full results can be compared. Package success does not replace correctness evaluation or manual rule review.

The official per-testcase score is `0.55 * Scoreuniformity + 0.35 * Scorevariance + 0.10 * Scorespeed`. Speed is 1 when measured time `t <= tfast`, 0 when `t >= tslow`, and otherwise `1 - ln(t / tfast) / ln(tslow / tfast)`. The published problem statement does not provide numeric `tfast` and `tslow`; the adapter therefore reports the local quality proxy `0.55 * uniformity + 0.35 * stability` and operation/init timing separately. It does not calculate the official total score. Do not infer the missing speed contribution or official test aggregation.

The adapter snapshots the candidate and writes binaries, logs, CSV, JSON, and package artifacts only under the requested output directory. It reuses the competition harness and is not a sandbox; only run candidate code you are authorized to execute. The candidate is a single UTF-8 C++ source file using the provided `solution.h` interface and standard library.

Compare completed runs with:

```powershell
python <skill-dir>/scripts/compare_timeslot_results.py `
  --baseline <baseline-result.json> `
  --candidate <candidate-result.json> `
  --output <new-comparison.json>
```

The comparator requires successful, complete results with matching evaluator hashes, runtime environments, and workload keys. Timing deltas are local measurements and need repeat confirmation before they are used to select a candidate.
