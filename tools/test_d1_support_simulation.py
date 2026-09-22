"""실측을 사용하지 않는 손계산 가능한 synthetic engine/계약 검증."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_support_simulation as s


def scenario():
    return dict(id='fixture',urgent_ns=90,normal_ns=800,arrivals=[0]*12,
                tasks=['classification','detection']*6,priorities=['urgent','normal']*6,
                thermal=0,resident=True,warmup=6,source_state_budget='urgent_warm')


def episode(sid,corun=False,solo=None):
    rows=[];lanes={'CPU':0,'GPU':0}
    for i in range(6 if solo else 12):
        task=solo[0] if solo else ('classification' if i%2==0 else 'detection')
        backend=solo[1] if solo else ('GPU' if corun and i%2 else 'CPU')
        priority='normal' if solo or task=='detection' else 'urgent'
        duration=(10 if task=='classification' else 100)+(5 if backend=='GPU' else 0)
        start=lanes[backend]+1;end=start+duration;lanes[backend]=end
        rows.append(dict(ordinal=i,source_request=f'{sid}/{i}',task=task,backend=backend,
                         priority=priority,arrival=0,dispatch=start,ready=end-2,
                         persist=end-1 if priority=='normal' else None,release=end,gap=1))
    return dict(session_id=sid,rows=rows,end=max(lanes.values())+1,tail=1,footprint=10,setup=[1],
                fingerprint=sid+'trace',memory=[dict(stage='before_workload',thermal_status=0,low_memory=False,
                 avail_bytes=1000,threshold_bytes=100,observed_peak_pss_bytes=10)])


def fixture():
    return dict(input_sha256=s.base.INPUT_SHA,
                pairs=[dict(pair_id=str(i),A=episode(f'A{i}'),B=episode(f'B{i}',True)) for i in range(5)],
                solo={t+'/'+b:[episode(f'{t}{b}{i}',solo=(t,b)) for i in range(5)]
                      for t in ('classification','detection') for b in ('CPU','GPU')})


def scenarios():
    return [dict(scenario(),id=str(i)) for i in range(54)]


class SupportSimulationTests(unittest.TestCase):
    def test_support_catalog_and_static_cpu_alias(self):
        c=fixture();self.assertTrue(s.validate_catalog(c))
        self.assertEqual(s.static_mapping(c),dict(classification='CPU',detection='CPU'))
        self.assertEqual(s.choose('STATIC',scenario(),c['pairs']),s.choose('FIFO_CPU',scenario(),c['pairs']))

    def test_out_of_support_scenario_axes(self):
        for k,val in [('thermal',1),('thermal',False),('resident',False),('warmup',5),
                      ('arrivals',[0]*11+[1]),('tasks',['detection']*12),('priorities',['urgent']*12),('reload',True)]:
            a=scenario();a[k]=val
            with self.subTest(k=k),self.assertRaises(s.OutOfSupport):s.support(a,'CPU_FIFO')
        for action in ('NPU','staggered','CPU_GPU_SERIAL','unload'):
            with self.assertRaises(s.OutOfSupport):s.support(scenario(),action)

    def test_solo_action_only_homogeneous_normal(self):
        a=scenario();a.update(tasks=['detection']*6,priorities=['normal']*6,arrivals=[0]*6)
        for b in ('CPU','GPU'):
            result=s.run_action(episode(b,solo=('detection',b)),a,b+'_SOLO')
            self.assertTrue(s.validate_result(result,a))
        a['priorities'][0]='urgent'
        with self.assertRaises(s.OutOfSupport):s.support(a,'GPU_SOLO')

    def test_cpu_fifo_replay_exact_and_urgent_no_preemption(self):
        e=episode('x');a=scenario()
        fifo=s.run_action(e,a,'CPU_FIFO')
        for old,new in zip(e['rows'],fifo['rows']):
            for k in ('dispatch','ready','persist','release'):self.assertEqual(old[k],new[k])
        self.assertEqual(e['end'],fifo['end'])
        urgent=s.run_action(e,a,'CPU_URGENT')
        self.assertEqual([r['priority'] for r in urgent['rows']],['urgent']*6+['normal']*6)
        self.assertEqual(urgent['end'],fifo['end'])
        self.assertEqual(s.metrics(urgent,a)['p95'],s.quantile([9,20,31,42,53,64],.95))
        self.assertTrue(s.validate_result(urgent,a))

    def test_corun_whole_timeline_and_no_early_lane_release(self):
        e=episode('b',True);r=s.run_action(e,scenario(),'PAIRED_CORUN')
        for old,new in zip(e['rows'],r['rows']):
            self.assertEqual([old[k] for k in ('dispatch','ready','release')],[new[k] for k in ('dispatch','ready','release')])
        self.assertEqual(r['end'],e['end'])
        with self.assertRaises(s.OutOfSupport):s.run_action(e,scenario(),'CPU_FIFO')

    def test_rejection_all_arrival_denominators(self):
        e=episode('x');e['memory'][0]['low_memory']=True
        r=s.run_action(e,scenario(),'CPU_FIFO');m=s.metrics(r,scenario())
        self.assertIsNone(m['p95']);self.assertEqual(m['miss'],1);self.assertEqual(m['normal'],0)
        self.assertEqual(m['completion'],0);self.assertEqual(m['memory_rejection'],12)
        self.assertEqual(m['terminals']['rejected'],12)

    def test_late_is_success_and_soft_no_expiry(self):
        a=scenario();a['urgent_ns']=1;a['normal_ns']=1
        m=s.metrics(s.run_action(episode('x'),a,'CPU_FIFO'),a)
        self.assertEqual(m['completion'],1);self.assertEqual(m['miss'],1);self.assertEqual(m['terminals']['expired'],0)

    def test_memory_strict_boundary_and_missing_snapshot(self):
        e=episode('x');e['memory'][0]['avail_bytes']=200
        self.assertFalse(s.admitted(e))
        e['memory']=[]
        with self.assertRaises(s.OutOfSupport):s.admitted(e)

    def test_catalog_replay_field_mixing_and_lane_overlap(self):
        c=fixture();c['pairs'][1]['A']['fingerprint']=c['pairs'][0]['A']['fingerprint']
        with self.assertRaises(s.OutOfSupport):s.validate_catalog(c)
        c=fixture();c['pairs'][0]['B']['rows'][1]['backend']='CPU'
        with self.assertRaises(s.OutOfSupport):s.validate_catalog(c)
        c=fixture();c['pairs'][0]['A']['rows'][1]['dispatch']=0
        with self.assertRaises(s.OutOfSupport):s.validate_catalog(c)

    def test_result_duplicate_terminal_and_fabricated_output(self):
        a=scenario();r=s.run_action(episode('x'),a,'CPU_FIFO')
        r['rows'][1]['ordinal']=0
        with self.assertRaises(s.OutOfSupport):s.validate_result(r,a)
        r=s.run_action(episode('x'),a,'CPU_FIFO');r['rows'][0]['terminal']='rejected'
        with self.assertRaises(s.OutOfSupport):s.validate_result(r,a)

    def test_epsilon_endpoints_tie_and_pareto(self):
        ref=dict(p95=100,miss=.5,makespan=100,throughput=10,normal=1,completion=1)
        other=dict(p95=50,miss=.25,makespan=120,throughput=8,normal=.8,completion=1)
        pred={'CPU_URGENT':ref,'PAIRED_CORUN':other}
        self.assertEqual(s.epsilon_choice(pred,0),'CPU_URGENT')
        self.assertEqual(s.epsilon_choice(pred,.5),'CPU_URGENT')
        self.assertEqual(s.epsilon_choice(pred,1),'PAIRED_CORUN')
        self.assertEqual(s.frontier(pred),sorted(pred))
        self.assertEqual(s.epsilon_choice({'CPU_URGENT':ref,'PAIRED_CORUN':ref},1),'CPU_URGENT')

    def test_adaptive_never_takes_realized_ticket(self):
        c=fixture();a=scenario();before=copy.deepcopy(c)
        self.assertIn(s.choose('ADAPTIVE_HALF',a,c['pairs']),('CPU_URGENT','PAIRED_CORUN'))
        self.assertEqual(c,before)
        with self.assertRaises(s.OutOfSupport):s.choose('random_policy',a,c['pairs'])

    def test_exact_bootstrap_has_no_rng(self):
        with patch('random.Random',side_effect=AssertionError('RNG')):
            self.assertEqual(s.exact_ci([3]*5),[3,3])
            for actual,expected in zip(s.exact_ci([0,2]),[.075,1.925]):
                self.assertAlmostEqual(actual,expected)

    def test_end_to_end_only_synthetic_fixture(self):
        c=fixture();before=copy.deepcopy(c)
        result=s.evaluate(c,[scenario()])
        self.assertEqual(len(result['results']),9)
        core=result['results'][0]
        self.assertEqual(len(core['records']),35)
        self.assertTrue(all(r['metrics']['completion']==1 for r in core['records']))
        self.assertEqual(c,before)
        for fold in result['results'][4:]:self.assertEqual(len(fold['records']),28)

    def test_plan_seed_config_and_noop_separation(self):
        self.assertEqual(s.key('s','pair','block'),s.key('s','pair','block'))
        c=fixture()
        with patch.object(s,'run_action',side_effect=AssertionError('engine')),patch.object(s,'evaluate',side_effect=AssertionError('simulation')):
            p=s.plan(c,scenarios())
        self.assertEqual(p['replications'],5);self.assertEqual(p['bootstrap_draws'],3125)

    def test_preparation_byte_identity_noop_and_mutation_rejection(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(s.base,'audit',return_value=({'fixture':True},{'consumed':['x']})),patch.object(s,'catalog',return_value=fixture()),patch.object(s,'scenarios',return_value=scenarios()),patch.object(s,'run_action',side_effect=AssertionError('engine')),patch.object(s,'evaluate',side_effect=AssertionError('engine')),patch('random.Random',side_effect=AssertionError('RNG')):
            root=Path(tmp);src=root/'source';src.mkdir();a=root/'a';b=root/'b'
            ra=s.generate(src,a);rb=s.generate(src,b)
            self.assertEqual(ra,rb)
            before={p.name:p.read_bytes() for p in a.iterdir()}
            self.assertEqual(before,{p.name:p.read_bytes() for p in b.iterdir()})
            self.assertEqual(s.verify(a,ra['freeze_sha256'])['simulated_completions'],0)
            self.assertEqual(before,{p.name:p.read_bytes() for p in a.iterdir()})
            with self.assertRaises(s.OutOfSupport):s.generate(src,a)
            with self.assertRaises(s.OutOfSupport):s.generate(src,src/'inside')
            with self.assertRaises(s.OutOfSupport):s.verify(a,'0'*64)
            mutations=[('plan.json',lambda x:x['configuration'].update(seed=1)),
                       ('plan.json',lambda x:x.update(protocol='bad')),
                       ('registry.json',lambda x:x.update(consumed=['replayed'])),
                       ('catalog.json',lambda x:x['pairs'][0]['A'].update(session_id='replayed'))]
            for name,mutate in mutations:
                value=s.base.read(a/name);mutate(value);(a/name).write_bytes(s.base.canonical(value))
                freeze=s.base.read(a/'freeze.json');freeze['files'][name]=s.base.digest(a/name)
                (a/'freeze.json').write_bytes(s.base.canonical(freeze))
                with self.assertRaises((ValueError,s.jsonschema.ValidationError)):s.verify(a,s.base.digest(a/'freeze.json'))
                for n,data in before.items():(a/n).write_bytes(data)
            for field,value in [('files',{'../outside.json':'0'*64}),('code',{})]:
                freeze=s.base.read(a/'freeze.json');freeze[field]=value
                (a/'freeze.json').write_bytes(s.base.canonical(freeze))
                with self.assertRaises(s.OutOfSupport):s.verify(a,s.base.digest(a/'freeze.json'))
                (a/'freeze.json').write_bytes(before['freeze.json'])

    def test_extraction_relative_epoch_and_joint_offsets(self):
        rows=[]
        def ev(name,time,rid=None):return dict(event=name,mono_ns=time,request_id=rid,data={})
        events=[ev('workload_start',1000),ev('workload_end',1100),ev('worker_dispatch',1005,'r'),ev('output_ready',1070,'r'),ev('persist_complete',1080,'r'),ev('worker_release_end',1090,'r')]
        block=dict(session_id='x',manifest=dict(requests=[dict(request_id='r',model_key='m',priority='normal')],models={'m':dict(model={'task_id':'detection'},execution={'backend':'CPU'})}),events=events,receipt=dict(sampled_peak_pss_bytes=1,samples=[],trace_fingerprint='x'))
        e=s.extract(block)
        self.assertEqual((e['end'],e['tail'],e['rows'][0]['dispatch']),(100,10,5))


if __name__=='__main__':unittest.main()
