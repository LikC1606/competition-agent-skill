# 专业比赛 Skills 与 Agents 收集

核查日期：2026-11-16。范围是 Kaggle／机器学习工程与算法优化比赛，围绕用户的五个方向筛选：找强资料、设计本地评测、防公榜过拟合、有依据地改进、改变机制。优先级表示对当前工作流的借鉴价值，不是系统性能排名。

后续已按用户要求下载 12 个仓库、13 份固定版本快照并阅读关键实现，见[下载与本地源码精读](competition-local-source-reading-2026-11-16.md)。本地复读补充了时间训练索引、资料身份、正例有效性、经验写回及候选选择的实际边界；下文已据此收窄相关结论。

本轮通过 skills.sh、`npx skills find kaggle`、GitHub 检索、官方材料和固定版本源码发现与核查对象。只做资料和静态源码研究，未安装这些 skill／agent，也未运行训练、模型调用或比赛效果实验。能力描述依据已读材料；建议迁移什么是设计判断，效果仍待验证。NVIDIA、RD-Agent 和 MLE-STAR 属于对已有收集的更新核查，其余重点对象补充了新的入口或机制。

共整理 10 个重点对象，另更新 ShinkaEvolve 和 ALE-Bench 两个接入／评测支撑项目。对当前流程最有针对性的组合是 **比赛资料入口 + FrankS 的验证设计 + HeurAgenix 的机制诊断 + ML-Master 的条件经验提炼**，继续沿用现有确定性评测和候选档案。

## 优先收集的 Skills

| 对象 | 实际用途与可复用部分 | 接入当前工作流的边界 |
| --- | --- | --- |
| **FrankS-IntelLab/agentic-kaggle-skill** | 验证优先的比赛求解：固定 folds、metric-correct baseline、OOF，然后实施有意义的模型／流水线变更 | 最贴近比赛迭代；应适配其实际提交、公榜回执、远程 GPU 与调参默认行为 |
| **NVIDIA/nvidia-kaggle** | 题面、规则、讨论及评论、kernels、获奖复盘和 research brief | 适合作为资料入口；后续机制实现与可信比较仍由现有循环承担 |
| **shepsci/kaggle-skill** | 统一的公共资料读取和 Kaggle 平台操作，支持保存正文、源码和 metadata | 与 NVIDIA 的研究流程有继承关系；按访问需求选择入口，无须叠加两套主流程 |
| **Galaxy-Dawn/claude-scholar：kaggle-learner + kaggle-miner** | 从前排方案抽取机制、代码模式和经验，积累题型知识 | Codex 应看 codex 分支；单装 learner 不等于已经注册 miner，也不等于建立候选评测 |

### FrankS：优先借鉴验证与完整流水线

