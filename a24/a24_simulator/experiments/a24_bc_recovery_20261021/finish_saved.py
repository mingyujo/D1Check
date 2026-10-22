"""Saved arithmetic and Korean reporting only. No simulator, Torch or training."""
import json
from pathlib import Path

H = Path(__file__).resolve().parent
R = H.parents[2]
O = R / 'a24_simulator/results/A24_BC_RECOVERY_20261021_01'


def read(name):
    return json.loads((O / name).read_text(encoding='utf8'))


def write(name, value):
    with (O / name).open('x', encoding='utf8', newline='\n') as f:
        f.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    a = read('ACCOUNTING.json')
    d = read('TRAIN_DIAGNOSTICS.json')
    r = read('RESULT.json')
    assert len(a['rows']) == 36 and len(a['aggregates']) == 18
    assert r['science_START'] == 19 and len(r['rows']) == 18
    assert all(x['status'] == 'COMPLETE' for x in r['rows'])
    assert all(x['service']['ALL']['missing'] == x['service']['ALL']['incomplete'] == 0 for x in a['rows'])
    names = {'FIFO_DYN': 'FIFO', 'EDF_DYN': 'EDF', 'RR_DYN': 'RR', 'BC_OLD': '기존 BC+필터', 'TEACHER': '교사 직접+필터', 'BC_RECOVERED': '보완 BC+필터'}
    order = list(names)
    rows = sorted(a['rows'], key=lambda x: (x['load'], x['pattern'], order.index(x['policy'])))
    rate = lambda s: 100 * s['on'] / s['n']
    out = ['# 기존 A24 BC 보완: 패턴별 전체 36행', '',
           '소비J*·평균 AP·최고 AP는 같은 case의 여섯 정책에 동일한 종료 시각을 적용했다. 정시율 분모는 전체 도착이며 P95는 예정 도착부터 응답까지의 완료 표본에서 nearest-rank로 계산한다. 모든 행 미응답/미완료는 0/0이다. 패턴0은 staggered_wave, 패턴1은 clustered_recovery다. 정책은 동일 CPU3/GPU1 가상 자원을 사용한다.', '',
           '|부하|패턴|정책|소비J*|평균 AP℃|최고 AP℃|전체 정시/도착|긴급 정시/도착|일반 정시/도착|전체P95 s|긴급P95 s|일반P95 s|최대큐|',
           '|---:|---:|---|---:|---:|---:|---|---|---|---:|---:|---:|---:|']
    for x in rows:
        s = x['service']; c = x['common']
        out.append(f"|{x['load']}|{x['pattern']}|{names[x['policy']]}|{c['J']:.6f}|{c['AP']:.6f}|{c['peak']:.6f}|{s['ALL']['on']}/{s['ALL']['n']}|{s['U']['on']}/{s['U']['n']}|{s['N']['on']}/{s['N']['n']}|{s['ALL']['P95']:.6f}|{s['U']['P95']:.6f}|{s['N']['P95']:.6f}|{x['max_queue']}|")
    out += ['', '## 대기량·장치 배분·공통 창', '',
            'WAIT는 정책이 선택한 대기시간 합계이며 모든 요청의 큐 대기시간 합계와 다르다. CPU/GPU는 요청 배정 수다. 공급 창 값은 각 행의 ACCOUNTING.json/supply에 별도로 보존했다.', '',
            '|부하|패턴|정책|WAIT 합계 s|CPU/GPU 건수|정책 호출|공통 종료 s|기존 완료 재사용|',
            '|---:|---:|---|---:|---|---:|---:|---|']
    for x in rows:
        out.append(f"|{x['load']}|{x['pattern']}|{names[x['policy']]}|{x['wait_s']:.6f}|{x['route_counts']['CPU']}/{x['route_counts']['GPU']}|{x['calls']}|{x['common_end_ns']/1e9:.9f}|{'예' if x['reused'] else '아니오'}|")
    out += ['', '[집계표](REPORT_KO.md) · [해석/모든 손해](INTERPRETATION_KO.md) · [정밀값·응답표본·별도 공급창](ACCOUNTING.json)', '']
    write('ALL_ROWS_KO.md', '\n'.join(out))

    by = {(x['load'], x['pattern'], x['policy']): x for x in rows}
    comparisons = []
    for load in (.4, .8, 1.2):
        for pattern in (0, 1):
            x = by[load, pattern, 'BC_RECOVERED']
            for ref in order[:-1]:
                y = by[load, pattern, ref]
                q = dict(load=load, pattern=pattern, reference=ref,
                         energy_saving_J=y['common']['J']-x['common']['J'],
                         energy_saving_percent=100*(1-x['common']['J']/y['common']['J']),
                         AP_change_C=x['common']['AP']-y['common']['AP'],
                         peak_change_C=x['common']['peak']-y['common']['peak'],
                         max_queue_change=x['max_queue']-y['max_queue'])
                for group in ('ALL', 'U', 'N'):
                    q[group+'_on_count_change'] = x['service'][group]['on']-y['service'][group]['on']
                    q[group+'_on_change_pp'] = rate(x['service'][group])-rate(y['service'][group])
                    q[group+'_P95_change_s'] = x['service'][group]['P95']-y['service'][group]['P95']
                q['losses'] = [k for k,v in q.items() if isinstance(v,(int,float)) and ((k.startswith('energy_saving') and v < -1e-9) or (k.endswith('_change_pp') and v < -1e-9) or (k.endswith('_on_count_change') and v < 0) or (k.endswith('_change_s') and v > 1e-9) or (k in ('AP_change_C','peak_change_C','max_queue_change') and v > 1e-9))]
                comparisons.append(q)
    mixing = []
    for policy in ('BC_OLD', 'TEACHER', 'BC_RECOVERED'):
        ag = next(x for x in a['aggregates'] if x['load']==.4 and x['policy']==policy)
        ps = [by[.4, p, policy]['service']['U']['P95'] for p in (0,1)]
        mixing.append(dict(policy=policy, pattern_U_P95_s=ps, mean_pattern_U_P95_s=sum(ps)/2, pooled_U_P95_s=ag['service']['U']['P95']))
    write('FINDINGS.json', dict(status='PASS', source='ACCOUNTING.json; saved arithmetic only', comparisons=comparisons, aggregate_deltas=a['deltas'], low_load_P95_definitions=mixing, TRAIN_diagnostics='TRAIN_DIAGNOSTICS.json', new_environment=0, new_fit=0))

    interpretation = '''# 기존 A24 BC 보완 결과 해석

보완 BC는 기존 BC보다 세 부하 모두 평균 예측 소비가 낮고, 부하 0.8·1.2에서는 전체·긴급 정시율도 높았다. 교사 직접 실행과 비교하면 조건에 따라 결과가 갈렸다. BC를 교사보다 항상 좋은 정책으로 판단할 근거는 없다. 여기서 기존 BC는 이번 비교에 사전 지정한 50특징 IDLE_BC+동일 WAIT 필터이며, 과거 모든 체크포인트 중 최선이라는 뜻은 아니다.

## 보완 내용과 학습 확인

기존 엔진·물리계수·CPU3/GPU1·ATC 후보·롤링 예측·교사 비용·50특징/36후보망은 유지했다. 원 TRAIN 1,320개를 현재 WAIT 필터 문맥으로 다시 인코딩한 결과 후보 mask 28개가 바뀌었고, 대표 교사 정답과 호환 목표는 바뀌지 않았다. 필터 차이가 기존 BC 성능 부족의 단독 원인이었다고 해석하지 않는다.

기존 동결 BC의 새 TRAIN 6개 실행에서 방문 상태에 같은 순간의 최소비용 교사 라벨을 붙였다. 기존 TRAIN 은행에서 별도 도착 지터로 만들고 부하0.8/1.2는 가상42℃로 시작했다. 원 자료를 유지한 최종 6,145개로 기존망을 warm start해 고정256epoch/새 Adam6,400회 갱신했다. 보완망 자신의 방문 상태를 반복 수집한 DAgger는 아니다. 데이터·학습량·LR을 함께 바꿨으므로 어느 한 요소의 독립 효과를 분해한 실험도 아니다.

|같은 자료에서 비교|기존망 정답 호환|보완망 정답 호환|
|---|---:|---:|
|원 TRAIN1,320개, 원/현재 필터 모두|1,066/1,320 = 80.76%|1,188/1,320 = 90.00%|
|보완 TRAIN6,145개|3,487/6,145 = 56.75%|5,159/6,145 = 83.95%|

두 행은 서로 다른 분모다. TRAIN 일치율은 일반화 성능이 아니다. 사전 조기종료 기준99.5%/각군99%/loss≤.05에 도달하지 못하고256epoch 상한에서 종료했다. 보완망 WAIT군 일치율도59.59%로 남았다. 실제 선택 TRAIN의 최고 온도41.995℃로 고온 범위는 늘었지만 최대큐14에 비해 보완 BC 평가 최대큐35여서 적체 상태 외삽은 남는다. EVAL 상태·교사 정답으로 학습하거나 EVAL 성적에 따라 epoch·seed·망을 재선정하지 않았다.

## 기존 BC 대비 효과와 손해

|부하|소비J* 기존→보완|절감J* / %|전체 정시% 기존→보완|긴급 정시% 기존→보완|긴급 pooled P95 변화s|
|---:|---:|---:|---:|---:|---:|
|0.4|999.347→996.705|2.642 / 0.264%|100→100|100→100|+0.028|
|0.8|1191.311→1181.976|9.335 / 0.784%|96.54→98.31|89.89→95.91|−0.071|
|1.2|1438.548→1414.943|23.605 / 1.641%|78.91→81.94|72.58→81.59|−0.155|

소비/AP는 두 패턴의 평균, 정시율은 도착 건수 합산, pooled P95는 두 패턴의 응답표본을 합쳐 다시 계산한 nearest-rank 백분위다. J*는 미교정 예측 소비이며 표의 절감J*는 두 패턴별 절감량의 평균이다. 두 실행을 합친 총 절감이나 실기기 배터리 절감을 뜻하지 않는다.

부하0.4의 긴급 pooled P95는 기존1.227120초→보완1.254679초로27.559ms 증가했다. 패턴0 P95는1.102129→0.945330초, 패턴1은1.332786→1.292458초로 둘 다 감소했다. 이는 모순이 아니다. 개별 패턴의95번째 백분위가 각각 개선돼도 합친 분포의95번째 백분위가 개선된다는 보장은 없다. 패턴 P95 산술평균은1.217458→1.118894초다. 이전 보고서의 세션 P95 평균과 이번 pooled P95를 섞어 비교하지 않는다.

부하0.8 패턴0에서는 긴급 P95가1.870424→2.046731초로0.176307초 늘었다. 같은 패턴의 긴급 정시 건수는349→381건으로 증가했다. 부하1.2 패턴1의 최대큐는33→35, 최고 AP는41.502503→41.507008℃로 소폭 증가했다. 같은 패턴의 소비·평균 AP·전체/긴급 정시·긴급 P95는 개선됐지만 모든 지표가 개선된 것은 아니다.

## 교사 직접 실행과 비교

부하0.4에서 보완 BC는 교사보다 평균0.388J*(0.039%) 낮고 pooled 긴급 P95도0.038초 짧았다. 부하0.8에서는 보완 BC가 교사보다1.240J*(0.105%) 더 쓰고 전체 정시율이0.145%p 낮았다. 긴급 정시율은0.114%p 높고 긴급 P95는0.036초 짧았다. 이 차이로 중간 부하에서 BC의 일관된 우위를 주장할 수 없다.

부하1.2 집계에서는 보완 BC가 교사보다2.296J*(0.162%) 낮고 전체/긴급 정시율이0.581/0.455%p 높았다. 그러나 두 패턴의 효과가 다르다.

|부하1.2 패턴|긴급 정시 교사→보완|소비J* 교사→보완|긴급P95 s 교사→보완|
|---:|---:|---:|---:|
|0|514/600→560/600|1310.677→1303.298|2.180179→2.176144|
|1|557/720→517/720|1523.801→1526.589|2.514080→2.534882|

밀집 패턴1에서는 교사보다 긴급 정시40건, 5.556%p가 줄었다. 교사의 큰 최대큐92와 보완 BC의35는 이 긴급 서비스 손해를 없애지 않는다. 부하0.4 패턴1 최고 AP와 부하0.8 패턴별 소비/전체 정시/P95 등 나머지 손해도 전체36행과 FINDINGS.json에 보존했다.

BC가 교사와 다른 최종 성과를 내는 것은 현재 상태의 명목 롤링 비용 최소화와 전체 실행 결과가 같지 않기 때문이다. BC의 불완전한 모방·호환 대안 선택은 이후 방문 상태도 바꾼다. 교사 롤링 내부의 EDF 후속 가정과 실제 교사/BC 반복 재호출의 차이는 유지했으며 이번 보완이 그 예측 가정을 바꾼 것은 아니다. 이번 작은 이득을 BC가 장기 보상을 직접 최적화했다거나 교사보다 본질적으로 우수하다는 증거로 해석하지 않는다. RL/PPO 학습은 수행하지 않았다. BC도 매번 모든 후보의 롤링 특징을 계산하므로 계산비용 절감은 입증하지 못했다.

## 비교 범위·검증·결론

FIFO·EDF·RR·기존 BC 24개 완료 세션은 재실행하지 않고 새 교사/보완 BC12개와 같은 case별 공통 완료 창에서 재집계했다. 따라서 이전 고부하 보고서와 소비 수치가 달라질 수 있다. 모든36행 미응답/미완료0이며 지각 요청도 분모에 남긴다. 기준선 포함 절대표는 REPORT_KO.md, 패턴별 서비스·경로·큐·대기는 ALL_ROWS_KO.md다.

TRAIN6·BC1fit·EVAL12=19 START 모두 COMPLETE, FAIL/SKIP0이다. JS3,342,776검사, 독립 물리795,448검사, TRAIN출처8,519상태 결합과 보완 BC24,362개 Torch/별도NumPy 선택 검산을 통과했다. Float64 최대 argmax regret0, 원 가중치·기존 결과와 평가 전후 전체 checkpoint/optimizer/RNG 불변을 확인했다. 검산은 구현·집계의 일관성을 확인하며 모형의 실기기 정확도를 새로 보장하지 않는다.

이는 이미 성적을 본 benchmark의 보완 비교이며 새 독립 확인 실험이 아니다. 두 주기 반복 패턴·공유 실측/명목/물리fit·가상 CPU3·D_GPU 파생값·미교정 전력·제어기 시간/전력 미가산의 한계는 유지한다. 보완 BC는 기존 BC보다 나아졌지만 교사 대비 이득이 작고 서비스 상충이 남아 자동 채택하지 않는다. 산업공학 방법론 적용 효과와 BC 근사의 추가 효과를 분리해 보고하며 기존 정책·망·결과를 보존한다. 후속 설계·추가 실험은 이번 실행에 포함하지 않는다.

[전체 집계](REPORT_KO.md) · [패턴36행](ALL_ROWS_KO.md) · [모든 차이](FINDINGS.json) · [TRAIN진단](TRAIN_DIAGNOSTICS.json) · [재개](CONTINUE_RUNNING.md)
'''
    write('INTERPRETATION_KO.md', interpretation)
    write('CONTINUE_RUNNING.md', '''# 기존 A24 BC 보완 완료·재개 안내

상태: 과학실행/독립 검산/결과 보고 완료. 대상은 기존 A24 ORIGINAL/CPU3·GPU1/beta.25/50특징 IDLE_BC이며 공통코어 또는 S26 결과와 구분한다.

TRAIN6·BC1fit·EVAL12=19 START/COMPLETE19, FAIL/SKIP0. 기존24세션 저장재사용, 비교36행이다. 보완망 network SHA-256은 `cec00807e6729c4f59bbb74723749eeb2db722786c55a7d754b1253477eb6ad7`이며 BC.RECOVERED.pt.gz에 보존했다. 압축파일 SHA는 RESULT.json의 fit/checkpoint를 따른다. 기존779d3d3b망과 모든 원 결과는 그대로다.

순수3712/입력14035·JS3342776·독립물리795448·Torch/별도NumPy24362선택 PASS, 실제 TRAIN6145·256epoch·새 Adam6400갱신을 저장 검증했다. 학습 상한에서 종료했고 충분 모방/일반화는 미입증이다. 신규 실측/PPO/물리fit/원identity 재시작/정책채택/게시0이다.

`study.py --run`, `--prepare`, 학습기나 환경을 다시 호출하지 않는다. 완료된 감사/보고 생성도 반복할 필요가 없다. 추가 작업은 보고서 해석과 변경 diff 검토이며 추가 과학실행은 별도 범위에서 결정한다. 공유 자원 때문에 기다렸던 공통판은 사용자의 “공통판 완료를 기다린 뒤 BC 진행”에 따라 실행 종료 후 잠금을 넘겨받았고 중단하지 않았다. 공통판의 결과/파일은 이 작업의 보완 대상이 아니다.

로컬19단위/도출누적137886은 로컬 예약 합산이며 전호스트 census나 사용자의 직접 숫자발언이 아니다. 기준HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf, 브랜치 codex/a24-simulator-handoff-20261016, 로컬 미커밋/미게시다. 시간 필드는 UTC, 프로젝트 작업일은2026-10-21 KST다.

[판정/손해](INTERPRETATION_KO.md) · [집계](REPORT_KO.md) · [전체36행](ALL_ROWS_KO.md) · [실행 전량](RESULT.json) · [학습진단](TRAIN_DIAGNOSTICS.json) · [JS감사](AUDIT_JS.json) · [학습/NN감사](AUDIT_PY.json) · [봉인](FINAL_PROOF.json) · [최종 불변/링크 확인](FINAL_RECHECK.json)
''')
    report_path = O / 'REPORT_KO.md'
    with report_path.open('a', encoding='utf8', newline='\n') as f:
        f.write('\n## 추가 판정과 패턴별 근거\n\n')
        f.write('원 TRAIN1,320개에서 같은 분모의 모방 일치율은80.76%→90.00%다. 보완 TRAIN6,145개에서56.75%→83.95%이며 두 분모를 혼합하지 않는다. 사전 충분모방 기준은 미달이고 실제 선택 TRAIN 최대큐14 대비 보완 평가35로 적체 외삽이 남는다.\n\n')
        f.write('기존 BC 대비 소비 감소는 전 부하에서 확인됐다. 다만 부하0.4 pooled 긴급P95+0.028초, 부하0.8 패턴0 긴급P95+0.176초와 부하1.2 패턴1 최대큐/최고온도 소폭 증가가 있다. 교사 대비 부하0.8 소비·전체정시 손해, 부하1.2 밀집 패턴1 긴급정시40건 감소를 포함한다. 패턴별P95가 둘 다 개선된 부하0.4에서도 pooled P95는 증가하므로 두 집계 정의를 구분한다.\n\n')
        f.write('[해석·모든 손해·BC 필요성 판정](INTERPRETATION_KO.md) · [패턴별 전체36행·대기·큐·경로](ALL_ROWS_KO.md) · [정밀 차이/백분위 정의](FINDINGS.json) · [같은 TRAIN 분모 진단](TRAIN_DIAGNOSTICS.json) · [완료/재개 안내](CONTINUE_RUNNING.md)\n')
    print(json.dumps(dict(status='PASS', rows=len(rows), per_pattern_comparisons=len(comparisons), new_environment=0, new_fit=0)))


if __name__ == '__main__':
    main()
