"""Recompute every virtual-device experiment (and the two measured-device references) on one common yardstick.
Best baseline = baseline with the highest pooled on-time in that setting (same convention as the source sessions).
"""
import json, statistics as st, csv
from pathlib import Path
H = Path('/home/claude/work/share_in'); VD = Path('/home/claude/work/vd/runs'); RL = Path('/home/claude/work/rlexp/runs')


def norm_other(r):  # sessions 2/3 schema
    return dict(on=r['on_time'], n=r['n'], uon=r['u_on'], un=r['u_n'], J=r['J'], AP=r['AP_mean'], peak=r['AP_peak'], unf=r['unfinished'],
                npu=(r['routes'] or {}).get('classification_NPU', 0), gpu=(r['routes'] or {}).get('classification_GPU', 0), cpu=(r['routes'] or {}).get('classification_CPU', 0))


def norm_mine(r):
    return dict(on=r['on_time'], n=r['planned'], uon=r['U_on'], un=r['U_planned'], J=r['J'], AP=r['AP_mean'], peak=r['AP_peak'], unf=r['unfinished'],
                npu=r['routes']['classification_NPU'], gpu=r['routes']['classification_GPU'], cpu=r['routes']['classification_CPU'])


def summarize(exp, setting, status, pairs, ours, bases, note=''):
    """pairs: {pairkey: {policy: normrow}}"""
    keys = [k for k in pairs if ours in pairs[k] and all(b in pairs[k] for b in bases)]
    pooled = lambda p: sum(pairs[k][p]['on'] for k in keys) / sum(pairs[k][p]['n'] for k in keys) * 100
    bb = max(bases, key=pooled)
    over = [k for k in keys if max(pairs[k][b]['on'] / pairs[k][b]['n'] for b in bases) < .99]
    def block(ks):
        if not ks: return dict(n=0)
        win = sum(pairs[k][ours]['on'] > max(pairs[k][b]['on'] for b in bases) for k in ks)
        tie = sum(pairs[k][ours]['on'] == max(pairs[k][b]['on'] for b in bases) for k in ks)
        d = [100 * pairs[k][ours]['on'] / pairs[k][ours]['n'] - max(100 * pairs[k][b]['on'] / pairs[k][b]['n'] for b in bases) for k in ks]
        o = [pairs[k][ours] for k in ks]; B = [pairs[k][bb] for k in ks]
        cls = sum(x['npu'] + x['gpu'] + x['cpu'] for x in o)
        dJ = [pairs[k][ours]['J'] - pairs[k][bb]['J'] for k in ks if pairs[k][ours]['J'] is not None and pairs[k][bb]['J'] is not None]
        dA = [pairs[k][ours]['AP'] - pairs[k][bb]['AP'] for k in ks if pairs[k][ours]['AP'] is not None and pairs[k][bb]['AP'] is not None]
        dP = [pairs[k][ours]['peak'] - pairs[k][bb]['peak'] for k in ks if pairs[k][ours]['peak'] is not None and pairs[k][bb]['peak'] is not None]
        return dict(n=len(ks), win=win, tie=tie, win_share=win / len(ks), d_pp=st.mean(d), d_min=min(d), d_max=max(d),
                    ours_on=100 * sum(x['on'] for x in o) / sum(x['n'] for x in o), best_on=100 * sum(x['on'] for x in B) / sum(x['n'] for x in B),
                    ours_urg=100 * sum(x['uon'] for x in o) / max(1, sum(x['un'] for x in o)), best_urg=100 * sum(x['uon'] for x in B) / max(1, sum(x['un'] for x in B)),
                    npu_share=sum(x['npu'] for x in o) / cls if cls else None, gpu_share=sum(x['gpu'] for x in o) / cls if cls else None,
                    dJ=st.mean(dJ) if dJ else None, dAP=st.mean(dA) if dA else None, dAP_neg=sum(x < 0 for x in dA) / len(dA) if dA else None,
                    dPeak=st.mean(dP) if dP else None, unf_ours=sum(x['unf'] for x in o), unf_best=sum(x['unf'] for x in B))
    return dict(exp=exp, setting=setting, status=status, ours=ours, best_baseline=bb, baselines=bases, note=note, all=block(keys), overload=block(over))


