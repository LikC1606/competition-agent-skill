# 真实表格数据流程 pilot

2026-10-10 用两个 sklearn 内置公开数据集，验证训练、开发集诊断、组合、冻结候选和独立确认能否组成可复现的闭环。入口是 [`examples/tabular_pilot.py`](../examples/tabular_pilot.py)。它执行预设的有限实验，只是集成验证；没有让 agent 自行读题、检索、编写新解法，也没有基础流程与增强 skill 的因果对照。

## 数据与协议

回归使用 [Diabetes](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_diabetes.html)：442 位患者、10 个数值特征，目标为一年后的疾病进展，指标为 RMSE。分类使用 [Wisconsin Diagnostic Breast Cancer](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_breast_cancer.html)：569 个病例、30 个数值特征，指标为二分类 LogLoss，沿用 sklearn 的 `1 = benign` 标签。原始来源及描述由 loader 的 `DESCR` 保存到运行目录；数据和模型不进入仓库。

- 先划出 20% 确认集，seed `1729`；再从其余样本划出 25% 开发集，seed `1730`。分类两次切分均分层。回归 train/development/confirmation 为 `264/89/89`，分类为 `341/114/114`。
- 使用原始特征，所有学习型预处理和模型仅拟合训练行。Diabetes 显式设 `scaled=False`，避免 loader 默认的全数据归一化。检查完整特征行无重复、三个集合 ID 互斥，并保存切分与数据 hash。
- 可信基线为训练集内 `StandardScaler + Ridge(alpha=1)` 或 `StandardScaler + LogisticRegression(C=1, max_iter=2000, tol=1e-6)`。
- 每题三个改进 trial：浅层 HistGradientBoosting、ExtraTrees，以及基线与开发集最好的树模型的等权组合。仅在逐例诊断显示双方各有胜例时测试组合；不扫描权重。完整参数保存在各候选的 `configuration.json`。
- 拟合顺序执行，线程上限为 1，模型 seed `1729`。确认先保存 `shortlist.json`，再使用其模型文件生成预测；混合配方通过 `apply` 原样复用。
- 运行前的交付规则：只有开发集和确认集指标均优于基线才选择 challenger，否则保留基线。确认 shortlist 为基线和开发指标最低的一个 challenger；未根据确认结果扩张候选或修改规则。
- 1000 次配对 row bootstrap，seed `0`、95% 区间、实用提升阈值 `0`。区间只是描述性证据，没有自动显著性晋升门槛。患者行独立可交换是此小实验的假设，不能替代临床、分组或时间外验证。

这不是实际比赛，因此所有结果标记为本地 `proxy`，不存在官方平台分数。

## 实测结果

以下指标均越低越好。

| 候选 | Diabetes 开发集 RMSE | Breast Cancer 开发集 LogLoss |
| --- | ---: | ---: |
| 可信线性基线 | 53.773319 | **0.062932** |
| HistGradientBoosting | 55.912673 | 0.100212 |
| ExtraTrees | 54.818209 | 0.122683 |
| 等权组合 | **53.550775** | 0.076641 |

回归的组合成员是 Ridge 与 ExtraTrees；分类的成员是 LogisticRegression 与 HistGradientBoosting。

| 任务 | 冻结 challenger | 确认基线指标 | 确认 challenger 指标 | 改善量的 95% 配对区间 | 按预定规则交付 |
| --- | --- | ---: | ---: | --- | --- |
| Diabetes | 等权组合 | 56.481675 | 56.177194 | [-1.492298, 2.048311] | 组合，收益仍未证实稳定 |
| Breast Cancer | 等权组合 | 0.085010 | 0.067601 | [-0.019278, 0.080232] | Logistic 基线，开发/确认排序反转 |

回归在本次确认样本上的改善为 `0.304480` RMSE，约 `0.54%`，两个区间都跨零。分类组合在确认集上较好，但开发集较差；不能看到确认分数后再把它改称为开发流程成功选出的方案。

总计 6 次模型拟合、2 个组合配方和 12 次 CSV 指标评测。12 项指标均与 sklearn 独立实现核对，容差 `1e-12`；各阶段的预测、配置、模型、父配方、evaluator 与 split hash 都保留在运行目录。另已检查 scaler 均值仅来自训练行、短名单事件先于确认计分、预测 ID 匹配切分、全部预测 hash 可复现、拒绝仓库内输出，以及已有目录不会被覆盖，审计摘要为运行目录中的 `audit.json`。一次完整运行约 8 秒，属于本机小数据结果，不能外推到比赛训练成本；已记录模型大小、各模型拟合/预测时间，未测峰值内存或证明比赛资源合规。

## 对 skill 的具体修正

1. 训练证据覆盖 data loader 和缓存来源，不能只审查模型里的 scaler；记录拟合行与模型流水线身份，区别于预测 CSV 的 hash。
2. 提分比较以可信 scoring baseline 为参照；弱 sanity baseline 的改善不作为竞争力证据。
3. 在小数据、少数样本主导损失或接近的排名下，先考虑预算内的匹配 folds/seeds，再做细调。固定预测 bootstrap 与训练重复各回答不同问题。
4. 确认前冻结 shortlist、fallback 和交付规则。排序反转是需要解释的结果，不能触发同一确认集上的权重、seed 或候选搜索。
5. 保留单体较弱但误差互补的模型。回归中两个树模型单独都逊于基线，组合仍有小幅观测收益；这支持尝试一次小组合，没有证明组合必然有益。

这些原则已进入 [`SKILL.md`](../skills/competition-optimize/SKILL.md)、[`score-search.md`](../skills/competition-optimize/references/score-search.md) 和 [`data-model.md`](../skills/competition-optimize/references/data-model.md)。本次数据已用于调整流程，后续不能再把它们称为未见过的 skill 测试任务。

## 复现

示例依赖是可选的；安装后的 skill 工具仍仅使用标准库。本次版本为 Python `3.14.7`、NumPy `2.5.3`、SciPy `1.17.1`、scikit-learn `1.9.1`、joblib `1.6.0`，需同时具备 scikit-learn 依赖的 threadpoolctl。其他版本的拟合及序列化字节可能不同，必须核对环境和数值结果。

```powershell
python examples/tabular_pilot.py --output-dir 'D:\华为云\tmp\tabular-pilot-reproduction'
```

`--output-dir` 必须在仓库外且尚不存在。脚本保存 source snapshot、环境和工具 hashes、数据与 split、任务契约、拟合模型、预测、追加事件账本、短名单、所有评测/诊断/区间及摘要。实际测量结果在 `D:\华为云\tmp\tabular-pilot-20261010-03`；仓库只保留方法与汇总，不提交患者数据或二进制。

开发时首轮还暴露了 Windows 中文路径下子进程输出编码不一致，修正为 Python UTF-8 模式后重复运行；没有更换切分、seed、模型参数或权重。重复执行用于基础设施验证，不能算独立 agent 运行或新增统计证据。

后续需要独立、预算匹配的完整 agent 运行与跨任务对照，尤其是分组/时间数据、非表格任务及较大训练成本。两项预设小实验不能证明泛化提分能力。
