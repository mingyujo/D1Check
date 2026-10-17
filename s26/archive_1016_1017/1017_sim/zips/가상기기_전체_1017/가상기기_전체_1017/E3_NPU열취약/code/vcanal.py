import json,statistics as st
R=[json.loads(l) for f in ['vcout0.jsonl','vcout1.jsonl'] for l in open(f)]
print('errors',sum('error' in r for r in R),'censored',sum(r.get('censored') is not None for r in R if 'error' not in r))
D={(r['vid'],r['wid'],r['context'],r['stream'],r['policy']):r for r in R if 'error' not in r}
B=['FIFO_BF_CN','FIFO_BF_ANY','EDF_BF_ANY','FIFO_PAIR_CN']
for vid in ['T0.5','T1.0','T2.0']:
  allk=[];tw=0;tn=0
  for w in ['D50_g0.55_c7d1_B','D25_g0.45_c7d1_B','D50_g0.65_c5d3_B','D50_g0.537155_c6d2_B']:
    keys=sorted({(k[2],k[3]) for k in D if k[0]==vid and k[1]==w})
    g=lambda t,p:D[(vid,w)+t+(p,)]
    pct=lambda p,f='on_time',d='n':sum(g(t,p)[f] for t in keys)/sum(g(t,p)[d] for t in keys)*100
    share=lambda p:(lambda a,b:a/(a+b)*100 if a+b else 0)(sum((g(t,p)['routes'] or {}).get('classification_NPU',0) for t in keys),sum((g(t,p)['routes'] or {}).get('classification_GPU',0) for t in keys))
    bb=max(B,key=pct); win=sum(g(t,'OWN_NW')['on_time']>max(g(t,b)['on_time'] for b in B) for t in keys); tw+=win; tn+=len(keys)
    mJ=lambda p:st.mean(g(t,p)['J'] for t in keys); mA=lambda p:st.mean(g(t,p)['AP_mean'] for t in keys)
    print(f"{vid} {w:20s} | OWN {pct('OWN_NW'):5.1f} (긴급 {pct('OWN_NW','u_on','u_n'):5.1f}) NPU {share('OWN_NW'):5.1f}% | NPU만 {pct('OWN_NPU'):5.1f} | best {bb} {pct(bb):5.1f} (긴급 {pct(bb,'u_on','u_n'):5.1f}) | win {win}/{len(keys)} | J {mJ('OWN_NW'):6.1f} vs {mJ(bb):6.1f} | AP {mA('OWN_NW'):.2f} vs {mA(bb):.2f} | 미완료 {st.mean(g(t,'OWN_NW')['unfinished'] for t in keys):.1f}/{st.mean(g(t,bb)['unfinished'] for t in keys):.1f}")
  print(f"  {vid} TOTAL win {tw}/{tn} = {tw/tn*100:.1f}%")
