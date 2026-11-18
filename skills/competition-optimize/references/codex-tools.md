# Use Codex Tools for Competition Research and Implementation

Use tools to change a consequential decision or deliver the requested implementation. Prefer direct evidence and inexpensive computations to unsupported reasoning or another full training run. Select the relevant actions below; this is not a per-turn tool quota or a requirement to use every capability.

## Start with the Actual Invocation

Use the tools and argument schemas exposed to the agent that will execute the work. A parent chat, CLI feature flag or model alias does not establish browser, search, MCP or sub-agent support in a background invocation. Reuse an already established capability while its environment remains applicable; revisit it after a relevant change or an actual failure, rather than rediscovering the whole tool catalog each turn. Preserve the task's chosen model and provider.

If a preferred tool is absent or fails, inspect the actual error and choose an available equivalent. A missing native browser can leave terminal source readers usable; one endpoint's authentication or transport failure does not show that all public sources are inaccessible. Conversely, an enabled feature is not proof of a successful call. Keep unresolved capability limits explicit in existing task notes when they affect the next action. Tool access does not change the task's data boundaries or authorize external writes.

Reuse interpreter and dependency paths already recorded by the task. A shell name such as `python3` can resolve to an unrelated wrapper even when a suitable interpreter is installed. Use the established absolute executable; after a failure, distinguish command resolution from a missing package before installing anything or inspecting tool internals. A supplied development brief already contains verified retrieval results; call brief/trace again only for missing evidence relevant to the current choice.

## Call Existing Operations Before Writing Code

When an existing tool can perform the required operation, call it directly. Check exposed tools, repository entrypoints, suitable CLI/SDK commands and installed library interfaces before writing a helper. Read their schemas, help or a relevant existing example when usage is unclear. Do not reimplement search/browsing, source retrieval, authentication, process polling, model loading or archive operations already supplied by a suitable interface. A failed invocation calls for inspecting and correcting that invocation; it does not by itself justify a replacement implementation.

Write code only for a concrete uncovered operation, the new competition mechanism, or the minimum glue between existing capabilities. State the actual gap in the existing proposal or notes when it matters to the implementation choice; no extra approval form or tool survey is required. Reuse the underlying library operations while implementing a novel mechanism. This keeps original algorithm development possible without rebuilding its supporting infrastructure.

## Reuse the Existing Numeric Operations

