"""Pinned A24 intact vectors; realized samples are engine-only, not input features."""
import csv,hashlib,statistics
from pathlib import Path
from tools import d1_empirical_request_policy as p
CSV=Path(__file__).resolve().parents[1]/"docs/results/overnight_device_20261011/requests.csv"
SHA="08421e953cd3ee606ff1d9e6cbc53e649a86a62548791a1494b3279e9953bce9"
def load_pool():
    groups={k:[] for k in p.CELLS}
    for i,row in enumerate(csv.DictReader(CSV.open(encoding='utf-8-sig',newline=''))):
        if row['terminal_status']!='succeeded':raise ValueError('empirical denominator changed')
        q=dict(task=row['task_id'],priority=row['priority'])
        ts=[float(row[k])*1e6 for k in ('dispatch_ms','execution_start_ms','output_ready_ms','persist_complete_ms','worker_release_ms','lane_available_ms')]
        ds=[round(y-x) for x,y in zip(ts,ts[1:])]
        if len(ds)!=5 or min(ds)<0:raise ValueError('invalid intact empirical phases')
        groups[p.key(q,row['backend'])].append(dict(source_request_id=f"ABBA{row['index']}/row{i}",durations_ns=ds))
    if [len(groups[k]) for k in p.CELLS]!=[4,188,192]:raise ValueError('source roster changed')
    return groups
POOL=load_pool()
FULL_SHA=hashlib.sha256(CSV.read_bytes()).hexdigest()
if FULL_SHA!=SHA:raise ValueError('known ABBA identity changed')
MEANS={key:[statistics.mean(x['durations_ns'][j] for x in rows) for j in range(5)] for key,rows in POOL.items()}
