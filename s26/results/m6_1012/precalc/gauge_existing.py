import json, statistics as st
from collections import Counter
from load import sessions
res={}
for tag in ["R3","R4C","SS"]:
    S=sessions(tag); rows=[]
    vint=[]; vn=[]
    for s in S:
        ps=[e for e in s['ev'] if e['kind']=='power_sample']
        t=[e['mono_ns']/1e9 for e in ps]; v=[e['voltage_mV'] for e in ps]
        tv=[t[i+1] for i in range(len(v)-1) if v[i+1]!=v[i]]
        vint+=[b-a for a,b in zip(tv,tv[1:])]; vn.append(len(tv)/((t[-1]-t[0])/60))
        c0=s['summ']['common_start_ns']/1e9
        # E_int and E_cc in [5,115] s of common window
        w=[(ti,e) for ti,e in zip(t,ps) if c0+5<=ti<=c0+115]
        Eint=0
        for (ta,a),(tb,b) in zip(w,w[1:]):
            P=-(a['current_raw']*1e-6)*(a['voltage_mV']*1e-3); Eint+=P*(tb-ta)
        a,b=w[0][1],w[-1][1]
        dcc=(a['charge_counter_raw']-b['charge_counter_raw'])*1e-6*3600  # C
        Vm=st.mean(e['voltage_mV'] for _,e in w)*1e-3
        Ecc=dcc*Vm
        ncc=len(set(e['charge_counter_raw'] for _,e in w))-1
        rows.append(dict(name=s['name'],idx=s['summ']['session_index'],policy=s['summ']['policy'],block=s['summ']['block'],
                         Eint=Eint,Ecc=Ecc,cc_updates=ncc,span=w[-1][0]-w[0][0],Vmean=Vm))
    res[tag]=rows
    print(tag,"voltage change interval med %.1f s p10 %.1f p90 %.1f; changes/min med %.2f"%(st.median(vint),sorted(vint)[len(vint)//10],sorted(vint)[len(vint)*9//10],st.median(vn)))
    print("  cc updates in 5-115 s:",Counter(r['cc_updates'] for r in rows))
json.dump(res,open("gauge_existing_rows.json","w"),indent=1,ensure_ascii=False)
# R4C pairs
r=sorted(res["R4C"],key=lambda x:x['idx'])
print("R4C pairs (PAR - CPU), J in [5,115] s")
same=0
for blk,idxs in [("A",range(0,8)),("N",range(8,16))]:
    for p in range(4):
        ss=[x for x in r if x['idx'] in idxs and ((x['idx']-(8 if blk=='N' else 0))//2)==p]
        c=[x for x in ss if x['policy'].startswith('CPU')][0]; q=[x for x in ss if not x['policy'].startswith('CPU')][0]
        di=q['Eint']-c['Eint']; dc=q['Ecc']-c['Ecc']; s=(di>0)==(dc>0)
        same+=s
        print(f"  {blk}{p} idx {c['idx']},{q['idx']}: dE_int {di:+7.1f}  dE_cc {dc:+7.1f}  same_sign {s}  cc_updates C{c['cc_updates']} P{q['cc_updates']}")
print("same sign",same,"/8")
step=4275e-6*3600*st.mean(x['Vmean'] for x in r)
print("one cc step = %.1f J"%step)
