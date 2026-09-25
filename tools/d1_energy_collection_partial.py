"""Read a stopped collection journal; never turn partial work into a comparison."""
import argparse
import collections
import json
from pathlib import Path
from tools import d1_energy_collection as c


def analyze(run):
    receipt = c.p.read(run / 'FINAL_RECEIPT.json')
    c.require(receipt['status'] == 'stopped_no_resume', 'stopped run only')
    session = next(run.glob('00_*'))
    raw = session / 'artifacts/progress.jsonl'
    events, incomplete = c.progress_prefix(raw.read_bytes())
    c.require(not incomplete and [e['sequence'] for e in events] == list(range(len(events))), 'journal continuity')
    samples = [e for e in events if e['kind'] == 'power_sample']
    windows = {}
    for phase in ('resident_baseline', 'load'):
        start = next(e['mono_ns'] for e in events if e['kind'] == 'phase_start' and e['phase'] == phase)
        ends = [e['mono_ns'] for e in events if e['kind'] == 'phase_end' and e['phase'] == phase]
        end = ends[0] if ends else max(e['mono_ns'] for e in samples if e['phase'] == phase)
        windows[phase] = c.integrate(samples, start, end, 1000)
        windows[phase]['phase_completed'] = bool(ends)
        windows[phase]['end_rule'] = 'phase_end' if ends else 'last_saved_power_sample; not work completion'
    baseline_w = windows['resident_baseline']['mean_power_w']
    windows['load']['increment_above_resident_idle_j'] = windows['load']['covered_energy_j'] - baseline_w * windows['load']['covered_s']
    screens = [c.p.read(f) for f in session.glob('screen_observations/*.json')]
    commands = [c.p.read(f) for f in sorted(run.glob('host_commands/*/client/result.json'))]
    thermal = [json.loads(line) for line in (session / 'thermal.jsonl').read_text().splitlines()]
    counts = collections.Counter((e['phase'], e['kind']) for e in events)
    calls = collections.Counter((e.get('stage'), e.get('edge')) for e in events if e['kind'] == 'call_stage')
    return dict(status='partial_not_comparable', source_run=str(run), journal_sha256=c.p.digest(raw),
        receipt_sha256=c.p.digest(run / 'FINAL_RECEIPT.json'), records=len(events),
        runtime_started=sum(e['kind']=='runtime_start' for e in events), runtime_returned=sum(e['kind']=='runtime_return' for e in events),
        warmup_returned=sum(e['kind']=='warmup_return' for e in events),
        diagnostic_started=sum(e['kind']=='request_start' for e in events), diagnostic_lane_available=sum(e['kind']=='lane_available' for e in events),
        load_started=counts['load','request_start'],load_lane_available=counts['load','lane_available'],
        load_completed_by_backend=dict(collections.Counter(e['key'] for e in events if e['phase']=='load' and e['kind']=='lane_available')),
        host_inference_start=calls['host_inference','start'],host_inference_succeeded=calls['host_inference','succeeded'],
        original_conservative_bounds=receipt['last_session_progress'],
        app_cleanup=c.p.read(session/'artifacts/cleanup.json'),host_cleanup=c.p.read(session/'host_cleanup.json')['status'],
        failure_host_cleanup=c.p.read(session/'failure_host_cleanup.json')['status'],
        screen_queries=len(screens),screen_pass=sum(s['status']=='sample_pass' for s in screens),
        screen_max_seconds=max(s['query_end']-s['query_start'] for s in screens),
        battery_percent_range=[min(e['battery_level'] for e in samples),max(e['battery_level'] for e in samples)],
        battery_deci_c_range=[min(e['battery_temperature_deci_c'] for e in samples),max(e['battery_temperature_deci_c'] for e in samples)],
        ap_c_range=[min(float(e['AP']) for e in thermal if e['AP']!=''),max(float(e['AP']) for e in thermal if e['AP']!='')],
        recorded_environment_ok=all(e['plugged']==0 and e['thermal_status']==0 and e['interactive'] and e['admission_reason']=='admit' for e in samples),
        conditional_whole_device_energy=windows,current_ua_per_raw=1000,absolute_accuracy_certified=False,
        receipt_elapsed_excludes_final_failure_cleanup_seconds=receipt['elapsed_seconds'],
        observed_first_client_to_last_cleanup_client_seconds=max(x['monotonic_end'] for x in commands)-min(x['monotonic_start'] for x in commands),
        work_completion_energy=None,common_480s_energy=None,cooling_energy=None,serial_parallel_comparison=None,
        freeze_created=(run/'development_freeze.json').exists(),experiment_ready=False)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--run',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    result=analyze(args.run)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    c.cal.write_new(args.output,result)
    print(json.dumps(result,ensure_ascii=False))
