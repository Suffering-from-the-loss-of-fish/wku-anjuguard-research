"""Render-ready Chinese reports from immutable measured summaries (python-docx)."""
from pathlib import Path
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'delivery'
D1=json.loads((ROOT/'runs/d1/all_8_methods_summary.json').read_text())
D1={r['method']:r for r in D1 if r['split']=='exploratory_holdout'}
D2={r['policy']:r for r in [json.loads(x) for x in (ROOT/'runs/d2/test/summary.jsonl').read_text().splitlines()]}
NAMES={'A_original':'A 原始','A_fix':'A 修复','A_fix_sequence_adapter':'来源适配 辅助','B_frozen':'B 冻结特征','C_relation_quality':'C 关系与质量','C_no_relation':'C 去关系','C_no_abstention':'C 取消待确认','B_binary':'B 不拒判','A_fixed':'A 固定间隔','B_original':'B 当前门控','C_fix':'C 修复','C_tuned':'C 开发调参','D_candidate':'D 候选机制'}

def make():
    d=Document();s=d.sections[0];s.page_width=Inches(8.27);s.page_height=Inches(11.69)
    s.top_margin=s.bottom_margin=Inches(.65);s.left_margin=s.right_margin=Inches(.7)
    for name,size in [('Normal',10.5),('Title',21),('Subtitle',10),('Heading 1',15),('Heading 2',12)]:
        st=d.styles[name];st.font.name='Heiti SC';st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
        fonts=st.element.get_or_add_rPr().rFonts
        for attr in ('asciiTheme','eastAsiaTheme','hAnsiTheme','cstheme'):
            fonts.attrib.pop(qn('w:'+attr),None)
        fonts.set(qn('w:eastAsia'),'Heiti SC')
        for border in st.element.xpath('.//w:pBdr'):border.getparent().remove(border)
        st.paragraph_format.space_after=Pt(7);st.paragraph_format.line_spacing=1.15
    d.styles['Normal'].paragraph_format.widow_control=True
    p=s.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    r=p.add_run('AnjuGuard 公开数据最小预实验  |  ');r.font.size=Pt(8)
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');p._p.append(fld)
    return d

def p(d,text):d.add_paragraph(text)
def h(d,text):d.add_heading(text,level=1)
def page(d):d.add_page_break()
def table(d,headers,values,widths=None):
    t=d.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    if widths:
        for c,w in zip(t.columns,widths):c.width=Inches(w)
    for c,x in zip(t.rows[0].cells,headers):c.text=str(x)
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in values:
        for c,x in zip(t.add_row().cells,row):c.text=str(x)
    for i,row in enumerate(t.rows):
        for j,c in enumerate(row.cells):
            if widths:c.width=Inches(widths[j])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tc=c._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
            for edge in ('top','left','bottom','right'):
                e=OxmlElement('w:'+edge);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');b.append(e)
            tc.append(b);mar=OxmlElement('w:tcMar')
            for side in ('top','bottom','left','right'):
                e=OxmlElement('w:'+side);e.set(qn('w:w'),'80');e.set(qn('w:type'),'dxa');mar.append(e)
            tc.append(mar)
            if i==0:
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E8EEF3');tc.append(shade)
            for par in c.paragraphs:
                par.paragraph_format.space_after=Pt(0);par.paragraph_format.line_spacing=1.05
                if j>0:par.alignment=WD_ALIGN_PARAGRAPH.CENTER
                for r in par.runs:r.font.size=Pt(9);r.bold=(i==0)
    d.add_paragraph().paragraph_format.space_after=Pt(0)
    return t

def percent(x):return '不可计算' if x is None else f'{100*x:.1f}%'
def num(x):return '不可计算' if x is None else f'{x:.2f}'

