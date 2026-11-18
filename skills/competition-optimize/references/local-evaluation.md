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

Fix the outer evaluation boundary before fitting a residual correction, blend, calibrator or stack. For each outer fold, fit the second layer using only its outer training partition, including the predictions or residual targets it learns from. When it needs out-of-fold (OOF) inputs, generate them by inner cross-fitting within that partition or reuse cached inputs with that verified provenance. The ordinary OOF table for all outer folds does not supply those inputs: predictions in other folds may come from base models trained on the current held-out labels. A second split of that table, including a split of `prediction - target` residuals, does not remove the dependence. Compare the learned rule with its fixed control under the same outer boundary.

Trace actual fit rows and how each cached input was produced. If a decision depends on a label perturbation check, hold the split, features and seeds fixed, change only the held-out labels, and exercise the actual fit and prediction path, regenerating the upstream artifacts whose dependence is in question. Compare predictions before scoring against the changed labels. A changed prediction exposes dependence; comparing frozen predictions with each other does not test how they were produced. See [training path checks](tabular-training.md#verify-supervised-preprocessing-information-flow).

Without a verified boundary, use cached predictions for descriptive diagnostics such as per-case losses, residual cross-moments and fixed-rule recomposition. A rule chosen using those labels and scored against them is an in-sample sensitivity result. Report the scope, and do not use it as a held-out gain or loss for candidate selection.

Zero new fits is a cost observation. Saved predictions can support a matched evaluation of a fixed rule only when all upstream fitting and rule selection excluded the scored-fold labels. A replay on cached artifacts or a small fixture can reveal a detached feature, an algebraic limitation or sensitivity in those inputs; it cannot tell what a changed training pipeline would predict after refitting. A learned stage whose dependencies changed needs its own fold-local evidence before its performance guides selection.

For a saved tabular pair, pass both `--baseline-fit BASE_RUN/fit.json` and `--candidate-fit CAND_RUN/fit.json` to `analyze_prediction_errors.py` along with the usual result and truth inputs. `fold_comparison` checks prediction identity and matching fold membership and reports the actual validation fold scores and win counts. An ID-ordered block is not a fold. Fold dispersion is descriptive; it does not measure new-row uncertainty or replace a declared paired decision rule.

`fold_comparison.pooled_oof_second_layer_boundary` shows which scored-fold labels were in the training sets of the OOF producers serving the other rows. `held_out_label_overlap` identifies a dependency if those residuals are reused to fit a second layer. It does not invalidate the original OOF. A zero-overlap result checks this specific dependency, not every preprocessing or selection step. When an affected calculation has already been reported, keep its exploratory values but withdraw held-out and route-closing claims.

When recording an unmanaged prediction CSV as scored development evidence, `candidate_archive.py record --prediction-boundary` needs a short citation to the actual fold/protocol and fit/selection evidence. This records the review, not a machine proof. Use `--role diagnostic --parent CONTROL --descriptive` when the boundary is missing or the output intentionally uses validation feedback. Unmanaged prediction diagnostics without a boundary citation default to descriptive. This keeps the observation and cost, but it may only motivate a new test; it cannot support scoped learning, selection or route closure. If a defect is established after acceptance, append `candidate_archive.py invalidate-score` with the original result hash and an evidence file; select `--scope predictions` when the defect follows the prediction bytes through rescoring. If the result supports an active interpretation, also correct or withdraw that exact correction key in the current receipt. Preserve historical records and limit the correction to observed dependencies. A parent ID can denote a comparison or idea without implying that its predictions were reused.

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

Before additional diagnostic training, state which pending choice each plausible outcome changes. Choose the smallest matched observation that can resolve it, reusing artifacts with matching computational identities. To isolate partition sensitivity, hold training size, seed schedule and the procedure fixed. Comparing three-fold with ten-fold OOF changes training size and fold membership, and may also change seeds. Compare methods within each matched protocol; the difference across protocols cannot identify which change mattered and is not a primary improvement. A protocol-only re-fit measures the same mechanism under new conditions. Charge its actual cost. Complete matched pairs before accumulating unmatched baseline runs. Predeclare any extension or stopping rule before observing results; honor an already-frozen plan or explicitly stop it, never rewrite it in place.

Repeated estimator seeds on fixed fit/validation IDs probe training randomness conditional on those rows and that partition. Repeated partitions of a fixed development sample probe variability over the tested partitions. Neither measures uncertainty from drawing a new dataset or undoes adaptive reuse of those rows. An unresolved ranking leaves that comparison open, not the entire mechanism family disproved.

A spread among ten-fold partitions at the same training size does not bound the partition component of a three-fold to ten-fold contrast. Averaging predictions from saved seeds is another intervention; its old-fold gain cannot be subtracted to isolate a training-size effect. Treat scores of combinations selected after looking at the same OOF labels as exploratory. Score them with the existing metric interface. A per-row OOF score estimates the scored fold-model procedure, not the error of a different full-data fit or a many-model delivery average.

An individual model's seed or partition spread is not a threshold for a paired improvement. Compute one `C - B` per matched candidate-control repetition, pair seeds and folds as declared, and report the resulting deltas and their scope. `Var(C-B)=Var(C)+Var(B)-2Cov(C,B)`; without the covariance, marginal variation does not identify contrast uncertainty. For example, `B=X` and `C=X+delta` can each vary widely while their difference is constant. Recover the quoted statistic's estimator, matching and population before using it to decide adoption or further investment. A number in an old source comment is a retrieval lead, not an automatically applicable gate.

The same matching requirement applies to a valid paired standard error: one candidate-control pair's uncertainty is not another pair's rejection threshold. A range collected from past pairwise comparisons is not a universal noise floor. Keep the current contrast's uncertainty unknown until its own matched evidence is available; that does not bar a reasoned prototype.

When a few rows dominate a score delta, report their contribution and how much the ranking depends on them. For squared error, use the sum of paired control-minus-candidate squared errors on those rows divided by the same sum on all evaluated rows; report the signed totals and avoid an unstable share when the denominator is near zero. Do not transfer that share from a family-mean contrast to a single model's gate or call it an additive share of RMSE. The same rows recurring under overlapping repartitions establish sensitivity on those development observations, not independent evidence of incorrect labels, irreducible error or the absence of a feature-based remedy. Keep those causal explanations as hypotheses unless task/source evidence supports them. An attempted rule's failure applies to that rule; it does not justify removing hard rows, revising a frozen delivery condition after confirmation, or declaring a whole mechanism family impossible. Reuse the existing decomposition before buying more fits.

### Freeze a Paired Eligibility Rule

When a decision to adopt a candidate depends on more matched evidence, define every hard condition before scoring the new pairs. Give each condition a statistic, comparison operator and numeric threshold. Retrieve and document the basis of a threshold before freezing it. If a requirement such as "outside the old dispersion" has no recoverable definition and scope, leave adoption unresolved; a win count or a newly computed standard error cannot substitute for it. This rule does not impose any default win count, margin or significance test.

Use the [paired plan in the candidate archive](iteration-trace.md#freeze-a-measurement-plan-for-eligibility). It binds the challenger to its primary development comparison and records any matched auxiliary protocols and reused controls. `measure-status` computes each frozen condition; a qualified decision requires all to pass. A raw best, an unresolved plan, and an eligible candidate are separate states. Passing a development eligibility rule still does not establish independent confirmation or authorize preparation outside the task's delivery scope.

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

Removing the rows most favorable to a candidate measures adversarial deletion sensitivity of fixed predictions. It changes the evaluated population and does not estimate sampling uncertainty, prove a noise floor, or set a universal minimum effect size. Report concentration alongside pooled and per-fold results; keep a task-specific promotion decision separate from the decision to prototype a mechanism. When a locally invented gate has blocked work through an unsupported implication, withdraw it prospectively and preserve the old decisions as history.

### Worked Example: Public Up, Local Down

Suppose an authorized submission improves the public score while the same candidate regresses in the matched local comparison. Keep both observations and the current local selection basis while investigating:

| Finding | Action and effect on selection |
| --- | --- |
| The local scorer, output ID alignment or executed inference path is wrong | Fix the responsible layer, retain the old identity and establish the necessary parent/candidate comparisons under the corrected boundary; do not update only the candidate's favorable score. |
| Official facts independently support a different test population or information boundary | Record that basis before seeing revised rankings, then repair the affected protocol or propose a mechanism for the supported gap. Do not choose folds by how well they reproduce the public ordering. |
| Only this public delta is known; its cause remains unresolved | Retain uncertainty and continue locally grounded work. The delta alone does not establish promotion or justify another sequence of public-score tuning. |

A historical private-board rank helps discover a source; it does not validate the current candidate's public delta. Repeatedly taking the best local development result also adapts to that set, so moving all selection locally does not create independent confirmation.

If a frozen finalist's confirmation errors reveal failures on late-arriving entities and those errors guide a feature or selector edit, the revised method has used that confirmation feedback for development. Preserve the original confirmation records and note the exposure; do not relabel the new method's evaluation on the same cases as independent. Follow the actual delivery rule, obtain fresh independent evidence when required and feasible, or report that confirmation is unavailable. The example imposes no new submission count, significance threshold or default extra training campaign.
