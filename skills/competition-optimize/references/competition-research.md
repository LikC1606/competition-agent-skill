# Find and Use Strong Competition Solutions

Read when choosing an initial strategy, investigating a concrete limitation, or learning from a stronger solution. The outcome is an explanation or a mechanism proposal supported by inspected sources, according to the user's scope.

## Frame the Question

State what remains uncertain and how different answers would change the next action: the statistical unit, objective, useful representation, missing signal, validity rule, failure mode, or resource bottleneck. For example, evidence that correct candidates are present but misselected favors selection research; absent correct candidates favors generation or supervision research. Seek strong public solutions early enough to inform strategy, and revisit them when a consequential question appears. Reuse sources already inspected when they still answer the question.

| Input to research | Decision to resolve | Return to the main loop |
| --- | --- | --- |
| Initial task or an unexamined solution family | Which applicable strong formulation should shape the first complete method? Search task facts and alternatives as well as incumbent vocabulary. | A selected capability and its implementation prerequisites, not just a bibliography |
| A strong writeup or local limitation exposes a capability gap | What information, representation, objective, construction or selection makes that capability possible? Inspect necessary coupled parts in matching code. | A complete mechanism proposal using existing fields |
| Public/local disagreement or suspected evaluation defect | Which scorer, split, pipeline or transfer explanation is consistent with official facts and source evidence? | A justified evaluation repair or falsifiable mechanism; unresolved disagreement remains uncertainty |
| An executed mechanism fails its prediction | Was the design mistranslated, a dependency omitted, or an applicability assumption false? Search the newly exposed gap. | A specific repair, changed capability or route retirement; do not restart general search |

Choose sources for the claim being checked:

- **Kaggle Discussions and Code:** actively seek high-scoring solution posts, validation discussions, error analyses, notebooks and relevant follow-up comments. A vote count or public score helps discovery but does not establish transfer.
- **Winning writeups and matching repositories:** recover the full approach, implementation dependencies, resource costs and exact source version. Include credible lower-ranked or negative reports when they expose an applicable failure.
- **Original papers:** inspect the method and assumptions behind a borrowed mechanism; follow citations from writeups or code when that resolves the question.
- **Official scorer, rules and organizer clarifications:** settle metric aggregation, permitted information, evaluation units and constraints. Check an author's interpretation against these when it affects the proposal.

## Search → Read → Pivot

1. **Search for the question.** Combine the exact competition name/year or task identity with the mechanism, metric, constraint or failure being investigated. Search the task family and analogous tasks when their structure may reveal another formulation. Include vocabulary from the objective and ideal solution structure alongside the incumbent's module names.
2. **Read the evidence.** Open the full original post, paper or notebook and relevant linked material. Follow corrections and substantive comments; inspect the matching repository/version for claims about implementation. Search snippets and summaries identify leads; they do not establish what the original source or code says.
3. **Pivot from what is missing.** Follow a reference chain, try another formulation or inspect a competing explanation when the source leaves a consequential gap. If reported gains use another split, scorer or resource regime, investigate that difference before transferring the conclusion. If a full source is inaccessible, retain the lead with that limit and seek another source for the claim.

For Kaggle sources, use the optional [source reader](kaggle-sources.md) when it can resolve access, competition identity, unread comments or a specific notebook version. Preserve the returned reading range and failures: a preview, a cached empty result or a partial comment response cannot establish that the original contains no relevant correction. Use other available sources when needed; settled evidence does not require another tool call.

