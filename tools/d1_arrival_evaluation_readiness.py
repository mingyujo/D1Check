"""Generate honest PC-only independent-device-evaluation readiness, never ADB."""
import argparse
import itertools
import json
from pathlib import Path
from tools.d1_arrival_plan import read,digest

def prepare(batch,bridge,output):
    batch,bridge,output=map(Path,(batch,bridge,output))
    if output.exists():raise ValueError('preserve previous preparation')
    frozen=read(batch/'freeze_before_evaluation.json');observed=read(bridge/'observed_bridge.json')
    result=dict(protocol='arrival-policy-evaluation-preparation-v1',status='BLOCKED_RESEARCH_AND_IMPLEMENTATION_GATES',
        experiment_ready=False,device_commands=[],measurement_budget=None,
        policies=['B2_FROZEN_AFTER_DEVICE_DEVELOPMENT','B3_SOLO_EFT','P_PAIR_COST'],
        balanced_order_templates=list(itertools.permutations(['B2','B3','P'])),
        paired_unit='independent block; same workload/input/resident/thread/environment across policies; requests are not independent sessions',
        primary_comparisons=['P minus B3','P minus B2'],
        candidate_primary='urgent session nearest-rank P95 plus normal service constraint, margins pending user objective',
        multiplicity='joint success requires both predeclared comparisons; report both CIs; interval method/precision and block count frozen before device evaluation',
        failure_rule='all planned arrivals; no retry/replacement/extra; no improvement-driven stopping; keep technical failures and unattempted denominator',
        remaining_gates={
            'normal_service_objective_and_margin':'unresolved user value decision; no retroactive 10 percent criterion change',
            'B2_device_candidate_selection':'PC exploratory GPU classification + CPU detection pair not measured concurrently; strict CPU_CPU is limited admissible candidate',
            'B3_P_Android_active_implementation':'PC logic differs from Android strict fallback; port and PC equivalence required before any policy evaluation',
            'parallel_prediction_acceptance':'no predeclared numerical accuracy margin; 1 independent followup session/condition is descriptive',
            'P_incremental_merit':'scenario-dependent harms; no basis to declare superiority or novelty',
            'sample_size_and_budget':'new policy paired session variance unavailable; no arbitrary device session count',
            'existing_system_comparison':'Band original-system comparison not implemented; PC candidate is not Band reproduction'},
        pc_freeze_hash=digest(batch/'freeze_before_evaluation.json'),observed_bridge_hash=digest(bridge/'observed_bridge.json'),
        pc_B2={m:x['candidate'] for m,x in frozen['B2'].items()},
        observed_conditions=list(observed['conditions']),
        next_recommended='resolve normal-service loss constraint and inspect static baseline before new P development or measurement; no automatic new diagnostic')
    output.mkdir(parents=True);(output/'readiness.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result['status']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('batch','bridge','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(prepare(a.batch,a.bridge,a.output))
