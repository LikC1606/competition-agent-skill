---
name: competition-optimize
description: Derive competition optimizations from current code and experiment history, implement and evaluate them, and iterate toward a higher declared score. Use when given contest rules or asked to build or improve an entry with a repeatable evaluation path.
---

# Competition Optimize

For an optimization request, deliver implemented, executed candidates and measured comparisons in the current session. Reading, planning, route names, and experiment records alone do not complete that request. Respect an explicit research-only request. A task adapter supplies the interface, validity checks and objective; optimize its declared metric in the correct direction.

## Start or Resume Quickly

Read the task/rules, current implementation and relevant successful/failed experiment history. Inspect the executed source and configuration of the candidate being improved, including the important code paths and pertinent prior changes. Reuse inspected code only while its identity matches. Recover unfinished work before rerunning. Reuse a verified evaluator and credible baseline with matching dependencies. Read [adapter requirements](references/adapter-contract.md) when establishing or changing evaluation; use [resume details](references/decision-loop.md) for interrupted, stale or ambiguous records.

Fix the interface, hard rules, metric/direction and development/confirmation protocol before candidate execution. Reserve confirmation/packaging resources only when an actual limit applies. Record unknown score terms. Keep candidate artifacts and results in an isolated run directory. Use existing records or a compact contract/ledger; document facts needed for reproduction, not every possible template field before doing useful work. Missing decisive rules/data may block execution; ask for that specific input and complete independent setup.

Use a bounded reconnaissance pass before expensive implementation: map the entry points and likely hot path, inspect only the history linked to the current incumbent and limiting behavior, and check the evaluator/contract hashes. Stop reading once one actionable bottleneck and its evidence are identified. Do not load every old log or source file merely to appear thorough. If the evidence does not support a proposal, run the smallest diagnostic that could change the implementation decision.

Maintain a compact candidate archive in the run directory. Keep the incumbent, the best representative of each materially different route, promising unresolved candidates, and rejected mechanisms with their evidence. Give each candidate a code/configuration fingerprint and parent IDs. Before implementing, compare the proposed change with the archive; a near-duplicate of a rejected change needs new evidence or a changed prerequisite, otherwise replace the proposal.

Separate implementation identity from output identity. Different stochastic predictions from unchanged code/recipe are measurements of one implementation; preserve their scores and costs, and resolve consequential uncertainty under the declared repetition protocol. Improve the actual code or complete recipe next. For algorithm source plus configuration, a genuine source change can retain the same settings.

