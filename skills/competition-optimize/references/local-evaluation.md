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

Apply that boundary separately at each selection level. Inner CV used to choose a penalty or model needs its own training-only centering, imputation, scaling and supervised encoding, unless the protocol explicitly justifies an invariant transformation. Fitting the transform on all outer-training rows before the inner split exposes inner-validation information. This can affect inner selection while outer OOF remains independent if outer-validation labels were never used. Trace actual fit inputs at each level; do not infer outer leakage solely from an inner defect, or silently change sealed historical evaluations.

Biased inner selection does not by itself make the outer OOF estimate optimistic: a strictly held-out outer fold evaluates the procedure that includes that selection, potentially showing its poor choices. Claim outer selection bias only when outer evidence was also used for selection; repeated development selection is a separate exposure described below.

For a relational feature such as group history or target encoding, check its information availability before fitting: when official test features are accessible, compare train/test entity overlap with train/validation overlap under the proposed split. A validation entity with labelled training peers is a different inference case from an entirely new test entity. Zero test overlap can invalidate that use of historical labels without any model run; distinguish it from feature-only group composition that may remain available within an unlabelled test batch. Record the observed boundary and derive the split from it, rather than assuming every recurring identifier requires the same holdout.

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

When a few rows dominate a score delta, report their contribution and how much the ranking depends on them. The same rows recurring under overlapping repartitions establish sensitivity on those development observations, not independent evidence of incorrect labels, irreducible error or the absence of a feature-based remedy. Keep those causal explanations as hypotheses unless task/source evidence supports them. An attempted rule's failure applies to that rule; it does not justify removing hard rows, revising a frozen delivery condition after confirmation, or declaring a whole mechanism family impossible. Reuse the existing decomposition before buying more fits.

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

## Worked Example: Future New Entities with Delayed Labels

Suppose the official task predicts future events for entities absent from fitting data, and labels arrive after their event times. An existing random row split mixes entities and uses labels that were unavailable at the prediction origin. This is a hypothetical protocol defect; no scores are assumed. If the actual task instead predicts future behavior of known entities, derive its boundary from that scenario rather than imposing this example's entity holdout.

At a fold origin of April 1, a training event on March 25 whose label arrives April 3 cannot train the April 1 model. A development row with a new entity ID still violates the protocol if its features use future aggregates. For this example, require every training event and label to be available strictly before the first validation event, with any additional gap justified by the task horizon. Derive explicit `train_ids`/`validation_ids` for each origin, disjoint entity groups, and `expected_oof_ids` excluding declared temporal warmup rows. A fold label alone cannot reconstruct all training prefixes.

