import json, statistics as st
from load import sessions
rows=[]
for tag in ["R3","R4C","SS"]:
    prev_end=None
    S=sorted(sessions(tag),key=lambda s:s['summ']['common_start_ns'])
    for s in S:
        ev=s['ev']; c0=s['summ']['common_start_ns']/1e9
        ph={}
        for e in ev:
            if e['kind'] in('phase_start','phase_end'): ph[(e['kind'],e['phase'])]=e['mono_ns']/1e9
        t_setup=ev[0]['mono_ns']/1e9
        hal=[(float(h['device_boottime_s']),float(h['AP']),float(h['SKIN']),float(h['BAT'])) for h in s['hal']]
        def at(t):
            c=min(hal,key=lambda h:abs(h[0]-t)); return c if abs(c[0]-t)<3 else None
        prep=[h for h in hal if t_setup<=h[0]<c0]
        a0=at(t_setup); aT0=at(c0); a35=at(c0+34)
        ps=[e for e in ev if e['kind']=='power_sample']
        def P(t1,t2):
            w=[-(e['current_raw']*1e-6)*(e['voltage_mV']*1e-3) for e in ps if t1<=e['mono_ns']/1e9<t2]; return st.mean(w) if w else None
        gap=(t_setup-prev_end) if prev_end else None
        prev_end=s['summ']['common_end_ns']/1e9
        dt=[b[0]-a[0] for a,b in zip(hal,hal[1:])]
        apch=[hal[i+1][0] for i in range(len(hal)-1) if hal[i+1][1]!=hal[i][1]]
        rows.append(dict(tag=tag,idx=s['summ']['session_index'],policy=s['summ']['policy'][:6],block=s['summ']['block'],
            setup_s=c0-t_setup, AP_setup=a0 and a0[1], AP_prep_max=max(h[1] for h in prep) if prep else None,
            AP_t0=aT0 and aT0[1], AP_t34=a35 and a35[1], SKIN_t0=aT0 and aT0[2], BAT_t0=aT0 and aT0[3],
            P_prep=P(t_setup,c0-30), P_base=P(c0-30,c0), P_0_34=P(c0,c0+34), gap_prev_s=gap,
            hal_dt_med=st.median(dt), ap_change_med=st.median([b-a for a,b in zip(apch,apch[1:])]) if len(apch)>2 else None))
json.dump(rows,open("residual_rows.json","w"),indent=1)
print("tag idx pol blk setup_s AP_setup AP_prepmax AP_t0 AP_t34 SKIN_t0 P_prep P_base P_0_34 gap halDt APchg")
for r in rows:
    f=lambda x,n=1: "-" if x is None else f"{x:.{n}f}"
    print(r['tag'],r['idx'],r['policy'],r['block'],f(r['setup_s'],0),f(r['AP_setup']),f(r['AP_prep_max']),f(r['AP_t0']),f(r['AP_t34']),f(r['SKIN_t0']),f(r['P_prep'],2),f(r['P_base'],2),f(r['P_0_34'],2),f(r['gap_prev_s'],0),f(r['hal_dt_med'],2),f(r['ap_change_med'],2))
