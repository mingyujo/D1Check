import time,copy
from common import *
from energy_model import SETTINGS
def integral(bb,a,b,causal=False):
    total=cover=0.
    for r in bb:
        if causal and r.get('left_available_s') is not None and (r['left_available_s']>35 or r['right_available_s']>35):continue
        dt=max(0,min(b,r['b'])-max(a,r['a']));total+=dt*r['v'];cover+=dt
    assert abs(cover-(b-a))<1e-6,(a,b,cover)
    return total
def build():
    parent=read(PREV/'REGISTRATION.json')
    for p in [parent['inputs'],parent['feature_inputs'],*parent['sources']]:assert sha(R/p['path'])==p['sha256'],p['path']
    data=read(PREV/'INPUTS.json')
    for c in data['cases']:
        bb=c['power_brackets'];mean=integral(bb,5,33,True)/28;early=integral(bb,5,19,True)/14;late=integral(bb,19,33,True)/14
        c.update(pre_mean=mean,pre_early_mean=early,pre_late_mean=late,pre_delta=max(-.5*mean,min(.5*mean,late-early)))
        assert mean>0
    data['config']={'candidates':SETTINGS,'fit_limit':600,'ridge_L1':.0001,'selection_window_weight':.1,'background_tau_s':60,'inner_MAPE_allowance':0.,'inner_P90_APE_allowance_pct':2.,'fresh_confirmation':False,'origin_s':35,'source_contract_unchanged':True}
    return data
def main():
    assert not O.exists();data=build();assert data==read(V/'PREPARED_INPUTS.json');O.mkdir()
    features=[{k:c[k] for k in ['session','family','group','segments','pre_power','pre_mean','pre_delta','pre_context','primary','source_power_unit']} for c in data['cases']]
    write(O/'INPUTS.json',data);write(O/'FEATURE_INPUTS.json',features)
    paths=[*sorted(H.glob('*.py')),*sorted(H.glob('*.cjs')),H/'PROTOCOL.md',*[PH/n for n in ['energy_model.py','energy_observer.cjs']],*[PREV/n for n in ['INPUTS.json','REGISTRATION.json','FIT_LEDGER.jsonl','INNER_SELECTIONS.json','OOF_PREDICTIONS.json','FINDINGS.json','ENERGY_WINDOWS.csv','FINAL_PROOF.json']],R/'common_simulator/v1/profiles.cjs',A/'results/A24_THERMAL_KERNEL_20261022_01/OOF_PREDICTIONS.json']
    write(O/'REGISTRATION.json',{'utc':time.time(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty_worktree':True,'sources':[pin(p) for p in dict.fromkeys(paths)],'inputs':pin(O/'INPUTS.json'),'feature_inputs':pin(O/'FEATURE_INPUTS.json'),'fit_limit':600,'new_measurements':0,'policy_environments':0,'fresh_confirmation':False})
    print(json.dumps({'state':'PREPARED','cases':len(data['cases']),'candidates':16,'fit_limit':600}),flush=True)
if __name__=='__main__':main()
