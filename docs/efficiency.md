# 流程与评测效率

2026-10-10 的改动覆盖入口上下文、实验选择和预测抽样评测。计分 evaluator 未改动，因此既有预测评测仍可通过原 hash 契约复用；抽样 estimator 的源码 hash 随实现更新。

## 少做重复工作

`SKILL.md` 从 943 个空白分隔词精简到 651 个，约减少 31%。保留任务契约、评分核验、预算、候选证据、独立确认和交付要求；按题型与当前动作读取详细参考，避免每轮加载所有工具说明。

新增的决策原则是先做便宜的有效分数比较，再按当前问题使用误差切片、profile、bootstrap 或训练重复。明显被否定的候选保留拒绝证据；排名接近、误差互补或机制不明确时再做相应诊断。以各阶段实测成本安排预算，并复用仍满足依赖条件的 baseline、来源和中间产物。

例如，只改集成权重可复用成员预测；只修正评分公式可复用未变的模型与预测，但重算评测；改 split 或训练特征需要重做依赖该变化的拟合和预测。固定预测 bootstrap 的缓存不允许跨模型、split 或配置盲目复用，也不会把旧开发证据变成独立确认。

规则见 [实验效率](../skills/competition-optimize/references/score-search.md#avoid-work-that-cannot-change-the-next-decision) 和 [预测缓存依赖](../skills/competition-optimize/references/data-model.md#establish-training-and-validation-evidence)。这些流程调整尚未单独测量完整 agent 的时间或提分效果。

## 抽样评测实测

profile 显示旧实现每次 bootstrap draw 都重建标签/预测数组，重复检查输入、计算 log loss 和排序 AUC。新实现先验证固定输入，缓存逐行损失/残差，并预先排序 AUC；抽样时使用整数行重复次数计算原 pooled AUC，保留 ties。回归仍使用每次 draw 自己的缩放，避免未抽到极端行时小残差下溢。

使用 [`examples/benchmark_prediction_uncertainty.py`](../examples/benchmark_prediction_uncertainty.py)，对照改动前 commit `5d7dd78` 的脚本。固定 1000 行、1000 次抽样，分别测试 row 和大小不等的完整 group；四种指标各重复计时 3 次并交替运行顺序，以下为中位数。本机 Python `3.14.7`，Windows 11。

| 指标 | 抽样单位 | 原耗时（秒） | 新耗时（秒） | 原耗时 / 新耗时 |
| --- | --- | ---: | ---: | ---: |
| RMSE | row | 1.470 | 0.763 | 1.93 |
| MAE | row | 1.358 | 0.675 | 2.01 |
| Binary LogLoss | row | 2.003 | 0.580 | 3.45 |
| ROC-AUC | row | 1.872 | 0.695 | 2.70 |
| RMSE | group | 1.133 | 0.476 | 2.38 |
| MAE | group | 0.997 | 0.339 | 2.94 |
| Binary LogLoss | group | 1.650 | 0.223 | 7.40 |
| ROC-AUC | group | 1.499 | 0.351 | 4.27 |

八项对照的逐次 score、case count、状态、改善量和实际 row draws 完全相同。测试另覆盖极端回归数值、零残差、概率边界、AUC tie/单类抽样、大小不等的 group、输入异常与预算超限。

复用上轮 [Diabetes 和 Breast Cancer pilot](tabular-pilot.md) 的确认预测进行 CLI 验证，两项 `bootstrap.csv` 与原文件逐字节相同，区间及预算消耗相同，没有重训模型。完整测试为 83 项通过，skill validator 通过。

性能数字只覆盖进程内 bootstrap，包括输入验证与预计算；不含 Python 启动、CSV 读取、模型训练或 agent 推理。大任务的实际收益取决于耗时构成，不能把 7.40 的单项比例当作整个比赛流程的提速。

## 复现与证据

先创建仓库外的新目录，保存来自自己仓库的可信旧脚本，再执行对照：

```powershell
New-Item -ItemType Directory -Path 'D:\华为云\tmp\efficiency-reproduction'
git show 5d7dd78:skills/competition-optimize/scripts/compare_prediction_uncertainty.py |
  Set-Content -Encoding utf8 -LiteralPath 'D:\华为云\tmp\efficiency-reproduction\before.py'
python examples/benchmark_prediction_uncertainty.py `
  --reference 'D:\华为云\tmp\efficiency-reproduction\before.py' `
  --output 'D:\华为云\tmp\efficiency-reproduction\benchmark.json'
```

脚本导入 reference 作为 Python 代码，仅使用可信的旧版本。输出须为新文件；结果保存各次计时、环境、seed、输入规模、源码 hash、抽样结果 hash 和一致性检查，性能断言不写入单元测试以避免机器负载造成误报。

本次证据保留在 `D:\华为云\tmp\efficiency-pilot-20261010`：原实现快照、profile、对照 `benchmark.json`、两项真实预测的重测产物及 `real-prediction-check.json`。仓库只提交代码、测试和汇总。
