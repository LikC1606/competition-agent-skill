# Search for Score Improvements

Read this when selecting or revising solution routes and their experiments. Optimize the contest objective under the remaining budget; choose actions from evidence and unresolved questions. A candidate is an executable method/configuration, not a prescribed small mutation.

## Compare Routes Before Choosing Variants

The outer decision is **which solution route deserves effort**; the inner decision is **which implementation or setting tests that route**. Keeping these separate prevents an easy parameter edit from repeatedly winning over a harder method with more headroom. For a score-seeking run, compare credible structural alternatives before a parameter campaign when affordable. If constraints, prior matched evidence, or remaining resources make alternatives unhelpful, state that reason and refine the supported route. Do not force breadth when the baseline is already near a credible bound.

Compare a few routes from task structure, baseline behavior and relevant sources. Keep only the information needed to choose an executable test in `research.md` or existing notes; the table below is optional. Drafting ideas does not consume candidate slots, but research and implementation consume time. Do not postpone a complete prototype to fill a route inventory. Establish viable representatives, then invest in supported mechanisms rather than giving every route an equal quota.

| Route field | Decision it enables |
| --- | --- |
| Route ID and mechanism | Distinguish representation, algorithm/model family, data/training signal, policy, and parameter variants |
| Evidence and prerequisites | Explain why the route fits this objective, scale, data, rules, and resources; retain the source/version |
| Objective headroom | Identify a fixable failure, stronger reference, bound, or missing capability; label unsupported gain estimates |
| Minimal complete prototype | State the smallest executable implementation that actually tests the different method, not an incomplete stub |
| Cost and continuation | Include implementation, evaluation, likely full-fidelity follow-up and combined inference cost; say what justifies deeper work |
| Status and best representative | Candidate/result IDs, tested maturity/resource limit, and supported, unresolved, or rejected mechanisms; keep investment eligibility separate from incumbent rank |

Compare the next proposed variant with the strongest affordable alternative route. Prefer the action with credible potential to change the best solution or resolve a consequential uncertainty; do not assign numerical expected gains without a basis. A tiny test can reveal a large opportunity, and a large rewrite can still be low value. Record the chosen route and why its nearest alternative was deferred; a short sentence at a decision boundary is enough.

Typical structural changes are algorithm/representation/encoding/neighborhood replacements; model/feature/pipeline changes; different permitted data or training objectives; and changes to observations or planning in a policy. Thresholds, weights, seeds, and neighboring hyperparameters are usually refinements of an existing route. The classification explains the search, not a mandatory schema or a ban on a useful cheap tweak.

A cache, a target-window filter or an extra cleanup pass inside the same optimizer usually tests a component refinement. Name it accurately. When repeated local refinements fail, implement a complete alternative method that addresses the limiting mechanism rather than renaming another local patch. Output equality with the incumbent is a useful check for an intentionally equivalent speedup; it must not exclude valid different solutions in a score-seeking route comparison.

Use one interpretable hypothesis or **coherent pipeline transition** per candidate. A new model may need different preprocessing, and a new representation may need a decoder and search moves; implement the coupled change together. Compare the complete candidate first. Use selective ablations only when attribution would change the next investment or final combination; without them, claim the whole pipeline's observed gain rather than identifying one component as the cause.

Repeated refinements with negligible objective gains, improvements within noise, or the same unresolved failure warrant reconsidering the route's current search. Check [maturity and stopping evidence](#decide-whether-to-repair-deepen-or-retire) before attributing a plateau to the method. Revisit assumptions, representation, data/training signal, search space, or policy before more neighboring settings. Keep successful incumbents and rejected evidence; budget or confirmation limits still stop exploration.

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
| Route and change scope | Which solution family it tests, and whether it replaces a method/pipeline, refines it, tunes settings, or combines parents |
| Parent and evidence | Candidate IDs, source or local result, and the remaining uncertainty |
| Prerequisites | Data, rules, scale, solver behavior, or resources needed for the idea to apply |
| Prediction and rejection test | An observable outcome and the cheapest useful experiment that could contradict it |
| Cost and next decision | Implementation/evaluation cost, failure condition, and whether success justifies a larger trial |

Prefer plausible objective gain per unit of total experiment cost while keeping room for unfamiliar mechanisms. Numeric gain predictions are estimates, not results.

## Decide Whether to Repair, Deepen, or Retire

After a weak result, decide two things separately: whether this candidate beats the incumbent, and whether its route merits another experiment. A valid low score can answer the first without answering the second. Record the narrowest supported conclusion; "not promoted" is not a diagnosis or proof that the entire route is unsuitable.