[完整 SKILL](https://raw.githubusercontent.com/FrankS-IntelLab/agentic-kaggle-skill/3cdd820356c80fbdd946138d2f86cbc2bd5e91b9/SKILL.md)第 10 行要求先把比赛看成验证问题，第 15–18 行把 folds、baseline 和 OOF 放在更强架构之前。[CV 指南](https://raw.githubusercontent.com/FrankS-IntelLab/agentic-kaggle-skill/3cdd820356c80fbdd946138d2f86cbc2bd5e91b9/references/cross-validation-and-metrics.md)要求识别测试采样单位、实体与时间边界、fold 内 fitting，并在 CV／公榜不一致时先检查 split、metric、format 和 drift。[make_folds.py](https://raw.githubusercontent.com/FrankS-IntelLab/agentic-kaggle-skill/3cdd820356c80fbdd946138d2f86cbc2bd5e91b9/scripts/make_folds.py)实际提供随机、分层、分组和时间划分，但输出只保存验证 fold ID、丢弃训练索引；时间训练边界仍需消费者正确实现，不能仅凭该 CSV 宣称无未来泄漏。

它还覆盖 embedding、增强、伪标签、蒸馏、校准、集成和多阶段模型。[competition-intel](https://raw.githubusercontent.com/FrankS-IntelLab/agentic-kaggle-skill/3cdd820356c80fbdd946138d2f86cbc2bd5e91b9/references/competition-intel.md)按验证、模型、训练和执行提取公开方案，MCP 不可用时允许手动检索。最值得吸收的是 **测试条件 → folds → OOF → 完整机制 → 匹配比较**。

直接使用前需要修改作用范围：SKILL 第 21–22、123–127 行把取得实际 Kaggle public score/status 作为完成条件，其他段落包含远程 GPU 和专门参数搜索。当前用户的正式提交授权、资源限制、默认机制改进与独立确认规则应继续生效。已读 case study 的排名改善叙述缺少具体可核验的比赛／分数链，本轮不把它当作效果证明。

### NVIDIA 与 shepsci：把原始资料送进研究分支

NVIDIA 的 [research-brief](https://raw.githubusercontent.com/NVIDIA/nvidia-kaggle/2b78cf29f5f30680764292a6592de8d53d4147a8/skills/nvidia-kaggle-skill/research-brief.md)组织官方页面、discussion、kernels 和 writeups，要求具体技巧链接到来源，明确区分标题中的作者分数声称、实际获取分数和票数。[discussion_read.py](https://raw.githubusercontent.com/NVIDIA/nvidia-kaggle/2b78cf29f5f30680764292a6592de8d53d4147a8/skills/nvidia-kaggle-skill/scripts/discussion_read.py)确实提取正文与评论，相关 client 依赖 Kaggle token 和网页会话。其 [18 项 benchmark](https://raw.githubusercontent.com/NVIDIA/nvidia-kaggle/2b78cf29f5f30680764292a6592de8d53d4147a8/BENCHMARK.md)评的是触发、工作流、效率和回答准确性，未证明端到端比赛提分。

shepsci 的 [SKILL](https://raw.githubusercontent.com/shepsci/kaggle-skill/a47bff9830af088bfce3bf974343916370137d1f/skills/kaggle/SKILL.md)提供公共 `brief/pages/solutions/writeup/topics/topic` 等入口；这部分可无凭据读取，账户、下载及 notebook 操作有不同依赖。[研究参考](https://raw.githubusercontent.com/shepsci/kaggle-skill/a47bff9830af088bfce3bf974343916370137d1f/skills/kaggle/modules/competitions/references/competition-research.md)把 raw text 和分析分开，并保存 notebook 源码、metadata 与版本；正文明确说明研究流程改编自 NVIDIA，因此两者不是独立的效果证据。

shepsci 的 [validate 实现](https://raw.githubusercontent.com/shepsci/kaggle-skill/a47bff9830af088bfce3bf974343916370137d1f/skills/kaggle/modules/competitions/scripts/competition_validate.py)明确只查 CSV 形状、ID、缺失和有限数值，不能评价预测质量。[平台操作指南](https://raw.githubusercontent.com/shepsci/kaggle-skill/a47bff9830af088bfce3bf974343916370137d1f/skills/kaggle/modules/competitions/references/competition-operations.md)将预期本地分数与公榜分歧作为诊断线索。它适合提供平台事实；本地验证仍需任务专属设计。

### Kaggle Learner：用作机制线索库，按 Codex 分支接入

核查了 main 与 codex 两个版本。当前环境更相关的是 [codex SKILL](https://raw.githubusercontent.com/Galaxy-Dawn/claude-scholar/b672e80951a2348dd6136316d096603bf2dc5b83/skills/kaggle-learner/SKILL.md)、[miner 的 AGENTS](https://raw.githubusercontent.com/Galaxy-Dawn/claude-scholar/b672e80951a2348dd6136316d096603bf2dc5b83/agents/kaggle-miner/AGENTS.md)和[注册文件](https://raw.githubusercontent.com/Galaxy-Dawn/claude-scholar/b672e80951a2348dd6136316d096603bf2dc5b83/agents/kaggle-miner.toml)。它要求读取实际 solution/discussion 并保留来源，按比赛简介、前排方案、代码模式和实践沉淀知识。

main miner 的专用网页 MCP 与 `~/.claude` 路径限制不能泛化到 codex 分支；codex 已使用通用 web tools。自动挖掘仍需要 host 支持、agent 注册和网页工具。已有 [AIMO 知识样例](https://raw.githubusercontent.com/galaxy-dawn/claude-scholar/d394fb599ed9e6ea2212a9e6daa864345fe97a26/skills/kaggle-learner/references/knowledge/nlp/aimo-2-2025.md)没有逐项建立细粒度原始来源链，所以知识摘要宜用来发现线索，再回读获奖帖、论文和版本代码。无需继承其 Top 20 或固定输出结构作为每轮配额。

### 可选安装定位

以下仅提供已发现的安装定位，未执行安装。`@` 后为技能名称，不是固定 commit；复用前应核对上表与版本表指定的内容。

```sh
npx skills add franks-intellab/agentic-kaggle-skill@agentic-kaggle-skill
npx skills add nvidia/nvidia-kaggle@nvidia-kaggle-skill
npx skills add shepsci/kaggle-skill@kaggle
```

2026-11-16 的目录查询分别返回 FrankS `30`、NVIDIA `61`、shepsci `591`、kaggle-learner `448` 次安装；这些只是发现渠道的快照，不能推出机制或效果优劣。Galaxy 的目录命令默认指向主分支；Codex 接入应明确选择已核查 codex 分支，并核对 miner 注册，而不是直接混用 main 配置。

## 值得研究的机器学习比赛 Agents

### ML-Master 2.0／EvoMaster：将执行经验分层沉淀

原 ML-Master 的 [README](https://raw.githubusercontent.com/sjtu-sai-agents/ML-Master/d55311af2a3a9038952a31b8ca6d7771454f54ce/README.md)指向 EvoMaster；当前更合适的代码入口是 EvoMaster 的 [ML-Master 2.0](https://raw.githubusercontent.com/sjtu-sai-agents/EvoMaster/50dc0000ebaf7a1dfe8b5fef44c690b2026bf176/playground/ml_master_2/README.md)。实际阶段包含知识预取、初始解、研究方向、隔离实现、知识总结和跨任务经验提炼。[orchestrator](https://raw.githubusercontent.com/sjtu-sai-agents/EvoMaster/50dc0000ebaf7a1dfe8b5fef44c690b2026bf176/playground/ml_master_2/core/playground.py)把计划、执行结果与后续总结相连，[知识总结提示](https://raw.githubusercontent.com/sjtu-sai-agents/EvoMaster/50dc0000ebaf7a1dfe8b5fef44c690b2026bf176/playground/ml_master_2/prompts/knowledge_promotion_user_prompt.txt)要求区分执行是否符合预期、值得深入的方向与低价值路线。

对当前 workflow 的价值是：把原始执行、任务内结论和跨任务经验分开，检索时保留适用条件与来源。本地复读确认任务内总结会进入下一轮规划；prefetch 检索本地示例库，已读主链尚未把新 wisdom 自动写回检索库。现有 `scoped_learning` 已承担部分责任，应先补实际缺口，不必为层级名称迁入一整套框架。

边界也很具体：[improve_exp.py](https://raw.githubusercontent.com/sjtu-sai-agents/EvoMaster/50dc0000ebaf7a1dfe8b5fef44c690b2026bf176/playground/ml_master_2/core/exp/improve_exp.py)由 metric agent 从终端文本提取分数，且 grading server 失败时存在默认通过格式检查的路径。这些行为不应代替当前确定性 adapter 与有效性证据。运行还需模型／embedding 接口、数据和计算资源；源码存在不等于已经复现论文效果。

### RD-Agent：假设、组件实现和反馈的完整链

[Data Science 文档](https://raw.githubusercontent.com/microsoft/RD-Agent/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/docs/scens/data_science.rst)描述提出假设、选择动作、实现、验证和反馈；自定义任务需要 description、prepare、valid 和 grade 等明确接口。[实际 loop](https://raw.githubusercontent.com/microsoft/RD-Agent/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/loop.py)区分 data loader、feature、model、ensemble 与 pipeline 开发，并把运行结果送回 feedback。[策略说明](https://raw.githubusercontent.com/microsoft/RD-Agent/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/proposal/exp_gen/README.md)区分 draft、idea、merge 和 router。

优先借鉴具体假设如何落到组件与执行反馈，特别是特征、训练目标和数据流水线，而不只换模型常数。它是独立框架，接入成本高于 skill；文档出现 validation、test 或 Kaggle leaderboard 时仍需按用途辨明开发与最终评测，不能仅沿用名称便认为已经隔离。

### MLE-STAR：检索和有依据的组件改进，保留历史入口

历史官方 [README](https://raw.githubusercontent.com/google/adk-samples/7d187b6f97522915a153b1cdc30a8f4a164c7b5a/python/agents/machine-learning-engineering/README.md)、[initialization 源码](https://raw.githubusercontent.com/google/adk-samples/7d187b6f97522915a153b1cdc30a8f4a164c7b5a/python/agents/machine-learning-engineering/machine_learning_engineering/sub_agents/initialization/agent.py)与 [refinement 源码](https://raw.githubusercontent.com/google/adk-samples/7d187b6f97522915a153b1cdc30a8f4a164c7b5a/python/agents/machine-learning-engineering/machine_learning_engineering/sub_agents/refinement/agent.py)直接支持：用搜索获取模型和示例，运行初始候选，再用消融选定代码块并进行组件内改进。它特别对应“从资料找到机制”与“说明为什么改这里”。

这份官方仓库现重定向到 `google/adk-recipes`；2026-07-23 的清理提交移除了旧示例，当前完整 main tree 中未找到该目录。因此按固定历史版本收集方法，不能把旧目录写成当前可直接安装入口。消融后损失大说明现有解依赖该组件，并不自动证明它剩余可改进空间最大；还需结合机制、上限与执行成本。

## 算法优化比赛的专业机制

### HeurAgenix：论文迁移与正负轨迹驱动的启发式改进

Microsoft 的 [HeurAgenix](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/README.md)面向 TSP、CVRP、JSSP、MaxCut、MKP 等组合优化问题，声明了 evolution／validation／test／smoke 划分。它在本轮新对象中最直接连接“从专业资料提取机制”和“根据失败行为改进”。

[heuristic_generator.py](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/src/pipeline/heuristic_generator.py)读取给定论文／LaTeX，先检查摘要相关性，再选择章节，直到能够实现或放弃；也可以分析相似问题的操作和启发式源码，进行组件映射。这里的能力是资料到代码的迁移，外部强解的主动检索仍需另接。

[heuristic_evolver.py](https://github.com/microsoft/HeurAgenix/blob/e84bfb19e785ae2d670af6e3ab68890c71c536ea/src/pipeline/heuristic_evolver.py)第 195–310 行在同一实例保留基线负轨迹，通过扰动寻找分数更好的正轨迹，比较两条轨迹、最终解与分数，定位瓶颈操作，再重建操作前状态并提出具体修改。正例筛选忽略了求解器返回的完整性／有效性布尔值，因此不能统称为已验证可行正例。第 328–388 行比较旧版、新版和基线，并在声明的 validation 实例上评价。这提供了比“再调一个值”更明确的后继依据。

适合借鉴 **资料 → 操作映射 → 行为反例 → 具体启发式修改 → 开发验证**。内部平均相对改进不能直接替换正式比赛计分；存在分目录的数据集也不证明 test 的访问被限制或只在最终调用。运行成本还包括扰动、完整求解与可选 Monte Carlo rollout，本轮没有核验其比赛奖牌、费用上限或新实例泛化收益。

### SkyDiscover：由进展调整搜索，分别理解 Optimize 与 SkySynth

其 [Optimize](https://github.com/skydiscover-ai/skydiscover/blob/0d932b690670a7e544388ad362e9876c8bd256a0/skydiscover/optimize/README.md)执行 `sample → prompt → generate → evaluate → add`，将分数、日志和产物放回候选数据库。[AdaEvolve](https://github.com/skydiscover-ai/skydiscover/blob/0d932b690670a7e544388ad362e9876c8bd256a0/skydiscover/optimize/search/adaevolve/README.md)按近期奖励分配预算、调整探索强度，并在全局停滞时请求新范式；[EvoX](https://github.com/skydiscover-ai/skydiscover/blob/0d932b690670a7e544388ad362e9876c8bd256a0/skydiscover/optimize/search/evox/README.md)进一步演化采样／选择策略。

可借鉴的是实测进展如何改变下一项搜索动作。不要直接继承默认指标：Optimize 文档说明缺少 `combined_score` 时会平均数字指标，比赛 adapter 应明确正式目标。[实际 controller](https://github.com/skydiscover-ai/skydiscover/blob/0d932b690670a7e544388ad362e9876c8bd256a0/skydiscover/optimize/search/evox/controller.py)还有候选迭代之外的搜索策略演化调用，比较成本需包含这些调用。容器和超时支持也不能单独证明独立确认集或数据隔离协议。

仓库另有 [SkySynth 的 SKILL](https://github.com/skydiscover-ai/skydiscover/blob/0d932b690670a7e544388ad362e9876c8bd256a0/skydiscover/synthesize/workflow/SKILL.md)，要求读固定 commit 参考系统、形成规格、实现、逐轮评测并审计新 best。它属于系统构建流程，不宜与 Optimize 合称为已经打通的比赛求解 skill。自动强解检索、完整费用硬上限和效果复现本轮未核验。

### LoongFlow：反思应改变后续采样

官方仓库是 `baidu-baige/LoongFlow`。其 [PES](https://github.com/baidu-baige/LoongFlow/blob/945c78bc1554f8281aac40320b3599bd68d528d7/src/loongflow/framework/pes/README.md)组织 Planner → Executor → Summary，任务仍需用户提供初始程序和 evaluator。[math planner](https://github.com/baidu-baige/LoongFlow/blob/945c78bc1554f8281aac40320b3599bd68d528d7/agents/math_agent/planner/plan_agent.py)读取记忆和父方案；[summary_agent.py](https://github.com/baidu-baige/LoongFlow/blob/945c78bc1554f8281aac40320b3599bd68d528d7/agents/math_agent/summary/summary_agent.py)比较父子程序及其分数，生成反思，调整后续采样权重并保存经验。

可借鉴“结果 → 条件解释 → 下一次选什么”的连接。文本反思作为父方案字段进入后继上下文，数值采样权重另由分数和迭代位置计算，不能混称为模型反思直接决定权重。已读 planner 的工具主要查询内部记忆，不能据此称它已能主动学习比赛强解。[PES 成本实现](https://github.com/baidu-baige/LoongFlow/blob/945c78bc1554f8281aac40320b3599bd68d528d7/src/loongflow/framework/pes/pes_agent.py)依赖配置单价，缺少单价时成本可记为零，不能把日志 cost 当作完整账单。其独立进程超时评价支持故障恢复，但没有建立独立确认协议的证据；示例 README 的成绩口径还需另核，不引用为收益结论。

## 接入和评测支撑的更新

**ShinkaEvolve** 的 [2026-11-13 README](https://github.com/SakanaAI/ShinkaEvolve/blob/7ab55d7254d2732b26d9c30dde23ab777de631cb/README.md)确认 setup、convert、run、inspect 四个 skills：适合建立 evaluator、接入已有代码、执行和查看候选。它是现有研究对象，本轮补核了当前技能入口。`max_api_costs` 可限制后续新提案，但异步在途调用仍要记账，不应承诺精确费用封顶。借鉴接入与证据查看接口即可，尚无迁入完整进化框架的收益依据。

**ALE-Bench** 的[评测文档](https://github.com/SakanaAI/ALE-Bench/blob/8ba16e6baf743aa8736516c45d1c52afdbd4de99/docs/evaluation.md)提供 public 迭代选择、private 最终评价，以及对话、结果、时间和成本文件，是算法比赛评测结构的直接参考。它是 benchmark 与 scaffold；单独名为 ALE-Agent 的当前独立发布范围未核验。不能从猜测路径的 404 推断未开源，也不能把 benchmark 安装成功当作专业求解能力。

## 五个方向对应的采用顺序

| 用户方向 | 最有针对性的来源 | 建议迁移的责任与产出 |
| --- | --- | --- |
| 更会查专业资料 | NVIDIA／shepsci、Codex kaggle-learner | 先选一个平台入口；来源、版本、适用条件和当前能力差距进入现有 `basis`，摘要回查到原文 |
| 高质量本地评测 | FrankS、ALE-Bench，按题型参考 HeurAgenix | 从测试单位和信息边界设计开发协议；保留完整目标和独立确认，不把格式检查当模型评测 |
| 不过拟合公榜 | FrankS 的 CV/LB 诊断与 ALE-Bench 的开发／最终评价区分 | 分歧触发验证假设；新 split／权重需有任务依据，最终选择不靠反复 public probing |
| 有理由地改进 | MLE-STAR、RD-Agent、LoongFlow | 从代码、机制预期和实际结果形成可反驳的提案，再决定实现修复、改变路线或补测 |
| 改变机制 | HeurAgenix、FrankS；停滞时参考 AdaEvolve | 优先改变信息、操作、表示、训练信号与选择能力；完整实现依赖组件，保留行为证据 |

先整理可借鉴片段和任务接口，再决定是否接入。当前 archive、proposal、`scoped_learning`、测量计划和确认规则已有相应责任；迁移时应补具体缺口，避免新增重复主循环。本文没有发现已核验同时满足全部五个方向、可以直接替代当前工作流的单一项目。

## 未列为优先求解入口的对象

官方 Kaggle skills 的核查版本包含 [benchmark 编写](https://raw.githubusercontent.com/Kaggle/kaggle-skills/e5b4d148d8758a900c9f8192f294de00010e31ce/write-kaggle-benchmarks/SKILL.md)、[agent exam](https://raw.githubusercontent.com/Kaggle/kaggle-skills/e5b4d148d8758a900c9f8192f294de00010e31ce/kaggle-standardized-agent-exam/SKILL.md)和 [hackathon judging](https://raw.githubusercontent.com/Kaggle/kaggle-skills/e5b4d148d8758a900c9f8192f294de00010e31ce/hackathon-judging/SKILL.md)。这些分别服务评测编写、考试和主办方判分，不能只因官方名称而当成参赛优化器。

另读了独立的 [liaoruoxue/ml-master-skills](https://raw.githubusercontent.com/liaoruoxue/ml-master-skills/d68c4d650f48fb43e14b70165eefaacbf33f2b65/skill/SKILL.md)：它把 HCC 思想写成 L1／L2／L3 文件、总结和恢复指令，但含 Claude hooks、每五次操作记笔记等固定规则。适合作为记忆组织参考，不是官方 ML-Master 2.0 的等价运行实现，也没有本轮核验的比赛收益。

此前已研究的 AIDE、OpenEvolve、LLM4AD／ReEvo 不重复作为“新发现”。其早期证据见[已有研究](automation-and-solving-experience.md)；不能将旧版本结论自动当作本轮最新版本的核查结果。

## 已核查版本与许可

下表日期是对应 commit 的 UTC 日期，不是仓库 `pushed_at`，也不证明该项目之后没有其他分支活动。许可证记录指根目录已读许可／官方 license 元数据，不扩展到外部数据、模型和依赖。

| 对象／分支 | 固定 commit | 日期 | 许可 |
| --- | --- | --- | --- |
| FrankS main | `3cdd820356c80fbdd946138d2f86cbc2bd5e91b9` | 2026-10-28 | MIT |
| NVIDIA main | `2b78cf29f5f30680764292a6592de8d53d4147a8` | 2026-08-04 | MIT |
| shepsci main | `a47bff9830af088bfce3bf974343916370137d1f` | 2026-10-03 | MIT |
| claude-scholar main | `d394fb599ed9e6ea2212a9e6daa864345fe97a26` | 2026-10-19 | MIT |
| claude-scholar codex | `b672e80951a2348dd6136316d096603bf2dc5b83` | 2026-09-23 | MIT，已读该分支 LICENSE |
| EvoMaster main | `50dc0000ebaf7a1dfe8b5fef44c690b2026bf176` | 2026-10-09 | Apache-2.0 |
| RD-Agent main | `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` | 2026-09-23 | MIT |
| MLE-STAR 历史官方示例 | `7d187b6f97522915a153b1cdc30a8f4a164c7b5a` | 2026-07-23 | Apache-2.0 |
| HeurAgenix main | `e84bfb19e785ae2d670af6e3ab68890c71c536ea` | 2025-12-15 | MIT |
| SkyDiscover main | `0d932b690670a7e544388ad362e9876c8bd256a0` | 2026-09-14 | Apache-2.0 |
| LoongFlow main | `945c78bc1554f8281aac40320b3599bd68d528d7` | 2026-04-09 | Apache-2.0 |
| Kaggle/kaggle-skills main | `e5b4d148d8758a900c9f8192f294de00010e31ce` | 2026-06-06 | Apache-2.0 |
| 独立 ml-master-skills main | `d68c4d650f48fb43e14b70165eefaacbf33f2b65` | 2026-03-26 | MIT |

支撑项目另核对 ShinkaEvolve `7ab55d7254d2732b26d9c30dde23ab777de631cb` 的入口，后续本地复读确认根 LICENSE 为 Apache-2.0。ALE-Bench 核查版本为 `8ba16e6baf743aa8736516c45d1c52afdbd4de99`，[README 许可说明](https://github.com/SakanaAI/ALE-Bench/blob/8ba16e6baf743aa8736516c45d1c52afdbd4de99/README.md)区分代码 Apache-2.0 与数据 CC BY-ND 4.0。

## 收集与验证范围

关键能力核对了 SKILL／README、相关参考和实际实现入口，未以星数、安装量或“Grandmaster”角色设定代替证据。上游的论文／benchmark 分数不是本项目的效果结果，本文不据此做横向性能排名。

本轮部分原文、locator 与证据卡保存在 `/data/lzh/workspace/outputs/competition-skill-research/20261116-795am4ic/`；另有按固定 commit 直接读取到内存的核查，本文保留其来源链接与范围。未抓取完整数据集或运行上游安装说明。当前交付是资料清单与接入建议，尚未自动融合这些外部工作流。
