---
name: competition-optimize
description: Implement and evaluate substantive competition solutions, research task-specific methods, and iterate toward a higher declared score. Use when given contest rules or asked to build or improve an entry with a repeatable evaluation path.
---

# Competition Optimize

For an optimization request, deliver implemented, executed candidates and measured comparisons in the current session. Reading, planning, route names, and experiment records alone do not complete that request. Respect an explicit research-only request. A task adapter supplies the interface, validity checks and objective; optimize its declared metric in the correct direction.

## Start or Resume Quickly

Read the task/rules, current solution and latest relevant results. Recover unfinished work before rerunning. Reuse a verified evaluator and credible baseline with matching dependencies. Read [adapter requirements](references/adapter-contract.md) when establishing or changing the evaluation path; use [resume details](references/decision-loop.md) for interrupted, stale or ambiguous records.

Fix the interface, hard rules, metric/direction, development protocol and confirmation reserve before candidate execution. Record unknown score terms. Keep candidate artifacts and results in an isolated run directory. Use existing records or a compact contract/ledger; document facts needed for reproduction, not every possible template field before doing useful work. Missing decisive rules/data may block execution; ask for that specific input and complete independent setup.

## Bound Work Without Repeated Approval

Honor explicit user time/compute/trial limits at their stated scope and retain all consumed work. Do not reset an exhausted user cap. When none applies, start one default work round: at most **45 minutes of total wall time and eight tested candidate configurations**, stopping at either limit. Reserve measured confirmation/packaging cost first; research, implementation, diagnostics and repairs use this time. New baselines, failed implementations and repairs count as configurations; unchanged verification consumes time/compute.

This default is per user work request, not a lifetime allowance for the task. After delivery, a new request to continue permits another default round if no explicit user cap prevents it; retain the incumbent, history and cumulative costs. Never renew rounds automatically. Distinguish user limits from old skill defaults or agent estimates in recovered records. Requesting optimization already authorizes ordinary local research, implementation and evaluation within these bounds; do not ask permission merely to start those actions.

## Execute a Meaningful Alternative

1. **Identify the limiting mechanism.** Prioritize hard feasibility risks, then objective headroom. Compare the strongest affordable alternative using task structure, measurements and targeted original sources. Read the relevant [task-family guidance](references/task-playbooks.md) or [search reference](references/score-search.md) only when it helps this choice.
2. **Implement a complete test.** For substantive score improvement, favor a different algorithm/representation, model/training pipeline or policy before another series of adjacent settings, caches or cleanup passes. Couple required components so the prototype actually tests that method. A route label does not make a local patch a different method. Retain a supported refinement when constraints or credible bounds favor it; explain that choice with evidence. Do not require identical outputs to the incumbent unless the task/user requires them.
3. **Run it.** Record a short hypothesis, parent, comparison protocol and planned cost, then compile/train/execute the candidate. Preserve source/configuration, commands, results and validity evidence. Diagnose defects and make a bounded repair when worthwhile. A prototype must have an actual valid evaluation before its method can be judged; reduced fidelity cannot establish a full-score winner.
4. **Choose the next implementation from the result.** Compare the complete objective at matched fidelity. Keep the incumbent and useful alternatives. Separate candidate promotion from route investment; use relevant [failure evidence](references/score-search.md#decide-whether-to-repair-deepen-or-retire) and [comparison lessons](references/score-search.md#learn-from-evaluated-pairs) when a result changes the next test. After a weak result, execute the next worthwhile alternative if it fits outside the reserve; one patch or a list of ideas is not a reason to end the round. Do not spend the entire round documenting hypotheses or polishing the same saturated mechanism.

## Select by the Actual Objective

Enforce competition/user hard limits. Do not invent universal minimum gains, maximum slowdowns, statistical-significance gates or output-equivalence requirements that replace the objective. Agent-chosen screens are provisional search policies, not contest rules; state their basis and revise them prospectively when they exclude useful comparisons. Do not retrospectively change a frozen delivery rule from confirmation feedback.

If score terms are missing, preserve raw components and tradeoff candidates, label proxy choices provisional, and identify what could reverse selection. A small gain may be real; a quality/runtime tradeoff with unknown score parameters cannot establish a net loss. Resolve consequential measurement noise within budget.

## Confirm and Deliver

Freeze finalist artifacts and the delivery rule before independent confirmation. Keep final tests out of tuning. Verify selected validity, resource checks and package bytes. Stop when no useful candidate fits outside the reserve.

Deliver runnable artifacts, baseline/candidate metrics with provenance, real changes, cost, reproduction commands and remaining uncertainty. If nothing improved, report that outcome with executed alternatives or the concrete blocker; do not rename a plan as progress. Official submission/upload requires explicit user authorization.

## Adapter Routing

- Fixed-timeslot C++: [adapter usage](references/fixed-timeslot.md).
- Unweighted regression/binary CSV predictions: the needed section of [prediction tools](references/data-model.md); establish training/leakage/resource provenance separately.
- Other families: verify a task-specific interface, objective and validity path before costly search.
