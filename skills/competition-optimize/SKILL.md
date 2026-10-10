---
name: competition-optimize
description: Derive competition optimizations from current code and experiment history, implement and evaluate them, and iterate toward a higher declared score. Use when given contest rules or asked to build or improve an entry with a repeatable evaluation path.
---

# Competition Optimize

For an optimization request, deliver implemented, executed candidates and measured comparisons in the current session. Reading, planning, route names, and experiment records alone do not complete that request. Respect an explicit research-only request. A task adapter supplies the interface, validity checks and objective; optimize its declared metric in the correct direction.

## Start or Resume Quickly

Read the task/rules, current implementation and relevant successful/failed experiment history. Inspect the executed source and configuration of the candidate being improved, including the important code paths and pertinent prior changes. Reuse inspected code only while its identity matches. Recover unfinished work before rerunning. Reuse a verified evaluator and credible baseline with matching dependencies. Read [adapter requirements](references/adapter-contract.md) when establishing or changing evaluation; use [resume details](references/decision-loop.md) for interrupted, stale or ambiguous records.

Fix the interface, hard rules, metric/direction, development protocol and confirmation reserve before candidate execution. Record unknown score terms. Keep candidate artifacts and results in an isolated run directory. Use existing records or a compact contract/ledger; document facts needed for reproduction, not every possible template field before doing useful work. Missing decisive rules/data may block execution; ask for that specific input and complete independent setup.

Use a bounded reconnaissance pass before expensive implementation: map the entry points and likely hot path, inspect only the history linked to the current incumbent and limiting behavior, and check the evaluator/contract hashes. Stop reading once one actionable bottleneck and its evidence are identified. Do not load every old log or source file merely to appear thorough. If the evidence does not support a proposal, run the smallest diagnostic that could change the implementation decision.

## Bound Work Without Repeated Approval

Honor explicit user time/compute/trial limits at their stated scope and retain all consumed work. Do not reset an exhausted user cap. When none applies, start one default work round: at most **45 minutes of total wall time and eight evaluated candidate implementations/recipes**, stopping at either limit. Reserve measured confirmation/packaging cost first; research, implementation, diagnostics and repairs use this time. Every tested code/pipeline/recipe variant, including baselines, failures and repairs, counts; unchanged verification consumes time/compute.

This default is per user work request, not a lifetime allowance for the task. After delivery, a new request to continue permits another default round if no explicit user cap prevents it; retain the incumbent, history and cumulative costs. Never renew rounds automatically. Distinguish user limits from old skill defaults or agent estimates in recovered records. Requesting optimization already authorizes ordinary local research, implementation and evaluation within these bounds; do not ask permission merely to start those actions.

## Repeat the Feedback Loop

Initialize the best development candidate from the credible baseline. Repeat steps 1-5 in the same work round; a completed trial returns to step 1 when a useful next action fits outside the reserve. Do not wait for another user prompt between trials.

The default is agent-proposed implementation changes, grounded in code and history. Do not schedule grid/random/Bayesian parameter searches, neighboring-value sweeps or seed hunting. Dedicated parameter tuning requires an explicit user request. A supported mechanism may change internal settings as part of its implementation; changing a list of values alone does not establish that mechanism.

1. **Propose from code and history.** Identify the current limiting behavior in specific code paths, using matched results and relevant successful/failed attempts. Prioritize hard feasibility, then objective headroom. Choose one concrete optimization: cite the code location, historical evidence, proposed mechanism and expected observation. Explain what differs from rejected attempts and why this proposal deserves the next budget. Use the [efficient proposal and quality gate](references/score-search.md#efficient-proposal-and-quality-gate); search a specific knowledge gap when needed, then implement without waiting for proposal approval within the authorized scope.
2. **Implement the chosen change.** Name the parent, concrete implementation target, expected observation and planned cost. Favor a complete alternative algorithm/representation, model/training pipeline or policy over repeated adjacent settings, caches or cleanup passes when substantive headroom warrants it. Implement necessary coupled components together. Keep an evidence-supported refinement when worthwhile; a route name does not make a local patch a different method. Valid outputs may differ from the incumbent.
3. **Run and compare.** Pass the candidate through the [quality gate](references/score-search.md#efficient-proposal-and-quality-gate) before a costly full run: interface and hard rules, evaluator identity, artifact reproducibility and a cheap stage calibrated to the declared objective when one exists. Then compile/train/execute at matched fidelity, preserving source/configuration, commands, results and validity evidence. Compare with the parent and current best under the declared objective, including resource costs. Separate partial/invalid runs from valid low scores; reduced fidelity cannot establish a full-score winner.
4. **Turn the result into feedback.** State the observed gain/regressions, relevant errors or bottlenecks, and whether the prediction was supported, contradicted or unresolved. Keep causal explanations provisional unless tested. Decide promotion separately from further investment: update the best only with eligible evidence; retain useful alternatives. Choose repair, measurement, deepening, route replacement or combination using [feedback rules](references/score-search.md#close-the-feedback-loop).
5. **Execute the follow-up or stop with a reason.** Link the feedback to the next specific code/pipeline change, its parent and expected observation. If it fits and remains useful, return to step 1 and implement it now. Missing evidence warrants a targeted diagnostic or search that produces a next implementation decision. Stop for the applicable budget/reserve, a concrete blocker or no credible useful follow-up; then freeze/confirm/deliver. A weak score, one patch or a list of ideas alone does not end the round.

## Select by the Actual Objective

Enforce competition/user hard limits. Do not invent universal minimum gains, maximum slowdowns, statistical-significance gates or output-equivalence requirements that replace the objective. Agent-chosen screens are provisional search policies, not contest rules; state their basis and revise them prospectively when they exclude useful comparisons. Do not retrospectively change a frozen delivery rule from confirmation feedback.

If score terms are missing, preserve raw components and tradeoff candidates, label proxy choices provisional, and identify what could reverse selection. A small gain may be real; a quality/runtime tradeoff with unknown score parameters cannot establish a net loss. Resolve consequential measurement noise within budget.

## Confirm and Deliver

Freeze finalist artifacts and the delivery rule before independent confirmation. Keep final tests out of tuning. Verify selected validity, resource checks and package bytes. Stop when no useful candidate fits outside the reserve.

Deliver runnable artifacts, baseline/candidate metrics with provenance, real changes, cost, reproduction commands and remaining uncertainty. Include a compact iteration trace: measured result -> feedback decision -> actual successor/change -> new result or stated stop. Mark unexecuted follow-ups as pending, never as completed progress. If nothing improved, report that outcome with executed alternatives or the concrete blocker. Official submission/upload requires explicit user authorization.

## Adapter Routing

- Fixed-timeslot C++: [adapter usage](references/fixed-timeslot.md).
- Unweighted regression/binary CSV predictions: the needed section of [prediction tools](references/data-model.md); establish training/leakage/resource provenance separately.
- Other families: verify a task-specific interface, objective and validity path before costly search.
