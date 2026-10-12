import json, statistics as st
from load import sessions
occ={}
coord=[]
for tag in ["R3","R4C","SS"]:
    for s in sessions(tag):
        c0=s['cb']['start_ns']; pol=s['summ']['policy']
        rows=s['cb']['rows']
        last=max(r['lane_available_ns'] for r in rows if r.get('lane_available_ns'))
        first=min(r['scheduled_arrival_ns'] for r in rows)
        coord.append((tag,s['summ']['session_index'],pol,(first-c0)/1e9,(last-c0)/1e9,(s['cb']['end_ns']-c0)/1e9, s['val'].get('eligible')))
        if tag=="R3":
            for r in rows:
                k=(pol,r['task_id'],r['selected_backend'])
                occ.setdefault(k,[]).append((r['lane_available_ns']-r['dispatch_ns'])/1e6)
json.dump({"|".join(k):v for k,v in occ.items()},open("r3_occ.json","w"))
for k,v in sorted(occ.items()): print(k,len(v),"med %.1f p95 %.1f max %.1f"%(st.median(v),sorted(v)[int(len(v)*.95)],max(v)))
print("tag idx policy first_arrival last_lane_avail window_end eligible")
for c in coord: print("%s %2d %-24s %.2f %.2f %.2f %s"%c)
