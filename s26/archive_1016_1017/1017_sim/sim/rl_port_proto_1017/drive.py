"""PROTOTYPE driver: A24 legacy policy_bridge + A24 learner (unmodified) controlling the S26 engine.

Feasibility only. Not a registered experiment. Costs mirror the A24 train_v2 terminal-cost layout.
"""
import importlib.util, json, os, subprocess, sys, time
import numpy as np, torch

A24 = '/home/claude/work/a24/a24_simulator'
S26 = '/home/claude/work/s26/s26_simulator'
HERE = os.path.dirname(os.path.abspath(__file__))
torch.set_num_threads(1)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m

bridge = load('legacy_bridge', f'{A24}/reference/rolling/policy_bridge.py')   # S26-shaped contract (C:CPU/GPU/NPU, D:CPU, pairs D_CPU+C_GPU/NPU)
learn = load('a24_learner', f'{A24}/reference/rolling/learner.py')            # unmodified PPO

def episode(controller, scenario, stream, out):
    p = subprocess.Popen(['node', f'{HERE}/rl_bridge.cjs', scenario, str(stream), out], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         env={**os.environ, 'S26_ROOT': S26}, text=True, bufsize=1)
    n = 0
    while True:
        line = p.stdout.readline()
        if not line:
            raise RuntimeError('engine closed: ' + str(p.wait()))
        msg = json.loads(line)
        if msg['type'] == 'DONE':
            p.wait(); return msg['summary']
        obs = msg['obs']
        bank = bridge.build_bank(obs, 'JOINT_ATC_RL', allow_wait=True)
        if obs['engine_owner_count'] > 0:          # S26 engine: WAIT only when no owner (physical contract)
            bank['mask'][72:75] = False; bank['physical_mask'][72:75] = False
            if not bank['mask'].any(): bank['mask'][75] = bank['physical_mask'][75] = True
        idx = controller.choose(bank, obs['now_ns'])
        a = bank['actions'][idx]
        p.stdin.write(json.dumps(a) + '\n'); p.stdin.flush(); n += 1

def costs_for(summary, frames):
    s = summary['service']; c = np.zeros((len(frames), 5))
    def miss(k):
        v = s.get(k) or {}; pl = v.get('planned', 0); return (pl - v.get('on_time', 0)) / pl if pl else 0.
    curve = summary.get('curve') or []
    c[-1] = [summary['J_API0_180'] / 100, 0., miss('urgent'), miss('normal'), summary['unfinished'] / 128]
    return c

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'smoke':
        learner = learn.Learner(20261017, 'JOINT_ATC_RL')
        ctl = learner.controller(.95, .5, collect=False)
        t = time.time(); r = episode(ctl, 'R1-4-M128_BASE', 260016200, f'{HERE}/smoke.json')
        print(json.dumps({k: r[k] for k in ('decisions', 'wall_s', 'hard_feasible', 'J_API0_180', 'AP35_180_mean', 'AP_peak_sampled', 'wait_s', 'unfinished', 'route_counts')}, ensure_ascii=False))
        print('frames', len(ctl.frames), 'multi-legal frames', sum(int(f['mask'].sum()) > 1 for f in ctl.frames), 'py wall', round(time.time() - t, 1))
        print('service', json.dumps(r['service'])[:400])
    elif mode == 'train':
        n_ep = int(sys.argv[2]); learner = learn.Learner(20261017, 'JOINT_ATC_RL', learn.Settings(episodes_per_update=8))
        scen = ['R1-4-M128_BASE', 'R1-6-SMOOTH128_BASE']; t = time.time(); log = []
        init = learn.network_digest(learner.net)
        for e in range(n_ep):
            ctl = learner.controller(.95, .5, collect=True)
            r = episode(ctl, scen[e % 2], 260090000 + e, f'{HERE}/train_{e}.json')
            meta = learner.add_episode(ctl.frames, costs_for(r, ctl.frames), .95,
                                       {'U': r['service']['urgent']['planned'], 'N': r['service']['normal']['planned']})
            log.append(dict(ep=e, frames=len(ctl.frames), feas=r['hard_feasible'], J=r['J_API0_180'], routes=r['route_counts']))
        print(json.dumps(log[-2:], ensure_ascii=False)); print('updates', learner.updates, 'adam', learner.steps, 'logs', learner.logs[-1] if learner.logs else None)
        print('network changed', init != learn.network_digest(learner.net), 'wall', round(time.time() - t, 1))
