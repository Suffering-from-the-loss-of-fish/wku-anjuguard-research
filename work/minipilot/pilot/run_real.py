"""Run fresh inference in a new isolated directory; retain delivered evidence.

Raw downloads/models are reused; all derived data and logs are new. No mock fallback.
Requires Apple Silicon, ffmpeg/ffprobe on PATH, and the locked environment.
"""
import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def call(args, cwd=ROOT, env=None):
    subprocess.run([sys.executable, *args], cwd=cwd, env=env, check=True)


def main():
    for name in ('ffmpeg', 'ffprobe'):
        if not shutil.which(name):
            raise SystemExit(f'{name} is required. Install FFmpeg before real execution.')
    if sys.platform != 'darwin' or os.uname().machine != 'arm64':
        raise SystemExit('This pinned MLX model requires Apple Silicon macOS; no simulated fallback.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT/'runs/reproductions'/stamp
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('pilot', 'tests', 'configs'):
        shutil.copytree(ROOT/folder, out/folder, ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('README.md','README_d1.txt','ATTRIBUTION.txt','requirements.lock','run.sh'):
        shutil.copy2(ROOT/name, out/name)
    for name in ('models','.venv'):
        (ROOT/name).mkdir(exist_ok=True)
        (out/name).symlink_to(ROOT/name, target_is_directory=True)
    for direction in ('d1','d2'):
        (out/'data'/direction).mkdir(parents=True)
        (ROOT/'data'/direction/'raw').mkdir(parents=True,exist_ok=True)
        (out/'data'/direction/'raw').symlink_to(ROOT/'data'/direction/'raw',target_is_directory=True)
    parent_protocol=ROOT/'data/d2/proxy_protocol.json'
    if parent_protocol.exists():
        shutil.copy2(parent_protocol,out/'data/d2/parent_proxy_protocol.json')
    (out/'logs').mkdir();(out/'runs').mkdir()
    state = {'status':'running','kind':'fresh_real_local_inference','paid_api_budget_usd':0,
             'data_models_shared_from':str(ROOT),'output':str(out),'started_utc':stamp}
    status = out/'run_status.json'
    status.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    server = None
    try:
        for script, args in [('d1_download.py', []), ('download_model.py', []),
                             ('d1_data.py', []), ('d2_data.py', ['download','--range-workers','8']),
                             ('d2_data.py', ['unpack']), ('d2_data.py', ['extract']),
                             ('d2_data.py', ['proxy'])]:
            call(['pilot/'+script, *args],out)
        # Data commands preserve failure rows; reject incomplete acquisition here.
        frames=[json.loads(x) for x in (out/'data/d2/frames.jsonl').read_text().splitlines()]
        if len({f['video_id'] for f in frames}) != 6:
            raise RuntimeError('Incomplete real data: all six approved videos are required')
        call(['pilot/d1_run.py'],out)
        initial=out/'runs/d1/initial_run';initial.mkdir()
        for p in (out/'runs/d1').iterdir():
            if p.is_file(): shutil.copy2(p, initial/p.name)
        call(['pilot/d1_supplement.py'],out)
        call(['pilot/d1_coverage_analysis.py'],out)
        # A free loopback port prevents disturbing an already running App/server.
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        with (out/'logs/model_server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'pilot/model_server.py','--port',str(port)],
                                    cwd=out,stdout=log,stderr=subprocess.STDOUT)
            health=None
            for _ in range(180):
                if server.poll() is not None: raise RuntimeError('Model server failed; see model_server.log')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=2) as response:
                        health=json.load(response)
                    break
                except Exception: time.sleep(1)
            if health is None: raise TimeoutError('Model server did not become healthy within 180 seconds')
            frozen_contract=json.loads((out/'configs/d2_model_contract.json').read_text())
            for key,value in frozen_contract.items():
                if key not in health or value != health[key]:
                    raise RuntimeError(f'Frozen model contract mismatch: {key}')
            (out/'runs/model_health.json').write_text(json.dumps(health,ensure_ascii=False,indent=2))
            for split in ('dev','test'):
                call(['pilot/d2.py','--split',split,'--contract','configs/d2_model_contract.json',
                      '--timeout','60','--endpoint',f'http://127.0.0.1:{port}/analyze'],out)
                call(['pilot/d2_audit.py','--split',split],out)
        call(['pilot/recompute.py'],out)
        state['status']='completed'
    except BaseException as exc:
        state.update(status='incomplete',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if server is not None:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill();server.wait()
        status.write_text(json.dumps(state,ensure_ascii=False,indent=2))
        print(status,flush=True)


if __name__=='__main__':main()
