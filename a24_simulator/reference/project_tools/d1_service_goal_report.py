"""Offline integration of completed studies. Never starts an environment."""
import argparse
import csv
import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/results/service_goal_20261011'
DISPLAY = {
    'Band': 'Band 판단 규칙 이식', 'Triton': 'Triton 배치 규칙 이식',
    'JointList': '공동 서비스 리스트', 'CostList': '열·에너지 비용 리스트',
    'CostV2': '기한 보호 비용 리스트 V2',
    **{f'FreshPPO{s}_64': f'리스트 보정 PPO · 초기화 {s}' for s in (11, 23, 37)},
}


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def summarize(rows, scope):
    result = []
    for role in sorted({row['policy'] for row in rows}):
        group = [row for row in rows if row['policy'] == role]
        identities = {(row['condition'], row['arrival_seed'], row['family'], row['context']) for row in group}
        if len(group) != 48 or len(identities) != 48:
            raise ValueError('requires completed 48-condition roles, no pooled repetitions')
        result.append(dict(scope=scope, policy=role, conditions=len(group),
            planned=sum(row['planned'] for row in group), completed=sum(row['completed'] for row in group),
            urgent_failure=sum(row['urgent_failure'] for row in group),
            normal_failure=sum(row['normal_failure'] for row in group),
            mean_condition_P95_ms=statistics.mean(row['urgent_p95_ms'] for row in group),
            mean_energy_J=statistics.mean(row['energy_j'] for row in group),
            mean_modeled_AP_C=statistics.mean(row['peak_ap_c'] for row in group)))
    return result


