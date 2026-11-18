# Derive Strategies and Learn from Strong Solutions

Read this when forming the first strategy, studying a stronger public solution, or escaping repeated local patches. The outcome is a mechanism-level explanation or a concrete implementation choice, according to the user's request. Reuse the current proposal/notes; no extra route inventory, report or experiment quota is required.

## Formulate the Problem Independently of the Code

The incumbent is a feasible witness and a source of engineering evidence. Its functions and neighborhoods need not define the next solution. Before following its call graph, describe what a good solution would look like in the problem's own terms. Use only the questions that change the strategy:

| Task fact | Reasoning it can unlock |
| --- | --- |
| Objective structure, symmetries, conservation laws or exact special cases | An ideal configuration or useful bound; a representation that makes the desired structure easy to construct |
| Difference between ideal structure and feasible outputs | A projection, decoder or joint allocation that preserves structure while satisfying constraints |
| Decisions coupled by a shared resource or constraint | Joint construction, decomposition with a coordinating variable, or a larger valid neighborhood |
| Penalties measured relative to a particular state or reference | Put that reference and cost into candidate generation; a final acceptance check alone may never generate the valuable compromise |
| Scores accumulated over time or repeated decisions | Price improvements by how long they can survive; identify which changes invalidate them and what information is legally available |
| A small change has limited dependencies | Maintain only affected terms or propagate a work queue until dependencies settle, rather than rescanning everything |
| Different regimes have different structure | Use an exact special case, specialized construction or selector where justified; check what applies outside that regime |

These are derivation prompts, not algorithms to apply to every contest. An idealized solution may be jointly infeasible; a bound or exact special case needs its assumptions. In learned systems, the analogous structural question may concern the statistical unit, missing signal, representation, or prediction target rather than geometric construction.

Compare the independent formulation with the incumbent: which useful outputs or information can it not currently express, and what coherent change would enable them? A profile can support a speed hypothesis, but cannot establish that the current representation is adequate. A structural conjecture needs a task-based argument and an observable consequence before implementation, not prior proof of a score gain. Use a diagnostic when it distinguishes competing explanations; otherwise prototype the mechanism.

For online prediction or planning, separate predicting the next event, estimating the lifetime of an improvement, and optimizing a robust action across plausible continuations. They require different evidence. Use only permitted observations and label assumptions about future events. A longer horizon can overpay for a fragile improvement or regress on short episodes; do not call a lifetime heuristic an accurate event predictor.

## Read a Strong Solution as a System

When finding or checking sources, use [competition research](competition-research.md) for question-driven search, full-source reading and following corrections to matching code. Then reconstruct the design below before selecting a transplant.

Start from the supplied writeup and its corresponding source/version when available. Read for the design chain: **task fact → simplifying assumption → representation → candidate construction → internal objective/pricing → maintenance and compute allocation**. Follow the score-affecting path far enough to understand interactions; avoid both exhaustive unrelated code reading and stopping at the first recognizable module.

Explain the central design in plain language: what choice becomes possible, why it addresses the objective, which approximation makes it affordable, and where it can fail. Distinguish the strategy from its implementation tricks and fitted constants. For each mechanism that matters to the comparison, identify:

- **Dependencies:** the construction, decoder, cost model, acceptance rule or update machinery it relies on. For example, a rebuild may need a retained-position reward and a matching move price; a copied search kernel alone does not test that design.
- **Actual difference:** whether the incumbent lacks the capability, implements it only in a restricted regime, or already has an equivalent. Different names and code size do not establish novelty.
- **Transfer conditions:** scale, information, constraints and resource assumptions that make the mechanism applicable. Preserve a strong incumbent specialization when the reference solves a different regime better.

Separate author-reported results, what inspected code establishes, and locally measured effects. A reported higher official score is a reason to learn the strategy, not proof that every module is superior. When the user supplies credible score context, use it without repeatedly making score verification the main task. Missing source or score details narrow the claim; they need not prevent explaining a well-described idea. Aggregate comparisons establish a system-level difference, not a component's causal contribution.

