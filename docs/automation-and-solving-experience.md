# 自动化解题与高分经验补充研究

检索日期：2026-10-10。目标是加强跨题型的提分能力，覆盖数据建模和算法优化。本文区分源码中确认的机制、作者报告的结果与本项目的设计推论；没有安装、运行或复现这些上游系统。

## 最值得迁移的发现

1. **搜索应该改变实验选择。** 用题型、指标、数据结构和瓶颈检索，再将资料转成有适用条件、预期影响和验证方法的假设。星数、notebook 票数和“冠军同款”都不能代替本地效果。
2. **既要探索不同路线，也要围绕关键组件深入优化。** 搜索新的模型或算法家族解决路线偏差，组件级迭代解决每次大改却没有深入验证的问题。
3. **解题空间不只有参数。** 状态表示、SAT 编码、搜索邻域、特征、训练目标、评分近似和评估速度都可能改变可达到的分数。
4. **验证方式决定反馈是否有用。** 患者、用户、时间和仿真场景需要相应的切分或重复协议；开发集上的最佳结果需要独立确认。
5. **候选的价值包含互补性。** 不同候选可以在不同样本、规模或子问题上表现更好。允许集成或策略路由时，评测组合后的官方目标和资源成本。

## 自动化系统

### MLE-STAR：搜索方法，再定位组件深入迭代