| Evidence from the trial | Supported conclusion and next choice |
| --- | --- |
| Broken interface, invalid output, or a failed known-answer check | The implementation failed to test the mechanism. Consider a bounded repair if its cause is identifiable and the repaired experiment beats the strongest affordable alternative in value. |
| Infrastructure failure or interruption before a complete result | Quality is unresolved. Preserve partial work for diagnosis, reconcile cost, and repair/recover only if useful. |
| Valid result stops at a resource cap; progress remains near the stop | The tested allocation is insufficient to establish convergence. Consider a legal deeper or more efficient implementation; do not assume extrapolated improvement. |
| Valid result is flat, but the search did not finish a neighborhood, training is underfit, or a required component is absent | This prototype leaves a mechanism unresolved. Test the missing component or a complete affordable pipeline when evidence justifies it. Flatness alone does not establish maturity. |
| Completed local search, stable development learning behavior, or repeated negligible gains at suitable fidelity | The tested mechanism has plateau evidence. Consider a new representation, neighborhood, training signal, or route; local convergence is not global optimality. |
| A complete, applicable implementation loses under the intended limits and no supported rescue remains | Retire the tested mechanism at that scale/resource setting, retaining its result and reason. Broader rejection needs broader evidence. |

Use adapter-specific evidence already available: termination reason, actual work and objective progress for search; training/development curves and fit provenance for learned models; complete episode/horizon and constraint failures for policies. Small exact cases or an independently scored reference can reveal a defect, but do not prove large-case competitiveness. If evidence is missing, retain uncertainty; collect only diagnostics that can alter the next investment. Use development evidence, never confirmation errors, for this diagnosis.

Compare a lagging route's proposed **complete pipeline** against further refinement of the leader. Initial construction quality need not predict quality after local optimization; a model may require different preprocessing/training; a weak parent may have complementary errors. Test a credible combination or missing component rather than repeatedly polishing the same premature prototype. This does not give every route an automatic rescue trial: include implementation, full execution, downstream cost and remaining confirmation reserve, and defer when another action has stronger support.

Before a rescue, name the defect or missing capability, the observation that would justify continuation, and the rejection/stop condition. Count the changed implementation or resource setting as a candidate trial; unchanged diagnostic measurements still consume time/compute. A contest's per-candidate hard cap cannot be extended: improve work allocation or implementation within it. Training more can overfit, and searching longer can remain trapped; a recent progress trace is evidence for a test, not a promised gain. Compare any new result under the sealed full objective and intended resource constraints.

Keep the route's best representative, tested scope, unresolved mechanism and next investment decision alongside its promotion status. A route deferred because budget ran out is **untested or unresolved**, not empirically rejected. Reopen a retired mechanism only when a relevant dependency, implementation finding, resource setting or new evidence changes the reason for retirement.

## Select the Next Action

| Evidence or uncertainty | Action | Evidence needed to continue |
| --- | --- | --- |
| Only one family has been tried, with unclear fit | Explore a materially different route | A valid result, resource fit, and promising objective or complementary behavior |
| Low score with an unclear cause | Diagnose using case analysis, a profile, ablation, or small reference solution | A bottleneck or falsifiable explanation that suggests an affordable change |
| A valid lagging prototype leaves a credible mechanism unresolved | Compare a bounded repair/deepening or complete pipeline against the leader's next refinement | Cause/maturity evidence, a useful rejection test, and a full candidate within the intended limits |
| A component has a supported improvement mechanism | Refine that component | Matched evaluations that justify another variant or reveal a new testable mechanism |
| A route has evidence and unresolved high-impact mechanisms | Replace or deepen that mechanism | Full-objective gains or a consequential rejected hypothesis |
| A mechanism works and settings are now the consequential uncertainty | Tune its parameters | Full-fidelity gains that reproduce beyond the screening setup |
| Repeated tweaks produce negligible gains while structural alternatives remain | Return to the route map | A materially different affordable prototype or a documented reason to stop |
| Candidates have compatible, complementary strengths | Combine or select by regime | Improvement in the combined candidate's objective within its resource limits |
| Apparent gain is comparable to measurement variation | Repeat a matched comparison | Enough evidence to resolve the promotion decision |
| Final reserve is all that remains | Confirm the frozen shortlist | Validity and independent objective measurements for delivery |

Diagnostics are experiments too and consume budget. Keep their results separate from candidate ranking. A correctness failure may justify a repair when the mechanism remains promising; an infrastructure failure gives no evidence about algorithm quality. Neither warrants unlimited retries.

## Refine a Measured Component

When the budget supports deeper search, use a targeted ablation, runtime profile, or small reference solution to choose a component worth refining. Within it, test an explanatory mechanism or coherent replacement per trial and use prior results to select the next variant. Include representation, solver encoding, search neighborhoods, features, and training signals where the task supports them; parameter changes are only one search action. Do not limit a route replacement to the incumbent's editable lines if its interface and rules permit a different implementation.

