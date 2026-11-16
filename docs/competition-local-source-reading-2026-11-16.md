# 专业比赛项目：下载与本地源码精读

2026-11-16，已将上一轮的 12 个重点及支撑仓库下载为 13 份固定 commit 的源码快照，包含 claude-scholar 的 main／codex 两个版本，以及 MLE-STAR 所在的历史官方版本。下载目录为 `/data/lzh/downloads/competition-skills-agents-20261116/`。

进一步补读与理论分析见[完整研究报告](competition-skills-agents-research-report-2026-11-16.md)，包括当前 skill 的已有覆盖、RD-Agent 可选重评路径、机制等价性与采用优先级。

本机入口：[下载索引](/data/lzh/downloads/competition-skills-agents-20261116/README.md)、[版本与压缩包校验值](/data/lzh/downloads/competition-skills-agents-20261116/sources.json)。共 8,585 个随仓库分发的文件，压缩包合计约 268.5 MiB；这些是下载量，不是通读文件数。完整 ADK 历史快照还包含 MLE-STAR 之外的示例。原始压缩包保留在 `archives/`，没有安装依赖、运行上游程序或进行比赛实验。

阅读集中于实际 SKILL、提示词、资料客户端、切分脚本、候选选择、评测和经验回流的调用链。下文 **E** 表示已读源码直接支持，**I** 表示由源码与当前需求推得的建议或条件结论。版本及上游链接见[收集清单](competition-skills-agents-2026-11-16.md)。

## 阅读后的采用判断

最值得借鉴的仍是具体衔接：**强资料的身份与正文 → 有明确训练边界的本地评测 → 状态／行为支持的机制提案 → 执行结果与条件经验 → 下一项实现**。没有必要因下载了框架，就迁移其整个主循环。

| 用户方向 | 本地代码中最有用的机制 | 对现有工作流的建议（I） |
| --- | --- | --- |
| 更会找专业资料 | shepsci 区分榜单关联与搜索线索；NVIDIA 缓存讨论及回复 | 记录真实比赛、排名来源、正文与纠正；发现候选后回读全文及匹配代码 |
| 高质量本地评测 | FrankS 的验证先行和持久划分；ALE-Bench 的实际评价调用顺序 | 把训练索引、标签可用时间及评分过程落实到执行，不能只检查 fold 文件和分数格式 |
| 不拟合公榜 | ALE-Bench 先开发选择、后 private 评价 | 继续沿用当前独立确认规则；历史排名用于发现资料，当前公榜反馈用于诊断 |
| 有依据地改进 | RD-Agent 的假设／diff／结果反馈；MLE-STAR 的消融与历史计划比较 | 将预期行为、具体实现、实际结果和失败原因接到同一提案，明确什么证据会改变下一步 |
| 改进机制 | HeurAgenix 的操作映射与轨迹前缀重放；SkyDiscover 根据最优程序构思并实施新方向 | 先用已有轨迹定位缺失行为，再提出完整机制并绑定父程序；避免把批次收益归给每个想法 |

## 专业资料：检索命中还要保留发现关系

**E：shepsci 的来源分级有实际实现。** [leaderboard_writeups.py](/data/lzh/downloads/competition-skills-agents-20261116/shepsci-kaggle/skills/kaggle/modules/discussions/scripts/leaderboard_writeups.py:108) 优先读取已发布 private board，否则 public board，通过 `teamId` 关联排名和 writeup。第 411 行起的后备搜索带精确 `competitionIds`，但返回项标为 `source=content-search, rank=None`。正文预览默认截到 360 字符，完整 writeup 另有读取命令。

**I：优先借鉴这种关系区分。** 历史强队排名能帮助发现方案；普通讨论也可能提供关键纠正，但不应被虚构成获奖方法。预览、搜索摘要、正文和匹配实现各有不同证据范围。

**E：NVIDIA 能先抓取、再围绕问题查询本地缓存。** [discussion_client.py](/data/lzh/downloads/competition-skills-agents-20261116/nvidia-kaggle/skills/nvidia-kaggle-skill/scripts/discussions/discussion_client.py:130) 支持热门、票数、评论及时间排序，详情读取会递归收集回复。其搜索请求使用比赛标题与 competition 类型，未附精确比赛 ID；解析时却用请求的比赛 ID 标注记录归属。当前抓取集合也受页数限制，本地查询不自动扩大远端召回。

**E：缓存成功的范围需要细分。** [discussion_ingest.py](/data/lzh/downloads/competition-skills-agents-20261116/nvidia-kaggle/skills/nvidia-kaggle-skill/scripts/discussion_ingest.py:46) 仅在已有 body 为空时填入详情正文，评论读取出错会打印后继续；`last_fetched_at` 不是全文及评论均刷新成功的证明。

