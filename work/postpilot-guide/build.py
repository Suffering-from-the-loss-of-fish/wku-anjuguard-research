from pathlib import Path
import json, hashlib
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent
DEST=Path('/Users/wangkai/Desktop/温肯科研')
OUT=ROOT/'方向选择与下一步.docx'
existing={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.iterdir() if p.suffix.lower() in ('.docx','.xlsx') and p.name!='方向选择与下一步.docx'}
if not (ROOT/'existing_files_before.json').exists():
    (ROOT/'existing_files_before.json').write_text(json.dumps(existing,ensure_ascii=False,indent=2))

doc=Document(); sec=doc.sections[0]
sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.65);sec.bottom_margin=Inches(.62)
sec.left_margin=Inches(.75);sec.right_margin=Inches(.75)
sec.footer_distance=Inches(.28)

def font(style,size,east='Songti SC',bold=False):
    s=doc.styles[style];s.font.name='Calibri';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0);s.font.bold=bold
    s.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),east)
    p=s.paragraph_format;p.space_before=Pt(0);p.space_after=Pt(5);p.line_spacing=Pt(16)
    p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    pp=s.element.get_or_add_pPr();snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'0');pp.append(snap)
    return s
font('Normal',11)
font('Title',21,'Songti SC',True).paragraph_format.space_after=Pt(8)
doc.styles['Title'].paragraph_format.line_spacing=Pt(28)
font('Subtitle',10,'Songti SC').paragraph_format.space_after=Pt(10)
for st,size in [('Heading 1',13),('Heading 2',11.5)]:
    s=font(st,size,'Songti SC',True);s.paragraph_format.space_before=Pt(8);s.paragraph_format.space_after=Pt(5);s.paragraph_format.keep_with_next=True
    s.paragraph_format.keep_together=True

def para(text,bold=False,small=False):
    p=doc.add_paragraph();p.paragraph_format.widow_control=True
    r=p.add_run(text);r.bold=bold
    if small:r.font.size=Pt(9)
    return p

def heading(text):return doc.add_paragraph(text,'Heading 1')

def link(p,label,url):
    rel=p.part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    h=OxmlElement('w:hyperlink');h.set(qn('r:id'),rel)
    r=OxmlElement('w:r');pr=OxmlElement('w:rPr')
    col=OxmlElement('w:color');col.set(qn('w:val'),'22577A');pr.append(col)
    sz=OxmlElement('w:sz');sz.set(qn('w:val'),'18');pr.append(sz)
    r.append(pr);t=OxmlElement('w:t');t.text=label;r.append(t);h.append(r);p._p.append(h)

doc.add_paragraph('预实验后的方向选择与下一步','Title')
doc.add_paragraph('温肯科研  通俗说明  2026年11月1日','Subtitle')
para('我的建议是：下一轮科研优先方向一，方向二先保留简单修复作为 App 优化候选。方向一的核验更集中，适合先查清现成方法还解决不了什么。这个排序是投入建议；最终选题仍需你和导师确认。',True)
para('两条路线都已完成实验代码和真实本机模型运行，但还没有证明新机制稳定优于现成方法。现有48对照片和250段事件都尚未完成独立人工复核；当前测的是公开物品身份与家具可见性，完整风险识别和原 App 实际收益仍未验证。')

heading('方向一 让 App 认清是不是同一个东西')
para('同一根线从三个角度拍，应该对应一个问题、保留三张证据；两根长得很像的线，又不能被合成一个。方向一就是研究怎样把这些照片正确对应起来。')
para('在留出的24对照片中，原规则漏掉了12对同物关联，不设“待确认”的现成视觉特征方法把漏关联降到3对。不过，原规则在这些公开照片缺少 App 来源信息时本来就不会触发，因此“解决9/12”不能写成 App 准确率提高75%，也不能全算成我们的创新。')
para('更关键的是，新加的“参照物关系”模块去掉后，结果完全一样。目前能肯定的是基础方法跑通了；关系模块的额外价值还没有证据。下一步值得查的是相似物体、遮挡和换角度时仍然出错的原因。')

heading('方向二 让 App 决定什么时候问 AI')
para('方向二研究什么时候发送图片、发多清楚，目标是在重要信息不漏掉的前提下，减少无效请求和等待。')
para('这次简单修复把策略请求从52次降到37次，主要来自调整无效返回后的等待规则。复杂策略进一步降到35次，却把图片数据量从约1.85 MB增到4.14 MB，等待更久、没有可用答案的时刻更多。独立复跑还显示调参结果不稳定。')
para('这些是策略请求量，不能直接换算成省钱比例。模型调用的新增付费都是0；事件标注尚无人独立复核，自动参考也有问题。因此还不能说识别质量保住了，更不能把低匹配全部归咎于模型。')

