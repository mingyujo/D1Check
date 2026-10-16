"""Prepared inputs/budget/service verdicts only; no native simulator calls."""
import unittest
from unittest.mock import patch
from tools import d1_rolling_execution_pilot as x
def row(i,policy,family='low',**changes):
    r=dict(condition=i,policy=policy,family=family,planned=2,completed=2,incomplete=0,urgent_failure=0,normal_failure=0,urgent_p95_ms=100.,energy_j=2.,peak_ap_c=31.,normal_mean_ms=500.)
    r.update(changes);return r
def rows(**change):
    return [r for i in range(24) for r in [row(i,'Band'),row(i,'Triton'),row(i,'ExecutionPrefix',**change)]]
class Contract(unittest.TestCase):
    def test_same_completion_and_one_axis_gain_can_be_promising(self):
        self.assertTrue(x.gate_rows(rows(peak_ap_c=30.9))['promising'])
        self.assertTrue(x.gate_rows(rows(energy_j=1.9))['promising'])
    def test_any_condition_service_loss_blocks(self):
        r=rows(peak_ap_c=30.9);r[-1]['urgent_failure']=1
        self.assertFalse(x.gate_rows(r)['promising'])
    def test_reduced_completion_or_missing_cost_is_not_better(self):
        self.assertFalse(x.gate_rows(rows(completed=1,incomplete=1,energy_j=1.))['maintenance_pass'])
        self.assertFalse(x.gate_rows(rows(energy_j=None))['maintenance_pass'])
    def test_primary_absolute_deadlines_required(self):
        r=rows(peak_ap_c=30.9)
        for q in r:q['normal_failure']=1
        self.assertFalse(x.gate_rows(r)['promising'])
    def test_four_roles_and_gate_then_fixed24_batch(self):
        self.assertEqual(len(x.ROLES),4);self.assertEqual(4+24*len(x.ROLES),100)
        self.assertEqual(len(x.fixtures()),4);self.assertTrue(all(len(q['tickets'])==2 for q in x.fixtures()))
    def test_preparation_does_not_activate_execution_clock(self):
        # Verify source boundaries: preparation has no native/activation calls.
        import ast,inspect,textwrap
        tree=ast.parse(textwrap.dedent(inspect.getsource(x.prepare)))
        names=[node.func.attr if isinstance(node.func,ast.Attribute) else getattr(node.func,'id','') for node in ast.walk(tree) if isinstance(node,ast.Call)]
        self.assertNotIn('simulate',names);self.assertNotIn('Budget',names);self.assertNotIn('run',names)
    def test_duplicate_or_missing_conditions_cannot_fake_full_coverage(self):
        r=rows(peak_ap_c=30.9);r[-1]=dict(r[2])
        with self.assertRaises(ValueError):x.gate_rows(r)
        with self.assertRaises(ValueError):x.gate_rows(rows()[:-1])
    def test_shared_check_never_creates_local_execution_lineage(self):
        import tempfile,hashlib,json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            public=Path(directory)/'shared';public.mkdir();local=Path(directory)/'local'
            cases=[dict(condition=i) for i in range(24)]
            reg=dict(source_sha256={},inputs_sha256=hashlib.sha256(json.dumps(cases,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            x.write(public/'execution_contract.json',reg);x.write(public/'cases.json',dict(cases=cases))
            with patch.object(x,'PUBLIC',public),patch.object(x,'LOCAL',local),patch.object(x.new.p,'inputs',return_value=None):
                self.assertEqual(x.check()['scope'],'shared_read_only')
                with self.assertRaises(ValueError):x.check(require_local=True)
            self.assertFalse(local.exists())
if __name__=='__main__':unittest.main()
