"""All12 conditions: found feasible saving versus optimistic upper bound."""
from pathlib import Path
import hashlib
import json
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
G.OWN_TOKENS+=('savings_limit_20261017','coupled_345_20261017')


def main():
    G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/'])
    op=json.loads((HERE/'OPERATION.json').read_text(encoding='utf-8'));out=ROOT/op['output_dir']
    a=json.loads((out/'ANALYSIS.json').read_text(encoding='utf-8'));target=out/'HEADROOM.png'
    G.require(not target.exists(),'Preserve existing figure')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,6),constrained_layout=True)
    for i,c in enumerate(a['cases']):
        lo=c['found_saving_percent'];hi=c['maximum_total_saving_percent']
        ax.plot([lo,hi],[i,i],color='#95a6b8',lw=3)
        ax.scatter([lo],[i],color='#2178b5',marker='o',zorder=3,label='Found feasible saving (EDF count SLA)' if i==0 else None)
        ax.scatter([hi],[i],color='#c16a24',marker='|',s=180,zorder=3,label='Optimistic upper bound (not achieved)' if i==0 else None)
    ax.axvline(10,color='#b94242',ls='--',lw=1,label='Original 10% total-energy target')
    ax.set_yticks(range(len(a['cases'])),[c['case'] for c in a['cases']]);ax.invert_yaxis()
    ax.set_xlabel('Total proxy energy saving from EDF (%)');ax.grid(axis='x',alpha=.2)
    ax.set_title('Scheduling headroom in the frozen coupled345 hypothesis model\nTrue optimum is bracketed; this is not calibrated device energy')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=1,frameon=False)
    fig.savefig(target,dpi=170);plt.close(fig)
    G.write_new(out/'FIGURE.json',dict(utc=G.now(),command=sys.argv,new_environment_START=0,
        source_analysis_sha256=G.sha(out/'ANALYSIS.json'),path=target.name,sha256=G.sha(target),bytes=target.stat().st_size))
    print('HEADROOM_FIGURE_SAVED')


if __name__=='__main__':main()
