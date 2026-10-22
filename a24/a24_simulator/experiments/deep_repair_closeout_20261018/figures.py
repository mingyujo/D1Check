"""Static scientific comparison from completed, audited saved tables only."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'results/DEEP_REPAIR_CLOSEOUT_20261018_01'
data=json.loads((out/'GROUP_COMPARISONS.json').read_text(encoding='utf-8'))
assert not (out/'comparison.png').exists(), 'Preserve consumed figure'
rows=[r for r in data['rows'] if r['group']=='ALL_30']
labels=[r['policy']+f" ({r['common_completed_cases']}/30)" for r in rows]
colors=['#9aa0a6' if r['policy'] in ('EDF','ATC') else '#8da0cb' if r['policy'].startswith(('GUARD','FT_','REPAIR_')) else '#009688' if r['policy'] in ('BC_ONLY','BC_PPO_OFF','CALIBRATED_PPO_OFF') or r['policy'].startswith(('CONTEXT_BC_','MINMAX_')) else '#e69f00' for r in rows]
fig,axes=plt.subplots(1,4,figsize=(18,7.5),sharey=True)
fields=[('on_time','On-time responses / 12,260',False),('saving_percent','Completion total energy saving (%)',True),('common_saving_percent','Common-window total energy saving (%)',True),('mean_temperature_reduction_c','Common-window mean temperature reduction (C)',True)]
for ax,(key,title,zero) in zip(axes,fields):
    ax.barh(range(len(rows)),[r[key] for r in rows],color=colors)
    if zero:ax.axvline(0,color='#444444',linewidth=.8)
    ax.set_title(title,fontsize=10,pad=14)
    ax.grid(axis='x',alpha=.25)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=9)
axes[0].set_yticks(range(len(rows)),labels,fontsize=9)
axes[0].invert_yaxis()
fig.suptitle('Same 30 inputs: all policies, including regressions',fontsize=14)
fig.text(.25,.025,'Positive energy/temperature values indicate improvement vs EDF. Labels show cases completed within the common window.\nDescriptive aggregates retain SLA losses and unfinished common-window work; use per-case eligibility to judge joint gains.',fontsize=9)
fig.tight_layout(rect=(0,.08,1,.94))
fig.savefig(out/'comparison.png',dpi=180)
fig.savefig(out/'comparison.svg')
plt.close(fig)
print('SAVED_FIGURE_COMPLETE',len(rows),flush=True)
