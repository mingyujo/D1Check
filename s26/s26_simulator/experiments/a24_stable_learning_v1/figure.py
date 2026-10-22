"""Scientific summary figure; ranges denote3 seeds, not confidence intervals."""
import hashlib,json
from pathlib import Path
def main(out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 s=json.loads((out/'COMPARISON_SUMMARY.json').read_text(encoding='utf-8'));g=s['grouped_by_load'];x=[100*r['load']for r in g];fig,ax=plt.subplots(1,2,figsize=(12.6,4.7),layout='constrained');styles=[('EDF_GPU_FIRST','#7b8793','--'),('ATC','#30343b',':'),('ATC_SALVAGE','#208a65','-.'),('FROZEN','#cf8d22','--'),('BASE','#3475bd','-'),('REPAIR','#cc4547','-')]
 for name,color,ls in styles:ax[0].plot(x,[r[name+'_on_percent']for r in g],label={'BASE':'DEFAULT','REPAIR':'STABLE','FROZEN':'Frozen parent'}.get(name,name),color=color,linestyle=ls,marker='o',markersize=4,linewidth=1.6)
 for name,color in [('BASE','#3475bd'),('REPAIR','#cc4547')]:
  a=[next(z for z in s['summaries']if z['load']==r['load']and z['method']==name)['seed_range_percent']for r in g];ax[0].fill_between(x,[z[0]for z in a],[z[1]for z in a],color=color,alpha=.12)
 for i,seed in enumerate([581081,581083,581087]):ax[1].plot(x,[next(z['delta_pp']for z in r['paired_seed_deltas']if z['seed']==seed)for r in g],label=f'Paired seed {seed}',marker='o',linewidth=1.2,alpha=.8)
 ax[1].plot(x,[r['REPAIR_minus_BASE_pp']for r in g],color='#20262e',label='Mean of3 paired seeds',linewidth=2.2);ax[1].axhline(0,color='#8c969f',linestyle='--',linewidth=1)
 ax[0].set(title='On-time completion; all planned arrivals',ylabel='On-time (%)',ylim=(0,102));ax[1].set(title='Stable minus matched-budget default',ylabel='On-time difference (percentage points)')
 for a in ax:a.set_xlabel('Nominal CENTRAL capacity load (%)');a.set_xticks(x);a.grid(alpha=.2);a.legend(fontsize=8)
 fig.suptitle('S26 conditional optimizer study: deadline protection removed',fontsize=12);fig.text(.5,-.025,'Shading = min/max of3 training seeds. Model power/thermal accuracy remains unvalidated; no real-device savings claim.',ha='center',fontsize=8);p=out/'REPAIR_LOAD_CURVE.png';fig.savefig(p,dpi=180,bbox_inches='tight');plt.close(fig)
 proof=dict(status='FIGURE_SAVED',path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),new_environment=0,new_training=0)
 with(out/'FIGURE_PROOF.json').open('x',encoding='utf-8')as f:json.dump(proof,f,indent=2)
