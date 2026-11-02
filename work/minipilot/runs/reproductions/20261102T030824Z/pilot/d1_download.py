"""Download fixed, public research data and a revision-pinned frozen encoder."""
from __future__ import annotations
import concurrent.futures, hashlib, json, os, pathlib, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENES = ('desk_1', 'kitchen_small_1', 'meeting_small_1', 'table_1')
REVISION = 'ed25f3a31f01632728cabb09d1542f84ab7b0056'
DATA_BASE = 'https://rgbd-dataset.cs.washington.edu/dataset/rgbd-scenes/'

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def fetch(url, path):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.stat().st_size:
        return {'url': url, 'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': sha256(path), 'reused': True}
    part = path.with_suffix(path.suffix+'.part')
    start = time.time()
    for attempt in range(3):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'AnjuGuard-research-minipilot/1.0'})
            with urllib.request.urlopen(req,timeout=90) as r, open(part,'wb') as f:
                length = r.headers.get('Content-Length')
                while chunk := r.read(1024*1024): f.write(chunk)
            if length and part.stat().st_size != int(length): raise IOError('Incomplete download')
            os.replace(part,path)
            return {'url':url,'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':sha256(path),'download_seconds':time.time()-start,'attempts':attempt+1}
        except Exception:
            if attempt == 2: raise
            time.sleep(attempt+1)

def main():
    tasks = [(DATA_BASE+s+'.tar', ROOT/'data/d1/raw'/f'{s}.tar') for s in SCENES]
    tasks += [('https://huggingface.co/facebook/dinov2-small/resolve/'+REVISION+'/'+name, ROOT/'models/dinov2-small'/name) for name in ('config.json','preprocessor_config.json','model.safetensors')]
    tasks += [(DATA_BASE+'README.txt', ROOT/'data/d1/raw/README_source.txt'),('https://rgbd-dataset.cs.washington.edu/dataset.html',ROOT/'data/d1/raw/license_source.html')]
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_map={executor.submit(fetch,url,path):(url,path) for url,path in tasks}
        for future in concurrent.futures.as_completed(future_map):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
    (ROOT/'data/d1/download_manifest.json').write_text(json.dumps({'dataset':'UW RGB-D Scenes v1','license':'non-commercial research/educational use only','model':'facebook/dinov2-small','model_revision':REVISION,'files':results},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
