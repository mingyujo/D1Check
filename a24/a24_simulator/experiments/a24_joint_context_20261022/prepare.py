import gzip,re,time,math
import numpy as np
from common import *
from model import Bases,TKEY,EKEY

def sessions(path):
    decoder=json.JSONDecoder()
    with gzip.open(path,'rt',encoding='utf-8') as f:
        buffer=''
        while True:
            buffer+=f.read(1048576);match=re.search(r'"sessions"\s*:\s*\[',buffer)
            if match:buffer=buffer[match.end():];break
            assert len(buffer)<10485760
        while True:
            buffer=buffer.lstrip(', \r\n\t')
            if buffer.startswith(']'):return
            try:row,end=decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk=f.read(1048576);assert chunk;buffer+=chunk;continue
            yield row;buffer=buffer[end:]

def power(c,a,b):
    total=cover=second=0.
    for r in c['power_brackets']:
        if r.get('left_available_s') is not None:assert max(r['left_available_s'],r['right_available_s'])<=35 or r['a']>=33 or r['b']<=a
        dt=max(0,min(b,r['b'])-max(a,r['a']))
        if not dt:continue
        if r.get('left_available_s') is not None:assert max(r['left_available_s'],r['right_available_s'])<=35
        total+=dt*r['v'];second+=dt*r['v']**2;cover+=dt
    assert abs(cover-(b-a))<1e-6,(c['session'],a,b,cover)
    return total/cover,max(0,second/cover-(total/cover)**2)

def build():
    data=read(ENERGY/'INPUTS.json');t=read(CAL/'INPUTS.json');tc={c['session']:c for c in t['cases']};assert data['outer_groups']==t['outer_groups']
    item=next(p for p in read(A/'data/CORE_MANIFEST.json') if p['name']=='MODEL_INPUTS.json');raw=A/item['stored'];assert sha(raw)==item.get('stored_sha256',sha(raw));cs={c['session']:c for c in data['cases']};raw_pre={};seen=0
    for row in sessions(raw):
        seen+=1;sid=row['session_id']
        if sid in cs:raw_pre[sid]=[o for o in row['observations'] if o.get('channel')=='AP' and o['t_s']<=35 and o['hi_s']<=35 and math.isfinite(o['ap_c'])]
    assert seen==115 and len(raw_pre)==106
    for sid,c in cs.items():
        thermal=tc[sid];assert c['owners']==thermal['owners'] and c['group']==thermal['group'];c.update({k:thermal[k] for k in ['observations','pre_slope_C_s','fit_window_s','initial_time_s','initial_return_hi_s']});obs=raw_pre[sid];ctx={'ap_level':(c['initial_c']-28)/5};receipts={}
        for width in [5,20,60]+([120] if c['family']=='m8' else []):
            oo=[o for o in obs if 35-width<=o['t_s']<=35];assert oo,(sid,width);avg=float(np.mean([o['ap_c'] for o in oo]));receipts[str(width)]={'n':len(oo),'min_t':min(o['t_s'] for o in oo),'max_t':max(o['t_s'] for o in oo),'max_return':max(o['hi_s'] for o in oo),'mean':avg}
            if width==5:ctx['ap_bias5']=float(np.clip(avg-c['initial_c'],-.1,.1))
            else:ctx['ap'+str(width)]=c['initial_c']-avg
        mean,var=power(c,5,33);prev,_=power(c,-25,5);assert abs(mean-c['pre_mean'])<1e-8*mean
        ctx.update(p_trend=float(np.clip((mean-prev)/mean,-1,1)),p_mean_median=float(np.clip((mean-c['pre_power'])/mean,-1,1)),p_cv=float(np.clip(var/mean**2,0,1)))
        if c['family']=='m8':older,_=power(c,-85,-25);ctx['p_older']=float(np.clip((prev-older)/mean,-1,1))
        c.update(context=ctx,context_receipt=receipts,causal_AP_observations=obs,previous_power_mean=prev,pre_power_variance=var)
    bases=Bases();settings={};receipts=[]
    for family in ['old','m8']:
        ids=[s for s,c in cs.items() if c['family']==family]
        for fold in [*range(5),'DEPLOYMENT']:
            tr=ids if fold=='DEPLOYMENT' else [s for s in ids if cs[s]['group'] not in data['outer_groups'][family][fold]];key=f'{family}/{fold}';settings[key]={}
            for head,folder in [('T',THERMAL),('E',ENERGY)]:
                p=folder/(f'{family}_DEPLOYMENT_MODEL.json' if fold=='DEPLOYMENT' else f'{family}_OUTER_{fold}.json');b=read(p);b=b if fold=='DEPLOYMENT' else b['model'];assert set(tr)==set(b['training_sessions']);settings[key][head]={k:b[k] for k in (TKEY if head=='T' else EKEY)}
                for k,held in enumerate([None,*split([cs[s] for s in tr],3)]):
                    ti=tr if held is None else [s for s in tr if cs[s]['group'] not in held];bm=bases.get(ti,settings[key][head],head);assert set(bm['training_sessions'])==set(ti);receipts.append({'family':family,'fold':fold,'head':head,'inner_index':k-1,'base_identity':bm['identity'],'training_sessions':ti})
    data.update(base_settings=settings,base_reuse_preflight=receipts,raw_source=pin(raw),raw_session_count=seen,AP_source_uncompressed_SHA256=item['sha256'],config={'fit_limit':600,'fresh_confirmation':False,'context_clips':{'power_trends':[-1,1],'power_mean_median':[-1,1],'power_cv':[0,1],'ap_bias5':[-.1,.1]}});return data

