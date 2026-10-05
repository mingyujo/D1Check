"""Necessary CPU service-demand test for the current detection-only-CPU model.

Omit classification and post-response ownership: an optimistic relaxation.
Violation proves infeasibility only inside this fixed-duration model; passing
is not sufficient for nonpreemptive scheduling or an empirical guarantee.
"""
from tools import d1_empirical_request_policy as p


def capacity(tickets,profile):
    for q in tickets:p.backends(q)
    jobs=sorted((q for q in tickets if q['task']=='detection'),key=lambda q:q['arrival_ns'])
    duration=sum(profile['detection_CPU_normal'][:3])/1e9
    worst=dict(excess_s=0.,window_start_s=None,window_end_s=None,required_s=None,requests=0)
    # Same detection relative deadline means arrival/deadline ordering coincide.
    if len({q['deadline_offset_ns'] for q in jobs})>1:raise ValueError('unequal deadlines require general demand test')
    for i,q in enumerate(jobs):
        start=q['arrival_ns']/1e9
        for j in range(i,len(jobs)):
            end=(jobs[j]['arrival_ns']+jobs[j]['deadline_offset_ns'])/1e9
            demand=(j-i+1)*duration;excess=demand-(end-start)
            if excess>worst['excess_s']:
                worst=dict(excess_s=excess,window_start_s=start,window_end_s=end,required_s=demand,requests=j-i+1)
    return dict(**worst,necessary_condition_violated=worst['excess_s']>1e-9,
        conclusion='infeasible_in_fixed_service_model' if worst['excess_s']>1e-9 else 'not_ruled_out_not_proven_feasible')