**I：可以吸收缓存和回复读取，但引用前仍需核对真实比赛、原文及关键纠正。** 标题近似造成错归是上述代码允许的条件风险，本轮没有调用 API 证实实际发生。缓存里搜不到也不能推出没有相关资料。

**E：Scholar 的更新提示能保留跨比赛机制和适用条件，但自动入库没有验证知识。** Codex 的 [miner](/data/lzh/downloads/competition-skills-agents-20261116/claude-scholar-codex/agents/kaggle-miner/AGENTS.md:15) 要求实际方案、实现细节和来源；[learner](/data/lzh/downloads/competition-skills-agents-20261116/claude-scholar-codex/skills/kaggle-learner/SKILL.md:112) 还支持从会话提取 root cause、workaround 和条件。抽查的 [AIMO 笔记](/data/lzh/downloads/competition-skills-agents-20261116/claude-scholar-codex/skills/kaggle-learner/references/knowledge/nlp/aimo-2-2025.md:208) 在第 208 与 1016 行对 GRPO 给出不一致展开；[Konwinski 学习模板](/data/lzh/downloads/competition-skills-agents-20261116/claude-scholar-codex/skills/kaggle-learner/references/knowledge/nlp/konwinski-prize-2025-6th-place-study.md:185) 用 `max(scores) < percentile(scores)` 表达拒绝条件，正常有限数值下无法实现其意图。这些是知识笔记中的具体问题，不能归因给原参赛代码。

**I：把这类知识库作为检索线索；对会进入当前提案的机制，回查原文和实现。** 不需要为不影响当前决策的全部条目进行穷尽审计。

## 本地评测：切分建议必须落实到训练与评分

**E：FrankS 的验证设计建议很有用，时间划分产物的保证更窄。** [make_folds.py](/data/lzh/downloads/competition-skills-agents-20261116/franks-agentic-kaggle/scripts/make_folds.py:339) 生成划分时只保存 `valid_idx` 对应的 fold ID，丢弃 `train_idx`。`auto` 同时收到 group/time 参数时先选 group。脚手架的 [train.py 模板](/data/lzh/downloads/competition-skills-agents-20261116/franks-agentic-kaggle/scripts/scaffold_competition.py:70) 仍是待实现入口。

**I：若时间任务的消费者直接用 `fold != current_fold` 训练，早期验证可能读到后期数据。** 这是对消费者写法的条件推断，没有声称已经跑出泄漏。时间 CV 需要保存或重建每次训练前缀、标签可用时间；实体与时间同时构成信息边界时，也不能认为自动选择一种策略就满足两者。

**E：运行日志提供证据，但状态名不等于有效成绩。** FrankS 的 [prepare_kaggle_kernel.py](/data/lzh/downloads/competition-skills-agents-20261116/franks-agentic-kaggle/scripts/prepare_kaggle_kernel.py:26) 生成逐指标、异常与产物日志；第 140 行起的默认运行块却只是写假 submission 和 `placeholder_metric=0.0, stage=smoke`，然后标记完成。**I：可复用日志接口，成绩采信仍应依据实际阶段、评分器和有效性证据。**

**E：ALE-Bench 的开发／最终评价区分体现在调用链里。** [主流程](/data/lzh/downloads/competition-skills-agents-20261116/ale-bench/src/ale_bench_eval/__main__.py:123) 先按 public 结果选择，完成自改进，再构造各预算前缀的候选，最后统一 private 评价。[自改进](/data/lzh/downloads/competition-skills-agents-20261116/ale-bench/src/ale_bench_eval/scaffolds.py:406) 使用 public feedback，未通过判题的候选记最差分。这里的 public/private 是 benchmark 的开发与最终评测角色，不应仅按名称等同于 Kaggle 公榜／私榜。

**I：值得吸收的是反馈方向和调用时机。** 其 repeated sampling 默认可按 median 选解，服务模型能力测量的目的；这不是比赛夺分时通用的选择策略。确认结果一旦用于修改，便不再独立。

## 算法改进：让状态与行为进入提案

**E：HeurAgenix 的反例诊断比泛化反思具体。** [heuristic_evolver.py](/data/lzh/downloads/competition-skills-agents-20261116/heuragenix/src/pipeline/heuristic_evolver.py:233) 把同实例的好坏轨迹、最终解、分数和当前源码交给瓶颈识别，再重放负轨迹前缀，恢复操作前状态，提出能改变该状态输出的修改。[提示词](/data/lzh/downloads/competition-skills-agents-20261116/heuragenix/src/problems/base/prompt/identify_bottleneck.txt:27) 要求排除等价变化和不影响最终成本的差异，优先找引发后续问题的第一步。

**I：优先从已有轨迹复用这种诊断。** 它可以说明为什么改变操作、状态表示或选择规则，而不是只追一个分数；单个反例仍只支持机制诊断，不足以排名完整方法。

