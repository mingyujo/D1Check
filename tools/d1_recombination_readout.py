"""Read-only first-decision audit of preserved microcase forecasts, no engine."""
import json
from pathlib import Path
from tools import d1_rule_recombination as r
from tools import d1_rules_rl_common as c


def audit(folder=c.OUTPUT):
    folder=Path(folder);root=folder/'recombination'
    frozen,case=r.P.inputs(r.P.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    inputs={(x['stage'],x['seed'],x['pattern']):x['tickets'] for x in c.read(root/'inputs.json')}
    results=[]
    for line in (root/'local_details.jsonl').read_text(encoding='utf8').splitlines():
        detail=json.loads(line)
        if detail['policy']!=r.COMPLETE:continue
        log=next((x for x in detail['search'] if len(x.get('pool_ids',[]))==3),None)
        if log is None:continue
        qs=inputs[detail['stage'],detail['seed'],detail['pattern']]
        now=log['now_ns']/1e9
        if any(q['arrival_ns']!=log['now_ns'] for q in qs):raise ValueError('audit restricted to first simultaneous arrival')
        controller=r.Controller(frozen,initial,r.COMPLETE)
        lanes={b:dict(request=None,phase=None,since=0,dispatch=None) for b in ('CPU','GPU')}
        controller.observe(log['now_ns'],lanes)
        qs=r.area.x.ordered(qs,log['now_ns'],r.area.x.settings())
        reference=tuple(tuple(x) for x in log['reference_sequence'])
        ref_jobs,_=controller.finish_plan(reference,qs,[],now,controller)
        ref_score=controller.score(ref_jobs,now)
        if any(abs(ref_score[k]-value)>1e-9 for k,value in log['reference_prediction'].items()):
            raise ValueError('forecast readout did not reproduce registered reference')
        ref_long,_=controller.finish_plan(reference,qs,[],now,controller.long)
        ref_lateness=r.area.x.lateness(ref_long)
        # The recorded selector explicitly appends its reference incumbent to an
        # aliased candidate list. It is not an additional complete permutation.
        # Correct only this diagnostic count, preserving raw records and choices.
        sequences=sorted({tuple(tuple(x) for x in s) for s in log['missed_sequences'] if len(s)==len(qs)})
        for sequence in sequences:
            failures=[]
            for depth in range(1,len(sequence)):
                jobs,first=controller.finish_plan(sequence[:depth],qs,[],now,controller)
                long_jobs,_=controller.finish_plan(sequence[:depth],qs,[],now,controller.long)
                score=controller.score(jobs,now)
                causes=[]
                if first['start']>now+1e-9:causes.append('not_immediate')
                if r.area.x.guard_worsens(r.area.x.lateness(long_jobs),ref_lateness):causes.append('service_guard')
                if score is None:causes.append('window_or_AP_area')
                elif (score['remaining_energy_j']>ref_score['remaining_energy_j']+1e-9 or
                      score['predicted_peak_ap_c']>ref_score['predicted_peak_ap_c']+1e-9):causes.append('J_or_peak_guard')
                if causes:failures.append(dict(depth=depth,causes=causes))
            full_jobs,_=controller.finish_plan(sequence,qs,[],now,controller)
            full_long,_=controller.finish_plan(sequence,qs,[],now,controller.long)
            full_score=controller.score(full_jobs,now)
            if (full_score is None or r.area.x.guard_worsens(r.area.x.lateness(full_long),ref_lateness) or
                full_score['remaining_energy_j']>ref_score['remaining_energy_j']+1e-9 or
                full_score['predicted_peak_ap_c']>ref_score['predicted_peak_ap_c']+1e-9):
                raise ValueError('reported missed complete branch does not pass final guard')
            results.append(dict(stage=detail['stage'],seed=detail['seed'],pattern=detail['pattern'],context=detail['context'],
                sequence=sequence,prefix_failures=failures,
                cause='intermediate_guard' if failures else 'beam_width_or_prefix_retention',full_score=full_score,
                reference=ref_score))
    c.atomic(root/'first_decision_branch_audit.json',dict(records=results,environment_runs=0,
        scope='first simultaneous 3-request decision only; current modeled thermal state reproduced',
        raw_counter_correction='explicit reference incumbent excluded from complete-permutation counts; actions/metrics unchanged',
        input_sha256=c.digest(root/'inputs.json'),raw_sha256=c.digest(root/'local_details.jsonl')))
    return results


if __name__=='__main__':
    rows=audit();print(json.dumps(dict(records=len(rows),intermediate_guard=sum(x['cause']=='intermediate_guard' for x in rows),
        retained_other=sum(x['cause']!='intermediate_guard' for x in rows))))
