# Numeric Tabular Training

Use `scripts/tabular_training.py` for finite numeric features and scalar regression (`rmse`, `mae`) or binary classification (`binary_log_loss`, `roc_auc`, `accuracy`). This adapter performs actual fitting; the prediction tools also score saved predictions without fitting. It does not prepare arbitrary Kaggle datasets, support multiclass/image/text tasks, or submit to a platform.

## Setup and Candidate Interface

Reuse the task's numeric environment for prediction scoring and optional tabular fitting. If none exists, create an isolated environment; archive-only operations and the other adapters do not need these packages:

```sh
uv venv /absolute/path/to/tabular-env --python /usr/bin/python3
uv pip install --python /absolute/path/to/tabular-env/bin/python \
  -r /absolute/path/to/competition-optimize/scripts/requirements-tabular.txt
```

A candidate is a single Python source file exposing `build_model(seed, task)`. Return a fresh sklearn-compatible estimator or pipeline. Keep learned preprocessing **inside** the returned pipeline. Use installed dependencies; snapshot any additional implementation dependencies before extending this single-file interface. For example:

```python
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge, LogisticRegression

def build_model(seed, task):
    estimator = (LogisticRegression(random_state=seed, max_iter=2000)
                 if task == "binary" else Ridge(alpha=1))
    return make_pipeline(StandardScaler(), estimator)
```

The adapter gives each fit only the declared training features/labels. It records the rows and saved model bytes. Candidate Python and joblib files are trusted executable code: this is not a sandbox or proof that arbitrary code did not read other files. Upstream features, external data permission and prior holdout exposure still require task-specific review.

Before claiming a capability gap, inspect the model's mapping and objective. An RBF kernel, including its Nystroem approximation, can represent nonlinear interactions already; explicit product columns change its geometry and regularization and may help, but do not introduce nonlinearity into an otherwise additive model. Attribute a gain to the executed comparison unless a targeted analysis supports the stronger mechanism claim.

## Verify Supervised Preprocessing Information Flow

The adapter's fit-row receipt establishes which rows were passed to `estimator.fit`; it does not prove what each nested transformer passed to its downstream estimator. Review the actual `Pipeline`/wrapper call path when a proposal relies on cross-fitting, target statistics, feature selection or stacking.

