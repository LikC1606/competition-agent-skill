---
name: competition-optimize
description: Research strong competition solutions, build trustworthy local evaluation, and implement evidence-based mechanism improvements against the declared objective, including resumable unattended campaigns. Use when asked to build or improve a contest entry, sustain automatic optimization, compare solution approaches, or understand a high-scoring method.
---

# Competition Optimize

For an implementation or optimization request, deliver executed candidates and measured comparisons. Reading, plans and experiment records alone do not complete it. For a request to understand a strong solution, explain its reasoning and interacting mechanisms first. Respect research-only scope. The task adapter supplies the interface, validity checks and objective; optimize that objective in its declared direction.

Choose work by the missing premise: discover a stronger capability, repair an unreliable comparison, implement a reasoned mechanism, or resolve a consequential uncertainty. Search and local evaluation shape the strategy throughout the run. Public leaderboard movement is an observation to explain, not the optimization target.

## Establish or Recover the Task

Read the rules, current executed source/configuration and relevant successful or failed history. Fix the candidate interface, hard rules, metric/direction and development/confirmation protocol before execution. Establish [credible local evaluation](references/local-evaluation.md): scoring fidelity, representative cases, leakage-free information boundaries and comparisons that can distinguish meaningful mechanisms. A runnable scorer or stable hash alone does not establish that quality. Reuse a credible baseline and evaluator only while their identities and dependencies match. Preserve unknown score terms. Keep artifacts in an isolated run directory and record enough facts to reproduce them; do not require a new template when existing records suffice.

Recover unfinished work before rerunning it. A completed experiment without an archive entry calls for artifact reconciliation, not another execution. Use [adapter-contract.md](references/adapter-contract.md) when establishing/changing evaluation and [decision-loop.md](references/decision-loop.md) for interrupted or ambiguous records. Missing decisive data or rules can block dependent execution; continue independent preparation.

Start repeated-trial decisions with `scripts/candidate_archive.py brief`. Inspect the selected code and cited feedback, including open opportunities and unfinished proposals. The latest or highest-scoring candidate is not always the right parent. `trace --proposal-id ID` retrieves exact omitted details. Different predictions from unchanged code/recipe are repeated measurements of one implementation, not new implementations. A failed, unscored or unresolved successor does not close its parent's opportunity.

## Choose the Next Useful Action

After recovery, route the current decision before proposing another implementation. Reuse settled task facts and evidence; this is not a checklist to repeat each turn. Execution repair and frozen measurement obligations retain priority in driver-managed runs.

| Missing premise or new evidence | Action and return condition |
| --- | --- |
| Scoring, information boundaries or workload coverage cannot support this comparison | Repair the specific [local evaluation defect](references/local-evaluation.md), separating systematic bias from random variation. Preserve old identities and reassess affected controls under one legal protocol. Block unsupported promotion; independent research or prototyping may continue. |
| Public and local results disagree | Investigate scorer/pipeline failures, leakage, distribution and sampling explanations. Return with a task-supported evaluation correction or mechanism proposal; without a cause, retain uncertainty and the local selection basis. Do not fit folds, constants or weights to public rankings. |
| The initial route is unformed, an applicable strong solution may change it, or proposed work is only adjacent settings | Use [targeted source research](references/competition-research.md) and task reasoning to identify a missing capability and its prerequisites. Implement when the remaining uncertainty is whether that understood mechanism transfers. |
| A mechanism is understood but its ranking or a necessary premise remains unclear | Reuse artifacts, inspect a counterexample, or run the smallest diagnostic/paired comparison that can change the choice. Mechanism probes do not replace representative ranking evidence. |
| A complete, affordable mechanism and usable comparison are ready | Propose and execute it. A small targeted change can qualify; its capability or behavior must explain why it should help. |