An ablation measures the current solution's reliance on a component, not its remaining improvement potential. Combine that evidence with a plausible improvement mechanism and evaluation cost. Keep the official evaluator fixed. An approximation used inside the candidate's search is itself a hypothesis and still needs confirmation on the declared objective.

Reallocate trials to another component or route when gains fail to reproduce, a limiting bound is reached, or remaining variants lack a credible benefit. A promising line need not be abandoned after one failed variant, and a familiar line does not earn extra trials merely because it is easy to edit.

## Explore, Refine, Combine

Use the route map to start with materially different solution families when affordable. Keep their parent IDs and best validated representatives; one route may excel at a different regime or later combine with another. This is a candidate portfolio and can be executed by one agent sequentially. Exploration is not finished merely because one quick-to-implement variant exists; deepening is not postponed merely to fill a prescribed number of routes.

After a mechanism works, tune its sensitive parameters with a small sweep or adaptive search. Compare candidates at documented evaluation fidelity. If promising gains from routes can coexist, make a separate combination trial with all parent IDs and an ablation where it changes the decision. Gains need not add; evaluate the combination's objective, runtime, and memory including selection or ensemble overhead. Use ensembling only when the submission format and metric support it.

For model ensembles, inspect complementary validation errors rather than selecting solely by individual rank. Reuse cached predictions only with matching sample IDs, split, preprocessing, model/configuration provenance, and metric. OOF predictions must exclude held-out samples and dependent groups from label-dependent fitting. Fit learned preprocessing within folds unless the contract permits transductive fitting; document any such use of held-out features. Tune combination weights on development evidence and confirm the frozen combination independently. A regime-specific algorithm selector must use features available at inference, not ground-truth outcomes.

