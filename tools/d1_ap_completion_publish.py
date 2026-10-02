"""Publish six registered confirmations from separate pre/post-pause blocks.

No fitting, device command, state/support enlargement or raw evidence mutation.
"""
import argparse
import csv
import json
from pathlib import Path
from tools import d1_ap_completion_study as study
from tools import d1_resident_control_readout as energy
from tools import d1_simulator as sim
from tools import d1_energy_thermal as integration

p=study.p


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def write_csv(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader();writer.writerows(rows)


def publish(previous,remaining,output):
    previous,remaining,output=map(Path,(previous,remaining,output))
    output=output.resolve()
    s=p.read(remaining);study.verify_sources(s);freeze=study.verify_remaining_freeze(s)
    study.require(s['previous_pause']=={'path':str(previous),'sha256':p.digest(previous)},'previous block binding')
    root=Path(s['output_root']);receipt=p.read(root/'FINAL_RECEIPT.json')
    study.require(receipt['status']=='completed_remaining_confirmation','only completed registered block can publish full six')
    study.require(not output.exists() and output.resolve().is_relative_to(study.ROOT/'docs/results'), 'fresh small share bundle required')
    output.mkdir(parents=True)
    cases=[];scores=[];directions=[];paths=[];energy_paths=[];phase_scores=[]
    blocks=[('v2',previous.parent/'confirmation/collection_plan.json',2),
            ('v3',remaining.parent/'confirmation/collection_plan.json',4)]
    for block,file,count in blocks:
        plan=p.read(file);r=Path(plan['output_root'])
        for entry in plan['entries'][:count]:
            folder=r/f"{entry['index']:02d}_{entry['session_id']}"
            study.require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only','ineligible confirmation')
            case=study.readout.case_from_session(file,plan,entry)
            case.update(id=block+'_'+case['id'],source_block=block,study_phase='confirmation')
            cases.append(case)
            y,init=study.model.predict(case,freeze['selected_model'])
            desc=study.readout.describe(case,y,init,p.read(study.contrast.BUNDLE/'analysis_contract.json'))
            e=energy.session(folder,p.read(file.parent/entry['manifest']),p.read(plan['frozen_model']['path']))
            observed=e['windows']['common']['observed_j'];err=e['signed_diagnostic_error_j']
            study.require(observed is not None and err is not None,'no full common energy; never fill gaps')
            artifact=folder/'artifacts';origin=p.read(artifact/'common_boundary.json')['start_ns']
            events=[json.loads(line) for line in (artifact/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
            samples=[dict(v,mono_ns=(v['snapshot_start_ns']+v['sensor_read_end_ns'])//2)
                     for v in events if v.get('kind')=='power_sample']
            powers=p.read(plan['frozen_model']['path'])['whole_device_power_w']
            from tools.d1_arrival_recorded_replay_analysis import state_key
            for t in range(1,121):
                measured=integration.integrate(samples,origin,origin+t*1_000_000_000,1000)['full_energy_j']
                predicted=sum(max(0,min(seg['end_s'],t)-max(0,seg['start_s']))*powers[state_key(seg['state'])]
                              for seg in case['inputs']['segments'])
                energy_paths.append(dict(id=case['id'],common_s=t,observed_j=measured,
                    original_w_predicted_j=predicted,residual_j=None if measured is None else predicted-measured))
            study.require(abs(energy_paths[-1]['observed_j']-observed)<1e-8 and
                abs(energy_paths[-1]['original_w_predicted_j']-e['frozen_diagnostic_120s_j'])<1e-8,'common endpoint integration mismatch')
            for item in desc['phase_scores']:phase_scores.append(dict(id=case['id'],**item))
            actual_states={}
            for seg in case['inputs']['segments']:
                duration=max(0,min(seg['end_s'],120)-max(seg['start_s'],0))
                actual_states[seg['state']]=actual_states.get(seg['state'],0)+duration
            row=dict(id=case['id'],source_block=block,condition=case['condition'],requests=case['requests'],
                ap_start_c=case['common_start_ap_c'],ap_first_s=desc['first_s'],ap_last_s=desc['last_s'],
                ap_samples=desc['samples'],first_dispatch_s=case['first_dispatch_s'],last_lane_s=case['last_lane_s'],
                power_samples=e['windows']['common']['power_samples'],power_missing_s=e['windows']['common']['missing_seconds'],
                observed_120s_j=observed,original_w_prediction_j=e['frozen_diagnostic_120s_j'],
                signed_energy_difference_j=err,relative_energy_difference_pct=100*err/observed,
                ap_mae_c=desc['scores']['mae_c'],ap_max_error_c=desc['scores']['max_absolute_error_c'],
                ap_peak_signed_error_c=desc['scores']['peak_signed_error_c'],
                ap_delta_mae_c=desc['scores']['mae_c'], # same measured anchor subtracted from both
                current_raw_unit='mA conditional; absolute accuracy uncertified',
                original_initial_ap_supported=32.5<=case['common_start_ap_c']<=34,
                new_fit=False,accuracy_pass=None,strict_support=False)
            row['actual_states_120s_json']=json.dumps(actual_states,sort_keys=True)
            scores.append(row)
            for window in study.model.directions(case,y,p.read(study.CONTRACT)['direction_windows_s']):
                directions.append(dict(id=case['id'],source_block=block,condition=case['condition'],**window))
            for t,o,v in zip(case['inputs']['query_s'],case['observed_ap_c'],y):
                paths.append(dict(id=case['id'],source_block=block,condition=case['condition'],
                    common_s=t,observed_c=o,predicted_c=v,residual_c=v-o))
    study.require([c['condition'] for c in cases]==p.read(study.CONTRACT)['confirmation_order'],'confirmation denominator/order')
    write_json(output/'ap_cases.json',cases);write_json(output/'model.json',freeze['selected_model'])
    write_csv(output/'confirmation_scores.csv',scores);write_csv(output/'directions.csv',directions)
    write_csv(output/'ap_paths.csv',paths)
    write_csv(output/'energy_paths.csv',energy_paths);write_csv(output/'phase_scores.csv',phase_scores)
    rel=lambda f:Path(f).relative_to(study.ROOT).as_posix()
    bound=[output/'ap_cases.json',output/'model.json',Path(study.model.__file__),
        study.ROOT/'tools/d1_ap_preparation_memory.py',study.ROOT/'tools/d1_ap_model_completion.py',
        study.ROOT/'tools/d1_arrival_recorded_replay_analysis.py']
    register=dict(version='registered-conditional-ap-v1',cases_file=rel(output/'ap_cases.json'),
        model_file=rel(output/'model.json'),case_ids=[c['id'] for c in cases],
        files={rel(f):p.digest(f) for f in bound},original_freeze_sha256=s['confirmation_model']['sha256'],
        source_blocks='two confirmations before user pause + four after pause; same freeze, different sessions/environment',
        scope='actual schedule and measured pre35 AP only; no arbitrary arrivals or thermal performance feedback',
        new_fit=0,strict_support=False,accuracy_pass=None,experiment_ready=False)
    write_json(output/'ap_resources.json',register)
    summary=dict(status='registered_confirmations_completed_descriptive_only',development_sessions=6,
        development_reused_old_c=1,selected_name=freeze['selected_name'],model_freeze_sha256=s['confirmation_model']['sha256'],
        freeze_utc=freeze['utc'],confirmation_sessions=6,confirmation_blocks=[dict(id=b,sessions=n) for b,_,n in blocks],
        root_plan_sha256=p.digest(remaining),remaining_budget=s['budget'],remaining_receipt=receipt,
        scores=scores,directions=directions,accuracy_pass=None,strict_support=False,
        energy_ap_policy_rank=None,thermal_performance_feedback='unsupported',experiment_ready=False,
        inputs='actual full lane schedule and AP strictly before common+35; later AP/current are targets only',
        inference='Independent acquired sessions of unchanged selected M0; not blind new-family evaluation or universal error bounds',
        conditioning='Session-specific effective idle criterion and memory from preparation AP; neither ambient nor internal heat observation',
        sources=dict(previous_plan_sha256=p.digest(previous),remaining_plan_sha256=p.digest(remaining)),
        publication_device_commands=0)
    # Private process/transport fields stay in external original receipt, not the small bundle.
    summary.pop('remaining_receipt')
    write_json(output/'summary.json',summary)
    charts=[]
    for row in scores:
        pp=[x for x in paths if x['id']==row['id']]
        chart=sim.plot([(name,[[x['common_s'],x[key]] for x in pp])
                       for name,key in [('Observed','observed_c'),('M0','predicted_c')]],'AP C')
        charts.append('<h2>'+row['id']+'</h2>'+chart+sim.plot([('M0 minus observed',[[x['common_s'],x['residual_c']] for x in pp])],'Residual C'))
        ep=[x for x in energy_paths if x['id']==row['id']]
        charts.append(sim.plot([(name,[[x['common_s'],x[key]] for x in ep])
                               for name,key in [('Observed J','observed_j'),('Original W diagnostic','original_w_predicted_j')]],'Cumulative J'))
    table='<table><tr>'+''.join('<th>'+v+'</th>' for v in ['Block','Condition','Initial AP','MAE C','Max C','Peak error C','Observed J/120s','W minus observed J'])+'</tr>'
    for row in scores:
        values=[row[k] for k in ['source_block','condition','ap_start_c','ap_mae_c','ap_max_error_c','ap_peak_signed_error_c','observed_120s_j','signed_energy_difference_j']]
        table+='<tr>'+''.join('<td>'+sim.fmt(v)+'</td>' for v in values)+'</tr>'
    table+='</table>'
    (output/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>AP 등록 확인6 완료</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:16px}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ccc}svg{max-width:100%;background:#f7f9fb}svg text{font:13px system-ui}</style><h1>동결 M0: 두 block의 확인6 완료</h1><p>개발6에서 사전 규칙으로 M1 미채택·M0 동결 후 확인2＋사용자 휴지 후 확인4를 확보했습니다. 연속12세션 완주·일반 정책 검증이 아닙니다. 실제 일정과 common+35초 전 AP를 사용한 조건부 예측입니다. 에너지는 원래 W식의 [0,120]초 외삽 진단입니다. 정확도 PASS·strict/default 승격·재적합 없음. experiment_ready=false.</p>'+table+'<p><a href="summary.json">판독·범위</a> | <a href="confirmation_scores.csv">확인 오차 CSV</a> | <a href="directions.csv">방향·양자화 민감도</a> | <a href="ap_resources.json">PC 재생 계약</a> | <a href="../../../AP_MODEL_COMPLETION_STUDY_20261002.md">통합 보고서</a></p>'+''.join(charts)+'</html>',encoding='utf-8')
    return summary


def main():
    q=argparse.ArgumentParser(description=__doc__)
    for name in ('previous','remaining','output'):q.add_argument('--'+name,required=True)
    a=q.parse_args();r=publish(a.previous,a.remaining,a.output)
    print(json.dumps(dict(status=r['status'],confirmation_sessions=6,device_commands=0)))


if __name__=='__main__':main()
