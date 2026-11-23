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

## Check the Actual Feature Consumer Before Fitting

When a changed or reportedly broken stage decides whether to spend on a fit, trace the real `build_model` and pipeline calls. Use a discriminating development case or small synthetic fixture. Run the actual feature producer through the wrapper and selector that consume it and inspect the values and their column identities at the downstream estimator. For example, a new column can be nonconstant in the feature frame and still be dropped by a fixed selector. Vary its input through the real caller and compare the selected columns and values with the control; calling the feature helper alone would miss the drop.

For filters with physical thresholds, pass rows on both sides of the threshold through the actual stage and check the units it receives. Filter in the original units or transform the cutoff consistently. Build physical aggregates from the original measurements before applying a nonlinear transform to the aggregate. In Lavanya Shukla v29, cell 28 transforms prices with `log1p` and cell 32 applies dollar thresholds to those values. On the official training table this drops two rows. Applying the predicates in dollars would drop three. Cell 47 also fits Box–Cox on selected columns before cell 52 sums area inputs. Any transformed input in that sum changes its meaning as a physical area. [Lavanya Shukla v29](https://www.kaggle.com/code/lavanyashukla01/how-i-made-top-0-3-on-a-kaggle-competition?scriptVersionId=15419856)

For a change to a wrapper's decision rule, use the actual `build_model`, `fit` and prediction methods with deterministic outputs from unchanged members. For example, use Python's `unittest.mock.patch` on the unchanged member constructors while leaving the wrapper and its splitter active. Give the members different predictions so the expected change can be checked at the scored output. For a learned gate, exercise a group that should change and an unseen group that should use the fallback. Use different fit and prediction row counts when the rule carries row-dependent state.

When compatible saved fits exist, replay the real prediction path using each member's fitted transforms and the task's declared interpreter. Reproduce the control and then exercise the change through the same consumer. A full small fit is useful when the question requires new learned state or its interaction with the pipeline. Fit only the needed stages when the rest can be reused. Keep real columns and fit/score boundaries, including capacity for the actual inner splits, and estimate cost from the nested work as well as the row count. Record what the check exercised and its cost in the existing proposal or notes. Use a matched run for the performance comparison. [Saved fold models](#inspect-saved-fold-models-without-fitting) · [Supervised fitting](#verify-supervised-preprocessing-information-flow)

If a transform selects a domain from fit data and then raises on a valid scoring row, inspect the actual selection and inputs at both boundaries. A nonnegative observed minimum in the fitting rows gives no guarantee about unseen rows. For example, an age derived from two dates can be negative on a rare input even when every age in a small training slice is positive. Retain that case, check whether the declared folds and inference path encounter it, and scope the conclusion to the contexts tested. An alternate fixture can test the wrapper while the transform's input-domain question remains open.

## Verify Supervised Preprocessing Information Flow

The adapter's fit-row receipt establishes which rows were passed to `estimator.fit`; it does not prove what each nested transformer passed to its downstream estimator. Review the actual `Pipeline`/wrapper call path when a proposal relies on cross-fitting, target statistics, feature selection or stacking.

In sklearn's [TargetEncoder](https://scikit-learn.org/1.7/modules/generated/sklearn.preprocessing.TargetEncoder.html), internal cross-fitting runs in `fit_transform(X, y)`. `fit(X, y).transform(X)` uses encodings fitted on all those labels. Setting `cv=5`, checking `categories_`, or comparing a stored encoder's `transform` with itself cannot distinguish these paths. The [official example](https://scikit-learn.org/1.7/auto_examples/preprocessing/plot_target_encoder_cross_val.html) demonstrates the resulting overfitting risk.

`Pipeline`/`ColumnTransformer` directly containing `TargetEncoder` uses its `fit_transform` during fitting. A custom `TransformerMixin` wrapper with only `fit` and `transform` defaults to `fit(...).transform(...)`, which can bypass the encoder's cross-fitting. Prefer direct composition where suitable; otherwise implement the wrapper's training transformation explicitly and retain a full-fit encoder for later inference. Return the cross-fitted training block to the downstream model; do not overwrite it with the full-fit `transform` result. Inner splits must respect the task's group/time boundary when required; plain KFold is not universally appropriate.

For example, to append one already-built final column to a supervised base transformer, use `ColumnTransformer([("base", base, slice(0, -1)), ("extra", "passthrough", [-1])])` when that matches the array contract. It preserves the base transformer's training call. Recheck the emitted training matrix after changing this composition: unchanged non-target members, correct row boundaries and an earlier encoder audit do not prove a new wrapper preserves cross-fitting.

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

For an existing primary development comparison, identify its reference result and saved `evaluate_predictions.py` and `prediction_core.py` before training. Check the returned `evaluator_hash` against the reference before comparing or archiving. If the hash differs but the scoring inputs match, rescore the sealed OOF with the reference evaluator and use that result for the primary archive entry. This preserves proposal binding and measured fit cost. See [zero fit rescoring](#rescore-with-the-frozen-evaluator).

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

## Match Saved OOF Before Screening

Use the original training run's `oof.csv` as the reference. Pass the saved predictions to screen as paths.

```sh
"$PY" "$S/prediction_evidence.py" --reference runs/incumbent/oof.csv runs/*/oof.csv
```

The command verifies the prediction, truth and fit receipt against the seal of a tabular training run or its frozen copy. It uses standard Python and reads no model files. Select paths with status `matched` for the fold-matched pool. They have identical truth bytes and the same training and validation members per fold. Row order in the fit receipt, fold names, fold order and seeds are outside this membership comparison. `different_truth` means the sealed truth bytes differ, including any change in their serialization. `different_folds` means the truth bytes match but train or validation membership differs. Missing or inconsistent evidence, including outputs with no tabular training fit receipt, is `unverified` with a reason. An unverifiable reference stops the command.

Keep the report with the decision. Use the reported `oof_sha256` to identify the exact predictions and score identical copies once. Matching fold membership is one input to the comparison. Check prediction scale, scoring units, inference context and which fits produced the members. See [ensemble boundaries](prediction-ensembles.md#reuse-predictions-at-the-right-fitting-boundary).

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

## Reuse Fitted Artifacts for Prediction-Only Changes

Before scheduling a fit, trace the actual build, fit and prediction paths. A fixed output weight or aggregation rule can reuse fitted artifacts when the change does not affect training, fitted preprocessing, member selection or calibration. Check the saved data and protocol, feature order and target scale, and the fit and validation IDs, seeds and environment for each fold of each partition being compared. A newly fitted coefficient or calibrator needs its own [label boundary](local-evaluation.md); reusing members does not make that step fixed.

Use matching saved OOF columns aligned by ID, or load the relevant fold models as above and recover the required member predictions through their own saved transforms. Apply the proposed rule at the same point as intended for inference. A rule within a fold model can differ from one applied after averaging, thresholding or inverse transformation. Before interpreting the comparison, reproduce the saved control with its original rule on each used partition and explain any numerical difference against the recorded precision. If a needed prediction or compatible model is missing, locate it first, then fit only the components and folds required by the declared comparison.

For a batch quantile applied to otherwise row-local predictions, cache each fold's predictions before the quantile and any unaffected member outputs. Use NumPy to recompute the quantile on the values in each context, in the original units with the original tie and singleton behavior. Reapply subsequent blending, averaging and transforms in their original order. Check against direct `predictions(...)` calls on representative contexts and against the saved control. If predicted features or member outputs depend on other rows, recompute those stages too. [Choose the prediction contexts](local-evaluation.md#match-the-prediction-context)

For a fixed affine blend under RMSE, squared error along that direction is quadratic; reuse paired residuals and predictions to reason about or evaluate a declared change. The [existing blend direction check](codex-tools.md#reuse-the-existing-numeric-operations) answers whether an interior convex blend can beat both endpoints on those rows. It supplies neither weights nor validation of a new recipe. A zero-fit grid is still a parameter sweep; do not use it when tuning is out of scope, and do not convert a value selected on those labels into independent evidence.

Score newly composed predictions in a fresh directory with the matching `evaluate_predictions.py` contract. Keep the output rule, input recipe/model identities, and the control reproduction with the evidence. Record an exploratory ablation as `--role diagnostic`; for a declared contender, provide the executed output recipe as `--configuration` and cite how scoring rows were excluded from all fitting/selection stages with `--prediction-boundary`. Do not borrow the parent's `training_execution` or rebind its proposal. The managed `rescore` command below accepts unchanged sealed OOF only.

### Reuse Inner Predictions for a Learned Combiner

Before proposing another gate or stack, inventory two inputs per outer fold. The scored member predictions come from the outer models and use the original scoring context. The combiner's fit inputs come from inner folds within the outer training rows and use the declared training prediction rule. These contexts can differ, for example when the validation batches use a quantile calculated over the entire batch.

If follow-up fits of the combiner are likely, retain its inner predictions and targets or sufficient statistics as fitted attributes in the sealed model. Bind each value to the outer fold's ordered `train_ids` and retain the actual inner train/validation assignments, producer code and prediction rule. Recover the state through `SavedTabularRun`. If only fitted weights or aggregate losses survived, reconstruct the missing inner inputs with the existing branch code and preserve the outer fits where valid. Check the inner split and label boundary before using an existing cache. [Nested validation](local-evaluation.md#fitted-diagnostics-on-stored-predictions)

Use `recompose --control RUN --composition compose.py --output-dir NEW_DIR` when the rule operates on the control's saved members and fitted state. The hook receives `None` for `member`, `member_x_fit` and `member_x_score`. Use `include_member=False` for the original rule and `True` for the changed rule. The hook gets features in recorded fit and scoring row order. Derive learned coefficients from the permitted cached fit state. Count any new solves and schedule missing estimator fits separately. Exercise the changed operation on a small fixture or saved state before a costly fit. [Hook signature](#fit-only-an-added-member)

### Fit Only an Added Member

When the existing fitted members and upstream transforms stay fixed, keep their sealed control run. Use the normal `train` command with a candidate that constructs only the new member. Give it the same data and fold protocol; the feature list may differ, and each model will receive its own feature columns in order. If a change alters how an existing member was fitted, its old state cannot test that change.

```sh
$PY "$S/tabular_training.py" train --data training.csv --protocol member-folds.json \
  --candidate member.py --output-dir runs/added-member
$PY "$S/tabular_training.py" recompose --control runs/baseline --member runs/added-member \
  --composition compose.py --output-dir runs/composed
```

Implement the declared rule as `predict_fold(control, member, x_fit, x_score, member_x_fit, member_x_score, *, include_member)` in `compose.py`. Both models are already fitted. For example, a fixed regression blend could return `base + share * (extra - base)`, with `base = control.predict(x_score)`, `extra = member.predict(member_x_score)`, and `share = DECLARED_WEIGHT * include_member`. For an internal ensemble change, reuse its fitted members and transforms and turn off the new contribution **in the same formula**. Use [the existing CSV blend tool](data-model.md) if a fixed convex blend of available predictions is all that is needed.

The same hook can replace one fitted member when its peers and upstream transforms are proven unchanged. Reproduce the full old control with `include_member=False`; with `True`, substitute only the declared member and recompute downstream calibration or mixing fitted from its outputs using only that fold's permitted fit data. Preserve any inner cross-fitting the original rule requires. Stored validation predictions alone cannot reconstruct fit-side state or establish that the replacement reaches the scored output. If the new member changes another member's inputs, fit that dependent member again.

The adapter matches training/inference bytes and the protocol (including ordered fit/score rows and seeds), then checks the disabled rule on every scored fold against the saved control. The default reproduction tolerance is exact; specify `--control-atol` only for a justified numerical difference. For accuracy it also checks the raw control probabilities. Reproduction checks the disabled rule and row alignment. To verify an active change, perturb the exact statistic at its consumer and check the fitted state or final score-path predictions. A check on `train_prediction_` says nothing about a clip scale that reads `model.predict(x_fit)` instead. Neither a changed row count nor reproduced control proves that an arbitrary hook uses the intended input.

The result is a fresh development score for `runs/composed/oof.csv`. Keep `recipe.json` with the rule and input recipe hashes, and sealed `recomposition.json` with the source run seals, fold checks and original training costs. Recomposition adds zero adapter fits. If you trained a new member, record its cost with `cost --run runs/added-member`. The composition still needs an inference path before frozen delivery.

If the returned evaluator differs from the pinned comparator, run the saved `evaluate_predictions.py` directly on the **new** OOF and its sealed truth snapshot. Copy the reference result's metric, split ID, column names, score kind and custom metric options. For a pinned default-column RMSE proxy:

```sh
$PY "$PINNED_EVALUATOR" --truth runs/composed/truth.csv --predictions runs/composed/oof.csv \
  --stage development --metric rmse --split-id "$REFERENCE_SPLIT_ID" \
  --score-kind proxy --case-profile --output-dir runs/composed-pinned
```

Check the result with `compare_prediction_results.py` against the reference before interpreting the gain. Archive the matching result with the new composition recipe and a boundary citation to both sealed fits and the actual composition. The adapter cannot certify arbitrary code's information flow.

## Freeze the Submission Schema and Target Scale

Internal evaluation columns and target units need not match the official CSV. At `freeze`, declare `--submission-column` when the official target name differs, and `--inverse-transform` when model predictions require a target inverse. Defaults preserve the protocol prediction column and use `identity`. Supported regression inverses are `exp` for a target trained as `log(y)` and `expm1` for `log1p(y)`. Choose from the actual preprocessing/model output contract; an estimator that already returns original units needs `identity`. Do not infer units from plausible-looking values or apply the inverse twice.

For custom training recipes and source notebooks, trace the actual estimators reaching the final `predict`. If delivery uses a full-data fit, fit after validation or preserve that estimator apart from the fold fits. If delivery ensembles folds, bind the saved members and aggregation to the recipe. In Arnout Van Avermaet v16, `model_this` fits on all training rows and then passes the same estimator to `oof_pred`, which mutates it in each fold. The test output therefore uses the last fold's fit. The exporter also applies `expm1` to outputs trained with `log(y)`, subtracting one unit from the prices. [Arnout Van Avermaet v16, cells 45–50 and 61](https://www.kaggle.com/code/theupgrade/step-by-step-eda-lasso-lgbmr-stack?scriptVersionId=125563448)

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

### Count and Bind Paired Fits Before Launch

Before a bounded stage, count fit calls from the protocol files for the planned new executions. List each execution once; a matched cached control is not a new execution. The estimate counts one adapter call per actual fold. For example, two five-fold protocols require ten calls, regardless of how many times a prior procedure called `fit`:

```sh
$PY "$S/tabular_training.py" plan-cost --protocol repartition-a.json --protocol repartition-b.json \
  --expected-fit-calls 10
```

This command reads protocol JSON and fails on a mismatch before launch. Pass the per-execution count to `train --expected-fit-calls` to check the actual protocol used. For a nested model, count the changed and reusable fits inside each call, including prototype calls. One outer fit with three final members and three inner splits of two members runs nine direct member fits before any deeper nesting. Use the previous run's recorded fit time and the scope of the changed work to estimate elapsed cost. Read the fit journal for actual adapter calls and elapsed time.

To run a slot in a [frozen paired plan](local-evaluation.md#freeze-a-paired-eligibility-rule), copy that exact protocol's `protocol_sha256` from `plan-cost` into the run entry before archiving the plan. One managed training call is one repetition. The slot's `seeds` may be `[]` when the exact protocol already binds all folds and their seeds, or the list of unique estimator seeds in protocol order. Pass its IDs when launching:

```sh
$PY "$S/tabular_training.py" train --data training.csv --protocol repartition-a.json \
  --candidate candidate.py --output-dir runs/paired-a --expected-fit-calls 5 \
  --measurement-archive ARCHIVE --measurement-plan-id paired-gate --measurement-run-id round-a
```

The adapter checks the frozen slot, exact protocol bytes and executed recipe identity before importing the candidate. Record the sealed result with `candidate_archive.py record --configuration runs/paired-a/recipe.json --result runs/paired-a/evaluation/result.json` and the other usual fields, including a reuse reason where needed. The archive checks the completed matching comparison. This path uses the trainer's current scorer and recipe identity; keep matched cached controls whose evidence belongs to that same contract.

### Rescore with the Frozen Evaluator

When installed scorer code has changed but a development comparison must retain its existing contract, use the original run's sealed OOF with the exact saved scorer that produced a valid reference result:

```sh
$PY "$S/tabular_training.py" rescore --run runs/challenger \
  --evaluator /path/to/saved/scripts/evaluate_predictions.py \
  --reference-result runs/reference/evaluation/result.json \
  --output-dir rescored/challenger
```

`rescore` requires the selected scorer's dependencies. It verifies the original training manifest, checks the saved scorer's fingerprint through the shared identity function, copies it and its sibling `prediction_core.py`, and carries the original metric, column names, split and score-kind into evaluation. New scorers bind numerical-library versions; old source-only scorers retain their original identity format. It rejects a changed input contract or reference from confirmation. It never imports candidate code, loads models or fits; a different score recipe requires a separately declared evaluation. A scorer mismatch is a reason to locate the matching saved scorer and environment, not to relabel the evaluator hash.

The new directory preserves the reference, scorer, output and failures without changing the original run. A successful result links the original training seal and execution receipt; archive it using `--configuration ORIGINAL_RUN/recipe.json` and its original bound `--proposal-id`. Archive recording verifies that link and keeps the original fit cost and proposal timing. `new_fit_calls: 0` describes this rescore; `originating_cost` describes the training that generated its predictions. Count the original execution once with `cost --run ORIGINAL_RUN`, not as another fit for each rescore. Older runs without a managed receipt can still use the standalone prediction scorer, but cannot gain retrospective proposal evidence.

The adapter durably appends `fit_started`, `fit_completed` or `fit_failed` for every fold. A prediction failure after `fit_completed` leaves a completed fit to charge and an unfinished run without a valid score. A killed fit remains `unresolved_fit_calls`, with unknown duration instead of zero. After an incomplete identical attempt, automatic repetition is refused; inspect its journal, then supply `--retry-reason 'actual reason'` in a fresh directory only when a new attempt is useful. This flag also permits an intentional planned repeat of completed work, which remains a measurement of the same implementation. Partial folds are not automatically resumed.

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