Use [decision-loop.md](references/decision-loop.md#route-the-current-decision) for exact recovery and return conditions. Research is not reserved for exhausted ideas, and more repetitions cannot fix a systematically biased evaluator.

## Derive the Mechanism

At initial formulation, after consequential new evidence, or when progress becomes adjacent patches, reason from the task independently of the incumbent. Identify binding constraints, available information, useful representations, the true cost baseline and scoring timescale. Compare the solution you would build from scratch with what the current code actually implements. An evidence-supported local refinement need not repeat this analysis every round.

Actively use [competition research](references/competition-research.md) to find strong applicable methods and evaluation pitfalls before investing in a formulation, and revisit it when a specific unresolved mechanism warrants another search. Do not wait for supplied URLs. Reuse relevant sources already read and move to implementation once the mechanism and prerequisites are understood.

For Kaggle-specific discovery, original posts/comments and matched notebook versions, use the optional [source reader](references/kaggle-sources.md). It saves source snapshots and visible reading limits for the existing research notes and proposal basis. [Ground decision-changing source claims](references/competition-research.md#ground-decision-changing-claims) in an inspected passage, cell or function; separate the author's claim, inspected implementation and your own deduction. Snapshot integrity alone does not verify an attribution or transfer.

When studying a strong solution, reconstruct why its representation, construction, internal pricing, maintenance and compute allocation work together. Identify missing capabilities and coupled components before transplantation. Read [strategy-design.md](references/strategy-design.md) and, when useful, its [source patterns](references/source-patterns.md). Before paying for execution, [check the claimed capability against equivalence and the actual pipeline](references/strategy-design.md#check-equivalence-before-execution). A coherent structural hypothesis can justify a prototype before measured gain exists; promotion still requires results.

For entries that run an LLM or agent, use [the evidence-to-mechanism guide](references/llm-agent-competitions.md#choose-the-layer-from-evidence) to distinguish supervision, answer selection, inference limits and interaction failures before choosing another training variant. Fixed generated answers can support [vote replay](references/inference-vote-replay.md); its report informs a proposal, not candidate promotion.

Accept user ideas in their intended form. Distinguish discussion, a suggestion, an explicit test/priority request and a hard requirement. In active optimization, turn a feasible idea into an implementation decision; honor explicit test priorities within the rules. Retain its origin and distinguish the tested interpretation from the original idea. See [user-idea handling](references/score-search.md#turn-user-ideas-into-experiments).

Once a mechanism is ready, execute this loop, returning to the routing above when a prerequisite changes:

1. **Propose.** Connect the basis → limitation/opportunity → changed capability → predicted local observation → useful comparison in the existing proposal. Task reasoning, an inspected source or development evidence can supply the basis; prior measured gain is not required. Choose a parent or independent construction, include necessary coupled parts, a plausible failure/counterexample, differences from rejected attempts and cost. Say how materially different outcomes change the next action; skip optional diagnostics that cannot change selection, implementation or delivery. Preserve required checks and explicit user test requests. Read the [proposal gate](references/score-search.md#efficient-proposal-and-quality-gate) when needed.
2. **Implement.** Inspect the actual target code and implement the complete mechanism. When warranted, change the representation, algorithm, model or training pipeline. A route name does not turn adjacent settings into a new method. For construction without inherited code, use [`construction_mode=independent`](references/iteration-trace.md#declare-an-independent-construction), with comparison controls retained and `code_targets=[]`.
3. **Evaluate.** Compile/train/execute at matched fidelity. Preserve source/recipe identities, commands, results, validity scope and costs. Compare with both parent and incumbent. Reduced fidelity, a diagnostic and independent confirmation answer different questions. Separate invalid or incomplete runs from valid low scores; inspect machine interference before consequential timing.
4. **Interpret and route.** If the predicted mechanism did not occur, inspect execution and missing coupled parts. If it occurred without objective gain, revisit its transfer assumptions or choose another capability. If ordering alone is unresolved, obtain decision-changing matched evidence. Record gain/regressions and prediction status; these explanations remain provisional. Decide promotion separately from further investment.
5. **Continue.** Execute the selected follow-up: source research, evaluation repair, a consequential diagnostic or the next complete mechanism. Reuse the existing proposal/feedback chain rather than starting generic research again. Use [plateau-recovery.md](references/plateau-recovery.md) when the formulation stalls. A completed batch, weak score or list of ideas does not complete open-ended optimization.

Default to agent-developed implementation changes. Do not schedule grid/random/Bayesian searches, neighboring-value sweeps or seed hunting unless the user explicitly requests parameter tuning. Settings may change as part of an implemented mechanism. Do not impose default total time, cost, candidate or round limits. Record real consumption, failures, repairs and repetitions; honor actual competition/resource constraints and the user's current limits. Later limit changes apply prospectively without erasing earlier costs.

## Retrieve Only the Evidence Needed Now

Read the relevant section of [iteration-trace.md](references/iteration-trace.md) when a decision uses one of these capabilities. Exposure never counts as execution or evidence of value.

| Current need | Evidence / section |
| --- | --- |
| Select code, recover a proposal, attach its actual outcome | `brief`, `trace`; **Retrieve Evidence**, **Record One Actionable Proposal**, **Attach the Measured Outcome** |
| Revisit an unresolved lower-scoring branch | `review_frontier`; inspect feedback and attempted successors |
| Explain or combine complementary behavior | `complementary_evidence`; **Retrieve Complementary Case Evidence**; case wins are clues, not a blend score |
| Trade quality for measured candidate resources | `resource_tradeoffs`; **Retrieve Measured Resource Tradeoffs**; missing profiles remain unknown |
| Test an intentional ablation/counterfactual | `role=diagnostic`; **Diagnostics and Contenders**; diagnostics do not rank contenders |
| Learn from actual completed attempts | `trial_history`; **Resume and Deliver the Actual Chain**; inspect code/result identities, not only explanations |
| Reuse a conditional conclusion | `scoped_learning`, `learning_from`; **Carry Conditional Learning into the Next Construction**; agent interpretation remains source-bound |
| Check a suspected omitted mechanism | **Review the Actual Implementation**; missing implementation has not been tested by its score |
| Resolve same-contract ordering reversals | `repeat_conflict`; **Retrieve Evidence for the Next Implementation**; predeclare a paired `measure-plan`, resume slots, then `measure-decide` or `measure-stop` |

Select optional evidence because it can change the next decision, not to fill a checklist. Keep required identifiers, paths and sealed report fields intact. Retrieve exact evidence when summaries are insufficient. Do not infer candidate latency from total evaluation time or infer method failure from broken execution.

## Unattended Continuation

Use [unattended-campaign.md](references/unattended-campaign.md) when the user requests durable autonomous continuation, after verifying the adapter and development archive. A conversation turn alone does not guarantee a long campaign. The runner preserves launch intent, process identity, evidence and checkpoints; reuse its recovery path.

Inside a driver-managed invocation, finish a useful archived implementation/evaluation step and return the structured receipt. When a specific research or evaluation prerequisite prevents meaningful execution, persist the inspected finding, affected decision and concrete next action in existing notes/card and cite them in the receipt. This does not count as an executed implementation or reset stagnation; do not repeat generic research after the prerequisite is understood. The outer loop performs the follow-up; a checkpoint does not end the campaign. Treat complete/blocked receipts as advisory unless the configured verifier confirms completion. Stop for a user stop, an applicable resource constraint, verified completion or an observed blocker that cannot be resolved.

Use the supplied development evidence packet. Failed/invalid/unscored runs enter repair; diagnose code, data, environment or measurement without treating absent scores as method evidence. `comparison_continuity`/`comparison_recovery` identify contracts without a different measured implementation: measure a trusted reference and candidate under one legal common development protocol. Preserve confirmation isolation. Use fixed paired measurement plans for consequential repeat conflicts; unchanged code may fill declared measurement slots but is not a new implementation. Never choose lucky repeats or replace a frozen rule with an informal average.

## Select, Confirm and Deliver

Select by the actual objective under the declared local protocol. Treat public leaderboard disagreement as a question about evaluation or transfer; investigate it without tuning constants, folds or shortlist rules to public-score fluctuations. Do not invent universal minimum gains, slowdowns, significance gates or output-equivalence requirements. Provisional screens must not replace contest rules. With unknown score terms, preserve components and tradeoff candidates, label proxy choices provisional and identify what could reverse selection. Local repetitions cannot reveal missing official terms.

At a stated stopping condition, freeze finalist artifacts and the delivery rule **before** independent confirmation. Keep confirmation/final-test feedback out of development and never change the frozen rule retrospectively. [Track prior feedback exposure](references/local-evaluation.md#track-feedback-already-used-for-selection) in existing task notes: repeated OOF selection and repartitioning already-used rows remain development evidence. Verify validity, applicable resource checks and final package bytes. Deliver runnable artifacts, baseline/candidate metrics and provenance, actual changes, costs, reproduction commands and the measured result → feedback → executed successor chain. Mark unfinished follow-ups and unperformed checks accurately. Report no improvement when that is the outcome. Official submission/upload requires explicit authorization.

When relocating archived evidence, use the explicit mapping and byte checks in [evidence-portability.md](references/evidence-portability.md); preserve original archive/seal identities.

## Task Adapters

- Fixed-timeslot C++: [fixed-timeslot.md](references/fixed-timeslot.md), including workload completeness, static-rule coverage and packaging boundaries.
- Scalar regression/binary CSV scoring: the required section of [data-model.md](references/data-model.md). Prediction scoring alone does not establish training or leakage provenance.
- Numeric tabular fitting, fold/OOF evidence and frozen model delivery: [tabular-training.md](references/tabular-training.md). Its supported workflow is narrower than general Kaggle automation.
- LLM training, generation and multi-turn agents: [llm-agent-competitions.md](references/llm-agent-competitions.md) for conditional mechanisms, task-specific adapter requirements and trajectory replay limits. This is guidance; executable evaluation remains task-specific.
- Group/time partition checks: [validation-split.md](references/validation-split.md); audit declarations and actual fitting separately.
- Other task families: [task-playbooks.md](references/task-playbooks.md); establish a task-specific objective, interface and validity path before costly search.
