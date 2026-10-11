"""Export conservative seed reservations for an offline desktop handoff."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect(root=ROOT):
    candidates = set()
    for pattern in ('*/registration*.json', '*/inputs.json', '*/*/registration*.json', '*/*/inputs.json'):
        candidates.update((root / 'output').glob(pattern))
    for pattern in ('*/execution_contract.json', '*/contract.json', '*/cases.json', '*/*/execution_contract.json'):
        candidates.update((root / 'docs/results').glob(pattern))
    seeds, ranges, receipts = set(), set(), []

    def walk(value, name=''):
        if isinstance(value, dict):
            for key, child in value.items():
                # Do not interpret random numeric substrings in source hashes.
                if 'sha' not in key.lower() and key.lower() not in ('sources', 'rng'):
                    walk(child, key.lower())
        elif isinstance(value, list):
            if 'seed' in name and 'range' in name and len(value) == 2 and all(type(v) is int for v in value):
                if 0 <= value[0] <= value[1]:
                    ranges.add(tuple(value))
            for child in value:
                walk(child, name)
        elif type(value) is int and 'seed' in name and value >= 0:
            seeds.add(value)
        elif isinstance(value, str) and ('seed' in name or name in ('confirmation', 'training', 'development')):
            seeds.update(int(v) for v in re.findall(r'(?<!\d)[89]\d{8}(?!\d)', value))
            for lo, short in re.findall(r'([89]\d{8})\.\.([89]?\d{1,9})', value):
                upper = lo[:-len(short)] + short if len(short) < len(lo) else short
                if int(lo) <= int(upper):
                    ranges.add((int(lo), int(upper)))

    for path in sorted(candidates):
        raw = path.read_bytes()
        value = json.loads(raw.decode('utf-8-sig'))
        before = len(seeds), len(ranges)
        walk(value)
        if before != (len(seeds), len(ranges)):
            receipts.append(dict(logical_path=path.relative_to(root).as_posix(), sha256=hashlib.sha256(raw).hexdigest()))
    if not {833110101, 835110101, 834010001} <= seeds | {v for lo, hi in ranges for v in (lo, hi)}:
        raise ValueError('known latest sibling train/confirmation reservations missing')
    return dict(version='arrival_seed_registry_v1', seeds=sorted(seeds), ranges=[list(r) for r in sorted(ranges)],
        source_receipts=receipts, not_all_seeds_are_independent=True,
        scope='conservative exported registrations and case metadata at export; not a cross-computer live registry',
        initialization_and_realization_seeds_may_be_conservatively_reserved=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/desktop_handoff_20261011_v1/arrival_seed_registry.json')
    args = parser.parse_args()
    data = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status='exported', seeds=len(data['seeds']), ranges=len(data['ranges']),
        source_receipts=len(data['source_receipts']), native=0, learning=0, device=0)))


if __name__ == '__main__':
    main()
