"""Two-session forward check of a posthoc thermal-only hybrid; no fit/device API."""
import argparse
import copy
import html
import json
from pathlib import Path
import statistics

from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v3 as model
from tools import d1_simulation_model_v3_inputs as inputs
from tools import d1_simulation_model_v3_report as base

VARIANT = 'thermal_only_hybrid_v1'
MODELS = ('original', 'v2', 'hybrid')
POLICIES = (base.POLICIES[0], base.POLICIES[1])
TOLERANCE = 1e-10
PARENT_REPORT = model.ROOT/'docs/results/simulation_model_v3_expert_01/run_v1/summary.json'
LIMITATIONS = [
    '새 2세션은 정책마다 1회인 최소 전향 확인이다. 통계적 유의성과 일반적인 우월성은 미판정이다.',
    '첫 v3의 AP와 에너지 동시 오차 감소 판정은 FAIL로 유지한다. 사후 hybrid 조립과 새 판정 기준을 이전 결과에 소급 적용하지 않는다.',
    '에너지와 P95는 원모형 예측과 동등하다. 에너지 또는 응답시간 오차 감소를 주장하지 않는다.',
    '정책 한쪽의 AP 오차가 커지면 두 정책 모두 개선됐다고 표현하지 않는다. 모든 세션, 피크, 최악 오차와 잔차를 공개한다.',
    '기기 전체 전류를 mA로 해석한 에너지는 절대 교정이 미인증이다. 배터리 6% 하한을 허용한 새 APK 환경의 확인이다.',
    '원 collector의 완료 영수증 scope에는 four라는 고정 문구가 남아 있다. 이는 메타데이터 문구 오류이며 실제 계획과 세션 분모는 2이다. 원 collector와 영수증은 수정하지 않는다.',
]


def hybrid_guard(plan, run, hashes, allow_missing_local=False):
    frozen, original, previous = base._model_guard(plan, run, hashes, allow_missing_local)
    candidate = frozen['model']
    spec = frozen['parent_candidate_freeze']
    if plan['parent_candidate_freeze'] != spec:
        raise ValueError('hybrid parent reference mismatch')
    base._hash(spec['path'], hashes, spec['sha256'])
    parent = p.read(spec['path'])
    parent_model = Path(spec['path']).parent/'model.json'
    base._hash(parent_model, hashes, candidate['parent_model_sha256'])
    if p.read(parent_model) != parent['model']:
        raise ValueError('parent numerical export mismatch')
    if candidate.get('variant') != VARIANT or candidate.get('composition_is_posthoc') is not True:
        raise ValueError('hybrid variant/posthoc scope missing')
    if frozen['fit_calls'] != 0 or candidate['thermal'] != parent['model']['thermal']:
        raise ValueError('thermal head was refit or changed after parent confirmation')
    energy = candidate['energy']
    if (energy['increments'] != original['energy_increment_w'] or energy['gain'] != 0
            or energy.get('energy_fit_calls') != 0 or energy.get('ridge_not_applied') is not True
            or energy.get('energy_mode') != 'frozen_original_exact'
            or energy.get('original_sha256') != plan['original_model']['sha256']):
        raise ValueError('energy must be exact original; no fitting/ridge/relaxation')
    if candidate.get('energy_decrease_claim') is not False or candidate.get('service_decrease_claim') is not False:
        raise ValueError('hybrid must not claim energy/service error decrease')
    base._hash(plan['hybrid_contract']['path'], hashes, plan['hybrid_contract']['sha256'])
    completed = plan['parent_completed_experiment']
    base._hash(completed['path'], hashes, completed['sha256'])
    parent_receipt = p.read(completed['path'])
    if parent_receipt.get('sessions') != 4 or parent_receipt.get('post_confirmation_fit_calls') != 0:
        raise ValueError('parent four-session terminal evidence mismatch')
    base._hash(PARENT_REPORT, hashes)
    parent_report = p.read(PARENT_REPORT)
    if (parent_report['frozen_model_sha256'] != spec['sha256']
            or parent_report['comparison']['joint_cost_error_decrease_pass'] is not False
            or parent_report['terminal_receipt'] != parent_receipt):
        raise ValueError('original v3 joint FAIL evidence must remain unchanged')
    return frozen, original, previous, parent, parent_report


