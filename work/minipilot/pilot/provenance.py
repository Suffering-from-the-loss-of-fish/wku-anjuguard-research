"""Capture reproducibility metadata without collecting environment secrets."""
from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    def cmd(args):
        p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
        return {'exit_code': p.returncode, 'output': p.stdout.strip()}
    files = []
    for folder, pattern in [('pilot','*.py'),('tests','*.py'),('configs','*.json'),('models','*.safetensors')]:
        for p in sorted((ROOT/folder).rglob(pattern)):
            files.append({'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)})
    for p in (ROOT/'requirements.lock', ROOT/'run.sh', ROOT/'README.md'):
        if p.exists(): files.append({'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
    data = {'captured_utc':datetime.now(timezone.utc).isoformat(),
            'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
            'machine':platform.machine(),'macos':platform.mac_ver()[0],
            'experiment_git':cmd(['git','rev-parse','HEAD']),
            'experiment_worktree':cmd(['git','status','--short']),
            'files':files,'paid_api_spending_authorized':0,'currency':'USD',
            'measurement_boundaries':{'independent_human_review':'not completed',
             'on_phone_measurement':'not performed','energy':'not measured',
             'cloud_api':'not used','dataset_licenses':'noncommercial research; see ATTRIBUTION.txt'}}
    target=ROOT/'runs/provenance.json';target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(target)


if __name__=='__main__':main()
