"""Train one seed (PREREG §3). Usage: python3 train.py <seed> <episodes>"""
import json, os, random, sys, time
import rl_lab as R

SLOTS = {'TRAIN': [f'R1-{i}' for i in range(7)], 'DEV': [f'R2-{i}' for i in range(7)], 'EVAL': [f'R3-{i}' for i in range(7)]}
GEN = [dict(kind='GEN', dur=25, gap=g, mixC=c, mixD=d, shape=sh) for g in (0.537, 0.65) for (c, d) in ((6, 2), (5, 3)) for sh in ('burst', 'smooth')]
HELD = [dict(kind='GEN', dur=50, gap=0.6, mixC=5, mixD=3, shape=sh) for sh in ('burst', 'smooth')]


def loads(split, held=False):
    out = []
    for s in SLOTS[split]:
        sid = SLOT_IDS[s]
        if held:
            out += [{**g, 'slot': sid} for g in HELD]
        else:
            out += [{'kind': 'R21', 'slot': sid}] + [{**g, 'slot': sid} for g in GEN]
    return out


SLOT_IDS = {}
for sid in ['R1-0-M128_PAIR_G', 'R1-1-M128_ORDER', 'R1-2-M128_WAIT200x16', 'R1-3-SMOOTH128_PAIR_G', 'R1-4-M128_BASE', 'R1-5-M128_NPU_SERIAL', 'R1-6-SMOOTH128_BASE',
            'R2-0-M128_WAIT200x16', 'R2-1-SMOOTH128_PAIR_G', 'R2-2-SMOOTH128_BASE', 'R2-3-M128_BASE', 'R2-4-M128_PAIR_G', 'R2-5-M128_NPU_SERIAL', 'R2-6-M128_ORDER',
            'R3-0-M128_WAIT200x16', 'R3-1-M128_BASE', 'R3-2-SMOOTH128_BASE', 'R3-3-M128_NPU_SERIAL', 'R3-4-M128_ORDER', 'R3-5-SMOOTH128_PAIR_G', 'R3-6-M128_PAIR_G']:
    SLOT_IDS[sid[:4]] = sid

CKPTS = (0, 64, 128, 256, 512)

if __name__ == '__main__':
    seed, n = int(sys.argv[1]), int(sys.argv[2])
    out = f'{R.HERE}/runs/seed{seed}'; os.makedirs(out, exist_ok=True)
    rng = random.Random(seed); pool = loads('TRAIN')
    learner = R.learn.Learner(seed, 'JOINT_ATC_RL', R.learn.Settings(episodes_per_update=8))
    eng = R.Engine(); log = open(f'{out}/train_log.jsonl', 'a'); t0 = time.time()
    learner.save_snapshot(f'{out}/EP000.pt')
    for e in range(1, n + 1):
        load = rng.choice(pool); stream = 1_000_000 + 10_000 * seed + e
        ctl = learner.controller(.95, .5, collect=True)
        s = eng.rl(ctl, load, stream)
        meta = learner.add_episode(ctl.frames, R.episode_costs(s, len(ctl.frames)), .95, {'U': s['U_planned'], 'N': s['N_planned']})
        log.write(json.dumps({'ep': e, 'load': load, 'stream': stream, 'on_time': s['on_time'], 'planned': s['planned'], 'unfinished': s['unfinished'],
                              'J': s['J'], 'AP_mean': s['AP_mean'], 'routes': s['routes'], 'wait_s': s['wait_s'], 'frames': len(ctl.frames),
                              'updates': learner.updates, 'duals': learner.duals[3].tolist(), 'wall': round(time.time() - t0, 1)}) + '\n'); log.flush()
        if e in CKPTS:
            learner.save_snapshot(f'{out}/EP{e:03d}.pt')
    eng.close()
    print('done seed', seed, 'updates', learner.updates, 'adam', learner.steps, 'wall', round(time.time() - t0))