If asked to **learn the thinking**, deliver the central idea, how the task could have led to it, its interacting parts, and what changes in our approach. Do not substitute another benchmark campaign or a list of algorithms. If implementation is also authorized, use that explanation to choose the next complete candidate.

## Synthesize a Mechanism from the Mathematics

Check the decision-level implication as well as the equation. A construction establishes possibility under its assumptions; it does not identify the actual implementation or prove uniqueness. Test a uniqueness claim with another admissible parameter choice, and distinguish a restricted perturbation path from an arbitrary new intervention. Use exact algebra, a small counterexample or existing numeric tools when sufficient; a learner and cross-validation loop add no evidence to a simple possibility argument.

Derive beyond the supplied recipe when the task supports it. Mathematical synthesis means constructing a useful mechanism from explicit task structure; it does not require inventing a new theorem or claiming worldwide novelty. Work in the existing proposal's `basis`, `change` and `expected_observation`, at the depth needed for the decision:

1. Identify the variables, objective, constraints and information available at training and use time. State which simplifying assumptions are facts and which are hypotheses. An incumbent interface, blend rule or representation is not a task constraint unless the task says so.
2. Derive a consequential relationship: an invariance, decomposition, coupling, bound, bias/variance condition or constructive rule. Show enough steps to check the implication. Inspect a hand case, limiting case or counterexample before paying for training; do not turn the derivation into another obligatory benchmark campaign.
3. Turn the relationship into executable behavior. Explain what the candidate can now represent, optimize or coordinate, what coupled parts it needs, and how it differs from existing implementations. Combining known ideas can qualify when the joint mechanism follows from the derivation; merely appending modules or adjusting a constant does not establish that.
4. State an observable prediction that distinguishes the mechanism from a plausible competing explanation. Name where it can fail, what each outcome would change, and the smallest useful test. A coherent conditional hypothesis can justify a prototype even when its score effect is unknown. Do not demand a measured gain as the prerequisite for generating a new idea.

For example, under squared loss let an executable predictor be `f`, a deployable alternative be `g`, a fixed blend be `h = f + a(g-f)`, `e = f-y` and `d = g-f`. With finite second moments, expanding the square gives

```text
L(h) - L(f) = 2a E[e d] + a² E[d²].
```

This is an identity for those predictors and that evaluation distribution, not a fitted score guarantee. For a fixed positive `a`, improvement requires `E[e d] < -(a/2) E[d²]`. This gives a testable mechanism question about the direction and scale of a correction; neither better standalone accuracy nor a correlation threshold alone answers it. If clipping, calibration or another integration changes the deployed predictor, derive the condition for that actual output. The incumbent's equal blend need not constrain a complete alternative. These quantities may be analysed on development labels; prediction cannot access `y`, so a correction or selector must be trained within the declared information boundary. A repeatedly selected OOF estimate remains development evidence.

Use raw cross-moments in this calculation. For residuals `e` and `r`, `E[e r] = Cov(e,r) + E[e]E[r]`; Pearson correlation multiplies centered standard deviations, not RMSEs. Residual vectors `(1,2)` and `(-2,-1)` have Pearson correlation 1, yet their equal blend has MSE `1/4` versus `5/2` for either parent.

For the fixed blend with residual `(1-w)e + wr`, the inward MSE derivative at `w=0` is `2(E[e r] - E[e²])`. A small positive weight improves on that endpoint exactly when `E[e r] < E[e²]`; the raw cross-moment may be positive. Use `analyze_prediction_errors.py --check-blend-direction` on matched saved predictions. Negative inward derivatives at both endpoints mean some convex weight beats both parents on those rows; a nonnegative inward derivative makes that endpoint a minimum. This check does not choose a weight or assess learned integration. It covers only those saved vectors: an unbuilt member's fold-local fit would produce a different prediction direction with unknown conditional effects. A ceiling for the new member needs a bound on its actual feasible predictions.

