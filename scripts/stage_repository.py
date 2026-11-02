#!/usr/bin/env python3
"""Audit/stage the shared snapshot without modifying embedded Git repositories.

Run from any directory. --stage updates only the parent Git index. It deliberately
includes recorded results that the original experiment .gitignore omits.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'work/repository-setup/upload_manifest.json'
SKIP_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'fontcache'}


def exclusion(path):
    parts = path.parts
    name = path.name
    if any(p in SKIP_DIRS for p in parts):
        return 'local runtime/cache/git metadata'
    if parts[:2] == ('work', 'sync') or parts[:3] == ('work', 'repository-setup', 'private'):
        return 'local coordination state'
    if parts[:3] == ('work', 'minipilot', 'models'):
        return 'downloadable fixed-revision model weights'
    for i, part in enumerate(parts):
        if part == 'data' and len(parts) > i + 2 and parts[i+1] in ('d1', 'd2') and parts[i+2] in ('raw', 'sparse'):
            return 'downloadable original dataset/cache'
    if name == '预实验代码.zip':
        return 'release asset (over regular Git file limit)'
    if name == '.DS_Store' or path.suffix == '.pyc':
        return 'local runtime/cache/git metadata'
    if (name == '.env' or name.startswith('.env.')) and name != '.env.example':
        return 'local credentials/configuration'
    if path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx'}:
        return 'local credentials/configuration'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', action='store_true')
    args = parser.parse_args()
    selected, excluded = [], []
    for base, dirs, files in os.walk(ROOT, followlinks=False):
        dirs.sort()
        # Git internals may contain auth/configuration; never enumerate them.
        kept = []
        for d in dirs:
            full_dir = Path(base) / d
            rel_dir = full_dir.relative_to(ROOT)
            reason = exclusion(rel_dir)
            if d == '.git':
                continue
            if full_dir.is_symlink():
                reason = 'local symbolic link'
            if reason:
                excluded.append({'path': str(rel_dir) + '/', 'bytes': None, 'reason': reason})
            else:
                kept.append(d)
        dirs[:] = kept
        for name in sorted(files):
            full = Path(base) / name
            rel = full.relative_to(ROOT)
            reason = exclusion(rel)
            if full.is_symlink():
                reason = 'local symbolic link'
            size = full.lstat().st_size
            if reason:
                excluded.append({'path': str(rel), 'bytes': size, 'reason': reason})
                continue
            if size >= 100 * 1024 * 1024:
                raise SystemExit(f'File needs explicit large-file handling: {rel} ({size} bytes)')
            if full == REPORT:
                continue
            digest = hashlib.sha256()
            with full.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            sha = digest.hexdigest()
            mode = '100755' if full.stat().st_mode & stat.S_IXUSR else '100644'
            selected.append({'path': str(rel), 'bytes': size, 'sha256': sha, 'mode': mode})
    selected.sort(key=lambda x: x['path'])
    excluded.sort(key=lambda x: x['path'])
    manifest = {
        'schema': 1,
        'scope': 'Current project files; original downloads/runtime excluded; ZIP published separately as a Release asset.',
        'manifest_self_excluded_from_hashes': True,
        'included_files': len(selected),
        'included_bytes': sum(x['bytes'] for x in selected),
        'excluded_counts': dict(Counter(x['reason'] for x in excluded)),
        'included': selected,
        'excluded': excluded,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    if args.stage:
        # Plumbing intentionally stores ordinary blobs, never embedded gitlinks.
        paths = [x['path'] for x in selected] + [str(REPORT.relative_to(ROOT))]
        modes = [x['mode'] for x in selected] + ['100644']
        quoted = ''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in paths)
        hashes = subprocess.check_output(['git', 'hash-object', '-w', '--stdin-paths'], cwd=ROOT, input=quoted.encode()).decode().splitlines()
        if len(hashes) != len(paths):
            raise SystemExit('Git object count mismatch')
        records = b''.join(f'{m} {h}\t{p}\0'.encode() for m, h, p in zip(modes, hashes, paths))
        subprocess.run(['git', 'update-index', '-z', '--index-info'], cwd=ROOT, input=records, check=True)
        previous = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        wanted = set(paths)
        removed = [p for p in previous if p and p not in wanted]
        if removed:
            subprocess.run(['git', 'update-index', '--force-remove', '-z', '--stdin'], cwd=ROOT,
                           input=('\0'.join(removed) + '\0').encode(), check=True)
        print(f'Staged {len(paths)} ordinary files; removed {len(removed)} obsolete parent-index entries.')
    print(json.dumps({k: manifest[k] for k in ('included_files', 'included_bytes', 'excluded_counts')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
