"""Saved-only time traces for both preregistered 3x loads; no simulation."""
from pathlib import Path
import gzip
import json
import sys
import subprocess
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / 'reference/model_integration'))
import runtime_guard as G


def main():
    G.OWN_TOKENS += ('load_density_20261017', 'load_density_thermal_view_20261017',
                     'sustained_load_20261017', 'coupled_345_20261017')
    guard = G.process_guard(Path(__file__).resolve())
    volumes = G.free_guard([ROOT, 'D:/'])
    import msvcrt
    lock = (ROOT / 'runtime/worker.lock').open('r+b')
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        source = ROOT / 'results/LOAD_DENSITY_20261017_01'
        proof = G.read(source / 'FINAL_HANDOFF_PROOF.json')
        for p in proof['files']:
            G.pin({**p, 'path': REPO / p['path']})
        metrics = G.read(source / 'WORK_METRICS.json')['rows']
        thermal_path = ROOT / 'experiments/load_density_20261017/THERMAL_PURE_TEST.json'
        bound = G.read(thermal_path)['refined_invariant_upper_c']
        rows = [r for r in metrics if r['condition']['rate_multiplier'] == 3]
        G.require(len(rows) == 6, 'Both patterns and all three policies')
        out = ROOT / 'results/LOAD_DENSITY_THERMAL_VIEW_20261017_01'
        G.require(not out.exists(), 'Saved-view namespace already used')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), layout='constrained')
        colors = {'EDF': '#39495c', 'ATC': '#1b9e77', 'RL': '#d95f02'}
        pins = []
        summaries = []
        idle_endpoint_checks = 0
        max_idle_endpoint_error = 0.
        for ax, pattern, title in zip(axes, ['staggered_wave', 'clustered_recovery'],
                                      ['Dispersed', 'Clustered']):
            group = [r for r in rows if r['condition']['pattern'] == pattern]
            end = max(120, max(r['completion']['duration_s'] for r in group)) + 100
            ax.axvspan(0, 120, color='#dee8f0', alpha=.5, label='Request supply (120s)')
            for row in group:
                label = row['case'] + '_' + row['policy']
                p = source / (label + '.raw.json.gz')
                result = json.loads(gzip.decompress(p.read_bytes()))['result']
                trace = result['trace']
                xs, ys = [0], [result['initial_ap_c']]
                c = result['config']
                shared = G.read(thermal_path)['shared_W_proxy']
                for s in trace:
                    start = s['start_ns'] / 1e9 - 35
                    if start >= end:
                        break
                    if not s['active'] and s['dt'] > 1:
                        # Exact saved idle-interval interpolation, including its
                        # decaying activation tail; not a new environment rollout.
                        def value(dt):
                            tt, tz = c['thermal_tau_s'], c['idle_tail_s']
                            decay = math.exp(-dt / tt)
                            forcing = c['thermal_resistance'] * shared * s['state']['shared_z']
                            forcing *= tz / (tz - tt) * (math.exp(-dt / tz) - decay)
                            return c['idle_c'] + (s['state']['temperature_c'] - c['idle_c']) * decay + forcing
                        error = abs(value(s['dt']) - s['next_state']['temperature_c'])
                        max_idle_endpoint_error = max(max_idle_endpoint_error, error)
                        idle_endpoint_checks += 1
                        G.require(error < 1e-8, 'Saved idle endpoint agreement')
                        stop = min(s['dt'], end - start)
                        for j in range(1, math.ceil(stop) + 1):
                            dt = min(j, stop)
                            xs.append(start + dt)
                            ys.append(value(dt))
                    elif s['end_ns'] / 1e9 - 35 <= end:
                        xs.append(s['end_ns'] / 1e9 - 35)
                        ys.append(s['next_state']['temperature_c'])
                G.require(max(s['peak'] for s in trace) <= bound + 1e-8, 'Invariant bound')
                color = colors[row['policy']]
                ax.plot(xs, ys, color=color, label=row['policy'], linewidth=1.3)
                duration = row['completion']['duration_s']
                ax.axvline(duration, color=color, linestyle=':', linewidth=1, alpha=.8)
                pins.append({'path': str(p.relative_to(REPO)).replace('\\', '/'), 'sha256': G.sha(p), 'bytes': p.stat().st_size})
                summaries.append({'label': label, 'n': row['n'], 'completion_duration_s': duration,
                                  'peak_AP_c': row['original']['peak_AP_c']})
            ax.axhline(bound, color='#8b5e83', linestyle='--', linewidth=1.2,
                       label=f'Model invariant upper bound ({bound:.2f} C)')
            ax.set(title=f"{title}: 3x arrival rate, {group[0]['n']} requests, all policies",
                   xlabel='Time since first request (s)', ylabel='Temperature proxy (C)',
                   xlim=(0, end), ylim=(25, 43))
            ax.grid(alpha=.2)
            ax.legend(fontsize=8, ncol=3, loc='upper right')
        fig.suptitle('A24 hypothesis model: heating, bounded operation and cooling\n'
                     'Dotted lines: each policy completes all work. No temperature clipping added.', fontsize=12)
        out.mkdir()
        fig.savefig(out / 'THERMAL_TRACES.png', dpi=170)
        fig.savefig(out / 'THERMAL_TRACES.svg')
        plt.close(fig)
        manifest = {'utc': G.now(), 'new_environment_START': 0, 'new_training': 0,
                    'new_physical_fit': 0, 'temperature_clipping_added': False,
                    'HEAD': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                    'parent_proof_sha256': G.sha(source / 'FINAL_HANDOFF_PROOF.json'),
                    'source_sha256': G.sha(Path(__file__)), 'thermal_proof_sha256': G.sha(thermal_path),
                    'idle_endpoint_checks': idle_endpoint_checks, 'max_idle_endpoint_error_c': max_idle_endpoint_error,
                    'guard': guard, 'volumes': volumes, 'inputs': pins, 'rows': summaries,
                    'scope': 'Saved traces, both 3x patterns and all policies. Long idle intervals exactly resampled with the pinned decay equation. Hypothesis temperatures, not device measurements.',
                    'outputs': [{'path': p.name, 'sha256': G.sha(p), 'bytes': p.stat().st_size}
                                for p in sorted(out.iterdir())]}
        G.write_new(out / 'PROOF.json', manifest)
        print(json.dumps({'status': 'SAVED_THERMAL_VIEW_PASS', 'rows': summaries, 'new_environment_START': 0}), flush=True)
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    main()
