import json,statistics as st,sys
files=sys.argv[1].split(',')
R=[json.loads(l) for f in files for l in open(f)]
print('errors',sum('error' in r for r in R))
D={(r['vid'],r['wid'],r['context'],r['stream'],r['policy']):r for r in R if 'error' not in r}
B=['FIFO_BF_CN','FIFO_BF_ANY','EDF_BF_ANY','FIFO_PAIR_CN']
for vid in ['R','T2','P','PT1','PT2']:
  print('=== device',vid)
  for w in sorted({k[1] for k in D if k[0]==vid}):
    keys=sorted({(k[2],k[3]) for k in D if k[0]==vid and k[1]==w and all((vid,w,k[2],k[3],p) in D for p in ['OWN_NW']+B)})
    if not keys: continue
    g=lambda t,p:D[(vid,w)+t+(p,)]
    pct=lambda p:sum(g(t,p)['on_time'] for t in keys)/sum(g(t,p)['n'] for t in keys)*100
    share=lambda p:(lambda a,b:a/(a+b)*100 if a+b else 0)(sum((g(t,p)['routes'] or {}).get('classification_NPU',0) for t in keys),sum((g(t,p)['routes'] or {}).get('classification_GPU',0) for t in keys))
    bb=max(B,key=pct)
    win=sum(g(t,'OWN_NW')['on_time']>max(g(t,b)['on_time'] for b in B) for t in keys)
    dJ=[g(t,'OWN_NW')['J']-g(t,bb)['J'] for t in keys if g(t,'OWN_NW')['J'] is not None and g(t,bb)['J'] is not None]
    dA=[g(t,'OWN_NW')['AP_mean']-g(t,bb)['AP_mean'] for t in keys if g(t,'OWN_NW')['AP_mean'] is not None and g(t,bb)['AP_mean'] is not None]
    print(f"  {w:20s} n={g(keys[0],'OWN_NW')['n']:4d} | OWN {pct('OWN_NW'):5.1f} (NPU {share('OWN_NW'):5.1f}%) | BF_CN {pct('FIFO_BF_CN'):5.1f} BF_ANY {pct('FIFO_BF_ANY'):5.1f} (NPU {share('FIFO_BF_ANY'):4.1f}%) EDF_ANY {pct('EDF_BF_ANY'):5.1f} PAIR_CN {pct('FIFO_PAIR_CN'):5.1f} | win {win}/{len(keys)} | dJ {st.mean(dJ) if dJ else float('nan'):+6.1f} dAP {st.mean(dA) if dA else float('nan'):+.3f} vs {bb}")
