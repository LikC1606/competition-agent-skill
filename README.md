# Competition Agent Skill

一个以分数最大化为目标的竞赛优化流程：Codex 从题目目标和约束推导策略，学习强方案的整体设计，再结合你的想法、当前代码与历史实验实施优化、实际评测并更新判断。实现请求应交付代码、实测对比和可复现产物；学习方案的请求先讲清思路、推导和对当前解法的启发。

当前仓库包含通用的 `competition-optimize` 控制流程、固定时隙 C++ 评测 adapter，以及通用预测 CSV 评测、比较、抽样不确定性估计、错误诊断和固定权重集成工具。核心流程面向不同竞赛题型；每项任务仍需核对其规则、指标和验证协议。比赛源代码、二进制和评测结果不会被复制到本仓库。

## 最小版本

架构是 **一个通用 Codex skill + 按题型扩展的评测适配器 + 可恢复的长周期驱动器**：

- **Skill**：指导 Codex 固定官方目标，从题目独立推导表示与构造方式，理解高分方案中构造、定价和维护如何配合，再比较路线、实施完整机制并按官方指标分析反馈。
- **比赛适配器**：提供题型专属的候选接口、硬约束、评测和官方评分计算；当前有算法/代码 adapter，以及预测 CSV 的 RMSE、MAE、二分类 LogLoss 和 ROC-AUC 评测层。可按独立样本或完整组估计固定预测的抽样不确定性，诊断开发集误差与分组退步，生成加权集成候选，并将冻结配方复用于确认集或测试集。数据准备、训练、防泄漏和资源验证仍需按比赛接入。
- **长周期驱动器**：[autonomous_campaign.py](skills/competition-optimize/scripts/autonomous_campaign.py) 在后台持续唤起 Codex，默认无轮次上限；模型自报“完成、卡住、没思路”会触发重新规划。独立 worker 和后台守护负责故障恢复与证据对账。每轮自动注入最好版本、失败和备选分支；成绩停滞时重审策略，执行失败或缺分数时转入带真实诊断的修复，另独立定期轮换上下文。策略、评分与晋升仍由 agent、adapter 和任务协议负责；[启动、停止和恢复说明](skills/competition-optimize/references/unattended-campaign.md)。

候选档案工具 [`candidate_archive.py`](skills/competition-optimize/scripts/candidate_archive.py) 提供评测前重复检查、JSONL 追加记录与紧凑历史摘要。重复测量改用固定大小的历史链接，避免重复 ID 在磁盘上平方增长，查询时仍还原完整展示。它根据同契约开发结果、路线历史最好成绩和有依据的未解决机会输出继续、换路线或诊断建议；确认集不会改变优化建议，必要复测需说明原因。官方分数、下一项具体实现与晋升仍由 adapter 和 agent 按题目规则决定。

同条件复测出现排名反转时，档案支持先写入固定的配对测量计划，再按预定 run/seed 核对后续真实结果；中断后可继续未完成的配对，而不会把碰巧收集的分数取均值或自动改变代表排名。

现在还能[把提案连到实际执行结果](skills/competition-optimize/references/iteration-trace.md)：agent 先引用父版本代码和开发反馈提出具体改动，再把新评测结果、观察和预测是否成立接回提案。`trace` 明确区分待执行、已评测和已停止，拒绝用旧结果、未改流水线或确认反馈冒充一次优化。默认只展开最近八项，保留全部待执行 ID，恢复任务时不用重读所有历史。

