"""DEV selection and one-shot EVAL (PREREG §3-§4).
python3 evaluate.py dev  <seed>        -> runs/seed<seed>/dev.jsonl (all checkpoints) + selected.json
python3 evaluate.py rules <split>      -> runs/rules_<split>.jsonl   (split = DEV | EVAL | HELD)
python3 evaluate.py eval <seed>        -> runs/seed<seed>/eval.jsonl (selected + EP000, EVAL main + HELD)
"""
import json, os, sys, time
import rl_lab as R, train as T

RULES = ['RULE', 'RULE_NOWAIT', 'FIFO_FREE', 'EDF_FREE', 'FIFO_PAIR_CN', 'FIFO_PAIR_CG']
STREAMS = {'DEV': [2000], 'EVAL': [3000, 3001], 'HELD': [3000, 3001]}


def jobs(split):
    ld = T.loads('EVAL', held=True) if split == 'HELD' else T.loads(split)
    return [(l, s) for l in ld for s in STREAMS[split]]


def score(rows):  # A24 train_v2 score, lexicographic
    short = []
    for r in rows:
        for p in ('U', 'N'):
            if r[p + '_planned']:
                short.append(max(0, .95 - r[p + '_on'] / r[p + '_planned']))
    Js = [r['J'] for r in rows if r['J'] is not None]
    return [sum(r['unfinished'] for r in rows), sum(short) / len(short), sum(Js) / max(1, len(Js)),
            sum(r['AP_mean'] for r in rows if r['AP_mean'] is not None) / len(rows)]


if __name__ == '__main__':
    mode, arg = sys.argv[1], sys.argv[2]
    eng = R.Engine(); t0 = time.time()
    if mode == 'dev':
        d = f'{R.HERE}/runs/seed{arg}'; f = open(f'{d}/dev.jsonl', 'w'); ranking = []
        for ep in T.CKPTS:
            rows = []
            for load, st in jobs('DEV'):
                s = eng.rl(R.frozen_controller(f'{d}/EP{ep:03d}.pt'), load, st); s.update(ckpt=ep, load=load); rows.append(s)
                f.write(json.dumps(s) + '\n'); f.flush()
            ranking.append({'episode': ep, 'score': score(rows)})
        sel = min(ranking, key=lambda x: (x['score'], x['episode']))
        json.dump({'ranking': ranking, 'selected_episode': sel['episode'], 'rule': 'A24 score lexicographic; ties -> earlier episode'}, open(f'{d}/selected.json', 'w'), indent=1)
        print('seed', arg, 'selected', sel['episode'], ranking)
    elif mode == 'rules':
        f = open(f'{R.HERE}/runs/rules_{arg}.jsonl', 'w')
        for load, st in jobs(arg):
            for p in RULES:
                s = eng.rule(p, load, st); s['load'] = load; f.write(json.dumps(s) + '\n'); f.flush()
    elif mode == 'eval':
        d = f'{R.HERE}/runs/seed{arg}'; sel = json.load(open(f'{d}/selected.json'))['selected_episode']
        f = open(f'{d}/eval.jsonl', 'w')
        for split in ('EVAL', 'HELD'):
            for ep in sorted({sel, 0}):
                for load, st in jobs(split):
                    s = eng.rl(R.frozen_controller(f'{d}/EP{ep:03d}.pt'), load, st)
                    s.update(ckpt=ep, selected=(ep == sel), split=split, load=load); f.write(json.dumps(s) + '\n'); f.flush()
    eng.close(); print(mode, arg, 'wall', round(time.time() - t0))
