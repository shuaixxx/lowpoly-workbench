"""Check publish-set integrity, provenance, sample status and portable links without Blender."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'skills/lowpoly-workbench/scripts'))
import mesh_cases


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    rules = read_json(ROOT/'skills/lowpoly-workbench/references/lowpoly-rules.json')
    source = rules['sources']['project-document']
    original = ROOT/source['file']
    assert hashlib.sha256(original.read_bytes()).hexdigest() == source['sha256'], 'Original document hash changed'
    assert len(original.read_text(encoding='utf-8-sig').splitlines()) == source['lines']
    assert [r['id'] for r in rules['rules']] == [f'LP-{n:03d}' for n in range(1, 17)]
    for rule in rules['rules']:
        lines = rule.get('source_lines', [])
        assert len(lines) % 2 == 0
        assert all(1 <= start <= end <= source['lines'] for start, end in zip(lines[::2], lines[1::2]))
    third_party = read_json(ROOT/'third-party.json')
    assert len(third_party['commit']) == 40 and third_party['license'] == 'MIT'
    upstream = read_json(ROOT/'third-party-sha256.json')
    for relative, expected in upstream.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == expected, f'Pinned upstream file changed: {relative}'
    for name in third_party['bundled_skills']:
        assert 'MIT License' in (ROOT/'skills'/name/'LICENSE').read_text(encoding='utf-8')
    for name in ('lowpoly-workbench', *third_party['bundled_skills']):
        assert (ROOT/'skills'/name/'SKILL.md').is_file()

    # Only maintained files are checked for local paths; untouched third-party text is archived as-is.
    maintained = [ROOT/'README.md', ROOT/'AGENTS.md', ROOT/'THIRD_PARTY.md']
    for directory in ('docs', 'tools', 'skills/lowpoly-workbench', 'examples'):
        maintained.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.md', '.py', '.json', '.yaml', '.txt'))
    forbidden = [re.compile(r'[A-Za-z]:[\\/]Users[\\/]', re.I),
                 re.compile(r'[A-Za-z]:[\\/]GPT' + r'zoom[\\/]', re.I),
                 re.compile(r'gh' + r'[pousr]_[A-Za-z0-9]{25,}'),
                 re.compile(r'github' + r'_pat_[A-Za-z0-9_]{25,}')]
    for path in maintained:
        text = path.read_text(encoding='utf-8-sig')
        assert not any(pattern.search(text) for pattern in forbidden), f'Local path or token-like text: {path.relative_to(ROOT)}'
        if path.suffix == '.md':
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if '://' in target or target.startswith('#'):
                    continue
                relative = unquote(target.split('#', 1)[0].strip('<>'))
                assert (path.parent/relative).exists(), f'Broken local link in {path.relative_to(ROOT)}: {target}'
    files = [p for directory in ('tools', 'skills') for p in (ROOT/directory).rglob('*.py')]
    for path in files:
        compile(path.read_text(encoding='utf-8-sig'), str(path.relative_to(ROOT)), 'exec')
    for path in ROOT.rglob('*.json'):
        if '.local' not in path.parts and '.git' not in path.parts:
            read_json(path)

    sample = ROOT/'examples/scenario-002'
    cases = [read_json(path) for path in sorted((sample/'cases').glob('*.json'))]
    assert len(cases) == 4
    for case in cases:
        mesh_cases.validate_record(case)
        assert case['status'] == 'unreviewed' and not case.get('review')
        assert all(weight is None for weight in case['importance']['weights'])
    uri = (sample/'cases.sqlite3').as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        stored = {case['id']: case for (raw,) in conn.execute('SELECT record_json FROM cases') for case in [json.loads(raw)]}
        assert stored == {case['id']: case for case in cases}, 'Sample index differs from JSON sources'
    finally:
        conn.close()
    report = read_json(sample/'report.json')
    assert report['status'] == 'passed' and report['prototype_version'] == rules['version']
    assert report['scenario_commit'] == third_party['commit']
    assert report['blend_reopened'] and not report['user_asset_modified']
    assert not report['weights_painted'] and not report['bake_verified']
    assert report['user_acceptance'] == 'pending'
    assert (ROOT/report['blend']).is_file() and (ROOT/report['database']).is_file()
    assert all((ROOT/path).is_file() for path in report['review_sheets'])
    print(json.dumps({'status': 'passed', 'version': rules['version'], 'rules': len(rules['rules']),
                      'synthetic_cases': len(cases), 'accepted_cases': 0, 'python_files_compiled': len(files)}, indent=2))


if __name__ == '__main__':
    main()
