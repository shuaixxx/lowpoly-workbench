"""Build a new local SQLite index from the committed synthetic JSON cases."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'skills/lowpoly-workbench/scripts'))
import mesh_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Output already exists; choose a new database path.')
    records = [json.loads(path.read_text(encoding='utf-8'))
               for path in sorted((ROOT/'examples/scenario-002/cases').glob('*.json'))]
    if len(records) != 4 or any(record['status'] != 'unreviewed' for record in records):
        raise SystemExit('Expected four unreviewed synthetic cases.')
    for record in records:
        mesh_cases.validate_record(record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for record in records:
        mesh_cases.add_case(args.out, record)
    with mesh_cases.connect(args.out) as conn:
        result = dict(conn.execute('SELECT status,COUNT(*) FROM cases GROUP BY status'))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
