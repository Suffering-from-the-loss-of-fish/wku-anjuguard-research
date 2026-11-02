# AnjuGuard 两方向最小预实验

本目录是独立实验工程，原 App 源码未修改。公开真实 RGB 数据、真实本机模型、按已测 HTTP 完成时间的离线因果回放、合成机制测试分开记录。API 新增支出 0 美元；电费、设备折旧和手机性能未测。独立人工复核尚未完成，正式事件召回、关键风险类别召回及质量非劣效均为“未测”。本轮用于选题筛查。

## 快速运行

本次验证环境为 Apple Silicon / macOS 15.8.1 / Python 3.12 / 24 GB 内存。方向二 MLX 依赖 Apple Silicon；不要在其他硬件上把替代模型结果混入本轮。FFmpeg 和 ffprobe 须在 PATH。首次真实运行约下载 8 GB（数据约 5.10 GB、模型约 3 GB）；建议至少留 20 GB 空间。数据及模型各自许可见 `ATTRIBUTION.txt`，仅在适用许可范围内使用。

```bash
cd '/Users/wangkai/Documents/ChatGPT/温肯科研/work/minipilot'
./run.sh setup
./run.sh smoke
./run.sh recompute
./run.sh real
```

解压后将 `cd` 改成实际解压目录。`setup` 安装 `requirements.lock` 固定版本，可用 `PILOT_PYTHON=/path/to/python3.12 ./run.sh setup` 指定解释器。没有模型文件也可运行 `smoke` 和 `recompute`；前者为明确的合成/单元验证，后者读取交付记录，不作新推理。`real` 自动下载并校验来源、重新准备数据，再在 `runs/reproductions/UTC时间/` 执行真实模型；独立 `run_status.json` 记录 completed 或 incomplete。模型或网络错误不会改用模拟结果。不要并行启动多个真实运行，以免争抢内存和改变计时环境。

`real` 不覆盖本轮结果；数据和权重下载后共用。服务仅监听 127.0.0.1 的空闲端口；每个请求上传实际 JPEG base64，单并发、无模型 KV/结果缓存。实验调度回放允许跨策略读取相同图片请求的原始记录，按原测延迟释放结果。汇总分别记录新 HTTP 请求与记录重放。缓存访问耗时不作为模型时延。初次模型加载、开发探针、独立无缓存短片测量与正式 dev/test 均单列。

## 数据与划分

方向一使用 UW RGB-D Scenes v1 四序列，各等间隔 16 张，共 64 张、315 个发布方候选框、48 个固定同/异物配对。开发 desk_1 与 kitchen_small_1；探索留出 meeting_small_1 与 table_1。该数据没有证明独立建筑划分，跨序列也可能出现相同实物；不能宣称独立场地泛化。desk 的六个负例为不同类别易负例；留出负例均为同类不同实例。真实拍摄时间与 App source_id 未提供，保持 null。

方向二使用 ARKitScenes 六段 MOV 的第一视频流。开发 40777060、40777063（Training，visit 369709）；留出 41069042、41069043（Validation，visit 381649）及 41159529、41159530（Validation，visit 381875）。共 481.400 秒、483 张约 1 Hz 实际 PTS 帧。开发 136 帧/174 个派生可见段，留出 347 帧/76 段。同 visit 保持同组；不同 visit 不等于已确认不同家庭。使用官方 Training/Validation 划分，家具扫描主要覆盖视野进入、遮挡、重访，没有线缆风险或真实物体状态变化真值。

原始 MOV 自带 Display Matrix -90 度：保留 raw 帧，并将模型图片和代理框一起转为直立方向。469/483 帧具备派生参考，14 帧明确缺失参考，不当成空场景。代理框来自官方 3D OBB 与稀疏深度支持；自动事件只是待复核草稿，first_sufficiently_judgable_s、关键类别、人工签名均为空。

## 方法和结果边界

方向一 A 保留当前代码原始来源、8 秒时间、IoU 与贪心行为；源方法快照保留原 MIT 许可并通过 AST/行为等价测试。A_fix 保留缺失来源边界，只修同图和多对一问题；在初次结果后补充，单列为工程审计。A_fix_sequence_adapter 是辅助输入适配，不称原 App 行为。B 用固定 DINOv2-small 特征、dummy 一对一分配与待确认；C 加自动框外 ORB 几何参照和质量加权。开发自动判定目标同为 80%，实际 20/24；测试同时报告实际比例。C_no_relation、C_no_abstention、B_binary 提供消融。所有算法都不读取真实实例 ID。