For supported numeric regression/binary tasks, use [the existing trainer](tabular-training.md#freeze-the-fold-protocol-before-comparing-candidates) with `split.kind=group_time`, `group_column`, event/availability columns and the justified gap. Keep learned preprocessing inside the estimator pipeline; each fold fits only its training rows and predicts its held-out rows. Check upstream feature construction against the same availability boundary. [Partition auditing](validation-split.md#evidence-and-limits) checks declarations separately from actual fitting. The repository's [training pilot](../../../examples/tabular_training_pilot.py) demonstrates fitting, OOF and frozen delivery; its dataset does not establish this task's group/time semantics.

Record the official task basis, offending dependency and correction before examining revised rankings. Preserve the old evaluation identity and scope each consequence:

| Evidence | After correcting this split/information defect |
| --- | --- |
| Old OOF, models and their rankings | Keep as historical evidence under the old protocol; they cannot justify promotion under the corrected one. Refit affected candidates needed for the current choice under a common new identity. |
| Target encoders, learned selectors or cached features using forbidden rows/information | Rebuild the affected dependency and descendants; changing only the final scoring call cannot remove fitting leakage. |
| Unchanged raw data, permitted deterministic features, source findings and unaffected correctness checks | Reuse while their inputs and assumptions still match. Do not rerun all history solely because a new split exists. |
| Pure scorer/output-alignment defect, with fitting boundaries otherwise valid | Reuse verified predictions and rescore/re-align when that repairs the actual defect; refitting is not automatically required. |

The timestamp comparison can establish an information violation without training. A mechanism probe can then check that fitting receives the permitted rows. Representative development comparisons under the repaired protocol support ranking; more seeds on the old protocol cannot supply that evidence. Freeze finalists and their rule before a separate later confirmation with the task's required entity boundary.

## Keep Public Feedback from Becoming the Objective

Public leaderboard scores describe a reused visible portion of evaluation, often with unknown sampling variation. Repeatedly choosing prompts, seeds, blend weights or preprocessing by tiny public deltas adapts to that set even without direct access to labels. A small public gain alone cannot establish a generalizable improvement or validate a mechanism.

Before an authorized submission, retain the candidate's task/source basis, predicted effect and comparable local evidence. If public and local outcomes disagree, hold the local selection basis while investigating competing explanations: metric conventions, preprocessing, coverage, runtime/failure treatment, leakage, plausible distribution differences and sampling noise. Targeted organizer clarifications or validation discussions may resolve a missing fact. A single mismatch does not establish which explanation is correct.

Return to the main loop with either an independently justified task/data/implementation reason to repair evaluation, or a mechanism addressing a falsifiable transfer hypothesis. Record the revision's reason before examining its new rankings, preserve the old identity and affected results, and reassess invalidated comparisons. Without such evidence, retain uncertainty and continue locally grounded work. Do not choose new folds or scoring weights merely to reproduce leaderboard rankings. Keep platform feedback separate from local measurements; submission limits do not authorize submissions.

The development set also receives adaptive feedback over many iterations. Freeze finalist artifacts and the selection rule before independent confirmation; if confirmation errors guide another edit, they become development evidence. Broader justified development coverage can improve diagnosis, but cannot turn repeatedly inspected cases into fresh confirmation. See [search/confirmation separation](score-search.md#keep-search-and-confirmation-separate).

### Track Feedback Already Used for Selection

When establishing or recovering a task, retain a short account in existing task notes of which labels, scores, residuals, public feedback or confirmation results have influenced choices, and which evidence remains untouched. Recover known exposure from actual history; leave unknown history explicit. Update this account when its status changes, not as a new per-trial form. Archive counts and hashes can help recover history but cannot certify what the agent or researcher has already seen.

| Available evidence | Legitimate interpretation and action |
| --- | --- |
| Fixed-fold OOF repeatedly used to choose models or features | Matched development evidence; fold-local fitting prevents that form of training leakage, but does not remove adaptive selection optimism |
| New folds, seeds or a holdout drawn from already-used development rows | Another development comparison; changing the partition or seed does not make those rows fresh independent confirmation |
| Historical confirmation inspected by an earlier run or researcher | Preserve its historical scope and record known exposure. Keep its feedback out of subsequent development; do not claim new independent confirmation on the same cases |
| Genuinely untouched units under the task's intended sampling boundary | Can support independent confirmation of artifacts and a decision rule frozen before observing that feedback |
| No independent evidence available within the permitted resources | Continue justified development if authorized, label selection and gains as development-only, and report the unresolved generalization question |

Use existing per-fold/regime losses or cached predictions to inspect concentrated gains and regressions when that can change the next action. Neither repeated OOF improvements nor the absence of public submissions establishes generalization. More seeds, nested CV, fresh data collection or another training campaign are not automatic requirements: choose additional evidence only for a consequential unresolved decision and within actual constraints. Correct a split for a task-based information defect, preserving identities and affected controls; do not redesign it to favor the current candidate or call repartitioning an exposure reset.

### Worked Example: Public Up, Local Down

Suppose an authorized submission improves the public score while the same candidate regresses in the matched local comparison. Keep both observations and the current local selection basis while investigating:

| Finding | Action and effect on selection |
| --- | --- |
| The local scorer, output ID alignment or executed inference path is wrong | Fix the responsible layer, retain the old identity and establish the necessary parent/candidate comparisons under the corrected boundary; do not update only the candidate's favorable score. |
| Official facts independently support a different test population or information boundary | Record that basis before seeing revised rankings, then repair the affected protocol or propose a mechanism for the supported gap. Do not choose folds by how well they reproduce the public ordering. |
| Only this public delta is known; its cause remains unresolved | Retain uncertainty and continue locally grounded work. The delta alone does not establish promotion or justify another sequence of public-score tuning. |

A historical private-board rank helps discover a source; it does not validate the current candidate's public delta. Repeatedly taking the best local development result also adapts to that set, so moving all selection locally does not create independent confirmation.

If a frozen finalist's confirmation errors reveal failures on late-arriving entities and those errors guide a feature or selector edit, the revised method has used that confirmation feedback for development. Preserve the original confirmation records and note the exposure; do not relabel the new method's evaluation on the same cases as independent. Follow the actual delivery rule, obtain fresh independent evidence when required and feasible, or report that confirmation is unavailable. The example imposes no new submission count, significance threshold or default extra training campaign.
