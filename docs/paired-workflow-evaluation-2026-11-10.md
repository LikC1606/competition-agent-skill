# 新旧工作流成对实验：收尾状态

用户已授权：2 个任务 × 新旧 2 版 × 3 次独立重复，共 12 次模型运行，每次最多 30 分钟。随后用户要求北京时间 2026-11-10 22:59 前收尾，并明确不启动新的长任务。本轮据此停止在准备阶段；没有启动任何正式模型实验，也没有自动安排后续运行。

## 已完成并验证

- Max-Cut：固定 Stanford Gset 开发集 G1/G6/G11，确认集 G2/G7/G12；实现下载哈希核对、八起点局部搜索基线、受限执行、独立 cut 重算与冻结确认。10 项测试通过。seed 17 的开发总 cut 为 13817，确认总 cut 为 13609；两者图集不同，不能直接比较高低。
- Energy：基于 UCI Appliances Energy Prediction 构造下一 10 分钟预测任务；固定 3 个时间前向折与 24 小时间隔，保存 OOF、训练证据和冻结模型，确认只做推理。8 项测试通过。seed 11 的 Ridge 基线开发 RMSE 为 67.01006472918493 Wh，冻结确认 RMSE 为 61.18600900738106 Wh。
- 固定 CLI launcher：固定 gpt-6-astra / max / my_codex、CPU 与线程设置；独立 CODEX_HOME、bubblewrap 挂载隔离、禁用 shell 网络/web/apps。9 项测试通过，包括真实 bubblewrap 读写边界和宿主进程组清理。
- 两个任务的结果均已被旧版 `80331a1` 与当前新版 archive 接收。上述测试结果来自各模块完成时的实际验证；不是模型效果实验。
- 真实 Codex CLI 的隔离 version/exec help/resume help 检查通过。真实 Codex 内层 sandbox 的本地探针尚未完成，不能据此声称端到端模型运行可用。

代码位于 [benchmarks/paired](../benchmarks/paired)。数据来源与许可见 [Max-Cut 说明](../benchmarks/paired/tasks/maxcut_sources.md)及 [Energy 说明](../benchmarks/paired/tasks/energy-sources.md)。Gset 原始下载数据未提交到仓库。

## 保存的草稿与未完成事项

[run.py](../benchmarks/paired/run.py) 已保存准备器草稿，包含版本快照、任务复制、12 个 job 定义、最小 provider 配置、基线入档与原生 campaign 命令构造。**它尚未完成集成验证，不是可直接执行整轮实验的完成版。** `run` / `finalize` 明确抛出 `NotImplementedError`；本轮也未执行 `prepare`。

仍缺：可信候选选择/冻结模块及测试、成对调度与恢复集成、真实内层 sandbox 验证、端到端离线 smoke、正式冻结协议、全部 12 次模型运行、实际结果分析。候选选择模块和实验 README 的子代理在落盘前收到 provider 503 错误，未产生相应文件。不要把此前接口讨论视为实现。

拟定协议为 seeds 11/29/47、六对依次进行、每对两臂同时运行并轮换 CPU；模型随机种子没有可用控制接口，只能称任务种子匹配的独立重复。基线准备和冻结后确认计时单列；选择经核验且比较合同匹配的最佳开发结果，同分优先基线/最早结果；失败不剔除。Energy 使用相同训练适配器，因此只能比较整体工作流，不能单独归因于 P2a。两个任务都是公开数据，不能保证模型没有既往接触。不得混合平均两个任务的原始分数。

## 已有产物与恢复入口

- 先前重构验证：`/home/lzh/workspace/competition-agent-validation/refactor-20261110`；原有 591 项测试通过记录与源码快照保留。
- Max-Cut：`/tmp/competition-paired-eval-20261110/maxcut/prepared`、`smoke-report.json`。
- Energy：`/tmp/competition-paired-eval-20261110/energy/prepared-final`、`final-validation.json`。
- 临时 ML 环境：`/tmp/competition-skill-refactor-20261110/ml-env/bin/python`。
- 计划正式实验目录 `/home/lzh/workspace/competition-agent-validation/paired-20261110` 尚未创建。恢复时先检查临时产物仍在，再补齐上述未完成项；不要直接开始付费模型调用。

本轮没有提交 git commit、全局安装 skill、平台提交或后台正式实验。保留仓库既有未提交改动。停止后不自动开启下一轮工作。
