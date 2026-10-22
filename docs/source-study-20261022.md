# 自动比赛 Agent 源码研究：让搜索产生不同的解法

这次研究最有价值的改变，是把候选生成单元从“当前代码的一处改动”扩展为“能完整工作的策略假设”。强方案往往先改变状态表示、构造方式、信息使用或模块间协调，再做局部优化。增加实验数量只能更准确地比较已经提出的候选；它无法补出从未考虑过的策略。

研究包含算法进化、Kaggle/机器学习、编程竞赛和评测基础设施。逐项区分完整控制器、组件、宿主 skill、生成代码/轨迹、结果仓库和资料索引。以下依据是固定 commit 上的静态源码阅读，没有运行第三方 Agent，也没有独立复现作者成绩。

## 最值得借鉴的机制

| 决策问题 | 源码支持的做法 | 迁移到本 skill |
| --- | --- | --- |
| 为什么候选总是相似 | CoMind 先提出完整路径再分解组合；KAPSO 用不同研究视角产生方案，再独立选择 | 先明确哪些能力不同，再实施原子改动；没有必要在机制已清楚时强制凑固定路线数 |
| 怎样摆脱旧代码的假设 | LLM4AD Next 有不读记忆、无父代的生成分支 | 停滞时允许从题目重新构造；不让失败记忆或 incumbent 限定所有新方案 |
| 非第一名是否还有价值 | EoH-S 保留逐实例互补覆盖；MCTS-AHD 保留可继续扩展的祖先 | 保留会影响实际目标或后继探索的候选；单一固定实例下不为多样性本身付出成本 |
| 提速与质量怎样共同探索 | AI Telco Engineer 保留指标/复杂度前沿和其他家族的忠实实现，并将实际代码带回下一轮 | 依据真实目标与约束保留有价值的取舍；复杂度代理需要先确认与当前成本的关系 |
| 一次失败是否否定了整条路线 | AI Telco Engineer 将“核心机制是否实现”与分数分开评价 | 按执行代码里的机制归类；不完整移植不能证明原策略无效 |
| 日志怎样变成经验 | HeurAgenix 比较好坏方案的操作和轨迹；RefineEvo 记录相对父代成败并按后续复用效果更新经验 | 保存带适用条件和反例风险的规则，并实际影响下一项提案 |
| 评估很贵时怎样筛选 | Predict-Before-Execute 用成对预测减少执行，并为低置信比较保留未决候选 | 预测是预算筛选信号；真实评估负责分数，保留探索并对照真实结果校准 |
| 高分方案应学哪一版 | NVIDIA Kaggle skill 沿排名、writeup 和 notebook 谱系恢复历史版本 | 学取得结果时的完整系统及其依赖，不默认最新代码就是获胜代码 |

固定版本、源码路径与行号见 [source-patterns.md](../skills/competition-optimize/references/source-patterns.md)。这些实现提供思路，不能证明照搬后在另一场比赛提分。

## 对华为固定时隙问题的启发

应从题目的最终配额、稳定性参考状态和得分时间尺度推导布局，再对比旧代码能表达什么。最终配额提示先构造理想布局再投影到可行位置；稳定性参考状态提示将保留旧位置的价值放入构造；跨更新累计质量提示比较改善能存续多久；局部依赖提示只修复受影响的间隔和状态。

下一事件预测、布局收益寿命估计、对多种后续情形做稳健决策是三种不同能力。Agent 对候选代码的成对排序，解决的是搜索预算分配；它不能替代本题对未来增删的建模。更长视野的收益定价也不自动等于更准确的事件预测。

双色“数量差为 1”是一个有用情形，不能当成其他计数不存在最优结构的依据。一般化策略需要明确其可表达状态与成立条件。局部 incumbent 已有的 DP、lookahead 或几何索引也要如实记录，比较覆盖范围和组件如何配合。

完整的推导方法见 [strategy-design.md](../skills/competition-optimize/references/strategy-design.md)。这部分加强策略形成过程，保留实现请求所需的执行与评估闭环。

## 源码阅读中需要保留的边界

