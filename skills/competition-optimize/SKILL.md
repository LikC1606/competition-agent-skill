---
name: competition-optimize
description: Improve competition scores through task-specific research, diverse baselines, targeted experiments, and independent confirmation within a budget. Use when given a contest task and rules or asked to optimize an entry with a repeatable evaluation path.
---

# Competition Optimize

Optimize the declared objective in the current Codex session. The core selects experiments and manages budget; a task adapter supplies candidate interfaces, rules, scoring, and diagnostics. Maximize or minimize as the metric requires.

## Workflow

1. **Seal or resume.** Read an existing run's contract and latest decisions first. For a new run, identify task family, candidate format, hard rules/resources, official metric/formula/direction/aggregation, data/tests, submission limits, and budget. Resolve ambiguous hard rules and direction before costly search; label unknown score terms. Declare the confirmation shortlist limit, fallback, and delivery rule. Create `<competition-workspace>/agent-runs/<UTC>-<slug>/` outside protected data/test directories with `task-contract.json`, `research.md`, `trials.jsonl`, `candidates/`, `evaluations/`, and `comparisons/`.
2. **Verify scoring.** Read [the adapter contract](references/adapter-contract.md). Check rules against the evaluator's direction, units, aggregation, timeouts, and validity scope using known-good/bad candidates. Freeze evaluator, development workloads, and confirmation protocol. A scoring correction needs a new contract version and reevaluation of compared candidates. Distinguish local official metrics, proxies, and platform scores.
3. **Research and baseline.** Read the applicable [task-family guidance](references/task-playbooks.md). Search primary sources/source code for the objective, scale, constraints, and bottleneck. Convert findings into hypotheses with prerequisites and cheap transfer tests; stop broad research once an affordable test is ready. Reuse a valid matching baseline or establish one. Identify sanity versus credible scoring baselines; assess improvements against the credible reference. Save immutable artifacts, commands, hashes, logs, and results.
4. **Budget by cost.** Reserve confirmation and packaging first; use measured baseline cost to allocate remaining work. Without an explicit budget, allow at most three candidate trials plus final verification. Code/configuration variants, including ablations, repairs, and rejected candidates, consume trial slots; declared repetitions consume time/compute. Include research, diagnostics, retries, and execution costs. Use the [efficiency guidance](references/score-search.md#avoid-work-that-cannot-change-the-next-decision) to select useful measurements and caches. A larger search budget needs user authorization.
5. **Choose and learn.** Follow [the search protocol](references/score-search.md): explore, diagnose, refine, tune, or combine according to evidence. Before implementation record parents, target component, hypothesis, predicted observation, cheapest rejection test, and cost. Preserve incumbent and promising alternatives; cheaply reject weak/invalid candidates and compare promising ones at matched full fidelity. Check close-ranking stability before fine tuning. Refine supported mechanisms; switch when credible gains run out. Append evidence and the next decision, separating observation, explanation, and proposed test.
6. **Promote and confirm.** Pass hard checks and promote by the declared total objective at matched fidelity; soft speed/component regressions may be acceptable. Missing score terms require provisional proxy choices and preserved tradeoffs. Tune on development evidence and confirm on separate data/seeds. Freeze finalist identities, pipeline/recipe hashes, and delivery rule before confirmation; apply it even when rankings reverse. Repeat noisy comparisons within budget and label unresolved gains unproven. Official final tests cannot guide tuning.
7. **Deliver.** Stop at budget or when no credible trial fits outside the reserve. Verify selected rules and package bytes. Report baseline and confirmed metrics/direction/provenance, material results, cost, reproduction commands, artifact/evaluator/data hashes, output paths, and uncertainty. Retain task-qualified lessons linked to their evidence.

Reuse evaluations only when candidate, evaluator, score model, data/split, configuration, and relevant environment hashes match. An unfinished trial can be repaired within budget or classified as interrupted; it cannot establish a best. Resume the same task's run unless a new run is requested.

## Adapter Routing

- Fixed-timeslot C++: [adapter usage](references/fixed-timeslot.md).
- Unweighted scalar regression/binary CSV predictions: [prediction tools](references/data-model.md). Read the section needed for evaluation, diagnostics, uncertainty, or frozen blends. Establish training provenance, leakage, member identity, and resource compliance separately.
- Data/model, algorithm/optimization, or stochastic simulation: the applicable section of [task-family guidance](references/task-playbooks.md).
- Other families: establish a verified score contract and adapter before costly search; implementation coverage is task-specific.

Official upload/submission/publication requires explicit user authorization. Keep loops bounded. Parallel evaluations require controlled timing/resource effects and an adequate budget.
