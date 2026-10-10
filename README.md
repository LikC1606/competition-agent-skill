# Competition Agent Skill

一个以分数最大化为目标的竞赛优化流程：Codex 读取题目和规则，建立可核验的评分闭环，再按真实评测结果迭代候选。

当前仓库包含通用的 `competition-optimize` 控制流程、固定时隙 C++ 评测 adapter，以及通用预测 CSV 评测、比较、抽样不确定性估计、错误诊断和固定权重集成工具。核心流程面向不同竞赛题型；每项任务仍需核对其规则、指标和验证协议。比赛源代码、二进制和评测结果不会被复制到本仓库。

## 最小版本

架构是 **一个通用 Codex skill + 按题型扩展的评测适配器**；薄型 runner 等重复操作确实造成错误后再决定：

- **Skill**：指导 Codex 固定官方目标、定向检索、建立 baseline、提出可检验假设，并按官方指标分析反馈。
- **比赛适配器**：提供题型专属的候选接口、硬约束、评测和官方评分计算；当前有算法/代码 adapter，以及预测 CSV 的 RMSE、MAE、二分类 LogLoss 和 ROC-AUC 评测层。可按独立样本或完整组估计固定预测的抽样不确定性，诊断开发集误差与分组退步，生成加权集成候选，并将冻结配方复用于确认集或测试集。数据准备、训练、防泄漏和资源验证仍需按比赛接入。
- **可选薄型 runner**：只在手工 pilot 出现快照、超时或记录错误后，实现候选隔离和结构化记账；不实现搜索算法或通用沙箱平台。

核心循环不依赖题型，但搜索策略和验证方式由 adapter 提供。没有可靠评测器时，先建立并验证评测器，不进入昂贵搜索；尚未实现 adapter 的题型不能宣称已支持自动优化。

## 工作流程

1. **固定目标**：生成任务卡，提取官方指标、改善方向和聚合方式、硬约束、资源限制、数据划分和提交要求，记录缺失参数。
2. **建立评测器**：优先复用官方工具；自行实现时用已知正例和反例核对，区分本地复现官方指标、平台回执与代理指标。
3. **检索与 baseline**：按指标、规模、规则和瓶颈检索方法，将来源转成有适用条件和验证办法的假设，得到正确且有实测结果的初始方案。
4. **选择实验动作**：根据证据决定探索新路线、诊断瓶颈、深入组件、调参或组合；围绕有希望的组件连续迭代，收益不再可信时调整方向。
5. **配对评测与学习**：保留不同路线、独立候选和缓存来源，对照代码与逐例结果更新假设；将观察、解释和下一步验证分别记录。
6. **确认与交付**：预算先留出最终确认，用独立场景评测冻结候选，再输出最好方案、实验对比和符合规则的提交包。

## 关键约定

- 按官方指标决定候选，明确越大越好或越小越好；缺少评分参数时保留分项和 Pareto 候选，代理指标只用于暂定搜索。
- 优化期间保持评测口径一致；评测器变化后，重新评测需要比较的版本。
- 保留独立验证场景，用于检查最终候选的泛化表现。
- 每次实验记录父版本、假设、代码快照、配置、指标、耗时、状态和失败原因。
- 最好版本与最新版本分别保存，失败实验不覆盖已验证的方案。
- 输出提交包；正式提交按用户授权和比赛配额处理。

## 源码研究结论

- 从 AIDE 借鉴父子候选记录、先产生 baseline 和一次只提出一个可检验改进的做法。
- 从 ShinkaEvolve 借鉴窄范围可变代码区、非 Python 评测适配和结构化正确性结果。
- 将 AIDE 式搜索选择与 Shinka 式评测/检查能力组合成一个轻量闭环；第一版不引入外部进化框架或多 agent 群组。
- Meta 的 LLM Speedrunner 是更贴近算法优化的参照：阶段化假设、实现、执行、分析，版本化工作区记录候选历史。其完整实验框架与 GPU/Slurm 配置不纳入 MVP。
- MLEvolve 的停滞检测、跨分支经验值得后续验证；其 MCGS、多 agent、embedding memory 和 Kaggle 数据栈不作为首版依赖。
- FDE-Bench 的离子束均匀性 case 是“优化/均匀性”表述上的近邻，但实际任务是预测曲线；只参考任务澄清和 evaluator 设计。case 数据和实现没有开放再分发许可，不复制进本仓库。
- 评分器以程序输出为准；测试失败、耗时和多项指标都作为单独证据。模型的解释用于选择下一项实验，不直接决定候选分数。
- 每轮保留可运行的最好版本，并用固定测试集配对比较；达到已配置预算即停止。

完整的源码依据、竞品取舍和首版接口草案见 [`docs/research.md`](docs/research.md)。

新增流程借鉴 MLE-STAR 的搜索与组件内优化、ReEvo 的候选对照学习、ALE-Agent 的表示和邻域搜索，以及获奖选手的验证与互补集成经验。具体来源和适用条件见[补充研究](docs/automation-and-solving-experience.md)；按题型选择实验时读取 [task-playbooks.md](skills/competition-optimize/references/task-playbooks.md)。这些是已写入 skill 的决策方法，提分效果仍需跨任务对照验证。

## 第一个验证案例

已使用华为云固定时隙均匀调度算法题验证 adapter，覆盖 C++ 函数接口、在线增删操作、均匀性与稳定性权衡、运行时间，以及禁止乘除、取余和浮点运算的限制。

现有比赛材料与解法留在原工作区。算法 adapter 已有 11 项单元测试及真实 smoke/full 运行验证；预测 CSV 工具新增指标、样本对齐、异常输入、评测契约比较及 CLI 测试。核心流程在其他题型上的提分效果仍需真实任务验证。

## 参考项目

| 项目 | 参考重点 |
| --- | --- |
| [LLM Speedrunner](https://github.com/facebookresearch/llm-speedrunner) | 算法/代码优化实验循环、版本化工作区；最贴近本项目目标。 |
| [AIDE](https://github.com/WecoAI/aideml) | 候选代码搜索树，以及生成、修复和改进之间的选择。 |
| [AutoKaggle](https://github.com/multimodal-art-projection/AutoKaggle) | 读题、规划、开发、评审和总结的竞赛流程。 |
| [MLEvolve](https://github.com/InternScience/MLEvolve) | Kaggle 与数学优化上的进化搜索；借鉴停滞识别与多分支保留，不搬完整框架。 |
| [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve) | 程序演化，以及已有的 Codex / Claude skill 组织方式。 |
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) | 初始程序与自定义评测器驱动的代码优化。 |
| [MLE-bench](https://github.com/openai/mle-bench) | 参赛 agent 的评估方法与比赛评测适配。 |
| [FDE-Bench](https://github.com/baidubce/FM-Agent/tree/main/FDE-Bench) | 端到端交付与 evaluator 设计；case 006 是曲线预测任务，不是时隙调度。 |
| [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2) | 研究型树搜索和代码隔离风险提示；仅作概念参考。 |

## 下一步

按 [`docs/mvp-plan.md`](docs/mvp-plan.md) 了解当前实现边界。通用流程见 [`skills/competition-optimize/SKILL.md`](skills/competition-optimize/SKILL.md)，固定时隙计分限制见 [`fixed-timeslot.md`](skills/competition-optimize/references/fixed-timeslot.md)，预测 CSV 评测用法见 [`data-model.md`](skills/competition-optimize/references/data-model.md)。新增题型先遵守 [`adapter-contract.md`](skills/competition-optimize/references/adapter-contract.md)；当前没有完整的 Kaggle 数据准备、训练和提交集成。