A ratio between a member's score change and a blend's score change is a secant for that particular intervention. It does not rank the future value of model families or predict a different change's benefit without additional assumptions. With truth 0 and equal-weight predictions 2 and -2, improving the first member to 1 worsens the blend from zero loss to 1/4; with predictions 2 and -3, worsening the first to 3 makes the blend perfect. Use exact small examples or cached predictions to test such implications before fitting. Diagnose the actual integration and residual direction; a standalone-member gain threshold is neither necessary nor sufficient for blend gain.

A weak linear correlation does not show that a conditional advantage is unpredictable. For equally likely `S in {0,1,2,3,4}`, let `D=(S-2)^2-2`: `Cov(S,D)=0`, yet `D` is determined by `S`. Nor does superiority in a few aggregate bins exclude a different conditional selector. These counterexamples invalidate the universal inference; they do not establish that a useful selector exists in the competition. Keep a failed gate scoped to its actual inputs, fitted rule and evaluation, and require appropriate evidence before investing in another one.

When a candidate changes both solver and regularization, separate the observed system gain from its explanation. A wide and narrow grid choosing the same penalty can rule out the need for the wider grid on those observations. A fixed-penalty result for only one solver cannot separate solver effects, penalty effects and interaction. If that distinction changes the next action, seek the missing matched control using cached sufficient statistics or existing artifacts first; otherwise retain the competing explanations. An incomplete contrast does not establish a sole transferable lever or that two components are jointly necessary.

For several predictors, the pointwise identity `(mean(f_i)-y)² = mean((f_i-y)²) - mean((f_i-mean(f_i))²)` guarantees that averaging cannot exceed their average squared loss. It does not guarantee beating a particular incumbent member. An expected comparison with one random draw additionally needs a stated probability law and the appropriate marginal comparison; deterministic seed offsets do not establish that law or certify this realised gain. Account for the extra training/inference cost separately. Identify which comparator a theorem actually bounds before using it to justify promotion.

Likewise, high error in a subgroup does not determine whether its training influence should increase or decrease. That requires a hypothesis about the target population, noise, model bias or optimization, with an observable counterexample. Predeclaring one numerical weight prevents a sweep but does not supply the missing mechanism. A few sampled settings, especially on different parents, cannot prove a continuous optimum.

Keep exact deductions, assumptions and measured estimates distinct. A derivation can expose a capability or invalidate an explanation without settling competitive performance. Preserve alternative explanations when the evidence cannot discriminate; use targeted source research for the missing premise, not to avoid original reasoning or to decorate an already chosen setting.

Identify the quantity the evidence actually estimates. Printed decimal precision supplies no error distribution, confidence band or rounding model. A score difference between different configurations is not a repeatability estimate; a hypothetical interpretation of an unidentified baseline cannot turn it into a noise floor. Equal reported scores and selected settings can support equivalence on those observations without proving a global optimum or broken search plumbing. Inspect a missing fact only if it changes the action, keep hypothetical examples labelled, and avoid repeat solves or new fits merely to make a stronger story.

Bind a claimed bound to the operation it covers. A perturbation through fixed fitted coefficients does not bound retraining those coefficients or other members. A subgroup's error below the pooled error does not establish irreducible error or zero headroom. The number of rows carrying a rare feature does not determine how many deletions would reverse a gain, and retraining can change predictions outside those rows. A larger ensemble is not a strict performance superset of a smaller recipe merely because it contains its members. Use a small counterexample when one of these implications is driving a rejection.

One measured intervention, including a tiny or negative effect, is not an upper bound on the improvable capability of its input channel or model family. Calling that number "realised headroom" must not carry it into an expectation or ceiling for an untested mechanism. For truth zero, the predictor `f=1` can be perturbed to `f=1-epsilon` with arbitrarily small squared-loss improvement, while another replacement `f=0` eliminates the loss. A valid stronger bound needs assumptions that restrict the untested replacements and a checked derivation; otherwise retain only the observed effect. This possibility does not predict that such a replacement can be learned in the competition.

