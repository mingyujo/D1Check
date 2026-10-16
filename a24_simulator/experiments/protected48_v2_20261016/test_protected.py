import copy,unittest
import numpy as np
from protected_policy import protected_bank, marginal_terms, owner_remaining, CONFIG, NS
from dense_rewards import energy_integral,make_costs

P={'classification_CPU':.58,'classification_GPU':.47,'detection_CPU':.71,'detection_GPU':.60,
   'classification_GPU+detection_CPU':.88,'classification_CPU+detection_GPU':.88,
   'classification_CPU+classification_GPU':.75,'detection_CPU+detection_GPU':1.01}
G={k:v*.2 for k,v in P.items()}
def q(rid,task='C',priority='U',due=1.54):
    return dict(request_id=rid,ordinal=int(rid[-1]),task=task,priority=priority,
                scheduled_arrival_ns=0,queue_entry_ns=0,deadline_ns=round(due*NS))
def obs(now=1.27,owner=True):
    queue=[q('u0'),q('n1','D','N',5.)]
    owners={'GPU':dict(request_id='o2',task='D',route='GPU',dispatch_ns=0)} if owner else {}
    estimates={}
    for r in [*queue,*owners.values()]:
        estimates[r['request_id']]={b:dict(occupancy_ns=round(o*NS),response_ns=round(t*NS),energy_proxy_j=.5)
            for b,o,t in (('CPU',.11 if r['task']=='C' else .57,.10 if r['task']=='C' else .55),
                          ('GPU',.25 if r['task']=='C' else 1.1,.24 if r['task']=='C' else 1.08))}
    return dict(now_ns=round(now*NS),queue=queue,owners=owners,estimates=estimates,
        last_release_ns={},history={'planned_U':1,'planned_N':1},wait_used_ns=0,
        waited_request_ids=[],horizon_ns=180*NS,alpha=1.,heat_weight=.5,
        sensor=dict(AP_c=27.,power_w=1.2,age_s=0.,recent_activity={'CPU':0.,'GPU':0.,'NPU':0.},
                    ap_slope_c_s=0.,power_slope_w_s=0.))

