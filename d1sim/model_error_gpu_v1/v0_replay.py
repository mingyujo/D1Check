"""v0_replay.py — standalone helper (run in its own process): replay the frozen v0 model for C1a (T1) / M3 (T2) exactly as
d1sim/tools/v0_driver_1003.py did (frozen _scratch copies · T0 = actual start SKIN · measured on/off flags) and print the SKIN series +
reproduction values as JSON. No d1sim package import here: the v0 driver must see the frozen v0 tree first on sys.path (its own assert).

  py -X utf8 d1sim/model_error_gpu_v1/v0_replay.py c1a|m3
"""
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
V0_LAST = r'C:\Users\rhoyo\AndroidStudioProjects\_scratch\v0_4708788'
sys.path.insert(0, os.path.join(ROOT, 'd1sim', 'tools'))
sys.path.insert(0, V0_LAST)
import v0_driver_1003 as V0  # noqa: E402  (frozen driver, unmodified; imports the _scratch v0 copies)


def main():
    tag = sys.argv[1]
    r1 = V0.rows1(tag)
    T0 = V0.t_start_of(tag)
    flags = [True] * len(r1) if tag == 'c1a' else V0.active_flags(tag)
    mod = V0.sim_flags(V0.P_V0, T0, flags)
    skin = [r['T'] for r in mod]
    skin_mae = statistics.mean(abs(mod[int(r['t_s'])]['T'] - float(r['SKIN'])) for r in r1 if r['SKIN'] != '')
    m10 = V0.bins10_model(mod, len(flags))
    onset_model = V0.onset(m10, V0.P_V0['L0'])
    out = dict(tag=tag, T0=T0, n_rows=len(skin), skin=skin, skin_mae_c_1s=skin_mae, model_skin_end=mod[-1]['T'], onset_model_s=onset_model, n_flags_on=sum(flags),
               v0_throttle_sha=V0.sha(os.path.join(V0.V0_FIX, 'd1sim', 'throttle.py')), v0_fix=V0.V0_FIX, env_file=V0.v0env.__file__, rows_1s=len(r1))
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
