# Resume and Choose the Next Action

Use this when continuing a run, recovering an interrupted trial, or deciding whether more research or diagnostics would help. The contract, append-only ledger, and immutable artifacts are the evidence; `next-action.md` is a replaceable summary. It neither grants extra budget nor establishes candidate validity.

## Recover Only What Changed

Read the sealed contract and the compact card first. Check the contract bytes against the card's hash and the ledger prefix against its checkpoint (byte length and SHA-256); these checks can read bytes without loading all events into model context. If both match, read only appended complete events and the evidence needed for the current decision. Verify the dependencies and validity scope of results you intend to reuse. A hash confirms identity, not training provenance or unchecked hard rules.

If the card is missing, its prefix differs, or the contract changed, rebuild relevant state from the ledger and artifacts. Contract changes invalidate dependent conclusions; they do not erase spent trials. No new event does not prove that an unfinished evaluation failed: inspect its process and output directory before retrying. A successful result missing a completed event can be reconciled only after verifying its completeness, dependencies, and hard checks, then appending the recovered outcome. A truncated final event or partial result remains unresolved; do not invent a completion or overwrite old evidence. Resolve a ledger write failure before appending more events; preserve damaged bytes and record the repair.

Reconcile consumed and remaining trials/time/compute, the confirmation/packaging reserve, the incumbent's promotion scope, alternatives, unfinished work, and frozen shortlist. If records do not establish remaining budget, state the gap and account for visible work conservatively; never reset the allowance. When further improvement is requested after delivery, retain the selected incumbent and spent budget. Further search needs remaining authorized budget and fresh confirmation if earlier confirmation feedback is used for tuning; otherwise deliver the existing evidence and explain the limit.

## Route the Current Decision

Choose the first applicable condition; this is routing within the current run, not a sequence to replay every turn.

| Current state | Next useful action | Exit condition |
| --- | --- | --- |
| An unfinished trial may already have evidence | Reconcile its artifacts/process and actual cost | Record verified completion, interruption, or failure before another trial |
| Hard rules, score meaning, or comparison dependencies are unresolved | Resolve the specific contract/measurement defect | A trustworthy comparison path or an explicit provisional limitation |
| No credible action fits outside the reserve | Freeze/confirm the shortlist, or deliver if confirmation is done | Apply the sealed delivery rule; preserve remaining uncertainty |
| No valid credible baseline exists | Establish one affordable reference | Validity, objective, and measured cost for subsequent comparisons |
| Ranking or mechanism uncertainty prevents choosing a trial | Run a targeted diagnostic or matched repetition | A stated result changes promotion or identifies a testable mechanism |
| An affordable falsifiable mechanism is ready | Execute its cheapest useful rejection test | Reject, advance to matched full fidelity, or identify missing evidence |
| Missing knowledge prevents a viable mechanism | Search for that specific gap | A source-backed test with prerequisites, or retire the route |

Resolve a rules/scoring defect within the authorized budget even when search is exhausted; do not report an invalid comparison as confirmed. An infrastructure failure warrants a bounded repair when useful, not a fresh algorithm conclusion. Repair variants consume trial slots; rerunning unchanged candidates consumes time/compute under the sealed protocol.

Before execution, ask: which observation changes the next decision, which evidence can be reused, and does implementation + execution + analysis + possible full-fidelity follow-up fit outside the reserve? Use measured costs where available and label estimates. No plausible decision change means defer that action. Full-fidelity promotion, provenance checks, and confirmation remain necessary even when intermediate work is cached.

Keep rejected hypotheses with their mechanism, prerequisites, and rejection evidence. Reopen one when a dependency, implementation diagnosis, or new source changes that evidence. A new filename or another request to continue is not new evidence. After a failure, update the mechanism or switch route; do not regenerate the same configuration through repeated broad searches.

## Compact Decision Card

Refresh `<run>/next-action.md` after a decision or before a handoff, not after every tool call. Keep only facts needed for the next action and link to details; it is disposable and never replaces ledger events. The checkpoint covers complete JSONL events through the recorded byte offset. Later events must be reconciled before acting. Do not checkpoint a partial final line.

Use the fields relevant to the task; this is a copyable example, not a required adapter schema:

```markdown
# Next action

Contract: task-contract.json; SHA-256: <contract hash>
Ledger checkpoint: <byte length>; prefix SHA-256: <hash>; last event: <trial/event/time>
Incumbent: <ID>; scope: <development/provisional/confirmed>; evidence: <result and checks>
Alternatives: <IDs and the uncertainty worth preserving>
Budget: <consumed / authorized trials, time, compute>; reserved: <confirmation + packaging>
Unfinished: <trial ID and output/process, or none>
Frozen shortlist: <path/hash, or not yet frozen>

Next action: <one action and parent IDs>
Question and prediction: <what is uncertain and the expected observation>
Evidence to reuse / invalidate: <paths, dependency hashes, affected descendants>
Execution: <command or implementation target, stage/fidelity, resource cap, total cost estimate>
If rejected / promising: <next branch, including full-fidelity cost when needed>
```

An old run needs no migration: rebuild a card only when resuming it. A tiny completed run may have nothing unresolved beyond delivery; do not create a new hypothesis queue just to fill the template. Source details stay in `research.md`, candidate history in `trials.jsonl`, and final selection in the frozen shortlist and delivery evidence. Record only aggregate confirmation outcomes needed for the delivery rule, never tuning suggestions extracted from confirmation errors.