def report():
    d=make();d.add_paragraph('AnjuGuard 两方向最小预实验报告','Title')
    d.add_paragraph('2026年11月1日美东  运行证据保存于2026年11月2日UTC  公开数据探索初测','Subtitle')
    p(d,'本轮已实现并运行两个方向：方向一使用真实照片与 DINOv2 冻结特征；方向二使用真实视频帧与本机 Qwen HTTP 推理。原 App 未修改，新增付费 API 支出为 0。结果支持继续核验方向一的强基线可行性，但两个候选机制都没有显示可靠的额外研究收益。')
    p(d,'方向一的强基线把留出 12 个同物对中的漏关联从 12 降至 3；C 去掉关系后结果不变。方向二 C 修复版减少请求，但 D 的上传量、等待和未知比例反而上升。独立人工复核尚未完成，真实风险效果、正式事件召回和质量非劣效均为未测。学术价值暂无法判断。')
    p(d,'本报告主表固定呈现初次冻结运行。另一次完整独立复跑用于验证一键入口，其新测时延、开发选择和留出结果单列保留，不替换初次主表。')
    h(d,'已执行范围')
    table(d,['项目','方向一','方向二'],[
      ['真实数据','UW RGB-D Scenes v1\n4 序列 64 图 315 框','ARKitScenes\n6 视频 481.400 秒 483 帧'],
      ['固定评价样本','48 对  各序列 6 同物 6 异物','250 个自动可见段\n不是已确认事件真值'],
      ['开发与留出','desk kitchen 各 16 图\nmeeting table 各 16 图','开发 136 帧 174 段\n留出 347 帧 76 段'],
      ['真实推理','DINOv2-small CPU float32','Qwen2.5-VL-3B MLX 4bit\n固定提示词 本机 HTTP'],
      ['分组局限','独立场地未验证\n序列可能共享同一实物','沿官方 Training/Validation\n3 个 visit 不等于 3 个家庭'],
      ['独立人工复核','0  发布方框与身份待复核','0  事件开始与结束待复核']], [1.2,2.82,2.82])
    h(d,'证据分层')
    p(d,'实际测得：本机模型输出、HTTP 延迟、运行失败、请求与上传字节。离线回放：按原始视频 PTS 推进，按已测请求耗时释放结果。合成验证：同图冲突、局部变化、晚到响应、429、超时、重试等机制。未测：手机、互联网、功耗、云费用收益、人类确认的风险识别效果。')
    p(d,'源码核查为 df281277215a1b55fd74dc8e43203e3954081976，工作区干净。实验置于 work/minipilot 的独立 codex/minipilot 分支；原源码和研究材料保持原位。没有授权云额度，也没有调用付费模型。')

    page(d);h(d,'方向一 关联方法与留出结果')
    p(d,'A 保留原来源条件、8 秒时间条件、IoU 阈值和贪心行为。公开照片没有 App source_id 或可靠拍摄时间，保持缺失，因此 A 无法跨帧关联。A_fix 只修同图、多对一等问题；它是初次结果后的补充工程审计，没有重调 B/C。另列来源序列适配辅助实验，不冒充原 App 行为。')
    p(d,'B 使用固定 DINOv2 ROI 特征、余弦相似度、带不匹配节点的一对一分配。C 加框外 ORB 背景对应、通过一致性检查的近似平面几何和图像质量。关系缺失不补造；不输入实例 ID、人工关系或屏幕左右真值。B/C 在开发上共同设定 80% 自动判定目标，离散样本实际均为 20/24。')
    methods=['A_original','A_fix','A_fix_sequence_adapter','B_frozen','C_relation_quality','C_no_relation','B_binary','C_no_abstention']
    table(d,['方法','误合并','漏合并','待确认','自动比例','已判错误率'],[[NAMES[m],D1[m]['false_merges'],D1[m]['missed_merges'],D1[m]['pending'],percent(D1[m]['automatic_fraction']),percent(D1[m]['decided_error_rate'])] for m in methods],[1.65,.65,.65,.65,1.05,1.5])
    p(d,'分母为 24 对，其中 12 同物、12 同类别不同实例。全部方法运行失败 0、缺失 0、结果完整率 100%。待确认不算正确；本次没有误合并，不代表相似实物误合并问题已被解决。开发 desk 的六个异物对为不同类别易负例，开发/留出难度并不完全一致。')
    h(d,'增益来自哪里')
    p(d,'A → A_fix 在真实照片上没有收益，因为来源条件没有触发。B 不拒判时解决 9/12 个原规则漏关联，但这同时反映 A 的输入适用范围限制。C 与去关系消融逐对相同，B 不拒判与 C 取消待确认也逐对相同；当前不能认定 C 提升了身份匹配能力。')
    p(d,'45 个图像对只有 1 对通过背景几何检查。C 已判错误率从 16.7% 到 10.5% 的变化伴随不同待确认集合，不是关系信息带来的证据。开发阈值生成的覆盖率曲线另存 CSV/PNG，不用测试曲线反选参数。')
    p(d,'初次集成运行 7.468 秒；特征阶段 4.997 秒（含加载、裁剪、质量、预处理、推理与保存），其中编码器 forward 4.244 秒。共享几何准备 0.681 秒。末端判定耗时不能充当完整方法耗时，未独立测每种方法端到端速度。')

    page(d);h(d,'方向二 固定模型与因果回放')
    p(d,'固定 Qwen2.5-VL-3B 4bit 权重、processor、温度 0、512 token 上限、提示词及 JSON 结构。任务仅为家具出现与位置判断，类别为 chair、table、sofa、cabinet、bed、shelf。两档图片来自同一时刻，长边 720/1280，JPEG 质量 82。MOV 第一视频流按真实 PTS 抽取约 1 Hz 候选，并同步纠正图像和框的旋转。')
    p(d,'A 每 6 秒固定 720；B 保留 H5 质量门控、dHash、冷却、退避与每视频 30 次上限。C_fix 修无效/不可用返回的去重与退避执行；C_tuned 仅开发选参，最后选回 C_fix 参数。D 加局部变化、答案过期检查和静默触发。服务单并发、超时 60 秒、指定可重试状态最多重试 1 次；视频结束仍在途的响应记未完成。')
    table(d,['留出方法','请求','2秒','5秒','10秒','20秒'],[[NAMES[m],D2[m]['logical_requests'],*[f'{round(D2[m]["proxy_recall_by_deadline"][str(t)]*76)}/76' for t in (2,5,10,20)]] for m in D2],[1.7,.7,1.0,1.0,1.0,1.0])
    p(d,'表中仅为派生可见性参考的及时匹配数，不是正式事件召回。模型类别与框须匹配，IoU≥0.3，结果须在起始时刻加截止时间之前且仍可见时返回。没有已批准的质量门槛，不能宣称质量非劣效。留出 chair 和 sofa 的事件分母为 0，相关召回不可计算；关键风险类别未定义、未测。')
    h(d,'工程收益与候选机制')
    p(d,'B → C_fix 请求 52→37，减少 28.8%；20 秒代理匹配 3→5 段，但仍很低。首个分歧来自 quality_usable=false 后的退避：B 在视频 41069042 的 77.001 秒继续发送，C_fix 等待。本组没有 duplicate 门控触发，不能把收益归因于哈希修复。C_tuned 与 C_fix 相同，开发调参没有额外收益。')
    p(d,'D 进一步降为 35 次请求，但 20 秒仅匹配 2/76，编码图片合计 4.14 MB，高于 C_fix 的 1.85 MB 和 A 的 2.52 MB；高分辨率请求使等待增加。D 的静默检查受质量、冷却和在途请求限制，不能作为回应时限保证。未运行密集高清参考；它即使运行也不能替代人工真值。')

    page(d);h(d,'方向二 失败 延迟与成本')
    table(d,['方法','无效输出','未完成','未知帧','过期帧','可用完成'],[[NAMES[m],D2[m]['request_status_counts']['invalid'],D2[m]['unfinished_at_video_end'],D2[m]['unknown_answer_ticks'],D2[m]['proxy_stale_answer_ticks'],f'{D2[m]["usable_completed_requests"]}/{D2[m]["logical_requests"]}'] for m in D2],[1.65,1,.9,.9,.9,1.05])
    p(d,'“未知帧/过期帧”按 347 个候选时刻计。D 未知 298/347，答案覆盖仅 14.1%；不能用过期帧更少证明答案更新更好。过期统计只针对先前匹配物体已结束；旧空答案漏新物体由事件匹配与未知统计体现。最新无效结果记未知。运行无网络错误或超时重试，相关边界由合成测试验证；D 有 2 次视频结束未完成。')
    table(d,['方法','请求结束\nP50/P95 秒','可用返回条件\nP50/P95 秒','调度 P95\n毫秒','JPEG MB'],[[NAMES[m],f'{num(D2[m]["recorded_e2e_p50_s"])}/{num(D2[m]["recorded_e2e_p95_s"])}',f'{num(D2[m]["usable_response_conditional_p50_s"])}/{num(D2[m]["usable_response_conditional_p95_s"])}',num(D2[m]['scheduler_p95_ms']),f'{D2[m]["encoded_image_bytes_all_logical_attempts"]/1e6:.2f}'] for m in D2],[1.4,1.6,1.65,1.1,.75])
    p(d,'请求结束延迟包括无效返回，不能解释为得到可用答案的等待。条件分位数只覆盖可用且在视频结束前完成的请求；所有方法完整请求集的可用答案 P50/P95 均不可计算。表中回放延迟采用原测 HTTP、原编码时长与当次调度开销，不采用缓存读取速度。')
    p(d,'正式开发 64 次真实 HTTP 加 64 次记录重放；正式留出 139 次真实 HTTP 加 74 次记录重放。另对开发前 20 个候选做禁缓存短片技术重复，共 11 次真实 HTTP、22.75 秒墙钟，仅 A 有 1 次可用返回。样本太小，不能据此声称等待改善。模型加载约 1.66 秒与前期技术探针单列保留。')
    p(d,'本地 API 支出始终为 0，云费用下降百分比不计算。各策略上传字节为其逻辑请求负载；实际新增传输与记录复用分开列在结果表。方向二强基线的质量水平尚不足以讨论“保质量降成本”。')
    h(d,'可追溯失败与标注局限')
    p(d,'方向一 meeting_small_1_p02、p05 在 B/C 都漏关联；table_1_p06 从 B 错误转为 C 待确认，去关系结果仍相同。方向二 A_fixed_41069042_000007_2 对应 PTS 6.014167 秒，真实输出框超出输入尺寸，被严格记为 invalid。HTML 可打开原图、上传图、原视频时间点和原始响应。')
    p(d,'人工尚未复核。技术抽查确认图像直立，但 41069042 的 bed 投影框会混入前景柜，表明派生框存在遮挡污染。14/483 帧缺参考已单列；“未匹配代理框”不得称为人工确认误报，正式误报率仍未测。')

    page(d);h(d,'复现 验证与后续证据')
    p(d,'实验目录为 /Users/wangkai/Documents/ChatGPT/温肯科研/work/minipilot。依赖锁在 requirements.lock，模型/提示词/源码哈希在 configs 与 runs/provenance.json。初次结果、冻结配置、逐样本输出、失败和前期探针均保留。A_fix 补充审计、后处理参考完整率与曲线均有独立记录，没有用测试结果修改 B/C 或调度策略。')
    table(d,['命令','行为'],[['./run.sh setup','安装隔离环境和固定依赖'],['./run.sh smoke','合成与单元流程验证 不作真实研究结论'],['./run.sh recompute','从交付记录重新评价 无新模型请求'],['./run.sh real','下载公开数据和权重 在新目录运行真实实验'],['./run.sh provenance','记录代码 权重 环境与版本']], [2.0,4.85])
    p(d,'已通过原规则等价、同图多实例、时间缺失、一对一冲突、真值置换不影响预测、同源划分、局部变化但哈希不变、晚到、质量拒绝、429、超时、重试、结束未完成及空分母/漏跑检查。正式调度日志审计无未来信息或重试违规，测试晚于开发冻结；逐项重算与原指标一致。日志中的模拟边界与真实失败分开保存。')
    p(d,'独立复跑中，开发选择的 C 间隔变为 3 秒；留出调参版为 45 次请求、20 秒代理匹配 2/76，而 C_fix 仍为 37 次、5/76。重新测量会影响时刻和选参，这个重复结果提示调参不稳定。算法没有据此修改；完整对照保存在预实验明细的复现对照文件。')
    h(d,'最小补充清单')
    p(d,'先双人独立复核现有 48 对身份与 250 段事件。复核者分别使用空白副本，先看原图/视频，填类别、候选框、同异物、首次足够可判定、可见结束、状态变化及是否关键类别；不先看算法答案。分歧再由第三人或共同回看裁决。补充复核.xlsx 已预填入口，不填写虚构人名和签名。')
    p(d,'补域数据最低为 3 个独立授权场地，每场地 2 布置×8 图，共 48 图；文件 S01_G01_P01.jpg，移动实物另建 G02。每场地 2 段 60–120 秒视频，共 6 段，文件 S01_V01.mov。覆盖线缆/箱子、同类相似物、远小目标、短暂出现、遮挡、重访及真实局部变化。S01 开发，S02/S03 留出；房间、相邻帧与裁剪不得跨组。')
    h(d,'给导师的建议')
    p(d,'建议先投入一轮小规模人工复核与困难配对，优先核验方向一的强基线和剩余失败；理由是任务可定义、已有真实身份标签和可运行基线，验证成本较低。暂不继续叠加关系复杂度。方向二先修固定模型的可用性、框定位和事件标注，再决定是否继续调度研究。这个优先顺序是资源安排建议，不是用户已选题、导师批准或学术创新结论。')
    p(d,'来源：UW 数据与许可 https://rgbd-dataset.cs.washington.edu/dataset.html；ARKitScenes 数据说明 https://github.com/apple-aiml-research/ARKitScenes/blob/main/DATA.md；DINOv2 https://github.com/facebookresearch/dinov2；Qwen MLX 模型 https://huggingface.co/mlx-community/Qwen2.5-VL-3B-Instruct-4bit。固定 revision、完整提示词、原许可和引用在 ATTRIBUTION.txt 与 configs 中。')
    OUT.mkdir(exist_ok=True);d.save(OUT/'预实验报告.docx')

