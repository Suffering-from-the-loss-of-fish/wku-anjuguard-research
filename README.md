# 温肯科研 · AnjuGuard

用于团队协作的项目仓库，包含现有 App 源码、科研方案、两方向申请稿、最小预实验代码和已保存的实验记录。研究仍处于选题筛查阶段；导师批准、正式立项、独立人工复核和正式风险效果尚未完成。以 [项目总览](项目材料/05_项目总览.txt) 的最新记录为准。

## 从这里开始

- [方向选择与下一步](项目材料/方向选择与下一步.docx)：通俗比较、当前建议和后续行动。
- [导师结论](项目材料/导师结论.docx)、[预实验报告](项目材料/预实验报告.docx)：已测结果及证据边界。
- [方向一申请书](项目材料/方向一申请书.docx)、[方向二申请书](项目材料/方向二申请书.docx)：供导师比较的讨论稿。
- [预实验结果](项目材料/预实验结果.xlsx)、[补充复核](项目材料/补充复核.xlsx)、[失败案例](项目材料/失败案例.html)：结果与人工复核入口。

## 目录

| 目录 | 内容 |
|---|---|
| `AnjuGuard/` | 现有 React/Web、FastAPI、Swift/iOS 应用的完整源码快照与原许可证 |
| `项目材料/` | 桌面交付的研究文档、表格、失败案例和实验明细；仓库副本的链接已改为相对路径 |
| `work/minipilot/` | 两方向独立预实验、配置、依赖锁、抽取图像、原始模型响应、逐条结果与复跑记录 |
| `work/research-package/` 等 | 研究与申请材料的生成脚本、源文件和既有检查记录 |
| `work/repository-setup/` | 本次仓库整理的来源、文件清单与链接检查记录 |
| `scripts/stage_repository.py` | 同步本机工作区到父仓库索引，避免把嵌套仓库提交为空目录 |

## 拉取与使用

```bash
git clone https://github.com/Suffering-from-the-loss-of-fish/wku-anjuguard-research.git
cd wku-anjuguard-research
```

仓库已公开，任何人都可以查看、下载或克隆，无需邀请即可阅读。向本仓库推送修改仍需仓库所有者授权。源码以普通文件保存，不需要 `--recurse-submodules`。

Word/Excel 建议下载后打开；HTML 请在本机打开。表格中的相对链接以所在文件夹为基准，移动单个文件可能使链接失效，应保留整个仓库结构。原始视频链接在运行下载步骤后才可用。原Word/Excel交付未改写，仓库副本只修复链接，不改研究数值或格式。

App 启动说明见 [AnjuGuard/README.md](AnjuGuard/README.md)。预实验说明见 [work/minipilot/README.md](work/minipilot/README.md)：

```bash
cd work/minipilot
./run.sh setup
./run.sh smoke
./run.sh recompute
# 需要重新下载数据/模型并重新推理时：
./run.sh real
```

`recompute` 只复算已保存记录；`real` 才是新一轮真实模型运行。方向二依赖 Apple Silicon/MLX。不要把此次上传和文件完整性检查称为新的模型、真机或人工复核实验。历史文件中的 `/Users/...`、本地分支及原提交哈希是原运行记录；新机器按实际目录使用，原始证据不为适配路径而改写。

## 大文件与许可证

本仓库保存源码、文档、抽取图像及实测证据；不提交虚拟环境、依赖缓存、凭据、本机聊天同步状态、可重新下载的原始视频/归档/稀疏数据以及模型权重。恢复下载的代码、数据来源、模型固定 revision 和许可证保留在预实验目录。唯一例外是 App 本身已有的 Core ML 模型，作为现有应用资产保留。

原桌面 `预实验代码.zip`（约 160 MB）作为 [Releases](https://github.com/Suffering-from-the-loss-of-fish/wku-anjuguard-research/releases) 附件保存，避免超过普通 Git 单文件限制。ZIP 是原始交付归档，内部仍保留历史本机路径；协作优先使用本仓库中的文件。

AnjuGuard 原许可证见 [LICENSE](AnjuGuard/LICENSE) 和 [THIRD_PARTY_NOTICES](AnjuGuard/THIRD_PARTY_NOTICES.md)。数据和模型许可见 [ATTRIBUTION](work/minipilot/ATTRIBUTION.txt) 及各数据目录的许可文件，第三方许可独立适用；本仓库没有把研究材料或第三方数据统一授予新开源许可证。

## 后续更新

用户已授权后续项目文件在完成检查后直接同步到本仓库。助手每次交付结束时，将新增或修改的桌面材料更新到 `项目材料/`，维护相对链接，并提交、推送及核对远端结果；无需逐次确认。每小时后台同步已于2026-11-02按用户要求停止；新任务按需读取项目上下文，交付后的GitHub上传保留。

只更新源文件实际变化的材料，不整目录覆盖已有的相对链接副本。本机收据 `work/sync/github.json` 记录源文件、仓库副本和已发布提交，且不上传。先获取远端状态并处理并行修改；仅提交已经完成并检查的文件，不包含其他任务的未完成内容，不强制推送。

以下脚本只整理父仓库索引，不复制桌面文件。它保留两个原嵌套仓库，不改它们的提交、远端或分支：

```bash
python3 scripts/stage_repository.py --stage
git diff --cached --stat
git commit -m "Update research materials"
git push
```

协作者克隆后可以正常使用 Git，也可使用同一脚本纳入实验目录默认忽略的新增结果。脚本会扫描整个工作区，提交前需要核对暂存清单，并保留未完成的并行工作。大文件、模型与原视频等仍遵守上面的归档范围；新的超限交付使用版本化 Release 附件。

“直接同步”由助手在交付时完成 `commit`/`push`，不依赖用户再提醒，也不会把每次编辑中的临时文件即时上传。推送失败会保留本地成果并报告待补传状态；成功以远端核验为准。其他成员通过 `git pull` 获取更新。