| Required operation | Existing interface |
| --- | --- |
| Score saved CSV predictions | `evaluate_predictions.py` or `evaluate_prediction_batch.py`, using the task's numeric environment |
| Score arrays inside a mechanism-specific diagnostic | `prediction_core.calculate_metric`; accepts lists, tuples and one-dimensional NumPy arrays. For repeated row draws, prepare once with `prediction_core.prepare_metric` and pass each draw's indices to the returned scorer |
| Inspect fitted objects or preprocessing | `tabular_training.SavedTabularRun.load_model(fold_id)` for each run; inspect the loaded estimator through its existing API. Apply each pipeline's own `pipeline[:-1].transform(x)` before accessing members of its final estimator; do not share the challenger's transforms with its parent or manually register candidate modules |
| Recompute a fixed prediction change | [Reuse matched OOF or fitted fold artifacts](tabular-training.md#reuse-fitted-artifacts-for-prediction-only-changes); `tabular_training.predictions` reads full pipeline output in model units. Apply the declared rule and score a new artifact with the same evaluator contract |
| Check whether a convex blend can improve on two fixed parents | `analyze_prediction_errors.py --check-blend-direction` on matching RMSE or MAE development results and their truth CSV. Returns endpoint derivative signs, without selecting a weight or scoring a new recipe |
| Attach a managed training result | `candidate_archive.py record --result RUN/evaluation/result.json --configuration RUN/recipe.json`, with the original bound proposal when applicable. The recorder verifies and imports training cost automatically; omit `training_execution` from optional `--cost` |
| Total actual fitting costs, including failed attempts | `tabular_training.py cost --run RUN_A --run RUN_B`; repeated copies of one execution are counted once |

For Kaggle discovery, inspect the existing reader's output rather than writing an envelope parser: default leads are at `source.sources`; `--format source` prints the normalized document with `sources` at the root. See [the reader's output contract](kaggle-sources.md#discover-and-read).

Use [zero-fit rescoring](tabular-training.md#proposal-binding-reuse-and-interrupted-costs) when an unchanged prediction artifact needs a saved evaluator's contract. Preserve the old scorer and results; do not recreate the formula or change their hashes by hand. These interfaces leave new mathematical mechanisms and task-specific diagnostics open for implementation.

Describe diagnostic cost by the actual operations and elapsed time. Loading models, reusing sufficient statistics, solving new coefficients and calling `estimator.fit` are different operations. Zero calls to that method can still include parameter estimation or a costly search; operation counts alone do not establish that a diagnostic is cheap. Report the solves/refits actually performed and unknown timing without labelling every saved-artifact diagnostic free or requiring another training run.

A reported fit-call count supports only that instrumentation's boundary. It cannot rule out uninstrumented fitting, and solving coefficients is itself parameter estimation even when no estimator API was called. Do not use an operation count to infer a cause of a score improvement or relate it to unrelated row counts.

The campaign passes native Codex `shell_environment_policy.set.SHELLOPTS="pipefail"` on fresh and resumed invocations. Keep the option enabled in Bash commands. Prefer tool output limits or reading a saved log over `| head`: an early reader exit can generate SIGPIPE. Check the command's final status before using its output; error-looking text alone is not a failure detector.

## Choose the Tool from the Missing Evidence

| Current question or action | Useful tool path and required observation |
| --- | --- |
| Which strong method or evaluation assumption applies? | Use available search/web/browser tools to discover and read original discussions, papers and matching code. When native tools are absent, use the existing source reader, SDK or permitted HTTP client. Follow material comments and versions; retain the actual passage and reading limits as in [competition research](competition-research.md). |
| What does the implementation actually compute? | Use file search such as `rg`, targeted reads, language navigation or AST inspection. Follow the input-to-output path and coupled components; do not infer implementation from a function name or search hit. |
| Does a mathematical implication hold? | Use the recorded task interpreter for exact arithmetic, a small constructive example, limiting cases or counterexample search. Use a symbolic algebra package when available and useful. Check assumptions and the actual comparator; finite numerical checks do not prove an unrestricted theorem or generalization. |
| What was already executed or learned? | Use archive `brief`/`trace`, saved predictions and the verified saved-model reader. Recover source/result identities before repeating work; loading or rescoring a model need not fit it again. |
| Where does a candidate change behavior or error? | Inspect existing traces, per-fold/regime losses and prediction differences. Plot or view an image when it makes structure easier to assess. Keep the observation separate from the proposed cause. |
| How should the understood mechanism be implemented? | Use the available patch/edit tools in the task's isolated source or run directory. Inspect the diff, run focused interface/correctness checks, and preserve the executed snapshot. Use existing experiment directories or an appropriate worktree when competing changes need isolation. |
| Is a long-running command complete or failed? | Retain the tool's session/process handle; poll or wait with the supported interface, read incremental output and the final exit status. Track owned jobs and costs, join local children before returning, and reconcile uncertain results before retrying. A launched command is not a successful experiment. |
| Can independent work proceed together? | Batch independent searches, file reads, source fetches or unrelated checks with the available concurrency primitive. Inspect every success/failure. Keep dependent edits, state transitions, uncertain retries and consequential shared-resource timing comparisons ordered. |
| Would independent agent work improve a material decision? | Where delegation is authorized and supported, give bounded independent tasks with explicit evidence and integration responsibilities. Verify that child model/provider routing honors the task's requirement; otherwise use tool-level concurrency. The coordinating agent still checks results and owns the final implementation. |

## Observe, Then Route

Associate a tool action with the question it answers and inspect the returned evidence before continuing. When output is truncated, read the necessary saved range or a bounded summary; truncated output cannot establish absence. Follow source links or inspect the changed code when a result leaves the decisive premise unresolved. Once the evidence supports an implementation choice, execute it instead of continuing broad discovery.

Use the environment's actual interpreter and installed dependencies, including task-specific virtual environments; a familiar executable name can resolve to a wrapper. Use a small local script only for an operation not covered by suitable existing tools or interfaces. Add a dependency or reusable helper only for that demonstrated gap. Do not replace available native tooling with another agent framework or repeatedly rebuild one-off shell machinery.

Check the actual installation boundary when a package is absent. A prohibition on global installation does not prohibit adding a dependency to an authorized task virtual environment. Keep missing dependencies and failed implementations separate from evidence that an algorithm cannot help.

Classify failure at its observed boundary: a nonblocking startup warning, unavailable tool, transport/authentication problem, command error and valid negative experiment have different consequences. Repair the path needed for this decision, preserve its failure evidence, and continue independent authorized work. An alternative access path must retain the original authorization and verification requirements.

Judge tool use by what it established, which uncertainty it removed, or which execution cost it avoided. More calls, screenshots, parallel jobs or agents do not by themselves demonstrate stronger research or a better competition result.
