"""Package portable code plus measured evidence; omit raw video/weights/env."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def selected(path):
    rel=path.relative_to(ROOT);parts=rel.parts
    if any(x in {'__pycache__','.DS_Store','.git','.pytest_cache','.venv','node_modules'} for x in parts):return False
    if parts[0]=='models':return False
    if parts[0]=='delivery':return path.name!='package_check.json' and path.suffix in {'.docx','.xlsx','.html','.txt','.json'}
    if parts[0]=='logs':return path.suffix=='.log'
    if parts[0]=='runs':
        if 'artifact_qa' in parts:return path.suffix=='.json'
        if 'font_probe' in parts:return False
        if any(x in {'reproductions','recomputed','reanalyzed'} or x.startswith('reproduced_') for x in parts):return False
        if path.suffix=='.pdf':return False
        return True
    if parts[0]=='data':
        if 'sparse' in parts or ('frames' in parts and 'd2' in parts):return False
        if path.suffix.lower() in {'.mov','.mp4','.tar','.zip','.partial'}:return False
        if any(x.endswith('.chunks') for x in parts):return False
        return True
    return parts[0] in {'pilot','configs','tests','docs'} or len(parts)==1

def main():
    out=ROOT/'delivery/预实验代码.zip'
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink() and selected(p))
    manifest=[]
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            rel=str(p.relative_to(ROOT));data=p.read_bytes()
            z.write(p,'minipilot/'+rel)
            manifest.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        z.writestr('minipilot/PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(out) as z:
        bad=z.testzip()
        if bad:raise ValueError('Corrupt member: '+bad)
    result={'path':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(manifest),'zip_integrity':'passed','raw_video_and_models':'not packaged; pinned downloaders supplied'}
    (ROOT/'delivery/package_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
