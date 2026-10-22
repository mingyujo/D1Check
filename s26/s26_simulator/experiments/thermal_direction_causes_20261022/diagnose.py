"""Existing-data diagnostic only. Measured post-anchor inputs never become deployable features."""
from pathlib import Path
import sys,json,gzip,collections,csv,importlib.util
import numpy as np
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent;T=E/'thermal_trend_preservation_20261021';sys.path.insert(0,str(T));from engine import read,save,steps
sys.stdout.reconfigure(encoding='utf-8')
raw=read(E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz');rawby={s.get('session_uid',s['id']):s for s in raw};power={r['id']:r for r in read(E/'capacity_power_v1/artifacts/G001/OOF_ROWS.json.gz')};windows=read(E/'simulator_accuracy_rise_fall_20261021/artifacts/A001/WINDOWS.json.gz');pred={r['id']:r for r in read(T/'artifacts/G001/OOF_ROWS.json.gz') if r['candidate']=='TREND_BALANCED'}
def label(x):return 'RISE' if x>=.2-1e-9 else 'FALL' if x<=-.2+1e-9 else 'STEADY'
def interp(t,y,q):return float(np.interp(q,t,y)) if t[0]<=q<=t[-1] else None
def mean(t,y,a,b):
    if a<t[0] or b>t[-1]:return None
    grid=np.r_[a,t[(t>a)&(t<b)],b];return float(np.trapezoid(np.interp(grid,t,y),grid)/(b-a))
out=[];sensor=[]
for uid,r in pred.items():
    t=np.array(r['times']);y=np.array(r['observed']);s=rawby[uid];obs=s['targets']['AP']['observations'];events=steps(s['activity9']['intervals']);et=np.array([z[0] for z in events]);v=np.array([z[1] for z in events]);pw=power[uid];pt=np.array(pw['times']);py=np.array(pw['observed']);pp=np.array(pw['predicted']);late=t>=256
    for cat,mask in [('ALL',np.ones(len(t),dtype=bool)),('LATE',late)]:
        yy=y[mask];tt=t[mask]
        if len(yy)<2:continue
        changes=np.r_[0,np.where(abs(np.diff(yy))>1e-9)[0]+1,len(yy)];durations=[float(tt[b-1]-tt[a]) for a,b in zip(changes[:-1],changes[1:]) if b>a+1]
        sensor.append(dict(id=uid,group=r['group'],category=cat,points=len(yy),grid0p1_percent=float(100*np.mean(abs(yy*10-np.round(yy*10))<1e-6)),same_consecutive_percent=float(100*np.mean(abs(np.diff(yy))<1e-9)),median_read_interval_s=float(np.median(np.diff(tt))),plateau_durations_s=durations))
    for w in [z for z in windows if z['id']==uid and z['start']>=256]:
        a=w['start'];b=w['end'];mid=(a+b)/2;idx=np.searchsorted(et,mid,side='right')-1;state=v[idx] if idx>=0 else np.zeros(5);inside=(et>a)&(et<b);nchanges=int(sum(np.any(v[1:]!=v[:-1],axis=1)&inside[1:])) if len(v)>1 else 0
        before=interp(t,y,a-10);now=interp(t,y,a);previous_delta=now-before if before is not None else None
        delta=interp(t,y,b)-now;pd=interp(t,np.array(r['predicted']),b)-interp(t,np.array(r['predicted']),a);shifted=[]
        for shift in [-2,2]:
            aa=interp(t,y,a+shift);bb=interp(t,y,b+shift)
            if aa is not None and bb is not None:shifted.append(label(bb-aa)!=w['direction'])
        p0=mean(pt,py,a-10,a);p1=mean(pt,py,a,b);p2=mean(pt,py,b,b+10);phat=mean(pt,pp,a,b)
        item=dict(id=uid,group=r['group'],start=a,direction=w['direction'],AP_delta=delta,predicted_AP_delta=pd,previous_measured_AP_delta=previous_delta,observer_persistence_direction=label(previous_delta) if previous_delta is not None else None,activity_changes=nchanges,any_modelled_activity=bool(np.any(state>0)),power_mean=p1,power_pred_mean=phat,power_change_from_previous=p1-p0 if p0 is not None and p1 is not None else None,power_change_to_next=p2-p1 if p1 is not None and p2 is not None else None,power_residual=p1-phat if p1 is not None and phat is not None else None,endpoint_shift_flip_fraction=float(np.mean(shifted)) if shifted else None)
        for sensorname in ['SKIN','BAT']:
            available=[o for o in obs if isinstance(o.get(sensorname),(int,float))];st=np.array([o['t_s'] for o in available]);sy=np.array([o[sensorname] for o in available]);aa=interp(st,sy,a) if len(st)>1 else None;bb=interp(st,sy,b) if len(st)>1 else None;item[sensorname+'_delta']=bb-aa if aa is not None and bb is not None else None
        out.append(item)
summary=[]
for cl in ['RISE','FALL','STEADY']:
    rr=[r for r in out if r['direction']==cl];by=collections.defaultdict(list)
    for r in rr:by[r['id']].append(r)
    def macro(field):return float(np.mean([np.mean([v[field] for v in ss if v[field] is not None]) for ss in by.values() if any(v[field] is not None for v in ss)]))
    for r in rr:r['observer_persistence_correct']=r['observer_persistence_direction']==r['direction'];r['no_activity']=not r['any_modelled_activity'];r['no_activity_change']=r['activity_changes']==0
    correlations={}
    for feature in ['power_mean','power_change_from_previous','power_residual','SKIN_delta','BAT_delta','previous_measured_AP_delta']:
        vals=[]
        for ss in by.values():
            valid=[v for v in ss if v[feature] is not None]
            if len(valid)>=5 and np.std([v[feature] for v in valid])>1e-9 and np.std([v['AP_delta'] for v in valid])>1e-9:vals.append(float(np.corrcoef([v['AP_delta'] for v in valid],[v[feature] for v in valid])[0,1]))
        correlations[feature]=dict(sessions=len(vals),session_macro_pearson=float(np.mean(vals)) if vals else None)
    summary.append(dict(direction=cl,windows=len(rr),sessions=len(by),no_modelled_activity_percent=100*macro('no_activity'),no_activity_change_percent=100*macro('no_activity_change'),endpoint_shift_2s_flip_percent=100*macro('endpoint_shift_flip_fraction'),observer_persistence_accuracy_percent=100*macro('observer_persistence_correct'),correlations=correlations))
sensor_summary=[]
for cat in ['ALL','LATE']:
    rr=[r for r in sensor if r['category']==cat];dur=[v for r in rr for v in r['plateau_durations_s']];sensor_summary.append(dict(category=cat,sessions=len(rr),grid0p1_percent=float(np.mean([r['grid0p1_percent'] for r in rr])),same_consecutive_percent=float(np.mean([r['same_consecutive_percent'] for r in rr])),median_session_read_interval_s=float(np.median([r['median_read_interval_s'] for r in rr])),plateau_duration_quantiles_s=[float(v) for v in np.percentile(dur,[10,50,90])]))
fields=list(dict.fromkeys(k for r in out for k in r))
with (H/'LATE_WINDOW_DIAGNOSTICS.csv').open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
save(H/'DIAGNOSIS.json',dict(status='COMPLETE_EXISTING_DATA_CAUSE_DIAGNOSTICS',direction=summary,sensor=sensor_summary,interpretation='Associations, not causal identification. Past measured AP observer is a different information contract; not replacement free-running accuracy.',new_fits=0,new_measurements=0));print(json.dumps(dict(direction=summary,sensor=sensor_summary),ensure_ascii=False))
