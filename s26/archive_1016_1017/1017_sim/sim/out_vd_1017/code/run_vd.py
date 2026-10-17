"""Run all 6 virtual devices (PREREG_VD_1017 §1-2). python3 run_vd.py <device_index...>"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DEVICES = [dict(name=f"A{a}_B{int(b)}", npu_ap_coef=c, accel_pair=b) for a, c in (('meas', None), ('015', .15), ('030', .30)) for b in (False, True)]
SLOTS = ['R3-0-M128_WAIT200x16', 'R3-1-M128_BASE', 'R3-2-SMOOTH128_BASE', 'R3-3-M128_NPU_SERIAL', 'R3-4-M128_ORDER', 'R3-5-SMOOTH128_PAIR_G', 'R3-6-M128_PAIR_G']
GEN = [dict(kind='GEN', dur=25, gap=g, mixC=c, mixD=d, shape=sh) for (c, d) in ((7, 1), (6, 2), (5, 3)) for g in (0.4, 0.537) for sh in ('burst', 'smooth')]
POL = ['RULE', 'FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']
if __name__ == '__main__':
    for i in map(int, sys.argv[1:]):
        d = DEVICES[i]; vd = {'accel_pair': d['accel_pair']}
        if d['npu_ap_coef'] is not None: vd['npu_ap_coef'] = d['npu_ap_coef']
        jobs = [dict(policy=p, stream=3000, load=l) for s in SLOTS for l in [dict(kind='R21', slot=s)] + [{**g, 'slot': s} for g in GEN] for p in POL]
        jf = f'{HERE}/runs/jobs_{d["name"]}.json'; os.makedirs(f'{HERE}/runs', exist_ok=True); json.dump(jobs, open(jf, 'w'))
        env = {**os.environ, 'S26_ENGINE_DIR': f'{HERE}/engine', 'S26_VD_JSON': json.dumps(vd)}
        with open(f'{HERE}/runs/{d["name"]}.jsonl', 'w') as out:
            subprocess.run(['node', f'{HERE}/lab_vd.cjs', jf], stdout=out, env=env, check=True)
        print('done', d['name'], len(jobs), flush=True)