来源：[论文 v3](https://arxiv.org/abs/2506.15692v3)、[正文与附录](https://arxiv.org/html/2506.15692v3)、[作者仓库](https://github.com/jaehyun513/MLE-STAR)。论文 v3 为 2025-08-28；本次仓库 HEAD 为 `d33445de01d66b42cf3e5093bc0623502393864c`，README 只有项目标题，未提供复现步骤。本段主要依据论文。

论文第 3 节与算法附录描述了三个阶段：从网络搜索任务相关模型并构建初始解；用消融实验选择重点代码块，外层选择组件、内层围绕组件尝试改进；探索集成策略。历史消融摘要参与下一次选择，以避免一直修改相同组件。

作者报告，在 MLE-bench Lite 的 22 个任务、24 小时时限下，Gemini 2.5 Pro 版本达到奖牌阈值的比例为 `63.6% ± 6.0%`，误差为三次随机运行的标准误。这是论文中的基准结果，不能当作新比赛的获奖概率；模型、预算和评测数据都影响结果。

**迁移：** 用便宜的消融、profile 或小规模参考解选择值得深挖的组件，再做有预算的组件内搜索。消融损失大表示当前解依赖它，并不自动说明它剩余的提升空间最大；还要结合可改进机制和成本判断。

### ALE-Bench / ALE-Agent：算法领域知识与多样化搜索

来源：[官方介绍](https://sakana.ai/ale-bench/)、[论文](https://arxiv.org/abs/2506.09050)、[评测仓库](https://github.com/SakanaAI/ALE-Bench/tree/3da9b12fb5d112dabb3af693d1a42031c95142bc)。官方介绍发表于 2025-06-17。

ALE-Bench 收集 40 个历史 AtCoder Heuristic Contest 优化问题，提供题面、可视化、执行和排名工具。ALE-Agent 结合算法领域知识与多样化候选搜索。作者报告其在实时 AHC047 中取得约 1,000 名参赛者中的第 21 名。具体改进包括用 Poisson 近似加速搜索内部的评分，以及扩充模拟退火邻域。

官方同时记录了反复修不好 bug、复杂度分析不足导致超时、持续优化低收益代码等失败；在适合退火的短比赛中表现较好，不能据此推断对其他算法或长周期比赛同样有效。

**迁移：** 由题型 adapter 提供针对性的算法知识和诊断工具；观察搜索行为和逐场景结果后选择下一步。搜索内部可以使用近似目标，但最终晋升仍使用冻结的比赛 evaluator。这里的可用公开仓库是 ALE-Bench，不将 ALE-Agent 描述为已下载、可直接运行的独立项目。

### LLM4AD / EoH / ReEvo：把搜索动作和经验反馈具体化

来源：[LLM4AD README](https://github.com/Optima-CityU/llm4ad/blob/ffb6acf64497be93932c98d25369352efd3865cf/README.md)、[EoH 提示源码](https://github.com/Optima-CityU/llm4ad/blob/ffb6acf64497be93932c98d25369352efd3865cf/llm4ad/method/eoh/prompt.py)、[ReEvo 提示源码](https://github.com/Optima-CityU/llm4ad/blob/ffb6acf64497be93932c98d25369352efd3865cf/llm4ad/method/reevo/prompt.py)、[ReEvo 原论文](https://proceedings.neurips.cc/paper_files/paper/2024/hash/4ced59d480e07d290b6f29fc8798f195-Abstract-Conference.html)。本次直接读取了 README 和两份提示源码，未复现原论文实验。

LLM4AD 将任务、搜索方法与 LLM 接口分开。EoH 的提示显式区分全新机制、从已有算法抽取共同思路、修改机制和修改参数。ReEvo 将表现较差与较好的代码成对比较，产生短期反馈，并累计长期建议用于下一次变异。

**迁移：** 每个 trial 明确属于新路线、组件改进、调参还是组合；从已评测候选的代码差异和逐例结果产生下一条可检验假设。反思文字是解释，不是因果证明。跨题复用时保存指标、限制和奏效场景，重新验证适用性，不将历史赢家写成默认答案。

### NVIDIA Kaggle skill：可借鉴的资料获取入口

来源：[README](https://github.com/NVIDIA/nvidia-kaggle/blob/2b78cf29f5f30680764292a6592de8d53d4147a8/README.md)、[研究 brief 流程](https://github.com/NVIDIA/nvidia-kaggle/blob/2b78cf29f5f30680764292a6592de8d53d4147a8/skills/nvidia-kaggle-skill/research-brief.md)、[评测报告](https://github.com/NVIDIA/nvidia-kaggle/blob/2b78cf29f5f30680764292a6592de8d53d4147a8/BENCHMARK.md)。检查版本为 2026-08-04 的 commit。

它将题面、规则、指标、数据说明、讨论、公开 kernels、获奖复盘和 notebook 本地复现组织成可组合工作流。研究指南要求结论链接到真实来源，并区分作者声称的分数、实际获取的分数和票数。

评测报告包含 18 个触发或不触发任务，主要衡量工作流执行、回答准确性和任务完成。它不能证明自动训练与优化能获得高竞赛分数。

**迁移：** 借鉴检索入口与来源记录方式，接到我们的假设队列；优化循环继续由 evaluator 和实验结果驱动。本轮没有安装插件、访问账户或执行提交。

### RD-Agent：研究假设与实现反馈形成循环

来源：[README](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/README.md)、[Data Science Agent 文档](https://rdagent.readthedocs.io/en/latest/scens/data_science.html)。

文档串联假设提出、实验动作选择、模型或特征实现、验证与反馈。自定义任务需要题目说明、数据准备、提交格式和评分实现，说明通用 agent 仍然依赖明确的任务接口。

**迁移：** 实验失败后更新假设和动作，不只重写代码。文档中的“测试集”与 leaderboard 反馈要根据用途拆成开发验证和外部最终评测；不能照搬名称后持续用最终真值调参。README 的领先宣传随时间变化，本研究不将它当作当前系统排名。

### AlphaEvolve：自动验证支持跨领域程序搜索

来源：[DeepMind 官方介绍](https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)，发表于 2025-05-14。

公开介绍描述了候选程序生成、自动执行与评分、程序数据库和进化选择，应用覆盖调度、硬件、训练计算与数学问题。广泛适用的前提是候选能够表示成程序，而且质量和有效性可以自动评价。

**迁移：** 通用部分负责候选和实验决策，领域部分负责表示、约束、评分与诊断。公开博文不足以让本项目复现其效果，本轮也没有获得或运行该系统。

## 解题者的经验与源码

### ICFP 2025 Team Unagi：改变编码带来更大的搜索空间

来源：[Takuya Akiba 的团队复盘](https://sakana.ai/icfp-2025/)、[优化配置](https://github.com/icfpc-unagi/icfpc2025/blob/23439908ed97bdff72c0d95803e9a875b22c9436/evo/exp2/main.py)、[提示](https://github.com/icfpc-unagi/icfpc2025/blob/23439908ed97bdff72c0d95803e9a875b22c9436/evo/exp2/prompt.md)、[实际 evaluator](https://github.com/icfpc-unagi/icfpc2025/blob/23439908ed97bdff72c0d95803e9a875b22c9436/evo/exp2/evaluate.py)。

人工先设计总体解法和 SAT baseline，再用 ShinkaEvolve 搜索 Rust 编码改进。作者报告 320 次 trial、约 60 美元成本，在 18 房间案例从 `2.86s` 到 `0.44s`，24 房间案例从 `127s` 到 `13s`。重要变化是加入中间连接变量，让求解器先决定房间间的拓扑，再决定门的连接；人工后来将这个思路用于其他问题。

**源码核查的限制：** 提示描述中位运行时间，但该版本 evaluator 实际优化 `combined_score = -p25_val`；测试固定为 18 房间、189 个 seed，63 个 worker 并行运行，非 `AC` 或 score 不为 2 的案例记为 30 秒。`correct` 只要求至少一次 `AC`。因此，配置不是完整正确性证明，计时也受资源并发影响。团队最终比赛成绩来自总体解法与工程，局部运行时间优化也不等于官方探测次数指标的直接提升。

**迁移实验：** 在已知求解器瓶颈上试新的表示或编码；比较有效率、完整目标、不同规模和受控环境下的运行时间。将搜索得到的机制作为下一项人工或自动实验的线索。

### Kaggle Grandmasters playbook：可靠验证、多路线与互补候选

来源：[Kazuki Onodera、Théo Viel、Gilberto Titericz、Chris Deotte 的经验文章](https://developer.nvidia.com/blog/the-kaggle-grandmasters-playbook-7-battle-tested-modeling-techniques-for-tabular-data/)，发表于 2025-09-18。

作者强调优化整个实验流水线的速度，检查训练与测试分布差异，并让验证切分匹配测试场景：时间数据按时间切分，患者或用户等相关样本按组切分。初期尝试不同模型家族，再按验证表现推进特征工程、hill-climbing 混合、stacking 和额外训练。

文章还指出伪标签应避免 fold 间泄漏，软标签和强 teacher 是可尝试的方法。外部数据、测试特征和伪标签是否允许，仍由当前比赛规则决定。更多 seed 或全量重训会增加资源成本；最终全量重训本身不提供新的独立验证分数。

**迁移实验：** 用低成本比较不同模型家族；保存相同验证协议下的预测和错误分布，再检验组合是否带来净提升。跨题通用的是选择和验证方法，具体模型与特征由任务决定。

### CrowdFlower 冠军：缓存预测让组合搜索便宜

来源：[冠军仓库 README](https://github.com/ChenglongChen/Kaggle_CrowdFlower/blob/a72eabb2e53c308c345905eff79c3c8e3a389239/README.md)、[固定 folds](https://github.com/ChenglongChen/Kaggle_CrowdFlower/blob/a72eabb2e53c308c345905eff79c3c8e3a389239/Code/Feat/gen_kfold.py)、[ensemble selection](https://github.com/ChenglongChen/Kaggle_CrowdFlower/blob/a72eabb2e53c308c345905eff79c3c8e3a389239/Code/Model/ensemble_selection.py)。比赛为 2015 年，代码使用较旧的 Python / sklearn 接口。

作者报告最佳单模型的 private LB 为 `0.70768`，最终 35 个提交的 median ensemble 为 `0.72189`。README 说明最终提交从 public LB 表现好的提交中选择；这属于该次比赛经历，不能作为泛化保证。

源码先固定 folds，训练模型库并保存验证预测，再从这些预测搜索组合与权重。组合评价使用比赛的 Quadratic Weighted Kappa，省去了每次重新训练模型的成本。

**迁移实验：** 在样本 ID 对齐、fold 和预处理来源可追溯的条件下缓存 OOF 预测；用冻结开发协议选择组合，再独立确认。需要观察候选的错误互补性，不能仅按单模型分数取前几名，也不能把某次 public LB 选择经验泛化到新任务。

### SIIM-ISIC 亚军：以患者为单位切分，并改进训练信号

来源：[Ian Pan 的亚军仓库](https://github.com/i-pan/kaggle-melanoma/blob/caaec0d7e9cafc7b405eb86e7fdf00107d89e1d9/README.md)、[患者级切分源码](https://github.com/i-pan/kaggle-melanoma/blob/caaec0d7e9cafc7b405eb86e7fdf00107d89e1d9/src/etl/1_create_cv_splits.py)。

切分脚本先将每位患者压成一行，构造分层 outer / inner folds，再按 `patient_id` 合并回所有图像；同一患者的图像共享分组。README 的流程包含 ISIC 2019 模型、额外诊断标签、跨年份训练、伪标签与后续训练，说明提分可以来自数据和训练信号，而非只更换 backbone。

**迁移实验：** 先找相关样本的基本单位，再决定切分。对训练信号、外部数据和伪标签分别做有归因的实验，验证其规则许可和泛化收益。本次没有训练这些模型，也没有核验完整流水线的每个数据处理步骤。

### Pahcer：逐例比较和可重复调参的工程支持

来源：[AHC 本地测试工具](https://github.com/terry-u16/pahcer/blob/32bbf0645c2d1c1866e8c34d75a12387e505633a/README.md)。本次确认 README 中的 seed 批测、JSON 输出、历史结果、相对评分和 Optuna 接口。

它保存逐 seed 结果并支持参数优化，适合把评测机械工作与策略推理分开。README 明确提示并行时运行时间只供参考；正分数算 accepted，耗时过长也不会自动算 TLE。相对分数还依赖持续更新的历史最佳值。

**迁移实验：** adapter 保留原始指标并自行检查比赛时限；比较时冻结相对分数的参照，或在同一参照下重算历史候选。可以借鉴工具接口，不能将其 accepted 字段直接当作比赛有效性。

## 对当前 Skill 的落实

本轮只加强实验决策说明，没有引入付费服务、自动提交或通用重框架：

| 决策能力 | 加入流程的具体方法 | 何时使用 |
| --- | --- | --- |
| 有方向的检索 | 按题型、目标、规模、规则和瓶颈检索，将来源转成可否证的假设 | 选 baseline、缺少机制或搜索停滞时 |
| 组件内深入优化 | profile / 消融定位后，围绕组件连续探索，按实际反馈调整或换路线 | baseline 已稳定，且预算足够时 |
| 改变解题空间 | 将状态表示、编码、邻域和训练信号列入候选机制 | 现有参数搜索收益很低时 |
| 用实验学习 | 对照已评测候选的代码与逐例结果，分开记录事实、解释和下一步测试 | 每次有信息量的成功或失败后 |
| 组合与复用 | 检查错误互补性，缓存来源一致的预测和中间结果，单独评测组合 | 格式、规则和资源允许时 |

这些变化已融入 [`SKILL.md`](../skills/competition-optimize/SKILL.md) 的主流程和 [`score-search.md`](../skills/competition-optimize/references/score-search.md) 的实验动作选择、组件内迭代与证据记录。按题型选择具体实验时读取 [`task-playbooks.md`](../skills/competition-optimize/references/task-playbooks.md)；评分实现、聚合与有效性字段的核查写入 [`adapter-contract.md`](../skills/competition-optimize/references/adapter-contract.md)。

## 如何验证泛化能力

下一步应选彼此不同的任务：表格建模、含分组或时间结构的数据任务、组合优化、带随机性或时限约束的任务。在相同模型、预算和硬件下比较基础流程与增强流程，记录最终独立分数、有效结果率、费用、耗时和失败原因；重复完整 agent 运行以观察波动。只在开发任务上调整 skill，保留未用于流程调整的任务做确认。

可参考 [ALE-Bench](https://github.com/SakanaAI/ALE-Bench/tree/3da9b12fb5d112dabb3af693d1a42031c95142bc) 与 [MLE-bench](https://github.com/openai/mle-bench/blob/507f92e1138bb6e40dac5c6ee7a6758e6424bf97/README.md) 的任务和评价结构。MLE-bench 对公开训练数据重新切分，结果不等于原比赛隐藏 private test；其完整集为 75 个任务，Lite 为 22 个低复杂度任务，Lite 的成功不足以证明复杂任务能力。是否能够检索历史获奖解法也应单独记录，以区分资料辅助解题与面向新题的能力。

`Kaggle/kaggle-skills` 的[检查版本](https://github.com/Kaggle/kaggle-skills/tree/e5b4d148d8758a900c9f8192f294de00010e31ce)主要包含 benchmark 编写、agent exam 和 hackathon judging，不能仅凭“官方 skills”名称就当作自动优化比赛的实现。

当前仓库已有固定时隙题 adapter 和标准预测 CSV 的指标评测层，后者用合成数据验证了指标与比较行为。真实训练流程、泄漏验证和跨题型提分效果仍需要上述实测。
