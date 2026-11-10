# Max-Cut task: source and evaluation contract

This task uses original Gset files served from Yinyu Ye's Stanford directory. The adapter and baseline are original code; no graph data or upstream generator source is committed.

## Primary evidence checked on November 10, 2026

- Directory: https://web.stanford.edu/~yyye/yyye/Gset/
- Author page: https://web.stanford.edu/~yyye/
- Generator source inspected, not executed: https://web.stanford.edu/~yyye/yyye/Gset/rudy.c

The directory lists the downloaded instance names. In the inspected `rudy.c`, lines 1021–1042 number vertices from one and write the vertex/edge count header; lines 1044–1072 output one integer-weight edge for each endpoint pair with the first endpoint smaller than the second. The downloaded files were independently parsed to verify their declared counts, integer weights, endpoint range, absence of self-loops and duplicate undirected edges. These are direct source/file checks; this task does not rely on a third-party Gset mirror, claimed optimum, instance-family description, or leaderboard.

| File | Assigned role | Vertices | Edges | Observed weights | SHA256 |
| --- | --- | ---: | ---: | --- | --- |
| G1 | Development | 800 | 19176 | +1 | `73bf704d8ffc55ba42260ab4cb659e3dcb6e729be70404d2cf476ba4e46d1665` |
| G6 | Development | 800 | 19176 | −1, +1 | `e3dd8b29205280f1ad5806849321cdff6f11324c75cb95647d5783f3e47a1103` |
| G11 | Development | 800 | 1600 | −1, +1 | `c2a760d2926db4fefd23b25c098dcd6311f711b355dbd1cc689fa25660c73174` |
| G2 | Confirmation | 800 | 19176 | +1 | `732d57480a0151e81253a08535da539ff579f77dbc8673d2b58f4b051f6ccdac` |
| G7 | Confirmation | 800 | 19176 | −1, +1 | `62a49edc162b2548ea4a58f2b65a6398f9a54a24ea448f3939f1526326200329` |
| G12 | Confirmation | 800 | 1600 | −1, +1 | `a8628108d95d74b90a342fabe97faaa566dabfb3f64382a93548b3bdf131f8e3` |

Each file URL is the directory URL followed by the exact filename. The first-read directory snapshot SHA256 was `509c7e8c18df4a8f624a6009f7becda5d577ec1922fc09e4e53d3c21b5687508`; `rudy.c` was `365c1441272edfa431d3a0a6f2f2122c63e7fd44bff091f1d2f3eeabfc0d119a`. The live author page can change and is not a scoring dependency. `fetch_sources` records the bytes it actually checks and fails on a changed pinned graph instead of silently redefining the task.

No explicit dataset redistribution license was located in the inspected directory, author page or generator snapshot. This is a limited observation about those sources, not a declaration that no license exists anywhere. Public download is not treated as a redistribution grant. Raw downloads and execution artifacts belong in the caller's external cache/run directories. They must not be committed to the repository.

## Fixed task choices

The two graph sets were selected before any candidate runs. They cover the observed all-positive and signed weights at two edge counts. These are task-author choices, not official Gset train/test partitions. Public preparation contains only the development graphs, candidate source and a self-contained evaluator; confirmation selection/data stays in the controller's private directory. Copy only `public/` to an agent workspace, never the cache, `private/`, or preparation-root source manifest. Because Gset is public, this is posterior evaluation on public instances, not evidence that an agent has never seen them.

Candidate interface: `solve(n, edges, seed) -> list[int | bool]`, with zero-based endpoints and exactly one 0/1 label per vertex. The trusted evaluator computes the signed raw cut independently. The objective is the sum of raw cuts on the fixed three-graph workload, maximized. This local aggregation weights the larger-magnitude graphs more heavily; it is not a platform ranking. Each case retains its raw cut and sum-of-positive-weights upper bound. That bound is not claimed to be tight or optimal. Development and confirmation totals use different graphs and must not be directly treated as the same measurement.

The supplied baseline performs eight seeded random starts, each followed by complete best-improvement single-vertex flips until no positive flip remains; it retains the highest raw cut. It handles signed weights and maintains exact flip gains. It is more than random assignment but does not escape single-flip local optima or claim a best-known Gset solution. The task leaves those mechanisms and search efficiency open for improvement, under the same per-graph budget for both paired arms.

Public limits are 3 seconds wall time per graph including worker setup, 3 seconds CPU per process, 256 MiB address space per process, and 1 MiB per output file. POSIX worker limits and process-group cleanup are implemented. These do not provide a security sandbox, enforce a total limit over adversarial child processes, or prove no network/external-file access. Candidate instructions prohibit those actions. An invalid partition, exception, resource termination or timeout stops the run and yields no aggregate objective; valid low/zero/negative cuts remain valid measurements.

`evaluate` snapshots `candidate.py`, saves per-case input/output/logs/partitions, and emits source, evaluator, score-model, configuration and full workload identities. Its `archive` helper contains absolute source/result paths and `configuration: null`; those paths are for immediate archive ingestion. `confirm` ignores original absolute paths: it verifies the copied `candidate.py` and `result.json` inside `frozen_run`, checks the matching complete development contract, then executes only that frozen source on distinct confirmation graph IDs/bytes. The whole run can therefore be copied before confirmation.

The public evaluator is copied from `maxcut_runtime.py` to `public/task.py` byte-for-byte. Both paired arms should use the controller's common trusted evaluator/public data for final rescoring, even if an agent edits its workspace copy. The helper exposes `evaluate --public ... --candidate ... --output ... --seed ...`; the import interface additionally provides `fetch_sources`, `prepare`, and `confirm` in `maxcut.py`.