新增只读的 [`brief` 入口](skills/competition-optimize/references/iteration-trace.md#retrieve-evidence-for-the-next-implementation)，一次取回同口径历史最好代码、最近失败反馈、备选路线及未完成提案。最好版本不受近期退步影响，备选按实测目标排列，重复测量不能靠幸运高分或改路线名制造新代表。agent 随后直接读相关代码、提出并实施改动，无需增加一份记录。

高分参考之外，`review_frontier` 单独检索有明确未决反馈的历史分支，包括低分旧路线和同路线的多个机会。长期驱动在成功交接后轮转曝光，失败或中断不消耗机会；失败、缺分数或仍未解决的子代也不会关闭父代机会。每项同时带上已尝试的真实子代及身份，供 agent 判断下一步，不强制选父代或自动分配试验次数。

未完成提案也会在成功交接后轮转，避免早期工作被最新四项永久挡住；`trace --proposal-id` 能直接找回原代码目标和当前结局。提案按首个父代归属，跨口径修复参考只带身份与源码/result 指针并要求重验。执行/策略重审的检查点同样成功后才提交，429 或失败调用不会把尚未交接的诊断记成完成。机制与源码依据见[恢复迁移记录](docs/source-study-20261022.md#未完成提案接回真实执行)。

已完成试验通过 `trial_history` 继续影响下一次构造：原先“为什么改、改了什么、预期看到什么”与实际结果、源码及反馈一起交接。当前/最好实现相关的近期试验优先，旧试验另按成功交接轮转，避免完成后只剩一个脱离假设的失败标签。Agent 据此辨认缺失能力并调整方案；跨口径需重验，执行失败不等于方法无效。借鉴 RefineEvo 的经验回注、OpenEvolve 的实测 artifacts 和 HeurAgenix 的具体轨迹，见[实现与来源](docs/source-study-20261022.md#已完成试验影响下一次构造)。

消融与反事实试验可显式记为 `diagnostic`：绑定普通开发控制版本，保留源码、结果及反馈，用于选择下一项构造；它们不参与候选排名或被误计为候选停滞。失败诊断仍须修复，真正的优化退步仍记普通候选。借鉴 MLE-STAR 将消融指导与候选保留分开的实际流程，见[诊断迁移](docs/source-study-20261022.md#诊断试验指导构造而不参与候选排名)。

评测口径不断变化也会掩盖空转：每个实现只有自己的基线，代码一直变却没有共同对照。新增 `comparison_continuity` 保留这些缺口，穿插成功的 smoke 测试也不会清零；积累到触发窗口后，切换到 `measure`，交接孤立实现、合同差异和参考源码，要求在合法共同开发口径下补测后再比较。复用旧源码的真实新测量可以补齐对照，跨口径分数始终独立。设计借鉴与边界见[共同基准迁移](docs/source-study-20261022.md#评测口径缺少共同对照)。

进一步区分实现与产物：同训练流水线的随机预测差异会保留为多次测量，不能制造新方法或路线进步；算法源码改动可沿用原配置。缺少训练代码的旧预测保留分数并标出证据缺口，输出文件也不能冒充代码优化目标。

仓库全套 **392 项测试通过**，覆盖诊断分流、已完成试验召回、共同基准重审、未完成提案轮转、跨口径修复、失败重审、旧分支后继及成功交接记账。独立 Agent 用新版 skill 完成“消融→反馈→机制改进”，隔离背包任务开发目标 **624→627**，保留三项前瞻提案和四项真实 adapter 结果。此前共同基准恢复的 11 次受控 CLI、40 次真实执行，以及故障恢复、复测档案增长和真实 Codex 交接证据均保留，详见[验证记录](docs/unattended-campaign-validation.md)。这不代表华为官方提分或跨日可靠性已获验证。此前工具的受控拟合、程序执行和效率结果见[效率记录](docs/efficiency.md#区分真实实现改动与随机输出差异)。

## 无人值守启动

在已有题目、当前代码、baseline 和可运行评测器的工作区中：

~~~sh
/usr/bin/python3 skills/competition-optimize/scripts/autonomous_campaign.py start \
  --workspace /absolute/path/to/contest \
  --task-file /absolute/path/to/contest/continuing-task.md \
  --campaign /absolute/path/to/contest/agent-runs/campaign-01 \
  --archive /absolute/path/to/contest/agent-runs/campaign-01/candidates.jsonl \
  --background
~~~

命令返回后继续运行，断开终端不影响守护进程。用 status 查看候选数、实际执行的新实现、下一步、心跳和 token；stop 完成本轮后停止，stop --now 取消当前本地执行；resume --background 对账后继续。各命令均传 --campaign 指向同一目录。默认开放式持续优化；只有配置的完成验证器、用户停止、显式资源限制或实际主机/证据阻塞能结束任务。主机重启后需 resume，或由系统服务恢复。

默认同口径 4 个有效新实现没有刷新历史最好分时请求新上下文重审，--stagnation-window 可调整；每 8 个成功检查点独立轮换上下文，--session-checkpoints 可调整，0 可关闭周期轮换。两者均可在 start/resume 配置，保留累计历史和消耗，均不构成候选额度或停机规则。每轮证据包固定保存在 turns/NNNNNN/context.json 并注入 prompt。实现依据见[源码迁移记录](docs/source-study-20261022.md#长期驱动器中的实际迁移)。

失败、部分完成或成功却缺少可用分数的开发执行，下一轮直接进入 repair；默认连续 3 次没有可用观测时切新上下文重新诊断，--failure-review-window 可在 start/resume 调整。真实错误、源码身份和开发参考父代随包交接；可用低分会结束执行失败串，但仍接受独立成绩停滞判断。缺分数不等于算法无效，三次失败也不会停止 campaign。细节见[失败恢复迁移](docs/source-study-20261022.md#执行失败分流与长期档案)。

`--comparison-review-window` 默认 4：自上次成功测量重审后，新增且至今仍只有一个有效实现的口径达到该数才触发共同基准重审。合法 smoke→full 切换并为两边建立对照会消除相应缺口；失败调用不提交检查点。此配置同样支持 start/resume，只影响重审时机，开放式 campaign 会继续运行。

核心循环不依赖题型，但搜索策略和验证方式由 adapter 提供。没有可靠评测器时，先建立并验证评测器，不进入昂贵搜索；尚未实现 adapter 的题型不能宣称已支持自动优化。

## 工作流程

1. **新建或恢复**：读取题目、当前实现和近期结果，核对未完成实验，复用依赖匹配的评测器与 baseline；固定指标、硬规则、开发和确认协议。预算记录来源与作用范围，保留历史消耗。
2. **核验评测器**：新建或口径变化时用已知正反例核对评分；已有匹配评测器沿用原证据。区分本地官方指标、平台回执与代理指标。
3. **推导策略、学习强方案**：复用可信 baseline，从目标、约束、可用信息和评分时间尺度描述理想解及可行构造，再看当前代码缺少什么能力。有高分方案时读懂其表示、构造、内部代价、维护和算力分配的联系，分清已有能力、覆盖范围和真正差异。普通续跑复用已有理解；新资料或连续局部小改才触发重审。详见[策略推导](skills/competition-optimize/references/strategy-design.md)。
4. **高效提出并实施优化**：结合题目推导、你的想法和参考方案，用有边界的侦察检查相关源码、成功/失败版本和评测身份，选择最小完整实现。结构假设可以先于实测瓶颈提出；说明依据、必要的耦合组件和可观察预期即可进入原型验证。维护候选档案，避免重复改动，尊重明确的试验优先级。先实施候选并做接口、硬规则和评测一致性检查，再进入昂贵评测；默认不安排参数搜索。
5. **反馈决定下一次实现**：实际编译、训练或执行，与父版本和当前最好版本比较有效性、完整目标及成本。判断预测是否成立，分别决定是否晋升和是否继续投入；将本次证据接到具体的下一项代码/流水线改动，返回第 4 步实际运行。平台期按[恢复流程](skills/competition-optimize/references/plateau-recovery.md)分清不可避免损失、可行改善和代理失配，再测试新的表示或完整方法。备选先保留源码与开发结果，不默认逐个独立确认和打包；共享机器的计时干扰不自动作废有效质量证据。结束一条路线后继续选择有依据的下一项实现，后续试验之间不等待用户再次提示。
6. **确认与交付**：用户停止、实际硬约束/资源条件阻止继续、具体阻塞无法解决或任务完成条件通过验证时，冻结候选并独立确认，输出方案、提交包和迭代链：实测结果 → 反馈决定 → 已实施的后继改动 → 新结果或停止原因。暂时没有新思路时重新推导路线；未运行的建议明确标为待执行。

第 4–5 步持续反复执行，具体反馈分支见 [score-search.md](skills/competition-optimize/references/score-search.md#close-the-feedback-loop)：

```mermaid
flowchart TD
    A[从题目推导策略；学习强方案整体设计] --> I[对照当前代码与相关历史，识别能力差异]
    I --> B[提出完整机制并实现候选]
    H[你补充的想法或优先试验要求] --> B
    B --> C[实际评测并对比]
    C --> D[反馈：分数、错误、瓶颈与成本]
    D --> E[更新最好版本；选择下一项具体改动]
    E --> F{下一步决策}
    F -->|修复、深入或组合| B
    F -->|平台期或缺少新思路| A
    F -->|用户停止、实际约束或验证完成| G[冻结、独立确认与交付]
```

## 提供你的想法

开始时或 agent 正在迭代时，直接用自然语言补充即可。例如：

> $competition-optimize 继续优化。我怀疑当前只做两两交换容易卡住，优先实现一次多位置重排，与当前最好版本按相同评测口径比较。

> 我觉得错误可能与时间有关，这个想法供参考。结合当前特征、数据划分和历史结果判断，值得就实现验证，否则说明原因。

> 先讨论这个想法，暂时不要改代码：能否把两条路线按输入特征组合起来？

Agent 会保留你的原意，区分建议、优先试验和明确要求，把想法接到具体代码位置、假设及验证办法。一般建议参与下一步方案选择；明确要求试验时优先执行可行方案。遇到影响实现的歧义才定向澄清，常规细节说明假设后继续。

如果你说“重点是学习这个高分方案的思路”，agent 会先解释核心设计、如何从题目想到、各组件为何配合，以及我们应改变什么，不默认再开一轮测试。学习范围内保持只读；同时授权实现时，再把理解转成完整候选。

反馈包含“你的想法 → 实际实现的解释 → 候选与实测对比 → 下一步”。未验证的想法会标为待执行或说明推迟原因，已有类似失败会引用历史证据。新想法不会清空已测结果或重新开始整个流程。处理规则见 [用户想法接入](skills/competition-optimize/references/score-search.md#turn-user-ideas-into-experiments)。

## 关键约定

- 按官方指标决定候选，明确越大越好或越小越好；缺少评分参数时保留分项和 Pareto 候选，代理指标只用于暂定搜索。
- 不设置默认的时间、计算、候选数量或轮次数额。记录每个 baseline、失败实现、修复版本和复测的实际消耗，利用反馈持续实施下一项有价值的优化；只有比赛硬规则、实际资源条件或用户当前明确的限制会停止搜索。
- 用户取消或调整限制后，从后续决策开始按新范围继续，保留累计记录和已消耗资源；不把历史 skill 默认值当成仍然有效的额度，也不要求通过“再开一轮”获得许可。
- 不将自定的最小收益、最大减速或与 incumbent 完全相同的输出当成比赛要求；等价加速可检查输出一致性，其他有效解按实际目标比较。
- 默认由 agent 结合题目结构、用户想法、强方案及代码历史推导下一步并实施验证；不自动做网格、随机、贝叶斯或邻近值扫描。用户明确要求调参时才开启专门的参数搜索。
- 先做有边界的策略与代码侦察，足以选择机制就实施；不遍历无关日志，也不把实测局部瓶颈当成提出新表示的前置条件。候选先过接口、硬规则、评测身份、产物可复现和目标口径质量门，再进入昂贵评测。
- 持续维护 incumbent、runner-up、不同路线代表、待验证候选和失败机制；新候选必须有指纹和父版本，近重复改动需要新证据。连续弱结果时切换表示、模型、邻域、数据或策略，不用便宜小改耗尽可用资源。
- 优化期间保持评测口径一致；评测器变化后，重新评测需要比较的版本。
- 保留独立验证场景，用于检查最终候选的泛化表现。
- 每次实验记录父版本、假设、代码快照、配置、指标、耗时、状态和失败原因。
- 最好版本与最新版本分别保存，失败实验不覆盖已验证的方案。
- 输出提交包；正式提交按用户授权和比赛配额处理。

## 源码研究结论

2026-10-23 借鉴 LLM4AD Next 的空父集生成与 Comind 的可选 codebase：新增 `construction_mode=independent`，让验证过的父版作为比较控制，`code_targets=[]` 明确不继承旧源码。模式进入提案、真实后继和跨轮交接；独立结果不再误关闭控制父版的改进机会。[用法与边界](skills/competition-optimize/references/iteration-trace.md#declare-an-independent-construction)说明默认 refinement 不变，模式声明不认证创新性或信息隔离。

独立 Agent 从固定区间调度任务推导并实现带重建的动态规划，真实总收益 **693→938（+35.35%）**，全套 **414 项检查通过**。这是单个隔离任务的实际可用性验证，没有旧版 Agent 对照或官方提分结论。[验证记录](docs/unattended-campaign-validation.md#独立构造与比较控制分开2026-10-23)保留原始证据。

2026-10-23 将 Telco 的“实际实现复核 → 下一次构造”接入运行链：可选 `--implementation-review` 将实际机制、缺失组件和后继源码 hash 绑定原 proposal，由 `brief`、`trace` 和 `trial_history` 交给下一轮。忠实度与真实成绩独立，原方案没有进入代码的部分不会因一次弱结果被当作已测失败；它不改变排名或要求每个不完整方案重试。用法见[实现复核](skills/competition-optimize/references/iteration-trace.md#review-the-actual-implementation)。

独立 Agent 根据历史复核与源码补全缺失组件，固定开发集仍为 1097→1097，保留更简单父版；全套 408 项检查通过。[证据与边界](docs/unattended-campaign-validation.md#实际实现复核指导后继2026-10-23)区分了机制补全与真实提分，本轮没有官方成绩提升结论。

2026-10-23 继续借鉴 EoH-S 的逐实例选亲与 Telco 的次优实现保留：`brief.complementary_evidence` 自动找回总分较低但有真实局部胜例的已执行候选，将胜负实例与源码交给下一次构造。可选 `case_profile` 仅作为构造依据，排名仍使用实际总分；预测工具支持 `--case-profile` 输出可分解损失。具体合同与边界见[逐实例互补检索](skills/competition-optimize/references/iteration-trace.md#retrieve-complementary-case-evidence)。

独立 Agent 使用新交接后，在隔离背包任务中选择并实现精确容量 DP，实测总利润 1075→1127（+4.84%）；全套 402 项检查通过。[证据与边界](docs/unattended-campaign-validation.md#最新逐实例互补证据接入构造2026-10-23)保留实际命令和源码。这是本地使用验证，尚未证明官方比赛提分。

2026-10-22 扩展研究补充了[完整策略生成、条件经验与源码边界](docs/source-study-20261022.md)：先生成结构不同的完整候选，保留对实际目标有用的互补分支；将相对父代的成败用于后续提案；把预测筛选与真实分数分开，并按运行代码核查提出的机制是否真正实现。固定版本和代码行号见 [source-patterns.md](skills/competition-optimize/references/source-patterns.md)。这轮是静态源码研究与 skill 改进，未运行第三方 Agent 或复现其成绩。

- 从 AIDE 借鉴父子候选记录、先产生 baseline 和一次只提出一个可检验改进的做法。
- 从 ShinkaEvolve 借鉴窄范围可变代码区、非 Python 评测适配和结构化正确性结果。
- 将 AIDE 式搜索选择与 Shinka 式评测/检查能力组合成一个轻量闭环；第一版不引入外部进化框架或多 agent 群组。
- Meta 的 LLM Speedrunner 是更贴近算法优化的参照：阶段化假设、实现、执行、分析，版本化工作区记录候选历史。其完整实验框架与 GPU/Slurm 配置不纳入 MVP。
- MLEvolve 的停滞检测、跨分支经验值得后续验证；其 MCGS、多 agent、embedding memory 和 Kaggle 数据栈不作为首版依赖。
- FDE-Bench 的离子束均匀性 case 是“优化/均匀性”表述上的近邻，但实际任务是预测曲线；只参考任务澄清和 evaluator 设计。case 数据和实现没有开放再分发许可，不复制进本仓库。
- 评分器以程序输出为准；测试失败、耗时和多项指标都作为单独证据。模型的解释用于选择下一项实验，不直接决定候选分数。
- 保留可运行的最好版本，并用固定测试集配对比较；缺少可信后继时重新审视策略，按用户停止、实际约束、具体阻塞或验证完成条件结束。

完整的源码依据、竞品取舍和首版接口草案见 [`docs/research.md`](docs/research.md)。

新增流程借鉴 MLE-STAR 的搜索与组件内优化、ReEvo 的候选对照学习、ALE-Agent 的表示和邻域搜索，以及获奖选手的验证与互补集成经验。具体来源和适用条件见[补充研究](docs/automation-and-solving-experience.md)；按题型选择实验时读取 [task-playbooks.md](skills/competition-optimize/references/task-playbooks.md)。这些是已写入 skill 的决策方法，提分效果仍需跨任务对照验证。

## 验证边界与历史案例

2026-10-22 的华为云优化暴露了另一类偏差：虽然已有大量实测与组件改动，却过早接受了旧解法的搜索空间。用户要求学习公开高分方案时，工作仍偏向模块迁移和继续测试。本次据此补充[独立策略推导与高分方案学习](skills/competition-optimize/references/strategy-design.md)：从最终配额推导构造、把稳定性放入候选生成、按收益寿命理解轨迹定价、按变化依赖推导增量维护。案例用于展示推导过程，不把具体算法、常量或规则设为通用要求；保留实现请求的执行闭环。本次修改的技能检查不构成比赛提分证据。

2026-10-10 的实际使用中，用户反馈“只分析或小改，没有实质推进”。复核发现两轮共运行 9 个变体，但多数仍围绕同一优化器微调，且反复受额度询问、自定速度门槛和缺失评分参数影响，没有产生更强发布版。本次据此重写执行入口、移除人为默认额度、纠正代理门槛和路线分类；详见[实际使用复盘](docs/execution-first-revision.md)。此次为指令和文档修正，尚未经过新版的完整 agent 实战验证。

已使用华为云固定时隙均匀调度算法题验证 adapter，覆盖 C++ 函数接口、在线增删操作、均匀性与稳定性权衡、运行时间，以及禁止乘除、取余和浮点运算的限制。

现有比赛材料与解法留在原工作区。算法 adapter 已有 11 项单元测试及真实 smoke/full 运行验证；预测 CSV 工具新增指标、样本对齐、异常输入、评测契约比较及 CLI 测试。

另已完成两个公开真实数据集的[受限表格 pilot](docs/tabular-pilot.md)，串联训练、诊断、冻结组合与独立确认，并与 sklearn 独立计分核对。回归组合在本次确认集有约 0.54% 的 RMSE 改善，但区间跨零；分类出现开发/确认排名反转。该结果已用于加强 loader 防泄漏审查、排名稳定性判断和预先声明的确认决策。它是预设脚本的集成验证，跨任务自主提分能力仍待独立对照。

已做[效率优化与对照](docs/efficiency.md)：入口按决策需要加载参考，复用匹配的中间结果；bootstrap 缓存损失与 AUC 排序，在八项计时中约提速 1.9–7.4 倍，逐次结果与旧实现一致。该性能比例只描述抽样评测，不代表完整比赛流程提速。

主流程现已加强[路线选择与较大候选替换](docs/route-search-pilot.md)：先比较解题路线，再深入表示、算法、训练信号或策略，收益饱和时重新选择路线。候选可以替换完整耦合流水线。算法端到端示例中，两组各六个候选名额，路线组冻结方案在新 seed 的 12 个确认实例上平均路径长度降低约 17.3%，参数组未超过 baseline；路线组使用更多计算。这是预设合成任务的说明性对照，不能作为自主 agent 或真实比赛提分的证明。

继续投入时新增[弱结果诊断与完整路线对照](docs/route-search-pilot.md#弱结果之后怎样投入)：不把低分或工作上限直接解释为整个方法失败，也不给每条路线自动追加试验。本次固定协议中，较弱构造接上完整搜索后明显改善，但仍未胜过第一名，两组选择相同；全面探索用了更多计算。结果支持有证据的投入判断，未证明新增流程提分。

进一步将[实验反馈接到下一项可执行改动](docs/route-search-pilot.md#让反馈改变下一项实验)：先记录预测是否得到支持，再限定解释与迁移条件。三个候选的条件脚本试验中，上限附近仍在改善的证据触发搜索顺序改动；较弱路线开发长度降低约 3.36%，仍未超过最好方案，因此保留 baseline。这个收益未独立确认，也不是自主 agent 生成方法的效果证明。

错误分析可用 [`--summary-only`](skills/competition-optimize/references/data-model.md#diagnose-development-errors)保留全样本核验、分组摘要和最差案例，按需导出完整逐例表。50,000 行 RMSE 对照中，摘要诊断约提速 1.89 倍，Python 分配峰值从 66.5 MB 降到 35.3 MB；两项真实数据的 6 个候选对照诊断一致，默认完整导出字节不变。

决定是否尝试两模型组合时，可按需增加 [`--check-blend-direction`](skills/competition-optimize/references/data-model.md#check-whether-a-two-parent-blend-has-a-useful-direction)：对 RMSE/MAE 检查目标函数方向，排除无法严格超过最好单体的理想凸组合，并识别较弱模型可能提供的组合价值。它不选择权重或给出组合分数；每个实际测试的配方仍计一次 trial，其他指标需另作判断。已通过 144 项测试和两题集成复跑，尚未证明完整 agent 的试验节省或提分效果。

新增同契约预测的[批量评测入口](skills/competition-optimize/references/data-model.md#batch-ready-candidates)：单进程顺序评分、独立候选证据和可选基线比较。两项 CLI 对照约提速 4.5–5 倍；12 份既有真实数据预测的分数、hash 与契约一致，未重训模型。批量数量不改变试验预算，确认只处理冻结候选。

候选档案工具已用 23 个行为测试覆盖重复拦截、训练前流水线检查、父版本、无效反馈、口径变化、停滞判断、中断恢复与确认隔离，并回放两项真实数据 pilot 的 12 份既有结果，保留原分数、hash 和检查范围。未重新训练或执行新比赛候选；自主提分与节省试验的效果仍需实战验证。

流程新增[决策卡与恢复路由](skills/competition-optimize/references/decision-loop.md)：继续任务只补读变化的事件和当前决策所需证据，实验完成但未记账时先核对产物，候选预算耗尽后进入冻结确认。只读的 `inspect_run_resume.py` 自动核验契约/日志检查点，分页返回新增事件，拒绝损坏记录，检查点仅覆盖本页事件。已对两个真实 pilot 的历史记录做回放核对，保留原交付规则与预算；这不代表完整 agent 的提分或耗时对照。

复用预测缓存时，可给[比较命令](skills/competition-optimize/references/data-model.md#compare-local-scores)增加 `--truth`，核验标签/预测字节及安装中的 evaluator，并重算保存的分数，输出独立核验回执。快速比较继续保留；评分口径变化时仅重做受影响的评测，数据或训练变化时另核对拟合来源。

训练前可用[数据划分检查](skills/competition-optimize/references/validation-split.md)核对 ID 重叠，并按协议检查分组隔离、时间边界与标签可用时间。回执可在依赖一致时复用，避免逐模型重复检查；它核验声明的划分记录，实际拟合与上游预处理仍需另查。

使用便宜评测淘汰候选前，可用[筛选校准工具](skills/competition-optimize/references/screening.md)检查参考候选的排序反转，以及按计划保留数量会漏掉哪些完整开发评测最优候选。支持两阶段各自的指标方向与并列容差，适用于配对标量分数；分数与候选关联由 adapter 核验，筛选不能替代完整评测。

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