heading('做出来 发论文 帮助 App 怎么比较')
table=doc.add_table(rows=1,cols=3);table.alignment=WD_TABLE_ALIGNMENT.CENTER;table.autofit=False
widths=[1.05,2.98,2.97]
for c,w in zip(table.columns,widths):c.width=Inches(w)
headers=['比较点','方向一','方向二']
rows=[
 ['后续可行性','照片配对容易人工核对，剩余问题较容易收窄。','视频要检查出现时间、遮挡和回答质量，核验工作更多。'],
 ['论文路线','更值得优先探索；候选机制仍未证明额外收益。','先补可信标注和模型可用性，暂不追加复杂策略。'],
 ['App 帮助','有望减少重复报告、错误合并，让问题与证据对应清楚。','简单修复可能减少无效请求；省钱和质量收益尚待验证。']
]
for cell,txt in zip(table.rows[0].cells,headers):cell.text=txt
for vals in rows:
    for c,t in zip(table.add_row().cells,vals):c.text=t
for ri,row in enumerate(table.rows):
    trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
    if ri==0:
        repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
    for ci,c in enumerate(row.cells):
        c.width=Inches(widths[ci]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        tcpr=c._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
        for edge in ['top','left','bottom','right']:
            el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');b.append(el)
        tcpr.append(b)
        mar=OxmlElement('w:tcMar')
        for edge,val in [('top',75),('bottom',75),('left',95),('right',95)]:
            el=OxmlElement('w:'+edge);el.set(qn('w:w'),str(val));el.set(qn('w:type'),'dxa');mar.append(el)
        tcpr.append(mar)
        if ri==0:
            sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E7F0F5');tcpr.append(sh)
        for p in c.paragraphs:
            p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=Pt(13.5)
            if ci==0 or ri==0:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:r.font.size=Pt(10);r.bold=(ri==0)

doc.add_page_break()
heading('你接下来先做什么')
para('先完成下面三步。普通手机就能开始，目前不用购买设备或付费 API；方向二的250段事件复核，可以留到确定继续该方向时再安排。')

doc.add_paragraph('第一步 带着现有结论找导师讨论','Heading 2')
para('把同文件夹的“导师结论.docx”给导师看，并找一位愿意参与独立复核的同学。请导师帮助判断研究切口、可拍摄场地和后续分工。')
para('你可以这样讲：“两个方向都跑过了。方向一的基础方法能用，但新模块还没显示收益。我想先核对困难样本，再决定论文具体研究什么。”')

doc.add_paragraph('第二步 两个人分别核对48对照片','Heading 2')
para('打开“补充复核.xlsx”的“对象复核”。你和另一人各用一份空白副本，分别判断同一个物体、不同物体或看不清，并记下理由与时间。先不要看算法结果、发布方答案或对方填写的内容。')
para('全部独立填完后再比较。分歧交给第三人裁决或保留待确认，不能为了凑答案强行选同物或异物。这48对是现成的公开样本，不需要先拍照片才能做。')

doc.add_paragraph('第三步 确定继续后补拍48张照片','Heading 2')
para('找3个独立、获准拍摄的场地，每处2组静态布置，每组8张，共48张。拍同一物体的正面、侧面、远近、遮挡与离开后重访，也要包含外观相似但实际不同的物体。每组保持物体位置不动，移动后另建组。')
para('同一家庭的三个房间不能当成三个独立场地。至少1个场地用于开发、2个场地留到最终检查；同场地的照片、裁剪和视频都留在同一组，不能把相邻照片拆到两边。文件名可用 S01_G01_P01.jpg。')
para('如果顺便保留方向二的数据，每个场地再拍2段1至2分钟视频，共6段，文件名可用 S01_V01.mov。视频采集是可选补充，不影响先完成方向一的照片复核。')

heading('什么时候值得继续冲论文')
para('拿到人工复核和新照片后，先确定数据划分、评价标准与参数，再比较现成强方法和候选新方法。重点看相似物和困难视角：能否少漏关联，同时不增加错误合并，也不靠大量“待确认”掩盖问题。')
para('如果这种额外改善在保留的新场地上反复出现，再扩大实验并确定论文问题。如果只有现成方法有帮助，就把它作为 App 工程改进，调整研究切口。3个场地仍只够做小规模筛查；两条方向目前都不能认定已有 CCF A/B 级别的研究成果。')
para('多视角关联和视频选帧已有相关研究。论文还需要说明现有方法遗漏了什么、为什么我们的办法能改善，并给出可信的对照证据。',small=True)
p=doc.add_paragraph();p.paragraph_format.space_after=Pt(4)
link(p,'ConceptGraphs 作者项目页','https://concept-graphs.github.io/');p.add_run('  |  ');link(p,'Q-Frame 论文摘要','https://arxiv.org/abs/2506.22139')

heading('配套文件在哪里')
para('桌面“温肯科研”：导师结论.docx用于沟通，预实验报告.docx解释结果，预实验结果.xlsx保存明细，补充复核.xlsx用于人工填写。本说明记录当前建议，最终选题仍由你和导师确认。',small=True)

footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=footer.add_run();r.font.size=Pt(9)
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');r._r.addnext(field)
doc.core_properties.title='预实验后的方向选择与下一步'
doc.core_properties.subject='方向一和方向二的通俗比较与行动顺序'
doc.core_properties.author='';doc.core_properties.last_modified_by=''
for root in [doc.element,doc.styles.element]:
    for border in list(root.iter(qn('w:pBdr'))):border.getparent().remove(border)
for grid in list(sec._sectPr.iter(qn('w:docGrid'))):grid.getparent().remove(grid)
doc.save(OUT)
print(OUT)
