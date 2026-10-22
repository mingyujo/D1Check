"""Only preparation/screening; seals sources before the first fit."""
import math,gzip,statistics,subprocess,time,re
from collections import Counter
from common import *
from energy_model import schedule,SETTINGS
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def valid_native(r):return (finite(r.get('t_s')) and finite(r.get('current_raw')) and r['current_raw']<0 and r['current_raw']!=-2147483648 and r.get('plugged')==0 and finite(r.get('voltage_raw')) and 2500<=r['voltage_raw']<=5000)
def sessions(path):
    # Streaming parser, same declared sessions-array contract as the saved raw audit.
    decoder=json.JSONDecoder()
    with gzip.open(path,'rt',encoding='utf-8') as f:
        buf=''
        while True:
            buf+=f.read(1048576);m=re.search(r'"sessions"\s*:\s*\[',buf)
            if m:buf=buf[m.end():];break
            assert len(buf)<10485760
        while True:
            buf=buf.lstrip(', \r\n\t')
            if buf.startswith(']'):return
            try:row,end=decoder.raw_decode(buf)
            except json.JSONDecodeError:
                chunk=f.read(1048576);assert chunk;buf+=chunk;continue
            yield row;buf=buf[end:]
def brackets(t,v,valid=None,available=None):
    if valid is None:valid=[True]*len(t)
    assert len(t)==len(v)==len(valid) and all(b>a for a,b in zip(t,t[1:])), 'Reversed/duplicate power clocks'
    return [{'a':a,'b':b,'v':v[i],'left_index':i,'left_available_s':available[i] if available else None,'right_available_s':available[i+1] if available else None} for i,(a,b) in enumerate(zip(t,t[1:])) if 0<b-a<=2 and valid[i] and valid[i+1]]
def integrate(bb,lo,hi):
    total=covered=0.
    for r in bb:
        dt=max(0,min(hi,r['b'])-max(lo,r['a']));total+=dt*r['v'];covered+=dt
    return total if abs(covered-(hi-lo))<=1e-6 else None
def weighted_pre(bb):
    known=all(r.get('left_available_s') is not None and r.get('right_available_s') is not None for r in bb)
    if known:bb=[r for r in bb if r['left_available_s']<=35 and r['right_available_s']<=35]
    ww=[(r['v'],max(0,min(33,r['b'])-max(5,r['a']))) for r in bb];ww=[(v,w) for v,w in ww if w>0]
    cov=sum(w for v,w in ww);assert cov>=20 and len(ww)>=10,'Insufficient causal pre power'
    pos=0
    for v,w in sorted(ww):
        pos+=w
        if pos>=cov/2:return v,{'interval_s':[5,33],'coverage_s':cov,'brackets':len(ww),'latest_left_t_s':max(max(5,r['a']) for r in bb if min(33,r['b'])>max(5,r['a'])),'cutoff_s':33,'sensor_refresh_verified':False,'read_completion_bounds_present':known,'latest_return_used_s':max(r['right_available_s'] for r in bb if min(33,r['b'])>max(5,r['a'])) if known else None}
