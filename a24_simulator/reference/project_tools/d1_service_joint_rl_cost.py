"""New objective version: absolute service counts, strong JointList reference.

Same AP telescope/energy scale/PPO architecture, different objective semantics.
Old32/512 learners and their schema/weights must never be resumed here.
"""
import numpy as np
from tools import d1_rolling_list_rl as r

OBJECTIVE='JOINT_LIST_ABSOLUTE_SERVICE_AP_PRIMARY_V2'
COST_CHANNELS=('signed_J_difference_vs_JointList','absolute_incomplete_count',
               'absolute_urgent_failure_count','absolute_normal_failure_count',
               'positive_urgent_P95_difference_vs_JointList_over1500ms')

def episode_targets(controller,row,curve,reference):
    frames,rewards,old_costs,valid=r.c.episode_targets(controller,row,curve,reference)
    if row['planned']!=reference['planned']:raise ValueError('same planned request contract')
    costs=old_costs.copy()
    costs[1]=row['planned']-row['completed']
    if valid[3]:costs[2]=float(row['urgent_failure'])
    if valid[4]:costs[3]=float(row['normal_failure'])
    # Signed J and relative P95 already use the unchanged1J/1500ms scales.
    # Absolute service is counted once. Relative excess remains diagnostic.
    for frame in frames:
        frame['target'][1:]=costs.astype(np.float32);frame['valid']=valid.copy()
    diagnostic=dict(objective=OBJECTIVE,channels=COST_CHANNELS,
        relative_excess=dict(incomplete=max(0.,costs[1]-(reference['planned']-reference['completed'])),
            urgent=max(0.,row['urgent_failure']-reference['urgent_failure']),normal=max(0.,row['normal_failure']-reference['normal_failure'])),
        absolute_service_not_subtracted_by_reference=True,double_counted_absolute_plus_excess=False,
        urgent_denominator=row.get('urgent_planned'),normal_denominator=row.get('normal_planned'),planned_denominator=row['planned'])
    return frames,rewards,costs,valid,diagnostic