def evaluate_case(c, manifest, candidate, original, previous):
    result = base.evaluate_case(c, manifest, candidate, original, previous)
    for row in result['scores']:
        if row['model'] == 'v3':
            row['model'] = 'hybrid'
    for row in result['curves']:
        row['hybrid_AP_c'] = row.pop('v3_AP_c')
    public = inputs.public_input(c)
    initial = dict(preload=public['pre'], preload_power_w=public['pre_w'])
    control, _ = base.v2.prior.base.forecast(initial, manifest['requests'], manifest['policy'], original,
                                            planning_input_role='confirmation')
    forecast = result['forecast']
    other_service = base.forecast_service(control)
    service = result['forecast_service']
    energy_delta = forecast['predicted_J120']-forecast['original_J120']
    identity = dict(session=c['id'], policy=manifest['policy'], J120_delta_j=energy_delta,
        J120_prediction_identity=abs(energy_delta)<=TOLERANCE,
        ledger_identity=forecast['legacy']['ledger']==control['ledger'],
        service_metrics_identity=service==other_service,
        P95_identity=all(service[k]['response_P95_ms']==other_service[k]['response_P95_ms'] for k in service),
        tolerance_j=TOLERANCE, energy_decrease_claim=False, service_decrease_claim=False)
    result['identity'] = identity
    result['forecast']['variant'] = VARIANT
    for row in result['service_rows']:
        row['original_and_hybrid_P95_ms'] = row.pop('original_and_v3_P95_ms')
        row['service_scope'] = 'frozen original service; hybrid ledger/P95/success exactly equal'
    return result


def aggregate_scores(rows, roster, identities):
    validated = sum(r['status']=='validated' for r in roster)
    result = dict(planned_sessions=len(roster), validated_sessions=validated,
        missing_sessions=len(roster)-validated, all_two_validated=len(roster)==2 and validated==2,
        hybrid_comparison_pass=None, original_V3_joint_pass=False,
        energy_decrease_claim=False, service_decrease_claim=False,
        primary_mode=base.MODES[1], missing_measurements_are_not_zero=True, modes={})
    def summarize(use):
        if len({r['session'] for r in use}) != len(use):
            raise ValueError('duplicate hybrid score rows')
        return dict(evaluated_sessions=len(use), mean_AP_MAE_c=statistics.mean(r['mae_c'] for r in use),
            mean_J120_abs_j=statistics.mean(r['J120_abs_j'] for r in use),
            mean_J120_signed_j=statistics.mean(r['J120_signed_j'] for r in use),
            worst_AP_MAE_c=max(r['mae_c'] for r in use),
            worst_AP_max_error_c=max(r['max_absolute_error_c'] for r in use),
            worst_J120_abs_j=max(r['J120_abs_j'] for r in use))
    for mode in base.MODES:
        use = [r for r in rows if r['mode']==mode]
        overall = {name:summarize([r for r in use if r['model']==name]) for name in MODELS if any(r['model']==name for r in use)}
        policies = {}
        for policy in POLICIES:
            policies[policy] = {name:summarize([r for r in use if r['model']==name and r['policy']==policy])
                for name in MODELS if any(r['model']==name and r['policy']==policy for r in use)}
        result['modes'][mode] = dict(overall=overall, by_policy=policies)
    if result['all_two_validated']:
        values = result['modes'][base.MODES[1]]['overall']
        if any(values.get(name,{}).get('evaluated_sessions')!=2 for name in MODELS):
            raise ValueError('two valid sessions require all fixed candidate scores')
        if len(identities)!=2 or len({r['session'] for r in identities})!=2:
            raise ValueError('two session identity checks required')
        ap = values['hybrid']['mean_AP_MAE_c'] < values['original']['mean_AP_MAE_c']
        same = all(r[key] for r in identities for key in
                   ('J120_prediction_identity','ledger_identity','service_metrics_identity','P95_identity'))
        policy_changes = {}
        for policy, group in result['modes'][base.MODES[1]]['by_policy'].items():
            if any(group.get(name,{}).get('evaluated_sessions')!=1 for name in MODELS):
                raise ValueError('exact one new CPU and one new PAR required')
            policy_changes[policy] = group['hybrid']['mean_AP_MAE_c']-group['original']['mean_AP_MAE_c']
        result.update(AP_mean_improved=ap, energy_and_service_identity_pass=same,
            hybrid_comparison_pass=ap and same, policy_AP_change_c=policy_changes,
            policies_with_AP_worsening=[k for k,v in policy_changes.items() if v>0],
            policy_AP_improved={k:v<0 for k,v in policy_changes.items()})
    result['comparison_rule'] = 'new2 mean B AP MAE strictly decreases; each J120 prediction equals original within1e-10 J and ledger/P95/predicted service counts equal; not original V3 joint AP/J decrease gate'
    result['scope'] = 'minimum forward confirmation: one session per policy, no significance or population superiority conclusion'
    return result