class Tests(unittest.TestCase):
    def test_imminent_urgent_excludes_normal(self):
        b=protected_bank(obs(),P,G)
        self.assertTrue(b['mask'].any())
        for i in np.flatnonzero(b['mask']):self.assertEqual(b['actions'][i]['request_id'],'u0')
    def test_urgent_prevents_voluntary_wait(self):
        self.assertFalse(protected_bank(obs(),P,G)['mask'][72:75].any())
    def test_no_modification(self):
        a=obs();before=copy.deepcopy(a);protected_bank(a,P,G);self.assertEqual(a,before)
    def test_no_physical_mask_expansion(self):
        b=protected_bank(obs(),P,G);self.assertFalse(np.any(b['mask']&~b['physical_mask']))
    def test_no_npu(self):
        b=protected_bank(obs(owner=False),P,G)
        self.assertFalse(any(b['mask'][i] and b['actions'][i].get('route')=='NPU' for i in range(72)))
    def test_loose_deadlines_keep_both_routes(self):
        a=obs(now=.1,owner=False)
        for row in a['queue']:row['deadline_ns']=20*NS
        b=protected_bank(a,P,G)
        for task in ('C','D'):
            routes={b['actions'][i]['route'] for i in np.flatnonzero(b['mask'][:72]) if next(q for q in a['queue'] if q['request_id']==b['actions'][i]['request_id'])['task']==task}
            self.assertEqual(routes,{'CPU','GPU'})
    def test_future_duration_keys_do_not_affect_policy(self):
        a=obs();b=copy.deepcopy(a);b['future_sampled_duration_ns']=10**12
        x,y=protected_bank(a,P,G),protected_bank(b,P,G)
        self.assertTrue(np.array_equal(x['mask'],y['mask']));self.assertTrue(np.array_equal(x['prior_logits'],y['prior_logits']))
    def test_already_infeasible_has_recovery(self):
        a=obs(now=2.)
        b=protected_bank(a,P,G);self.assertTrue(b['mask'].any())
    def test_owner_elapsed_uses_nominal_margin(self):
        a=obs();self.assertAlmostEqual(owner_remaining(a,'GPU'),max(.02,1.2*1.1-1.27))
    def test_marginal_energy_observer(self):
        a=obs(now=.1,owner=False);e,h=marginal_terms(a,a['queue'][0],'CPU',P,G)
        self.assertAlmostEqual(e,.11*.58);self.assertAlmostEqual(h,.11*.58*.2)
    def test_shared_increment_not_baseline(self):
        a=obs(now=.1);e,_=marginal_terms(a,a['queue'][0],'CPU',P,G)
        self.assertAlmostEqual(e,.11*(P['classification_CPU+detection_GPU']-P['detection_GPU']))
    def test_dense_energy_solo_overlap(self):
        rows=[dict(task='C',route='GPU',start_s=0.,end_s=1.),dict(task='D',route='CPU',start_s=.5,end_s=1.5)]
        self.assertAlmostEqual(energy_integral(rows,P,0,1.5),.5*.47+.5*.88+.5*.71)
    def test_dense_reward_telescope_and_deadline(self):
        row={**q('u0',due=1.),'response_ns':round(1.3*NS)}
        result={'prediction':{'requests':[row],'decisions':[{'time_ns':0,'public_state':{'queue':[row]}},{'time_ns':NS,'public_state':{'queue':[row]}}]},
                'summary':{'diagnostics':{'common_work_window_s':[0.,2.],'work_window_increment_J_proxy':.4*P['classification_CPU']},
                           'gantt':[dict(task='C',route='CPU',start_s=1.,end_s=1.4)]},
                'AP':{'t_s':[0.,1.,2.],'ap_c':[20.,21.,20.]}}
        costs,counts,proof=make_costs(result,[{'time_ns':0},{'time_ns':NS}],dict(initial_ap_c=20.,drain_stop_ns=2*NS),{'cost_anchor':{'energy_increment_w':P}})
        self.assertAlmostEqual(costs[:,0].sum(),.4*.58/10)
        self.assertAlmostEqual(costs[:,2].sum(),1.3)
        self.assertEqual(proof['terminal_potential'],[0.,0.]);self.assertEqual(counts['U'],1)
    def test_safety_configuration_is_explicit(self):
        self.assertEqual(CONFIG['goal_service_alpha'],1.)
        self.assertGreater(CONFIG['nominal_bound_factor'],1.)

    def test_actor_resource_wait_not_in_kernel_decisions(self):
        row={**q('u0',due=1.),'response_ns':round(1.3*NS)}
        result={'prediction':{'requests':[row],'decisions':[]},
                'summary':{'diagnostics':{'common_work_window_s':[0.,2.],'work_window_increment_J_proxy':.4*P['classification_CPU']},
                           'gantt':[dict(task='C',route='CPU',start_s=1.,end_s=1.4)]},
                'AP':{'t_s':[0.,1.,2.],'ap_c':[20.,21.,20.]}}
        # Two actor decisions at t=0, one busy RESOURCE_WAIT, then t=1.
        frames=[{'time_ns':0,'index':0},{'time_ns':0,'index':75},{'time_ns':NS,'index':0}]
        snapshots=[{'time_ns':f['time_ns'],'chosen_index':f['index'],'public_state':{'queue':[row]}} for f in frames]
        args=(result,frames,dict(initial_ap_c=20.,drain_stop_ns=2*NS),{'cost_anchor':{'energy_increment_w':P}})
        costs,_,proof=make_costs(*args,actor_decisions=snapshots)
        self.assertEqual(costs.shape,(3,5));self.assertAlmostEqual(costs[:,2].sum(),1.3)
        self.assertAlmostEqual(proof['energy_telescope_error'],0.)
        snapshots[1]['time_ns']=1
        with self.assertRaisesRegex(ValueError,'time mismatch'):make_costs(*args,actor_decisions=snapshots)

if __name__=='__main__':unittest.main()
