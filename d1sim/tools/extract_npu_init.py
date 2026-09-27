"""NPU CompiledModel init span (event=compiled_model_init, latency_ms) from 9/25 formal + 0927 C4. READ-ONLY.
Excludes runs not (slot_status completed & validation valid) in exports-v2/run_summary.csv, and runs with any
d1check telemetry sample plugged != 0 (CLAUDE.md 무효 수치 규칙). Usage: py d1sim/tools/extract_npu_init.py"""
import csv, glob, json, os, statistics as st
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
out = {}
for res in ('results/S26_NPU_formal_0925b', 'results/S26_C4_npu_runonly_0927'):
    d = os.path.join(ROOT, res)
    summ = {r['run_id']: r for r in csv.DictReader(open(os.path.join(d, 'exports-v2', 'run_summary.csv'), encoding='utf-8'))}
    vals, excl = [], []
    for rid, r in sorted(summ.items()):
        ok = r.get('slot_status') == 'completed' and r.get('validation_status') == 'valid'
        plugged = any('"plugged":' in l and '"plugged":0' not in l
                      for l in open(os.path.join(d, 'runs', rid, 'raw', 'logcat.jsonl'), encoding='utf-8') if '"event":"sample"' in l)
        ev = [json.loads(l) for f in glob.glob(os.path.join(d, 'runs', rid, 'gpu', '*.jsonl'))
              for l in open(f, encoding='utf-8') if '"event":"compiled_model_init"' in l]
        if not ok or plugged or not ev:
            excl.append(dict(run=rid, slot=r['slot_id'], ok=ok, plugged=plugged, n_ev=len(ev))); continue
        vals.append(dict(run=rid, slot=r['slot_id'], init_ms=ev[0]['latency_ms'], status=ev[0].get('status')))
    ms = [v['init_ms'] for v in vals]
    out[res] = dict(n=len(ms), median_ms=st.median(ms) if ms else None, min_ms=min(ms, default=None),
                    max_ms=max(ms, default=None), runs=vals, excluded=excl)
p = os.path.join(ROOT, 'd1sim', 'out', 'npu_init_span.json')
json.dump(out, open(p, 'w', encoding='utf-8'), indent=1)
for k, v in out.items():
    print(k, v['n'], v['median_ms'], v['min_ms'], v['max_ms'], 'excluded', len(v['excluded']))
