# Local Prediction Evaluation

Use the bundled scripts for unweighted, scalar regression or binary classification predictions in CSV files. They evaluate a fixed local split and compare metrics; task-specific data preparation, training, leakage checks, and resource checks still belong to the task adapter.

## Fit the Competition Metric

| Metric argument | Direction | Inputs and exact behavior |
| --- | --- | --- |
| `rmse` | Minimize | Finite numeric targets and predictions; square root of mean squared residual |
| `mae` | Minimize | Finite numeric targets and predictions; mean absolute residual |
| `binary_log_loss` | Minimize | Labels 0/1 and probabilities in [0, 1]; natural-log loss, clipped at epsilon and 1 minus epsilon |
| `roc_auc` | Maximize | Labels 0/1 with both classes present and finite ranking scores; ties contribute one half |

Check the contest's scorer before choosing an argument. Weighted, per-group, per-fold, multi-target, multiclass, custom aggregation, and transformed metrics require a task-specific implementation. Pooled OOF ROC-AUC is not generally equal to mean fold ROC-AUC. Log-loss epsilon defaults to `1e-15`; set `--log-loss-epsilon` to the official value when applicable, including its numerical conventions.

The default `--score-kind proxy` labels the measurement provisional. Use `--score-kind official_metric` only after verifying that the exact formula, label encoding, weights, clipping, and aggregation match the contest. The flag records that declaration; it does not check official rules or make the result a platform score.

## Inputs and Evaluation

Provide a local truth CSV such as `id,target` and a candidate prediction CSV such as `id,prediction`. Column names can be set with `--id-column`, `--target-column`, and `--prediction-column`. Each file must contain unique, non-empty IDs and finite numeric values. IDs are compared as exact strings, preserving leading zeros; row order can differ. Extra named columns are allowed but do not change scoring weights or aggregation. Missing/extra IDs, duplicate columns or IDs, malformed rows, and invalid metric domains fail the evaluation.

Seal the truth bytes, split ID, columns, metric, score kind, clipping parameters, and stage. Fit training and preprocessing under the task's fold protocol and save their provenance separately. Use `development` for iterative comparison and `confirmation` for the frozen shortlist on a separate split. These stage names describe intended use; they do not verify that a dataset was previously unseen.

```powershell
python <skill-dir>/scripts/evaluate_predictions.py `
  --truth <development-truth.csv> `
  --predictions <candidate-predictions.csv> `
  --metric rmse `
  --stage development `
  --split-id <frozen-split-name> `
  --output-dir <new-evaluation-directory>
```

The output directory's parent must exist. A successful run saves `predictions.csv` as the exact candidate snapshot and `result.json` with metric direction/value, validity scope, expected/completed cases, and candidate/evaluator/score-model/split/configuration hashes. It reads the truth file without copying it into the run. Keep truth bytes fixed when reusing evidence; use the saved prediction snapshot when reproducing an evaluation. Inputs are UTF-8 CSV, optionally with a BOM; the scripts use Python's standard library and do not train models or execute candidate code.

`valid: true` covers prediction format, ID coverage, finite values, and the metric domain only. The result lists training leakage, training provenance, resource limits, and competition rules as unchecked. The skill must establish those checks separately before promoting a competition entry. A failed run exits with code 2 and records a null score when a new output directory was created; an existing directory is never overwritten.

## Compare Local Scores

```powershell
python <skill-dir>/scripts/compare_prediction_results.py `
  --baseline <baseline-evaluation/result.json> `
  --candidate <candidate-evaluation/result.json> `
  --output <new-comparison.json>
```

The comparator accepts only complete successful results with matching evaluator, metric/score model, split, stage, and evaluation configuration. Keep each result beside its `predictions.csv`; it verifies the snapshot hash. It reports raw score delta, improvement oriented in the correct metric direction, and `metric_preference` as baseline/candidate/tie. `--tie-epsilon` defaults to `1e-12` and is a numerical threshold, not a statistical confidence interval. Existing comparison files are never overwritten.

This preference is about the deterministic local metric. Independently check training repeatability, task hard rules, and final confirmation; a favorable CSV score alone does not prove the full model should be promoted. Compare separate confirmation results with one another, never a development result directly against a confirmation result. For metrics outside this interface, extend the task's adapter rather than substituting a supported metric and calling it official.

## Construct and Confirm a Prediction Blend

When compatible models have complementary held-out errors, use `blend_predictions.py` to test a convex weighted mean without retraining. This is candidate construction; evaluate its output with the same frozen evaluator and compare against the best individual candidate. A weaker individual model can help a blend, while highly similar predictions can add cost without gain. Check the actual metric rather than inferring improvement from diversity alone.

Create a recipe from at least two named, complete **development** evaluations with matching metric, evaluator, split, stage, and configuration:

```powershell
python <skill-dir>/scripts/blend_predictions.py create `
  --member model-a <model-a-development/result.json> `
  --member model-b <model-b-development/result.json> `
  --weights 3 1 `
  --output-dir <new-blend-directory>
```

Weights correspond to the member order in this command. They must be finite, non-negative, and have a positive total; the tool normalizes and saves them. It reads the verified `predictions.csv` beside each result and aligns exact string IDs. It saves blended `predictions.csv`, `recipe.json`, byte-for-byte parent prediction snapshots under `parents/`, and `manifest.json` containing parent, recipe, builder, and candidate hashes. The manifest has a null score and is not an evaluation result. Custom ID/prediction columns are inherited from the development evaluations. Input/output CSVs use the same scalar interface as the evaluator.

Count every tested weight recipe as a candidate trial, including recipes rejected after cached-prediction evaluation. Select weights using development evidence and reserve confirmation before a sweep. Start with a small blend justified by error complementarity; the tool does not optimize weights, stack models, calibrate outputs, or compute a score. For ROC-AUC it blends raw ranking scores, whose scales may differ; it does not silently rank-normalize them. For log loss, blending probabilities keeps the convex result in [0, 1]. Do not average incompatible target encodings, units, or prediction interpretations.

Once selected, apply the **same recipe** to confirmation or final-test predictions using the same named model pipelines:

```powershell
python <skill-dir>/scripts/blend_predictions.py apply `
  --recipe <selected-blend-directory/recipe.json> `
  --member model-b <model-b-confirmation.csv> `
  --member model-a <model-a-confirmation.csv> `
  --output-dir <new-confirmation-blend-directory>
```

Member order may change here: weights map by exact name. Choose distinct ASCII member names without case-only differences or Windows device names so parent snapshots remain portable. All recipe members must be present, including zero-weight members, with identical sample coverage within this invocation; new sample IDs can differ from the development IDs. The tool validates the recipe content hash and copies the unchanged recipe into the new output. `apply` requires no labels and has no weight override. Evaluate confirmation predictions with `--stage confirmation` on the sealed independent truth; compare with separately evaluated individual confirmation predictions. Changing weights after looking at confirmation outcomes turns that evidence into development data and requires fresh confirmation for an unbiased claim.

Member names and hashes identify artifacts, not model semantics. Record the exact model/preprocessing configurations behind each name and verify that confirmation/test predictions come from the selected pipelines. Parent CSVs must have valid OOF or held-out provenance; blending cannot repair leakage. Measure combined model inference time/memory and permitted dependencies under the task rules. Recipe hashes detect accidental changes; they are not signatures or proof of provenance. Existing output directories are never overwritten; a failed run returns code 2 with a null score in a new directory's manifest. A failed or incomplete construction cannot be used as an evaluated candidate.
