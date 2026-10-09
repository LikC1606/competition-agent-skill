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