def main(dry=False):
    if not dry:assert not O.exists();O.mkdir()
    cal=read(CAL/'INPUTS.json');old=read(OLD/'INPUTS.json')
    mp=A/'experiments/a24_cem_identification_20261019/MEASUREMENTS.json.gz';meas=json.loads(gzip.decompress(mp.read_bytes()))
    legacy={('A24_'+s['id']):s for s in meas['legacy']};raw={s['session_id']:s for s in meas['sessions']}
    priorreg=read(OLD/'REGISTRATION.json');assert sha(OLD/'INPUTS.json')==priorreg['inputs']['sha256']
    for p in priorreg['sources']:assert sha(R/p['path'])==p['sha256'],p['path']
    pinlegacy=read(A/'experiments/competition_cost_20261017/COST_OPERATION.json')['historical_power_pin']
    decoded=gzip.decompress((A/pinlegacy['stored']).read_bytes());assert hashlib.sha256(decoded).hexdigest()==pinlegacy['sha256'];assert json.loads(decoded)==old['legacy_power']
    legacy={('A24_'+s['id']):s for s in json.loads(decoded)}
    assert len(legacy)==len(meas['legacy'])==35
    for reduced in meas['legacy']:
        full=legacy['A24_'+reduced['id']];assert all(full[k]==v for k,v in reduced.items()),reduced['id']
    source=next(p for p in read(A/'data/CORE_MANIFEST.json') if p['name']=='MODEL_INPUTS.json');assert source['sha256'] in meas['source_hashes']
    digest=hashlib.sha256()
    with gzip.open(A/source['stored'],'rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):digest.update(chunk)
    assert digest.hexdigest()==source['sha256']
    rawbattery={};seen=0
    for s in sessions(A/source['stored']):
        seen+=1
        rr=(s.get('battery') or {}).get('raw_samples') or []
        if rr:
            extracted=raw[s['session_id']]['battery']['raw_samples'];assert len(rr)==len(extracted)
            assert all(all(r[k]==e[k] for k in e) for r,e in zip(rr,extracted))
            rawbattery[s['session_id']]=rr
    assert seen==115 and len(rawbattery)==71
    csvold=list(csv.DictReader((OLD/'ENERGY_PROXY.csv').open(encoding='utf-8-sig')))
    refs={}
    for r in csvold:
        if r['mode']=='tick0.05_observed_pre':refs.setdefault(r['session'],{})[r['name']]={k:float(r[k]) for k in ['lo','hi','predicted_J_proxy','observed_gauge_J_proxy'] if r[k] not in ('','None')}
    cases=[];screen=[{**s,'energy_included':False,'energy_reason':'original_schedule_excluded'} for s in old['screening'] if not s['included']]
    for cc in cal['cases']:
        c={k:cc[k] for k in ['session','family','source','group','activity_end_s','owners','last_work_s','schedule_kind','initial_c']};s=raw[c['session']];reason=None
        try:
            c['segments']=schedule(c)
            if c['family']=='old':
                d=legacy[c['session']];t=d['power_t'];v=d['power_w'];ok=[finite(x) and x>0 for x in v];available=None;unit='W_PROXY';end=d.get('common_end_s',120.);ref=refs[c['session']]
                c['legacy_metadata']={k:d.get(k) for k in ['policy','block','gap','role','study_phase','evaluation_block']}
            else:
                rawp=rawbattery[c['session']];t=[r['t_s'] for r in rawp];ok=[valid_native(r) for r in rawp];available=[r.get('hi_s') for r in rawp];assert all(finite(x) for x in available);v=[-r['current_raw']*r['voltage_raw'] if z else 0. for r,z in zip(rawp,ok)];unit='RAW_IV_PRODUCT';end=180.;ref={}
            bb=brackets(t,v,ok,available);pre,context=weighted_pre(bb);assert pre>0
            assert end<=c['activity_end_s'];truth=integrate(bb,35,end);assert truth is not None,'Primary coverage gap or invalid bracket'
            c.update(pre_power=pre,pre_context=context,source_power_unit=unit,primary=[35.,end],power_brackets=bb,old_references=ref,
                native_raw_samples=len(t),invalid_power_samples=sum(not z for z in ok),absolute_unit_qualified=False)
            windows=[]
            a=35.
            while a<end-1e-8:
                b=min(a+10,end);y=integrate(bb,a,b);assert y is not None;windows.append({'lo':a,'hi':b,'observed_source_energy':y,'observed_relative_power':y/(b-a)/pre});a=b
            c['train_windows']=windows;c['observed_primary_source_energy']=truth
            ev=[{'name':'registered','lo':35.,'hi':end}]
            for name,w in ref.items():
                if name!='registered':ev.append({'name':name,'lo':w['lo'],'hi':w['hi']})
            if c['family']=='m8':
                stop=min(end,max(35.,c['last_work_s'] or 35.))
                if stop>35:ev.append({'name':'work_present','lo':35.,'hi':stop})
                if end>stop:ev.append({'name':'recovery_observed','lo':stop,'hi':end})
            c['eval_windows']=[]
            for w in ev:
                y=integrate(bb,w['lo'],w['hi']);c['eval_windows'].append({**w,'observed_source_energy':y,'coverage_valid':y is not None})
            cases.append(c)
        except (AssertionError,ValueError,KeyError) as e:reason=str(e)
        screen.append({'session':c['session'],'family':c['family'],'group':c['group'],'energy_included':reason is None,'energy_reason':reason})
    assert len(screen)==115
    folds={f:[[g for g in fold if any(c['family']==f and c['group']==g for c in cases)] for fold in cal['outer_groups'][f]] for f in ['old','m8']}
    assert all(fold for f in folds.values() for fold in f),'Empty inherited outer fold'
    config={'candidates':SETTINGS,'ridge':.001,'fit_limit':300,'train_window_s':10,'level_weight':.75,'total_weight':.25,'inner_window_score_weight':.25,'origin_s':35,'pre_range_s':[5,33],'absolute_energy_verified':False,'fresh_confirmation':False}
    features=[{k:c[k] for k in ['session','family','group','segments','pre_power','pre_context','primary','source_power_unit']} for c in cases]
    packet={'cases':cases,'screening':screen,'outer_groups':folds,'config':config,'profile':old['profile']}
    if dry:return packet,features
    write(O/'INPUTS.json',packet)
    write(O/'FEATURE_INPUTS.json',features);csvwrite(O/'SCREENING.csv',screen)
    paths=[*sorted(H.glob('*.py')),*sorted(H.glob('*.cjs')),H/'PROTOCOL.md',OLD/'INPUTS.json',OLD/'REGISTRATION.json',OLD/'ENERGY_PROXY.csv',CAL/'INPUTS.json',mp,A/pinlegacy['stored'],A/'data/CORE_MANIFEST.json',A/source['stored'],A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',R/'common_simulator/v1/profiles.cjs',A/'results/A24_THERMAL_KERNEL_20261022_01/OOF_PREDICTIONS.json']
    write(O/'REGISTRATION.json',{'utc':time.time(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty_worktree':True,'sources':[pin(p) for p in dict.fromkeys(paths)],'inputs':pin(O/'INPUTS.json'),'feature_inputs':pin(O/'FEATURE_INPUTS.json'),'fit_limit':300,'included':dict(Counter(c['family'] for c in cases)),'excluded':115-len(cases),'new_measurements':0,'policy_environments':0,'fresh_confirmation':False})
    print(json.dumps({'state':'PREPARED','included':dict(Counter(c['family'] for c in cases)),'excluded':115-len(cases),'groups':{f:len({c['group'] for c in cases if c['family']==f}) for f in folds}}),flush=True)
if __name__=='__main__':main()
