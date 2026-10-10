---
name: competition-optimize
description: Improve competition scores through task-specific research, diverse baselines, targeted experiments, and independent confirmation within a budget. Use when given a contest task and rules or asked to optimize an entry with a repeatable evaluation path.
---

# Competition Optimize

Optimize the declared objective in the current Codex session. The core selects experiments and manages budget; a task adapter supplies candidate interfaces, rules, scoring, and diagnostics. Maximize or minimize as the metric requires.

## Start or Resume

Resume the same task's run unless a new run is requested. Read its contract and `next-action.md`, reconcile new ledger events and referenced evidence using [the decision loop](references/decision-loop.md), then act on the unresolved question. Missing or stale cards can be rebuilt from `trials.jsonl`. Preserve consumed budget; continuation does not renew the default allowance. Inspect unfinished artifacts before rerunning; partial or interrupted trials cannot establish a best.

For a new run, identify task family, candidate format, hard rules/resources, official metric/formula/direction/aggregation, data/tests, submission limits, and budget. Resolve ambiguous hard rules and direction before costly search; label unknown score terms. Declare confirmation shortlist limit, fallback, and delivery rule. Create `<competition-workspace>/agent-runs/<UTC>-<slug>/` outside protected data/test directories with `task-contract.json`, `research.md`, `trials.jsonl`, `candidates/`, `evaluations/`, and `comparisons/`.

Reserve confirmation and packaging first; allocate remaining work using measured cost. Without an explicit budget, allow at most three candidate trials per run plus final verification. Tested code/configuration variants, including baselines, ablations, repairs, and rejected candidates, consume slots unless separately budgeted. Include research, diagnostics, repetitions, retries, and execution in time/compute costs. A larger search budget needs user authorization.

For a new or changed protocol, read [the adapter contract](references/adapter-contract.md). Verify scoring units, aggregation, timeouts, and validity scope with known-good/bad candidates. Freeze evaluator, development workloads, and confirmation protocol; a scoring correction needs a new contract version and reevaluation. Distinguish local official metrics, proxies, and platform scores. Reuse a matching credible baseline or establish one; distinguish it from a sanity baseline.

## Decision Loop

1. **Choose one affordable action.** Follow [the search protocol](references/score-search.md) to explore, diagnose, refine, tune, or combine from evidence. Before implementation append a planned ledger event with parents, target, hypothesis, predicted observation, cheapest rejection test, and total cost. Search relevant primary sources/code for the specific knowledge gap; use the applicable [task-family guidance](references/task-playbooks.md). An affordable test ends broad research. Check close-ranking stability before fine tuning.
2. **Execute and compare.** Reuse evidence only when candidate, evaluator, score model, data/split, configuration, and relevant environment dependencies match. Recompute affected descendants, preserving independent candidate artifacts, commands, hashes, logs, and results. Cheap screens reject weak/invalid candidates; promotion requires hard checks and matched full fidelity under the declared total objective. Soft speed/component regressions may be acceptable. Preserve incumbent and promising alternatives; missing score terms require provisional proxy choices and preserved tradeoffs.
3. **Record and advance.** Append observation, explanation, decision, cost, and the next falsifiable test to the ledger; refresh the compact decision card at decision boundaries. Refine supported mechanisms and switch when credible gains run out. Diagnose or repeat only when the outcome could change a decision. Do not repeat an unchanged rejected configuration without new evidence.

## Confirm and Deliver

Stop search when no credible action fits outside the reserve. Freeze finalist identities, pipeline/recipe hashes, and delivery rule before independent confirmation; apply it even when rankings reverse. Repeat noisy comparisons within budget and label unresolved gains unproven. Official final tests cannot guide tuning.

Verify selected rules and package bytes. Report baseline and confirmed metrics/direction/provenance, material results, cost, reproduction commands, artifact/evaluator/data hashes, output paths, and uncertainty. Retain task-qualified lessons linked to evidence.

## Adapter Routing

- Fixed-timeslot C++: [adapter usage](references/fixed-timeslot.md).
- Unweighted scalar regression/binary CSV predictions: [prediction tools](references/data-model.md). Read the section needed for evaluation, diagnostics, uncertainty, or frozen blends. Establish training provenance, leakage, member identity, and resource compliance separately.
- Data/model, algorithm/optimization, or stochastic simulation: the applicable section of [task-family guidance](references/task-playbooks.md).
- Other families: establish a verified score contract and adapter before costly search; implementation coverage is task-specific.

Official upload/submission/publication requires explicit user authorization. Keep loops bounded. Parallel evaluations require controlled timing/resource effects and an adequate budget.
