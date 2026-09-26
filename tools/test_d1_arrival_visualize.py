"""Focused verification of the shared visualization against frozen source results."""
import csv
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.d1_arrival_visualize import DEFAULT_OUTPUT, ROOT, read_csv


class VisualizationTest(unittest.TestCase):
    def test_published_numbers_and_denominators(self):
        source = read_csv(ROOT / 'docs/results/arrival_explore_20260925/summary.csv')
        actual = read_csv(DEFAULT_OUTPUT / 'service.csv')
        lookup = {(r['mode'], r['scenario'], r['policy']): r for r in source}
        self.assertEqual(len(actual), 48)
        for row in actual:
            key = row['mode'], row['scenario'], row['policy']
            reference = lookup[key]
            self.assertAlmostEqual(float(row['urgent_p95_ms_mean']), float(reference['urgent_p95_ms']))
            self.assertAlmostEqual(float(row['normal_mean_ms_mean']), float(reference['normal_mean_ms']))
            self.assertEqual(int(row['planned']), 120)
            self.assertEqual(int(row['urgent_planned']), 30)
            self.assertEqual(int(row['normal_planned']), 90)
        trace = read_csv(DEFAULT_OUTPUT / 'timeline.csv')
        self.assertEqual(len(trace), 2*3*8*24)
        self.assertEqual({r['seed'] for r in trace}, {'201'})

    def test_fixed_results_are_separate_and_missing_energy_is_not_zero(self):
        rows = read_csv(DEFAULT_OUTPUT / 'fixed_870_comparison.csv')
        source = read_csv(ROOT / 'docs/results/energy_operational_sim_01/comparison.csv')
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['work_requests'] for r in rows}, {'870'})
        for result, reference in zip(rows, source):
            for key in ('work_completion_s', 'common_window_energy_j_conditional', 'load_ap_peak_c'):
                self.assertEqual(result[key], reference[key])
        curves = read_csv(DEFAULT_OUTPUT / 'fixed_870_model_curve.csv')
        evaluation = json.loads((ROOT / 'docs/results/energy_operational_sim_01/confirmation_evaluation.json').read_text(encoding='utf-8'))
        for mode in ('serial', 'parallel'):
            first = next(r for r in curves if r['mode'] == mode)
            self.assertAlmostEqual(float(first['load_start_ap_c']),
                evaluation['outcomes'][mode]['prediction']['phase_trace'][2]['ap_start_c'])
            self.assertAlmostEqual(float(first['cumulative_energy_j_conditional']), 0)
            endpoint = [r for r in curves if r['mode'] == mode and float(r['elapsed_s']) == 480]
            self.assertEqual(len(endpoint), 1)
            self.assertAlmostEqual(float(endpoint[0]['cumulative_energy_j_conditional']),
                evaluation['outcomes'][mode]['prediction']['common_window_energy_j_conditional'])
        html = (DEFAULT_OUTPUT / 'dashboard.html').read_text(encoding='utf-8')
        self.assertIn('UNSUPPORTED_MISSING_ARRIVAL_STATE_PROFILE',
                      (ROOT / 'tools/d1_arrival_energy_research.py').read_text(encoding='utf-8'))
        self.assertIn('계산 불가', html)
        self.assertNotIn('https://', html)
        self.assertNotIn('http://', html.replace('http://www.w3.org/2000/svg', ''))

    def test_browser_filters(self):
        chrome = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
        if not chrome.is_file():
            self.skipTest('Chrome absent; browser QA must be run separately')
        html = (DEFAULT_OUTPUT / 'dashboard.html').read_text(encoding='utf-8')
        check = """<script>
        function verify(s,m,p){
          scenario.value=s; mode.value=m; policy.value=p;
          scenario.dispatchEvent(new Event('change'));
          return document.getElementById('scope').textContent.includes(s+' / '+m)
            && document.getElementById('timeline-note').textContent.includes(s+' / '+m+' / '+p)
            && document.querySelectorAll('#timeline rect').length>20;
        }
        document.body.setAttribute('data-qa-low', verify('low','strict','B2_PC'));
        document.body.setAttribute('data-qa-burst', verify('burst','explore','P_PAIR_COST_PC'));
        </script>"""
        html = html.replace('</body>', check + '</body>')
        with tempfile.TemporaryDirectory(prefix='d1_viz_') as directory:
            folder = Path(directory)
            page = folder / 'check.html'
            page.write_text(html, encoding='utf-8')
            cmd = [str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                   '--disable-background-networking', '--no-default-browser-check',
                   f'--user-data-dir={folder / "profile"}', '--dump-dom', page.as_uri()]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=30, check=True)
            rendered = proc.stdout.decode('utf-8', errors='replace')
            self.assertRegex(rendered, r'data-qa-low="true"')
            self.assertRegex(rendered, r'data-qa-burst="true"')


if __name__ == '__main__':
    unittest.main()
