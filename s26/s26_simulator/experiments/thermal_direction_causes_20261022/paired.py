"""Descriptive paired whole-group bootstrap from exported session scores; no fits."""
from engine import *
import csv,collections
O=H/'artifacts/G001'
with (O/'PAIRED_SESSIONS.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
by={}
for r in rows:by.setdefault(r['candidate'],{})[r['id']]=r
ref=by['TREND_BALANCED'];groups=sorted({r['group'] for r in ref.values()});rng=np.random.default_rng(20261021);draws=rng.integers(0,len(groups),size=(4000,len(groups)));out=[]
for kind in ['MARGIN_BALANCED','MARGIN_STEADY_GUARD']:
    for metric in ['overall_MAE','late_MAE','ALL_RISE_MAE','ALL_FALL_MAE','ALL_RISE_direction','ALL_FALL_direction','LATE_RISE_direction','LATE_FALL_direction','LATE_STEADY_direction']:
        picked=[(a,by[kind][uid]) for uid,a in ref.items() if a.get(metric) and uid in by[kind] and by[kind][uid].get(metric)];counts=np.array([sum(a['group']==g for a,b in picked) for g in groups]);sums=np.array([sum(float(b[metric])-float(a[metric]) for a,b in picked if a['group']==g) for g in groups]);den=counts[draws].sum(axis=1);valid=den>0;boot=sums[draws].sum(axis=1)[valid]/den[valid]
        differences=[float(b[metric])-float(a[metric]) for a,b in picked];direction=metric.endswith('direction');out.append(dict(candidate=kind,metric=metric,sessions=len(picked),groups=int(sum(counts>0)),new_minus_previous=float(np.mean(differences)),descriptive_95=[float(x) for x in np.percentile(boot,[2.5,97.5])],improved=sum(x>1e-12 if direction else x<-1e-12 for x in differences),worse=sum(x<-1e-12 if direction else x>1e-12 for x in differences),equal=sum(abs(x)<=1e-12 for x in differences)))
save(O/'PAIRED_DIAGNOSTICS.json',dict(status='COMPLETE_PAIRED_DEVELOPMENT_DIAGNOSTICS',resamples=4000,unit='27 whole groups with paired sessions; descriptive conditional interval, not independent post-selection inference',statistics=out))
print(json.dumps([x for x in out if x['metric'] in ['late_MAE','LATE_RISE_direction','LATE_FALL_direction']],ensure_ascii=False))
