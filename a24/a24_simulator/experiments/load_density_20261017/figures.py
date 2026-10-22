"""Standalone scientific sensitivity figures; saved data only."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main(out):
 out=Path(out);r=json.loads((out/'WORK_METRICS.json').read_text(encoding='utf-8'))['rows']
 fig,axes=plt.subplots(2,3,figsize=(13,7.8),layout='constrained')
 styles={'EDF':('#39495c','o'),'ATC':('#1b9e77','s'),'RL':('#d95f02','^')}
 patterns=['staggered_wave','clustered_recovery']
 for row,p in enumerate(patterns):
  for policy,(color,marker) in styles.items():
   group=sorted([x for x in r if x['condition']['pattern']==p and x['policy']==policy],key=lambda x:x['condition']['rate_multiplier'])
   xx=[x['condition']['rate_multiplier'] for x in group]
   ys=[[100*x['original']['on_time']/x['n'] for x in group],[x['completion_J_proxy_per_request'] for x in group],[x['original']['P95_completed_response_s'] for x in group]]
   for col,y in enumerate(ys):axes[row,col].plot(xx,y,color=color,marker=marker,label=policy,linewidth=1.8)
  for col,ax in enumerate(axes[row]):
   ax.set_xlabel('Arrival-rate multiplier (fixed120s supply)');ax.set_xticks([.5,1,1.5,2,3]);ax.grid(alpha=.22)
   ax.set_title(('Dispersed' if row==0 else 'Clustered')+' - '+['On-time requests','Completion energy / request','Completed response P95'][col])
   ax.set_ylabel(['Success (%)','Conditional J* / request','Response (s)'][col]);ax.legend(fontsize=8)
  axes[row,0].set_ylim(-3,103)
 fig.suptitle('A24 frozen EDF / ATC / RL: load-density sensitivity (hypothesis model)',fontsize=13)
 fig.savefig(out/'SENSITIVITY.png',dpi=170);fig.savefig(out/'SENSITIVITY.svg');plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
 for ax,p in zip(axes,patterns):
  for policy,(color,marker) in styles.items():
   group=sorted([x for x in r if x['condition']['pattern']==p and x['policy']==policy],key=lambda x:x['condition']['rate_multiplier'])
   ax.plot([x['condition']['rate_multiplier'] for x in group],[x['common']['mean_AP_c'] for x in group],color=color,marker=marker,label=policy)
  ax.set(title=p,xlabel='Arrival-rate multiplier',ylabel='Mean temperature proxy (C)');ax.grid(alpha=.22);ax.legend(fontsize=8)
 fig.savefig(out/'TEMPERATURE.png',dpi=170);fig.savefig(out/'TEMPERATURE.svg');plt.close(fig)
 print('SAVED_FIGURES sensitivity/temperature PNG+SVG; new_environment0',flush=True)
if __name__=='__main__':
 import sys
 main(sys.argv[1])
