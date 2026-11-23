# 视觉、语音和文档识别高分方案

每条记录对应一个比赛或正式赛道。按当前的决策问题查找案例，再用同一批本地样本检查迁移条件。[按问题查找案例](case-library.md)

## ntire-2024-night-render-efficiency

**NTIRE 夜间照片渲染 · 2024 效率赛道**

- **成绩** MiAlgo 第 1，单图 1.5 秒，质量均值 0.73。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Ershov_NTIRE_2024_Challenge_on_Night_Photography_Rendering_CVPRW_2024_paper.pdf)
- **机制** 先把四通道 RAW 缩到目标分辨率，再进行 RAW 去噪、白平衡和 RGB 修复，把整个后续流程的工作量一起降下来。
- **证据边界** 主办方先按 50 张隐藏测试图的人评质量选出前五，再按处理耗时排序。1.5 秒排除 I/O，报告呈现整条 MiAlgo 流水线。
- **本地对照建议** 用固定可复用的流水线交换缩放顺序，仅测 20 张不同照度的夜景。固定输出分辨率和设备，比较耗时、亮部细节与盲评偏好。

## ntire-2024-blind-jpeg

**NTIRE 盲 JPEG 压缩图恢复 · 2024**

- **成绩** IMCL-BVQE 第 1，PSNR 34.4749 dB。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Yang_NTIRE_2024_Challenge_on_Blind_Enhancement_of_Compressed_Image_Methods_CVPRW_2024_paper.pdf)
- **机制** 复原模型从输入特征生成与压缩状态相适应的提示，在上采样阶段把这些提示送回复原分支。
- **证据边界** 主办方报告还记录了训练外的 LIVE1 上前四名顺序相同。榜分来自含两模型与旋转集成的提交，未单独测定提示的贡献。
- **本地对照建议** 用同一批原图生成不同 JPEG 质量因子的配对样本。同宽同算量训练固定提示与按图生成提示，按原图扣留再分压缩强度汇报 PSNR。

## ntire-2024-stereo-sr-fidelity

**NTIRE 双目图像超分辨率 · 2024 Track 1 双三次降质保真**

- **成绩** Davinci 第 1，RGB PSNR 23.6503 dB。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Wang_NTIRE_2024_Challenge_on_Stereo_Image_Super-Resolution_Methods_and_Results_CVPRW_2024_paper.pdf)
- **机制** 对相同结构的多套 SwinFIRSSR 参数做等权平均，得到一次可运行的模型。主网络还用跨目注意力融合左右特征。
- **证据边界** 参数平均减少多模型推理次数。报告的榜分还包含输入变换集成和其他架构改动，不能单独给参数平均计功。
- **本地对照建议** 复用从同一初始化或训练轨迹得到的几个 checkpoint，保持输入变换次数相同，在未见双目场景对比最佳单模型、参数平均和预测平均的 PSNR 与单图耗时。

## ntire-2024-shadow-fidelity

**NTIRE 高分辨率去阴影 · 2024 Track 1 保真**

- **成绩** LUMOS 第 1，PSNR 24.78 dB、SSIM 0.832、LPIPS 0.110。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Vasluianu_NTIRE_2024_Image_Shadow_Removal_Challenge_Report_CVPRW_2024_paper.pdf)
- **机制** 先用能处理 2K 图的 Transformer 去除大范围不均匀阴影，再用 NAFNet 精修暗阴影及分块伪影。
- **证据边界** 冠军由多项保真指标决定，PSNR 单项第 2。报告没有给精修模块独立的增益。
- **本地对照建议** 用已保存的粗模型及精修模型，在同一批场景比较第一阶段与完整输出，分阴影内部、边界和无遮挡区域量误差，并记录延迟。

## ntire-2025-rgb-to-raw-efficient

**NTIRE 手机 RGB 反推 RAW · 2025 高效赛道**

