import json
import re
import sys
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

BASE = Path(__file__).resolve().parent
OUT = Path('/Users/wangkai/Documents/Codex/2026-10-29/zhe/outputs/AnjuGuard科研方案')
FILES = {
    'summary': '00_AnjuGuard科研与工程方向总结.docx',
    'route1': '01_跨视角问题实例关联与证据一致性研究方案.docx',
    'route2': '02_移动视觉任务的质量约束推理调度研究方案.docx',
    'route3': '03_室内改造预览的可验证局部图像编辑研究方案.docx',
    'comparison': '04_三方向比较与选题推荐.docx',
}

def font(run, size=None, bold=None, color='000000', cjk='Songti SC'):
    run.font.name = 'Arial'
    if size is not None: run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    prop = run._element.get_or_add_rPr()
    fonts = prop.find(qn('w:rFonts'))
    if fonts is None:
        fonts = OxmlElement('w:rFonts'); prop.insert(0, fonts)
    for a, v in [('ascii','Arial'),('hAnsi','Arial'),('eastAsia',cjk),('cs','Arial')]:
        fonts.set(qn('w:'+a), v)
    for a in list(fonts.attrib):
        if 'theme' in a.lower(): del fonts.attrib[a]

def add_text(p, text, size=None, bold=None):
    for i, part in enumerate(re.split(r'\*\*(.*?)\*\*', str(text))):
        if part:
            r=p.add_run(part); font(r,size,bold if i%2==0 else True)
    return p

def para(d, text, style=None):
    p=d.add_paragraph(style=style)
    add_text(p,text)
    return p

def heading(d, text, level=1):
    p=d.add_paragraph(style=f'Heading {level}')
    add_text(p,text, bold=True)
    return p

def hyperlink(p, text, url):
    rel=p.part.relate_to(url,RT.HYPERLINK,is_external=True)
    h=OxmlElement('w:hyperlink'); h.set(qn('r:id'),rel)
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr')
    f=OxmlElement('w:rFonts')
    for a,v in [('ascii','Arial'),('hAnsi','Arial'),('eastAsia','Songti SC')]:f.set(qn('w:'+a),v)
    pr.append(f)
    c=OxmlElement('w:color');c.set(qn('w:val'),'1F4E79');pr.append(c)
    sz=OxmlElement('w:sz');sz.set(qn('w:val'),'20');pr.append(sz)
    u=OxmlElement('w:u');u.set(qn('w:val'),'single');pr.append(u)
    r.append(pr);t=OxmlElement('w:t');t.text=text;r.append(t);h.append(r);p._p.append(h)

def table(d, b):
    headers=b['headers']; rows=b['rows']
    t=d.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    raw=b.get('widths') or [1]*len(headers)
    widths=[6.67*float(x)/sum(float(y) for y in raw) for x in raw]
    for c,w in zip(t.columns,widths):c.width=Inches(w)
    for rowdata in [headers]+rows:
        row=t.rows[0] if rowdata is headers else t.add_row()
        trpr=row._tr.get_or_add_trPr()
        cant=OxmlElement('w:cantSplit');trpr.append(cant)
        if rowdata is headers:
            repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
        for idx,(cell,text) in enumerate(zip(row.cells,rowdata)):
            cell.width=Inches(widths[idx]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=cell._tc.get_or_add_tcPr()
            borders=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
            pr.append(borders)
            mar=OxmlElement('w:tcMar')
            for edge,value in [('top',100),('bottom',100),('left',100),('right',100)]:
                el=OxmlElement('w:'+edge);el.set(qn('w:w'),str(value));el.set(qn('w:type'),'dxa');mar.append(el)
            pr.append(mar)
            sh=OxmlElement('w:shd')
            sh.set(qn('w:fill'),'244A63' if rowdata is headers else ('F1F5F8' if len(t.rows)%2==0 else 'FFFFFF'))
            pr.append(sh)
            p=cell.paragraphs[0];p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(1.5);p.paragraph_format.line_spacing=1.12
            r=p.add_run(str(text));font(r,9.7,rowdata is headers,'FFFFFF' if rowdata is headers else '000000')
    p=d.add_paragraph();p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0)
    p.paragraph_format.line_spacing=1;p.add_run().font.size=Pt(3)

