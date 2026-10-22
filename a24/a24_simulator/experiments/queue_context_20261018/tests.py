import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'deep_repair_20261018'))
from common import B,ROOT,read
from public_controller import PublicController
from queue_controller import QueueContextController

class Tests(unittest.TestCase):
    def make(self,n):
        physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'))
        rows=[dict(request_id='q%04d'%i,task='C' if i%2==0 else 'D',priority='U' if i%3==0 else 'N',scheduled_arrival_ns=35_000_000_000-i*1_000_000,deadline_ns=38_000_000_000+i*1_000_000,ordinal=i) for i in range(n)]
        state=dict(now_ns=35_000_000_000,queue=rows,owners=[],sensor=dict(temperature_c=26.,shared_z=0.,peak_c=26.))
        vectors={(q['request_id'],r):[.01,.05,.005,.005,.005] for q in rows for r in ('CPU','GPU')}
        actor=QueueContextController(None,physics,dict(n=n,service_stop_s=1000),'RL',deadline_guard=False)
        return actor,state,vectors

    def test_chosen_and_bounded_public_union(self):
        a,s,v=self.make(562);chosen=s['queue'][-8:];x=a.context(s,chosen,v)
        self.assertLessEqual(len(x),24);self.assertTrue({q['request_id'] for q in chosen}<={q['request_id'] for q in x});self.assertTrue(all(q in s['queue'] for q in x));self.assertEqual(len({q['request_id'] for q in x}),len(x))
        a,s,v=self.make(20);self.assertEqual(len(a.context(s,s['queue'][-8:],v)),20)

    def test_short_queue_full_context_and_same_forecast(self):
        a,s,v=self.make(3);chosen=s['queue'];first=dict(kind='DISPATCH',request_id=chosen[0]['request_id'],route='CPU')
        b=PublicController(None,a.physics,a.case,'RL',deadline_guard=False)
        self.assertEqual(a.preview(s,chosen,[],v,first),b.preview(s,chosen,[],v,first))

    def test_hidden_future_metadata_cannot_change_context(self):
        a,s,v=self.make(40);other=copy.deepcopy(s);other['future_arrivals']=[dict(request_id='secret',actual_s=.0001)];other['future_true_work']=999
        self.assertEqual(a.context(s,s['queue'][:8],v),a.context(other,other['queue'][:8],v))

    def test_added_context_completes_every_visible_job(self):
        a,s,v=self.make(8);chosen=s['queue'][-1:];first=dict(kind='WAIT',wait_ns=50_000_000)
        r=a.preview(s,chosen,[],v,first)
        self.assertGreater(r['visible_jobs'],len(chosen));self.assertEqual(r['visible_jobs'],len(a.context(s,chosen,v)));self.assertEqual(r['nominal_unfinished'],0)
        self.assertFalse(r['future_arrivals_used']);self.assertTrue(r['nominal_only'])

    def test_same_context_for_all_first_actions(self):
        a,s,v=self.make(30);chosen=s['queue'][-8:];expected=None
        for first in [dict(kind='DISPATCH',request_id=chosen[0]['request_id'],route='CPU'),dict(kind='DISPATCH',request_id=chosen[-1]['request_id'],route='GPU'),dict(kind='WAIT',wait_ns=200_000_000)]:
            r=a.preview(s,chosen,[],v,first);ids=[q['request_id'] for q in a._last_context]
            if expected is None:expected=ids
            self.assertEqual(ids,expected);self.assertEqual(r['visible_jobs'],len(expected))

if __name__=='__main__':unittest.main()
