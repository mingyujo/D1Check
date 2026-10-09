"""Recompute six energy rows and 18 AP rows from shared derived inputs; no ADB/fit."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.d1_ap_tail_observation_results import assess_case, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    original_path = ROOT / 'docs/results/online_policy_study_01/overnight_sustained_run01/model.json'
    candidates_path = ROOT / 'docs/results/ap_tail_identification_01/run_v2/candidates.json'
    for path, expected in (
        (original_path, '5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'),
        (candidates_path, 'aa28410d701c9810001a4e6c176823e7d2b446f46f980ebeab3ff14f4540cc84'),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('frozen model bytes changed')
    original, candidates = read(original_path), read(candidates_path)
    with gzip.open(Path(__file__).with_name('inputs.json.gz'), 'rt', encoding='utf8') as f:
        cases = json.load(f)
    metrics, energy = [], []
    for case in cases:
        _, rows, energies = assess_case(case, original, candidates)
        label = case['policy']
        metrics.extend(dict(session=label, **row) for row in rows)
        energy.extend(dict(session=label, **row) for row in energies)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    for name, rows in (('metrics.csv', metrics), ('energy.csv', energy)):
        with (out / name).open('w', newline='', encoding='utf8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(dict(metrics_rows=len(metrics), energy_rows=len(energy), fit_calls=0,
                          device_commands=0, output=str(out))))


if __name__ == '__main__':
    main()