Choose the access path from [the current invocation's actual tools](codex-tools.md), including available native search/browser tools and terminal readers. Batch independent discovery or source reads when supported, then follow the decision-changing source chain sequentially. Local cached notebooks are reusable evidence, not the boundary of discovery when a new question requires another source. If one access path fails, inspect the failure and try an authorized available alternative; keep the specific unresolved reading limit rather than declaring the whole research direction inaccessible.

Continue only while a missing fact can change the mechanism, its legality, evaluation or necessary components. Stop when the evidence supports the requested explanation or a concrete next mechanism with understood prerequisites. If the remaining question is whether it works on this task, more reading cannot replace local evidence in an implementation task. For theory-only scope, state the predicted effect and unresolved transfer rather than launching that evaluation. No query/source count or fresh full search is required each iteration.

## Preserve the Source Chain

Use existing `research.md` or task notes for decision-relevant findings. Retain the source URL, matching code/version, license where reuse matters, and the source chain from a summary to its original evidence. Keep the metric/split, information, data scale and compute assumptions needed to interpret a reported result.

Keep raw responses, readable originals and code snapshots under the current task's `<run>/research/`, with their actual paths and byte hashes. In `research.md`, record the question, decisive passage/location, snapshot/version, transfer conditions and unresolved point; keep the agent's interpretation separate from the source. Cite those paths and hashes in the existing `basis` rather than copying whole sources into the proposal or creating a candidate for a reading action. Hashes identify the material, not the truth of its interpretation.

Distinguish author-reported outcomes, inspected implementation and local measurements. Preserve useful negative results, caveats, corrections and discrepancies between a writeup and its code. A complete system's score does not identify which component caused its advantage. Record a gap as unresolved rather than silently choosing the more favorable account.

Before using numerical evidence in a decision, retain its entity, unit, population/split and exact source location beside the value. Use the reader's `quantities` bindings when supplied; otherwise inspect the original. A number in an old interpretation is not a new observation. If the population or relationship is missing, leave it unknown instead of combining unrelated counts or inventing a denominator.

Extreme or rounded leaderboard scores and leakage-themed titles are reasons to inspect validity, not proof of contamination or the cause of a score cluster. Without the relevant body/code and information-flow evidence, keep that explanation conditional and do not declare the whole board or method invalid. A title can identify a useful lead while its causal claim remains unread.

### Ground Decision-Changing Claims

Before a source-specific statement enters a proposal's `basis`, inspect the supporting passage in the saved version. Retain its section, notebook cell or function/line locator and enough of the passage to recover the reasoning in the existing notes. A whole-notebook URL, title, hash or search hit does not establish that a particular feature or algorithm appears there. Check the relevant code path when attributing implementation behavior; an author's discussion and executable code can differ.

Keep these evidence types explicit where they affect the decision:

| Evidence | What it supports |
| --- | --- |
| Author's statement in an inspected passage | What the author reports, with its metric, split and stated conditions |
| Inspected implementation in the matched version | What that code actually constructs or executes; its local contribution remains unmeasured |
| Agent's task-based deduction | A proposed mechanism inferred from task facts or code; label the inference and assumptions rather than attributing it to the source |

For example, a housing notebook's skew/log preprocessing does not establish that it constructs total floor area or elapsed building age. If those features are absent from the inspected version, a useful aggregate-feature hypothesis can still proceed as task-derived reasoning after the [equivalence check](strategy-design.md#check-equivalence-before-execution). Do not invent a source attribution to justify it. A mismatched or inaccessible version leaves the specific attribution unresolved; narrow the claim or obtain the relevant original only if it changes the next action.

When an error is discovered after a proposal is sealed, preserve the original and append the correction to existing task notes, outcome feedback or a successor's `basis`. Reassess the mechanism if the correction removes its premise. A citation correction alone does not invalidate unchanged training artifacts or require another fit; record exactly which interpretation or dependency changed. These are semantic checks performed by the agent, not guarantees supplied by archive hash validation.

Keep the editable current interpretation consistent when making that correction: replace the unsupported assertion or mark it withdrawn at its location, rather than appending a contradictory conclusion. In campaign receipts, replace the same correction key with supported conditions, or withdraw it without inventing a replacement using `{key, status: "withdrawn", reason, evidence}`. The driver retains the withdrawal and its prior-receipt pointer across contexts; sealed notes and results stay unchanged. Recheck a remembered premise against its cited original before using it in another calculation.

## Convert a Finding into a Mechanism

Use [strategy learning](strategy-design.md#read-a-strong-solution-as-a-system) to reconstruct task facts → information used → representation/objective → construction/selection → coupled components. Compare with actual incumbent code: what can the strong design do that this implementation cannot, and why? Extract that transferable capability and its assumptions; copied winner constants alone do not explain a change. A high-scoring full system does not imply that an isolated transplanted component will work.

Attach the inspected source, capability gap, transfer argument and unresolved assumptions to the existing proposal's `basis`. Use `change` for the concrete mechanism and necessary coupled parts, `expected_observation` for its predicted effect, and `validation` for the comparison that could support or contradict it. Predict an observable behavior, a plausible failure and how either outcome changes the next action; invented numerical gains are unnecessary. Keep useful deferred or rejected findings in the same notes with their reason.

Choose validation from [the local evaluation guide](local-evaluation.md): align the scorer and independent units with the competition, compare matched candidates, and preserve independent confirmation. Public leaderboard feedback can expose a mismatch, but repeated public-score selection cannot replace local evidence. For a learning-only request, deliver the explanation and its implications within that scope.

## Worked Example: Source Evidence to a Dispatch Proposal

The [JSSP behavior example](strategy-design.md#worked-example-jssp-dispatch) starts from inspected HeurAgenix source at commit `e84bfb19e785ae2d670af6e3ab68890c71c536ea`: its [base rule](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/src/problems/jssp/heuristics/basic_heuristics/shortest_processing_time_first_c374.py#L23) ranks next-operation duration, while the [readiness rule](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/src/problems/jssp/heuristics/evolved_heuristics/shortest_processing_time_first_d471.py#L53) reads machine/job end times. Assume a task's archived parent uses the base rule and exposes those states. This is a proposal illustration, not a selected competition or a measured improvement.

Retain the relevant source passages, pinned URL and actual snapshot hash in that task's notes. After checking the real parent, express the finding through the existing fields:

| Field | Content for this hypothetical proposal |
| --- | --- |
| `basis` | Cite the pinned source and saved path/hash; explain that the parent ranks duration and cannot distinguish available jobs by their machine/job readiness. State that the source establishes an implementation, with full-objective transfer still unknown. |
| `change` | Maintain accurate operation indices and machine/job end times, rank by the next operation's feasible start, and feed the selected job through the legal state-update operator with defined tie-breaking. |
| `expected_observation` | In the stated A/B state, selection changes from A to B; this may avoid reserving the machine for a job ready much later. Earlier starts may still delay critical-path work and worsen final makespan. |
| `validation` | Use the hand calculation to distinguish the rules; if implementing, inspect the actual selection/update path and compare complete valid schedules with the parent under one unchanged development protocol and resource limit. |

Use real archived parent/feedback IDs and code targets when recording this proposal; the source document is supporting material, not an ID for `feedback_from`. The [execution follow-through](iteration-trace.md#worked-follow-through-readiness-dispatch) shows how actual implementation and results, once available, determine the next action.
