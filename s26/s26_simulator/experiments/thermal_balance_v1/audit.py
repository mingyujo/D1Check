"""Saved-only independent JS replay, provenance and passivity audit."""
import gzip
import json
import math
import subprocess
from pathlib import Path
import numpy as np
from calibrate import read, save, sha, verify


def audit(op):
    out = Path(op['output'])
    verify(op)
    eps = read(out/'PREPARED.json.gz')
    rows = read(out/'OOF_ROWS.json.gz')
    result, model = read(out/'RESULT.json'), read(out/'MODEL.json')
    receipts = [json.loads(line) for line in (out/'FIT_RECEIPTS.jsonl').read_text(encoding='utf-8').splitlines()]
    starts, completes = [[r for r in receipts if r['event']==event] for event in ('START','COMPLETE')]
    assert len(starts)==len(completes)==result['fits']==op['planned_fit_START']
    assert len({r['id'] for r in starts})==len(starts)
    models = {}
    for r in completes:
        p = out/'models'/(r['id']+'.json')
        assert sha(p)==r['model_sha256']
        models[r['id']] = read(p)
    by = {r['id']: r for r in rows}
    models_used = {r['model'] for r in rows}
    checks = 0
    for ep in eps:
        r = by[ep['id']]
        m = models[r['model']]
        assert ep['group'] not in m['train_groups'] and ep['id'] not in m['train_ids']
        assert r['times']==ep['times'] and r['observed']==ep['observed']
        ep['model'] = r['model']
        checks += 4
    for profile in read(out/'TAU_PROFILES.json'):
        selected = min(profile['profiles'],key=lambda m:(m['train_MSE'],m['tau_s']))
        assert selected['id']==profile['selected']
        checks += 1
    payload = dict(cases=eps,models={k:models[k] for k in models_used})
    replay = subprocess.run(['node',str(Path(__file__).parent/'test_rc.cjs'),'replay'],
        input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',check=True)
    max_error = 0.
    for r in json.loads(replay.stdout):
        error = abs(np.asarray(r['predicted'])-np.asarray(by[r['id']]['predicted']))
        max_error = max(max_error,float(max(error)))
        checks += len(error)
    assert max_error < 1e-8
    # Independent numerical quadrature for ramp convolution, not the update implementation.
    from scipy.integrate import quad
    numeric_error = 0.
    from rc_model import advance
    for tau in op['tau_grid_s']:
        for dt in (.0001,.3,5.,60.,900.):
            a,b,x = .7,2.3,.2
            integration = quad(lambda u: math.exp(-(dt-u)/tau)*(a+(b-a)*u/dt)/tau,
                               0,dt,epsabs=1e-11,epsrel=1e-11)[0]
            expected = x*math.exp(-dt/tau)+integration
            numeric_error=max(numeric_error,abs(expected-advance(x,a,b,dt,tau)))
            checks += 1
    assert numeric_error < 1e-9
    gain = model['gain_C_per_API_W']
    assert gain >= 0 and model['tau_s']>0
    # Constant-input extrema and finite equilibrium are structural properties, not measured phone claims.
    support = read(out/'MARGINAL_SUPPORT.json')['limits']
    eq = [s+model['delta_C']+gain*(p-b) for s in support['anchor_SKIN_C']
          for p in support['power_API_W'] for b in support['baseline_API_W']]
    tests = read(out/'PURE_TESTS.json')
    assert tests['status']=='PASS'
    checks += tests['checks']
    validity = []
    oldsummary = read(op['inputs']['sustained_summary']['path'])
    # Supports JSON summary variants without changing original saved data.
    case_rows = oldsummary if isinstance(oldsummary,list) else oldsummary.get('cases',oldsummary.get('rows',[]))
    for r in case_rows:
        m = r.get('metrics') or r
        peak = m.get('AP_peak',m.get('AP_peak_C'))
        validity.append(dict(id=r.get('id',r.get('case_id',str(r.get('input'))+'_'+str(r.get('model'))+'_'+str(r.get('policy')))), AP_peak_C=peak,
            AP_marginal_support=bool(peak is not None and support['AP_C'][0]<=peak<=support['AP_C'][1]),
            policy_advantage_admissible=False, reason='Frozen wall-phase model lacks validated CPU waiting/power/thermal transfer; fit-range check alone is insufficient'))
    assert len(validity)==36 and len({r['id'] for r in validity})==36
    save(out/'SUSTAINED_VALIDITY.json',validity)
    audit_result = dict(status='PASS_SAVED_REPLAY_AND_MATH_ONLY',checks=checks,JS_replay_points=sum(len(r['times']) for r in rows),
        max_JS_python_error_C=max_error,max_quadrature_error=numeric_error,
        fit_START=len(starts),fit_COMPLETE=len(completes),OOF_sessions=len(rows),
        max_constant_input_equilibrium_over_marginal_box_C=float(max(eq)),
        marginal_box_is_not_a_validated_joint_state=True,adopted=False,physical_validation=False)
    save(out/'AUDIT.json',audit_result)
    summary = result['summary']
    lines = ['# S26 장시간 부하: 열 모형 현실성 보완', '',
       '기존 모형의 장시간 고온 결과로 정책 우위를 판정하지 않는다. 원 결과와 실패는 보존했다.', '',
       '## 원인', '',
       'LONG64/CENTRAL/EDF의 저장 곡선 261.10℃ 중 POST 벽시계 proxy의 모형 기여가 219.74℃였다. 공유 CPU 대기를 포함하는 합산 체류가 발열로 외삽되는 구조다. 물리 발열의 실측 분해가 아니다. 기존에도 지수 감쇠가 있어 단순한 냉각항 누락은 아니다.', '',
       '## 별도 보완판과 실측 replay', '',
       f"전력 구동 수동 RC 응답을 구현했다. 일정 전력이면 유한한 열평형으로 수렴하고 전력이 줄면 냉각한다. 온도 clamp는 없다. {result['inventory_sessions']}세션 원장 중 공통 AP/전력 적격 {result['included_sessions']}세션을 사용하고 나머지는 사유를 보존했다. {result['fits']} fit을 등록·완료했으며 새 정책환경/RL/기기측정은0이다.", '',
       f"FULL: tau={model['tau_s']}초, G={gain:.6f}℃/API-W, delta={model['delta_C']:.6f}℃. SKIN 초기값은 대용 경계이며 실제 주변 온도로 식별하지 않았다. API 전력도 절대 물리 W 인증값이 아니다.", '',
       '|자료|세션|새 RC OOF MAE℃|원 모형 OOF MAE℃|초기 AP 유지 MAE℃|',
       '|---|---:|---:|---:|---:|']
    for s in summary:
        lines.append(f"|{s['category']}|{s['sessions']}|{s['RC_MAE_C']:.4f}|{s['parent_MAE_C']:.4f}|{s['anchor_MAE_C']:.4f}|")
    lines += ['', '이미 본 자료의 그룹 제외 개발 OOF다. 미래 실측 전력을 입력으로 주는 진단이며 배포용 미래 전력 예측 또는 독립 실기기 정확도가 아니다.', '',
       '|실측 시간 구간초|세션|새 RC MAE℃|원 모형 MAE℃|초기 AP 유지 MAE℃|', '|---|---:|---:|---:|---:|']
    for s in result['time_bins']:
        if s['sessions']:
            lines.append(f"|{s['time_bin_s'][0]}~{s['time_bin_s'][1] or '끝'}|{s['sessions']}|{s['RC_MAE_C']:.4f}|{s['parent_MAE_C']:.4f}|{s['anchor_MAE_C']:.4f}|")
    lines += ['', '## 판정', '',
       f"정확도 gate: {'PASS' if result['accuracy_gate_pass'] else 'FAIL'}. 기본 식별 gate(G>0/비경계tau): {'PASS' if result['basic_identification_gate_pass'] else 'FAIL'}. 배포/정책환경 채택 gate: **미충족, 채택하지 않음**.", '',
       f"저장 독립 JS replay {audit_result['JS_replay_points']:,}점의 Python 최대차 {max_error:.3g}℃, 별도 수치적분 최대차 {numeric_error:.3g}. 수학/계보 검산 PASS이며 실기기 검증은 아니다.", '',
       f"공통 적격 실측 AP 범위 {support['AP_C'][0]:.2f}~{support['AP_C'][1]:.2f}℃, API 전력 범위 {support['power_API_W'][0]:.4f}~{support['power_API_W'][1]:.4f}. 이 경계는 안전 임계값 또는 동시 지속 부하의 공동 지원이 아니다. 지원 밖 입력은 UNSUPPORTED이며 경계로 잘라서 계산하지 않는다.", '',
       '장시간 작업은 열평형과 기기 스로틀링을 함께 검증해야 한다. 아직 실제 CPU 서비스·대기를 분리한 전력 예측, AP/표면 센서 의미와 열 severity/클럭 변화 근거가 부족하다. 이를 임의의 온도별 감속 계수로 대신하지 않는다. 다음 정책 실험은 이 gate를 통과한 새 세대에서만 시작한다.', '',
       '공식 근거: [Android Thermal mitigation](https://source.android.com/docs/core/power/thermal-mitigation), [Thermal API](https://developer.android.com/games/optimize/adpf/thermal). 기기별 severity와 성능 완화 정책을 확인해야 하며 AP 60℃를 모든 센서의 공통 불가능 온도로 가정하지 않는다.', '',
       '## 관련 결과', '',
       '[작업량·시간 확대 전체표](../../sustained_load_v1/artifacts/G001/FINAL_REPORT_KO.md). LOW 규칙적 공급의 실제 작업시간은15.34/63.17/255.18초, EDF=ATC이며 기저 비중은60.1/32.0/17.7%다. 시간 증가만으로 새 정책의 이득이나 NPU 편중 해소를 보장하지 않는다.', '']
    with (out/'REPORT_KO.md').open('x',encoding='utf-8') as f:
        f.write('\n'.join(lines))
    verify(op)
    save(out/'FINAL_HANDOFF_PROOF.json',dict(status='THERMAL_CANDIDATE_EVALUATED_NOT_ADOPTED',operation_sha256=sha(Path(__file__).parent/'OPERATION.json'),
        artifacts={name:sha(out/name) for name in ['RESULT.json','MODEL.json','AUDIT.json','REPORT_KO.md','USE_LEDGER.json','SUSTAINED_VALIDITY.json','TAU_PROFILES.json','OOF_ROWS.json.gz']},
        new_fit=result['fits'],new_policy_environments=0,new_RL=0,physical_policy_advantage_proven=False,failed_identity_retry=False))