Even a certified optimum remains restricted to its feasible class and evaluated population. On two equally weighted cases with observable `x in {0,1}` and truth zero, let `f1(x)=2x` and `f2(x)=2(1-x)`. A constant blend `w*f1+(1-w)*f2` has MSE `1+(2w-1)^2 >= 1`, while the feature-based selector taking `f1` at `x=0` and `f2` at `x=1` has zero loss with the same fixed predictors. Optimizing constant weights therefore cannot bound conditional integration. A numerical feasible solution alone is an upper bound on minimum loss, not the lower bound needed to cap possible gain; a solver's success flag is not a certificate for an enlarged class. This counterexample establishes possibility, not a learnable gain on the competition.

For a decision-changing equation, check both sides by exact expansion or an independent tool calculation on a discriminating case, including non-unit weights where they matter. Checking only the arithmetic examples does not verify a separately written derivative. Identify each operand's entity, unit, split and operation before forming a relation: a count of leaderboard entries is not a training sample count, and a linear-solve count need not divide either. If two grids choose the same candidate, equal output is compatible with ordinary successful selection; it does not by itself imply that added candidates were skipped or ignored. Keep missing facts unknown rather than manufacturing an evaluation defect.

## Turn Understanding into a Complete Candidate

Choose the smallest implementation that preserves the proposed mechanism's dependencies. A different representation may need a decoder and valid moves; a model family may need different preprocessing; a trajectory policy may need a matching cost model. A standalone prototype behind the existing interface can be clearer than layering it on every old heuristic. Module replacement is useful when its prerequisites already hold or it answers a specific question; an incomplete transplant losing cannot reject the full method.

Name the observation that could distinguish the new capability from the incumbent. Use a trace or small mechanism experiment when it answers that question; then use matched full-objective evaluation for promotion and independent confirmation at delivery. Reuse trustworthy evidence. Add ablations only when component attribution would change the next decision. More tests refine the evidence for the proposed candidates; they cannot discover a representation that was never proposed.

## Check Equivalence Before Execution

Before implementing a claimed new capability, simplify its decision rule and compare it with what the actual parent pipeline can already express. Use algebra, a hand example or an existing trace to settle a concrete question; no separate report or preliminary training run is required. Record the relevant deduction in the proposal's existing `basis` and predicted observation.

| Proposed change | Check before spending execution cost |
| --- | --- |
| A common offset before `argmin`, or a strictly increasing transform before the same ranking | Under the applicable arithmetic and tie rules, does the selected action change at all? |
| A new linear combination of existing numeric inputs | Does it expand the model's function class, or instead change regularization, preprocessing or optimization? |
| A new feature, selector or state variable | Does it reach the actual output, and is its information available at fitting and inference time? |
| A nonlinear transform or a feature supplied to a depth-limited tree | Identify the function or partition that becomes easier to represent, and a case where that matters |

For example, with the same numeric inputs available to a linear predictor, appending `z = aᵀx` adds no linear expressivity: `βᵀx + γz = (β + γa)ᵀx`. Raw area sums or year differences therefore cannot be justified as information that a linear model was unable to combine. A Ridge fit may still change because the added coordinates alter its penalty; scaling, missing-value treatment or a nonlinear transform of the aggregate may also change the effective pipeline. A shallow tree can threshold an aggregate in one split where separate component thresholds require more structure. Inspect the actual order of these operations before choosing the explanation. Equal expressivity does not imply equal fitted predictions or performance.

