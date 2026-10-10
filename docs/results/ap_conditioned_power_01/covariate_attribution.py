"""Diagnostic target-covariate substitution only; never called by prediction API."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_conditioned_power as m


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);source=m.BUNDLE/'run_v1';m.assets(source)
    context=ROOT/'docs/results/preboundary_evidence_01/run_v1/matched_C0_CPU_context.csv'
    target={r['session']:r for r in m.table(context) if r['phase']=='future85_idle'}
    public={p['id']:p for p in m.public_cases(source)};rows=[]
    for r in m.table(m.BUNDLE/'readout_v1/C0_oracle_attribution.csv'):
        p=public[r['session']];key=str(p['gap']) if p['role']=='development' else 'final';model=m.old.old.read(source/('candidate_CPU_AP_'+key+'.json'))
        x=target[r['session']]
        if float(x['lo_s'])!=35 or float(x['hi_s'])!=120 or x['full_8core_sched_coverage']!='True':raise ValueError('context coverage/window')
        U=float(x['other_cpu_seconds'])/85;prediction=p['features']['persistent_other_proxy']
        error=model['CPU_slope_W_per_core_s_per_s']*(prediction-U)*85
        rows.append(dict(r,forecast_persistent_CPU_rate=prediction,observed_future_CPU_rate=U,
            CPU_feature_forecast_error_contribution_J=error,
            oracle_CPU_AP_future_signed_error_J=float(r['oracle_AP_future_signed_error_J'])-error,
            forbidden_future_covariates_for_diagnosis_only=True,not_a_forecast=True))
    m.old.old.prior.prior.old.scope_api.tail.s.csv_write(out/'C0_covariate_oracle.csv',rows)
    m.old.old.write(out/'receipt.json',dict(status='fixed_covariate_attribution_complete',controls=4,
        context_sha256=m.old.old.sha(context),contract_sha256=m.old.old.sha(m.BUNDLE/'covariate_attribution_contract.json'),
        new_fits=0,new_forecasts=0,oracle_not_used_as_input_or_selector=True,device_commands=0,
        default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False))
    print(m.old.old.prior.prior.terminal_json(rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
