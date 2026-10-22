"""Causal residual heads. Targets occur only in fitting/scoring, never prediction."""
import importlib.util,copy,math
import numpy as np
from common import *

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
thermal=module('_joint_thermal',TH/'thermal_model.py')
energy=module('_joint_energy',EH/'energy_model.py')
SCHEMA='A24-causal-joint-context-v1'
SETTINGS={h:[{'features':f,'response':r,'ridge':v} for f in ['own','shared'] for r in ([60.,180.] if h=='T' else ['decay','relax']) for v in [.001,.03]] for h in ['T','E']}
TKEY=['tau_fast_s','tau_slow_s','transport_s','hinge_strength'];EKEY=['background','tau_s','total_weight']

def base_key(ids,m,head):return (tuple(sorted(ids)),*(m[k] for k in (TKEY if head=='T' else EKEY)))

class Bases:
    def __init__(self):
        self.index={'T':{},'E':{}}
        for folder in [FIRST,THERMAL]:
            for line in (folder/'FIT_LEDGER.jsonl').read_text().splitlines():
                r=json.loads(line)
                if r['event']!='COMPLETE':continue
                m=r['model']
                if folder==FIRST and m['hinge_strength']!=0:continue
                m=copy.deepcopy(m);m['original_schema']=m['schema'];m['schema']='A24-direction-aware-two-thermal-states-v2'
                self.index['T'][base_key(m['training_sessions'],m,'T')]=m
        for line in (ENERGY/'FIT_LEDGER.jsonl').read_text().splitlines():
            r=json.loads(line)
            if r['event']=='COMPLETE' and r['model']['kind']=='V2':
                m=r['model'];self.index['E'][base_key(m['training_sessions'],m,'E')]=m
    def get(self,ids,setting,head):return copy.deepcopy(self.index[head][base_key(ids,setting,head)])

def names(c,head,setting):
    ap=['ap20','ap60','ap_level']+(['ap120'] if c['family']=='m8' else [])
    pw=['p_trend','p_mean_median','p_cv']+(['p_older'] if c['family']=='m8' else [])
    return (ap if head=='T' else pw) if setting['features']=='own' else ap+pw

def statistics(cs,head,setting):
    ns=names(cs[0],head,setting);x=np.array([[c['context'][n] for n in ns] for c in cs]);return {'names':ns,'center':x.mean(axis=0).tolist(),'scale':np.maximum(3*x.std(axis=0),.01).tolist()}

def z(c,stats):return np.r_[1.,np.clip((np.array([c['context'][n] for n in stats['names']])-stats['center'])/stats['scale'],-1,1)]

def t_design(c,times,setting,stats):
    s=np.array(times)-35;q=np.exp(-s/setting['response'])-np.exp(-s/10);return np.column_stack([q[:,None]*z(c,stats),c['context']['ap_bias5']*np.exp(-s/180)])

def e_area(s,response):
    a=-60*np.expm1(-np.array(s)/60);return a if response=='decay' else np.array(s)-a

def e_design(c,windows,setting,stats):
    a=np.array([a-35 for a,b in windows]);b=np.array([b-35 for a,b in windows]);g=(e_area(b,setting['response'])-e_area(a,setting['response']))/(b-a);return c['pre_mean']*g[:,None]*z(c,stats)

def bounds(stats,head):
    n=len(stats['names'])+1;lo=np.full(n,-.15/n);hi=-lo
    return (np.r_[lo,0.],np.r_[hi,1.]) if head=='T' else (lo,hi)

def baseline_t(c,m):
    segs=thermal.segments(c);taus={m['tau_fast_s'],m['tau_slow_s']}
    if m['transport_s']:taus.add(m['transport_s'])
    conv={t:thermal.convolution(c,segs,t) for t in taus};x=thermal.matrix(c,conv,m['tau_fast_s'],m['tau_slow_s'],m['transport_s']);return c['initial_c']+x@np.array(m['coefficients'])

def predict_t(c,m):
    out=baseline_t(c,m['base'])
    if m['setting'] is not None:out+=t_design(c,[o['t'] for o in c['observations']],m['setting'],m['statistics'])@np.array(m['coefficients'])
    return out

def predict_e(c,windows,m):
    out=energy.predict_source_mean(c,windows,m['base'])
    if m['setting'] is not None:out+=e_design(c,windows,m['setting'],m['statistics'])@np.array(m['coefficients'])
    return out

def t_area(c,m,end):
    out=thermal.integrated(c,m['base'],end)
    if m['setting'] is not None:
        s=end-35;tau=m['setting']['response'];b=m['coefficients'];amp=float(z(c,m['statistics'])@np.array(b[:-1]));out+=amp*(-tau*math.expm1(-s/tau)+10*math.expm1(-s/10))+b[-1]*c['context']['ap_bias5']*(-180*math.expm1(-s/180))
    return out

