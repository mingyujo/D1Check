"""S26 롤링+ATC+RL experiment driver.

A24 policy bridge (reference/rolling/policy_bridge.py, S26-shaped contract) and A24 learner.py are loaded
UNMODIFIED. The only S26-specific rules live in `adapt_mask` (registered in PREREG §3).
"""
import importlib.util, json, os, subprocess, sys, time, hashlib, random
import numpy as np, torch

A24 = os.environ.get('A24_ROOT', '/home/claude/work/a24/a24_simulator')
S26 = os.environ.get('S26_ROOT', '/home/claude/work/s26/s26_simulator')
HERE = os.path.dirname(os.path.abspath(__file__))
torch.set_num_threads(1)
NS = 10**9


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m


bridge = load('a24_legacy_bridge', f'{A24}/reference/rolling/policy_bridge.py')
learn = load('a24_learner', f'{A24}/reference/rolling/learner.py')
SOURCE_SHA = {p: hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in
              [f'{A24}/reference/rolling/policy_bridge.py', f'{A24}/reference/rolling/learner.py',
               f'{HERE}/rl_server.cjs', f'{HERE}/lab.cjs', __file__]}


def adapt_mask(bank, obs):
    """S26 physical contract on top of the A24 bank (registered): WAIT only with no owner, and
    cumulative WAIT <= 2 s. If nothing legal remains, RESOURCE_WAIT (engine advances time)."""
    for j, d in zip(range(72, 75), bridge.WAIT_DURATIONS_NS):
        if obs['engine_owner_count'] > 0 or obs['wait_used_ns'] + d > obs['wait_cap_ns']:
            bank['mask'][j] = False; bank['physical_mask'][j] = False
    if not bank['mask'].any():
        bank['mask'][75] = bank['physical_mask'][75] = True
    return bank


class Engine:
    def __init__(self):
        self.p = subprocess.Popen(['node', f'{HERE}/rl_server.cjs'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  env={**os.environ, 'S26_ROOT': S26}, text=True, bufsize=1)

    def _send(self, o):
        self.p.stdin.write(json.dumps(o) + '\n'); self.p.stdin.flush()

    def rule(self, policy, load, stream):
        self._send({'cmd': 'rule', 'policy': policy, 'load': load, 'stream': stream})
        return json.loads(self.p.stdout.readline())['summary']

    def rl(self, controller, load, stream):
        self._send({'cmd': 'run', 'load': load, 'stream': stream})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError('engine died rc=%s' % self.p.poll())
            m = json.loads(line)
            if m['type'] == 'DONE':
                return m['summary']
            obs = m['obs']
            bank = adapt_mask(bridge.build_bank(obs, 'JOINT_ATC_RL', allow_wait=True), obs)
            idx = controller.choose(bank, obs['now_ns'])
            a = dict(bank['actions'][idx]); a['legal_count'] = int(bank['mask'].sum())
            self._send(a)

    def close(self):
        self.p.stdin.close(); self.p.wait()


def episode_costs(s, n):
    """A24 train_v2 layout: [J/100, heat/1000, U miss frac, N miss frac, incomplete frac] at the last decision."""
    c = np.zeros((n, 5))
    J = s['J'] if s['J'] is not None else 0.
    c[-1] = [J / 100, s['heat_area'] / 1000, (s['U_planned'] - s['U_on']) / max(1, s['U_planned']),
             (s['N_planned'] - s['N_on']) / max(1, s['N_planned']), s['unfinished'] / max(1, s['planned'])]
    return c


def frozen_controller(path):
    lr = learn.Learner.load_snapshot(path)
    return lr.controller(.95, .5, collect=False)
