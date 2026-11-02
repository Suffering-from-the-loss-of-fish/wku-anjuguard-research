from copy import deepcopy
from hashlib import sha256
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

BASE = Path(__file__).resolve().parent
REFERENCE = BASE / '学校原模板.docx'
DIRECTION = int(sys.argv[1])
OUTPUT = Path('/Users/wangkai/Desktop/温肯科研') / ('方向一申请书.docx' if DIRECTION == 1 else '方向二申请书.docx')
EXPECTED_HASH = 'c577c4e311f8ff371aa5b288e23efecf28c04f97ee28bfb7ed2412fcaf864095'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}


def el(name, **attrs):
    e = etree.Element(f'{{{W}}}{name}')
    for key, value in attrs.items():
        e.set(f'{{{W}}}{key}', str(value))
    return e


def ensure(parent, name):
    found = parent.find('w:' + name, NS)
    if found is None:
        found = el(name)
        parent.append(found)
    return found


def keep(p, following=True, before=False):
    pp = ensure(p, 'pPr')
    if following:
        ensure(pp, 'keepNext')
    if before:
        ensure(pp, 'pageBreakBefore')
    ensure(pp, 'widowControl').set(f'{{{W}}}val', '1')


def answer(text, kind='p'):
    p = el('p')
    pp = el('pPr')
    pp.append(el('pStyle', val='a'))
    pp.append(el('widowControl', val='1'))
    pp.append(el('snapToGrid', val='0'))
    pp.append(el('overflowPunct', val='0'))
    pp.append(el('spacing', before=100 if kind == 'h' else 0,
                 after=100 if kind == 'h' else 120,
                 line=300 if kind in ['ref', 'note'] else 400, lineRule='exact'))
    pp.append(el('jc', val='left'))
    if kind == 'ref':
        pp.append(el('ind', left=260, hanging=260))
        pp.append(el('keepLines'))
    if kind in ['h', 'title', 'en_title']:
        pp.append(el('keepNext'))
    p.append(pp)
    r = el('r')
    rp = el('rPr')
    rp.append(el('rFonts', ascii='Times New Roman', hAnsi='Times New Roman', eastAsia='Songti SC', cs='Times New Roman'))
    if kind in ['h', 'title']:
        rp.append(el('b'))
    rp.append(el('color', val='000000'))
    size = 28 if kind == 'title' else (21 if kind in ['ref', 'note'] else 24)
    rp.append(el('sz', val=size))
    rp.append(el('szCs', val=size))
    rp.append(el('lang', val='en-US', eastAsia='zh-CN'))
    r.append(rp)
    t = el('t')
    t.text = text
    r.append(t)
    p.append(r)
    return p


assert sha256(REFERENCE.read_bytes()).hexdigest() == EXPECTED_HASH
content = json.loads((BASE / f'direction{DIRECTION}_content.json').read_text())
with ZipFile(REFERENCE) as zin:
    root = etree.fromstring(zin.read('word/document.xml'))
    body = root.find('w:body', NS)
    ps = body.findall('w:p', NS)
    source_texts = [''.join(p.xpath('.//w:t/text()', namespaces=NS)) for p in ps]

    # Preserve all original heading wording; keep bilingual question pairs together.
    for idx in [0, 1, 2, 4, 7, 8, 9, 11, 12, 14, 15, 17, 18, 20, 21, 23, 24, 25, 27, 28]:
        keep(ps[idx])
    keep(ps[23], before=True)

    # Replace only answer slots and the research-title placeholder.
    body.replace(ps[5], answer(content['title_zh'], 'title'))
    body.replace(ps[6], answer(content['title_en'], 'en_title'))
    for index, key in [(10, 'context'), (13, 'objectives'), (16, 'methods'),
                       (19, 'innovation'), (22, 'plan'), (26, 'basis'), (29, 'conditions')]:
        position = body.index(ps[index])
        body.remove(ps[index])
        for offset, (kind, text) in enumerate(content['sections'][key]):
            body.insert(position + offset, answer(text, kind))

    # Empty template spacers may contract when filling the answer areas.
    spacer = ps[3]
    for child in list(spacer):
        spacer.remove(child)
    pp = el('pPr')
    pp.append(el('snapToGrid', val='0'))
    pp.append(el('spacing', before=0, after=0, line=100, lineRule='exact'))
    spacer.append(pp)

    # Keep generated paragraph properties in OOXML schema order for Word.
    property_order = '''pStyle keepNext keepLines pageBreakBefore framePr widowControl
        numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap
        overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid
        spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection
        textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange'''.split()
    order = {name: i for i, name in enumerate(property_order)}
    for p in body.findall('w:p', NS):
        props = p.find('w:pPr', NS)
        if props is not None:
            props[:] = sorted(props, key=lambda child: order.get(etree.QName(child).localname, 999))

    xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Preserve opaque OOXML parts, relationship bytes, styles and page furniture.
    settings = etree.fromstring(zin.read('word/settings.xml'))
    update = el('updateFields', val='true')
    settings.insert(list(settings).index(settings.find('w:hdrShapeDefaults', NS)), update)
    settings_xml = etree.tostring(settings, xml_declaration=True, encoding='UTF-8', standalone=True)
    with ZipFile(OUTPUT, 'w') as zout:
        for item in zin.infolist():
            zout.writestr(item, xml if item.filename == 'word/document.xml' else settings_xml if item.filename == 'word/settings.xml' else zin.read(item.filename))

with ZipFile(REFERENCE) as a, ZipFile(OUTPUT) as b:
    assert set(a.namelist()) == set(b.namelist())
    changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
    assert set(changed) == {'word/document.xml', 'word/settings.xml'}, changed
    rr = etree.fromstring(b.read('word/document.xml'))
    texts = [''.join(p.xpath('.//w:t/text()', namespaces=NS)) for p in rr.find('w:body', NS).findall('w:p', NS)]
    for i in [0, 1, 2, 4, 7, 8, 9, 11, 12, 14, 15, 17, 18, 20, 21, 23, 24, 25, 27, 28]:
        assert source_texts[i] in texts, (i, source_texts[i])
    authored = [content['title_zh'], content['title_en']] + [t for blocks in content['sections'].values() for _, t in blocks]
    assert all(t in texts for t in authored)

report = {
    'reference_sha256': EXPECTED_HASH,
    'source_unchanged': sha256(REFERENCE.read_bytes()).hexdigest() == EXPECTED_HASH,
    'output': str(OUTPUT),
    'output_sha256': sha256(OUTPUT.read_bytes()).hexdigest(),
    'modified_parts': changed,
    'preserved_parts': 21,
    'sections_filled': list(content['sections']),
    'authored_paragraphs': len(authored),
    'all_authored_paragraphs_present': True,
    'character_count': sum(len(t) for t in authored),
    'all_bilingual_questions_retained': True
}
(BASE / f'direction{DIRECTION}_build_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
