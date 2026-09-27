"""Plot measured vs model (10 s bins) for C1-probe r1/r2. Usage: py d1sim/tools/plot_throttle.py <fit.json> <out.png>"""
import json, os, statistics as st, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from d1sim.tools.fit_throttle import load, params, run_model, FORMS  # noqa: E402

fit = json.load(open(sys.argv[1], encoding='utf-8'))
base = {k: fit['fixed'][k] for k in ('L0', 'P0', 'P_idle', 's_min', 'alpha')}
fig, ax = plt.subplots(3, 2, figsize=(11, 9), sharex=True)
for c, tag in enumerate(('c1p_r1', 'c1p_r2')):
    d = load(tag)
    t10 = [t for t, _, _ in d['ten']]
    ax[0][c].plot(t10, [m for _, m, _ in d['ten']], 'k.', label='measured')
    ax[1][c].plot(t10, [p for _, _, p in d['ten']], 'k.')
    ax[2][c].plot([r['t'] for r in d['one'] if r['SKIN']], [r['SKIN'] for r in d['one'] if r['SKIN']], 'k-', lw=.8)
    for form in ('M-A1', 'M-A2', 'M-B2'):
        f = fit['forms'][form]; sensor, _, names = FORMS[form]
        sim = run_model(params(form, [f['fitted'][n] for n in names], base), d, sensor)
        ax[0][c].plot(t10, [st.median(x['latency_ms'] for x in sim[t:t + 10]) for t in t10], label=form)
        ax[1][c].plot(t10, [st.mean(x['power_w'] for x in sim[t:t + 10]) for t in t10])
        if sensor == 'SKIN':
            ax[2][c].plot([x['t'] for x in sim], [x['T'] for x in sim])
    ax[0][c].set_title(f'{tag} ({"fit" if c == 0 else "half-holdout"})')
ax[0][0].set_ylabel('latency ms (10 s median)'); ax[1][0].set_ylabel('battery power W (uncertified)')
ax[2][0].set_ylabel('SKIN C'); ax[2][0].set_xlabel('load s'); ax[2][1].set_xlabel('load s'); ax[0][0].legend()
fig.tight_layout(); fig.savefig(sys.argv[2], dpi=90)