In sklearn's [TargetEncoder](https://scikit-learn.org/1.7/modules/generated/sklearn.preprocessing.TargetEncoder.html), internal cross-fitting runs in `fit_transform(X, y)`. `fit(X, y).transform(X)` uses encodings fitted on all those labels. Setting `cv=5`, checking `categories_`, or comparing a stored encoder's `transform` with itself cannot distinguish these paths. The [official example](https://scikit-learn.org/1.7/auto_examples/preprocessing/plot_target_encoder_cross_val.html) demonstrates the resulting overfitting risk.

`Pipeline`/`ColumnTransformer` directly containing `TargetEncoder` uses its `fit_transform` during fitting. A custom `TransformerMixin` wrapper with only `fit` and `transform` defaults to `fit(...).transform(...)`, which can bypass the encoder's cross-fitting. Prefer direct composition where suitable; otherwise implement the wrapper's training transformation explicitly and retain a full-fit encoder for later inference. Return the cross-fitted training block to the downstream model; do not overwrite it with the full-fit `transform` result. Inner splits must respect the task's group/time boundary when required; plain KFold is not universally appropriate.

For this kind of defect, use a small deterministic synthetic fixture before another competition fit:

- Fix the inner partitions and all features; change labels only in one held-out inner block. That block's training encoding should stay unchanged when its own labels are excluded, while an intentionally self-inclusive implementation should fail the check. Choose continuous labels or explicit task type so perturbation does not change the splitter's inferred target type.
- Exercise the actual wrapper inside a pipeline with a recording downstream estimator. Verify what fitting receives, the difference from full-fit inference on a non-degenerate fixture, and unseen-category behavior based only on fit rows.
- Check inference after serialization and ensure external validation labels never enter fitting. Reuse the repaired run's saved objects for verification rather than fitting the full candidate twice.

These behavioral checks establish the tested information boundary, not universal absence of leakage. A training-row encoding defect does not automatically invalidate an outer OOF score if outer validation labels were kept out. Preserve historical runs, correct the overstated provenance, and evaluate a separate repaired candidate under the unchanged outer protocol; do not retain defective code merely to preserve its score. Track raw historical scores separately from the implementations eligible under the corrected requirement when they differ.

For custom leave-one-out or smoothed encodings, include the fallback prior and partition construction in that review. Subtracting a row's label from its group sum still leaves self-dependence if the smoothing prior includes it. Test the actual emitted encoding after the relevant label perturbation and declared fixed partition, not just group counts or a manually reconstructed branch. Report the residual dependence if intentionally retained; an unchanged group sum does not establish an unchanged feature.

## Freeze the Fold Protocol Before Comparing Candidates

The training CSV contains unique string IDs, declared numeric feature columns, the target and any split metadata. Binary targets are exactly 0/1; each training fold needs both classes. Column names default to `id`, `target`, `prediction` and may be overridden in the protocol.

```json
{
  "schema_version": 1,
  "task_id": "my-task-v1",
  "task": "regression",
  "metric": "rmse",
  "score_kind": "proxy",
  "features": ["x1", "x2"],
  "split": {"kind": "group", "group_column": "patient"},
  "expected_oof_ids": ["a", "b", "c", "d"],
  "folds": [
    {"id": "0", "seed": 1729, "train_ids": ["c", "d"], "validation_ids": ["a", "b"]},
    {"id": "1", "seed": 1730, "train_ids": ["a", "b"], "validation_ids": ["c", "d"]}
  ]
}
```

This example assumes groups in the two partitions are disjoint. `iid` and `group` require exactly one OOF prediction for every data row. `time` and `group_time` allow a declared warmup set excluded from `expected_oof_ids`; every row must still be used in some train/validation fold. Validation IDs cannot repeat across folds. The metric is pooled over all declared OOF rows, **not** the mean of fold scores. No default fold or seed search is performed.

For `accuracy`, use numeric 0/1 targets and declare `decision_threshold` in the protocol when the default `0.5` is unsuitable. OOF decisions use `probability >= threshold`; frozen inference averages fold probabilities before applying that same threshold. The threshold is part of the sealed recipe. Numeric evaluation CSVs remain 0/1; delivery preserves `True`/`False` when the official sample uses that encoding.

When a mechanism depends on related rows, declare its inference premise before fitting, for example `"relations": [{"column": "household", "inference": "new_groups", "rationale": "Official test household IDs have zero overlap with train"}]`. Pass unlabeled metadata with `--inference-data test-features.csv`. The adapter checks the fraction of inference/validation rows whose group appears in the relevant fit set. `new_groups` requires zero overlap; `known_groups` requires full overlap; `mixed` reports fractions without imposing a tolerance. Choose the premise from task facts, not favorable scores. This checks declared relations and cannot discover an omitted relation.

For temporal protocols, set `time_column`, `time_format` (`number` or timezone-aware `iso8601`), optional `available_time_column`, and optional nonnegative `minimum_time_gap` under `split`. Each validation period must follow both the latest training event and label-availability timestamp by the declared gap. Combine with `group_column` using `group_time` when both restrictions apply. The same checks apply between development data and confirmation/final features; final features need event/group metadata, but not future label-availability timestamps.

## Train, Compare, Freeze, Confirm

Keep training outputs together under an existing `runs/` parent. A failed fit leaves its launch and per-fold journal, without a successful manifest. See recovery below before repeating it.

```sh
PY=/absolute/path/to/tabular-env/bin/python
S=/absolute/path/to/competition-optimize/scripts
$PY "$S/tabular_training.py" train --data training.csv --protocol folds.json \
  --candidate candidate.py --output-dir runs/baseline
# Record a successor proposal before fitting, then bind it at launch.
$PY "$S/tabular_training.py" train --data training.csv --protocol folds.json \
  --candidate changed.py --archive archive.jsonl --proposal-id mechanism-01 \
  --output-dir runs/challenger
$PY "$S/compare_prediction_results.py" \
  --baseline runs/baseline/evaluation/result.json \
  --candidate runs/challenger/evaluation/result.json --truth runs/baseline/truth.csv \
  --output runs/development-comparison.json
$PY "$S/tabular_training.py" freeze --run runs/challenger \
  --decision-rule 'Apply the predeclared independent confirmation rule; otherwise retain the baseline' \
  --output-dir runs/frozen
$PY "$S/tabular_training.py" confirm --frozen runs/frozen \
  --data confirmation-features.csv --truth confirmation-truth.csv --output-dir runs/confirmation
$PY "$S/tabular_training.py" predict --frozen runs/frozen --data test-features.csv \
  --sample-submission sample_submission.csv --output-dir runs/final
```

Choose the candidate from development evidence before `freeze`; the example command is not a direction to select the challenger regardless of results. Freeze all finalists and the actual selection/delivery rule before reading confirmation labels. `freeze` copies and seals source, protocol, data, OOF, fitting receipts and model files. Later commands recheck those bytes and recorded Python/package environment before loading the models. The fixed inference recipe is the arithmetic mean of all frozen fold models; it does not retrain on holdout rows or tune blend weights. The tool records the decision rule but does not interpret natural language or automatically promote a candidate.

`confirm` checks ID/group/time separation, predicts with frozen models, then reads the separate confirmation truth file and produces a normal prediction result with `stage=confirmation`. Keep it out of development decisions. `predict` verifies the exact sample ID set, column names and order; it writes predictions in sample order plus a hash receipt. Sample format is exactly the ID and frozen submission column. Upload remains a separately authorized action.

## Inspect Saved Fold Models Without Fitting

Use existing `oof.csv` or `predictions.csv` when the question only needs predictions. When a diagnostic needs fitted members, preprocessing or behavior on a constructed input, use `SavedTabularRun` from the snapshot's `scripts/tabular_training.py` instead of registering candidate modules and calling `joblib.load` by hand:

```python
from pathlib import Path
from tabular_training import SavedTabularRun, csv_rows, matrix, predictions, runtime

left = SavedTabularRun(Path("runs/parent"))
right = SavedTabularRun(Path("runs/challenger"))
left_model = left.load_model(left.fit["folds"][0]["fold_id"])
right_model = right.load_model(right.fit["folds"][0]["fold_id"])

np, _, limits = runtime()
fold = left.fit["folds"][0]
identifier = left.protocol.get("id_column", "id")
_, rows = csv_rows(left.root / "training.csv", [identifier, *left.protocol["features"]])
x = matrix(np, rows, fold["validation_ids"], left.protocol["features"])
with limits(limits=1):
    values = predictions(np, left_model, x, left.protocol["task"])
```

For member-level diagnostics on a sklearn Pipeline, obtain each model's own saved feature representation with `left_model[:-1].transform(x)` and `right_model[:-1].transform(x)`, then inspect their final estimators through `model.steps[-1][1]`. The two representations may differ even when their shapes match. This also works when transforms reference candidate-defined functions; the reader already binds their source. Do not import the candidate a second time to reconstruct those transforms. Use `prediction_core.calculate_metric` for array scores.

The reader accepts sealed training and frozen runs, checks their manifests and recorded environment, and rechecks source/model bytes before loading a fold by its recorded ID. Each run gets its own source namespace; historical `competition_candidate` pickle references resolve temporarily to that run, and the caller's previous alias is restored on success or failure. Custom classes with the same name but different implementations and candidate-defined transform functions can coexist. `predict` and `confirm` use this reader too.

Pass raw numeric features in that model's declared order to the full saved pipeline; it includes its own derived-feature and preprocessing steps. If a member diagnostic intentionally bypasses pipeline stages, apply the fitted upstream stages once and verify the member's actual input contract. Do not refit an unchanged estimator just because an inspection script used the wrong module or feature shape. Compare fold records explicitly when crossing runs; the reader does not establish matched splits or candidate comparability.

This is a single-threaded reader for trusted candidate code, not a sandbox. It performs no fitting or artifact writes; use it for analysis/prediction, and keep model creation/serialization in the managed training path. It cannot restore optional dependencies or implementation files that were never snapshotted.

## Freeze the Submission Schema and Target Scale

Internal evaluation columns and target units need not match the official CSV. At `freeze`, declare `--submission-column` when the official target name differs, and `--inverse-transform` when model predictions require a target inverse. Defaults preserve the protocol prediction column and use `identity`. Supported regression inverses are `exp` for a target trained as `log(y)` and `expm1` for `log1p(y)`. Choose from the actual preprocessing/model output contract; an estimator that already returns original units needs `identity`. Do not infer units from plausible-looking values or apply the inverse twice.

For example, when the protocol evaluates log-price predictions and the official sample expects `Id,SalePrice`:

```sh
$PY "$S/tabular_training.py" freeze --run runs/selected \
  --decision-rule 'The previously declared selection and confirmation rule' \
  --submission-column SalePrice --inverse-transform exp --output-dir runs/frozen
$PY "$S/tabular_training.py" predict --frozen runs/frozen --data test-features.csv \
  --sample-submission official-sample.csv --output-dir runs/final
```

The frozen manifest binds the column mapping and inverse. `predict` averages fold outputs in their existing target space, applies the inverse once, and writes `submission.csv` using the official sample's IDs and order. It rejects invalid columns, a mismatched sample, non-finite transformed values and `exp` underflow. Binary prediction keeps its existing probability/decision behavior and permits only `identity`; accuracy delivery preserves a boolean sample encoding.

`predictions.csv` retains the evaluation column and scale. `confirm` always scores these unconverted predictions against truth in the declared evaluation space, even when submission uses an inverse. No extra training occurs. Older frozen manifests without this declaration retain their original identity behavior; create a new freeze from the saved training run when a different mapping is needed, preserving the original frozen directory.

Read `submission_path` and `submission_hash` from `delivery.json` or the returned JSON for the actual final file; `raw_prediction_path` and `raw_prediction_hash` identify evaluation-space predictions. `prediction_path`/`prediction_hash` retain the existing meaning of the primary emitted file (submission for `predict`, raw predictions for `confirm`). The receipt also records the frozen submission mapping and sample hash. Avoid reconstructing directories or handwritten postprocessing after this receipt: that would produce different bytes from the verified submission.

## Proposal Binding, Reuse and Interrupted Costs

For a proposed tabular successor, pass `--archive` and `--proposal-id`. Before importing candidate code, the adapter validates the open proposal and saves its exact hash and archive prefix in `execution.json`. `candidate_archive.py record` verifies this receipt, inputs, recipe, sealed files and fit costs. A managed run trained without this binding cannot later fulfill a newly written proposal. Initial baselines and standalone legacy use can run without a proposal and are marked `unregistered`; legacy results without execution evidence remain readable without a claim about proposal timing.

An identical request automatically reuses a verified completed sibling run when only `--output-dir` changes or a completed output is requested again. Identity includes exact source/data/protocol bytes, seeds, inference metadata, Python/packages, adapter and evaluator. The copy retains the original seal and `execution_id`; the returned receipt says `new_fit_calls: 0`. It cannot acquire a later proposal identity. Changed scoring may reuse predictions by reevaluating them, but does not silently reuse an old scoring contract through training.

When installed scorer code has changed but a development comparison must retain its existing contract, use the original run's sealed OOF with the exact saved scorer that produced a valid reference result:

```sh
$PY "$S/tabular_training.py" rescore --run runs/challenger \
  --evaluator /path/to/saved/scripts/evaluate_predictions.py \
  --reference-result runs/reference/evaluation/result.json \
  --output-dir rescored/challenger
```

`rescore` requires the selected scorer's dependencies. It verifies the original training manifest, checks the saved scorer's fingerprint through the shared identity function, copies it and its sibling `prediction_core.py`, and carries the original metric, column names, split and score-kind into evaluation. New scorers bind numerical-library versions; old source-only scorers retain their original identity format. It rejects a changed input contract or reference from confirmation. It never imports candidate code, loads models or fits; a different score recipe requires a separately declared evaluation. A scorer mismatch is a reason to locate the matching saved scorer and environment, not to relabel the evaluator hash.

The new directory preserves the reference, scorer, output and failures without changing the original run. A successful result links the original training seal and execution receipt; archive it using `--configuration ORIGINAL_RUN/recipe.json` and its original bound `--proposal-id`. Archive recording verifies that link and keeps the original fit cost and proposal timing. `new_fit_calls: 0` describes this rescore; `originating_cost` describes the training that generated its predictions. Count the original execution once with `cost --run ORIGINAL_RUN`, not as another fit for each rescore. Older runs without a managed receipt can still use the standalone prediction scorer, but cannot gain retrospective proposal evidence.

The adapter durably appends `fit_started`, `fit_completed` or `fit_failed` for every fold. A killed fit remains `unresolved_fit_calls`, with unknown duration instead of zero. After an incomplete identical attempt, automatic repetition is refused; inspect its journal, then supply `--retry-reason 'actual reason'` in a fresh directory only when a new attempt is useful. This flag also permits an intentional planned repeat of completed work, which remains a measurement of the same implementation. Partial folds are not automatically resumed.

```sh
$PY "$S/tabular_training.py" cost --run runs/failed --run runs/repaired --run runs/copied
```

When recording a managed run, pass its saved `--result` and `--configuration` to the existing archive command, with its bound `--proposal-id` when applicable. Verified training costs are imported automatically. Optional `--cost` is for extra measured resources; do not reconstruct or override `training_execution` from JSON fields. Use the `cost` command above for totals across attempts.

`cost` includes failed/unresolved calls and deduplicates copied `execution_id` values. Archive recording attaches the verified originating cost under `cost.training_execution`. These figures count adapter-level `estimator.fit` calls and measured fit/workflow time; nested estimator fits, research, agent time, tokens and money need separate evidence. Sibling reuse assumes one writer and does not control arbitrary training scripts.

## Artifacts and Archive Identity

- `candidate.py`, `protocol.json`, `training.csv`: snapshotted implementation and inputs.
- `recipe.json`: stable implementation identity containing the actual candidate source, feature/data identity and environment; it excludes output bytes, elapsed times and fold measurement seeds.
- `models/fold-N.joblib`, `fit.json`: trained models, actual fit rows, seeds, timings, package versions and unchecked scope.
- `execution.json`, `fit-events.jsonl`: pre-import input/proposal binding and durable fold attempts; `cost --run` reads these even when training failed.
- `oof.csv`, `truth.csv`, `evaluation/result.json`: complete OOF and normal scorer evidence, usable with existing prediction comparison/error tools.
- `manifest.json`: hashes of every run artifact; frozen copies additionally bind the training seal, delivery rule, submission column and target inverse. Paths inside the manifest are relative, so a complete frozen directory can move without rewriting its seal.
- `delivery.json`, `predictions.csv`, `submission.csv`: frozen identity, raw/final paths and hashes, target mapping and validated final row order. Confirmation emits raw predictions only.

For candidate archiving, the prediction hash identifies output, not implementation. Pass `--configuration RUN/recipe.json` to bind the actual candidate source, feature/data identity and environment. The fold protocol remains independently sealed in the evaluation and training manifest. Do not use elapsed time or fitted model/prediction hashes as implementation identity: repetitions of an unchanged recipe remain measurements of one implementation. Archive the normal result and retain `fit.json`/manifest as its fitting evidence. Confirmation results keep the confirmation role.

`examples/tabular_training_pilot.py` in the repository demonstrates real baseline/challenger OOF fitting, frozen confirmation and final CSV on bundled raw Diabetes data. It is a reproducible integration exercise, not a benchmark of autonomous contest gains.