If the claimed mechanism is equivalent or disconnected, remove that claim and revise or defer the proposal. If a different credible mechanism survives, state it and its counterexample rather than requiring a new model family. Theory establishes a behavior or limitation under its assumptions; it does not guarantee a score gain. Conversely, a better score does not prove the original explanation. Check [source attribution](competition-research.md#ground-decision-changing-claims) separately.

For an attribution check, state what is held fixed. Subtracting terms from a fitted predictor while keeping the shared coefficients and blend calibration fixed measures a conditional prediction change. A difference from the old fitted model can also include changed regularization, shared coefficients and recalibrated clipping or blending. The ratio of two score deltas is descriptive for that intervention and order, not a decomposition of the training effect. Anchor diagnostics to the campaign's frozen tools and saved fold models.

A single negative control can show that its specific intervention reproduces a gain; losing with one control does not establish that only the proposed mechanism can work. Match the dependency or geometry that could drive the result, not just the number and scaling of columns. Before spending fits on a weak control, ask whether either outcome would change the implementation choice. Keep competing explanations and a distinct mechanism open when the test cannot distinguish them.

## Generate Routes That Can Actually Disagree

When the task or history does not yet distinguish solution families, write a few compact, complete strategy hypotheses before committing code. Make them differ in representation, construction, optimization target, information use or coordination variable; changing a coefficient or operator name does not create a new route. At least one route should deliberately test the strongest structurally different idea, and a stalled search may need a route generated without the incumbent or its memory. Choose among routes by their plausible movement toward the target and applicable evidence, not by familiarity or proposal confidence alone. Do not force a fixed number of routes when the mechanism is already clear.

Keep score vectors, regimes or error cases when one scalar average would discard useful complementarity. Retain a strong specialist when it adds objective value on cases the current portfolio misses, and select parents or follow-up experiments that expose those differences. A lower-ranked candidate is useful only if its unique behavior can affect the task objective or unlock another route; diversity by itself is not progress.

Classify a tested route by the mechanism that reached the executed code. Check implementation fidelity separately from score: a partial or substituted implementation can be a useful candidate, but cannot establish that the proposed family failed. When speed and quality both matter, retain relevant tradeoffs under the actual objective and constraints; a simple complexity proxy needs its relationship to runtime checked before it drives selection.

Retire only the construction the evidence tested. A standalone model or fixed vote does not test a learned stack of the same members; a specialist failing in one blend or preprocessing path leaves other integrations unmeasured. For a feasible, materially different alternative, retain its distinguishing prediction and the matched comparison that could falsify it. Weigh its mechanism, evidence and cost against the best refinement. Do not require an advance gain, a negative raw-error cross-moment, or a noise threshold inferred for old refinements before prototyping. Apply the declared evidence requirements at promotion.

Separate diagnostics on fixed predictions from evaluation of a learned successor. Residual concentration, a fixed blend direction or a permutation comparison can suggest where to look. A residual model or stack fitted on cached OOF inputs needs [isolation at every fitting layer](local-evaluation.md#match-the-intended-test-conditions) before its score can guide selection. Even with that isolation, a negative result for the tested learners and controls supports deferring those designs; it does not establish irreducible error, close a whole representation or aggregation family, or require an unbuilt alternative to demonstrate a gain before prototyping.

Treat experience as a decision input, not an archive of prose. Compare a useful success with a relevant failure at the decision or operation that produced the outcome; extract a conditional rule, its scope and counterexample risk. Feed that rule into the next proposal and revisit it when new evidence conflicts. On stagnation, change the layer implicated by the failure: first the local construction or operator when its premise survives, then representation, decomposition or coordination when the reachable candidates are wrong, and a fresh strategy family when the current line's ceiling is credible. This escalation is a diagnostic choice, not an automatic ladder or a fixed patience threshold.

Before translating a nontrivial strategy into code, manually walk a small representative state or trajectory far enough to expose its invariant, coupling or failure mode. If that walk contradicts the mechanism, revise the strategy before coding; if the reasoning is sound but execution is weak, inspect translation, objective accounting and implementation behavior separately. A hand walkthrough can reveal a conceptual flaw but does not establish performance.

For concrete source-backed patterns and their limits, see [strategy-generation patterns](source-patterns.md). These examples are implementation leads, not rules to copy wholesale.

## Worked Example: JSSP Dispatch

Assume a parent dispatch rule in a job-shop scheduling task selects the unfinished job with the shortest next-operation duration. Inspected HeurAgenix [base code](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/src/problems/jssp/heuristics/basic_heuristics/shortest_processing_time_first_c374.py#L23) does this; its [readiness variant](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/src/problems/jssp/heuristics/evolved_heuristics/shortest_processing_time_first_d471.py#L53) instead computes `r_j = max(machine_end[next_machine(j)], job_end[j])`. This is a source-backed reasoning example, not a claim that this parent is our current entry or that the variant improves a contest score. The [research example](competition-research.md#worked-example-source-evidence-to-a-dispatch-proposal) shows how to cite it in a proposal.

Consider a valid partial state where both next operations use an idle machine M with end time 0, and A's predecessor on another machine has already been placed through time 100:

| Job | Next duration | Job end time | Feasible next start `r_j` |
| --- | --- | --- | --- |
| A | 1 | 100 | 100 |
| B | 10 | 0 | 0 |

Duration ranking selects A; readiness ranking selects B. The changed capability is to use available machine/job state during construction, potentially avoiding an append decision that reserves M behind a late-ready job. Complete the mechanism by maintaining those end times and operation indices, reading them in the actual ranking loop, and applying the selected job through the legal schedule-update operation. A new feature that never reaches selection, or stale state after an update, does not test this mechanism. Choosing an earlier start can still delay a critical operation or worsen downstream contention; full-schedule makespan and legal resource use remain the task evaluator's questions.

The same inspected variant subtracts `c = bias_weight / (job_diversity + 1)` from every candidate's `r_j` at that state. With a common finite `c`, exact arithmetic and unchanged tie-breaking, `argmin_j(r_j - c) = argmin_j(r_j)`. This offset cannot provide the claimed job-specific trajectory preference. Sweeping it does not test a new dispatch capability; relative to the duration parent, the actual change is the readiness term. This algebraic observation is not a measured performance result.

Use a hand walkthrough or existing trace to settle the decision difference, and source inspection to check that information reaches the returned action. If implemented, retain complete legal schedules, objective results and costs under a matched protocol. A stronger source system's score cannot establish this component's contribution, and a low score from an unconnected component cannot reject the intended mechanism. Record what actually happened through the existing [review and learning chain](iteration-trace.md#worked-follow-through-readiness-dispatch), without assigning a shared batch gain to every idea used during that batch.

## Worked Example: Dynamic Circular Layout

In the Huawei fixed-timeslot task, updates change category quotas on a ring. Uniformity U rewards spacing, stability V charges additional changes relative to the layout at the current API call's entry, and quality accumulates over an update trajectory. These facts support the following reasoning independently of an existing swap optimizer:

| Task fact | Derivation | Candidate idea |
| --- | --- | --- |
| The final quota determines ideal spacing | Intermediate greedy gaps need not resemble the final layout | Construct targets for the final quota, then project jointly to legal vacancies when choices interact |
| Stability uses the call-entry layout | A good rebuild can be expensive unless old occupancy influences its construction | Reward retained positions while constructing the layout and evaluate movement against the same entry state |
| Layout improvements contribute across later updates | A fragile vacancy pattern and a persistent business pattern need not have the same benefit lifetime | Estimate survival of useful structure, or compare permitted continuation scenarios, when pricing current movement |
| A local mutation changes a limited set of same-category gaps | Most unaffected score terms need no new work | Seed incremental repair from the changed dependencies and propagate only as needed |

The [SlotWeave writeup](https://bbs.huaweicloud.com/forum/thread-02127227933062879438-1-1.html) and [inspected source version](https://github.com/XJU-ICTHUB/SlotWeave/tree/ae02dd527e757426b67015c5acc17dcb3584cc4c) illustrate construction, retained-position rewards, lifetime-based pricing and incremental maintenance working together. The local incumbent in that comparison, R36, also had DP, lookahead and geometric indices in some regimes; the useful comparison is their coverage and integration, not claiming those techniques were absent. A longer-horizon price is a heuristic about persistence, not a predictor of the next add/delete request.

For a speed objective, this reasoning may favor a better cheap construction or dependency-limited repair before caching another scan. For trajectory quality, it may favor joint placement or construction with movement-aware pricing. Which candidate wins still needs the task's actual evaluation. These are examples of deriving a strategy; the task's arithmetic restrictions, exact special cases and source constants are not general competition requirements.
