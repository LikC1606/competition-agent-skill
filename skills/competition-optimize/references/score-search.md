# Search for Score Improvements

Read this when selecting experiments after a verified baseline exists. Optimize the contest objective under the remaining budget; choose actions from evidence and unresolved questions.

## Turn Research into Testable Mechanisms

Search using the task family, candidate representation, metric, input scale, resource constraints, and a concrete bottleneck. Prefer relevant original writeups, task documentation, and source code; check the actual evaluator when a reported objective or validity claim matters. Once an executable test is available, spend the next budget on it rather than extending a general literature list. Search again when an observed failure identifies missing knowledge.

Convert useful sources into the hypothesis queue below. Record URL/version, license where reuse matters, prerequisites, and a cheap transfer test. Separate author-reported outcomes, inspected implementation, and local measurements. Historical wins, stars, or votes do not establish transfer. Read only the relevant section of [the task-family guide](task-playbooks.md) for concrete experiment options.

## Diagnose Before Choosing a Trial

Break the baseline down by score component and representative case group. For each weak group, distinguish a poor solution from a measurement or implementation defect. Estimate the available improvement from bounds, small exact solutions, a stronger reference, or a targeted ablation when practical. A low raw metric is not necessarily fixable or heavily weighted in the contest score.

For supported CSV predictions, [paired development error analysis](data-model.md#diagnose-development-errors) can expose concentrated loss and slice regressions using saved predictions. Use its observations to propose a falsifiable mechanism, then evaluate any change on the full declared objective. A slice metric, majority of case wins, or loss concentration is diagnostic evidence; none changes the official aggregation or establishes that the errors can be fixed. Use the corresponding workload/episode diagnostics for algorithm and simulation tasks when available.

Maintain a short hypothesis queue in `research.md`:

| Field | What it must make clear |
| --- | --- |
| Mechanism and target | What changes and which score component or case regime should benefit |
| Parent and evidence | Candidate IDs, source or local result, and the remaining uncertainty |
| Prerequisites | Data, rules, scale, solver behavior, or resources needed for the idea to apply |
| Prediction and rejection test | An observable outcome and the cheapest useful experiment that could contradict it |
| Cost and next decision | Implementation/evaluation cost, failure condition, and whether success justifies a larger trial |

Prefer plausible objective gain per unit of total experiment cost while keeping room for unfamiliar mechanisms. Numeric gain predictions are estimates, not results.

## Select the Next Action

| Evidence or uncertainty | Action | Evidence needed to continue |
| --- | --- | --- |
| Only one family has been tried, with unclear fit | Explore a materially different route | A valid result, resource fit, and promising objective or complementary behavior |
| Low score with an unclear cause | Diagnose using case analysis, a profile, ablation, or small reference solution | A bottleneck or falsifiable explanation that suggests an affordable change |
| A component has a supported improvement mechanism | Refine that component | Matched evaluations that justify another variant or reveal a new testable mechanism |
| A mechanism works but sensitive settings are unresolved | Tune its parameters | Full-fidelity gains that reproduce beyond the screening setup |
| Candidates have compatible, complementary strengths | Combine or select by regime | Improvement in the combined candidate's objective within its resource limits |
| Apparent gain is comparable to measurement variation | Repeat a matched comparison | Enough evidence to resolve the promotion decision |
| Final reserve is all that remains | Confirm the frozen shortlist | Validity and independent objective measurements for delivery |

Diagnostics are experiments too and consume budget. Keep their results separate from candidate ranking. A correctness failure may justify a repair when the mechanism remains promising; an infrastructure failure gives no evidence about algorithm quality. Neither warrants unlimited retries.

## Refine a Measured Component

When the budget supports deeper search, use a targeted ablation, runtime profile, or small reference solution to choose a component worth refining. Within it, test one explanatory mechanism per trial and use prior results to select the next variant. Include representation, solver encoding, search neighborhoods, features, and training signals where the task supports them; parameter changes are only one search action.

An ablation measures the current solution's reliance on a component, not its remaining improvement potential. Combine that evidence with a plausible improvement mechanism and evaluation cost. Keep the official evaluator fixed. An approximation used inside the candidate's search is itself a hypothesis and still needs confirmation on the declared objective.

Reallocate trials to another component or route when gains fail to reproduce, a limiting bound is reached, or remaining variants lack a credible benefit. A promising line need not be abandoned after one failed variant, and a familiar line does not earn extra trials merely because it is easy to edit.

## Explore, Refine, Combine

With enough budget, start with materially different solution families rather than many minor edits to the same baseline. Keep their parent IDs and best validated representatives; one route may excel at a different regime or later combine with another. This is a candidate portfolio and can be executed by one agent sequentially.

After a mechanism works, tune its sensitive parameters with a small sweep or adaptive search. Compare candidates at documented evaluation fidelity. If promising gains from routes can coexist, make a separate combination trial with all parent IDs and an ablation where it changes the decision. Gains need not add; evaluate the combination's objective, runtime, and memory including selection or ensemble overhead. Use ensembling only when the submission format and metric support it.

For model ensembles, inspect complementary validation errors rather than selecting solely by individual rank. Reuse cached predictions only with matching sample IDs, split, preprocessing, model/configuration provenance, and metric. OOF predictions must exclude held-out samples and dependent groups from label-dependent fitting. Fit learned preprocessing within folds unless the contract permits transductive fitting; document any such use of held-out features. Tune combination weights on development evidence and confirm the frozen combination independently. A regime-specific algorithm selector must use features available at inference, not ground-truth outcomes.

For the supported scalar CSV interface, [the blend tool](data-model.md#construct-and-confirm-a-prediction-blend) constructs weighted candidates from compatible development evaluations and reapplies a frozen recipe by member name. Evaluate every blend with the declared metric, count each weight variant as a trial, and include all contributing models' inference cost. Freezing an algorithm selector's thresholds or a simulation policy mixture follows the same principle: selection settings are candidate parameters and cannot be retuned on confirmation evidence.

Reuse intermediates only when their dependencies match. A changed feature pipeline, split, model, or training configuration invalidates affected cached results even if output filenames are unchanged.

## Learn from Evaluated Pairs

Compare an informative candidate with its parent or another matched candidate using code differences, objective deltas, case-level behavior, and cost. Record the observation, the proposed explanation, and the next falsifiable test separately. A model-generated explanation does not establish causality. Use failed predictions to revise or retire hypotheses. Retain lessons in `research.md` with task/metric/constraints, success and failure regimes, and result paths. On a later task, recheck prerequisites and run a transfer test; do not turn a historical lesson into a universal rule.

## Spend Evaluation Budget Where It Changes Decisions

Measure baseline costs and reserve final verification first. Record consumed and remaining time/compute/trials after each batch, including research, evaluator development, diagnostics, retries, training, full runs, and confirmation. Code/configuration variants, including ablations, repairs, and rejected candidates, count against the candidate-trial limit. Respect the contract's budget and the initial default defined in `SKILL.md`; reserve final verification separately.

Use low-cost stages to reject invalid or clearly weak candidates. Before using a subset, reduced resolution, fewer training epochs, or shorter simulation as a score screen, check on reference candidates that it preserves useful ordering. Treat it as a screen, not the final score. Keep some full-fidelity comparisons on distinct mechanisms so a biased cheap screen does not eliminate all alternatives.

For paired scalar reference scores, [calibrate the proposed screen](screening.md) at the planned survivor count. Inspect inverted pairs and missed full-best candidates, not only overall agreement. Cutoff ties may increase survivors and cost; a successful analysis is not a screen-validity certificate. Prefer fewer credible full evaluations when affordable calibration cannot justify the shortcut.

If screening ordering fails, revise that screen and reevaluate affected candidates at comparable fidelity. Optimizing the development pipeline can buy more experiments without improving the submission itself; record which cost was reduced.

Evaluate the most promising candidates at full fidelity against the incumbent on matched cases. For noisy metrics, use repetitions to resolve a decision rather than choosing the largest single observed gain. Maintain validity, screening, and confirmation outcomes separately; a partial or failed run cannot establish a new best.

Distinguish execution/training randomness from finite-sample uncertainty and distribution mismatch. For fixed scalar predictions evaluated on exchangeable samples, [paired row/group bootstrap](data-model.md#estimate-paired-sampling-uncertainty) can estimate sensitivity to the validation sample. Declare independent units and sampling settings before interpreting the result; dependent groups stay together. For training randomness, rerun matched training seeds; for distribution shifts, confirm on task-appropriate independent scenarios. More draws on the same cached predictions do not resolve either issue. Report uncertain gains and retain promising alternatives without making significance a universal promotion gate, especially for exact deterministic contest objectives.

### Avoid Work That Cannot Change the Next Decision

Measure wall time by phase so research, setup, candidate execution, and diagnostic overhead are visible. Use [the decision card and resume routing](decision-loop.md) to recover only changed events and the current unresolved question. Reuse a verified contract, source finding, or baseline while its prerequisites and dependency hashes still match. Load only the relevant task/reference section.

Start with a cheap valid score comparison. Use detailed slicing, profiling, bootstrap, or repeated training for pairs whose outcome could change promotion or suggest the next mechanism. A clearly rejected candidate may need only its rejection evidence; a close finalist may justify a fuller analysis. These tools remain available when a weak route has informative complementary errors or another unresolved mechanism. Cache verified predictions and deterministic intermediates at their dependency boundaries; recompute only affected descendants after a change.

When a stage dominates cost, profile it before increasing search breadth. Improve loading, preprocessing, compilation, or score calculation when that buys useful trials within the same budget. Validate equivalent outputs against the original path and include required setup/verification cost in the efficiency claim. Keep full-fidelity hard checks and the independent confirmation reserve; computational speed alone does not establish a score gain.

### Check Whether the Evidence Can Rank Candidates

Before a fine parameter or weight sweep, ask whether the current ranking is stable enough to guide it. Small development sets, loss concentrated in a handful of cases, contradictory regimes, or gains comparable to variation suggest a measurement experiment. Choose matched folds, training seeds, instances, or episodes according to the task's uncertainty and remaining budget. Keep confirmation untouched. Preserve each repetition's score and compute the contract's aggregation; the best fold or luckiest seed is not the comparison score.

For learned models, declare internal folds in the training/development pool and fit every learned transform inside each fold. Compare the same pipelines on the same folds; specify pooled predictions versus mean fold scores because they can rank candidates differently. For algorithms and policies, use the same instances and environment seeds with the full declared resource limit. A cheap repeat can reveal unstable selection without changing either candidate.

Unchanged candidates repeated under a declared measurement protocol consume time/compute. Searching for a favorable seed is candidate selection, and tested seed variants consume trial slots. A multi-seed model ensemble is also a new candidate with combined inference costs. Save enough budget to evaluate the mechanism actually selected; do not silently add a large cross-validation campaign to a small run.

## Keep Search and Confirmation Separate

Freeze the development metric, evaluation split, case weights, and final confirmation protocol before tuning. Choose a split appropriate to deployment: group or time splits when samples are dependent, fresh instances for combinatorial tasks, and matched repeated seeds for stochastic simulations.

Keep repetitions of one candidate distinct from independent complete agent runs when assessing the skill itself.

Use development results to select a small final shortlist. Evaluate the frozen shortlist on the confirmation set within the reserved budget. If its errors guide another edit, that set has become development evidence; document the reuse and arrange fresh confirmation where possible. Do not describe repeatedly inspected fixtures as unseen.

Record a `shortlist.json` before reading confirmation scores: finalist IDs and artifact hashes, reference/fallback, shortlist size, comparison protocol, and the decision rule for ties, uncertain gains, or ranking reversal. The rule should suit the task: a fixed exhaustive contest objective may permit direct metric choice, while estimated generalization needs its sampling limits stated. Apply the recorded rule instead of inventing a new one after seeing the outcomes. Confirmation can evaluate a frozen shortlist under that policy; tuning another configuration or expanding the shortlist from its feedback needs fresh evidence.

Report the best development result separately when confirmation is unavailable or disagrees. Full-data retraining produces final artifacts, not a new unbiased validation score.

Public leaderboard results can diagnose a mismatch with local validation, but repeated submissions can overfit the public set. Keep platform feedback and local evidence in separate records and respect submission authorization and quota.

## Promotion and Stop Decisions

Promote using the declared metric direction and official aggregation at matched fidelity. Do not reject a net score gain merely because it slows down or regresses in some cases, unless those are hard constraints. Conversely, an attractive mean on a convenient subset does not prove a gain on the actual objective.

If a full score cannot be calculated, preserve tradeoff candidates and label any selected incumbent as provisional under its stated heuristic. State which missing terms could reverse the choice. Do not invent a Pareto direction for a component whose effect on the score is unknown.

## Record Decisions and Recover State

Append planned and completed events under each trial ID in `trials.jsonl`; do not rewrite old outcomes. Before implementation include parent IDs, action/target, hypothesis, predicted observation, rejection test, planned fidelity, and cost. After execution include candidate/configuration hashes, evaluation and comparison paths, validity/fidelity, objective kind/direction, actual cost, decision, and the next unresolved question. Reference immutable result files instead of copying raw logs into the ledger.

At decision boundaries, refresh `next-action.md` using [the compact card](decision-loop.md#compact-decision-card). On resumption, reconcile its ledger checkpoint with new events; a missing or stale card is rebuilt from evidence. Partial, invalid, or interrupted runs remain diagnostic evidence. Reuse results only when their dependencies still match. Stop when the budget is spent or only the confirmation reserve remains; when stalled, either test a materially new mechanism within budget or deliver the best confirmed artifacts. Continuation does not reset consumed budget; increasing it is a separate user decision.