**E：正例筛选不能统称为已验证可行。** [扰动筛选](/data/lzh/downloads/competition-skills-agents-20261116/heuragenix/src/pipeline/heuristic_evolver.py:195) 最多尝试 100 次，发现更好分数就停止，但忽略 `run(env)` 的布尔返回；[求解器](/data/lzh/downloads/competition-skills-agents-20261116/heuragenix/src/pipeline/hyper_heuristics/perturbation.py:21) 返回的正是完整性与有效性。**I：移植前必须用任务合法性过滤轨迹，不能把未完成解的低成本当成优良行为。**

**E：HeurAgenix 也允许调参。** [extract_suggestion.txt](/data/lzh/downloads/competition-skills-agents-20261116/heuragenix/src/problems/base/prompt/extract_suggestion.txt:11) 同时允许修改超参数、增加逻辑、条件化逻辑和替换操作。**I：保留当前默认机制改进规则，只吸收其状态定位、可解释操作与跨状态检查。**

**E：SkyDiscover 按最优程序构思新方向，并优先施于当前最优程序。** [controller.py](/data/lzh/downloads/competition-skills-agents-20261116/skydiscover/skydiscover/optimize/search/adaevolve/controller.py:340) 从当前最优源码、评价文本和已试想法生成范式；第 508 行起在实施时重新选择当前最优父项，同时保留兄弟候选和错误上下文。这不等于跨多次使用冻结了生成想法时的代码身份。[database.py](/data/lzh/downloads/competition-skills-agents-20261116/skydiscover/skydiscover/optimize/search/adaevolve/database.py:463) 区分本岛获得的改进和迁入成果，后者不领取本岛 UCB 奖励。**I：可以借鉴其上下文选择意图，在现有档案中明确绑定提案／父程序／结果，不必引入整套岛模型。**

**E：它的收益归因和停滞公式不能直接当机制证据。** [tracker.py](/data/lzh/downloads/competition-skills-agents-20261116/skydiscover/skydiscover/optimize/search/adaevolve/paradigm/tracker.py:244) 将同批期间的 best-score 总增量赋给该批每个用过的范式，并以固定 `0.001` 标成功；[adaptation.py](/data/lzh/downloads/competition-skills-agents-20261116/skydiscover/skydiscover/optimize/search/adaevolve/adaptation.py:85) 在未发现新最优时直接返回，局部 G 并非每个无提升轮次都会衰减。**I：应保留实际实施及其比较关系，不能将批次进展当作每个想法的独立收益。**

**E：LoongFlow 的文本经验与数值调度分两条路径。** [summary_agent.py](/data/lzh/downloads/competition-skills-agents-20261116/loongflow/agents/math_agent/summary/summary_agent.py:218) 从父子代码和评价生成反思，存入 `summary`，下次随所选父方案 JSON 进入规划；第 262 行起的采样权重另由父权重、分差、子分数和迭代位置计算，不由反思文本决定。[Boltzmann 采样](/data/lzh/downloads/competition-skills-agents-20261116/loongflow/src/loongflow/agentsdk/memory/evolution/boltzmann.py:249) 在开启对应配置时使用该权重。

**I：可借鉴“经验确实进入后继上下文”，不要写成反思自动控制数值采样。** 权重公式包含原始子分数，不保证退步子代的权重低于父项，也不是对评分尺度不变的通用规则。

## 机器学习研究循环：总结、搜索和最佳选择分别检查

**E：EvoMaster 的轮内经验会回流，长期检索写回在已读主链中未接通。** [入口](/data/lzh/downloads/competition-skills-agents-20261116/evomaster/playground/ml_master_2/core/playground.py:196) 从本地 `example_wisdom` 检索；[prefetch_exp.py](/data/lzh/downloads/competition-skills-agents-20261116/evomaster/playground/ml_master_2/core/exp/prefetch_exp.py:75) 使用 top-1 和 `0.7` 阈值。逐轮 knowledge promotion 被送回下一轮 research；timeout 时的 wisdom promotion 解析后返回并写日志，已读调用链没有写回检索库，正常完成路径也没有自动执行该提炼。

**E/I：该版本的方向内 best 有静态控制流问题。** [第 240 行起](/data/lzh/downloads/competition-skills-agents-20261116/evomaster/playground/ml_master_2/core/playground.py:240) 固定方向 baseline，每个超过它的成功候选都覆盖 `direction_best`。若越大越好、baseline 为 `0.70`，依次得到 `0.80`、`0.75`，该路径会留下 `0.75`；这是代码推演，没有执行该示例。[评分与格式检查](/data/lzh/downloads/competition-skills-agents-20261116/evomaster/playground/ml_master_2/core/exp/improve_exp.py:45) 还包含 Metric Agent 从日志提取分数，以及格式服务失败时默认放行的路径。

