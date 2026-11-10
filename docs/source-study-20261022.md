# 自动比赛 Agent 源码研究：让搜索产生不同的解法

> 历史证据可访问性（2026-11-10）：本文引用的 `/home/lzh/competition-agent-validation/` 原始路径在当前环境不可访问。以下数字保留为历史记录，不视为本轮重新验证；原始链接不重写。当前验证见 [本轮实施记录](refactor-implementation-2026-11-10.md)。

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

## 诊断试验指导构造而不参与候选排名

MLE-STAR 提供了一个具体区别：消融执行结果先被总结，再用于选择待改代码块和下一计划；下一版本的保留则依据实际 improvement 执行结果。其 outer update 分别保存候选和消融历史。[固定 commit 与实际调用链](../skills/competition-optimize/references/source-patterns.md#use-diagnostic-interventions-to-choose-the-next-construction)支持这种职责分开，不能据此声称来源采用了本仓的 role schema 或证明自动提分。

本仓此前只有 development/confirmation 两种角色。五次真实基线/特征消融执行得到 1.0、四次 0.875，虽然反馈明确说明消融用途，四项仍被计为未提分的新候选并触发策略重审。重审本身不会停止或拒绝工作；复现的是缺少诊断语义对收益信号的干扰。本轮也检查了旧结果别名、空工作和合法复测：原驱动已有无实现时的重审，不能把“没有新源码”一律拒绝，否则会误伤有理由的真实重测。LoongFlow 的内层修复和 LLaMEA 的 parent/operator 解耦作为比较材料保留，没有额外引入另一套选择器。

新增显式 `role=diagnostic`，首个 parent 必须是普通开发控制版本，保留执行源码/result、成本和反馈。`diagnostic_evidence` 单独检索最近两项及其控制卡；同合同可读实测目标，跨合同仅提供核验身份和重验指针。完成的前瞻诊断也进入 `trial_history`，带 outcome/evidence role，诊断双方不产生候选 gain。下一提案可引用这些诊断的代码和反馈，归属仍取首 parent 自身完整 comparison。

诊断不进入最好候选、路线排名、候选停滞、comparison 单例或普通 frontier 关闭判断；执行健康仍包含诊断，低分有效消融是观测，失败或缺分数仍进入 repair。实际提分尝试及退步保持普通 development，不能按分数自动重标。诊断转为可交付候选时需完整任务有效性和同口径证据，再显式记 development；已有有效测量可说明复用理由，避免无用重跑。仅新增诊断时不自动调用 completion verifier，显式 complete receipt 保留原规则。

既有 schema/默认角色不改，旧档案不重写；没有新增总轮次、时间、候选或成本上限、数据库或模型依赖。诊断窗口只是检索大小，不是实验额度，也不强制每轮消融。实际使用结果与边界见[验证记录](unattended-campaign-validation.md)。

## 已完成试验影响下一次构造

继续沿 RefineEvo、OpenEvolve 和 HeurAgenix 的实际生成调用链阅读，发现本仓已有“提案 → 执行 → 反馈”档案，却在完成后断开自动召回。公开 API 的真实小程序反例中，提案离开 pending 后，下一轮只见 outcome 的 `proposal_id`、`contradicted` 等反馈，不见原来的 `change` 和 `expected_observation`；继续执行后，旧试验连同反馈离开近期窗口，最好父代仍在。精确 `trace --proposal-id` 可以恢复完整链，因此这是自动交接缺口，不能称作档案丢失，也没有据此证明真实模型必然重复失败。

RefineEvo 在评估后保存父子实现、目标和差值，在下一次选定父代后按 operator goal 检索经验，最后把 success/fail experience 送进实际生成 prompt。OpenEvolve 将 evaluator artifacts 随子代保存，随后把选中父代的真实 artifacts 和 evolution history 注入生成；其该处 previous programs 来自高分列表，不能将它描述为旧失败召回。HeurAgenix 则从具体正负轨迹找瓶颈，再重建对应状态修改规则。共同可借鉴之处是把“尝试的机制及其实测结果”送回下一次构造。[固定版本、源码入口和迁移边界](../skills/competition-optimize/references/source-patterns.md#recall-the-tested-hypothesis-with-its-outcome)保留了证据；未执行第三方 Agent 或复现作者成绩。

新增 [campaign_trials.py](../skills/competition-optimize/scripts/campaign_trials.py)，直接从原 JSONL 的完成提案及实际后继派生 `trial_history`。每项保留原 basis、change、expected observation、验证与停止条件，以及 outcome 的预测状态、适用反馈和必要源码/result 身份。一个槽优先取与当前/最好实现相关的最新试验，其余槽按未曝光、最早成功曝光轮转，总计最多两项。检索规模不决定试验数量，也不强制选择父代。这样 agent 能检查原代码，辨认未实现的能力、实际失败和测量故障，再改变下一次表示或构造。

归属继续沿用首个父代的完整 comparison；跨合同后继及引用只带核验身份、路径和需重验标记，结构化分数、原 outcome 反馈和预测状态不进入当前证据。只有当前合同内的真实有效父子观测才给方向正确的 gain。预测与解释仍是 agent 自报，执行失败不否定算法，有新前提或实现时允许重新尝试同一机制。Pending、stopped、确认集、手工分数和仅输出文件不会制造已测试机制，也不会补造旧档案没有的预期。

曝光仍在成功 terminal、退出码零且 receipt 接受后才提交。prepare、封存包重建、429 和坏收据不消耗历史；裁剪后必要身份与指针须通过原检索摘要核对。极大试验卡可明确省略，完整记录可按 ID 回取，交接包继续限制 48 KiB。旧 schema-v2 state 和 in-flight 保持兼容，无新数据库、总结模型、黑名单或默认资源上限。实际前向结果和模型质量边界见[验证记录](unattended-campaign-validation.md)。

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

## 逐 case 胜例进入下一次构造

总分较低的实现仍可能在部分 case 胜过当前最好版本。继续核对 EoH-S 与 Telco，确认前者的逐实例向量确实进入存活和父代选择，再由 e1 生成新代码；但 L1 距离只是差异代理，原 prompt 也没有具体胜例。后者把前沿外其他家族的忠实实现代码带回下一轮，采样仍依赖标量成绩。这次借鉴专长证据和次优代码的召回通道，没有复制 L1 或把逐 case 最大值包络当收益。[固定源码与迁移边界](../skills/competition-optimize/references/source-patterns.md#retrieve-measured-case-strengths-for-the-next-implementation)列出了实际入口。

ReEvo 的真实双亲反思、crossover、评测链使用总体 scalar obj 区分 better/worse，没有按交叉胜例选亲。KAPSO 会将多个提案合成为方案并交给实施者，但这些提案尚未分别实测，实施仍从单一父分支开始。因此，多亲生成和 synthesis 接口本身不能证明候选互补或后继提分。本轮只读正文、locator、文件 hash 和 E/I 边界见 [complementarity.json](/home/lzh/competition-agent-validation/complementarity-study-20261023/source-study/complementarity.json) 与 [combination.json](/home/lzh/competition-agent-validation/complementarity-study-20261023/source-study/combination.json)。

本仓新增 [candidate_profiles.py](../skills/competition-optimize/scripts/candidate_profiles.py)，从可选 `case_profile` 派生 `brief.complementary_evidence`。只检索同一完整 comparison 下、实际执行且有有效分数和源码/recipe 快照的普通 development；profile 的 metric、direction、case IDs 必须匹配，每个实现保留首次有效 profile。最多两个检索槽按相对当前最好实现的新增胜例、总胜例、实测标量分和档案顺序选择，附 wins/losses 实例及核验后的源码/result 指针。重复测量不凭幸运 profile 扩大专长，窗口大小也不限制实际试验次数。

这些证据用于检查局部优势来自哪个机制，再构造并真实评测后继；原 scalar 排名和实际 best 不变，也不计算虚构组合分数。不能根据隐藏标签、验证集 ID 或已知 case 胜者表冒充运行时选择器。是否提高真实比赛总分仍需实际比较，本轮来源链不提供收益保证。

## 区分方案未实现与机制实测失败

继续沿 Telco 的真实执行链核对，重点从“保留哪些候选”转向“到底试过哪个机制”。其评测工具运行 draft，保留成功且更好的 solution，结束时保存实际评测结果；结果处理再将 solution.py 与 assigned idea 对照，总结 yes/partial/no，随 Candidate 写回 leaderboard。下一代生成同时收到原 idea、这个 verdict、实测指标和代码，明确把核心机制缺失或被替换的原方案视为尚未试验，并按代码实际家族判断多样性。新构造不带无关参考代码，以减少实现时重新退回旧补丁的倾向。[固定入口与迁移边界](../skills/competition-optimize/references/source-patterns.md#review-the-mechanism-that-reached-the-executed-code)保留了调用链。

本地文档此前已要求按执行代码分类，但实际后继记录只有 changed snapshot、执行结果、feedback 和 prediction_status；预期观察被支持或否定，不能回答原机制是否真正进入代码。本次将这个区别接入既有提案与结果链：可选 `record --implementation-review <JSON>`，与 `--proposal-id` 一起用于已执行的 development/diagnostic 后继。输入包含 fidelity（yes/partial/no/unknown）、actual_mechanism、missing_components 和 code_evidence；源码证据指向本候选 source 或 recipe 内的文件，在 detail 中描述具体代码观察，可引用函数或行号，partial/no 必须指出缺少什么。预测文件本身不能作为实现源码。

归档核对文件是否属于候选源码/recipe 根并补上文件 hash，将其绑定到原 proposal、implementation fingerprint 与 input hash，标为 `assessment_kind=agent_report`。工具不核验 detail 中的语义或非结构化行号。同完整 comparison 的 brief 与 trial_history 会将复核带给下一次构造，跨合同 trial 继续只给身份和重验指针，不带原 verdict/解释；精确 trace 可恢复原 review。没有旧字段仍代表 unknown，保留旧档案字节，不强制每轮填写，也不增加 provider 或默认额度。

Agent 据此检查耦合组件是否齐全，再选择补齐、修复、换构造或沿实际新机制继续。偏离原计划的实现仍可凭真实成绩成为最好候选；其分数不能否定缺失的原机制。yes 和文件身份核对也不是语义审计证明，不改变 valid、score、best、route、frontier 或停止条件。MLEvolve 的分支停滞→轨迹分析→Tier 2/3→审查→执行作为比较材料保留，但其 reviewer 只有 task/code 输入；本地已有轨迹召回与 rethink，本轮不再叠加类似 prompt 或照搬固定阈值。

两份来源均为只读固定 commit 源码：Telco `be94f40f4bdd255b3e4dfa8bf32798821813311b`，MLEvolve `f4a37b96c948bfed6564e62f3229e0b38e908d33`。[37 份最小摘录、文件 hash 和 E/I 边界](/home/lzh/competition-agent-validation/next-mechanism-20261023/source-study/generation.json)可复核；未执行第三方 Agent，源码链本身不证明比赛提分。

## 比较控制不等于源码继承

继续核对 LLM4AD Next 与 Comind，找到与本地“独立构造”原则直接对应的实际入口。LLM4AD Next 固定 `c23a45c64a4b1fed322bfefbfe8436eeea32c954` 的 I1 路径向 planner 传空 parents，随后用空 base_context 实现并批量评测；Comind 固定 `f93dff779b5d40dd3bf28b7b6ba5e39881e02e38` 允许 codebase=None，只在实际选定旧 codebase 时注入完整代码并复制工作区。Telco 的 fresh-start 省略 reference_workspaces 提供第三条相符链。它们共同支持可选地不继承旧源码，而不是只改变量名或沿最好代码局部打补丁。[固定代码入口](../skills/competition-optimize/references/source-patterns.md#separate-comparison-controls-from-inherited-code)和[18 处最小摘录、8 个文件 hash](/home/lzh/competition-agent-validation/fresh-construction-20261023/source-study/source-study.json)保留来源。

本地此前已允许从零推导、独立原型，但 API 强制非空父代码目标。它并未检查代码相似性，因此不能说框架禁止新算法；真实缺口是独立重写需要把不继承的父文件伪填为“修改目标”。这次增加可选 construction_mode=independent，要求 code_targets=[]，保留验证过的 parent_ids 作为比较控制和 feedback_from 作为证据。缺省仍是原 refinement，继承或组合父组件仍填写真实文件目标。

模式从 proposal 复制到真实 successor，并保留在 pending/brief/trace/trial_history；有界交接要求模式与 not_applicable 标志一致。真实源码/完整 recipe 快照与新执行结果仍不可缺，只有预测输出或声称源码 hash 的后继会被拒绝。独立结果不误关闭比较控制的 refinement 机会，但自己仍可成为新机会。实际分数与完整 comparison 决定比较，不靠模式声明晋升。

该字段是 Agent 对源码复用意图的声明；driver 仍展示开发历史，来源系统也保留任务、接口或 coordinator 上下文，因此不是信息隔离、创新性证明或提分保证。未增加默认 fresh-start 频率、额外 provider 或轮次上限，未执行第三方 Agent。

## 长期档案单次回放复用索引

这次从 FunSearch 和 OpenEvolve 借鉴实际“注册时维护索引、后续查询复用”的路径。FunSearch 对评估后的程序增量更新 signature→Cluster，下一次 sampler 从已有簇取 prompt；OpenEvolve 注册实测 child 后按 ID 查父版，load 时一次建 program map。它们没有实现本地的严格 JSONL 校验或结果摘要去重，不能把这些语义或提速归给来源。[固定 commit、5 个文件 hash 与 18 段摘录](/home/lzh/competition-agent-validation/archive-replay-20261023/source-study/source-study.json)保留真实调用链与迁移边界。

本地 read_records 已顺序维护 candidates，却在每条 proposal 和 successor 验证里重新扫描前缀建相同映射；后继又遍历全部历史结果找重复摘要。现在复用这次读取中已接受的 candidate 映射，并增量维护此前字符串 result digest 集合。只有通过原验证的事件才进入索引；每次读取重新从磁盘解析，没有跨读取缓存、额外数据库或旧档案改写。独立 validator 调用及非字符串旧 digest 保留原路径；角色、比较、源码、结果、错误顺序和确认隔离规则没有变化。

在 2,048 组提案/后继的剖析中，candidate_index 重建次数从 4,096 降到 0。固定宽度元数据规模样本从 512 到 8,192 组，读取时间观察到约 2.1× 至 17.2× 改善；8,192 组的三次中位数为 12.993→0.756 秒。它们是从真实 API 事件复制并重新赋予身份的规模 fixture，不能充当新增算法执行或比赛成绩。真实旧档案的 records、brief、trace 和 handoff 另作逐字段等价核对。[性能和行为验证](unattended-campaign-validation.md#档案回放提速2026-10-23)给出完整范围：record 写入、brief 其他检索与评分计算仍可能扫描历史，没有整体线性或端到端 17 倍的承诺。


## 条件经验的修订与实际消费

ReEvo 的固定代码将已执行 better/worse 源码的短期比较与旧长期反思合并，写出新反思，再把它注入下一次 mutation 并评测生成代码。ShinkaEvolve 在评测 outcome 后更新 recommendations，下一次取出并传到非 crossover 的生成 prompt，再将接受的程序交给评测。这里借鉴的是“更新后真正影响下一构造”的链，不是再添一段反思指令。[源码入口与迁移范围](../skills/competition-optimize/references/source-patterns.md#revise-conditional-learning-and-feed-it-into-construction)及[固定版本、23 处摘录、8 个文件 hash](/home/lzh/competition-agent-validation/scoped-learning-20261023/source-study/source-study.json)可逐步核对。ReEvo 的失败运行被该选择链排除；写文件也不能证明恢复读取。Shinka 的 save/load 方法不构成已验证的 runner 恢复链，本地没有复制其三阶段模型总结或默认次数。

本地已有 trial_history 每轮最多召回两个原始尝试，缺少结论跨窗口的显式修订与使用关系。新增可选 [scoped_learning.py](../skills/competition-optimize/scripts/scoped_learning.py)：在真实 proposal-linked、有效有分数的 development/diagnostic 后继上 record --learning，保存 lesson、conditions、next_action、limitations、evidence_from。完整 comparison 内相同 key 的更新必须显式 revises 当前 head，并保留旧 head 作为证据；当前后继自动加入，新事件追加，旧字节不改。确认、失败、手工分、缺完整 recipe 的输出记录不能成为这条学习证据。

brief.scoped_learning 返回当前结论与核对过的源码/result 指针，优先相关实现，再按最近修订，最多两项并显示省略量。新提案通过 learning_from 表明哪条结论改变了构造或反例设计，basis 解释如何使用；引用不必同时当作父版。pending、实际 successor、trace、trial handoff 都保留连接，精确 trace 返回原报告。归档身份与字节检查不认证自然语言语义或因果关系，仍须检查实际代码和结果。没有新 provider、数据库、强制复盘轮次、路线黑名单或停机规则。

隔离前向使用已闭环：修订报告离开原始 trial_history 窗口后仍可由 fresh brief 取回；独立 Agent 检查原始代码和反例后，用 learning_from 连接兼容前缀动态规划，固定 adapter 总收益从原最好 896 到 938，结果再修订旧报告。它只证明这次经验→构造→执行链真实发生，不是记忆机制的因果消融、长时运行或官方分数证明。[前向使用证据](unattended-campaign-validation.md#条件经验跨窗口影响实际构造2026-10-23)保留实际命令、程序与完整性边界。

## 单次交接中的证据读取复用（2026-10-23）

本轮深读 Aira Dojo 与 LLM Speedrunner 的固定源码，借鉴“构造时读取一次、由真实消费者显式复用”。Aira 的任务文本经 task_info 传到 MCTS，再进入 draft/improve；Speedrunner 的 Workspace 解析结果索引被 Ideator 和 top-k 选择实际消费，写入后刷新对应项。[固定 commit、14 份源码指纹和31段调用证据](/home/lzh/competition-agent-validation/evidence-read-reuse-20261023/source-study.md)保留原始范围。

本地实现只在一次 brief、trace 或 handoff 中共享 EvidenceReads，减少源码、共享 recipe 和 result 的重复哈希；不保留原始 bytes，不跨请求保留摘要，目录仍重新枚举。每次使用核对完整 stat 身份；针对实测同尺寸连续写入可共享 mtime/ctime 的问题，mtime 或 ctime 距操作开始不足一秒的文件始终重读，无生产等待。内容解析仍从当前读取的 bytes 产生。新操作重新读文件是本地证据合同，两仓没有直接提供这个完整保证。

没有迁移 Speedrunner summary 原地删除共享 metrics.private 的行为，也没有迁移 Aira 无内容 key 的 UI 缓存和 solver preview 寿命。实例范围不等于单操作范围，不能证明外部改字节后新鲜，也不能证明跨文件原子快照。来源仅作静态研究，未执行第三方代码。[使用说明](../skills/competition-optimize/references/iteration-trace.md#retrieve-evidence-for-the-next-implementation)和[本地实测](/home/lzh/competition-agent-validation/evidence-read-reuse-20261023/REPORT.md)分别说明实现合同与效果边界。

## 质量与实测资源的取舍进入下一次构造（2026-10-23）

AI Telco Engineer 的 pilotless evaluator 预热后实际计时 receiver 调用，并分别保留质量与延迟；leaderboard 把非支配源码版本送给后续 idea generator，LLM prompt 实际渲染指标和代码。LLaMEA 的通用多目标 population 也被后续父代选择消费，但 Fitness 来自任意 callback，不能据此声称运行成本已测。CodeEvolve 的单 fitness 与 MAP-Elites 特征格不构成质量/实测成本前沿。[三仓固定 commit、调用链、14 个文件 hash 和迁移边界](/home/lzh/competition-agent-validation/quality-cost-frontier-20261023/source-study.md)记录了这一区别。

本仓因此新增由 adapter 显式声明的 result.resource_profile，包含被测资源、单位、候选范围、测量协议 hash 和有限非负值；绝不把评测总 elapsed_seconds 或任意 --cost 解读为候选延迟。只从同完整 comparison、同 profile 协议的实际有效开发实现取质量/资源非支配子集，并把最快与最高质量源码端点送进下一轮交接；scalar best、晋级与停止逻辑不改。quality/resource 来自同一条真实观测；首个有效 profile 只是确定性代表，不是重复测量聚合或稳定性保证。接口、协议和两端检索均是本地推导，非上游原样算法。真实结果和测试见[本轮验证](/home/lzh/competition-agent-validation/quality-cost-frontier-20261023/REPORT.md)。

## 当前经验与历史结论分别保留（2026-10-23）

LoongFlow 实际由 math planner 消费 memory.sample 返回的 parent，Boltzmann 同时保留非elite候选入口；RD-Agent 的 CoSTEER V2 分别查当前失败轨迹、组件成功经验和错误修复，再由 factor coder 的模板真实消费。两仓说明“当前工作之外要保留实际入口”，不证明简单增加数据库或记忆字段有用。[固定源码研究](/home/lzh/competition-agent-validation/learning-rotation-20261023/source-study.md)保存两份commit、14文件hash与真实调用链；未执行第三方代码。

本地反例是 scoped_learning 固定相关/最新两条，让三个以上有效结论中的旧head连续交接都不出现；已有trial轮转也无法覆盖所有合法跨comparison后继。现保留最多一个related当前头，其余槽按从未/最久未成功交付轮转。按完整comparison隔离，按head candidate_id记曝光；修订自然重新未见，旧修订不回流。只有成功检查点、完整报告及源结果身份通过交接seal才提交曝光；准备、429、无效receipt和裁剪不消费，恢复可续用。

两槽分配与确定性成功交接协议属于本地推导，来源没有这个实现或覆盖保证。没有引入上游的随机概率、向量服务、跨任务cache或新停止条件。standalone brief保留原相关/新近顺序，轮转展示不代替检查条件和实际构造。[本轮报告](/home/lzh/competition-agent-validation/learning-rotation-20261023/REPORT.md)区分检索覆盖、真实使用与任务得分。
