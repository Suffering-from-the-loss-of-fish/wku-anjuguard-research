方向一最小预实验 真实公开 RGB 数据初测

结论
已运行真实 DINOv2-small 冻结视觉模型，不是模拟特征。四段公开室内序列选取64张图片、315个发布方候选框，预先固定48对，其中开发24对、探索留出24对。严格独立场地关系和本轮独立人工复核尚未确认。结果是发布方标注初测，不能等同用户自采48–80张照片的正式预实验，也不能解释成风险识别准确率。

探索留出结果（24对，12同物、12同类不同物）
方法                         误合并  漏合并  待确认  失败  自动判定        已判定错误率
A_original                   0       12       0      0    24/24 100%      50.0%
A_fix                        0       12       0      0    24/24 100%      50.0%
A_fix_sequence_adapter       0       12       0      0    24/24 100%      50.0%
B_frozen                     0        3       6      0    18/24 75.0%     16.7%
C_relation_quality           0        2       5      0    19/24 79.2%     10.5%
C_no_relation                0        2       5      0    19/24 79.2%     10.5%
C_no_abstention              0        3       0      0    24/24 100%      12.5%
B_binary                     0        3       0      0    24/24 100%      12.5%

B/C在开发数据上共同目标为80%自动判定；24对的离散数量使两者实际均为20/24=83.3%。测试实际比例如上，不能比较错误率而省略覆盖率。所有方法结果完整率100%。待确认不是正确答案，运行失败也不会剔除。

强基线B在不拒判时把当前规则的12次漏合并降至3次，但A对缺少source_id的普通照片本就无法跨帧合并。该差距包含原功能适用范围限制，不能包装为学术创新。C与去关系消融逐对决定相同，B_binary和C_no_abstention逐对决定也相同。45个图像对只有1对通过自动背景几何检查。当前没有关系模块额外收益证据；C较低已判定错误率主要是质量加权后选择不同待确认样本，不能宣称身份关联能力已稳定提升。

来源及划分
数据为UW RGB-D Scenes v1真实拍摄序列，许可为非商业科研/教育用途。
https://rgbd-dataset.cs.washington.edu/dataset.html
https://rgbd-dataset.cs.washington.edu/dataset/rgbd-scenes/README.txt
开发：desk_1、kitchen_small_1。探索留出：meeting_small_1、table_1。
每序列从现有帧位置等间隔取16张，不按模型表现挑图。每序列固定6同物、6异物配对，优先同类别异物；desk无同类异物，因此该序列6个负例是易负例。序列之间可能有相同实物，也没有已核实的独立建筑/场地ID。此划分只能用于探索，不能声称严格跨场地泛化。
发布方的框来源于人工标记3D重建后投影，不等于本轮逐框双人确认。所有review状态保留pending。没有填写虚构的人名、复核签名或拍摄时间。帧序号保留，captured_at_ms为null，不根据不确定帧率补造秒数。

算法
A_original从AnjuGuard df281277的两段原方法生成便携快照，原始条件和贪心行为保留；category适配risk_code用于对象关联筛查。照片source_id保持缺失。因此本输入下A全部判不同。
A_fix保留A原source_id和时间条件，修同图合并及多对一；不补造共同来源。它是初次结果之后新增的补充工程审计，未改动B/C参数或预测。
A_fix_sequence_adapter是另列辅助实验：使用公开数据真实sequence_id连接同视频来源并执行一对一IoU匹配；不是原客户端行为。缺失时间仍缺失。
B_frozen采用facebook/dinov2-small，revision ed25f3a31f01632728cabb09d1542f84ab7b0056；ROI CLS向量L2归一化，类别兼容限制，Hungarian加dummy节点允许不匹配。参数只用开发配对选择。B的余量拒判同样存在，不让C独享拒判优势。
C_relation_quality加入框外ORB自动背景对应、通过检查的近似平面单应性参照一致性及清晰度/大小/曝光质量。关系无法验证时按缺失处理。它不是稳定三维关系，也没有使用人工左右、深度、位姿或实例真值。
C_no_relation去掉参照分数，保留质量；C_no_abstention取消待确认；B_binary提供无待确认的强基线对照。

数据接口与防泄漏
data/d1/algorithm/frames.jsonl：图像路径、帧ID、真实序列/帧编号、尺寸、缺失时间及source_id。
data/d1/algorithm/observations.jsonl：观测ID、frame_id、category、零基半开bbox_xyxy及候选来源。
data/d1/algorithm/queries.jsonl：评价配对ID和两端观测引用，无身份答案。
data/d1/evaluation/labels.jsonl、pairs.jsonl：身份/同异物真值，只有校准开发标签和最后评测阶段读取。
预测模块不读取真值文件；19项测试包括原源码方法等价、dummy匹配、同图隔离、失败保留及真实预测真值字段置换不改变结果。

一键复现
在本实验目录执行：
  .venv/bin/python pilot/d1_reproduce.py
已有下载文件时可以完全离线：
  .venv/bin/python pilot/d1_reproduce.py --offline
方向一可单独安装torch、transformers、scipy、numpy、Pillow和OpenCV后使用Python；整份requirements.lock包含仅适用Apple Silicon的MLX，不能直接用于Windows/Linux。使用CPU float32、torch线程4。入口会重新运行真实模型，产物写入runs/d1/reproduced_UTC时间，不覆盖本次初始结果。首次需要联网下载四个数据包约287MB和模型约88MB；没有付费API。
分步命令：python pilot/d1_download.py；python pilot/d1_data.py；python pilot/d1_run.py；python pilot/d1_supplement.py。
单独测试：python -m unittest discover -s tests -p 'test_d1*.py' -v。

结果文件
以runs/d1/all_8_methods_summary.json/.csv和all_8_methods_per_pair.jsonl/.csv为当前8方法完整表。all_8_methods_coverage.csv单列覆盖与错误率。all_8_methods_review.html包含48对图片与红框，先看图片，再展开发布方答案/算法结果。
initial_run/、per_pair_results.jsonl和frozen_config.json保留初次7方法原始输出与冻结配置。supplement_audit.json记录补充A_fix、源码快照封装及当前代码哈希；没有重调B/C。data/d1/download_manifest.json保留下载URL、字节数和SHA；features.npz、quality.jsonl、frame_pair_outputs.jsonl保存原始特征、质量与自动参照输出。

运行与费用口径
初次集成运行7.468秒；特征阶段4.997秒（含模型加载、裁剪、质量、预处理、真实forward及保存）；其中模型forward4.244秒、预处理0.321秒。45图像对共享几何与匹配准备0.681秒。各方法末端decide耗时不是整条方法耗时，不用于宣称端到端提速。quality单项没有独立计时。详见performance_accounting.json。
API调用0，API收费0美元。未测电费、真机功耗或手机运行速度。

交付检查和已知限制
HTML结构已解析，48篇配对、96个图像链接全部存在并可解码。浏览器工具拒绝file协议，未绕过；因此浏览器视觉/交互QA尚未验证。原始64张PNG及CSV/JSON可读取。19项测试通过。一次测试的过严1e-12数值断言遇到JSON中float32转float64的6.7e-10舍入差异，改用1e-7误差容限，并保持所有决定严格相同、真值置换前后输出逐字段一致；没有改变模型或算法结果。

下一证据
逐对独立人工复核，确认框、实例身份与困难类型；获取真正独立场地和线缆/箱子照片补足域差异；扩大同类相似实物对照。当前方向一已看到强基线可行，C的研究增量暂未显示，不能给论文有效性结论。