def report(run, output):
    run, output = Path(run).resolve(), Path(output).resolve()
    terminal = run/'FINAL_RECEIPT.json'
    if not terminal.is_file():
        raise ValueError('active run: FINAL_RECEIPT.json required')
    if output.exists():
        raise ValueError('new immutable report output required')
    hashes = {}; base._hash(terminal, hashes); receipt=p.read(terminal)
    if receipt.get('status') not in ('completed_regimen_diagnostic_only','stopped_no_resume'):
        raise ValueError('unsupported hybrid terminal receipt')
    plan_file = run.parent/'plan/collection_plan.json'
    base._hash(plan_file, hashes); plan=p.read(plan_file)
    if not plan.get('model_v3_hybrid') or len(plan['entries'])!=2 or len({e['session_id'] for e in plan['entries']})!=2:
        raise ValueError('two new hybrid confirmation sessions required')
    frozen, original, previous, parent, parent_report = hybrid_guard(plan, run, hashes,
        allow_missing_local=receipt['status']=='stopped_no_resume' and receipt.get('completed_sessions')==0)
    candidate = frozen['model']
    if receipt.get('post_confirmation_fit_calls',0)!=0 or receipt.get('preserved_freeze_sha256',plan['prior_freeze']['sha256'])!=plan['prior_freeze']['sha256']:
        raise ValueError('hybrid terminal fitting/freeze mismatch')
    roster, metrics, curves, service_rows, forecasts, identities = [], [], [], [], [], []
    raw_inventory = {}
    from tools import d1_resident_identification_analysis as reader
    from tools import d1_separated_power_protocol as separated
    for e, policy in zip(plan['entries'],POLICIES):
        if e['index']!=len(roster) or e['role']!='confirmation' or e.get('completed_reuse'):
            raise ValueError('fresh hybrid index/role changed')
        source = plan_file.parent/e['manifest']
        base._hash(source,hashes,e['manifest_sha256']); manifest=p.read(source)
        if manifest['policy']!=policy or manifest['session_id']!=e['session_id'] or manifest['apk_sha256']!=plan['apk_sha256']:
            raise ValueError('hybrid policy/UUID/APK mismatch')
        separated.validate('confirmation',manifest['requests'])
        folder=run/f"{e['index']:02d}_{e['session_id']}"
        row=dict(index=e['index'],session=manifest['phase'],session_id=e['session_id'],policy=policy,
            planned_requests=96,status='not_validated',observed_completed=None,observed_timely=None,battery_scope=None,
            APK=manifest['apk_sha256'])
        raw_inventory[row['session']]={name:base._hash(folder/name,hashes) if (folder/name).is_file() else None for name in base.CORE_FILES}
        for path in sorted(folder.glob('artifacts/*failure.json')):
            raw_inventory[row['session']][str(path.relative_to(folder))]=base._hash(path,hashes)
        if (folder/'validated.json').is_file():
            for name in ('input_manifest.json','artifacts/manifest.json'):
                base._hash(folder/name,hashes,e['manifest_sha256'])
            stats=p.read(folder/'validated.json'); c=stats['analysis_case']
            if c['id']!=manifest['phase'] or c['role']!='confirmation' or c['manifest_requests']!=manifest['requests']:
                raise ValueError('hybrid raw/derived identity mismatch')
            if (stats['work_calls'],stats['warmup_calls'],stats['eligibility_calls'])!=(96,8,0):
                raise ValueError('hybrid full invocation denominator')
            requests=p.read(folder/'artifacts/requests.json')
            if requests!=c['actual_requests'] or len(requests)!=96 or {r['request_id'] for r in requests}!={r['request_id'] for r in manifest['requests']}:
                raise ValueError('hybrid raw completion/planned request IDs')
            events=[json.loads(line) for line in (folder/'artifacts/progress.jsonl').read_text(encoding='utf8').splitlines()]
            if not events or any(r['session_id']!=e['session_id'] for r in events):
                raise ValueError('hybrid journal ownership')
            derived=reader.arrival_case(folder/'artifacts',manifest)
            if any(c[k]!=derived[k] for k in ('pre','pre_w','q','ap','actual','power_t','power_w','common_end_s')):
                raise ValueError('hybrid derived targets/schedule differ from native raw')
            if p.read(folder/'artifacts/common_boundary.json')['start_ns']!=c['origin_ns'] or p.read(folder/'artifacts/cleanup.json')['status']!='completed' or any(folder.glob('artifacts/*failure.json')):
                raise ValueError('hybrid raw clock/cleanup/failure inconsistency')
            result=evaluate_case(c,manifest,candidate,original,previous)
            metrics.extend(result['scores']);curves.extend(result['curves']);service_rows.extend(result['service_rows'])
            identities.append(result['identity']);forecasts.append(dict(session=c['id'],policy=policy,**result))
            row.update(status='validated',observed_completed=sum(s['completed'] for s in result['observed_service'].values()),
                observed_timely=sum(s['timely'] for s in result['observed_service'].values()),battery_scope=stats.get('battery_scope'),
                initial_AP_c=c['pre'][-1]['ap'],initial_power_w=c['pre_w'],raw_requests=96,warmup=8)
        elif folder.exists():
            row['status']='attempted_not_validated'
        roster.append(row)
    valid=sum(r['status']=='validated' for r in roster)
    if receipt.get('sessions',receipt.get('completed_sessions'))!=valid or (receipt['status'].startswith('completed_') and valid!=2):
        raise ValueError('hybrid terminal/validated roster disagree')
    comparison=aggregate_scores(metrics,roster,identities)
    base._hash(Path(__file__),hashes);base._hash(Path(base.__file__),hashes)
    completed=sum(r['observed_completed'] for r in roster if r['observed_completed'] is not None)
    timely=sum(r['observed_timely'] for r in roster if r['observed_timely'] is not None)
    battery=[r['battery_scope'] for r in roster if r['battery_scope'] is not None]
    summary=dict(version=model.VERSION,variant=VARIANT,composition_is_posthoc=True,terminal_receipt=receipt,
        session_roster=roster,comparison=comparison,metrics=metrics,service_rows=service_rows,forecasts=forecasts,
        identities=identities,planned_requests=192,confirmed_completed_requests=completed,confirmed_timely_requests=timely,
        unvalidated_planned_requests=96*(2-valid),confirmed_completion_lower_bound_rate=completed/192,
        confirmed_timely_lower_bound_rate=timely/192,missing_raw_completions_are_unknown_not_failures=True,
        source_hashes=hashes,core_raw_sha256=raw_inventory,frozen_model_sha256=plan['prior_freeze']['sha256'],
        model_sha256=p.digest(Path(plan['prior_freeze']['path']).parent/'model.json'),fit_calls=0,post_confirmation_fit_calls=0,
        thermal_exact_parent=True,energy_exact_original=True,energy_fit_calls=0,ridge_not_applied=True,
        energy_decrease_claim=False,service_decrease_claim=False,original_V3_joint_pass=False,
        parent_candidate_freeze=copy.deepcopy(frozen['parent_candidate_freeze']),composition_scope=frozen['composition_scope'],
        parent_four_comparison=parent_report['comparison'],parent_four_scope='preregistered AP component evidence only; full hybrid assembled after parent outcomes',
        parent_development_nested=base.development_readout(parent),
        parent_failure_appendix=parent_report['failure_appendix'],
        environment=dict(native_APK_sha256=plan['apk_sha256'],admitted_minimum_percent=plan.get('battery_min_percent',20),
            minimum_observed_percent=min(r['minimum_observed_percent'] for r in battery) if battery else None,
            any_below20=any(r['any_below20'] for r in battery) if battery else None,
            power_save_mode_observed=any(r['power_save_mode_observed'] for r in battery) if battery else None),
        measurement_contract={k:copy.deepcopy(plan[k]) for k in ('experiment_id','budget','hybrid_contract')},
        default=False,strict_support=False,experiment_ready=False,accuracy_pass=None,
        receipt_scope_label_is_stale='four' in receipt.get('scope',''),
        limitations=copy.deepcopy(LIMITATIONS))
    output.mkdir(parents=True)
    for name,rows in (('sessions.csv',roster),('cost_scores.csv',metrics),('AP_curves.csv',curves),
                      ('service_scores.csv',service_rows),('identity_checks.csv',identities)):
        base._csv(output,name,rows)
    base._write(output,'summary.json',summary);base._write(output,'model.json',candidate)
    source=run/'development_freeze.json' if (run/'development_freeze.json').is_file() else Path(plan['prior_freeze']['path'])
    with (output/'development_freeze.json').open('xb') as handle:handle.write(source.read_bytes())
    if p.read(output/'model.json')!=candidate or p.digest(output/'development_freeze.json')!=plan['prior_freeze']['sha256']:
        raise ValueError('hybrid numerical export drift')
    base._write(output,'export_receipt.json',dict(model_sha256=p.digest(output/'model.json'),
        development_freeze_sha256=p.digest(output/'development_freeze.json'),numerical_dictionary_equal=True,
        fit_calls=0,device_commands=0,source_hashes=hashes))
    figures=plots(output,roster,curves,metrics,service_rows)
    (output/'index.html').write_text(page(summary,figures),encoding='utf8')
    return dict(status=receipt['status'],planned=2,validated=valid,
        hybrid_comparison_pass=comparison['hybrid_comparison_pass'],original_V3_joint_pass=False,
        model_sha256=p.digest(output/'model.json'),report=str(output/'index.html'),fit_calls=0,device_commands=0)