- MARS 快照主要发布生成代码与执行轨迹，能追踪一次方案如何演化；不能据此声称完整预算 MCTS 控制器已开源或已审计。
- Predict-Before-Execute 的成对缓存按无序代码对建 key，却保存依赖输入顺序的 winner index；类级缓存还缺少任务上下文。这是静态代码路径问题，本次未执行复现，不能直接复制该缓存。
- I-MCTS 的部分路径把 test_score 用于选择；迁移时必须使用当前任务允许的开发反馈。
- BehaveSim 的行为相似度函数保留了“占位、返回 0”的旧注释，实际函数体已经计算轨迹相似度。实现中的 DTW 累积值未按路径长度归一，实例 `zip` 不齐还会忽略尾部；迁移前应核查尺度与输入对齐。判断实现要沿调用链读函数体，不能照抄注释。
- 树搜索、多 Agent、模型自报置信度或较大框架规模，都不构成质量证据。复制前需要确认主链实际调用、目标方向、预算与数据边界。

## 长期驱动器中的实际迁移

进一步深读 MLEvolve、ShinkaEvolve、AgentDiscover、ReEvo 和 RefineEvo 的控制链后，将三个机制接入了 [autonomous_campaign.py](../skills/competition-optimize/scripts/autonomous_campaign.py)，信号和证据检索集中在 [campaign_search.py](../skills/competition-optimize/scripts/campaign_search.py)。

| 原有缺口 | 本轮实现 | 源码启发 |
| --- | --- | --- |
| 每轮改了新代码就被当成进展，连续退步仍沿用旧路线 | 顺序重放同口径历史最好成绩；默认 4 个有效新实现无新高时切新上下文重审。再次触发需要新窗口；切换路线名和口径不能消除原口径记录 | MLEvolve 改变停滞分支动作；ShinkaEvolve 记录最后真实进步并触发开岛 |
| 已有 brief，却需要模型自己记得调用 | 每轮启动前自动生成、持久化并注入最多 48 KiB 的开发证据包，带 best、失败、未解决分支、父子实测差值和源码/result 身份 | AgentDiscover 在 session.open 确定性装配 brief；ReEvo 将反馈归并后直接输入 mutation |
| 一直提分时也会永久续用一个 session | 默认每 8 个成功检查点切新上下文，保留 next_action、档案、消耗与额度；可配置或关闭周期轮换 | 从 fresh session 必须带外部记忆推得的上下文维护策略，不是作者实验最优参数 |

排名只用带实际 adapter 分数和代码/recipe 快照的开发实现。确认数据、重复实现的幸运高分、仅改变输出或手工声明的分数不制造历史收益。证据包仍可展示未执行或失败候选作为上下文，但不能将其选为实测 best。不同完整 comparison 分开记账，反馈解释保留适用范围，不成为自动晋升或因果定论。