方向二 A 每 6 秒 720 长边；B 为 H5 当前质量门控和 dHash 选择策略的统一模型接口适配；C_fix 修可用性去重与有界执行，C_tuned 仅开发选参；D 加局部变化、答案 TTL、最大静默触发与两档清晰度。D 静默触发仍受质量、冷却、在途请求约束，不是回应时限保证。严格 JSON/坐标解析失败保留为 invalid，不当成“没有家具”。最新无效结果使评价状态未知，不模拟原 UI 继续显示旧答案。

每个策略只有当前/过去图像和当时已完成结果；每次请求超时 60 秒，指定 429/502/503/504 最多重试一次，超时不盲重试。结束后才返回的结果明确未完成。2/5/10/20 秒是探索曲线，没有获批准的质量阈值。proxy_unmatched_predictions 是未匹配自动框，不是人工确认误报；reference_audit 另外区分无参考帧。过期答案统计只覆盖先前匹配物体结束，旧空答案遗漏新物体通过事件召回和未知比例体现。

## 文件入口

- `configs/`：协议、D2 模型提示词合同及开发后冻结参数。
- `data/d1/algorithm/`：不含身份答案的输入；`evaluation/`：仅评价/开发校准答案。
- `data/d2/frames.jsonl`：真实帧/视频 PTS；`proxy_events.jsonl`：独立评价派生参考。
- `runs/d1/all_8_methods_*`：8 方法逐对输出、汇总、覆盖与复核页面。
- `runs/d1/initial_run/`：初次 7 方法和冻结配置；`supplement_audit.json`：补充 A_fix 变更说明。
- `runs/d2/dev/`、`test/`：每策略 decisions、requests、attempts、events、summary、failure_cases、reference_audit。失败、未完成与重试不剔除。
- `runs/model_server/requests.jsonl`：真实模型原文、错误、tokens 与单调时钟延迟；`server_config.json` 保存固定提示词和权重版本。
- `runs/d2/independent_http_probe/`：短开发片段无缓存 HTTP 测量，不能等同完整留出比较。
- `runs/d2_data/`：来源、几何、时钟匹配 QA 与事件复核页面；AI 技术核对不是人工复核。
- `runs/provenance.json`：代码、权重和环境哈希；`requirements.lock`：依赖锁。
- `delivery/`：两份 Word、两本 Excel、失败入口和交付校验。

包内保留逐样本/逐事件 CSV、JSONL、抽取 RGB 图片及模型请求原文；不重复打包数 GB 的原视频、下载归档或权重，下载器可恢复。工作区原文件保留。HTML 中“原视频”链接需要先下载，帧图可直接查看；没有本轮人工确认签名。浏览器自动化对 file URL 的安全策略阻止了交互视觉检查，已做静态结构、文件存在和图片可解码检查；文档与表格另有渲染检查。

## 下一步最小证据

先完成 `补充复核.xlsx` 的 48 对实例与 250 段事件双人独立复核。每人先用空白副本看图/视频，独立填写类别、框、同异物/可判定开始与可见结束，最后比较并由第三人或共同回看裁决；算法答案不要提前给复核者。明确授权场地、关键类别和回应时限后再冻结正式评测。

确需补足真实场地与线缆/箱子域：至少 3 个独立授权场地，各 2 布置×8 张=48 张；命名 `S01_G01_P01.jpg`，物体移动另建 G02。每场地 2 段 60–120 秒视频=6 段，命名 `S01_V01.mov`，覆盖相似实物、远小目标、短暂出现、遮挡、重访、局部真实变化。场地 S01 用开发，S02/S03 留出；同房间/相邻照片/裁剪始终同组。拍摄/事件日志记录真实时间、同意授权、首次足够判定及可见结束，不推测时间戳。

当前应先验证人类真值和固定模型任务能力，再研究调度质量收益。两方向学术价值均不能由本轮小样本证明；不得把修 bug、减少请求或待确认造成的选择变化包装为研究创新。

## 文档和表格检查

报告5页、导师结论1页均已渲染并逐页核对，258个正文/表格文本块与PDF提取完全一致。两本Excel共9个sheet、16个视图已渲染，汇总公式与JSON对账通过。原生Excel点击和HTML浏览器交互没有验证。文档渲染器需显式设置 bundled LibreOffice 的 FONTCONFIG_FILE 才能正确显示中文；实际记录在 runs/artifact_qa/document_qa.json。

完整 ./run.sh real 已实际通过（runs/one_key_verification/verification.json）。重复运行另有229次真实HTTP，未覆盖初次结果；重新开发选参的C变为3秒/哈希4，在留出45次请求、20秒代理匹配2/76。C_fix仍37次、5/76。该不稳定性已写入报告。保存记录的复算精确一致，不要求新测时延逐位相同。
