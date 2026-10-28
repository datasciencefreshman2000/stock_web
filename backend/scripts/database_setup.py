"""Build a repeatable SQL setup file without reading credentials or changing any DB."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def build_sql():
    sources = [ROOT / 'backend/sql/schema.sql', *sorted((ROOT / 'backend/sql/migrations').glob('*.sql'))]
    parts = []
    for source in sources:
        # Old scripts seeded personal example balances. New databases start empty.
        sql = re.sub(r'(?im)^insert into\b[\s\S]*?;', '', source.read_text(encoding='utf-8'))
        parts.append(f'-- Source: {source.relative_to(ROOT).as_posix()}\n{sql}')
    for source in sorted((ROOT / 'supabase/migrations').glob('*.sql')):
        parts.append(f'-- Source: {source.relative_to(ROOT).as_posix()}\n{source.read_text(encoding="utf-8")}')
    return '\n\n'.join(parts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'tmp/database_setup.sql')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_sql(), encoding='utf-8')
    print(f'Generated SQL only; no database was changed: {args.output.resolve()}')