- **成绩** TongJi-IPOE 的 DBNet 在高效赛道终测第 1，综合 PSNR、SSIM 均最高，分别为 27.66 dB、0.7700。 [主办方赛报 §2.4、表 1](https://arxiv.org/html/2506.01947v1#S2.SS4)
- **机制** 按 Bayer 采样把输入排列成 RGGB，再让 RB 与 GG 分支分别复原。轻量卷积随输入改变偏置，最后混合分支输出。
- **证据边界** 高效赛道要求参数不足 0.2M 且可处理 12MP。训练阶段允许 ISP 元数据，评测阶段不提供。队伍在已知设备与新设备的 PSNR 分别为 30.76、23.94。
- **本地对照建议** 先留出一种训练可用设备，同参数预算比较独立 RB/GG 分支和共享复原分支。按设备汇报 RAW PSNR，随后再查输入偏置的增量。

## ntire-2025-event-deblur

**NTIRE 事件辅助图像去模糊 · 2025**

- **成绩** IVISLAB 第 1，PSNR 42.79 dB、SSIM 0.9196。 [原始报告](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Sun_NTIRE_2025_Challenge_on_Event-Based_Image_Deblurring_Methods_and_Results_CVPRW_2025_paper.pdf)
- **机制** 将连续事件按三种时间尺度变成体素，与模糊帧特征融合，让短时间窗保留边缘、较长窗提供运动上下文。
- **证据边界** 271 张 HighREV 测试图按 PSNR 排名。第二名 SSIM 更高。报告未隔离三尺度表示的收益。
- **本地对照建议** 对齐同一段可用曝光时间，固定图像分支、事件总输入预算与训练步数，对比单尺度和三尺度，在按录制场景留出的高速及低速运动组分别评分。

## ntire-2025-depth-stereo-tom

**NTIRE 镜面和透明表面高分辨率深度 · 2025 双目赛道 ToM 专项排名**

- **成绩** SRC-B 专项第 1，bad-2 42.47，全像素第 3。 [原始报告，表 1、§5.1.4](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Ramirez_NTIRE_2025_Challenge_on_HR_Depth_from_Images_of_Specular_CVPRW_2025_paper.pdf)
- **机制** 将冻结的单目深度编码器特征变成多尺度金字塔，引导双目匹配处理镜面和透明表面，并用模拟场景补充训练。
- **证据边界** 报告表 1 的名次及 §4.1 对应 bad-2，表注误写单目指标 δ。整套方案同时改变模型和训练数据。
- **本地对照建议** 固定双目模型和训练样本，短训有无单目特征注入的版本。按物体或场景留出，分 ToM 和普通材质各报 bad-2。

## ntire-2024-low-light

**NTIRE 高分辨率低照度增强 · 2024**

- **成绩** SYSU-FVL-T2 第 1，PSNR 25.52 dB、SSIM 0.8637。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Liu_NTIRE_2024_Challenge_on_Low_Light_Image_Enhancement_Methods_and_CVPRW_2024_paper.pdf)
- **机制** 利用三种分辨率预测共同监督，并在每个编码尺度动态融合邻接尺度的特征。
- **证据边界** 主办方以 PSNR 和 SSIM 的加权组合排名。报告指出 4K 以上图像使很多方法难在 12 GB 显存上运行。表 1 没有拆开多尺度监督的增益。
- **本地对照建议** 固定轻量骨干及样本量，有无中间尺度监督各短训一次，保留训练外场景。比较整图与低亮度区域误差，并记录峰值显存。

## ntire-2024-bracket-ire

**NTIRE 多曝光 RAW 括拍图像恢复 · 2024 Track 1 BracketIRE**

