# Build Local Evaluation That Can Guide Search

Use this when establishing evaluation or when local outcomes no longer support credible candidate decisions. A useful evaluator reproduces the scoring boundary and distinguishes methods on cases relevant to the competition. Executability, repeatability and file hashes are necessary evidence properties; they do not establish representativeness or freedom from leakage. Reuse the existing [adapter contract](adapter-contract.md), task notes and result archive.

## Establish What the Score Means

Read official rules, scorer code and organizer clarifications where available. Match the actual prediction/action interface, normalization or answer parsing, metric direction, units, per-case weights and aggregation. Include malformed outputs, missing cases, episode termination, timeouts and all costs charged by the competition. A correct metric applied to the wrong workload or an incomplete episode can still produce a misleading ranking.

Check available known answers and deliberately invalid or degenerate outputs against an independent calculation or official examples. A baseline producing a plausible number is insufficient. Where official terms or hidden-case generation are unavailable, preserve the missing information and label the local estimate's scope rather than inventing an exact simulator. Do not weaken the official score to favor the current implementation.

## Match the Intended Test Conditions

Choose the independent unit and information boundary from the task, then construct the development workload:

| Task property | Consequence for local evaluation |
| --- | --- |
| Evaluation targets previously unseen users, documents or original problems | Hold out those source groups before augmentation or synthetic generation; audit overlap and fitting provenance |
| Future events or delayed labels | Use forward splits and actual label-availability boundaries; respect the permitted information for fitting and prediction |
| Hidden algorithm instances or simulation episodes | Cover relevant sizes, structures, initial states and complete trajectories; match permitted observations and resource limits |
| Deployment limits on LLMs, models or policies | Evaluate the actual parser, retrieval, inference or interaction pipeline, including unfinished workload and failures |
| Different important regimes or a shifted test population | Preserve representative regime-level results and the official aggregation; state uncertainty about unknown prevalence |

Fit label-dependent preprocessing and learned selectors inside training boundaries; any permitted transductive use must be explicit in the task contract. Determine whether test entities are new or already known from the intended inference scenario, rather than forcing a group holdout merely because identifiers recur. Choose groups, folds and case weights for a task-based reason before comparing candidates. Do not pick the split whose scores most flatter a model or best track a few public submissions. A larger random holdout cannot repair a wrong statistical unit, missing regime or information leak.

Distinguish correctness and stress cases from the workload estimating expected competition quality. An adversarial case can expose a real defect without establishing how frequent that defect is. Use existing data and cached outputs first; add cases or repetitions only when the missing coverage or uncertainty can change a decision. High quality does not require a large cross-validation or multi-seed campaign by default.

## Check Whether It Can Distinguish Mechanisms

Keep three evaluation roles distinct; they can reuse infrastructure without pretending to be independent evidence:

| Role | Question answered | Decision it supports |
| --- | --- | --- |
| Correctness or mechanism probe | Does parsing/scoring work, or does the proposed behavior actually occur on a discriminating example? | Repair or advance a prototype; a hand calculation or cached artifact may suffice |
| Representative development comparison | Does the complete method improve the declared objective across relevant conditions under matched resources? | Rank candidates and diagnose regime tradeoffs; a newly chosen favorable slice cannot replace it |
| Independent confirmation | Does the frozen finalist/delivery rule hold on evidence kept out of development? | Deliver under that rule; using its errors to edit consumes its independence |

Use available baseline results, reference outputs and credible distinct methods to ask whether the workload exposes the capability under study. A saturated set of easy cases cannot rank methods whose differences appear only in long contexts, large instances or recovery episodes. Near-equal aggregate scores may hide opposite effects across relevant regimes. More decimal places or repetitions do not resolve a systematic mismatch.

For a proposed gain, connect the changed mechanism to an observable local outcome: which cases, objective components or completion failures should improve, and what could contradict the explanation? Inspect existing artifacts or a hand-worked example before spending on new runs. A structural argument can justify a prototype without an existing measured gain; the argument itself is not a measured result.

Compare candidates under the same evaluation identity, legal information and declared resource protocol. Treat reduced fidelity as diagnostic unless its ranking relation is justified. Use paired cases or seeds when needed to resolve a consequential ranking, retaining every outcome; selecting a lucky repeat does not improve the method. Relevant existing controls and cached predictions can avoid new fitting. Detailed execution rules remain in [score search](score-search.md#spend-evaluation-budget-where-it-changes-decisions).

## Route an Evaluation Problem

Use the specific defect to choose work; a blanket demand for more folds, seeds or runs is not a repair.

| Observed gap | Next action | Exit / evidence to retain |
| --- | --- | --- |
| Official scoring, output handling or charged costs disagree with local behavior | Check a known answer and a failing/degenerate case against the actual boundary; fix the responsible adapter behavior | Corrected behavior and a new evaluation identity where affected; previous scores remain scoped to the old one |
| Wrong independent unit, unavailable information, leakage, missing regime or unrealistic pipeline | Correct the specific split, availability boundary or workload for a task-based reason | State the correction before inspecting revised rankings; reassess needed reference/candidate controls under the same legal protocol |
| Workload cannot expose the capability under study | Inspect a discriminating example or existing trace; add development coverage only when relevant to the intended test conditions | Mechanism evidence plus representative comparison; no silent reweighting toward the candidate's favorable cases |
| Comparable outcomes reverse under stochastic execution | Check whether ordering changes the decision; if so use the existing frozen paired measurement plan | All declared paired outcomes and the fixed decision rule, not a lucky rerun |
| Hidden scoring terms or distribution remain unknown | Preserve components, plausible regimes and tradeoff candidates without fabricating weights or prevalence | An explicit provisional selection and what fact could reverse it; repeated local runs cannot supply unknown official terms |

Only the affected comparison is blocked. Independent source research, code inspection or prototyping may continue. Reuse valid caches and controls; evaluate anew only dependencies invalidated by the correction. Respect sealed task and measurement contracts: a revision must not silently change driver-owned files or fill an old frozen plan with a new protocol. Persist the diagnosis, reused/invalidated evidence and next action in existing notes/card; no separate quality certificate is required.

## Keep Public Feedback from Becoming the Objective

Public leaderboard scores describe a reused visible portion of evaluation, often with unknown sampling variation. Repeatedly choosing prompts, seeds, blend weights or preprocessing by tiny public deltas adapts to that set even without direct access to labels. A small public gain alone cannot establish a generalizable improvement or validate a mechanism.

Before an authorized submission, retain the candidate's task/source basis, predicted effect and comparable local evidence. If public and local outcomes disagree, hold the local selection basis while investigating competing explanations: metric conventions, preprocessing, coverage, runtime/failure treatment, leakage, plausible distribution differences and sampling noise. Targeted organizer clarifications or validation discussions may resolve a missing fact. A single mismatch does not establish which explanation is correct.

Return to the main loop with either an independently justified task/data/implementation reason to repair evaluation, or a mechanism addressing a falsifiable transfer hypothesis. Record the revision's reason before examining its new rankings, preserve the old identity and affected results, and reassess invalidated comparisons. Without such evidence, retain uncertainty and continue locally grounded work. Do not choose new folds or scoring weights merely to reproduce leaderboard rankings. Keep platform feedback separate from local measurements; submission limits do not authorize submissions.

The development set also receives adaptive feedback over many iterations. Freeze finalist artifacts and the selection rule before independent confirmation; if confirmation errors guide another edit, they become development evidence. Broader justified development coverage can improve diagnosis, but cannot turn repeatedly inspected cases into fresh confirmation. See [search/confirmation separation](score-search.md#keep-search-and-confirmation-separate).
