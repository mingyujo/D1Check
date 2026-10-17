"""PREREG_VD_1017 §3 judgement."""
import json, statistics as st
from pathlib import Path
from run_vd import DEVICES
D = Path(__file__).resolve().parent / 'runs'
BASE = ['FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']
rate = lambda r: 100 * r['on_time'] / r['planned']
out = {}
for d in DEVICES:
    rows = [json.loads(x) for x in open(D / f"{d['name']}.jsonl")]
    errs = [r for r in rows if 'error' in r]
    by = {}
    for r in rows:
        if 'error' in r: continue
        assert r['on_time'] <= r['completed'] and r['completed'] + r['unfinished'] == r['planned'], 'conservation'
        by.setdefault(json.dumps(r['load'], sort_keys=True), {})[r['policy']] = r
    gen = [k for k in by if json.loads(k)['kind'] == 'GEN']
    rule_gen = [by[k]['RULE'] for k in gen]
    cls = lambda rs, x: sum(r['routes']['classification_' + x] for r in rs)
    tot = sum(cls(rule_gen, x) for x in ('CPU', 'GPU', 'NPU'))
    npu, gpu = cls(rule_gen, 'NPU') / tot, cls(rule_gen, 'GPU') / tot
    S = npu <= .9 and gpu >= .1
    over = [k for k in by if max(rate(by[k][p]) for p in BASE) < 99]
    dd = [rate(by[k]['RULE']) - max(rate(by[k][p]) for p in BASE) for k in over]
    H1 = None if len(over) < 10 else (sum(x >= .5 for x in dd) / len(dd) >= .8 and st.mean(dd) > .5)
    th = {}
    if over:
        for m in ('J', 'AP_mean', 'AP_peak'):
            v = [by[k]['RULE'][m] - by[k]['FIFO_FREE'][m] for k in over if by[k]['RULE'][m] is not None and by[k]['FIFO_FREE'][m] is not None]
            th[m] = {'mean': st.mean(v) if v else None, 'neg_share': sum(x < 0 for x in v) / len(v) if v else None, 'n': len(v)}
    th_claim = bool(over) and th['AP_mean']['n'] > 0 and abs(th['AP_mean']['mean']) > .18 and max(th['AP_mean']['neg_share'], 1 - th['AP_mean']['neg_share']) >= .8
    mean_on = {p: st.mean(rate(by[k][p]) for k in over) for p in ['RULE'] + BASE} if over else {}
    fifo_gen = [by[k]['FIFO_FREE'] for k in gen]; ftot = sum(cls(fifo_gen, x) for x in ('CPU', 'GPU', 'NPU'))
    out[d['name']] = {'errors': len(errs), 'runs': len(rows), 'rule_NPU_share': npu, 'rule_GPU_share': gpu, 'FIFO_FREE_NPU_share': cls(fifo_gen, 'NPU') / ftot,
                      'S_no_concentration': S, 'overload_pairs': len(over),
                      'H1': {'pass': H1, 'mean_pp': st.mean(dd) if dd else None, 'share_ge_0.5': sum(x >= .5 for x in dd) / len(dd) if dd else None, 'min_pp': min(dd) if dd else None},
                      'MEANINGFUL': bool(S and H1), 'mean_on_time_overload': mean_on, 'thermal_energy_vs_FIFO_FREE': th, 'thermal_claim': th_claim,
                      'unfinished_rule_total': sum(by[k]['RULE']['unfinished'] for k in by)}
json.dump(out, open(D / 'JUDGEMENT_VD.json', 'w'), indent=1)
for n, v in out.items():
    print(n, 'err', v['errors'], '| NPU', round(v['rule_NPU_share'], 2), 'GPU', round(v['rule_GPU_share'], 2), 'S', v['S_no_concentration'], '| over', v['overload_pairs'],
          'H1', v['H1']['pass'], None if v['H1']['mean_pp'] is None else round(v['H1']['mean_pp'], 2), None if v['H1']['share_ge_0.5'] is None else round(v['H1']['share_ge_0.5'], 2),
          '| MEANINGFUL', v['MEANINGFUL'], '| dJ', None if not v['thermal_energy_vs_FIFO_FREE'] else round(v['thermal_energy_vs_FIFO_FREE']['J']['mean'] or 0, 1),
          'dAP', None if not v['thermal_energy_vs_FIFO_FREE'] else round(v['thermal_energy_vs_FIFO_FREE']['AP_mean']['mean'] or 0, 3))