def make(key):
    spec=json.loads((BASE/f'{key}.json').read_text())
    d=Document();sec=d.sections[0]
    for element in d.styles.element.iter():
        if element.tag in {qn('w:pBdr'),qn('w:tblBorders')}:
            element.getparent().remove(element)
        if element.tag==qn('w:rFonts'):
            for attr in list(element.attrib):
                if 'theme' in attr.lower(): del element.attrib[attr]
    sec.page_width=Inches(8.27);sec.page_height=Inches(11.69)
    sec.top_margin=Inches(.68);sec.bottom_margin=Inches(.68)
    sec.left_margin=Inches(.8);sec.right_margin=Inches(.8)
    sec.footer_distance=Inches(.3)
    for name in ['Normal','List Bullet','List Number','Title','Subtitle','Heading 1','Heading 2','Heading 3']:
        s=d.styles[name];s.font.name='Arial';s.font.color.rgb=RGBColor(0,0,0)
        s._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Songti SC')
    normal=d.styles['Normal'];normal.font.size=Pt(11)
    normal.paragraph_format.line_spacing=1.25;normal.paragraph_format.space_after=Pt(6)
    for name in ['List Bullet','List Number']:
        s=d.styles[name];s.font.size=Pt(10.7);s.paragraph_format.space_after=Pt(4);s.paragraph_format.line_spacing=1.2
    for name,size,before,after in [('Title',22,0,9),('Subtitle',9.5,0,11),('Heading 1',16,0,9),('Heading 2',12.5,9,5),('Heading 3',11,6,4)]:
        s=d.styles[name];s.font.size=Pt(size);s.font.bold=name!='Subtitle';s.paragraph_format.space_before=Pt(before);s.paragraph_format.space_after=Pt(after);s.paragraph_format.keep_with_next=True
    d.styles['Title'].paragraph_format.line_spacing=1.08
    d.styles['Subtitle'].font.color.rgb=RGBColor.from_string('555555')
    d.styles['Subtitle'].font.italic=False
    for tag in ['numPr','contextualSpacing']:
        for el in list(d.styles['Subtitle']._element.iter(qn('w:'+tag))):
            el.getparent().remove(el)
    for name in ['Title','Subtitle','Heading 1','Heading 2','Heading 3']:
        pr=d.styles[name]._element.get_or_add_rPr()
        for el in list(pr):
            if el.tag in {qn('w:spacing'),qn('w:iCs')}:
                pr.remove(el)
    if key in {'route2','comparison'}:
        normal.paragraph_format.line_spacing=1.13
        normal.paragraph_format.space_after=Pt(4)
        for name in ['List Bullet','List Number']:
            d.styles[name].paragraph_format.line_spacing=1.13
            d.styles[name].paragraph_format.space_after=Pt(3)
        d.styles['Heading 2'].paragraph_format.space_before=Pt(7)
        d.styles['Heading 2'].paragraph_format.space_after=Pt(4)
    for pnum,page in enumerate(spec['pages']):
        if not pnum:
            para(d,spec['title'],'Title');para(d,spec.get('subtitle','2026年10月29日'),'Subtitle')
        h=heading(d,page['title'])
        if pnum: h.paragraph_format.page_break_before=True
        for b in page['blocks']:
            typ=b['type']
            if typ=='p':para(d,b['text'])
            elif typ in ['h2','h3']:heading(d,b['text'],int(typ[-1]))
            elif typ in ['bullets','numbered']:
                for item in b['items']:para(d,item,'List Bullet' if typ=='bullets' else 'List Number')
            elif typ=='table':table(d,b)
            else:raise ValueError(typ)
    if spec.get('references'):
        heading(d,'参考资料与来源').paragraph_format.page_break_before=True
        p=para(d,'核查日期为2026年10月29日。文中编号对应下列来源。研究方案中的样本量、阈值、里程碑和创新点均为拟议设计，尚不是实验结果。')
        for ref in spec['references']:
            p=d.add_paragraph();p.paragraph_format.space_after=Pt(2);p.paragraph_format.keep_with_next=True
            add_text(p,f"[{ref['id']}] ",10,True);hyperlink(p,ref['title'],ref['url'])
            if ref.get('note'):
                p=para(d,ref['note']);p.paragraph_format.space_after=Pt(8)
                for r in p.runs:font(r,9.5,color='444444')
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    r=footer.add_run('AnjuGuard 研究方案  ·  ');font(r,8.5,color='666666')
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    settings=d.settings.element
    lang=OxmlElement('w:themeFontLang');lang.set(qn('w:val'),'en-US');lang.set(qn('w:eastAsia'),'zh-CN');settings.append(lang)
    d.core_properties.title=spec['title'];d.core_properties.subject='AnjuGuard research and engineering plan'
    d.core_properties.author='';d.core_properties.keywords='AnjuGuard;研究方案;CCF;实验设计'
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/FILES[key];d.save(path)
    print(json.dumps({'key':key,'path':str(path),'logical_pages':len(spec['pages'])+bool(spec.get('references'))},ensure_ascii=False))

if __name__=='__main__':
    for key in sys.argv[1:] or FILES:
        make(key)