For repeated trials, use [`candidate_archive.py`](scripts/candidate_archive.py) or verified equivalent records. Start the next decision with `brief`: retrieve matched best versions, recent feedback/failures, code paths and pending proposals once, then inspect the relevant code and implement. The latest experiment is not necessarily the best parent. Check snapshots, bind the proposal to code/feedback, and record its measured successor; only evaluated outcomes count as executed changes. Use [archive checks](references/score-search.md#candidate-archive-and-route-switching) and [evidence retrieval and proposal/result links](references/iteration-trace.md) as needed.

## Continue Without Default Caps

Do not impose default limits on total time, compute/cost, candidate count or rounds. An optimization request authorizes ordinary local research, implementation and evaluation; continue useful feedback-driven iterations without asking for renewed permission between trials or batches. Record actual time/compute/cost and evaluated variants, including baselines, failures, repairs and unchanged repetitions. Accounting is evidence for efficient decisions, not a quota.

Honor competition hard rules, actual resource availability and any limits the user currently specifies. Apply a user's later removal or change of optimization limits prospectively; preserve earlier consumption and evidence. On resumption, distinguish these applicable constraints from obsolete skill defaults and agent estimates. Record no self-imposed cap when none applies; do not require a numeric allowance, create a replacement cap or stop because a historical default was spent. Under a genuine finite constraint, plan confirmation/packaging resources from measured costs.

## Repeat the Feedback Loop

Initialize the best development candidate from the credible baseline. Repeat steps 1-5 while useful executable follow-ups remain within applicable constraints. A completed trial returns to step 1; do not wait for another user prompt between trials.

The default is agent-proposed implementation changes, grounded in code and history. Do not schedule grid/random/Bayesian parameter searches, neighboring-value sweeps or seed hunting. Dedicated parameter tuning requires an explicit user request. A supported mechanism may change internal settings as part of its implementation; changing a list of values alone does not establish that mechanism.

Use exploration and exploitation deliberately. Exploit when a route has a supported unresolved mechanism or measurable headroom; explore a different representation, model family, neighborhood, data signal or policy when the current route has repeated comparable weak results. Do not keep polishing the same route only because it is cheap to edit.

1. **Propose from code and history.** Identify the limiting code behavior from matched results and relevant successful/failed attempts. Prioritize hard feasibility, then objective headroom. Keep one compact proposal: parent/code location, historical basis, mechanism, difference from rejected attempts, expected observation, validation, cost and stop condition. Link it from other notes instead of copying it. Use the [proposal and quality gate](references/score-search.md#efficient-proposal-and-quality-gate); search a specific knowledge gap when needed, then implement within the authorized scope.
2. **Implement the chosen change.** Name the parent, concrete implementation target, expected observation and planned cost. Favor a complete alternative algorithm/representation, model/training pipeline or policy over repeated adjacent settings, caches or cleanup passes when substantive headroom warrants it. Implement necessary coupled components together. Keep an evidence-supported refinement when worthwhile; a route name does not make a local patch a different method. Valid outputs may differ from the incumbent.
3. **Run and compare.** Pass the candidate through the [quality gate](references/score-search.md#efficient-proposal-and-quality-gate) before a costly full run: interface and hard rules, evaluator identity, artifact reproducibility and a cheap stage calibrated to the declared objective when one exists. Then compile/train/execute at matched fidelity, preserving source/configuration, commands, results and validity evidence. Compare with the parent and current best under the declared objective, including resource costs. Separate partial/invalid runs from valid low scores; reduced fidelity cannot establish a full-score winner.
4. **Turn the result into feedback.** State the observed gain/regressions, relevant errors or bottlenecks, and whether the prediction was supported, contradicted or unresolved. Update the candidate archive and failure mechanism index. Keep causal explanations provisional unless tested. Decide promotion separately from further investment: update the best only with eligible evidence; retain useful alternatives. Choose repair, measurement, deepening, route replacement or combination using [feedback rules](references/score-search.md#close-the-feedback-loop).
5. **Execute the follow-up or stop with a reason.** Link the feedback to the next specific code/pipeline change, its parent and expected observation. If it remains useful and feasible, return to step 1 and implement it now. Missing evidence warrants a targeted diagnostic or search that produces a next implementation decision. Stop when the user asks, an applicable hard/resource constraint prevents further work, a concrete blocker cannot be resolved, or no credible useful follow-up remains after considering diagnostics and alternative routes; then freeze/confirm/deliver as feasible. A weak score, one patch, a list of ideas or a completed batch alone does not end optimization.

## Select by the Actual Objective

Enforce competition/user hard limits. Do not invent universal minimum gains, maximum slowdowns, statistical-significance gates or output-equivalence requirements that replace the objective. Agent-chosen screens are provisional search policies, not contest rules; state their basis and revise them prospectively when they exclude useful comparisons. Do not retrospectively change a frozen delivery rule from confirmation feedback.

If score terms are missing, preserve raw components and tradeoff candidates, label proxy choices provisional, and identify what could reverse selection. A small gain may be real; a quality/runtime tradeoff with unknown score parameters cannot establish a net loss. Resolve consequential measurement noise using applicable resources.

## Confirm and Deliver

When stopping for a stated reason, freeze finalist artifacts and the delivery rule before independent confirmation. Keep final tests out of tuning. Verify selected validity, resource checks and package bytes. Report any check that a concrete blocker or actual resource limit prevents.

Deliver runnable artifacts, baseline/candidate metrics with provenance, real changes, cost, reproduction commands and remaining uncertainty. Include the candidate archive summary, repeated-change checks, route switches and compact iteration trace: measured result -> feedback decision -> actual successor/change -> new result or stated stop. Mark unexecuted follow-ups as pending, never as completed progress. If nothing improved, report that outcome with executed alternatives or the concrete blocker. Official submission/upload requires explicit user authorization.

## Adapter Routing

- Fixed-timeslot C++: [adapter usage](references/fixed-timeslot.md).
- Unweighted regression/binary CSV predictions: the needed section of [prediction tools](references/data-model.md); establish training/leakage/resource provenance separately.
- Other families: verify a task-specific interface, objective and validity path before costly search.
