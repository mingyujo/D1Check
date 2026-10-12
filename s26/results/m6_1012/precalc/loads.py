"""M6 부하 L · B 정의 (등록 §3-2 와 같은 식) + R3 점유 표본 bootstrap 으로 완료 시각 · 긴급 응답 예상 [E]."""
import json, random, statistics as st
OCC={tuple(k.split("|")):v for k,v in json.load(open("r3_occ.json")).items()}
def load_L():  # 100건 · 400 ms · 짝=분류 urgent · 홀=탐지 normal
    return [dict(i=i,t=35.0+0.4*i,task='classification' if i%2==0 else 'detection') for i in range(100)]
def load_B():  # 10 버스트 × 10건 · 버스트 주기 4 s · 버스트 안 50 ms · 짝=분류 · 홀=탐지
    out=[]
    for k in range(10):
        for j in range(10):
            i=10*k+j; out.append(dict(i=i,t=35.0+4.0*k+0.05*j,task='classification' if j%2==0 else 'detection'))
    return out
POL={'C':'CPU_URGENT_ONLINE_V1','G':'B2_PARALLEL_ONLINE_V1','N':'S26_NPU_PARALLEL_V1'}
def lane(pol,task):
    if pol=='C': return 'CPU'
    return 'CPU' if task=='detection' else ('GPU' if pol=='G' else 'NPU')
def sim(reqs,pol,rng,slow=1.0):
    P=POL[pol]; free={}; queues={}; done=[]
    # event-driven per lane, non-preemptive, urgent first then ordinal
    import heapq
    pending=sorted(reqs,key=lambda r:r['t'])
    lanes={}
    for r in pending: lanes.setdefault(lane(pol,r['task']),[]).append(r)
    for ln,rs in lanes.items():
        t=0.0; waiting=[]; idx=0
        while idx<len(rs) or waiting:
            if not waiting: t=max(t,rs[idx]['t'])
            while idx<len(rs) and rs[idx]['t']<=t: waiting.append(rs[idx]); idx+=1
            waiting.sort(key=lambda r:(0 if r['task']=='classification' else 1, r['i']))
            r=waiting.pop(0)
            d=rng.choice(OCC[(P,r['task'],ln)])/1000*slow
            t=t+d; done.append(dict(r,end=t,resp=t-r['t']))
    return done
def summarize(load,name,reps=500):
    rng=random.Random(20261012); out={}
    for pol in 'CGN':
        last=[];p95=[];umiss=[];nmax=[]
        for _ in range(reps):
            d=sim(load,pol,rng)
            last.append(max(x['end'] for x in d))
            u=sorted(x['resp'] for x in d if x['task']=='classification'); n=[x['resp'] for x in d if x['task']=='detection']
            p95.append(u[int(round(0.95*len(u)))-1]*1000); umiss.append(sum(x>1.5 for x in u)); nmax.append(max(n))
        d=sim(load,pol,rng,slow=1.6)
        out[pol]=dict(last_med=st.median(last),last_max=max(last),urgent_p95_med=st.median(p95),urgent_miss_max=max(umiss),normal_resp_max=max(nmax),last_if_1p6x=max(x['end'] for x in d))
    return out
if __name__=="__main__":
    res={}
    for nm,L in [("L",load_L()),("B",load_B())]:
        print(nm,len(L),"cls",sum(r['task']=='classification' for r in L),"first %.2f last %.3f"%(L[0]['t'],L[-1]['t']))
        res[nm]=summarize(L,nm)
        for p,v in res[nm].items(): print("  ",p,{k:round(x,3) for k,x in v.items()})
    json.dump(res,open("load_sim.json","w"),indent=1)