**I：吸收轮内“计划→结果→条件总结→下轮研究”，不替换当前确定性评测和候选选择，也不宣称已经得到自动跨任务学习。**

**E：RD-Agent 的假设确实落实到实现与失败反馈。** [proposal.py](/data/lzh/downloads/competition-skills-agents-20261116/rd-agent/rdagent/scenarios/data_science/proposal/exp_gen/proposal.py:1184) 从 best 和失败历史生成假设及实现任务，继承父代码；[loop.py](/data/lzh/downloads/competition-skills-agents-20261116/rd-agent/rdagent/scenarios/data_science/loop.py:211) 将代码变化、分数与异常送回历史。配置类默认主要改整条 pipeline，knowledge base [默认关闭](/data/lzh/downloads/competition-skills-agents-20261116/rd-agent/rdagent/app/data_science/conf.py:78)，research RAG 与 fixed seed/split 也[默认关闭](/data/lzh/downloads/competition-skills-agents-20261116/rd-agent/rdagent/app/data_science/conf.py:178)。runner 检查候选生成的 `scores.csv` 结构和提交格式，并非独立重算其验证分数。

**I：可迁移“检验一个核心概念，允许必要协同修改”的提案方式，以及失败回流。** 组件标签、分数文件结构和模型审阅不能替代训练／评分边界。

**补读：上述评分描述只针对日常 runner。** RD-Agent 另有可选 [ValidationSelector](/data/lzh/downloads/competition-skills-agents-20261116/rd-agent/rdagent/scenarios/data_science/proposal/exp_gen/select/submit.py:264)，共用新数据和 grade.py 重跑候选；默认最终 selector 并非这条路径。新 test 标签仍放在候选可访问的 input 目录，因此统一重评也不能自动解释为封存确认，具体见完整研究报告。

**E：MLE-STAR 的搜索、消融和后继计划有实际连线。** 历史官方实现的 [initialization agent](/data/lzh/downloads/competition-skills-agents-20261116/mle-star-historical/python/agents/machine-learning-engineering/machine_learning_engineering/sub_agents/initialization/agent.py:342) 真正挂载 Google Search，再运行候选排序；保存的检索 schema 只有模型名和示例代码，未要求来源 URL、commit 和成绩证据。[refinement agent](/data/lzh/downloads/competition-skills-agents-20261116/mle-star-historical/python/agents/machine-learning-engineering/machine_learning_engineering/sub_agents/refinement/agent.py:141) 执行消融、总结结果、定位原始代码块；下一计划收到历史改进量和耗时。全部没有提升时保留原解。

**I：优先学它由结果决定改哪里及如何继续，另保留当前来源链与确定性评分。** 消融损失说明现有方案依赖该组件，并不直接证明它剩余提升空间最大。该实现也没有建立封存确认集协议；数据泄漏审阅默认关闭。

## 接入工具：只借已有责任的具体接口

**E：ShinkaEvolve 的 setup／convert／run／inspect 四份 SKILL 都已落地。** [inspect 实现](/data/lzh/downloads/competition-skills-agents-20261116/shinkaevolve/skills/shinka-inspect/scripts/inspect_best_programs.py:166) 打包源码、父项、分数、有效性和反馈；没有正确项时明确标注回退，供检查使用。[评测包装器](/data/lzh/downloads/competition-skills-agents-20261116/shinkaevolve/shinka/core/wrap_eval.py:314) 记录逐次有效性并拒绝非有限总分。但 setup 的 `validate_fn` 示例默认返回 True，`public/private` 默认空字典，这些模板字段本身不提供可信评测。

**I：借鉴紧凑的“源码＋反馈”阅读包即可。** 当前 archive 已保留失败、互补和未决分支，不能仅导出 top-k 高分项便替换全部决策上下文。此次也已读取其根 LICENSE，确认为 Apache-2.0。

## 阅读与交付范围

三份详细记录保留了调用链、精确行号及实际阅读文件／片段清单：[比赛 skills](/data/lzh/workspace/outputs/competition-skill-research/20261116-local-reading/skills-reading.md)、[机器学习 agents](/data/lzh/workspace/outputs/competition-skill-research/20261116-local-reading/ml-agents-reading.md)、[算法与评测支撑](/data/lzh/workspace/outputs/competition-skill-research/20261116-local-reading/algorithm-reading.md)。关键本地摘录和证据卡在同目录 `.deep-research/`；没有把搜索命中、文件枚举或下载量计作正文阅读。

本轮完成下载、关键源码阅读与设计判断，并修订上一轮清单中保证过宽的表述。尚未将上游代码或指令融合到当前 skill；没有进行训练、模型调用、比赛提交或效果排名。
