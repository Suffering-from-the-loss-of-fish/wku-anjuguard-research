from pathlib import Path
import json
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

OUT = Path('/Users/wangkai/Desktop/温肯科研')
BASE = Path(__file__).resolve().parent

def runstyle(r, size=None, bold=False, color='000000'):
    r.font.name = 'Arial'
    if size is not None: r.font.size = Pt(size)
    r.bold = bold
    r.font.color.rgb = RGBColor.from_string(color)
    f = r._element.get_or_add_rPr().get_or_add_rFonts()
    for key, value in [('ascii','Arial'),('hAnsi','Arial'),('eastAsia','Songti SC')]:
        f.set(qn('w:'+key), value)
    for k in list(f.attrib):
        if 'theme' in k.lower(): del f.attrib[k]

def p(d, text='', style=None, size=None, bold=False, after=None):
    a=d.add_paragraph(style=style)
    runstyle(a.add_run(text),size,bold)
    if after is not None: a.paragraph_format.space_after=Pt(after)
    return a

def head(d,text,level=1,newpage=False):
    a=p(d,text,'Heading '+str(level),bold=True)
    if newpage: a.paragraph_format.page_break_before=True
    return a

def setup(title, short=False):
    d=Document(); s=d.sections[0]
    s.page_width=Cm(21);s.page_height=Cm(29.7)
    s.left_margin=Cm(2);s.right_margin=Cm(2)
    s.top_margin=Cm(1.6 if short else 1.7);s.bottom_margin=Cm(1.6 if short else 1.7)
    s.footer_distance=Cm(.7)
    for el in list(d.styles.element.iter()):
        if el.tag==qn('w:pBdr'): el.getparent().remove(el)
        if el.tag==qn('w:rFonts'):
            for a in list(el.attrib):
                if 'theme' in a.lower():del el.attrib[a]
    for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','List Bullet','List Number']:
        st=d.styles[name];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0)
        st._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Songti SC')
    n=d.styles['Normal'];n.font.size=Pt(10.5 if short else 11)
    n.paragraph_format.line_spacing=1.15 if short else Pt(16)
    n.paragraph_format.space_after=Pt(4 if short else 6)
    for name,size,before,after in [('Title',20 if short else 22,0,6),('Subtitle',9,0,9),('Heading 1',12 if short else 16,7 if short else 9,4 if short else 7),('Heading 2',11.5,7,4)]:
        st=d.styles[name];st.font.size=Pt(size);st.font.bold=name!='Subtitle';st.font.italic=False
        st.paragraph_format.space_before=Pt(before);st.paragraph_format.space_after=Pt(after)
        st.paragraph_format.keep_with_next=True;st.paragraph_format.line_spacing=1.08
    d.styles['Title'].paragraph_format.space_before=Pt(0)
    for name in ['List Bullet','List Number']:
        st=d.styles[name];st.font.size=Pt(10.5);st.paragraph_format.line_spacing=1.15;st.paragraph_format.space_after=Pt(4)
    f=s.footer.paragraphs[0];f.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    runstyle(f.add_run('温肯科研  方向一  |  '),8.5,color='555555')
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');f._p.append(fld)
    d.core_properties.title=title;d.core_properties.author='';d.core_properties.subject='方向一的选题与小规模可行性实验'
    p(d,title,'Title',bold=True)
    return d