def plots(folder,roster,curves,metrics,services):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False})
    colors=dict(original='#a16207',v2='#64748b',hybrid='#0e7490')
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,session in zip(axes,roster):
        use=[r for r in curves if r['session']==session['session'] and r['mode']==base.MODES[1]]
        if use:
            t=[r['time_s'] for r in use];ax.plot(t,[r['observed_AP_c'] for r in use],color='black',label='관측',lw=1.8)
            for name in MODELS:ax.plot(t,[r[name+'_AP_c'] for r in use],color=colors[name],label=name)
            ax.legend()
        else:ax.text(.5,.5,'검증된 계측 없음',transform=ax.transAxes,ha='center')
        ax.set_title('CPU' if session['policy']==POLICIES[0] else 'PAR');ax.set_xlabel('공통 원점 이후 초');ax.set_ylabel('HAL AP °C')
    fig.suptitle('사후 조립 hybrid · 새2 전향 확인 · 동일 원서비스 B');fig.tight_layout();fig.savefig(folder/'AP_paths.png',dpi=140);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4))
    for j,name in enumerate(MODELS):
        use=[r for r in metrics if r['mode']==base.MODES[1] and r['model']==name]
        ax.bar([next(s['index'] for s in roster if s['session']==r['session'])+(j-1)*.24 for r in use],
            [r['J120_abs_j'] for r in use],width=.23,color=colors[name],label=name)
    ax.set_xticks(range(2),['CPU','PAR']);ax.set_ylabel('|예측-관측| J / 0..120초')
    ax.set_title('원모형 = hybrid 에너지 예측 · 감소 주장이 아닌 동등성');ax.legend();fig.tight_layout();fig.savefig(folder/'energy_error.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,priority in zip(axes,('urgent','normal')):
        use=[r for r in services if r['priority']==priority]
        for label,key,shift,color in (('실측','observed_P95_ms',-.14,'#111827'),('원서비스 = hybrid','original_and_hybrid_P95_ms',.14,'#0e7490')):
            ax.bar([next(s['index'] for s in roster if s['session']==r['session'])+shift for r in use],
                [r[key] for r in use],width=.28,label=label,color=color)
        ax.set_xticks(range(2),['CPU','PAR']);ax.set_title('긴급 분류' if priority=='urgent' else '일반 탐지');ax.set_ylabel('완료 응답 P95 ms');ax.legend()
    fig.suptitle('원장·P95·예측 성공률 원모형 동등 · 처리시간 개선 주장 없음');fig.tight_layout();fig.savefig(folder/'service_P95.png',dpi=140);plt.close(fig)
    return ['AP_paths.png','energy_error.png','service_P95.png']


def page(summary,figures):
    e=html.escape;result=summary['comparison'];passed=result['hybrid_comparison_pass']
    title='새2 평균 AP 감소 · 에너지/서비스 동등 조건 충족' if passed is True else '새2 판정 조건 불충족' if passed is False else '새2 미완료 · 판정 보류'
    def table(rows,keys):
        return '<table><tr>'+''.join('<th>'+e(k)+'</th>' for k in keys)+'</tr>'+''.join('<tr>'+''.join('<td>'+e(str(round(r[k],5) if isinstance(r.get(k),float) else r.get(k,'')))+'</td>' for k in keys)+'</tr>' for r in rows)+'</table>'
    rows=[]
    for mode in base.MODES:
        for name,values in result['modes'][mode]['overall'].items():rows.append(dict(mode=mode,model=name,**values))
    warning=' · '.join(result.get('policies_with_AP_worsening',[])) or '검증된 전체 자료의 정책별 수치는 summary/CSV 참조'
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>D1Check thermal hybrid 확인</title><style>body{font:16px system-ui;margin:28px;max-width:1200px}table{border-collapse:collapse;margin:16px 0}th,td{border:1px solid #ccc;padding:8px}img{max-width:100%}.note{background:#eef2ff;padding:14px}.scroll{overflow:auto}</style><h1>온도 보정 hybrid · 새2 전향 확인</h1><h2>'+e(title)+'</h2><p class="note">첫 v3의 AP/J 동시 감소 FAIL은 유지합니다. 새4 이후 에너지 보정을 폐기한 사후 조립이며 thermal 계수/α/λ는 사전동결값 그대로입니다. 새2의 기준은 AP 평균 감소＋원 에너지/서비스 동등성입니다. 에너지·P95 오차 감소를 주장하지 않습니다.</p><p><a href="summary.json">전체 수치·한계·부모FAIL</a> · <a href="model.json">새 hybrid 모형</a> · <a href="development_freeze.json">동결 증거</a> · <a href="cost_scores.csv">A/B 전체 오차</a> · <a href="identity_checks.csv">에너지·원장·P95 동등 검사</a> · <a href="service_scores.csv">전체 도착 분모·서비스</a> · <a href="../run_v1/index.html">첫 v3 확인4 원결과</a> · <a href="../../../SIMULATION_MODEL_V3_HYBRID_20261010.md">사전 후속 기준</a></p><h2>예정2 · 검증'+str(result['validated_sessions'])+'</h2>'+table(summary['session_roster'],('index','policy','status','planned_requests','observed_completed','observed_timely'))+'<h2>A/B 평균·최악</h2><div class="scroll">'+table(rows,('mode','model','evaluated_sessions','mean_AP_MAE_c','mean_J120_abs_j','worst_AP_MAE_c','worst_AP_max_error_c'))+'</div><p>정책별 AP 악화: '+e(warning)+'. 한쪽의 악화를 평균으로 숨기지 않습니다.</p><h2>동등성 검사</h2>'+table(summary['identities'],('policy','J120_delta_j','J120_prediction_identity','ledger_identity','P95_identity','service_metrics_identity'))+'<h2>배터리·절전</h2><pre>'+e(json.dumps(summary['environment'],ensure_ascii=False,indent=2))+'</pre>'+''.join('<img src="'+e(f)+'" alt="'+e(f)+'">' for f in figures)+'<h2>해석 범위</h2><ul>'+''.join('<li>'+e(v)+'</li>' for v in summary['limitations'])+'</ul><p>기본/RL/strict/experiment_ready=false를 유지합니다. 각 정책1회는 최소 전향 확인이며 유의성·일반 우월성·실제 정책 효과는 미판정입니다.</p></html>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(report(args.run,args.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