def load(path, norm, key, pol):
    P = {}
    for l in open(path):
        r = json.loads(l)
        if 'error' in r: continue
        P.setdefault(key(r), {})[pol(r)] = norm(r)
    return P


rows = []
# E0 measured device, regime confirm (session 2)
P = load(H / 'v1/share_minkyu_1017/results/s26_overload_confirm_864.jsonl', norm_other, lambda r: (r['wid'], r['context'], r['stream']), lambda r: r['policy'])
rows.append(summarize('E0 실측기기 과부하 확인', '계수 무변경 · 분류5·탐지3 12부하', '확인 (등록)', P, 'OWN_NW', ['FIFO_PAIR_CN', 'EDF_PAIR_CN', 'FIFO_BF_CN', 'EDF_BF_CN', 'FIFO_BF_CG']))
# E1 throttle k, rule only (dev)
A = [json.loads(l) for l in open(H / 'v1/share_minkyu_1017/results/virtual_rule_k_dev_672.jsonl')]
for k in (1, 2, 4, 8):
    P = {}
    for r in A:
        if r['k'] == k and 'error' not in r: P.setdefault((r['wid'], r['context'], r['stream']), {})[r['policy']] = norm_other(r)
    rows.append(summarize('E1 스로틀 k배 (규칙)', f'모든 AP 계수 ×{k}', '개발만 (확인 없음)', P, 'OWN_NW', ['FIFO_PAIR_CN', 'FIFO_BF_CN', 'EDF_BF_CN']))
# E2 throttle k, residual RL (eval)
A = [json.loads(l) for l in open(H / 'v1/share_minkyu_1017/results/virtual_rl_eval_1680.jsonl')]
for k in (1, 2, 4, 8):
    P = {}
    for r in A:
        if r['k'] == k and 'error' not in r: P.setdefault((r['wid'], r['context'], r['stream']), {})[r['policy']] = norm_other(r)
    for ours in ('RL', 'RULE'):
        rows.append(summarize('E2 스로틀 k배 (잔차 RL)', f'모든 AP 계수 ×{k}', '확인 (등록)', P, ours, ['FIFO_BF_CN', 'EDF_BF_CN', 'FIFO_PAIR_CN']))
    rows.append(summarize('E2 스로틀 k배 (잔차 RL)', f'모든 AP 계수 ×{k}', '확인 (등록)', P, 'RL', ['RULE'], note='RL vs 규칙'))
# E3 NPU thermal-weak (confirm)
A = [json.loads(l) for l in open(H / 'share_minkyu_1017_v2/results/vdev_npu_thermal_confirm_864.jsonl')]
for v in ('T0.5', 'T1.0', 'T2.0'):
    P = {}
    for r in A:
        if r['vid'] == v and 'error' not in r: P.setdefault((r['wid'], r['context'], r['stream']), {})[r['policy']] = norm_other(r)
    rows.append(summarize('E3 NPU 열 취약', f'AP:NPU 계수 = {v[1:]}', '확인 (등록, a=1.0 개발에서 본 뒤)', P, 'OWN_NW', ['FIFO_BF_CN', 'FIFO_BF_ANY', 'EDF_BF_ANY', 'FIFO_PAIR_CN']))
    rows.append(summarize('E3 NPU 열 취약', f'AP:NPU 계수 = {v[1:]}', '확인 (등록, a=1.0 개발에서 본 뒤)', P, 'OWN_NPU', ['FIFO_BF_CN', 'FIFO_BF_ANY', 'EDF_BF_ANY', 'FIFO_PAIR_CN'], note='분해: 우리 규칙 NPU만'))
# E3x explore (dev) — device groups
A = [json.loads(l) for l in open(H / 'share_minkyu_1017_v2/results/vdev_explore_dev.jsonl')]
for v in sorted({r['vid'] for r in A if 'vid' in r}):
    P = {}
    for r in A:
        if r.get('vid') == v and 'error' not in r: P.setdefault((r['wid'], r['context'], r['stream']), {})[r['policy']] = norm_other(r)
    try: rows.append(summarize('E3x 가상기기 탐색', f'기기 {v}', '개발만', P, 'OWN_NW', ['FIFO_BF_CN', 'FIFO_BF_ANY', 'EDF_BF_ANY', 'FIFO_PAIR_CN']))
    except Exception as e: pass