def adviser():
    d=make();d.add_paragraph('AnjuGuard 两方向预实验导师结论','Title')
    d.add_paragraph('公开真实数据与本机免费模型初测  2026年11月1日美东','Subtitle')
    p(d,'本轮已完成代码、真实推理、因果回放与结果复算，API 新增支出 0；原 App 未修改。两方向的学术价值仍暂无法判断。建议下一轮优先核验方向一的困难配对，方向二先补齐固定模型能力与人工事件真值。')
    h(d,'方向一 强基线可行 关系增益未出现')
    p(d,'留出 24 对中，A 漏关联 12 个同物对；B 不拒判降为 3 个，解决 9/12。A 在公开照片缺少 App 来源信息时本就不触发，不能把全部差距当创新。B 与 C 实际自动判定比例为 75.0% 与 79.2%，已判错误率为 16.7% 与 10.5%。')
    p(d,'C 去掉关系后逐对结果不变，B 不拒判与 C 取消待确认也相同。45 图像对仅 1 对通过自动几何检查。当前证据支持冻结特征强基线，未支持关系机制额外收益；误合并 0 也不代表已解决相似实物问题。')
    h(d,'方向二 工程修复有效 候选策略未改善')
    table(d,['留出策略','逻辑请求','20秒代理匹配','JPEG MB'],[['B 当前门控',52,'3/76','2.52'],['C 修复与调参',37,'5/76','1.85'],['D 候选机制',35,'2/76','4.14']],[2.15,1.25,1.85,1.45])
    p(d,'52→37 的主要原因是不可用返回后的退避修复，开发调参没有再增益；独立复跑调参版为 45 次、2/76，进一步提示不稳定。D 上传更多、请求结束 P95 从 C 的 1.67 秒升为 3.82 秒，未知时刻 298/347，未完成 2 次。不能由减少请求宣称费用下降或质量非劣效。')
    h(d,'还缺什么与优先顺序')
    p(d,'现有 64 张照片和 6 段视频均为真实公开数据，但独立人工复核为 0。方向一独立场地未知；方向二派生框有遮挡污染，家具代理任务不等于风险事件。正式事件召回、关键风险类别、误报率、手机与云费用收益未测。')
    p(d,'先复核 48 对身份并补同类困难物体，必要时采 3 场地×2 布置×8 图；这一步更有望迅速判断强基线剩余缺口。方向二先复核 250 段事件并改善固定模型的有效输出，再谈调度。任何后续测试须先冻结参数与质量/回应标准。当前不预先宣布方向获胜，也不将修 bug 包装为研究创新。')
    d.save(OUT/'导师结论.docx')

if __name__=='__main__':report();adviser();print(OUT)
