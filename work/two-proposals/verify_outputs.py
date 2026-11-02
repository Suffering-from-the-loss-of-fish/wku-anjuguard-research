from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json
import re
import unicodedata
from pypdf import PdfReader
from lxml import etree

BASE = Path(__file__).resolve().parent
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
REF = BASE / '学校原模板.docx'

def norm(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).replace('\u00ad', '')

reports = []
with ZipFile(REF) as original:
    refxml = etree.fromstring(original.read('word/document.xml'))
    original_paras = refxml.find('w:body', NS).findall('w:p', NS)
    preserved = [0, 1, 2, 4, 7, 8, 9, 11, 12, 14, 15, 17, 18, 20, 21, 23, 24, 25, 27, 28]
    for i, zh in [(1, '一'), (2, '二')]:
        out = Path('/Users/wangkai/Desktop/温肯科研') / f'方向{zh}申请书.docx'
        content = json.loads((BASE / f'direction{i}_content.json').read_text())
        authored = [content['title_zh'], content['title_en']] + [t for v in content['sections'].values() for _, t in v]
        with ZipFile(out) as target:
            assert set(original.namelist()) == set(target.namelist())
            changed = [n for n in original.namelist() if original.read(n) != target.read(n)]
            assert set(changed) == {'word/document.xml', 'word/settings.xml'}
            a = etree.fromstring(original.read('word/settings.xml'))
            b = etree.fromstring(target.read('word/settings.xml'))
            flag = b.find('w:updateFields', NS)
            assert flag.get(f'{{{W}}}val') == 'true'
            b.remove(flag)
            assert etree.tostring(a, method='c14n') == etree.tostring(b, method='c14n')
            root = etree.fromstring(target.read('word/document.xml'))
            assert etree.tostring(refxml.find('w:body/w:sectPr', NS), method='c14n') == etree.tostring(root.find('w:body/w:sectPr', NS), method='c14n')
            texts = [''.join(p.xpath('.//w:t/text()', namespaces=NS)) for p in root.findall('w:body/w:p', NS)]
            assert all(t in texts for t in authored)
            for index in preserved:
                source = original_paras[index]
                text = ''.join(source.xpath('.//w:t/text()', namespaces=NS))
                match = [p for p in root.findall('w:body/w:p', NS) if ''.join(p.xpath('.//w:t/text()', namespaces=NS)) == text]
                assert len(match) == 1
                assert [etree.tostring(r, method='c14n') for r in source.findall('w:r', NS)] == [etree.tostring(r, method='c14n') for r in match[0].findall('w:r', NS)]
            assert not any(x in '\n'.join(texts) for x in ['TODO', 'PLACEHOLDER', '研究标题', 'turn0search', 'turn1view'])
        render = BASE / f'direction{i}-render-v{1 if i == 1 else 2}'
        pdf = PdfReader(render / f'方向{zh}申请书.pdf').pages
        chunks = []
        page_counts = []
        for page in pdf:
            body = []
            for line in page.extract_text().splitlines():
                if re.fullmatch(r'\s*\d+\s*', line) or 'Wenzhou-Kean University' in line or 'ORSP (OGCO)' in line:
                    continue
                body.append(line)
            page_counts.append(len(norm(''.join(body))))
            chunks.extend(body)
        assert all(n > 100 for n in page_counts), page_counts
        pdftext = norm(''.join(chunks))
        missing = [t for t in authored if norm(t) not in pdftext]
        assert not missing, missing
        assert len(list(render.glob('page-*.png'))) == len(pdf)
        reports.append({'direction': i, 'file': str(out), 'sha256': sha256(out.read_bytes()).hexdigest(), 'pages': len(pdf), 'authored_paragraphs': len(authored), 'all_authored_paragraphs_in_pdf': True, 'all_original_prompts_and_run_formatting_preserved': True, 'page_geometry_preserved': True, 'unchanged_package_parts': 21, 'modified_parts': changed, 'settings_only_adds_updateFields': True, 'page_body_character_counts': page_counts})

before = json.loads((BASE / 'existing_deliverables_before.json').read_text())
assert all(sha256(Path(p).read_bytes()).hexdigest() == h for p, h in before.items())
report = {'outputs': reports, 'reference_sha256': sha256(REF.read_bytes()).hexdigest(), 'reference_unchanged': sha256(REF.read_bytes()).hexdigest() == 'c577c4e311f8ff371aa5b288e23efecf28c04f97ee28bfb7ed2412fcaf864095', 'existing_deliverables_unchanged': len(before), 'scope': 'Document creation and QA only. No model/device experiments or submission performed.'}
(BASE / 'structural_text_qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
