# Kaggle 高分方案

每条记录对应一个比赛或正式赛道。按当前的决策问题查找案例，再用同一批本地样本检查迁移条件。[按问题查找案例](case-library.md)

## amex-default-prediction

**American Express – Default Prediction · 2022 私榜**

- **成绩** 第 1 名，lucky shake，AmEx 指标 0.80977。 [榜单](https://www.kaggle.com/competitions/amex-default-prediction/leaderboard)
- **机制** 用树模型处理汇总特征，同时用打包后的变长客户序列训练神经模型，最后融合两个表示。 [团队复盘](https://www.kaggle.com/competitions/amex-default-prediction/writeups/lucky-shake-1st-solution-update-github-code)
- **证据边界** 选手说明神经分支的缺失值处理与序列打包，并提供复现代码。第一名的成绩来自重型融合，报告未给变长表示自身的配对收益。
- **本地对照建议** 按客户留出并保留时间边界，在相同历史输入下比较仅用汇总特征的树模型和加入序列神经网络分支后的组合。分历史长度评估增益。

## avito-demand-prediction

**Avito Demand Prediction · 2018 私榜**

- **成绩** 第 1 名，Dance with Ensemble，RMSE 0.21501。 [榜单](https://www.kaggle.com/competitions/avito-demand-prediction/leaderboard)
- **机制** 同一商品的标题、描述与图片分别编码。先用冻结的图片表示测试边际价值，再决定是否花预算做端到端微调。 [团队复盘](https://www.kaggle.com/competitions/avito-demand-prediction/writeups/dance-with-ensemble-dance-with-ensemble-sharing-th)
- **证据边界** 作者自己的模型开发记录中，VGG 特征初次接入变差，修改融合结构后改善。冻结的 ResNet 中层后续改善，尝试的图像微调方案未产生收益。各次同时包含其他变更，分差为作者报告的公榜近似值。
- **本地对照建议** 使用同一时间留出和冻结的文本分支，对照无图、冻结图像分支、图像微调。记录每个方案的分差、算力和图片缺失组误差。

## commonlit-evaluate-student-summaries

**CommonLit – Evaluate Student Summaries · 2023 私榜**

- **成绩** 第 1 名，Lucky shake，MCRMSE 0.45181。 [榜单](https://www.kaggle.com/competitions/commonlit-evaluate-student-summaries/leaderboard)
- **机制** 当训练中只有少数主题时，先用合成主题及不同质量的摘要扩展覆盖，用教师获得伪标签，再只用真实训练数据完成微调。 [团队复盘](https://www.kaggle.com/competitions/commonlit-evaluate-student-summaries/writeups/lucky-shake-1st-a-brief-review-of-the-competition-)
- **证据边界** 冠军说明提供四个主题、三轮伪标和分阶段训练。私榜是整个流程的成绩，没有分离主题覆盖、摘要质量和伪标的独立效果。
- **本地对照建议** 按主题做留一验证。用等量合成摘要对比扩大主题与只扩充已有主题，并保留无合成基线。

## commonlitreadabilityprize

**CommonLit Readability Prize · 2021 私榜**

- **成绩** 第 1 名，Mathis Lucka，RMSE 0.446。 [榜单](https://www.kaggle.com/competitions/commonlitreadabilityprize/leaderboard)
- **机制** 按原训练片段相似度从许可语料检索并打伪标签，以原片段的标注标准误差限制候选伪标签的偏离。先用伪标签训练，再回到真实标签。 [团队复盘](https://www.kaggle.com/competitions/commonlitreadabilityprize/writeups/mathis-lucka-1st-place-solution-external-data-teac)
- **证据边界** 冠军说明了筛选规则，并报告多轮伪标使 CV 表现继续改善、榜单表现变差。作者对反复评测造成过拟合的解释是推测。
- **本地对照建议** 锁定语料、采样量和学员模型。按原始文档或来源留组，一次比较随机选样、相似度检索和检索后筛选，再用封存留组核对净收益。

## elo-merchant-category-recommendation

**Elo Merchant Category Recommendation · 2019 私榜**

- **成绩** 第 1 名，Look alive，RMSE 3.57875。 [榜单](https://www.kaggle.com/competitions/elo-merchant-category-recommendation/leaderboard)
- **机制** 对一个固定极端标签值估计其出现概率，对普通区间单独做回归，然后按概率计算条件均值。 [团队复盘](https://www.kaggle.com/competitions/elo-merchant-category-recommendation/writeups/look-alive-my-simple-trick-for-this-competition)
- **证据边界** 冠军给出加权公式，并自报同特征直接回归的本地对照约改善 0.015。这个数字没有独立复现，且其他团队使用不同分类器的表现有差异。
- **本地对照建议** 锁定同一组输入和验证折，用平方损失配对比较直接回归、软门控和硬门控。单报常数点概率的校准和极端标签组误差。

## favorita-grocery-sales-forecasting

**Corporación Favorita Grocery Sales Forecasting · 2017–2018 私榜**

- **成绩** 第 1 名，w，NWRMSLE 0.50918。 [榜单](https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/leaderboard)
- **机制** 分别让 16 个子模型对 16 个预测步负责，并与共享预测模型一起做固定线性融合。 [团队复盘](https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting/writeups/w-1st-place-solution)
- **证据边界** 团队报告了四个单方案的公榜和私榜分数，并表示该设置中的堆叠表现不理想。分步训练的对照还伴随模型结构等差异。
- **本地对照建议** 在同一滚动切分复用完全相同的特征和模型容量预算，对比带步长索引的共享模型与分步模型，再按步长记录误差和训练开销。

## g-research-crypto-forecasting

**G-Research Crypto Forecasting · 2021–2022 最终私榜**

- **成绩** 第 2 名，Nathaniel Maddux，加权相关系数 0.0283。 [榜单](https://www.kaggle.com/competitions/g-research-crypto-forecasting/leaderboard)
- **机制** 同一时戳的各资产放在同一折，用带间隔的滚动前推做验证，观察不同日期对同一改动的方向。 [团队复盘](https://www.kaggle.com/competitions/g-research-crypto-forecasting/writeups/nathaniel-maddux-2nd-place-solution)
- **证据边界** 亚军描述了六折、约一周隔离的本地评测，但最终提交没有保留该间隔。其变动不提供普适最优间隔。
- **本地对照建议** 按标签未来依赖长度选择最小隔离量。固定模型和特征比较零隔离与有隔离时的配对结果，重合的时间窗按依赖关系汇总。

## google-quest-challenge

**Google QUEST Q&A Labeling · 2020 私榜**

- **成绩** 第 1 名，bibimorph，列均 Spearman 0.43100。 [榜单](https://www.kaggle.com/competitions/google-quest-challenge/leaderboard)
- **机制** 每个外层折用只见过该折训练数据的教师给相近外部问题生成伪标签，避免验证标签通过教师和近重复问题返回训练。 [团队复盘](https://www.kaggle.com/competitions/google-quest-challenge/writeups/bibimorph-1st-place-solution-with-code)
- **证据边界** 冠军自报基线 0.414。混用各折教师的方案本地到 0.445 但公榜未确认，按折重新生成的本地结果为 0.422。对照描述限定在团队环境。
- **本地对照建议** 先按问题来源和近重复关系分组，再冻结外层切分。比较无伪标签与折内教师伪标签，另审计每条伪标签的教师训练 ID。

## google-universal-image-embedding

**Google Universal Image Embedding · 2022 私榜**

- **成绩** 第 1 名，[cuilab.ai]，mMP@5 0.728。 [榜单](https://www.kaggle.com/competitions/google-universal-image-embedding/leaderboard)
- **机制** 先冻结视觉骨干训练低维投影头，再锁定投影来适配骨干，缓解缩到 64 维时类中心几何快速漂移。 [团队复盘](https://www.kaggle.com/competitions/google-universal-image-embedding/writeups/cuilab-ai-1st-place-solution)
- **证据边界** 作者报告观察到投影权重变化，并把冻结与增加 dropout 同批实验。最终胜出方案还更换了骨干和数据配方，无法由私榜隔离冻结的收益。
- **本地对照建议** 固定数据、初始化、投影维数和算力预算，在未见类别上比较联合训练与先后训练，报告检索质量和类中心距离矩阵变化。

## h-and-m-personalized-fashion-recommendations

**H&M Personalized Fashion Recommendations · 2022 私榜**

- **成绩** 第 1 名，senkin13 & 30CrMnSiA，MAP@12 0.03792。 [榜单](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/leaderboard)
- **机制** 按预测周先找候选，再让排序器使用复购、近段热门和协同过滤中的交互信号。区分近期活跃用户和缺近期历史的用户。 [团队复盘](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/writeups/senkin13-30crmnsia-1st-place-solution)
- **证据边界** 团队报告按周验证以及逐周的候选命中数。其设置下尝试的冷启动候选没有进入前 12，尚不能判断临时换一种候选或排序策略的效果。
- **本地对照建议** 只用切点可见的交易重放两个以上的下一周。固定每用户 100 个候选和同一个排序器，比较每种来源加入后的候选命中和最终 MAP@12。

## ieee-fraud-detection

**IEEE-CIS Fraud Detection · 2019 私榜**

- **成绩** 第 1 名，FraudSquad，ROC AUC 0.945884。 [榜单](https://www.kaggle.com/competitions/ieee-fraud-detection/leaderboard)
- **机制** 先用单个或一组特征训练轻量探针，跨月检验信号是否反转，再以多种时间切分和新旧实体分组复核。 [团队复盘](https://www.kaggle.com/competitions/ieee-fraud-detection/writeups/fraudsquad-1st-place-solution-part-2)
- **证据边界** 冠军团队报告有些特征近月 AUC 约 0.60、远月约 0.40，并明确存在特征交互。上述探针结果与完整模型删列的分数是两个问题。
- **本地对照建议** 固定后续窗口。核对输入时间与标签成熟时间，用跨窗口的整组删除对照决定是否移除特征，而后在封存月份检验。

## jane-street-market-prediction

**Jane Street Market Prediction · 2020–2021 私榜**

- **成绩** 第 1 名，Cats Trading...，效用 6476.594。 [榜单](https://www.kaggle.com/competitions/jane-street-market-prediction/leaderboard)
- **机制** 把由标签监督的自编码器与下游分类器一起放进每个时间折训练，避免先用全部样本拟合特征表示。 [团队复盘](https://www.kaggle.com/competitions/jane-street-market-prediction/writeups/cats-trading-yirun-s-solution-1st-place-training-s)
- **证据边界** 团队成员说明最终提交融合其分折联合训练模型与队友的 XGBoost，并给出做法。公开正文没有同设计下与无编码器基线的配对收益。
- **本地对照建议** 固定按日留出的隔离区间和官方效用计算，比较原始特征与折内监督表示。在评测入口校验编码器拟合行与外层验证行交集为空。

## jigsaw-unintended-bias-in-toxicity-classification

**Jigsaw Unintended Bias in Toxicity Classification · 2019 私榜**

- **成绩** 第 1 名，［ods.ai］ Toxiciology，官方综合 AUC 指标 0.94734。 [榜单](https://www.kaggle.com/competitions/jigsaw-unintended-bias-in-toxicity-classification/leaderboard)
- **机制** 用身份子群内、背景正例与子群负例、背景负例与子群正例的三类掩码聚合分类损失，以增加难类群的训练权重。 [团队复盘](https://www.kaggle.com/competitions/jigsaw-unintended-bias-in-toxicity-classification/writeups/ods-ai-toxiciology-1st-place-solution)
- **证据边界** 选手公开给出对应三个子群切片的分类损失代码。官方分数综合全局 AUC 与三类子群 AUC 的幂平均。训练用逐行交叉熵，最终评分用正负样本排序。整队成绩没有隔离这一项的贡献。 [指标定义](https://www.kaggle.com/c/jigsaw-unintended-bias-in-toxicity-classification)
- **本地对照建议** 复用相同编码器和切分，比较普通 BCE 和子群代理损失，报告三个子群 AUC 分量、全局 AUC 和少数群样本量。

## kaggle-llm-science-exam

**Kaggle – LLM Science Exam · 2023 私榜**

- **成绩** 第 1 名，Team H2O LLM Studio，MAP@3 0.933208。 [榜单](https://www.kaggle.com/competitions/kaggle-llm-science-exam/leaderboard)
- **机制** 检索同一题目的公共证据后只算一次题干前缀缓存，对选项逐个打分。需要选项对比时，用其他选项表示的均值作为排列无关的补充。 [团队复盘](https://www.kaggle.com/competitions/kaggle-llm-science-exam/writeups/team-h2o-llm-studio-1st-place-solution)
- **证据边界** 团队用公开合成题训练，从公开 Wikipedia 检索上下文。官方 200 道带标注样例接近满分后，团队另用约 6,000 道公开 STEM 题做本地验证。私榜成绩来自包含检索和模型融合的完整提交。无序选项聚合的独立分差未见报告。 [官方数据说明](https://www.kaggle.com/competitions/kaggle-llm-science-exam/data?select=test.csv)
- **本地对照建议** 在同一批缓存证据上打乱选项次序，检查映射回原 ID 后的名次和偏差，再配对比较只看单选项与带均值聚合的 MAP@3、时延。

## learning-agency-lab-automated-essay-scoring-2

**Learning Agency Lab – Automated Essay Scoring 2.0 · 2024 私榜**

- **成绩** 第 1 名，flg，QWK 0.84128。 [榜单](https://www.kaggle.com/competitions/learning-agency-lab-automated-essay-scoring-2/leaderboard)
- **机制** 先用旧语料学通用表示，再用与目标打分标准更接近的新语料适配。如要继续利用旧语料，可将它当作待重新标注的数据。 [团队复盘](https://www.kaggle.com/competitions/learning-agency-lab-automated-essay-scoring-2/writeups/flg-1st-place-solution-trust-cv-and-lb-a-bit)
- **证据边界** 冠军按题目与分数分层。其第一轮伪标使 CV 明显改善但公榜改善小。第二轮中有 CV 高而公榜低、私榜却不错的单模型。各私榜分数对应完整模型或组合。
- **本地对照建议** 按共同题目锁定评测，固定模型和真实数据量，比较旧新混训、旧预训练加新适配，以及旧数据重标后适配。单报稀有分数段误差。

## lux-ai-season-2

**Lux AI Season 2 · 2023 最终榜**

- **成绩** 第 1 名，ry_andy_，对战评分 2407.2。 [榜单](https://www.kaggle.com/competitions/lux-ai-season-2/leaderboard)
- **机制** 把单位的长期角色和眼前多步目标分开，跨决策调用保存。滚动模拟时每步检查角色失效，再用优先级分配有限资源。 [团队复盘](https://www.kaggle.com/competitions/lux-ai-season-2/writeups/ry-andy-1st-place-solution)
- **证据边界** 冠军报告时间限额下前看约 5 至 50 多步。模拟对对手和个别冲突作了简化，不保证越长越好。排名属于整套 Bot。
- **本地对照建议** 使用固定地图种子、双方出生位置与冻结对手，等时间预算对比即时规则、带持久角色的即时规则、带角色和前向模拟。统计超时、胜率与角色失效。

## mercari-price-suggestion-challenge

**Mercari Price Suggestion Challenge · 2017–2018 私榜**

- **成绩** 第 1 名，Paweł and Konstantin，RMSLE 0.37758。 [榜单](https://www.kaggle.com/competitions/mercari-price-suggestion-challenge/leaderboard)
- **机制** 用同一稀疏 MLP 学不同的文本表征，以较低成本产生互补预测。让词与数量绑定的特征专门处理组合商品。 [团队复盘](https://www.kaggle.com/competitions/mercari-price-suggestion-challenge/writeups/pawe-and-konstantin-1st-place-solution)
- **证据边界** 冠军团队报告文本预处理差异带来的改善，并说一个数据分支加入数量向量化后，整个融合改善 0.001。正文描述的是团队对照，无法独立归因于最终私榜。
- **本地对照建议** 固定资源，把候选限定为无数量绑定与有数量绑定。先在组合商品和单件商品上断面评分，再比较同输入多模型与同模型多表示在留出集的收益。

## optiver-trading-at-the-close

**Optiver – Trading at the Close · 2023–2024 最终私榜**

- **成绩** 第 1 名，hyd，MAE 5.4030。 [榜单](https://www.kaggle.com/competitions/optiver-trading-at-the-close/leaderboard)
- **机制** 按标签实际释放时间重放训练更新，以每日数据分片顺序写入预分配的数组，避免拼接新旧数据拖垮更新预算。 [团队复盘](https://www.kaggle.com/competitions/optiver-trading-at-the-close/writeups/hyd-1st-place-solution)
- **证据边界** 冠军列了不更新与多次更新的结果。作者说最佳提交因运行时余量只实际更新四次，表中的理论第五次预估不算已取得成绩。
- **本地对照建议** 顺序重放同一后续时段，在每次更新前校验所有标签已释放。比较不更新、单次更新与固定周期更新下的 MAE、运行时和最慢一轮。

## porto-seguro-safe-driver-prediction

**Porto Seguro’s Safe Driver Prediction · 2017 私榜**

- **成绩** 第 1 名，Michael Jahrer，归一化 Gini 0.29698。 [榜单](https://www.kaggle.com/competitions/porto-seguro-safe-driver-prediction/leaderboard)
- **机制** 按列从其他行抽值作交换噪声，破坏跨列关系且保留单列取值，再训练自编码器重建干净输入并复用隐层。 [团队复盘](https://www.kaggle.com/competitions/porto-seguro-safe-driver-prediction/writeups/michael-jahrer-1st-place-with-representation-learn)
- **证据边界** 冠军方案曾用训练集和无标签测试特征做预训练。作者对同参数的模型 2 改用纯训练集预训练后，私榜归一化 Gini 由 0.29298 降至 0.29235。榜首成绩来自多个模型的组合，迁移时应按目标比赛的规则确认可用数据。
- **本地对照建议** 固定按风险分层的切分，在只用折内训练数据的前提下配对比较无预训练、按列交换噪声与合适的遮蔽噪声，同时记录不同字段类型的重建误差。

## recruit-restaurant-visitor-forecasting

**Recruit Restaurant Visitor Forecasting · 2018 私榜**

- **成绩** 第 1 名，PPPP，RMSLE 0.50128。 [榜单](https://www.kaggle.com/competitions/recruit-restaurant-visitor-forecasting/leaderboard)
- **机制** 同样的模型和特征用三种预测训练窗口长度与取样位置构造监督，再融合不同时间配置的输出。 [团队复盘](https://www.kaggle.com/competitions/recruit-restaurant-visitor-forecasting/writeups/pppp-solution-public-0-471-private-0-505)
- **证据边界** 冠军成员 plantsgo 报告其窗口融合离线改善 0.002，同配置外加异类模型融合只改善 0.0002。说的是成员分支的离线结果，官方分数为团队整体。
- **本地对照建议** 在等量、相同历史范围和预测周期的回测里，比较同窗口异模型与同模型异窗口。按预测步长、餐馆与节假日分别查看误差。

## rossmann-store-sales

**Rossmann Store Sales · 2015 私榜**

- **成绩** 第 1 名，Gert，RMSPE 0.10021。 [榜单](https://www.kaggle.com/competitions/rossmann-store-sales/leaderboard)
- **机制** 将按门店、星期、促销、学校假期等分层的历史统计按预测用途分别配置。销售模型、客流模型与月前预测模型可看到的统计分别构建。 [团队复盘](https://www.kaggle.com/competitions/rossmann-store-sales/writeups/gert-model-documentation-1st-place)
- **证据边界** 冠军公开特征字典及历史分组缩写，确立了表示和分支归属，没有测量其中某项统计的独立私榜提升。
- **本地对照建议** 按预测原点冻结销售、客流、开闭店与促销的可见时点。在同一时间留出中比较仅分门店和加入促销/星期的历史统计，单报促销期和长预测步长。

## santa-2022

**Santa 2022 – The Christmas Card Conundrum · 2022–2023 最终榜**

- **成绩** 第 1 名，Newtonians，总成本 74075.7065416901。 [榜单](https://www.kaggle.com/competitions/santa-2022/leaderboard)
- **机制** 先用路径依赖的机械臂约束筛图像巡回路径，再用大臂状态的 DP 表剪枝、用束搜索恢复整条合法关节轨迹。 [团队复盘](https://www.kaggle.com/competitions/santa-2022/writeups/newtonians-1st-place-solution-with-visualized-rout)
- **证据边界** 冠军报告四项路径条件在其试验中足够剔除不想要的路径，但没有证明这些条件对所有实例充分。多队获得相同分数，名次不证明机制优越。
- **本地对照建议** 用小图和少量短候选做精确枚举，量化路径近似器的假接受、假拒绝和成本误差。完整评分器校验所有返回的机械臂动作与像素顺序。

## shopee-product-matching

**Shopee – Price Match Guarantee · 2021 私榜**

- **成绩** 第 1 名，Upstage, Making AI Beneficial，逐商品平均 F1 0.780。 [榜单](https://www.kaggle.com/competitions/shopee-product-matching/leaderboard)
- **机制** 固定图文嵌入后，选择满足相似度阈值的邻居，用相似度加权聚合，再检索并重复。 [团队复盘](https://www.kaggle.com/competitions/shopee-product-matching/writeups/upstage-making-ai-beneficial-1st-place-solution-fr)
- **证据边界** 选手公开算法与代码，并说明部分阶段阈值曾按榜单调节。它使用整个候选商品集合。弱匹配边可能随迭代扩散。整体排名不是邻域混合的独立增量。
- **本地对照建议** 使用训练时未见的完整商品簇和缓存嵌入，比较零次、一次、两次更新下的每查询 F1、孤立查询和错簇合并率。阈值由另一组商品簇确定。

## us-patent-phrase-to-phrase-matching

**U.S. Patent Phrase to Phrase Matching · 2022 私榜**

- **成绩** 第 1 名，gezi，Pearson 0.8782。 [榜单](https://www.kaggle.com/competitions/us-patent-phrase-to-phrase-matching/leaderboard)
- **机制** 在比较一对短语时，加入同一锚词及分类的其他候选作为集合上下文，不把当前被比较的目标重复放进去。 [团队复盘](https://www.kaggle.com/competitions/us-patent-phrase-to-phrase-matching/writeups/gezi-1st-place-solution)
- **证据边界** 冠军按锚词和词重叠分折。团队试过细分类和大类两种候选上下文，并把大类方案加入融合。迁移时要先确认规则允许看到完整候选集合。公开材料没有给出只切换上下文粒度的私榜对照。
- **本地对照建议** 让共享短语的连通分量进入同一折。锁定可见的候选集合，对比只看当前对、加同细分类候选和加同大类候选的 Pearson 与稀有术语表现。

## web-traffic-time-series-forecasting

**Web Traffic Time Series Forecasting · 2017 第 2 阶段私榜**

- **成绩** 第 1 名，Arthur Suilin，SMAPE 35.48065。 [榜单](https://www.kaggle.com/competitions/web-traffic-time-series-forecasting/leaderboard)
- **机制** 用按年、半年、季度对齐的可见滞后值显式提供远期季节信息，让编码器只处理较短的近邻历史。 [团队复盘](https://www.kaggle.com/competitions/web-traffic-time-series-forecasting/writeups/arthur-suilin-1st-place-solution)
- **证据边界** 冠军叙述先做窗口注意力，再发现显式滞后达到很强的结果并允许缩短编码长度。作者还试验按页面分割，发现它不能预测未来窗口上的表现。
- **本地对照建议** 在同一系列的几个滚动预测原点做基线，比较长历史编码与短历史加季节滞后，分别报告时间、节假日偏移和历史不足系列的误差。