def label(v):return 1 if v>=.2-1e-10 else -1 if v<=-.2+1e-10 else 0

def active_obs(c):return [i for i,o in enumerate(c['observations']) if c['fit_window_s'][0]<=o['t']<=c['fit_window_s'][1]]

def pairs(c):
    idx=active_obs(c);obs=[c['observations'][i] for i in idx];return [(idx[a],idx[b]) for a,b in thermal.window_pairs(obs)]

def train_arrays(cs,head,base,setting,stats):
    xx=[];yy=[];ww=[];guard=[];limit=[];ref=float(np.median([c['pre_mean'] for c in cs]))
    for c in cs:
        if head=='T':
            ts=[o['t'] for o in c['observations']];x=t_design(c,ts,setting,stats);b=baseline_t(c,base);truth=np.array([o['observed_c'] for o in c['observations']]);ix=active_obs(c);pp=pairs(c)
            xx.append(x[ix]);yy.append((truth-b)[ix]);ww.extend([1/(len(cs)*len(ix))]*len(ix))
            if pp:
                dx=np.array([x[j]-x[i] for i,j in pp]);db=np.array([b[j]-b[i] for i,j in pp]);dy=np.array([truth[j]-truth[i] for i,j in pp]);xx.append(dx);yy.append(dy-db);ww.extend([.2/(len(cs)*len(pp))]*len(pp))
                for row,pred,actual in zip(dx,db,dy):
                    if label(pred)!=label(actual):continue
                    if label(actual)==1:guard.append(-row);limit.append(max(0.,pred-.2+1e-10))
                    elif label(actual)==-1:guard.append(row);limit.append(max(0.,-.2-pred+1e-10))
                    else:
                        guard.extend([row,-row]);limit.extend([max(0.,.2-1e-10-pred),max(0.,.2-1e-10+pred)])
        else:
            ws=[(w['lo'],w['hi']) for w in c['train_windows']]+[tuple(c['primary'])];dt=np.array([b-a for a,b in ws]);x=e_design(c,ws,setting,stats)*dt[:,None]/(ref*100);truth=np.array([w['observed_source_energy'] for w in c['train_windows']]+[c['observed_primary_source_energy']]);b=energy.predict_source_mean(c,ws,base)*dt;xx.append(x);yy.append((truth-b)/(ref*100));ww.extend([.1/(len(cs)*len(c['train_windows']))]*len(c['train_windows'])+[.9/len(cs)])
    return np.vstack(xx),np.concatenate(yy),np.array(ww),np.array(guard),np.array(limit)

def metrics(cs,m,head):
    rows=[]
    for c in cs:
        if head=='T':
            truth=np.array([o['observed_c'] for o in c['observations']]);pred=predict_t(c,m);ix=active_obs(c);pp=pairs(c);ds=[(truth[j]-truth[i],pred[j]-pred[i]) for i,j in pp]
            rows.append({'session':c['session'],'group':c['group'],'MAE':float(np.mean(abs(pred[ix]-truth[ix]))),'abs_errors':abs(pred[ix]-truth[ix]).tolist(),'delta_errors':[abs(b-a) for a,b in ds],'classes':[[label(a),label(b)] for a,b in ds]})
        else:
            a,b=c['primary'];actual=c['observed_primary_source_energy'];pred=float(predict_e(c,[(a,b)],m)[0]*(b-a));err=pred-actual;scale=1 if c['family']=='old' else c['pre_power'];rows.append({'session':c['session'],'group':c['group'],'MAE':abs(err)/scale,'error':err/scale,'APE_pct':100*abs(err)/actual,'actual':actual/scale,'predicted':pred/scale})
    return rows

def score(rows,head):
    out={'MAE':float(np.mean([r['MAE'] for r in rows]))}
    if head=='T':
        ds=[v for r in rows for v in r['delta_errors']];cl=[v for r in rows for v in r['classes']];out.update(delta_MAE=float(np.mean(ds)),P90=float(np.quantile([v for r in rows for v in r['abs_errors']],.9)))
        for k,n in [(1,'rise'),(-1,'fall'),(0,'stable')]:
            a=[b for a,b in cl if a==k];out[n]=sum(b==k for b in a)/len(a) if a else 1.;out[n+'_n']=len(a)
    else:out.update(MAPE_pct=float(np.mean([r['APE_pct'] for r in rows])),P90=float(np.quantile([r['APE_pct'] for r in rows],.9)))
    return out

def eligible(s,b,head):
    if not s['MAE']<b['MAE']-1e-10:return False
    if head=='E':return s['MAPE_pct']<=b['MAPE_pct']+1e-9 and s['P90']<=b['P90']+1+1e-9
    return s['delta_MAE']<=b['delta_MAE']+1e-9 and s['P90']<=b['P90']+.005+1e-9 and all(s[k]>=b[k]-1e-10 for k in ['rise','fall','stable'])
