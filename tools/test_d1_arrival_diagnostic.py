"""Focused checks for the separate PC diagnosis and offline view."""
import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_diagnostic as diagnostic


def rows(name):
    with (diagnostic.OUTPUT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


class DiagnosticTest(unittest.TestCase):
    def test_frozen_grid_and_denominators(self):
        c=json.loads(diagnostic.CONFIG.read_text(encoding='utf-8'))
        self.assertEqual(c['realized_interference'],[1.,1.5,2.])
        self.assertEqual(c['p_predicted_interference'],[1.,1.5,2.])
        metrics=rows('interference_metrics.csv')
        self.assertEqual(len(metrics),3*5*3*(4+3))
        self.assertEqual({r['planned'] for r in metrics},{'24'})
        self.assertEqual({r['unfinished'] for r in metrics},{'0'})
        self.assertEqual(len(rows('interference_paired.csv')),3*5*3*3)

    def test_linear_energy_and_algebraic_crossing(self):
        d={'idle':-1.,'single':-.5,'pair':1.5}
        x,status=diagnostic.threshold(d,1.,2.)
        self.assertAlmostEqual(x,4/3)
        self.assertEqual(status,'finite_algebraic_boundary_not_physical_range')
        self.assertAlmostEqual(diagnostic.energy(d,1.,2.,x),0)
        self.assertEqual(diagnostic.threshold({'idle':0,'single':0,'pair':0},1,2)[1],
                         'identical_all_pair_powers')
        group=[r for r in rows('energy_boundaries.csv') if r['scenario']=='queue' and
               r['seed']=='201' and r['realized']=='1.5' and
               r['comparator']=='B3_SOLO_EFT_PC' and r['idle_w_assumed']=='1.0' and
               r['single_w_assumed']=='2.0']
        self.assertEqual(len(group),2)
        for row in group:
            delta={'idle':float(row['delta_idle_s']),'single':float(row['delta_single_s']),
                   'pair':float(row['delta_pair_s'])}
            self.assertAlmostEqual(float(row['p_minus_comparator_j']),
                diagnostic.energy(delta,1.,2.,float(row['pair_w_assumed'])))
            self.assertAlmostEqual(float(row['p_minus_comparator_relative_pct']),
                100*float(row['p_minus_comparator_j'])/float(row['comparator_energy_j_assumed']))

    def test_matched_prediction_is_not_default_and_no_feedback(self):
        paired=rows('interference_paired.csv')
        def mean(s,r,p,key):
            values=[float(x[key]) for x in paired if x['scenario']==s and
                    float(x['realized'])==r and float(x['predicted'])==p]
            self.assertEqual(len(values),5)
            return sum(values)/len(values)
        self.assertAlmostEqual(mean('queue',1.,1.,'p_minus_b3_urgent_p95_ms'),0)
        self.assertGreater(mean('queue',1.,1.5,'p_minus_b3_urgent_p95_ms'),0)
        self.assertGreater(mean('queue',2.,2.,'p_minus_b3_urgent_p95_ms'),0)
        ap=rows('ap_sensitivity.csv')
        self.assertEqual(len(ap),3*5*3*2*2)
        self.assertEqual({r['evidence'] for r in ap},
                         {'post-hoc state-thermal stress, no feedback'})
        paths=rows('ap_path_representative.csv')
        self.assertEqual(len(paths),3*2*25)
        self.assertEqual({r['time_s'] for r in paths if r['scenario']=='low'},
                         {str(x) for x in range(0,121,5)})

    def test_frozen_default_matches_prior_seed201_accounting(self):
        old=diagnostic.ROOT/'docs/results/arrival_visualization_01/arrival_energy_stress.csv'
        with old.open(encoding='utf-8-sig',newline='') as f:
            prior=list(csv.DictReader(f))
        new=rows('energy_boundaries.csv')
        for policy in ('P_PAIR_COST_PC','B3_SOLO_EFT_PC'):
            reference=next(r for r in prior if r['mode']=='explore' and r['scenario']=='queue'
                           and r['profile']=='P2_T30' and r['policy']==policy)
            result=next(r for r in new if r['scenario']=='queue' and r['seed']=='201'
                        and r['realized']=='1.5' and r['comparator']=='B3_SOLO_EFT_PC'
                        and r['idle_w_assumed']=='1.0' and r['single_w_assumed']=='2.0'
                        and r['pair_w_assumed']=='2.0')
            key='p_energy_j_assumed' if policy=='P_PAIR_COST_PC' else 'comparator_energy_j_assumed'
            self.assertAlmostEqual(float(reference['energy_j_assumed']),float(result[key]))
        old_ap={r['policy']:float(r['ap_peak_c_assumed']) for r in prior if r['mode']=='explore'
                and r['scenario']=='queue' and r['profile']=='P2_T30'}
        new_ap=next(r for r in rows('ap_sensitivity.csv') if r['scenario']=='queue' and
                    r['seed']=='201' and r['realized']=='1.5' and
                    r['initial_ap_c_assumed']=='29.0' and r['pair_ap_equilibrium_c_assumed']=='30.0')
        self.assertAlmostEqual(old_ap['P_PAIR_COST_PC'],float(new_ap['p_ap_peak_c_assumed']))
        self.assertAlmostEqual(old_ap['B3_SOLO_EFT_PC'],float(new_ap['b3_ap_peak_c_assumed']))

    def test_browser_diagnostic_tab(self):
        chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
        if not chrome.is_file():self.skipTest('Chrome absent')
        page=(diagnostic.OUTPUT/'diagnostic.html').read_text(encoding='utf-8')
        check="""<script>
        document.body.setAttribute('data-qa-default',document.querySelectorAll('#policyTable tbody tr').length===7);
        scenario.value='burst';realized.value='2';scenario.dispatchEvent(new Event('change'));
        document.body.setAttribute('data-qa-filter',heatmap.getAttribute('src')==='interference_heatmap_burst.png'
          && summary.textContent.includes('burst / 실현 2')
          && document.querySelectorAll('#apTable tbody tr').length===4);
        </script>"""
        with tempfile.TemporaryDirectory(prefix='d1_arrival_diag_') as directory:
            folder=Path(directory)
            f=folder/'diagnostic.html';f.write_text(page.replace('</body>',check+'</body>'),encoding='utf-8')
            cmd=[str(chrome),'--headless=new','--disable-gpu','--no-first-run',
                 '--disable-background-networking','--no-default-browser-check',
                 f'--user-data-dir={folder/"profile"}','--dump-dom',f.as_uri()]
            proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=True)
            rendered=proc.stdout.decode('utf-8',errors='replace')
            self.assertIn('data-qa-default="true"',rendered)
            self.assertIn('data-qa-filter="true"',rendered)


if __name__=='__main__':unittest.main()