没有照搬 MLEvolve 的全局停滞公式：它把近期节点与已经更新的 global best 比，可能把近期真实进步误判成停滞。也没有照搬 RefineEvo 的“语义相似即可适用”或按一次候选成败删除全部检索经验。源码位置、固定 commit 与迁移边界见 [source-patterns.md](../skills/competition-optimize/references/source-patterns.md#sustain-a-search-across-contexts)，使用和恢复协议见[长期运行说明](../skills/competition-optimize/references/unattended-campaign.md)。

本轮实现不增加第三方运行时、向量库或额外总结模型。它落实了“成绩停滞会改变下一轮工作方式”和“新上下文收到已有证据”，尚未证明真实比赛分数提高或 token 减少；4 与 8 是可调的工程初始值。

自动检索同时去掉了未展示候选的复测历史复制。独立对照的三档完整 JSON 相同；8,000 条同实现记录时，函数调用中位数 0.362→0.160 秒，增量分配峰值 245.24→0.54 MiB。该局部测量不包含档案读取和已有输入历史，不代表完整 campaign 提速，范围见[验证记录](unattended-campaign-validation.md#长期检索中的复测历史复制)。

## 未完成提案接回真实执行

这轮沿“提案 → 具体代码 → 真实执行 → 反馈”的路径查恢复。RD-Agent 的 data-science loop 将同一个实验对象和 pending tasks 传给 coding，再将 coded 实验传给 running；workflow 保存阶段输出和下一步索引，恢复时取回原阶段。这支持的是保留可执行工作及其所处阶段，不能从 snapshot 存在推断程序正确或有可用分数。[固定源码与迁移边界](../skills/competition-optimize/references/source-patterns.md#resume-the-proposed-work-at-the-recorded-step)列出具体入口，本轮未运行第三方 Agent。

本仓公开 API 的最小反例有两种：同口径七项 pending 提案中，brief 永久只展开最新四项，自动包还把全部 IDs 改成这四项，重读磁盘也无法让最早一项出现；失败父代缺少分数合同、引用旧有效开发反馈的合法 repair 提案，又因全部引用必须同口径而不能进入任何上下文。原提案均可接受合法后继，说明问题是检索遗漏，不能称作档案丢失。

实现继续使用原 JSONL 提案和结果链。提案按首个 parent 的完整 comparison 归属，其他开发引用可以跨合同，独立输出核验身份、代码/result 指针和需重验标记，不把其分数、原反馈或组件加入当前排名。修复后的后继允许形成完整的新评分合同；确认引用仍被拒绝。驱动单独持久化 pending 的成功曝光轮次，轮转未曝光、最早曝光的详情；保留当前口径的 ID 与总数，受 48 KiB 上限裁剪时明确记遗漏。独立 `brief` 保持最新详情的既有行为，按 ID 的 `trace` 可直接恢复完整原目标与结局。曝光不等于执行或关闭，agent 仍需运行有价值的后继，或记录具体停止原因。

同时复现了 fresh repair 在 `thread.started` 后遇到 429 的问题：prepare 提前提交 execution review 检查点，失败后的下一轮因信号已消耗而 resume 失败会话。现把 execution/strategy review 均存为本轮持久意图，成功 terminal、退出码与 receipt 接受后才提交；失败调用仍应重新触发到期的 fresh review。旧状态缺新增字段时从空曝光表恢复，旧 in-flight 原样完成，旧档案不改写。选中提案的原代码身份遭改动仍明确失败，不按年龄静默绕过。

这次迁移没有增加流程数据库、额外总结模型或强制试验配额，也不自动发现尚未归档的训练产物。控制流程验证、真实执行链和剩余边界见[验证记录](unattended-campaign-validation.md)。

## 旧分支与高分参考分开检索

继续核对 ShinkaEvolve 与 MCTS-AHD 的父代选择和上下文装配，发现本仓的检索偏向：备选路线先按历史最好分截为前三条，每条又只展示一个最新未决机会。低分但核心机制尚未展开的旧路线，以及同路线较早的另一个机会，可以长期不进下一轮。另一个错误是任意改过实现的子代都能让父代机会消失，即使子代执行失败或没有可用分数。

ShinkaEvolve 将父代选择与高分参考检索分开，并在父代权重中记录已有子代；MCTS-AHD 从祖先路径和多个根继续产生后继。这次迁移的是“高分参考与可继续评审的根分别检索、保留实际后继证据”，没有移植随机权重、UCT、岛数、固定扩宽预算或按分数判重。[固定版本与源码位置](../skills/competition-optimize/references/source-patterns.md#retrieve-open-branches-separately-from-score-leaders)支持该区别，未复现作者的比赛成绩。

新增 `review_frontier` 从全部同完整 comparison 的开发实现检索有明确反馈的 promising/unresolved 机会，默认最多展示两项。它按未曝光、最早曝光轮转，与高分列表独立；同时保留首次真实有效分数代表、首次机会声明、不同已执行/已测子代数量及最新后继卡。相同实现的换名和幸运复测不增加机会；后续测量首次提出反馈时，用单独的 `feedback_candidate_id` 指向声明，代表分数仍来自首次有效观测。

只有机会首次声明之后、实际测到可用目标且不再显式 unresolved 的不同子代实现，才能推进旧机会。失败、缺分数或仍未决的子代保留父代机会；声明之前的旧子代不能关闭后来提出的问题，重复声明也不能让已经推进的机会复活。这是档案中的后继进展判断，不等于判定反馈成立或整条方法已无价值。

长期驱动按 comparison 和实现指纹持久化最近成功曝光轮次。prepare 和崩溃接管保留原包，不提前消耗；只有成功 terminal、退出码和合法 receipt 才提交。机会、反馈及最新后继的核验身份必须留在最终有界交接包里。曝光仅说明证据成功交接，不能证明模型已经理解；它也不强制选父代、不授予固定试验次数。独立前向证据与边界见[验证记录](unattended-campaign-validation.md)。

## 执行失败分流与长期档案

继续检查两个会妨碍长期运行的问题：连续失败的新代码是否仍被当成进展；重复测量是否使持久化历史按平方增长。前者沿本仓驱动、归档和 adapter 的真实失败路径，以及 AIDE、MLExpert 的选择→执行→反馈链核对；后者检查 writer、reader 和所有 reuse 字段消费者，再用真实 record API 作隔离复算。源码与固定 commit 见 [失败恢复模式](../skills/competition-optimize/references/source-patterns.md#recover-execution-before-judging-the-method)。

原驱动的“新实现”计数包括失败执行，而收益信号只接受有效可比分数，因此不断换代码并失败能同时避开两种重审。编译/环境错误还可能发生在 score 和 evaluator identity 生成之前，不能按完整 comparison 给这些失败分桶。现新增独立的 execution_health：首次失败、无效、部分完成或成功却缺少可用目标时，下一轮转 repair，直接收到已核对 hash 的真实 error/phase、日志位置、源码身份和可参考的开发父代。默认连续 3 次没有可用观测切新上下文重新诊断，后续重审需要新尝试；参数可在 start/resume 修改，均不构成停机上限。

AIDE 启发的是按执行状态选择 debug/improve，并把真实输出交给修复；MLExpert 启发的是先辨认错误责任。这里没有复制固定 debug 深度、随机概率、清空目录或修改评分器。无分数不代表算法失败，不填虚构低分；低分但有效的观测会结束执行失败串，再由独立收益信号判断是否需要换策略。跨口径父代明示需复验；确认数据不参与诊断和父代选择。嵌套环境元数据过大时，交接包压为诊断与身份指针，仍遵守 48 KiB 上限，原结果不改。

同时修复了上一轮性能测量没有覆盖的**磁盘增长**：旧 writer 在第 N 次复测写入此前全部重复 ID，两份数组合计可达 N(N−1) 项。新事件只写 first/previous/count 链接，旧字节和候选身份不变，展示时从真实历史还原完整列表。512 条相同 artifacts 记录的隔离对照为 3,947,012→1,145,616 字节；同 pipeline、不同输出为 2,631,938→1,262,472 字节。两版 brief 除档案路径外一致。这里只证明这类档案的存储增长改善；单次 record 仍扫描历史，CLI 返回完整列表，不能据此声称总运行时间已变为线性。完整证据与行为验证见[验证记录](unattended-campaign-validation.md)。

## 评测口径缺少共同对照

继续检查“有代码、有分数、却没有可比较收益”的长跑路径，发现每次换 `config_hash` 时，所有结果都只是各自口径下的基线。旧的实现计数一直前进，执行健康正常，每个口径又不足以判断收益停滞。只统计连续漂移也不充分：在漂移 full 中穿插稳定 smoke，会不断重置全局计数。修复前的公开 archive API 反例及实际程序保留在[本轮证据目录](/home/lzh/competition-agent-validation/comparison-continuity-20261022/)。

这次借鉴 RD-Agent 固定 commit `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` 的共同重测路径：[ValidationSelector](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/proposal/exp_gen/select/submit.py#L298-L342) 先准备共同输入和评分脚本，把同一份交给所有候选；[process_experiment](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/proposal/exp_gen/select/submit.py#L560-L611) 实际运行候选与共同评分器，再从这轮结果比较。其 [development runner](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/dev/runner/eval.py#L152-L155) 检查 metric 名，解析失败时保持缺分数。迁移只使用“补共同评估再比较”的动作；本项目沿用合法固定 development adapter，完整 comparison 仍须一致。原仓会生成/替换评分脚本、部分 gate 引用历史或 medal 的行为不进入控制链。此前 feedback 的 LLM 对齐判断也不能当作严格合同恢复的证明。

新增 `comparison_continuity` 顺序重放有效 `(完整 comparison, implementation)` 的首次观测，保留至今仍只有一个不同实现的口径。自上次成功测量重审后，新增的这类口径默认达到四个便进入 fresh `measure`；稳定 smoke 不清零，正常 smoke/full 各自补齐对照后会消除相应缺口。相同实现的幸运复测、改名、确认、失败、手工分数与缺快照产物不制造比较对象。旧代码在新口径下真实补测，则能成为另一实现的共同参考。

`comparison_recovery` 交接真正的孤立 target、不同实现的开发祖先或更早参考、顶层合同差异和最近四项身份指针。跨口径卡只提供核验后的身份和路径，不提供分数与原反馈。Agent 检查哪些变化符合任务，选现有合法共同开发合同补测，再在完整相同的合同内判断收益。窗口只请求补证，合法 fidelity 探索仍可继续；该信号也不证明当前合同已稳定、噪声已解决或所有历史缺口均已补齐。

重审延续成功交接后才提交的协议，保存 prepare 时封存的观测数；本轮运行新产生的口径留待下一次判断。失败或 429 不消费诊断，执行 repair 优先。对必要指针额外计算 `retrieval_sha256` 并在裁剪后重算：独立审查复现了巨量环境元数据耗尽 64 项省略索引后，长 ID/路径虽被截断却误记交接的问题，摘要校验覆盖了这条路径。完整指针的 compact 卡仍可交接，包继续限制为 48 KiB。