- **成绩** Samsung 第 1，全图 PSNR 40.54 dB，去边缘后 41.77 dB。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Zhang_NTIRE_2024_Challenge_on_Bracketing_Image_Restoration_and_Enhancement__CVPRW_2024_paper.pdf)
- **机制** 第一阶段用第二帧作对齐参考。相对于第一帧，它噪声较低且模糊可接受。融合五帧后另有精修模块。
- **证据边界** 最终榜按全图 PSNR 排，表中另报告裁边分，整条提交同时有网络加宽和精修。选择参考帧的独立贡献未知。
- **本地对照建议** 冻结配准及融合网络，挑几组曝光差异明显的连拍，只交换参考帧并正确反变换回输出坐标。报告全图及边区变化。

## ntire-2024-dense-dehazing

**NTIRE 非均匀浓雾图像恢复 · 2024**

- **成绩** USTC-Dehazers 第 1，MOS 6.315、PSNR 22.943 dB。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Ancuti_NTIRE_2024_Dense_and_Non-Homogeneous_Dehazing_Challenge_Report_CVPRW_2024_paper.pdf)
- **机制** 在真实去雾配对有限时，动态控制合成雾与真实样本比例。网络分别处理长程空间信息和大图细节。
- **证据边界** 主办方测试仅 5 张图，最终还有盲评。真实与合成配比、双支路和感知损失同时变化，排名不能分配到某一项。
- **本地对照建议** 用相同骨干、总样本和步数比较固定混合比例和动态比例。扣留真实拍摄场景，先看浓雾区域及无遮挡区误差，再决定是否补盲评。

## ntire-2024-light-field-sr-classic

**NTIRE 光场超分辨率 · 2024 Track 1 保真**

- **成绩** BNU&TMU-AI-TRY 第 1，平均 PSNR 30.80 dB。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Wang_NTIRE_2024_Challenge_on_Light_Field_Image_Super-Resolution_Methods_and_CVPRW_2024_paper.pdf)
- **机制** 从 9×9 视角格抽取不同间距的 5×5 子视角，覆盖更大的视差。模型沿极线平面中的像素学习跨视角关系。
- **证据边界** 主办方分真实 Lytro 和合成测试场景。提交还加宽模型、增深并集成，报告未隔离重采样贡献。
- **本地对照建议** 冻结训练算力和骨干，中心采样与多种间距采样各训练一次。对同一组留出光场按视差分桶，测 PSNR 及大视差子集。

## ntire-2024-aigc-image-quality

**NTIRE 生成内容质量评测 · 2024 Track 1 图像**

- **成绩** pengfei 第 1，主分 0.9175，SRCC 0.9076、PLCC 0.9274。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Liu_NTIRE_2024_Quality_Assessment_of_AI-Generated_Content_Challenge_CVPRW_2024_paper.pdf)
- **机制** 让 CLIP 对同一提示词下的五级图文匹配描述打分，把提示遵从度和图像质量联系起来。
- **证据边界** 主分是 SRCC、PLCC 的绝对值均值，后者采用三阶非线性回归。冠军与第二名的主分只差 0.0006，作者报告未给模块独立的赛果。
- **本地对照建议** 缓存同一图像编码，分别换成带真实提示和通用提示的文本模板，固定回归程序。在留出的生成器和提示词上比较相关性，检查提示是否确实提供信息。

## ntire-2024-ugc-video-quality

**NTIRE 短视频质量评测 · 2024 用户生成视频**