def main():
    assert not O.exists();d=read(V/'PREPARED_INPUTS.json');O.mkdir();write(O/'INPUTS.json',d)
    write(O/'FEATURE_INPUTS.json',[{k:c[k] for k in ['session','family','group','context','context_receipt','initial_c','pre_slope_C_s','pre_mean','pre_power','pre_delta']} for c in d['cases']])
    paths=[*H.glob('*.py'),*H.glob('*.cjs'),H/'PROTOCOL.md',*CONTROL,*[ENERGY/n for n in ['INPUTS.json','FIT_LEDGER.jsonl','OOF_PREDICTIONS.json','FINAL_PROOF.json']],*[THERMAL/n for n in ['FIT_LEDGER.jsonl','OOF_PREDICTIONS.json']],A/'reviews/A24_THERMAL_DIRECTION_20261021_02/FINAL_PROOF.json',FIRST/'FIT_LEDGER.jsonl',CAL/'INPUTS.json',TH/'thermal_model.py',TH/'calibrated_profile.cjs',CAL.parents[1]/'experiments/a24_thermal_calibration_20261021/thermal_model.py',A/'experiments/a24_thermal_calibration_20261021/calibrated_profile.cjs',EH/'energy_model.py',EH/'energy_observer.cjs',PH/'energy_model.py',PH/'energy_observer.cjs',R/'common_simulator/v1/profiles.cjs',A/'data/CORE_MANIFEST.json',R/d['raw_source']['path']]
    for family in ['old','m8']:
        for folder in [THERMAL,ENERGY]:paths.extend([folder/f'{family}_OUTER_{k}.json' for k in range(5)]);paths.append(folder/f'{family}_DEPLOYMENT_MODEL.json')
    write(O/'REGISTRATION.json',{'utc':time.time(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty_worktree':True,'sources':[pin(p) for p in dict.fromkeys(paths)],'inputs':pin(O/'INPUTS.json'),'feature_inputs':pin(O/'FEATURE_INPUTS.json'),'fit_limit':600,'new_measurements':0,'policy_environments':0,'fresh_confirmation':False})
    print(json.dumps({'state':'PREPARED','sessions':len(d['cases']),'base_reuse_keys':len(d['base_reuse_preflight'])}),flush=True)
if __name__=='__main__':main()