For the supported scalar CSV interface, [the blend tool](data-model.md#construct-and-confirm-a-prediction-blend) constructs weighted candidates from compatible development evaluations and reapplies a frozen recipe by member name. When the two-parent decision needs error diagnostics, [the RMSE/MAE direction check](data-model.md#check-whether-a-two-parent-blend-has-a-useful-direction) can exclude segments with no strict development gain; case wins alone cannot decide this. It supplies no weight or practical gain estimate. Evaluate every blend with the declared metric, count each weight variant as a trial, and include all contributing models' inference cost. Freezing an algorithm selector's thresholds or a simulation policy mixture follows the same principle: selection settings are candidate parameters and cannot be retuned on confirmation evidence.

Reuse intermediates only when their dependencies match. A changed feature pipeline, split, model, or training configuration invalidates affected cached results even if output filenames are unchanged.

## Learn from Evaluated Pairs

Use an informative matched comparison to change the next decision, not merely to narrate a score. Contrast candidate code/configuration, full-objective results, representative regimes, stopping behavior and actual cost. Reuse existing artifacts; extra profiling, ablation or measurements need a consequential question and budget.

Keep three layers separate in `research.md`:

| Layer | Useful content |
| --- | --- |
| Observation | Parent/candidate IDs and result paths; tested change, matched fidelity, gain/regressions and cost. State whether the prediction was supported, contradicted or unresolved. |
| Explanation | The proposed reason and an alternative explanation still compatible with the evidence. An improving trace may motivate work-allocation changes without proving wasted work caused the loss. |
| Next test or scoped lesson | A specific change, prerequisites, expected observation, rejection condition, and why it outranks the nearest affordable alternative; or a bounded lesson when no trial fits. |

If a prediction fails, revise its mechanism, applicability or expected observation; do not preserve the same claim behind a new candidate name. If the result is unresolved because of defects or uncertainty, retain that limitation rather than rewriting it as a method failure. If a change improves its parent but loses to the incumbent, retain both conclusions: local progress supports that tested implementation, while promotion still follows the full-objective comparison. Another refinement needs its own headroom and cost argument.

Carry only decision-relevant lessons forward, with task/metric, scale/resources, success and failure regimes, and linked evidence. Preserve contradictory findings instead of accumulating only successful advice. A learning entry should change an action, constraint or falsifiable prediction; skip generic reflections that do not. On resumption, check the lesson's dependencies before using it. On a different task, verify prerequisites and make a budgeted transfer test; prior gains are not promised gains. Learned-model examples concern experiment records, not online weight updates or permission to reuse held-out labels.

Examples of testable feedback are replacing search order when capped work still progresses, revising training signal when permitted labels/features leave systematic errors, or changing solver encoding when the measured scale bottleneck persists. These are task-qualified choices, not defaults. A candidate's internal objective approximation, schedule or training loss may change; the official evaluator and confirmation separation remain fixed. Stop at the remaining budget even when feedback suggests another useful test.

## Spend Evaluation Budget Where It Changes Decisions

Measure baseline costs and reserve final verification first. Record round and cumulative time/compute/trials, including research, evaluator development, diagnostics, retries, training, full runs and confirmation. Changed configurations, ablations, repairs and rejected candidates count. Respect explicit user caps at their stated scope; otherwise use the bounded work-round default in `SKILL.md`, including the verification reserve. Do not convert an old default into a permanent task-wide user cap.

Use low-cost stages to reject invalid or clearly weak candidates. Before using a subset, reduced resolution, fewer training epochs, or shorter simulation as a score screen, check on reference candidates that it preserves useful ordering. Treat it as a screen, not the final score. Keep some full-fidelity comparisons on distinct mechanisms so a biased cheap screen does not eliminate all alternatives.

For paired scalar reference scores, [calibrate the proposed screen](screening.md) at the planned survivor count. Inspect inverted pairs and missed full-best candidates, not only overall agreement. Cutoff ties may increase survivors and cost; a successful analysis is not a screen-validity certificate. Prefer fewer credible full evaluations when affordable calibration cannot justify the shortcut.

If screening ordering fails, revise that screen and reevaluate affected candidates at comparable fidelity. Optimizing the development pipeline can buy more experiments without improving the submission itself; record which cost was reduced.

Evaluate the most promising candidates at full fidelity against the incumbent on matched cases. For noisy metrics, use repetitions to resolve a decision rather than choosing the largest single observed gain. Maintain validity, screening, and confirmation outcomes separately; a partial or failed run cannot establish a new best.

Distinguish execution/training randomness from finite-sample uncertainty and distribution mismatch. For fixed scalar predictions evaluated on exchangeable samples, [paired row/group bootstrap](data-model.md#estimate-paired-sampling-uncertainty) can estimate sensitivity to the validation sample. Declare independent units and sampling settings before interpreting the result; dependent groups stay together. For training randomness, rerun matched training seeds; for distribution shifts, confirm on task-appropriate independent scenarios. More draws on the same cached predictions do not resolve either issue. Report uncertain gains and retain promising alternatives without making significance a universal promotion gate, especially for exact deterministic contest objectives.

### Avoid Work That Cannot Change the Next Decision

Measure wall time by phase so research, setup, candidate execution, and diagnostic overhead are visible. Use [the decision card and resume routing](decision-loop.md) to recover only changed events and the current unresolved question. Reuse a verified contract, source finding, or baseline while its prerequisites and dependency hashes still match. Load only the relevant task/reference section.

Start with a cheap valid score comparison. Use detailed slicing, profiling, bootstrap, or repeated training for pairs whose outcome could change promotion or suggest the next mechanism. A clearly rejected candidate may need only its rejection evidence; a close finalist may justify a fuller analysis. These tools remain available when a weak route has informative complementary errors or another unresolved mechanism. Cache verified predictions and deterministic intermediates at their dependency boundaries; recompute only affected descendants after a change.

For CSV error analysis, use [summary output](data-model.md#diagnose-development-errors) when top cases and slice statistics resolve the question. It preserves full-split diagnostics while avoiding a redundant per-case export; retain referenced inputs and request the full table when other cases need inspection.

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

Keep competition/user hard constraints separate from agent-chosen screening policies. A minimum 2% speedup or maximum 5% slowdown has no default authority; use a threshold only with a stated task, user or measurement basis. A screening cutoff can guide cost allocation without establishing that a smaller gain is false or a tradeoff loses official score. Revise unsupported policies prospectively before further development/confirmation, preserving past protocol versions and outcomes; never change a frozen delivery rule after confirmation to obtain a preferred winner.

If a full score cannot be calculated, preserve tradeoff candidates and label any selected incumbent as provisional under its stated heuristic. State which missing terms could reverse the choice. Do not invent a Pareto direction for a component whose effect on the score is unknown.

## Record Decisions and Recover State

Append planned and completed events under each trial ID in `trials.jsonl`; do not rewrite old outcomes. Before implementation include parent IDs, action/target, hypothesis, predicted observation, rejection test, planned fidelity, and cost. After execution include candidate/configuration hashes, evaluation and comparison paths, validity/fidelity, objective kind/direction, actual cost, decision, and the next unresolved question. Reference immutable result files instead of copying raw logs into the ledger.

At decision boundaries, refresh `next-action.md` using [the compact card](decision-loop.md#compact-decision-card). On resumption, reconcile its ledger checkpoint with new events; a missing or stale card is rebuilt from evidence. Partial, invalid, or interrupted runs remain diagnostic evidence. Reuse results only when their dependencies still match. Stop when the current round or applicable user cap is spent, or only the confirmation reserve remains; when stalled, test a materially new mechanism that fits or deliver the best supported artifacts. Preserve consumed work on continuation. A new user request after a completed default round can start another bounded round under `SKILL.md`; an exhausted explicit user cap requires an explicit extension.