- **成绩** SJTU MMLab 第 1，综合分 0.9228。 [原始报告](https://openaccess.thecvf.com/content/CVPR2024W/NTIRE/papers/Li_NTIRE_2024_Challenge_on_Short-form_UGC_Video_Quality_Assessment_Methods_CVPRW_2024_paper.pdf)
- **机制** 按秒抽关键帧来提取场景和质量特征，同时以局部时空片段提取运动相关的质量特征，合并后做回归。
- **证据边界** 整体成绩含多种外部预训练和 10 个训练划分的集成。综合指标同时覆盖相关性与排序，不能从榜分判断时空特征贡献。
- **本地对照建议** 缓存相同视频的单帧和局部时空特征，只短训回归头对比有无时空分支。按原视频来源留出，分别看有运动和静态片段上的排序。

## ntire-2025-burst-hdr

**NTIRE 连拍 HDR 复原 · 2025**

- **成绩** ImvisionAI 第 1，PSNR 43.22 dB。推理 7.12 秒。 [原始报告](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Lee_NTIRE_2025_Challenge_on_Efficient_Burst_HDR_and_Restoration_Datasets_CVPRW_2025_paper.pdf)
- **机制** 先按曝光亮度校准并递归对齐多帧，单独训练对齐模块。第二阶段冻结该模块再训练复原，使配准与纹理恢复分阶段优化。
- **证据边界** 同一报告给第二名 DeepTrans 42.75 dB、0.24 秒，耗时均在单张 H100 上测。排名按精度，较高 PSNR 伴随较高延迟。
- **本地对照建议** 缓存参考坐标下的对齐结果及不做跨曝光校准的结果，固定复原模块，跑若干高饱和及高运动场景，比较 PSNR、重影与匹配失败率。

## ntire-2025-cross-domain-fewshot

**NTIRE 跨域少样本目标检测 · 2025 Main Open-Source Track**

- **成绩** MoveFree 第 1，组合分 231.01。 [原始报告](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Fu_NTIRE_2025_Challenge_on_Cross-Domain_Few-Shot_Object_Detection_Methods_and_CVPRW_2025_paper.pdf)
- **机制** Grounding DINO 在训练图上周期性产生候选伪框来补充漏标，然后继续微调。队伍还在解码层使用专家混合架构。
- **证据边界** 榜表组合三个域和不同样本数。补标和模型结构同时变化，榜分不给出补标的独立效果。
- **本地对照建议** 冻结骨干和训练步数，只在训练图加一轮高置信度伪框，人工抽查一小批是否补到漏标。对未参与补标的类别或图源计算 mAP，并量伪框误报。

## ntire-2025-reflection-wild

**NTIRE 真实场景单图去反射 · 2025**

- **成绩** X-Reflection 第 1，主观均值 4.328125、PSNR 33.7606 dB。 [原始报告](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Yang_NTIRE_2025_Challenge_on_Single_Image_Reflection_Removal_in_the_CVPRW_2025_paper.pdf)
- **机制** RDNet+ 让主干特征而非独立提示生成器提供恢复提示，同时把多套训练权重合并以平衡不同质量目标。
- **证据边界** 主办方只对初筛前七进行主观评估，前四名主观分最大差 0.046875。两项改动和真实及合成训练资料同时变化。
- **本地对照建议** 先使用模型已有 checkpoint，比单套权重及合并权重。对建筑玻璃与室内反射分别扣留场景，用相同推理增强，比较失真与成对盲评。

## ntire-2025-ambient-normalization

**NTIRE 环境光照归一化 · 2025**

- **成绩** LightWorker 总排名第 2，PSNR 26.500 dB 为单项第 1，MOS 9.05。 [原始报告](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Vasluianu_NTIRE_2025_Ambient_Lighting_Normalization_Challenge_Report_CVPRW_2025_paper.pdf)
- **机制** 用扩散模型给恢复图动态叠加多种阴影，再用这些成对数据迭代训练无掩码去阴影模型。
- **证据边界** 相同测试集上冠军 MI ALN R 的 PSNR 是 26.314、MOS 是 9.20。该排名及分项呈现整条方案，不能给合成影子单独归因。
- **本地对照建议** 缓存少量合成遮光样本，两组用相同模型和训练步数，对比简单几何阴影与扩散阴影，按真实留出场景的人评和局部阴影残留选方向。

## ntire-2025-depth-mono

**NTIRE 镜面和透明表面高分辨率深度 · 2025 单目赛道**

- **成绩** Lavreniuk 第 1，δ<1.05 在 ToM 像素 87.67%、全像素 84.19%。 [原始报告，表 2、§5.2.2](https://openaccess.thecvf.com/content/CVPR2025W/NTIRE/papers/Ramirez_NTIRE_2025_Challenge_on_HR_Depth_from_Images_of_Specular_CVPRW_2025_paper.pdf)
- **机制** 用于生成深度伪标签时，透明物先和掩码混合，镜面则先做补全，使用修复后的视图辅助估深。
- **证据边界** 提交还联合两个深度模型并使用多个训练集和推理增强。组织者按透明或镜面像素及所有像素分别排序。
- **本地对照建议** 在训练外、已有深度真值的场景上，固定教师比较原图伪标签和经遮挡修复视图的伪标签。分材质、分边区测误差，先确认伪标签再花钱训练学生。

## ai-city-2024-mcpt

**AI City 多摄像头行人跟踪 · 2024 Track 1（在线提交）**

- **成绩** SJTU-Lenovo 获赛道官方冠军，公开 HOTA 表列第 2，67.2175。 [成绩来源](https://www.aicitychallenge.org/2024-challenge-winners/)
- **机制** 轨迹对每个镜头分别保存可见、遮挡或缺失状态，只在后两类状态中从多视角外观记忆查找重识别证据，与一致几何匹配合用。 [方案原文](https://openaccess.thecvf.com/content/CVPR2024W/AICity/papers/Xie_A_Robust_Online_Multi-Camera_People_Tracking_System_With_Geometric_Consistency_CVPRW_2024_paper.pdf)
- **证据边界** 组织者表的公开第一是离线法。作者表 1 在已经加特征库的系统上依次打开遮挡和缺失纠错，HOTA 54.6255 → 64.1062 → 67.2175。这个分步结果来自该比赛测试。
- **本地对照建议** 缓存检测、姿态和外观特征，保持在线因果顺序，比较几何匹配及状态触发融合。按重遮挡和普通路段统计 ID 变换和 HOTA。

## icdar-2023-indic-handwriting

**ICDAR Indic 手写文本识别 · 2023**

- **成绩** PERO 第 2，38 分，十种语言平均词识别率 87.53%。 [原始报告](https://cvit.iiit.ac.in/images/ConferencePapers/2023/icdar2033_tr.pdf)
- **机制** 每种文字分别训练视觉识别器和字符语言模型，用前缀束搜索合并二者。训练语言模型时以词型词表为输入。
- **证据边界** 官方总分由每种文字的词识别名次积分得到，PERO 的平均字符识别率 95.98% 略高于总冠军 95.94%。报告未在同一榜上单独测语言模型贡献。
- **本地对照建议** 缓存视觉模型输出，在按书写者留出的同一份验证集比较纯视觉解码与加入语言模型的束搜索，单列词典外词和低频文字的错误。

## chime8-2024-dasr-constrained

**CHiME-8 远场会议多人转写 · 2024 Task 1 受限语言模型赛道**

- **成绩** STCON sys1 第 1，测试 macro tcpWER 19.9%，DER 20.8%。 [成绩来源](https://www.chimechallenge.org/challenges/chime8/task1/results)
- **机制** 先用人工生成的房间脉冲响应训练分类器，再对真实训练录音打分。用得分较高的模拟响应所对应的房间参数，生成多通道混合训练样本。 [方案原文，§2.2](https://arxiv.org/pdf/2410.13411)
- **证据边界** 作者采用约 2500 小时模拟语音，并使用后端融合和多种分离模型。现有报告不能给响应筛选分配独立的榜分收益。
- **本地对照建议** 取同一组干净语音、噪声与混合音量，比较均匀抽样和按真实训练房间响应筛选的同样本量小训练。按从未用于筛选的真实房间评估 DER 及 tcpWER。

## chime8-2024-notsofar-mc

**CHiME-8 NOTSOFAR-1 会议转写 · 2024 Task 2 多通道赛道**

- **成绩** USTC-NERCSLIP sys1 第 1，eval tcpWER 10.8%。 [成绩来源](https://www.chimechallenge.org/challenges/chime8/task2/results)
- **机制** 联合训练说话人分段和分离，先用分段给出每人的活动时间，再把网络预测的时频掩码用于引导空间分离。 [方案原文](https://arxiv.org/pdf/2409.02041)
- **证据边界** 作者表 6 固定转写后端，在 Train-set-1 的 plaza 0 子集上比较了两种分离模型。由 CSS 加重叠检测换成 3 秒 JDS 后，tcpWER 从 25.14% 降到 20.62%。正式提交还有组合与后端改动。
- **本地对照建议** 固定会议切分和转写模型，从已缓存的说话人区间和分离结果比较固定分离与分段引导分离，在未见会议按重叠率给 tcpWER。

## dcase-2023-seld-av

**DCASE 真实场景声事件定位与检测 · 2023 Task 3 Track B 音视频**

- **成绩** Du_NERCSLIP_task3b_1 第 1，F-score@20° 63.6%，定位误差 11.3°。 [成绩来源](https://dcase.community/challenge2023/task-sound-event-localization-and-detection-evaluated-in-real-spatial-sound-scenes-results)
- **机制** 先由音频预测声源方向，再在匹配该事件类别的可见物体或人体关键点中找最近方向。仅有角度一致证据才修正。 [方案原文](https://dcase.community/documents/challenge2023/technical_reports/DCASE2023_Du_102_t3.pdf)
- **证据边界** 技术报告在 STARSS23 开发集的既有集成上再加决策融合，定位误差由 13.12° 降到 10.76°。这与官方隐藏集结果属于不同切分。
- **本地对照建议** 缓存声源方向和视频检测，在扣留房间按原音频方向及门控修正成对评分，单列可见映射类别及门控未触发样本。

## dcase-2023-text-audio-retrieval

**DCASE 文本检索音频 · 2023 Task 6b**

- **成绩** CP-JKU 第 1，独立评测 mAP@10 0.401。 [成绩来源](https://dcase.community/challenge2023/task-language-based-audio-retrieval-results)
- **机制** 用人写描述和训练音频的关键词生成多种改写，让相同音频与不同自然语言查询对齐。微调时随机替换一部分训练描述。 [方案原文](https://dcase.community/documents/challenge2023/technical_reports/DCASE2023_Primus_72_t6b.pdf)
- **证据边界** 作者表 2 的匹配单模型在开发测试由 0.3800 到 0.3856。0.401 来自八模型集成。最终榜评估集独立于提交重训使用的完整开发集。
- **本地对照建议** 保持同一音频编码和微调步数，对比原描述、无关键词释义和有关键词释义。验证按原始录音隔离，同一音频的所有描述留在同侧。

## icassp-2023-dns-headset

**ICASSP 深度噪声抑制 · 2023 Track 1 耳麦**

- **成绩** Team36 UnbeatableTencent 第 1，综合分 0.594。 [成绩来源](https://www.microsoft.com/en-us/research/academic-program/deep-noise-suppression-challenge-icassp-2023/results/)
- **机制** TEA-PSE 3.0 从不同 STFT 分辨率计算幅度、相位等训练损失，让优化同时看到多个时频尺度。系统用登记语音的说话人特征引导抑噪。 [方案原文](https://arxiv.org/pdf/2303.07704)
- **证据边界** 主办方耳麦盲测中总体听感 OVRL 从原声 1.22 提高到 2.71，词准确率从 0.843 变为 0.761。作者表 1 的代理指标对照中，多尺度损失让 PDNSMOS OVRL 从 3.603 到 3.618。榜分还含其它改动。
- **本地对照建议** 设同一组说话人和未见噪声，用固定网络及同训练步数比较单尺度和多尺度损失。同时测转写准确率与总体听感代理，只对可能翻转结论的样本补盲听。
