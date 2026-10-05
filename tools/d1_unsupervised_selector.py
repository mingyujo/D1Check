"""Unsupervised history clustering + development-outcome policy calibration.
Saved-result, post-hoc study only: no new scheduler/device simulation.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
import numpy as np
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score,adjusted_rand_score
from tools import d1_supervised_selector as m
p=m.p
ROOT=p.ROOT/'docs/results/unsupervised_selector_01'


def history_matrix():
    keys=[(e,seed) for e in m.s.envelopes() if not m.holdout(e) for seed in (81001,81002)]
    return keys,np.asarray([m.features(m.previous(e,seed),0) for e,seed in keys])


def cluster_fit(X,kind):
    if kind not in ('kmeans','gmm'):raise ValueError('unknown clustering')
    if X.shape!=(36,5) or not np.isfinite(X).all():raise ValueError('invalid training features')
    scaler=StandardScaler().fit(X);Z=scaler.transform(X);candidates=[]
    for k in (3,6):
        model=(KMeans(n_clusters=k,n_init=20,random_state=20261005) if kind=='kmeans'
               else GaussianMixture(n_components=k,covariance_type='diag',n_init=5,reg_covar=1e-4,random_state=20261005))
        labels=model.fit_predict(Z)
        if kind=='gmm' and not model.converged_:raise ValueError('GMM not converged')
        score=float(silhouette_score(Z,labels));bic=float(model.bic(Z)) if kind=='gmm' else None
        candidates.append(((-score if kind=='kmeans' else bic,k),model,labels,dict(k=k,silhouette=score,bic=bic)))
    _,model,labels,_=min(candidates,key=lambda z:z[0])
    centers=model.cluster_centers_ if kind=='kmeans' else model.means_
    radius={int(c):float(max(np.linalg.norm(Z[labels==c]-centers[c],axis=1))) for c in set(labels)}
    return scaler,model,labels,radius,[z[3] for z in candidates]


def calibrate(keys,labels,rows):
    index={(r['envelope'],int(r['seed']),r['scenario'],r['policy']):r for r in rows if r['stage']=='development'}
    mapping={}
    for c in set(labels):
        members=[(e['id'],seed) for (e,seed),label in zip(keys,labels) if label==c];eligible=[]
        for pol in m.POLICIES:
            xs=[index[eid,seed,sc,pol] for eid,seed in members for sc in m.s.a.old.SCENARIOS]
            if any(r[t] is None for r in xs for t in m.TARGETS[1:]):raise ValueError('missing cost')
            if all(r['completed']==r['planned']==r['deadline_met'] for r in xs):
                eligible.append(dict(policy=pol,**{t:statistics.mean(r[t] for r in xs) for t in m.TARGETS[1:]}))
        mapping[int(c)]={}
        for mode in m.MODES:
            fields=('energy_j','peak_ap_c','thermal_degree_seconds') if mode=='energy' else ('peak_ap_c','thermal_degree_seconds','energy_j')
            mapping[int(c)][mode]=min(eligible,key=lambda r:tuple(round(r[t],6) for t in fields)+(r['policy'],))['policy'] if eligible else None
    return mapping


def choose(fitted,mapping,history,mode):
    if mode not in m.MODES:raise ValueError('unknown mode')
    scaler,model,_,radius,_=fitted
    x=np.asarray([m.features(history,0)]);z=scaler.transform(x);c=int(model.predict(z)[0])
    centers=model.cluster_centers_ if hasattr(model,'cluster_centers_') else model.means_
    distance=float(np.linalg.norm(z[0]-centers[c]))
    if distance>radius[c]+1e-9:pol,reason='EFT_REFERENCE','outside_training_radius'
    elif mapping[c][mode] is None:pol,reason='EFT_REFERENCE','no_cluster_feasible_policy'
    else:pol,reason=mapping[c][mode],'cluster_policy'
    return dict(cluster=c,distance=distance,radius=radius[c],policy=pol,reason=reason)


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),Path(m.__file__),m.SOURCE,p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']
    hashes={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    spec=dict(base_head='323c8628caa35369c577fb74bfa9888f3529eabb',utc=datetime.now(timezone.utc).isoformat(),
        methods=['kmeans','gmm'],candidate_k=[3,6],k_selection='KMeans max train silhouette; GMM min train BIC',
        train='18 envelopes x seeds81001/81002,36 independent synthetic history windows',
        evaluation_seeds=[91002,91003],evaluation='saved previously observed outcomes; posthoc NOT fresh holdout',
        policy_mapping='all cluster development contexts complete every deadline, then mean J or peak AP',
        radius='max assigned training distance in standardized feature space, not calibrated uncertainty',
        no_new_simulations=True,device_commands=0,experiment_ready=False)
    p.write(out/'preregistered.json',dict(spec=spec,hashes=hashes))
    rows=m.read(m.SOURCE);keys,X=history_matrix();fits={k:cluster_fit(X,k) for k in spec['methods']}
    maps={k:calibrate(keys,v[2],rows) for k,v in fits.items()}
    frozen={}
    train=[]
    for kind,f in fits.items():
        scaler,model,labels,radius,scores=f;centers=model.cluster_centers_ if kind=='kmeans' else model.means_
        frozen[kind]=dict(scores=scores,k=len(centers),scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),
            centers=centers.tolist(),radius=radius,mapping=maps[kind],
            paired_history_ARI=float(adjusted_rand_score(labels[::2],labels[1::2])),
            parameters=model.get_params(),weights=model.weights_.tolist() if kind=='gmm' else None,
            covariances=model.covariances_.tolist() if kind=='gmm' else None)
        for (e,seed),x,c in zip(keys,X,labels):train.append(dict(method=kind,envelope=e['id'],seed=seed,cluster=int(c),**dict(zip(m.FEATURES,x))))
    p.write(out/'freeze_before_evaluation.json',dict(utc=datetime.now(timezone.utc).isoformat(),models=frozen,hashes=hashes))
    m.s.save_rows(out/'clusters.csv',train)
    ix={(r['envelope'],int(r['seed']),r['scenario'],r['policy']):r for r in rows}
    decisions=[];comparisons=[]
    for kind in fits:
        for mode in m.MODES:
            allxs=[]
            for e in m.s.envelopes():
                for seed in spec['evaluation_seeds']:
                    d=choose(fits[kind],maps[kind],m.previous(e,seed),mode)
                    decisions.append(dict(method=kind,mode=mode,envelope=e['id'],seed=seed,withheld=m.holdout(e),**d))
                    allxs.extend(ix[e['id'],seed,sc,d['policy']] for sc in m.s.a.old.SCENARIOS)
            for subset in ('all','seen','withheld'):
                ids={e['id'] for e in m.s.envelopes() if subset=='all' or m.holdout(e)==(subset=='withheld')}
                xs=[r for r in allxs if r['envelope'] in ids]
                for ref in ('EFT_REFERENCE','SPLIT_REFERENCE','CPU_REFERENCE'):
                    bs=[ix[r['envelope'],int(r['seed']),r['scenario'],ref] for r in xs]
                    comparisons.append(dict(method=kind,mode=mode,subset=subset,reference=ref,
                        full_cases=sum(r['deadline_met']==r['planned']==r['completed'] for r in xs),
                        worse_service_cases=sum(r['deadline_met']<b['deadline_met'] for r,b in zip(xs,bs)),
                        **m.group_result(xs,bs)))
    m.s.save_rows(out/'decisions.csv',decisions);m.s.save_rows(out/'comparison.csv',comparisons)
    # Compare earlier frozen supervised learners on EXACTLY these saved seeds.
    # Refit from original development rows, never from evaluation outcomes.
    XX,YY,_=m.training(rows);bounds=(XX[:,:5].min(axis=0),XX[:,:5].max(axis=0))
    supervised=[]
    for mode,kind in [('energy','tree'),('thermal','boosting')]:
        ms=m.fit(XX,YY,kind);xs=[]
        for e in m.s.envelopes():
            for seed in spec['evaluation_seeds']:
                d=m.choose(ms,m.previous(e,seed),mode,bounds)
                xs.extend(ix[e['id'],seed,sc,d['policy']] for sc in m.s.a.old.SCENARIOS)
        bs=[ix[r['envelope'],int(r['seed']),r['scenario'],'EFT_REFERENCE'] for r in xs]
        supervised.append(dict(method=kind,mode=mode,reference='EFT_REFERENCE',**m.group_result(xs,bs)))
    m.s.save_rows(out/'supervised_same_inputs.csv',supervised)
    assert hashes=={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    summary=dict(models=frozen,comparison=[r for r in comparisons if r['subset']=='all' and r['reference']=='EFT_REFERENCE'],
        fallback={k+'/'+mode:dict(Counter(d['reason'] for d in decisions if d['method']==k and d['mode']==mode)) for k in fits for mode in m.MODES},
        comparisons=648,unique_saved_cases=162,device_commands=0,new_simulations=0,hashes_unchanged=True,experiment_ready=False)
    p.write(out/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    Z=fits['kmeans'][0].transform(X);xy=PCA(n_components=2).fit_transform(Z)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for ax,(kind,f) in zip(axs,fits.items()):
        ax.scatter(xy[:,0],xy[:,1],c=f[2],cmap='tab10');ax.set_title(kind+': training features only');ax.set_xlabel('PC1');ax.set_ylabel('PC2')
    fig.suptitle('Clusters are NOT energy/thermal effectiveness labels');fig.tight_layout();fig.savefig(out/'clusters.png',dpi=130);plt.close(fig)
    table=''.join('<tr>'+''.join(f'<td>{r[k]:.6f}</td>' if isinstance(r[k],float) else f'<td>{r[k]}</td>' for k in
        ('method','mode','deadline_met','reference_deadline_met','mean_delta_energy_j','mean_delta_peak_ap_c','worse_service_cases'))+'</tr>' for r in summary['comparison'])
    (out/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>비지도 군집 정책 탐색</title><style>body{max-width:1100px;margin:40px auto;font:17px/1.6 sans-serif}td,th{border:1px solid #ccc;padding:8px}table{border-collapse:collapse}img{max-width:100%}</style><h1>비지도 군집화＋개발 성적 기반 정책 연결</h1><p>저장된 합성입력 결과의 사후 분석. 새 실측·새 시뮬레이션·독립 확인 아님. 군집은 비용/기한 라벨 없이 fitting, 정책 연결은 개발 성적 사용. 기한 보장/물리모형 개선 아님.</p><img src="clusters.png" alt="개발 특징의 군집"><h2>EFT 대비 동일162조건, 요청분모7776</h2><table><tr><th>방법</th><th>목적</th><th>기한 충족</th><th>EFT 충족</th><th>ΔJ</th><th>Δ최고AP</th><th>서비스 악화 사례</th></tr>'''+table+'''</table><p><a href="comparison.csv">전체 기준·미학습 조합</a> · <a href="supervised_same_inputs.csv">같은 입력의 지도학습</a> · <a href="decisions.csv">선택과 fallback</a> · <a href="../README.md">판정·재현</a></p></html>''',encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='models'},indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();run(args.output)
