---
name: competition-optimize
description: Improve competition scores by researching and comparing solution routes, implementing substantive candidate changes, refining promising mechanisms, and independently confirming results within a budget. Use when given a contest task and rules or asked to optimize an entry with a repeatable evaluation path.
---

# Competition Optimize

Optimize the declared objective in the current Codex session. The core selects experiments and manages budget; a task adapter supplies candidate interfaces, rules, scoring, and diagnostics. Maximize or minimize as the metric requires.

Search at two levels: select a solution route, then improve its implementation. For score-seeking work, compare credible structural alternatives before settling into repeated parameter tweaks when the budget supports that comparison. A candidate can replace a complete method or coupled pipeline; one hypothesis does not mean one small edit. Choose changes by objective headroom and evidence, not code size.

## Start or Resume

Resume the same task's run unless a new run is requested. Read its contract and `next-action.md`, reconcile new ledger events and referenced evidence using [the decision loop](references/decision-loop.md), then act on the unresolved question. Missing or stale cards can be rebuilt from `trials.jsonl`. Preserve consumed budget; continuation does not renew the default allowance. Inspect unfinished artifacts before rerunning; partial or interrupted trials cannot establish a best.

For a new run, identify task family, candidate format, hard rules/resources, official metric/formula/direction/aggregation, data/tests, submission limits, and budget. Resolve ambiguous hard rules and direction before costly search; label unknown score terms. Declare confirmation shortlist limit, fallback, and delivery rule. Create `<competition-workspace>/agent-runs/<UTC>-<slug>/` outside protected data/test directories with `task-contract.json`, `research.md`, `trials.jsonl`, `candidates/`, `evaluations/`, and `comparisons/`.

Reserve confirmation and packaging first; allocate remaining work using measured cost. Without an explicit budget, allow at most three candidate trials per run plus final verification; treat this as an initial bounded search, not sufficient coverage for a high-score campaign. Prefer a credible baseline and affordable different mechanisms over spending these slots on neighboring parameters. Tested code/configuration variants, including baselines, ablations, repairs, and rejected candidates, consume slots unless separately budgeted. Include research, diagnostics, repetitions, retries, and execution in time/compute costs. A larger search budget needs user authorization.

For a new or changed protocol, read [the adapter contract](references/adapter-contract.md). Verify scoring units, aggregation, timeouts, and validity scope with known-good/bad candidates. Freeze evaluator, development workloads, and confirmation protocol; a scoring correction needs a new contract version and reevaluation. Distinguish local official metrics, proxies, and platform scores. Reuse a matching credible baseline or establish one; distinguish it from a sanity baseline.

## Decision Loop

1. **Choose the route and question.** Use [the route comparison](references/score-search.md#compare-routes-before-choosing-variants) and relevant [task-family guidance](references/task-playbooks.md) to compare substantive alternatives by applicability, headroom, total cost, and existing evidence. Search original writeups/code for the missing mechanism, not a generic reading list. Keep proposed routes distinct from tested variants; reuse a current route map rather than rebuilding it every turn.
2. **Implement the most useful affordable test.** Follow [the search protocol](references/score-search.md) to prototype a route, replace a bottleneck mechanism, refine, tune, or combine. Before implementation record route/mechanism, parents, expected observation, rejection test, fidelity, and total cost. Make the candidate executable at the intended interface; a substantive replacement may change several coupled components. Check close-ranking stability before fine tuning. An executable hypothesis ends broad research, but does not automatically outrank an unexplored stronger route.
3. **Execute and compare.** Reuse evidence only when candidate, evaluator, score model, data/split, configuration, and relevant environment dependencies match. Recompute affected descendants, preserving independent candidate artifacts, commands, hashes, logs, and results. Cheap screens reject weak/invalid candidates; promotion requires hard checks and matched full fidelity under the declared total objective. Soft speed/component regressions may be acceptable. Preserve incumbent and promising alternatives; missing score terms require provisional proxy choices and preserved tradeoffs.
4. **Update the route decision.** Record observation, explanation, cost, decision, and next test; refresh the compact decision card. Deepen a supported route when a credible larger mechanism remains. Repeated negligible refinements trigger a return to representation, training signal, algorithm, or policy alternatives rather than another cosmetic variant. Diagnose or repeat only when the outcome could change a decision. Do not repeat an unchanged rejected configuration without new evidence.

## Confirm and Deliver

Stop search when no credible action fits outside the reserve. Freeze finalist identities, pipeline/recipe hashes, and delivery rule before independent confirmation; apply it even when rankings reverse. Repeat noisy comparisons within budget and label unresolved gains unproven. Official final tests cannot guide tuning.

Verify selected rules and package bytes. Report baseline and confirmed metrics/direction/provenance, material results, cost, reproduction commands, artifact/evaluator/data hashes, output paths, and uncertainty. Retain task-qualified lessons linked to evidence.

## Adapter Routing

- Fixed-timeslot C++: [adapter usage](references/fixed-timeslot.md).
- Unweighted scalar regression/binary CSV predictions: [prediction tools](references/data-model.md). Read the section needed for evaluation, diagnostics, uncertainty, or frozen blends. Establish training provenance, leakage, member identity, and resource compliance separately.
- Data/model, algorithm/optimization, or stochastic simulation: the applicable section of [task-family guidance](references/task-playbooks.md).
- Other families: establish a verified score contract and adapter before costly search; implementation coverage is task-specific.

Official upload/submission/publication requires explicit user authorization. Keep loops bounded. Parallel evaluations require controlled timing/resource effects and an adequate budget.
