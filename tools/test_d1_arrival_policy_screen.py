import copy
import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_policy_screen as screen


class PolicyScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = screen.read_csv(screen.SOURCE / 'interference_metrics.csv')

    def test_aligned_existing_results_and_frontier(self):
        rows = screen.screen(self.source)
        self.assertEqual(len(rows), 45)
        queue = {r['policy']: r for r in rows if r['scenario'] == 'queue' and r['realized'] == 1.5}
        self.assertEqual({p for p, r in queue.items() if r['mean_frontier']},
                         {'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC'})
        self.assertEqual(queue['P_PAIR_COST_PC']['normal_planned'], 90)
        self.assertEqual(queue['P_PAIR_COST_PC']['predicted'], 1.5)
        self.assertEqual(sum(r['unfinished'] for r in rows), 0)

    def test_missing_denominator_or_duplicate_is_rejected(self):
        damaged = copy.deepcopy(self.source)
        damaged[0]['normal_planned'] = '17'
        with self.assertRaisesRegex(ValueError, 'denominator'):
            screen.screen(damaged)
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            screen.screen(self.source + [self.source[0]])

    def test_dominance_keeps_ties_and_rejects_tradeoff(self):
        a = dict(zip(screen.METRICS, (100., 0., 1000., 0., 0)))
        b = dict(a)
        c = dict(zip(screen.METRICS, (120., 0., 1100., 0., 0)))
        d = dict(zip(screen.METRICS, (90., 0., 1500., 0., 0)))
        self.assertFalse(screen.dominates(a, b))
        self.assertTrue(screen.dominates(a, c))
        self.assertFalse(screen.dominates(a, d))

    def test_joint_state_accounting_matches_preserved_stress(self):
        bundle=screen.OUTPUT/'repro_bundle'
        schedule=screen.read_csv(bundle/'occupancy_segments.csv')
        assumptions=json.loads((bundle/'assumptions.json').read_text(encoding='utf-8'))
        groups={}
        for row in schedule:
            key=(row['scenario'],int(row['seed']),float(row['realized']),row['policy'])
            groups.setdefault(key,[]).append(row)
        self.assertEqual(len(groups),135)
        stored=screen.read_csv(screen.ROOT/'docs/results/arrival_cost_boundaries_01/state_durations.csv')
        for reference in stored:
            key=(reference['scenario'],int(reference['seed']),float(reference['realized']),reference['policy'])
            rows=groups[key]
            duration=lambda predicate:sum(float(x['end_s'])-float(x['start_s']) for x in rows if predicate(x['state']))
            self.assertAlmostEqual(duration(lambda x:x=='idle'),float(reference['idle_s']),places=6)
            self.assertAlmostEqual(duration(lambda x:x!='idle' and '+' not in x),float(reference['single_s']),places=6)
            self.assertAlmostEqual(duration(lambda x:'+' in x),float(reference['pair_s']),places=6)
            power={s:1. if s=='idle' else 2. for s in assumptions['states']}
            energy,_=screen.assumed_account(rows,power,assumptions['ap_equilibrium_c'])
            self.assertAlmostEqual(energy,120+float(reference['single_s'])+float(reference['pair_s']),places=6)
        # Independently preserved seed-201 AP stress result, not a new prediction validation.
        old=screen.read_csv(screen.ROOT/'docs/results/arrival_visualization_01/arrival_energy_stress.csv')
        for r in old:
            if r['mode']=='explore' and int(r['seed'])==201 and r['profile']=='P2_T30' and r['policy'] in screen.COST_POLICIES:
                key=(r['scenario'],201,1.5,r['policy'])
                energy,peak=screen.assumed_account(groups[key],assumptions['power_w'],assumptions['ap_equilibrium_c'])
                self.assertAlmostEqual(energy,float(r['energy_j_assumed']),places=6)
                self.assertAlmostEqual(peak,float(r['ap_peak_c_assumed']),places=6)

    def test_independent_pair_power_and_bundle_reproduction(self):
        bundle=screen.OUTPUT/'repro_bundle'
        assumptions=json.loads((bundle/'assumptions.json').read_text(encoding='utf-8'))
        rows=screen.read_csv(bundle/'occupancy_segments.csv')
        selected=lambda p:[r for r in rows if r['scenario']=='queue' and float(r['realized'])==1.5
                         and int(r['seed'])==201 and r['policy']==p]
        b2,b3=selected('B2_PC'),selected('B3_SOLO_EFT_PC')
        def energy(s, power):return screen.assumed_account(s,power,assumptions['ap_equilibrium_c'])[0]
        base=assumptions['power_w']; changed=dict(base)
        x='classification:GPU+detection:CPU'; y='detection:CPU+detection:GPU'
        changed[x]+=1
        delta_x=(energy(b2,changed)-energy(b3,changed))-(energy(b2,base)-energy(b3,base))
        duration=lambda rows,state:sum(float(r['end_s'])-float(r['start_s']) for r in rows if r['state']==state)
        self.assertAlmostEqual(delta_x,duration(b2,x)-duration(b3,x),places=8)
        changed=dict(base);changed[y]+=1
        delta_y=(energy(b2,changed)-energy(b3,changed))-(energy(b2,base)-energy(b3,base))
        self.assertAlmostEqual(delta_y,duration(b2,y)-duration(b3,y),places=8)
        self.assertNotAlmostEqual(delta_x,delta_y)
        with tempfile.TemporaryDirectory() as directory:
            copied=Path(directory)/'bundle'
            import shutil
            shutil.copytree(bundle,copied)
            subprocess.run([sys.executable,'reproduce.py','--bundle','.','--output','.'],cwd=copied,
                           check=True,capture_output=True,text=True)
            self.assertEqual((copied/'dashboard.html').read_bytes(),(screen.OUTPUT/'dashboard.html').read_bytes())
            (copied/'assumptions.json').write_text('{}',encoding='utf-8')
            bad=subprocess.run([sys.executable,'reproduce.py','--bundle','.','--output','.'],cwd=copied,
                               capture_output=True,text=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn('bundle hash mismatch',bad.stderr)

    def test_offline_browser_renders_controls_and_accounting(self):
        chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        if not chrome.exists():
            self.skipTest('Chrome not installed')
        page=(screen.OUTPUT/'dashboard.html').resolve().as_uri()
        run=subprocess.run([str(chrome),'--headless=new','--disable-gpu','--no-sandbox',
                            '--disable-extensions','--virtual-time-budget=2000','--dump-dom',page],
                           capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
        self.assertEqual(run.returncode,0,run.stderr[-1000:])
        body=run.stdout
        self.assertIn('id="comparison" class="scroll"><table>',body)
        self.assertIn('id="boundary">ΔE(B2−B3)',body)
        self.assertIn('id="states" class="states"><div',body)
        self.assertIn('id="scope" class="small">queue / 실현 간섭 1.5 / 5 seed',body)
        with tempfile.TemporaryDirectory() as directory:
            changed=Path(directory)/'filter.html'
            html=(screen.OUTPUT/'dashboard.html').read_text(encoding='utf-8')
            code="<script>document.getElementById('scenario').value='burst';document.getElementById('seed').value='203';document.getElementById('delta').value='0';document.getElementById('scenario').dispatchEvent(new Event('input'));document.getElementById('p_0').value='3';document.getElementById('p_0').dispatchEvent(new Event('input'));</script>"
            changed.write_text(html.replace('</body>',code+'</body>'),encoding='utf-8')
            update=subprocess.run([str(chrome),'--headless=new','--disable-gpu','--no-sandbox',
                                   '--disable-extensions','--virtual-time-budget=2000','--dump-dom',changed.resolve().as_uri()],
                                  capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
            self.assertEqual(update.returncode,0,update.stderr[-1000:])
            self.assertIn('id="scope" class="small">burst / 실현 간섭 1.5 / 1 seed',update.stdout)
            self.assertIn('id="comparison" class="scroll"><table>',update.stdout)


if __name__ == '__main__':
    unittest.main()
