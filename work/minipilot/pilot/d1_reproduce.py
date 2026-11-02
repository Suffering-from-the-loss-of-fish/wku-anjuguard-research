"""One command, fresh real DINOv2 inference; original result files remain intact."""
import argparse, datetime, os, pathlib, shutil, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    name='reproduced_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT/'runs/d1'/name;out.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'D1_RUN_DIR':str(out)}
    commands=[]
    if not args.offline:commands.append([sys.executable,'pilot/d1_download.py'])
    commands += [[sys.executable,'pilot/d1_data.py'],[sys.executable,'pilot/d1_run.py']]
    for cmd in commands:
        subprocess.run(cmd,cwd=ROOT,env=env,check=True)
    backup=out/'initial_run';backup.mkdir()
    for p in list(out.iterdir()):
        if p.is_file():shutil.copy2(p,backup/p.name)
    subprocess.run([sys.executable,'pilot/d1_supplement.py'],cwd=ROOT,env=env,check=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_d1*.py','-v'],cwd=ROOT,env=env,check=True)
    print('Direction 1 reproduction complete:',out)

if __name__=='__main__':main()
