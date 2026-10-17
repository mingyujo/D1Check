"""PREREG §4 judgement. Reads runs/rules_EVAL.jsonl, rules_HELD.jsonl, rules_DEV.jsonl, seed*/eval.jsonl, seed*/dev.jsonl."""
import json, statistics as st, sys
from pathlib import Path

D = Path(__file__).resolve().parent / 'runs'
SEEDS = [46101, 46103, 46107]
BASE = ['FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']
OURS = ['RULE', 'RULE_NOWAIT']
M = 0.5  # %p margin


def key(r):
    l = r['load']; return json.dumps([l, r['stream']], sort_keys=True)


def rate(r):
    return 100 * r['on_time'] / r['planned']


def read(p):
    return [json.loads(x) for x in open(p)] if Path(p).exists() else []


def index(rows):
    out = {}
    for r in rows:
        out.setdefault(key(r), {})[r['policy']] = r
    return out


def test(rl, ref_rows, refs, pairs):
    """Return pass-flag + stats for RL - max(ref) on-time %p over the given pairs."""
    d = []
    for k in pairs:
        best = max(rate(ref_rows[k][p]) for p in refs)
        d.append(rate(rl[k]) - best)
    win = sum(x >= M for x in d) / len(d); eq = sum(abs(x) < M for x in d) / len(d)
    return {'n': len(d), 'mean_pp': st.mean(d), 'min_pp': min(d), 'max_pp': max(d), 'share_ge_margin': win, 'share_equal': eq,
            'pass': win >= .8 and st.mean(d) > M}


def run(split):
    rules = index(read(D / f'rules_{split}.jsonl'))
    res = {}
    for s in SEEDS:
        ev = [r for r in read(D / f'seed{s}/eval.jsonl') if r['split'] == split]
        sel = {key(r): r for r in ev if r['selected']}
        ep0 = {key(r): r for r in ev if r['ckpt'] == 0}
        if not sel:
            continue
        gen = [k for k in sel if json.loads(k)[0]['kind'] == 'GEN']
        r21 = [k for k in sel if json.loads(k)[0]['kind'] == 'R21']
        out = {'selected_episode': next(iter(sel.values()))['ckpt'],
               'H1_vs_best_baseline': test(sel, rules, BASE, gen),
               'H2_vs_our_rule': test(sel, rules, OURS, gen),
               'control_EP0_vs_best_baseline': test(ep0, rules, BASE, gen) if ep0 else None,
               'rule_vs_best_baseline': test({k: max((rules[k][p] for p in OURS), key=rate) for k in gen}, rules, BASE, gen)}
        if r21:
            guard = all(sel[k]['on_time'] == sel[k]['planned'] for k in r21)
            dap = [sel[k]['AP_mean'] - rules[k]['FIFO_FREE']['AP_mean'] for k in r21]
            dj = [sel[k]['J'] - rules[k]['FIFO_FREE']['J'] for k in r21]
            same = max(sum(x < 0 for x in dap), sum(x > 0 for x in dap)) / len(dap)
            out['H3_R21'] = {'n': len(r21), 'guard_all_on_time': guard, 'dAP_mean': st.mean(dap), 'dAP_same_sign_share': same,
                             'thermal_difference': guard and abs(st.mean(dap)) > .18 and same >= .8,
                             'dJ_mean': st.mean(dj), 'dJ_negative_share': sum(x < 0 for x in dj) / len(dj),
                             'rule_guard': all(rules[k]['RULE']['on_time'] == rules[k]['RULE']['planned'] for k in r21)}
        # per-policy mean on-time for the table
        out['mean_on_time_pct'] = {'RL': st.mean(rate(sel[k]) for k in gen), 'RL_EP0': st.mean(rate(ep0[k]) for k in gen) if ep0 else None,
                                   **{p: st.mean(rate(rules[k][p]) for k in gen) for p in BASE + OURS}}
        out['mean_J'] = {'RL': st.mean(sel[k]['J'] for k in gen if sel[k]['J'] is not None), **{p: st.mean(rules[k][p]['J'] for k in gen if rules[k][p]['J'] is not None) for p in BASE + OURS}}
        out['mean_AP'] = {'RL': st.mean(sel[k]['AP_mean'] for k in gen if sel[k]['AP_mean'] is not None), **{p: st.mean(rules[k][p]['AP_mean'] for k in gen if rules[k][p]['AP_mean'] is not None) for p in BASE + OURS}}
        res[s] = out
    seeds_pass = {h: sum(res[s][h]['pass'] for s in res) for h in ('H1_vs_best_baseline', 'H2_vs_our_rule')}
    h2_equal = sum(res[s]['H2_vs_our_rule']['share_equal'] >= .8 for s in res)
    verdict = {
        'H1': 'RL 우위 확인 (과부하 서비스)' if seeds_pass['H1_vs_best_baseline'] >= 2 else '미확인',
        'H2': 'RL 추가 기여 확인' if seeds_pass['H2_vs_our_rule'] >= 2 else ('동등' if h2_equal >= 2 else '미확인 (혼재 또는 열세)'),
        'H3': None if split == 'HELD' else ('열 차이 있음' if sum(res[s]['H3_R21']['thermal_difference'] for s in res) >= 2 else '모형 오차 안'),
        'seeds_pass': seeds_pass, 'H2_equal_seeds': h2_equal}
    return {'split': split, 'verdict': verdict, 'per_seed': res}


def dev_gap():
    rules = index(read(D / 'rules_DEV.jsonl')); out = {}
    for s in SEEDS:
        sel = json.load(open(D / f'seed{s}/selected.json'))['selected_episode']
        dv = {key(r): r for r in read(D / f'seed{s}/dev.jsonl') if r['ckpt'] == sel}
        gen = [k for k in dv if json.loads(k)[0]['kind'] == 'GEN']
        out[s] = test(dv, rules, BASE, gen)['mean_pp']
    return out


if __name__ == '__main__':
    rep = {'EVAL': run('EVAL'), 'HELD': run('HELD'), 'DEV_mean_pp_vs_best_baseline': dev_gap()}
    json.dump(rep, open(D / 'JUDGEMENT.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: (v['verdict'] if isinstance(v, dict) and 'verdict' in v else v) for k, v in rep.items()}, ensure_ascii=False, indent=1))
