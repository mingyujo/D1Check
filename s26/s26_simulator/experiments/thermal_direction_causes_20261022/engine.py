"""Frozen-chain replay and pre-anchor sensor history. Imports never fit models."""
from pathlib import Path
import sys,json,gzip,hashlib,importlib.util
import numpy as np
H=Path(__file__).resolve().parent;R=H.parents[2];E=H.parent;T=E/'thermal_trend_preservation_20261021';N=E/'thermal_decay_nonlinear_20261021'
spec=importlib.util.spec_from_file_location('frozen_trend_engine',T/'engine.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
read=P.read;save=P.save;sha=P.sha
def tree_predict(X,m):
    out=np.full(len(X),m.get('baseline_prediction',0.));rr=np.arange(len(X))
    for tree in m['trees']:
        feat=np.array([n['feature'] for n in tree]);thr=np.array([n['threshold'] for n in tree]);left=np.array([n['left'] for n in tree]);right=np.array([n['right'] for n in tree]);leaf=np.array([n['leaf'] for n in tree]);value=np.array([n['value'] for n in tree]);ix=np.zeros(len(X),dtype=int)
        while True:
            active=~leaf[ix]
            if not any(active):break
            jj=ix[active];ix[active]=np.where(X[rr[active],feat[jj]]<=thr[jj],left[jj],right[jj])
        out+=value[ix]
    return out
def initial_history(e,s):
    anchor=e['public']['anchor'];obs=[o for o in s['targets']['AP']['observations'] if o.get('available_upper_s',float('inf'))<=anchor and o['t_s']>=anchor-30];obs=sorted(obs,key=lambda o:o['t_s']);recent=[o for o in obs if o['t_s']>=anchor-20];short=[o for o in obs if o['t_s']>=anchor-10]
    def slope(items,key):
        rr=[o for o in items if isinstance(o.get(key),(int,float))]
        if len(rr)<2:return 0.
        t=np.array([o['t_s'] for o in rr]);y=np.array([o[key] for o in rr]);t=t-t.mean();return float(t@(y-y.mean())/(t@t)) if t@t>0 else 0.
    yy=np.array([o['AP'] for o in recent]);ap0=e['public']['AP0'];skin=e['public']['skin'];bat=e['context']['BAT'];changes=np.diff(yy) if len(yy)>1 else np.array([]);change_ix=np.where(abs(changes)>1e-9)[0];last_change=recent[change_ix[-1]+1]['t_s'] if len(change_ix) else (recent[0]['t_s'] if recent else anchor)
    if len(yy) and abs(yy[-1]-ap0)>1e-9:last_change=anchor
    values=[slope(short,'AP')*10,slope(recent,'SKIN')*10,slope(recent,'BAT')*10,(ap0-float(yy.mean()))/10 if len(yy) else 0.,float(yy.std())/10 if len(yy) else 0.,float(np.ptp(yy))/10 if len(yy) else 0.,(anchor-last_change)/30,float(np.mean(abs(changes)>1e-9)) if len(changes) else 0.,float(changes[change_ix[-1]]) if len(change_ix) else 0.,(skin-recent[-1]['SKIN'])/10 if recent and isinstance(recent[-1].get('SKIN'),(int,float)) else 0.,(bat-recent[-1]['BAT'])/10 if recent and isinstance(recent[-1].get('BAT'),(int,float)) else 0.,len(recent)/15]
    assert np.isfinite(values).all();return np.array(values),dict(observation_count=len(recent),maximum_available_s=max((o['available_upper_s'] for o in obs),default=None),anchor=anchor)
def load_entries():
    entries=P.load_entries();raw={s.get('session_uid',s['id']):s for s in read(E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz')}
    for e in entries:e['history'],e['history_audit']=initial_history(e,raw[e['id']])
    return entries
def frozen(group):return read(T/'artifacts/G001/models'/(group+'__TREND_BALANCED.json.gz'))
def design(e,chain):
    m=chain['frozen_HGB'];base,X=P.design(e['public'],m['base_power_model'],m['base_thermal_model']);prev=base+X[:,24]*tree_predict(np.column_stack((X,base)),m);X47=np.column_stack((X,base,prev,e['extra']));balanced=prev+X[:,24]*tree_predict(X47,chain);XX=np.column_stack((X47,balanced,np.repeat(e['history'][None,:],len(X),axis=0)));assert XX.shape[1]==60 and np.isfinite(XX).all();return XX,balanced,X[:,24]
def interpolate_coeff(t,q,offset):
    j=int(np.searchsorted(t,q))
    if j<len(t) and abs(t[j]-q)<1e-10:return [(offset+j,1.)]
    assert 0<j<len(t);a=(q-t[j-1])/(t[j]-t[j-1]);return [(offset+j-1,1-a),(offset+j,a)]