# E4 my 6 devices
for d in ('Ameas_B0', 'Ameas_B1', 'A015_B0', 'A015_B1', 'A030_B0', 'A030_B1'):
    P = load(VD / f'{d}.jsonl', norm_mine, lambda r: json.dumps(r['load'], sort_keys=True), lambda r: r['policy'])
    a = {'meas': '실측', '015': '0.15', '030': '0.30'}[d[1:5].replace('_', '').replace('mea', 'meas')[:4] if False else ('meas' if 'meas' in d else d[1:4])]
    rows.append(summarize('E4 NPU감속 × GPU+NPU동시', f"AP:NPU {a} · 동시실행 {'켬' if d.endswith('1') else '끔'}", '확인 (등록, 6기기 전부)', P, 'RULE', ['FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']))
# E5 my S26 PPO (measured device): eval main + held
for split in ('EVAL', 'HELD'):
    rules = load(RL / f'rules_{split}.jsonl', norm_mine, lambda r: json.dumps([r['load'], r['stream']], sort_keys=True), lambda r: r['policy'])
    for s in (46101, 46103, 46107):
        P = {k: dict(v) for k, v in rules.items()}
        for l in open(RL / f'seed{s}/eval.jsonl'):
            r = json.loads(l)
            if r['split'] == split and r['selected']: P.setdefault(json.dumps([r['load'], r['stream']], sort_keys=True), {})['RL'] = norm_mine(r)
        rows.append(summarize('E5 실측기기 A24-PPO 이식', f'{split} seed {s}', '확인 (등록)', P, 'RL', ['FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']))
        rows.append(summarize('E5 실측기기 A24-PPO 이식', f'{split} seed {s}', '확인 (등록)', P, 'RL', ['RULE'], note='RL vs 규칙'))

json.dump(rows, open(H / 'UNIFIED.json', 'w'), indent=1, ensure_ascii=False)
with open(H / 'UNIFIED.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['실험', '설정', '지위', '우리', '최강 비교군', '비고', '범위', '쌍', '승', '동률', '승 비율', 'Δ정시 평균 %p', 'Δ최소', 'Δ최대', '우리 정시 %', '비교군 정시 %', '우리 긴급 %', '비교군 긴급 %', '우리 NPU 비율', '우리 GPU 비율', 'ΔJ', 'Δ평균AP', 'ΔAP 음수 비율', 'Δ최고AP', '미완료 우리', '미완료 비교군'])
    for r in rows:
        for scope in ('all', 'overload'):
            b = r[scope]
            if not b.get('n'): continue
            w.writerow([r['exp'], r['setting'], r['status'], r['ours'], r['best_baseline'], r['note'], scope, b['n'], b['win'], b['tie'], round(b['win_share'], 3), round(b['d_pp'], 2), round(b['d_min'], 2), round(b['d_max'], 2),
                        round(b['ours_on'], 1), round(b['best_on'], 1), round(b['ours_urg'], 1), round(b['best_urg'], 1),
                        None if b['npu_share'] is None else round(b['npu_share'], 3), None if b['gpu_share'] is None else round(b['gpu_share'], 3),
                        None if b['dJ'] is None else round(b['dJ'], 1), None if b['dAP'] is None else round(b['dAP'], 3), None if b['dAP_neg'] is None else round(b['dAP_neg'], 2),
                        None if b['dPeak'] is None else round(b['dPeak'], 2), b['unf_ours'], b['unf_best']])
for r in rows:
    b = r['overload'] if r['overload'].get('n') else r['all']
    print(f"{r['exp'][:22]:22s} {r['setting'][:26]:26s} {r['ours']:8s} vs {r['best_baseline']:11s} n{b['n']:3d} win {b['win_share']:.2f} d{b['d_pp']:+6.1f} urg {b['ours_urg']:5.1f}/{b['best_urg']:5.1f} NPU {b['npu_share'] if b['npu_share'] is None else round(b['npu_share'],2)} dJ {b['dJ'] if b['dJ'] is None else round(b['dJ'],1)} dAP {b['dAP'] if b['dAP'] is None else round(b['dAP'],3)}")
