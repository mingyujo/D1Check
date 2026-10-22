"""Conservation checks of pressure inputs; no simulation or NN."""
import unittest
from study import H,old,read
class Inputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=read(H/'INPUTS.json')['cases'];cls.items=[]
        for c in cls.cases:
            b=read(H/'banks'/(c['id']+'.BANK.json.gz'));p=read(H/'banks'/(c['id']+'.PUBLIC.json'))['public']
            s=read(old.D/'banks'/f"D040_T60_P{c['condition']['pattern_index']}_S160.BANK.json.gz")
            cls.items.append((c,b,p,s))
    def test_exact_doubled_tripled_counts(self):
        self.assertEqual([c['n'] for c in self.cases],[1520,1920,2280,2880])
        self.assertEqual([c['condition']['rate_multiplier'] for c in self.cases],[.8,.8,1.2,1.2])
    def test_identity_and_single_binding(self):
        for c,b,p,s in self.items:
            self.assertEqual(len(b['jobs']),c['n']);self.assertEqual(len(p['requests']),c['n'])
            self.assertEqual(len({j['request_id'] for j in b['jobs']}),c['n'])
            self.assertEqual([j['request_id'] for j in b['jobs']],[j['request_id'] for j in p['requests']])
    def test_compressed_arrivals_only(self):
        for c,b,p,s in self.items:
            f=c['arrival_compression_factor'];n=c['source_base_n']
            for i,j in enumerate(b['jobs']):
                src=s['jobs'][i%n];off=src['scheduled_arrival_ns']-35_000_000_000
                expected=35_000_000_000+(off+f//2)//f+(i//n)*(60_000_000_000//f)
                self.assertEqual(j['scheduled_arrival_ns'],expected)
                self.assertEqual(round(c['input']['requests'][i]['arrival_s']*1e9),expected)
    def test_relative_deadline_preserved(self):
        for c,b,p,s in self.items:
            for i,j in enumerate(b['jobs']):
                src=s['jobs'][i%c['source_base_n']]
                self.assertEqual(j['deadline_ns']-j['scheduled_arrival_ns'],src['deadline_ns']-src['scheduled_arrival_ns'])
    def test_admission_jitter_not_compressed(self):
        for c,b,p,s in self.items:
            for i,j in enumerate(b['jobs']):
                src=s['jobs'][i%c['source_base_n']]
                self.assertEqual(j['admission'],src['admission'])
                self.assertEqual(j['queue_entry_ns']-j['scheduled_arrival_ns'],src['queue_entry_ns']-src['scheduled_arrival_ns'])
    def test_same_two_route_latents(self):
        for c,b,p,s in self.items:
            for i,j in enumerate(b['jobs']):self.assertEqual(j['routes'],s['jobs'][i%c['source_base_n']]['routes'])
    def test_same_public_nominals(self):
        for c,b,p,s in self.items:
            for i,j in enumerate(b['jobs']):
                src=s['jobs'][i%c['source_base_n']]
                for route in ('CPU','GPU'):self.assertEqual(b['nominal_vectors'][j['request_id']+'|'+route],s['nominal_vectors'][src['request_id']+'|'+route])
    def test_common_windows_and_public_attributes(self):
        for c,b,p,s in self.items:
            self.assertEqual(c['supply_stop_s'],635);self.assertEqual(p['service_stop_ns'],1235_000_000_000)
            self.assertLess(max(q['scheduled_arrival_ns'] for q in p['requests']),635_000_000_000)
            for i,q in enumerate(p['requests']):
                src=s['jobs'][i%c['source_base_n']]
                self.assertEqual((q['task'],q['priority']),(src['task'],src['priority']))
                self.assertEqual((q['deadline_ns'],q['scheduled_arrival_ns']),(b['jobs'][i]['deadline_ns'],b['jobs'][i]['scheduled_arrival_ns']))
if __name__=='__main__':unittest.main(verbosity=2)
