"""Read the same predictions through common fixed and workload windows."""
import hashlib,json
from four_route_model import conditional_energy
def add_diagnostics(summary,public,profile,ap,activity):
    arrivals=[q['scheduled_arrival_ns']/1e9 for q in public['requests']]
    start=min(arrivals); horizon=min(180.,max(arrivals)+15.)
    energy=conditional_energy(activity,profile,start,horizon)
    t,v=ap.get('t_s',[]),ap.get('ap_c',[])
    pairs=[(x,y) for x,y in zip(t,v) if start<=x<=horizon]
    summary['diagnostics']={
        'common_work_window_s':[start,horizon],
        'window_rule':'earliest arrival to latest arrival+15s, fixed from input for every policy',
        'work_window_total_J_proxy':energy.get('historical_conditional_J'),
        'work_window_increment_J_proxy':sum(energy.get('increment_terms_J',{}).values()),
        'whole_window_baseline_J':summary['energy'].get('baseline_J'),
        'whole_window_increment_J_proxy':sum(summary['energy'].get('increment_terms_J',{}).values()),
        'whole_window_baseline_fraction':summary['energy']['baseline_J']/summary['J_proxy'] if summary['J_proxy'] else None,
        'work_window_peak_AP_c':max((y for x,y in pairs),default=None),
        'AP_peak_rise_from_initial_c':summary.get('AP_peak_c',0)-public['initial_ap_c'],
        'measured_J':None,'energy_CI':None,'not_new_measurement':True}
def schedule_groups(rows):
    groups={}
    for r in rows:
        trace=[{k:q.get(k) for k in ('request_id','route','dispatch_ns','response_ns','available_ns')} for q in r['requests']]
        key=hashlib.sha256(json.dumps(trace,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        groups.setdefault(key,[]).append(r['policy'])
    return {'unique_schedules':len(groups),'groups':list(groups.values()),'same_schedule_does_not_prove_same_policy':True,
            'zero_WAIT_policies':[r['policy'] for r in rows if r['wait_s']==0]}
