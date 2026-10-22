"""Read-only result derivation followed by new human-readable reports."""
from study import H, O, read, MODES


NAMES = {'FIFO_DYN':'FIFO+동적배정', 'EDF_DYN':'EDF+동적배정', 'RR_DYN':'요청군RR+동적배정',
         'LSF_DYN':'기본 LSF', 'BAND_LSF_ALL':'Band-LSF 적용·전량처리',
         'BAND_LSF_DROP':'Band-LSF 적용·포기허용', 'IDLE_BC':'우리 정책'}


def fmt(value, digits=3):
    return '미정' if value is None else f'{value:.{digits}f}'


def table(groups):
    text = '|부하|정책|예측소비 J*|평균AP ℃|전체정시|긴급정시|응답/도착|포기|긴급P95 초|\n'
    text += '|---:|---|---:|---:|---|---|---|---:|---:|\n'
    for g in groups:
        if g['failed']:
            text += f"|{g['load']}|{NAMES[g['policy']]}|미정|미정|미정|미정|미정|미정|실행FAIL {g['failed']}|\n"
            continue
        a, u = g['service']['ALL'], g['service']['U']
        text += (f"|{g['load']}|{NAMES[g['policy']]}|{fmt(g['common_J'])}|{fmt(g['AP'])}|"
                 f"{a['on']}/{a['n']} ({100*a['on']/a['n']:.2f}%)|{u['on']}/{u['n']} ({100*u['on']/u['n']:.2f}%)|"
                 f"{a['responded']}/{a['n']}|{g['dropped']}|{fmt(u['mean_session_P95_s'])}|\n")
    return text


