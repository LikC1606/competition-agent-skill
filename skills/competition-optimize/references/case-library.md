# 按当前决策查竞赛案例

先明确正在选的下一步，例如修复切分、补候选或修改解码。沿着失败样本、评分规则或计算开销找相似的决策，读原方案的操作、成立条件和对照结果。用当前任务的评分单位、推理时可见的信息和预算检查这些条件。已有预测、小批留出样本或可穷举实例能区分两种解释时，先用它们缩小选择。

在现有研究笔记或提案里写清楚案例让你改变了什么，以及出现哪一种结果就要改走另一条路。用完整目标评测选中的方案，再把结论保留在它实际成立的条件下。分析阶段可以先推导边界或找反例，把待验证的效果留为假设。

## 按瓶颈定位

| 当前卡在哪里 | 先查什么，怎样决定下一步 | 相关案例 |
| --- | --- | --- |
| 验证与最终评测的排序不一致 | 按实际信息时点和独立评分单位重算已有预测。查到评分或标签来路有误时先修评测。规则一致但不同时间或群组排序反转时，查任务分布和配对差异。 | [重放评分分歧](#replay-when-scorers-disagree) · [DCASE 校准边界](#audit-calibration-and-metrics) · [G-Research 前推切分](cases-kaggle.md#g-research-crypto-forecasting) · [KDD 学习表现预测](cases-forecasting-recsys-nlp.md#kddcup-2010-tutor-all) · [BRAINTEASER 改写组](cases-forecasting-recsys-nlp.md#semeval-2024-task9-brainteaser) |
| 同一条输入换了同批样本后，预测会变 | 先查哪些样本按规则共同可见。真实的候选列表要完整保留。怀疑临时分批影响结果时，固定模型和全部计分样本，改变分批并按 ID 重算。 | [匹配预测时可见的集合](#match-the-observed-set) |
| 数据多了，失误类型没变 | 针对反复出错的场景抽查新增样本。场景仍缺时改善采样或生成规则。场景已覆盖但标注有偏差时先改监督，用同样的样本数和预算对照。 | [用规则检验合成标签](#test-the-label-rule-before-generating) · [BirdCLEF 伪标签](#separate-coverage-and-supervision) · [漏标与补标](#choose-supervision-from-observed-labels) · [CommonLit 合成主题](cases-kaggle.md#commonlit-evaluate-student-summaries) · [CHiME-8 模拟房间筛选](cases-perception.md#chime8-2024-dasr-constrained) · [Google QUEST 折内教师](cases-kaggle.md#google-quest-challenge) |
| 表示或解码丢了评分需要区分的结构 | 从评分推导哪些输出差异会扣分。保存的预测含有决策所需信息时，固定预测比较解码。缺少所需信息时，检查输入表示和训练目标。 | [AI4Code 位置解码](strategy-design.md#derive-a-decoder-from-the-scored-loss) · [M4 动态尺度](cases-forecasting-recsys-nlp.md#m4-2018-point) · [SemEval 多父类标签](cases-forecasting-recsys-nlp.md#semeval-2024-task4-meme-persuasion) · [NTIRE 多曝光参考帧](cases-perception.md#ntire-2024-bracket-ire) |
| 中间阶段表现好，完整结果仍常错 | 用同一批失败样本查正确候选是否存在，并重放后续阶段。有正确依据却用错时先查选择或解码。补入参考输入能恢复结果时，再找上游能取得的信号。 | [检索与生成的瓶颈](#diagnose-the-stage-that-loses-credit) · [AI4Code 召回与重排](#allocate-inference-to-recoverable-errors) · [H&M 候选来源](cases-kaggle.md#h-and-m-personalized-fashion-recommendations) · [DataBench 列选择](cases-forecasting-recsys-nlp.md#semeval-2025-task8-databench) · [DCASE 方向修正](cases-perception.md#dcase-2023-seld-av) |
| 多个回归模型在同一批样本上出错，要改分流还是补新成员 | 固定同批预测，算当前融合规则能到达的预测范围以及它与真实值的距离。若范围内的改善空间小，查新成员能否把范围推向真实值。若空间大，再查推理时能用的信号能否选对方向。 | [候选覆盖与重排](cross-competition-cases.md#otto-candidate-coverage-and-ranking) · [固定成员的误差下界](prediction-ensembles.md#check-what-fixed-members-can-recover) |
| 单独换一个阶段看不到收益，或收益随配套设置反转 | 查阶段间传了什么信息，下游能否利用。先复用产物比较原方案和最小完整组合。若还要决定能否省掉其中一步，再补同批同预算的单项对照。 | [比较相互依赖的改动](#compare-coupled-changes) |
| 单模型各有强项，专用模型或融合结果不稳 | 在相同留出组对照最强单路、固定融合和按类型选择。已知类型时专用有效、实际分流时丢分，先查分流信号。按时间或评分层级反转时，查推理时能观察到什么。 | [按预测窗口比较融合](#compare-blends-by-origin-and-aggregation) · [Benetech 按类型专化](#decide-when-to-specialize) · [ViSAGE 指标冲突](#audit-calibration-and-metrics) · [Elo 极端点概率](cases-kaggle.md#elo-merchant-category-recommendation) · [Recruit 时间窗融合](cases-kaggle.md#recruit-restaurant-visitor-forecasting) · [RecSys 较新窗口堆叠](cases-forecasting-recsys-nlp.md#recsys-2021-twitter-general) |
| 近似上表现好的解过不了硬约束 | 用小实例检查近似条件和合法解如何对应。能证明的必要条件可以减少搜索。若有通过近似条件却非法的例子，增加缺失的约束或比较可验证的修复，再用完整评分器比较。 | [PACE 一致森林强制单点](#derive-a-reduction-from-the-rules) · [PACE 簇编辑下界](cases-optimization.md#pace-2021-cluster-editing-exact) · [Santa 机械臂约束](cases-kaggle.md#santa-2022) · [ROADEF 装载反馈](cases-optimization.md#roadef-2022-2023-truck-loading) |
| 搜索反复保留看起来相同的状态 | 枚举同组候选的后续动作。较优前缀能继续执行较差前缀的所有动作且总代价无劣势时，可用支配规则去重。后续可行性或代价会分叉时，保留能解释分叉的状态或候选。 | [AHC 束搜索中的状态去重](#check-what-state-a-bucket-must-keep) |
| 单步改动到达局部最优 | 用同一评分器比较单步与联合动作。如果联合动作能提分，固定同一初解比较复合邻域与原搜索的得分和耗时。局部反例只证明当前状态存在额外机会。 | [联合收益与可变深度搜索](strategy-design.md#test-joint-gains-at-a-local-optimum) · [PACE 有向反馈顶点集的两种邻域](cases-optimization.md#pace-2022-dfvs-heuristic) |
| 周期方案每轮都执行同一套动作 | 先验证原样复制周期时的评分。若部分动作可以隔轮执行，改变其中一轮，用全周期评分检验新分配，保留覆盖和跨周期约束。 | [AHC027 回访频率](cases-optimization.md#atcoder-ahc027-recurring-cleaning-route) |
| 运输或调度方案同时决定顺序与数量 | 固定一条已验证的顺序来求数量，逐步检查库存或容量。对照同一顺序下的原操作和重算操作，再决定要不要把顺序纳入搜索。 | [AHC034 固定路线重算装卸](cases-optimization.md#atcoder-ahc034-fixed-walk-transport) |
| 逐步构造容易耗尽后续可行空间 | 从少量高质量解归纳决定顺序，检查部分状态是否仍能完成。用同一后续搜索比较新旧初解和总耗时。 | [AHC041 逐层覆盖](cases-optimization.md#atcoder-ahc041-layered-coverage) |
| 算力花在重复计算或不适合的阶段 | 看缓存命中是否满足同一输入和状态条件。若成本主要来自额外修正，用首轮和修正的配对结果检查哪些错误可修复，同成本比较固定分配与条件分配。 | [FactUEP 条件复判](#allocate-inference-to-recoverable-errors) · [Science Exam 题干缓存](cases-kaggle.md#kaggle-llm-science-exam) · [NTIRE 夜景提前缩放](cases-perception.md#ntire-2024-night-render-efficiency) · [MIP 跨实例复用](cases-optimization.md#mip-workshop-2023-reoptimization) |
| 差异接近评测波动，或长期只在相邻改动中试探 | 若两条实质不同的路线只差排序证据，选能改变决定的配对样本。若候选的表示、约束处理或决策规则一直相同，先从原目标推导一条不同的路线。 | [AHC074 配对评测与重启](#resolve-close-comparisons) |

## 检索完整语料

新增语料保留 984 条，其中冠军 290 条、其余前三 382 条、其余前十 312 条。名次取正式总榜或主办方定义赛道的最终成绩。证据只能确认进入前 N 名时，保留 `<=N`。810 条有官方成绩来源，174 条的最终名次由作者报告。按各赛道的提交系统计数。 [前十案例表](cases-top10.tsv)

按领域分布为 Kaggle 136、算法与组合优化 124、视觉与文档 97、音频与声学 373、语言与检索 246、科学计算与 AutoML 8。

比赛名或算法名没找到可用案例时，把问题改写成一个决策和它依赖的评分现象，再跨赛道找相同结构。例如，判断几个回归模型的共享误差该由分流还是新成员处理时，可以借用检索任务“固定候选后能找回多少分”的分析。查 `candidate coverage|候选.*上限` 定位原案例，再用回归的平方误差推导相应的下界。先看已有预测能解决哪部分，只有缺的前提会改变方案时才继续查原文。

从当前 skill 根目录按评分规则、失败表现或中间操作查详细正文。用原文中的指标名和中英文术语缩小范围，打开命中所在的章节。下面的查询用于定位不同预测时点的融合对照。

```sh
rg -in -- 'WRMSSE|forecast origin' \
  references/case-library.md references/cross-competition-cases.md references/cases-*.md
```

查前十表时，先筛出带 `experience` 的主题命中，再限制显示行数。表按名次排列，直接截取靠前的命中容易漏掉已有对照的案例。下例显示案例键、赛道、原评测范围和经验链接。

```sh
rg -i -- '融合|校准' references/cases-top10.tsv |
  awk -F '\t' -v OFS='\t' '$16 != "" && ++shown <= 8 { print $1, $6, $10, $16 }'
```

打开 `experience` 指向的章节，先核对原方案与当前任务的评分单位、可见信息或资源条件，再选能区分当前解释的对照。若已有经验未回答当前问题，可用更具体的术语查看表中其他命中，沿 `method_url` 和 `evidence_locator` 读原文，用 `result_url` 核对成绩与赛道。`evidence_scope` 说明原方案测到了什么，`transfer_test` 提供可在新任务检验的对照建议。也可按同一经验反查支持案例。

```sh
rg -n 'case-library\.md#diagnose-the-stage-that-loses-credit$' references/cases-top10.tsv | cut -f 1,6,8,11
```

语料没有覆盖具体问题时，沿原始比赛资料和近邻任务继续检索。 [竞赛资料检索流程](competition-research.md#search--read--pivot)

102 个详细案例按领域分册。 [Kaggle](cases-kaggle.md) · [视觉、语音与文档识别](cases-perception.md) · [组合优化与求解器](cases-optimization.md) · [预测、推荐与 NLP](cases-forecasting-recsys-nlp.md)

基准对照和失败机制可帮助判断一个方案的适用条件。 [机制专题](cross-competition-cases.md)

## 迁移示例

### Replay When Scorers Disagree

**SemEval 2020 常识解释生成。** BUT-FIT 用判别器从三种生成器的候选中选解释。与提交的 BART 集成相比，重排在全测试集的 BLEU 从 22.39 降到 19.22。作者复用前 100 题的候选人评，均分从 1.62 升到 1.70，按已有评分逐题挑最好的候选可达 1.88。正式人评 1.84 对应 BART 提交。 [参赛论文 §4.3、表 3](https://aclanthology.org/2020.semeval-1.46.pdf)

遇到相似分歧时，先比较同一批留出题的输出，区分指标分歧和题目构成差异。若计分是逐题均分且同题同输出得分相同，只需盲评两种规则选出不同答案的题。把这些题的配对分差求和，再除以全批题数。语料级 BLEU 则直接重算完整语料。用正式任务目标判断是否保留重排。检查候选中是否存在得分更高的解释。已有好解释却经常落选时先改选择器。候选大多只能复述题干时先改生成所用的信息或构造。

### Match the Observed Set

**RecSys 2019 酒店推荐。** 亚军 Layer 6 AI 把酒店的价格和星级在展示列表里的相对名次作为特征。酒店的原始属性相同，其他选项变了，它的相对名次就可能变。用这个经验时保留完整的真实展示列表，并按原来的点击和评分评估。要判断修改展示后的点击，需要能支持这种干预的数据。 [参赛论文，表 1、2](https://www.cs.toronto.edu/~mvolkovs/recsys2019_challenge.pdf) · [对照设计](cross-competition-cases.md#recsys-2019-model-the-observed-choice-set)

临时切分推理批次也能改变相对名次。设规则只调高每批得分最高的样本，整批 `[1, 2, 3, 4]` 只调高 `4`，拆成 `[1, 2]` 和 `[3, 4]` 时还会调高 `2`。若赛题允许用同一个完整集合，就可以统一计算一次名次，再分批应用结果。若部署只收到独立样本，可对照用训练集确定的阈值。在同一批留出样本上重放完整预测路径，检查是处理分批影响结果，还是任务本身改变了可见的选项。 [配对回放步骤](local-evaluation.md#match-the-prediction-context)

### Test the Label Rule Before Generating

**SemEval 2021 词义匹配。** Cambridge 从共享锚句推导新标签。同一个目标词在 A、B 中同义且在 A、C 中同义，可以推出 B、C 同义。A 与 B 同义、与 C 异义，可以推出 B、C 异义。若 A 与两句都异义，B、C 可能共享另一个义项。作者按可推出标签的关系扩展同域训练集，从 8,000 条到 10,798 条。该数字描述了数据规模。 [参赛论文 §3.1、表 4](https://aclanthology.org/2021.semeval-1.96.pdf#page=2)

**HANS 推理对照。** 使用 405 条施受角色对调样本后，词汇高度重合、实际不蕴含的切片准确率从 0.28 到 0.71。其余词汇高度重合、实际蕴含的样本从 0.96 到 0.77。作者在正文还指出，对称动词的角色对调可能造成标签错误。 [Min 等人 §4、表 A.2–A.3](https://aclanthology.org/2020.acl-main.212.pdf#page=10)

先用少量可核验的真实样本测试生成规则。例如在有方向的授权判断里，只换模板时标签应保持，互换授权发出方和接收方时要根据规则重算标签。检查每种模板是否有真实的正负反例。标签可推出且目标组合确实缺失时，先把同源或共享端点的样本放在同一组完成切分，再在训练组内生成缺失组合。在留出的真实样本里同时看修好的错误和被引入的错误。若标签推不出来或模板本身就能预测标签，先修生成规则或采集真实反例。

### Separate Coverage and Supervision

**BirdCLEF 2025。** 作者报告直接拼接伪标注数据效果差，改为对两种来源的音频及标签做 Mixup，再迭代更新教师。公开榜参与了作者的判断，私榜成绩还包含专用模型和融合。迁移时用合规的教师和样本池，比较原监督、拼接与混合，固定伪标注池和总训练步数。按地点或录音来源留出，观察有收益的样本来自新增场景还是原本覆盖的场景，再查训练是否反复强化教师的错误。 [冠军复盘的 Self-training 部分](https://www.kaggle.com/competitions/birdclef-2025/writeups/nikita-babych-1st-place-solution-multi-iterative-n)

### Choose Supervision from Observed Labels

**DCASE 2024 与 NTIRE CDiscover。** DCASE 主办方基线屏蔽各来源未标注类别的损失。保留屏蔽并加入从 MAESTRO 到 DESED 的部分标签映射后，开发测试的 DESED PSDS1 从 0.469 到 0.491，MAESTRO segMPAUC 从 0.722 到 0.731。这组对照测的是标签映射。CDiscover 发现 CARPK 图中可能有多辆车，而训练图只标一辆，于是用 GLIP 补框再迭代训练。CARPK 1-shot 的 mAP 63.26 对应完整提交。 [DCASE 报告 §6.1、§7.2、表 2](https://merl.com/publications/docs/TR2024-146.pdf) · [NTIRE 赛报 §4.2.1、图 6、表 1](https://openaccess.thecvf.com/content/CVPR2026W/NTIRE/papers/Qiu_The_Second_Challenge_on_Cross-Domain_Few-Shot_Object_Detection_at_NTIRE_CVPRW_2026_paper.pdf)

用于跨队列的多标签工单分类时，先查各队列实际标注哪些类别。单个二元交叉熵对 logit 的梯度是 `p-y`。把漏标的真阳性填成 0 会给出正梯度、压低预测概率，屏蔽该位置则不给梯度。按客户留出少量工单并补齐人工标签，在这些工单上重放教师预测，按队列和类别统计补回、误补和剩余漏标。教师补回的覆盖与精度符合当前指标的代价时，在同等预算下比较只屏蔽与屏蔽后补可靠标签。若误补多或能补回的少，先屏蔽未知标签。映射的标签应有相同定义，或是能由细类阳性确定的上位类阳性。

### Decide When to Specialize

**Benetech 图表转表格。** 通用模型接专用训练后，竖向柱状图和折线图有局部收益，横向柱状图的 CV 下降。点图只有合成数据，作者保留通用权重。迁移时先固定分流规则，用同一批真实留出预测对照通用与专用，分别看类型内效果和识别错类型造成的回退损失。小样本、合成与真实的错配和分流误判会导向不同改进。 [冠军复盘 §2-a](https://www.kaggle.com/competitions/benetech-making-graphs-accessible/writeups/yumeneko-1st-place-solution)

### Compare Blends by Origin and Aggregation

**M5 销售预测。** 冠军融合了递归与直接预测，以及三种门店内的数据共享范围。独立复现用相同的六路结构做等权融合。在全层级 WRMSSE 上，私榜窗口融合得 0.518，当窗最佳单路 0.525。公榜窗口融合得 0.634，当窗最佳单路 0.474。复现报告同时给出各聚合层级的结果。两个最佳单路都是事后在该窗确定的。 [M5 冠军方案复现与来源](cross-competition-cases.md#m5-forecasting-across-windows) · [Ma 与 Fildes 表 2](https://doi.org/10.1016/j.ijforecast.2021.09.002)

在有层级的时间序列任务里，先用已有且符合各预测时点的预测逐窗重放。用当前评分器比较原先选定的单路、等权组合和现用方案，保留总体以及各层级的配对差。若一种训练视图在长预测步长或特定层级有稳定互补，可以先比较不同窗口或数据共享范围形成的组合。若排序主要随时间窗变化，先找预测时可见的解释，再用更早窗口决定固定方案或拟合分流，在后续窗口验证。若观察解释不了这些变化，就把当前差异留为不确定性。 [可复用预测与融合操作](prediction-ensembles.md#reuse-predictions-at-the-right-fitting-boundary)

### Diagnose the Stage That Loses Credit

**SemEval 2026 多轮检索与生成。** IIMAS-RAG 在单独检索榜第 4，GigitAI 第 13。完整检索加生成榜的名次分别是第 13 和第 5。两队的检索和生成实现都不同，名次描述的是各赛道的提交系统。 [主办方赛报表 4、6](https://aclanthology.org/2026.semeval-1.447.pdf)

把这个区别迁移到只能从候选中选答案、按选对数量计分的任务。若 20 个留出问题中，12 个有正确候选、9 个选对，固定候选时任何选择器最多选对 12 个。3 个有正确候选却选错，适合查排序或评分。另有 8 个缺正确候选，可以在开发集把一个已知无关的候选替换为参考答案，保持候选数和选择器一致，再用同一评分器重放。替换后经常选对，支持优先查候选生成。替换后依然选错，检查选择规则怎样使用新增候选及其位置。

若赛方固定候选名单，替换用于诊断，可提交的改动限于给定候选。估计净收益时，在包含原先答对样本的留出组上数修好的错误和新增错误。开放式生成可以对照参考证据和原始证据的输出，在同一批样本和同一评分器上计算差值。

### Compare Coupled Changes

**OTTO 推荐。** 冠军在消融中同时从候选池和重排特征去掉同一来源的信息。得分变化覆盖这条完整路径。若想知道新增来源值不值得接入，先查它能补进哪些目标，预测时是否有可识别这些目标的信号，以及重排器是否实际读取该信号。 [冠军复盘与覆盖率推导](cross-competition-cases.md#otto-candidate-coverage-and-ranking)

**AIM 真实 RAW 去噪。** VMCL-ISP 的同骨干开发表中，参数噪声模型 PNNP 和混入暗帧实测噪声的 PMNNP，在不用方差稳定变换（VST）时分别得 42.59 和 42.69 dB。用 VST 时分别得 41.50 和 41.44 dB。正式名次对应完整系统。择定生成器前，先查目标设备、感光度和曝光下的真实残差方差与行相关，并按实际部署的变换比较生成器。 [赛报 §5.3、表 4、图 7](https://openaccess.thecvf.com/content/ICCV2025W/AIM/papers/Li_AIM_2025_Challenge_on_Real-World_RAW_Image_Denoising_ICCVW_2025_paper.pdf)

设工单按正确许可 ID 计分，每条只能保留两个候选。用规范化编号补候选，用相同编号在候选中优先选择，无匹配时按词面分回退。在六条示例的缓存回放里，原方案选对 3 条。只补候选时正确 ID 覆盖从 3 条到 5 条，仍选对 3 条。只改选择器也选对 3 条。两项一起用时找回 2 条，有 1 条原先正确的工单被分给错误的同号候选，最终选对 4 条。

先用配套的两步在同批留出上重放，记录找回的和弄错的工单。若还要决定能否省掉一步，固定候选数、样本和评分器，再补单项对照。新窗口里若错号或编号复用带来的错误抵消了补回数，先查编号何时可靠或保留原选择规则。 [配对比较的计算与适用范围](strategy-design.md#synthesize-a-mechanism-from-the-mathematics)

### Allocate Inference to Recoverable Errors

**AI4Code。** 第四名用折外召回结果构造重排训练候选，把较贵的成对重排用于低置信样本。迁移时先测正确位置进入候选的比例，再在缓存候选上区分召回漏失和错序。把同等额外调用预算给低置信分流和随机分流作对照，完整笔记本仍按真实指标评分。 [第四名复盘](https://www.kaggle.com/competitions/AI4Code/writeups/gezi-4th-solution)

**SemEval 2026 叙事相似性。** FactUEP 在 400 条测试上报告单次 74.25%、全部复判 75.25%、按分差选择复判 75.75%。相对单次判断的配对区间跨 0。迁移时固定首判和复判输出，比较同成本随机与按分差分配，分别统计错变对和对变错。只有在额外判断的净收益能由决策时信号预测时，条件分流才有依据。 [参赛论文 §5、表 2](https://aclanthology.org/2026.semeval-1.147.pdf) · [主办方赛报附录表 4](https://aclanthology.org/2026.semeval-1.429.pdf)

### Audit Calibration and Metrics

**DCASE 2016 声景分类。** 开发融合的 89.93% 来自在评分折拟合校准的设置。正式未见集上，校准后的最强单路得 88.7%，两路融合得 89.7%。迁移时先验证缓存的训练来路，校准和权重放到各外层训练分区内拟合，同一外层组上对照最强单路、等权和学习组合。 [技术报告 §6.2、表 5](https://dcase.community/documents/challenge2016/technical_reports/DCASE2016_Eghbal-Zadeh_1028.pdf) · [正式榜单](https://dcase.community/challenge2016/task-acoustic-scene-classification-results#teams-ranking)

**NTIRE ViSAGE 视频显著性。** 论文的 10% 留出上，logit 融合提高 CC、SIM 和 NSS，AUC Judd 从最佳单路的 0.900 降到 0.897。主办方赛报与公开实现支持等权 logit 融合，参赛论文对提交方式有两种表述。终测成绩对应完整系统。迁移时按视频来源分组，固定同一批缓存预测，对照单路、显著图融合及 logit 融合，按事先规定的指标与聚合方式决策。 [参赛论文 §3.3、表 4](https://arxiv.org/html/2604.08613v1#S3.SS3) · [主办方赛报 §4.1](https://arxiv.org/html/2604.14816v1#S4.SS1) · [公开实现](https://github.com/iLearn-Lab/CVPRW26-ViSAGE/blob/4817ebcaeee238fad8afea644effdeb3d498541e/ensemble.py#L19-L27)

### Derive a Reduction from the Rules

**PACE 2026 最大一致森林。** TreeOfLife 利用删边只能分裂连通块这一点。若叶子 1 在两棵树中的当前分量分别为 `{1,2,3}` 与 `{1,4,5}`，它的最终块必在这两个集合的交里，因此可直接定为单点。交集有更多叶时还需验证拓扑。例如 `((1,2),3)` 与 `((1,3),2)` 初始连通交集含三叶，仍无法保留同一个三叶块。先用小实例穷举核对最优值，再固定搜索顺序开关该规则，分别测节点减少、判定开销与墙钟时间。正式名次支持完整求解器的表现。 [赛题定义](https://pacechallenge.org/2026/maf/) · [参赛实现的 Singleton reduction](https://raw.githubusercontent.com/HerrPixel/tree_of_life/5382daef4b6de8aaf5e9e4777c94cd5565ba7385/README.md)

### Check What State a Bucket Must Keep

**AHC073 与 AHC066。** AHC073 冠军把相近坐标归入同一桶，只留已用步数最少的候选。作者本地对照中，4×4 分块优于精确坐标，8×8 进一步提升，16×16 出现退化。AHC066 冠军按位置、朝向和是否持球分桶，每桶留多个候选，另用含球位置等信息的哈希去重。AHC066 的终榜成绩对应整套求解器。 [AHC073 复盘第 2 节](https://atcoder.jp/contests/ahc073/editorial/27919/print) · [AHC066 复盘的分桶与去重](https://atcoder.jp/contests/ahc066/editorial/21476)

设一个任务要以最短时间过门。到同一扇门的两个前缀分别耗时 2 和 3，剩余电量分别为 0 和 1。若唯一的过门动作耗电 1，按位置只留更快的前缀会删掉唯一可行解，先把电量纳入状态或保留互不支配的前缀。若过门耗电 0 且两个前缀过门时间相同，耗时 2 的前缀可以保留，省下的扩展预算可以搜索其他位置。先在小实例找这种反例，把能证明的支配规则用于精确剪枝。近似分桶按相同时间预算比较完整得分和丢失的可行分支。

### Resolve Close Comparisons

**AHC074 With AI。** 作者在同一实例上相邻运行各求解器以减弱机器负载差异，搜索早期用 500 个实例，差距小时改用 2,000 个。只给最优分或文字解法的几次重启也未产出更强路线。迁移时用自己的配对分差与决策成本确定何时追加未用过的开发实例，另外用完整留出复核。若卡在生成候选，先换能改变表示或状态决策的构造。该复盘的实例数和重启结果只覆盖作者的设置。 [第三名选手复盘](https://atcoder.jp/contests/ahc074/editorial/28915) · [正式赛道成绩](https://atcoder.jp/contests/ahc074/results/with_ai)
