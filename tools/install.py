"""Install the three bundled skills; preserve any replaced version as a backup."""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ('lowpoly-workbench', 'scenario-blender-expert', 'scenario-blender-retopology')


def manifest(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'skills')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args()
    destination = args.dest.expanduser().resolve()
    plan = []
    for name in SKILLS:
        source, target = ROOT/'skills'/name, destination/name
        if not (source/'SKILL.md').is_file():
            raise SystemExit(f'Missing source skill: {name}')
        if target.is_symlink():
            raise SystemExit(f'Refusing to replace a symlink: {target}')
        if target.exists() and not target.is_dir():
            raise SystemExit(f'Target is not a directory: {target}')
        state = 'skip' if target.exists() and manifest(source) == manifest(target) else 'update' if target.exists() else 'install'
        plan.append((name, source, target, state))
    if any(state == 'update' for *_, state in plan) and not args.update:
        for name, _, target, state in plan:
            print(f'{state}: {name} -> {target}')
        raise SystemExit('Different version exists. Review it, then pass --update to back up and replace.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup_root = destination.parent/'skill-backups'/'lowpoly-workbench'/stamp
    for name, source, target, state in plan:
        print(f'{state}: {name} -> {target}')
        if args.dry_run or state == 'skip':
            continue
        destination.mkdir(parents=True, exist_ok=True)
        if state == 'update':
            backup_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup_root/name))
            print(f'backup: {backup_root/name}')
        try:
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        except Exception:
            print(f'Installation failed. Any previous version is preserved under {backup_root}.')
            raise


if __name__ == '__main__':
    main()