def table(d, headers, rows, widths, size=10):
    t=d.add_table(rows=1,cols=len(headers));t.autofit=False;t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for col,w in zip(t.columns,widths):col.width=Cm(w)
    for i,values in enumerate([headers]+rows):
        row=t.rows[0] if i==0 else t.add_row()
        pr=row._tr.get_or_add_trPr();no=OxmlElement('w:cantSplit');pr.append(no)
        if i==0:
            repeat=OxmlElement('w:tblHeader');pr.append(repeat)
        for j,(cell,value) in enumerate(zip(row.cells,values)):
            cell.width=Cm(widths[j]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp=cell._tc.get_or_add_tcPr();bd=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'4');x.set(qn('w:color'),'D9D9D9');bd.append(x)
            cp.append(bd);mar=OxmlElement('w:tcMar')
            for edge,v in [('top',95),('bottom',95),('left',105),('right',105)]:
                x=OxmlElement('w:'+edge);x.set(qn('w:w'),str(v));x.set(qn('w:type'),'dxa');mar.append(x)
            cp.append(mar);sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'244A63' if i==0 else ('F2F5F7' if i%2 else 'FFFFFF'));cp.append(sh)
            a=cell.paragraphs[0];a.paragraph_format.space_after=Pt(0);a.paragraph_format.line_spacing=Pt(14)
            if j==0 and widths[j]<2:a.alignment=WD_ALIGN_PARAGRAPH.CENTER
            runstyle(a.add_run(value),size,i==0,'FFFFFF' if i==0 else '000000')
    p(d,'',size=3,after=0)
    return t

def link(d,label,url):
    a=d.add_paragraph();a.paragraph_format.space_after=Pt(3)
    h=OxmlElement('w:hyperlink');h.set(qn('r:id'),a.part.relate_to(url,RT.HYPERLINK,is_external=True))
    r=OxmlElement('w:r');pr=OxmlElement('w:rPr')
    f=OxmlElement('w:rFonts');f.set(qn('w:eastAsia'),'Songti SC');f.set(qn('w:ascii'),'Arial');pr.append(f)
    c=OxmlElement('w:color');c.set(qn('w:val'),'1F4E79');pr.append(c)
    z=OxmlElement('w:sz');z.set(qn('w:val'),'18');pr.append(z)
    r.append(pr);txt=OxmlElement('w:t');txt.text=label;r.append(txt);h.append(r);a._p.append(h)

def make_brief():
    d=setup('方向一 导师选题单',True)
    p(d,'温肯科研  |  讨论稿  |  2026年10月30日','Subtitle')
    p(d,'拟题  面向室内移动巡检的跨视角问题关联研究',size=12,bold=True,after=6)
    p(d,'我们想先做一个两周小实验：用普通手机拍同一空间，看看能否更准确地认出不同照片中的同一个物体，再判断是否值得发展成正式课题。')
    head(d,'研究什么')
    p(d,'同一根电线从三个角度拍摄，应该关联为同一个物体；两根长得很像的电线，又应该分开。先研究“物体是否认对”，以后再扩展到“是否属于同一个问题”，应用可以是家庭、办公室或室内巡检。')
    head(d,'我们已有的基础')
    p(d,'已有 AnjuGuard App 的照片采集、识别和报告流程。当前代码主要按类别、来源、时间和画面中的框位置做合并；换角度后的实际错误频率还需要测量。App 基于 RASSAR 二次开发，新增研究贡献要单独说明。')
    head(d,'准备怎样做')
    p(d,'先用3至5个获授权空间，每个空间拍两组固定布置、每组8张，共48至80张照片。比较现有规则、只看外观的简单方法，以及加入周围参照物关系并允许“待确认”的方法。所有方法看同样的照片与目标框，人工答案只用于评测。')
    head(d,'可能值得研究的改进')
    p(d,'检验相似物体、遮挡和视角变化出现时，周围关系信息能否减少认错；信息不足时，系统能否合理地暂缓合并。已有多视角关联研究，创新性需要进一步对照文献和强基线，不能只凭接入模块判断。')
    head(d,'两周后交什么')
    p(d,'一小批授权照片与标注、三种方法的对比表、失败案例，以及继续或调整选题的理由。若小试有效，后续为 App 增加稳定物体与问题编号、多视角证据卡和人工合并拆分入口。')
    head(d,'希望老师帮助确认')
    p(d,'请老师确认研究范围与已有工作的差异，并一起确定采集空间、复核人员、每周投入、设备与调用预算，以及学校申请时间。普通手机可先做小试；深度设备和训练模型暂不作为起步前提。')
    p(d,'当前阶段：已选择方向一准备本轮材料；导师、正式立项和实验结果仍待确认。CCF A/B 是后续目标，具体会议随贡献和证据确定。',size=9.5,after=3)
    p(d,'讨论记录：________________________________________________________________',size=10,after=0)
    f=OUT/'06_导师选题单.docx';d.save(f);return f