def main():
    assert not (O / 'REPORT_KO.md').exists() and not (O / 'INTERPRETATION_KO.md').exists()
    assert read(O / 'AUDIT.json')['status'] == 'PASS'
    summary = read(O / 'SUMMARY.json'); rows = read(O / 'DERIVED.json')
    intro = '''# 기본 LSF와 Band-LSF 적용판 비교

**Band 전체 런타임의 재현 결과가 아니다.** Band 공개 LSF의 worker 대기 고려·busy 최적경로 건너뛰기·예측상 SLO 위반 포기를 현재 A24 요청 단위에 적용했다. 원본의 모델 분할, tensor 전송, 일괄 worker enqueue와 Android 실행은 재현하지 않았다. 기본 LSF, 포기를 끈 Band-LSF 적용판, 포기 허용 적용판을 모두 결과 전에 고정했다.

부하0.4/0.8/1.2, 공급600초, 두 패턴, 가상CPU3/GPU1·ORIGINAL 모형이다. 새18평가만 실행하고 기존24세션은 원자료를 재사용했다. 입력·latent·명목·물리·우리정책 체크포인트는 고정했다. 새학습/NN실행/BCfit/PPO/물리fit/실기기0이다.

소비·AP·P95는 두 패턴의 세션 평균이고 서비스 건수는 합계다. 모든 도착이 정시율 분모에 들어가며 포기는 미응답/실패로 센다. P95는 응답한 요청에 대한 조건부 통계이므로 포기 수와 함께 읽어야 한다. J*는 미교정 모형의 예측 소비다.

주 소비창은 각 입력의7정책이 모든 요청을 실제 반환 또는 명시적 포기로 종결한 시각의 최댓값까지다. 포기 외 미완료가 있으면 공통drain을 쓴다. 동일창으로 기존24세션도 재적분하므로 과거 표의 소비를 그대로 복사하지 않는다. 공급600초 고정창 소비, 전량실행 자체완료 비용과 포기를 포함한 종결 비용은 별도로 보존한다.

'''
    selected = [g for g in summary['groups'] if g['policy'] in (*MODES, 'IDLE_BC')]
    interpretation = intro + table(selected)
    interpretation += '\n## 우리 정책과의 차이\n\n양수 절감은 우리 정책이 덜 소비한다는 뜻이다. 정시율 차는 우리 정책−기준선, P95 차가 양수면 우리 정책이 더 느리다. 포기 허용 정책의 소비/P95 차이는 응답 수 차이와 함께 평가한다.\n\n'
    interpretation += '|부하|기준선|우리정책 소비절감 %|전체정시 차 %p|긴급정시 차 %p|긴급P95 차 초|\n|---:|---|---:|---:|---:|---:|\n'
    for c in summary['IDLE_BC_comparisons']:
        if c['baseline'] not in MODES:
            continue
        interpretation += f"|{c['load']}|{NAMES[c['baseline']]}|{fmt(c.get('saving_pct'))}|{fmt(c.get('ALL_ontime_percentage_point_delta'))}|{fmt(c.get('U_ontime_percentage_point_delta'))}|{fmt(c.get('U_P95_delta_s'))}|\n"
    interpretation += '\n## 포기·실행·소비 효율의 구분\n\n단위당 소비는 두 패턴의 소비 합계를 해당 건수 합계로 나눴다. 포기한 만큼 소비가 작아지는 효과를 전체 서비스 성공과 구분한다. 전량완료 자체꼬리 비용은 포기가 있으면 미정이다.\n\n'
    interpretation += '|부하|정책|포기 전체/긴급|미응답|실행미완료·포기제외|공급창 J*|응답1건당 J*|정시1건당 J*|최대큐|최적경로대기 호출|\n|---:|---|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for g in selected:
        if g['failed']:
            continue
        interpretation += (f"|{g['load']}|{NAMES[g['policy']]}|{g['dropped']}/{g['service']['U']['dropped']}|"
                           f"{g['service']['ALL']['missing']}|{g['unfinished_non_dropped']}|{fmt(g['supply_J'])}|"
                           f"{fmt(g['common_J_per_response'],4)}|{fmt(g['common_J_per_ontime'],4)}|{g['supply_peak_ready']}|{g['plan_wait_calls']}|\n")
    interpretation += '''
## 実装 범위와 근거

기본 LSF는 현재 가용 장치의 예측 응답으로 slack을 정하고, Band-LSF 적용판은 현재 점유자의 예상 반환까지 포함한 가장 빠른 계획으로 slack을 정한다. 계획이 busy면 뒤의 요청을 검사하며 빈 장치가 있어도 기다릴 수 있다. 포기허용판은 예측상 slack<0이면 포기한다. tie와 프로파일·물리 인터페이스는 A24에 맞게 정했다. 이 차이와 서브그래프/worker queue 생략을 Band 원형의 완전 재현이라고 부르지 않는다.

[사전 설계](../../experiments/a24_lsf_band_20261020/PROTOCOL.md) · [원문/적용 차이와 해시](../../experiments/a24_lsf_band_20261020/SOURCE_MANIFEST.json) · [전체42행](REPORT_KO.md) · [정밀 요약](SUMMARY.json) · [독립검산](AUDIT.json) · [정책/경로대기 재생](REPLAY.json). 새NN이 없으며 우리정책의 기존 신경망 검산은 [이전 증거](../A24_QUEUE_PRESSURE_20261020_01/NN_AUDIT.json)를 보존했다. 모든 손해와 포기를 보고하며 더 낮은 성능의 기준선만 선정하지 않는다.
'''.replace('実装', '구현')
    (O / 'INTERPRETATION_KO.md').write_text(interpretation, encoding='utf-8')
    full = intro + table(summary['groups']) + '\n## 패턴별42행\n\n'
    full += '|부하|패턴|정책|공통창 초|소비 J*|AP ℃|전체정시|긴급정시|응답|포기|실행미완료·포기제외|긴급P95 초|최대큐|자료|\n|---:|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|\n'
    for r in rows:
        if r.get('failed'):
            full += f"|{r['load']}|{r['pattern']}|{r['policy']}|미정|미정|미정|미정|미정|미정|미정|미정|미정|미정|FAIL/부분자료 보존|\n"
            continue
        a,u=r['service']['ALL'],r['service']['U']
        full += (f"|{r['load']}|{r['pattern']}|{r['policy']}|{fmt(r['common_end_ns']/1e9-35)}|{fmt(r['common']['J'])}|{fmt(r['common']['AP'])}|"
                 f"{a['on']}/{a['n']}|{u['on']}/{u['n']}|{a['responded']}|{r['dropped']}|{r['unfinished_non_dropped']}|"
                 f"{fmt(u['P95'])}|{r['queueStats']['supply_peak_ready']}|{'저장재사용' if r['reused'] else '새평가'}|\n")
    full += '\n[해석·포기·우리정책 대비](INTERPRETATION_KO.md) · [전체 서비스/일반정시/평균·pooled P95/공급창/꼬리/큐/경로](DERIVED.json) · [요약](SUMMARY.json) · [독립감사](AUDIT.json). 최고AP는 공통 trace 끝점 정의다. 포기의 미응답을 숨기지 않으며 모든 도착을 포함한다.\n'
    (O / 'REPORT_KO.md').write_text(full, encoding='utf-8')
    (O / 'CONTINUE_RUNNING.md').write_text('# 재개 안내\n\n기본LSF/Band-LSF 요청단위 적용18평가와 기존24세션의42행 비교를 종료했다. 완료/실패 실험을 재시작하지 않는다. INTERPRETATION_KO.md→REPORT_KO.md→SUMMARY.json→AUDIT.json/REPLAY.json→FINAL_HANDOFF_PROOF.json을 읽는다. Band 전체 native runtime/모델분할/Android 성능 재현이 아니다. 새학습/NN/fit/실기기0, 현재18단위·도출137759·자동추가/재시도0이다. 로컬미커밋/미게시이며 추가 실험은 후속지시를 따른다.\n',encoding='utf-8')
    print('LSF_BAND_REPORT_COMPLETE', len(rows), 'rows; explicit drop denominator and adaptation limits')


if __name__ == '__main__':
    main()
