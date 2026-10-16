"""Post-hoc explanation of saved actions only; no fitting or new policy selection."""
import argparse
import json
from pathlib import Path
from tools import d1_empirical_request_policy as p


def explain(folder):
    folder=Path(folder);groups={};waits={};witness=[]
    fields=('id','backend','dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns','response_ns','status')
    for line in (folder/'local_ledgers.jsonl').open(encoding='utf8'):
        r=json.loads(line)
        if r['stage']!='test':continue
        key=(r['trace_seed'],r['family'],r['scenario']);pol=r['policy']
        schedule=tuple(tuple(q.get(f) for f in fields) for q in r['ledger'])
        groups.setdefault(key,{})[pol]=schedule
        waits[pol]=waits.get(pol,0)+sum(d.get('chosen_explicit_delay_s',0)>0 and not d['selected'] for d in r['decisions'])
        if key==(70001,'low','mean') and pol=='PARETO_MPC_V1':
            by={q['id']:q for q in r['ledger']}
            for d in r['decisions']:
                if len(witness)>=6:break
                if d.get('chosen_explicit_delay_s',0)>0 and not d['selected']:
                    q=by[d['chosen_request_id']]
                    witness.append(dict(request_id=q['id'],decision_s=d['now_ns']/1e9,
                        proposed_wait_s=d['chosen_explicit_delay_s'],actual_dispatch_s=q['dispatch_ns']/1e9,
                        actual_response_ms=q['response_ns']/1e6,deadline_ms=q['deadline_offset_ns']/1e6))
    assert len(groups)==96
    equal={pol:sum(g[pol]==g['EFT_REFERENCE'] for g in groups.values()) for pol in next(iter(groups.values()))}
    mpc_equal=sum(g['PARETO_MPC_V1']==g['THERMAL_MPC_V1'] for g in groups.values())
    result=dict(evaluated_conditions=96,exact_request_timing_equal_to_eft=equal,energy_and_thermal_mpc_same_schedule=mpc_equal,
        wait_proposals=waits,wait_count_is_not_elapsed_wait_time=True,representative_mpc_wait_witness=witness,
        interpretation='post-hoc descriptive explanation; no causal ablation, no policy retuning, no final-test selection',
        device_commands=0,simulation_reruns=0)
    p.write(folder/'mechanism_summary.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();print(explain(args.folder))