def make_plan():
    d=setup('方向一 两周实验计划')
    p(d,'温肯科研  |  10个工作日安排  |  2026年10月30日','Subtitle')
    head(d,'第一部分 先把小实验做清楚')
    p(d,'两周结束时，要回答：换角度、遮挡或出现相似物体后，现有方法会不会认错？简单方法能解决多少？我们增加的机制还有没有值得继续研究的作用？本计划用于选题筛查，尚未开始采集或运行实验。')
    head(d,'本轮的范围',2)
    p(d,'先做普通彩色照片中的物体关联。选择已有线缆、箱子等容易核对的静态物体，不依赖长者招募。先不研究“缺少扶手”等需要完整观察才能判断的任务，也不做跨天整改复查、三维建图或基础模型训练。')
    p(d,'建议3至5个空间，每空间2组静态布置，每组8张，共48至80张。每组选择2至3个对象，包含外观相似的不同实物。一组内物体保持不动；改变摆放后另建布置组。这个数量用于试流程和找失败案例，不代表正式论文所需规模。')
    head(d,'比较三种方法',2)
    table(d,['方法','怎样做','本轮要看什么'],[
        ['A 现有规则','保留当前代码按类别、来源、时间和二维框合并的行为；单独记录明显实现问题。','留下真实起点；不能只靠打败旧规则判断创新。'],
        ['B 简单强基线','使用冻结的图像特征模型比较目标外观，再做一对一匹配；允许“不匹配”。阈值只在开发空间选择。','检验现成方法已经能解决多少问题。'],
        ['C 候选方法','在B上增加自动提取的参照物关系和图像质量信息；不够确定时输出“待确认”。','检验新增信息是否有用，及其额外成本。']
    ],[2.6,8.6,5.8],9.9)
    p(d,'B是本轮最低强对照，不代表最先进方法。阅读 ConceptGraphs 等相关工作，把输入条件相同且可运行的更强方法列入后续对照。A保留真实来源与时间，不为提高合并率伪造元数据。',size=10)
    head(d,'开始前要落实的事情',2)
    p(d,'确认能使用的空间和拍摄授权；确定至少一人采集、一人独立复核；写下每天可投入时间和模型调用预算。可由同一人兼任实现与采集，但正式计分前需要第二人核对答案。若条件尚未落实，先完成规则与小样例，实验日程顺延。')
    p(d,'预计团队合计约24至36人时，含整理和复核；这是排期估计。第2天用一个空间试算成本，超出可投入时间就缩小样本或延长，不跳过测试留出与复核。',size=10)

    head(d,'第二部分 两周每天做什么',newpage=True)
    p(d,'从具备采集与运行条件的那天算第1天。下面按10个工作日安排，具体日期由团队填入；不预设导师、设备或数据已经到位。')
    table(d,['日期','主要任务','当天留下什么'],[
        ['第1天','和导师或团队确认问题、资源与分工；读现有代码和直接相关工作；确定方法版本。','范围说明；资源清单；现有方法与拟新增部分。'],
        ['第2天','用一个开发空间试拍、试标；记录8张照片的采集和标注耗时；检查A/B能否运行。','小样例；预计总工作量；可执行的最小B方案。'],
        ['第3天','登记场地、房间、授权与分组；把所有空间预先分为开发和测试。按固定清单采集。','照片文件；场景登记和照片登记；固定分组。'],
        ['第4天','完成剩余采集；标出每张图中的目标、框、真实物体编号与可见性。','目标标注初稿；漏拍和画质问题清单。'],
        ['第5天','两人独立判断预定配对；分歧裁决或保留无法确定；锁定测试输入和答案。','已复核配对真值；不可评测项；第一周检查。'],
        ['第6天','在开发空间运行A/B；修复影响公平比较的明显代码问题并留版本；确定B参数。','A/B开发结果；修复记录；统一输入与输出格式。'],
        ['第7天','完成C的最小版本；记录关系信息如何自动获得。用开发数据确定参数。','可运行C；关系提取规则；耗时与调用记录。'],
        ['第8天','冻结模型、参数和测试清单；A/B/C处理同一批测试配对；失败或漏跑必须保留。','三种方法逐配对结果；版本与配置记录。'],
        ['第9天','按空间和条件检查错误；在同样自动判定比例下比较B/C；检查新增模块的作用。','对比表；错误样例；代价和待确认数量。'],
        ['第10天','写一页小试结论并和导师讨论，决定继续、缩小范围或调整方向。','数据与标注包；结果表；失败案例；下一阶段建议。']
    ],[1.65,8.5,6.85],9.8)
    head(d,'遇到卡点怎样调整',2)
    p(d,'拿不到授权空间：先完成登记表和离线样例，不对真实场景效果下结论。B或C跑不起来：记录原因，优先补齐可复现基线，不用人工猜测冒充算法输出。关系信息只能人工提供：把它单列为辅助上限实验，不能当作C的正式结果。')
    p(d,'第5天若数据与复核尚未完成，先解决这个问题再进入测试。测试结果看过后如需改参数，应使用新的留出空间；旧测试结果只用于探索。',size=10)

    head(d,'第三部分 怎样拍 怎样标',newpage=True)
    head(d,'一次采集的顺序',2)
    p(d,'先填“场景登记”，用匿名编号代替地址。同一家庭或办公室算一个场地组，其房间和布置全部放在开发或测试同一侧。建议至少3个独立场地，1至2个用于开发、至少2个留出测试；只有一个场地时只做流程演练，不声称跨场地有效。')
    p(d,'每空间2组，每组8张：正面、左侧、右侧、近景、远景、部分遮挡、近重复、离开后重访。每张都应尽量保留可辨认的目标和固定参照物。只改变拍摄位置或安全的遮挡条件，不为测试制造通行危险。')
    p(d,'保留原图与拍摄顺序，补拍也登记。记录照片ID、布置组、视角、画质、拍摄时间和来源。不要根据算法表现删难例；确实不可用的照片说明原因。避开人脸、证件和私密信息，云端处理与公开发布分别确认授权。')
    head(d,'编号和真值怎样理解',2)
    table(d,['字段','大白话解释','虚构示例'],[
        ['观察ID','某张照片里某个目标的一次出现；换照片就换观察ID。','OBS001和OBS008是两次观察。'],
        ['真实对象ID','现实中的同一个实物，换角度仍使用同一个编号。','两次观察都指向OBJ001。'],
        ['问题ID','某实物在某区域、某布置下的具体问题；首轮只记录，不作为主指标。','同一线缆换到另一通道，对象ID不变，问题ID新建。'],
        ['目标框','图像中能看到的目标范围，填写左上角x1、y1与右下角x2、y2。','坐标均为0至1；x1<x2、y1<y2。']
    ],[2.8,8.4,5.8],10)
    p(d,'框按原图尺寸归一化：横坐标除以图像宽度，纵坐标除以高度。部分遮挡只框可见部分，旁边记“部分可见”；完全看不见不猜框，身份无法判断时保留该状态。所有方法使用同一份经核验候选框，这只是在隔离测试关联模块，不代表检测能力已经验证。',size=10)
    head(d,'固定配对和人工复核',2)
    p(d,'每空间先选约12个跨照片配对，目标为6对同一实物、6对不同实物，覆盖正常、遮挡、相似干扰与重访。清单在看方法结果前固定；数量不足如实记录。无法确认的配对单列，不强行补成“同一”或“不同”。该配对比例是试验设计，不代表日常使用中的错误发生率。')
    p(d,'两人先独立写答案，再裁决分歧；仍无法确定的记录不计分。同一配对不因交换顺序重复计算。人工ID和关系真值只供评测。C的关系应围绕固定参照物自动提取，不能直接把随视角变化的屏幕左右当作稳定关系。')
    p(d,'填写顺序：场景登记 → 照片登记 → 目标标注 → 配对真值 → 方法结果 → 汇总。细项、下拉选项和虚构示例见“08_采集标注表.xlsx”的“填写说明”。',size=10,bold=True)

    head(d,'第四部分 怎样判断值不值得继续',newpage=True)
    p(d,'先检查测试空间的全部有效配对是否都有A/B/C结果、编号是否有效、真值是否完成复核。漏跑、失败和缺失要单列；不把空表或缺失结果当成零错误。')
    table(d,['指标','怎样计算或记录','怎样解释'],[
        ['误合并','真值为不同物体，方法却输出“合并”的对数。','本来两个东西，被认成一个。'],
        ['漏合并','真值为同一物体，方法却输出“分开”的对数。','本来一个东西，被拆成两个。'],
        ['待确认','方法输出“待确认”的对数；缺失或运行失败另记。','主动暂缓判断，不能藏进“正确”。'],
        ['自动判定比例','自动输出合并或分开的有效对数 ÷ 已复核、可判断的计划测试对数。','必须和结果完整率一起看。'],
        ['已判定错误率','误合并与漏合并总数 ÷ 自动判定对数；分母为0时不计算。','比例低但大量待确认，不能单独说更好。'],
        ['时间和费用','记录关联模块耗时、完整流程耗时与实际调用支出；本地计算与云调用分开。','单个小样本的时延只作描述，不推断真机性能。']
    ],[3.05,8.05,5.9],9.8)
    p(d,'先按空间列出对数和错误类型，再给总表。比较B/C时，在开发集设定相同自动判定目标，再看测试错误；实际比例不同就并列报告，不能只挑C的低错误率。A若无连续分数，只展示原始结果，不声称已做同判定比例比较。',size=10)
    p(d,'最小模块检查：在相同设置下比较C与“去掉关系信息的C”，并检查“取消待确认”后错误是否增加。若两周内未完成，列入下一阶段，不把模块作用写成已证实。',size=10)
    head(d,'第10天的决定依据',2)
    p(d,'继续：真实错误能重复出现，数据能可靠标注；C在留出空间和不同条件下出现一致的改善信号，且不是靠增加人工输入、更多调用或大量待确认换来的。下一阶段再扩大样本、加入更强方法并完成App集成。')
    p(d,'缩小或调整：B已解决主要问题；C只在开发空间有效；改进只来自明显代码修复；或标注分歧、成本暂时无法解决。保留工程收益和失败记录，不把小样本当作正式泛化或安全结论。')
    head(d,'交付与阅读依据',2)
    p(d,'两周交付：一页结论、授权照片清单与标注、A/B/C逐项结果、配置与版本、至少覆盖主要错误类型的失败案例。与现有01方案衔接，导师确认后再扩展为正式研究和申请材料。',size=10)
    link(d,'AnjuGuard 代码基础  df281277  关联实现见 assessment_service.py','https://github.com/banshanbans/AnjuGuard/tree/df281277215a1b55fd74dc8e43203e3954081976')
    link(d,'RASSAR  CHI 2024  手机空间扫描与安全问题呈现的上游研究','https://arxiv.org/abs/2404.07479')
    link(d,'ConceptGraphs  ICRA 2024  已有多视角对象关联与场景图研究','https://concept-graphs.github.io/')
    p(d,'来源核对：2026年10月30日。上述文献用于说明研究基础；本计划的规模、工时和方法均为待执行安排。',size=9,after=0)
    f=OUT/'07_两周实验计划.docx';d.save(f);return f

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    paths=[make_brief(),make_plan()]
    print(json.dumps({'created':[str(x) for x in paths]},ensure_ascii=False,indent=2))