def build():
    v1 = read('docs/results/service_envelope_20261011/confirmation_comparison.json')
    # Select explicitly labelled held-out rows; development is not confirmation.
    with (ROOT / 'docs/results/service_joint_rl_20261011/comparison.csv').open(encoding='utf-8-sig', newline='') as stream:
        ppo = [row for row in csv.DictReader(stream) if row['scope'] == 'confirmation']
    for row in ppo:
        for key in ('condition', 'arrival_seed', 'planned', 'completed', 'urgent_failure', 'normal_failure'):
            row[key] = int(row[key])
        for key in ('urgent_p95_ms', 'energy_j', 'peak_ap_c'):
            row[key] = float(row[key])
    keys = lambda rows: {(row['condition'], row['arrival_seed'], row['family'], row['context']) for row in rows}
    if keys(ppo) != keys(v1):
        raise ValueError('new PPO and list confirmation inputs differ')
    v2 = read('docs/results/service_envelope_v2_20261011/confirmation_comparison.json')
    if {row['arrival_seed'] for row in v1} & {row['arrival_seed'] for row in v2}:
        raise ValueError('V2 confirmation must use separate arrivals')
    summaries = summarize(v1 + ppo, '833 공동 확인') + summarize(v2, '835 별도 확인')
    consumes = dict(
        list_v1=read('docs/results/service_envelope_20261011/consumption.json'),
        ppo_v1=read('docs/results/service_joint_rl_20261011/result.json')['consumption'],
        list_v2=read('docs/results/service_envelope_v2_20261011/consumption.json'))
    native = sum(value['native_starts'] for value in consumes.values())
    learning = sum(value.get('learning_starts', value.get('new_learning', 0)) for value in consumes.values())
    if (native, learning) != (919, 192):
        raise ValueError('completed task consumption changed; do not silently replace totals')
    smoke_path = ROOT / 'docs/results/desktop_handoff_20261011/functional_smoke.json'
    smoke = json.loads(smoke_path.read_text(encoding='utf-8')) if smoke_path.exists() else None
    smoke_native = smoke['new_native'] if smoke else 0
    if smoke and (smoke_native != 3 or smoke['new_learning'] != 0 or smoke['completed'] != smoke['planned']):
        raise ValueError('functional handoff smoke contract changed')
    data = dict(status='completed_PC_comparison_goal_not_proven', conditions=summaries,
        comparison_native=native, handoff_smoke_native=smoke_native,
        new_native=native + smoke_native, new_learning=learning, lineage_native=13813 + native + smoke_native,
        lineage_learning=2989 + learning, new_device_inferences=0, new_installations=0,
        readiness_readonly_adb=8, automatic_adoption=False, experiment_ready=False,
        original_gate_changed=False, ppo_seed_scope='three initialization seeds; one shared round-robin session RNG',
        consumption=consumes, model_claim='A24 CPU/GPU modeled AP and conditional energy; not surface temperature or product superiority')
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (DEST / 'comparison.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader(); writer.writerows(summaries)
    table = ''.join('<tr>' + ''.join('<td>' + html.escape(DISPLAY.get(row[key], row[key]) if key == 'policy'
        else str(row[key]) if key in ('scope', 'normal_failure') else f'{row[key]:.6f}') + '</td>' for key in ('scope', 'policy', 'normal_failure',
        'mean_condition_P95_ms', 'mean_energy_J', 'mean_modeled_AP_C')) + '</tr>' for row in summaries)
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>최신 방법론 검증과 데스크톱 이관</title><style>
body{margin:32px auto;max-width:1180px;padding:0 20px;background:#f6f8fb;color:#173247;font:18px "Malgun Gothic",sans-serif;line-height:1.65}
section{background:white;padding:24px;margin:24px 0;border:1px solid #dce3eb;border-radius:10px}h1{font-size:32px;line-height:1.3}h2{font-size:25px}.warn{background:#fff1d2}table{border-collapse:collapse;width:100%;font-size:15px}td,th{padding:10px;text-align:left;border-bottom:1px solid #dce3eb}a{color:#075ab0}.scroll{overflow-x:auto}li{margin:8px 0}
</style><h1>서비스를 지키면서 비용을 줄였는가?</h1>
<section class="warn"><b>현재 답: 전체 평가 조건에서는 아직 입증하지 못했다.</b><p>새 리스트와 실제 PPO 학습·평가를 마쳤다. 과도한 예측 제한을 줄인 V2는 평균 AP/J를 낮췄지만 일반 기한 위반과 긴급 P95가 악화했다. 원 판정을 유지하고 정책을 자동 채택하지 않았다.</p></section>
<section><h2>최신 비교</h2><div class="scroll"><table><tr><th>자료</th><th>정책</th><th>일반 기한 위반</th><th>조건별 P95 평균 ms</th><th>평균 J</th><th>평균 모형 AP °C</th></tr>''' + table + '''</table></div>
<p>각 역할 3168/3168 완료·긴급 실패 0이다. 833과 835는 서로 다른 도착 자료이므로 차이를 전후 개선으로 합치지 않는다. 48조건은 4도착 seed×4부하×3모형 문맥이며 48독립 실측이 아니다. Band/Triton은 제한적으로 옮긴 규칙 비교군이며 실제 외부 제품을 실행한 결과가 아니다.</p></section>
<section><h2>무엇을 고쳤는가</h2><ol><li>물리적으로 가능한 CPU/GPU 병행과 예측 기반 성능 제한을 분리했다.</li><li>자체 공동 리스트를 기본·복귀·예측 후속·학습 참조로 고정했다. Band는 비교군이다.</li><li>새 PPO의 미완료·기한 실패를 절대 건수로 반영했다. 각 초기화 seed 64에피소드/8update/Adam96이며 공유 session RNG를 쓰는 세 모델이다.</li><li>비용 개선 예측 후보 866개 중 273개가 개별 일반 응답 불변 조건 하나로 막힌 반례를 찾았다. V2에서 그 항을 기존 기한·실패·지각 보호로 바꾸고 P95 순위를 앞에 놓았다.</li></ol><p>현재 큐 예측이 좋아도 미도착 요청의 전체 서비스는 보장하지 않는다. 다음 단계의 핵심은 더 많은 학습만이 아니라 이 예측과 전체 요청 흐름의 차이를 줄이는 것이다.</p></section>
<section><h2>데스크톱에서 계속할 수 있는가</h2><p>가능하다. Python과 NumPy/PyTorch, 동결 모형·입력·정책 코드로 CPU에서 실행한다. Android·ADB·APK·TFLite는 시뮬레이션에 필요하지 않다. 같은학습을 이어가려면 actor/critic/Adam/승수와 세모델의공유RNG·실행순서를 함께 보존해야 한다. 종료run을 다시 실행해 예산을 초기화하지 않고 새task/상한으로 등록한다.</p><p><a href="../desktop_handoff_20261011/README.md">데스크톱 실행·재개 안내</a> · <a href="../../SERVICE_ENVELOPE_PILOT_20261011.md">실행 계약</a></p></section>
<section><h2>현재 근거의 한계</h2><p>모형 AP는 최고 표면 온도가 아니다. J는 기기 전류 해석을 전제로 한 실측 기반 모형이며 교정된 자원별 rail 전력 측정이 아니다. 냉각에 따른 처리속도 회복과 실제 온라인 후보/actor 비용은 미지원이다. 미세 모형 차이를 실제 절감으로 확정하지 않는다.</p><p>새 대표96 요청의 Band/Joint/Cost 일정이 같아 중복 실측0이었다. 오전 AP25.5°C는 개발 초기 관측 최저25.9°C보다 낮았다. 새로운 다른 유망 일정과 실행 게이트 없이 기기를 반복하지 않았다.</p></section>
<section><h2>근거를 열어보기</h2><ul><li><a href="../service_envelope_20261011/README.md">공동 리스트 V1과 차단 원인</a></li><li><a href="../service_joint_rl_20261011/README.md">새 PPO64·실제학습·복원 검증</a></li><li><a href="../service_envelope_v2_20261011/README.md">과제약 보완 V2·새 확인48</a></li><li><a href="../morning_device_readiness_20261011/README.md">오전 A24 상태·중복 실측 보류</a></li><li><a href="../overnight_meeting_20261011/README.md">이전 회의19장과 실제 ABBA4 근거</a></li><li><a href="summary.json">통합 요약 JSON</a> · <a href="comparison.csv">정책 비교 CSV</a></li></ul></section></html>
'''
    (DEST / 'index.html').write_text(page, encoding='utf-8')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    data = build()
    print(json.dumps({key: data[key] for key in ('status', 'new_native', 'new_learning', 'automatic_adoption')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
