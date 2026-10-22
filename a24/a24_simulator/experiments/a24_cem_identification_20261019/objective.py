"""Actual episode outcome, independent of local nominal forecast ranking."""
import bisect,math
NS=10**9
def window(result,physics,end):
    E=Q=0.;peak=result['initial_ap_c']
    for t in result['trace']:
        lo=max(35*NS,t['start_ns']);hi=min(round(end*NS),t['end_ns'])
        if hi<=lo:continue
        assert lo==t['start_ns']
        if hi==t['end_ns']:v=t
        else:_,v=physics.transition(t['state'],t['active'],(hi-lo)/NS)
        E+=v['increment'];Q+=v['temperature_area'];peak=max(peak,v['peak'])
    return dict(increment=E,J=E+physics.c.baseline*max(0,end-35),AP=Q/max(1e-9,end-35),peak=peak)
def outcome(result,case,physics):
    q=result['requests'];drain=case['drain_stop_s'];complete=all(r['available_ns'] is not None and r['available_ns']/NS<=drain for r in q);end=max(case['supply_stop_s'],max((r['available_ns']/NS for r in q),default=35)) if complete else drain
    own=window(result,physics,end);tail=window(result,physics,end+30)['increment']-own['increment'];H=case['supply_stop_s']+30;fixed=window(result,physics,H);cost=[(own['J']+tail)/(case['n']*.35),max(0.,fixed['AP']-26)/10,0.,0.,sum(r['available_ns'] is None or r['available_ns']/NS>drain for r in q)/case['n']]
    for priority,ix in [('U',2),('N',3)]:
        rows=[r for r in q if r['priority']==priority]
        for r in rows:
            response=r['response_ns']/NS if r['response_ns'] is not None and r['response_ns']/NS<=drain else drain;ttl=max(.05,(r['deadline_ns']-r['scheduled_arrival_ns'])/NS);late=r['response_ns'] is None or r['response_ns']/NS>min(drain,r['deadline_ns']/NS);latency=max(0,response-r['scheduled_arrival_ns']/NS)
            cost[ix]+=(float(late)+.2*min(5.,latency/ttl))/max(1,len(rows))
    scalar=sum(a*b for a,b in zip(cost,[1,1,12,6,3]));assert math.isfinite(scalar)
    return dict(cost=cost,scalar=scalar,own_end_s=end,completion=complete,own=own,own_with_activity_tail_J=own['J']+tail,fixed=fixed,fixed_end_s=H,deadline_uses_actual=True,reference_calibration_used=False)
