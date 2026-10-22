"""Record the completed, audited saved-only comparison; no experiments."""
from study import H,O,R,read

def first_section(path, section):
    p=R/path;t=p.read_text(encoding='utf-8');assert t.startswith('## 2026-10-20') and 'LSF' in t.splitlines()[0]
    nxt=t.index('\n## ',1);p.write_text(section.rstrip()+'\n\n'+t[nxt+1:],encoding='utf-8')

def main():
    assert read(O/'AUDIT.json')['status']=='PASS' and read(O/'RESULT.json')['COMPLETE']==18
    first_section('docs/PROJECT_STATUS.md','''## 2026-10-20 A24-LSF-BAND-01 · 18평가/42행 비교 완료

기본LSF와Band-LSF 요청단위 적용판(전량처리/포기허용)·부하0.4/0.8/1.2·600초·두패턴 새18 START/COMPLETE·FAIL0, 기존24세션 저장재사용이다. 부하1.2 전량처리에서 우리정책은 기본LSF/Band적용 대비 소비0.838/1.177% 감소·전체정시78.91% 대54.75/51.47%·긴급P952.600초 대6.037/6.879초다. 포기허용Band적용판은307/5160건(긴급235)을 포기하면서도 전체도착 기준정시92.85%·긴급78.11%, 소비1392.021J*로우리1436.708J*보다3.110%낮았다. 우리전5160응답 대해당4853응답 차이를 명시하고 포기/중간부하 손해를 보존했다. 23순수검사/Node합성589검사·818pins·저장30960선택/12677경로대기재생·독립12385977검사/최대오차약1e-9 PASS다. [판정/모든상충](../a24_simulator/results/A24_LSF_BAND_20261020_01/INTERPRETATION_KO.md) · [전체42행](../a24_simulator/results/A24_LSF_BAND_20261020_01/REPORT_KO.md) · [차이/포기ID참고](../a24_simulator/results/A24_LSF_BAND_20261020_01/FINDINGS.json) · [재개](../a24_simulator/results/A24_LSF_BAND_20261020_01/CONTINUE_RUNNING.md). Band전체 native/framework/모델분할 재현이 아니며 새학습/NN/fit/기기0·현재18단위/도출137759·자동추가/재시도0이다. 방법론9.6반영·기준HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf+로컬미커밋/미게시·장애없음, 다음은결과해석/공유·diff검토다.''')
    p=R/'docs/PROJECT_PLAN.md';original=p.read_text(encoding='utf-8');body=original[:original.index('\n## ',1)].split('\n\n',1)[1]
    first_section('docs/PROJECT_PLAN.md','''## 2026-10-20 A24-LSF-BAND-01 · 완료

고정18환경/기존24세션 재사용으로42행 비교를 완료했다.23순수/589합성Node검사·818pins·30960선택/12677경로대기 재생·독립12385977검사 PASS다. 전량처리 고부하에서 우리정책의 정시/소비 이득, 중간부하 서비스 손해, 포기허용Band-LSF 적용판의 고부하92.85%정시·낮은소비/307포기를 모두 보고했다. Band전체재현으로확대하지않으며 기본LSF는저부하에서EDF와정확동일·고부하에서차이가있다. [판정/전체42행](../a24_simulator/results/A24_LSF_BAND_20261020_01/INTERPRETATION_KO.md). 방법론9.6/재개자료완료·새학습/NN/fit/기기0·현재18단위/도출137759·자동추가/재시도0, 다음은해석/공유·diff검토다.

### 실행 전 계획(보존)

'''+body)
    p=R/'docs/DECISIONS.md';t=p.read_text(encoding='utf-8');header,rest=t.split('\n\n',1)
    p.write_text(header+'\n\n'+'''실행 후 판정:18환경 모두완료·FAIL0, 독립12385977검사 PASS다. 부하1.2 전량처리에서는 우리정책이 기본LSF/Band적용판보다 전체정시24.167/27.442%p·긴급26.515/29.015%p 높고 소비0.838/1.177% 낮다. 포기허용Band적용판은307건을 포기하면서도 전체도착 기준정시92.85%로우리78.91%보다높고 소비3.110%낮아 우리정책전조건우수 주장을 하지않는다. 부하0.8우리정책의정시/지연손해, 포기예측오류가능성과 두패턴차이를 보존한다. 새학습/NN/fit/기기0·현재18단위/도출137759·자동추가0·로컬미커밋/미게시다. [전체판정](../a24_simulator/results/A24_LSF_BAND_20261020_01/INTERPRETATION_KO.md).

'''+rest,encoding='utf-8')
    first_section('a24_simulator/docs/LATEST_EXECUTION_FILES.md','''## 2026-10-20 최신 완료 · 기본LSF / Band-LSF 요청단위 적용판

[판정/4변형/포기와서비스손해](../results/A24_LSF_BAND_20261020_01/INTERPRETATION_KO.md) · [전체7정책42행](../results/A24_LSF_BAND_20261020_01/REPORT_KO.md) · [저장차이/포기ID참고](../results/A24_LSF_BAND_20261020_01/FINDINGS.json) · [재개](../results/A24_LSF_BAND_20261020_01/CONTINUE_RUNNING.md) · [사전설계](../experiments/a24_lsf_band_20261020/PROTOCOL.md). 부하0.4/0.8/1.2·600초·두패턴 새18평가완료/기존24저장재사용·새학습/NN/fit/기기0이다. 전량처리 고부하에서우리정시78.91% 대기본LSF54.75/Band적용51.47%, 포기허용Band적용은307건포기·전체도착정시92.85%·소비3.110%낮았다. Band전체 native/framework 재현이 아니다. 23순수검사/818pins·독립12385977검사·30960선택/12677경로대기 재생 PASS, 현재18단위/도출137759·방법론9.6반영·로컬미커밋/미게시·자동추가0이다.''')
    summary=read(O/'SUMMARY.json');names={'LSF_DYN':'기본 LSF','BAND_LSF_ALL':'Band-LSF 적용·전량처리','BAND_LSF_DROP':'Band-LSF 적용·포기허용','IDLE_BC':'우리 정책'}
    section='''### 9.6 기본 LSF와 모바일 Band-LSF 규칙 적용판

기본 LSF는 `납기−현재시각−가용장치 예측응답시간`이 작은 요청부터 선택한다. Band 공개 LSF의 worker 대기 고려, 최적 경로가 busy인 요청 건너뛰기, 예측상 SLO 위반 포기를 요청 단위에 적용했다. 포기 기능을 끈 판과 허용한 판을 모두 사전 고정했다. **Band 전체 프레임워크의 성능 재현이 아니다.** 원본 모델 분할, tensor 전송, 일괄 worker queue·native/Android 실행은 재현하지 않았다. pinned 공개원문9파일과 적용 차이를 보존했다.

부하0.4/0.8/1.2·600초·두패턴의 새18평가를 완료하고 기존FIFO/EDF/RR/우리정책24세션을 저장재사용했다. CPU3/GPU1·ORIGINAL·명목/latent/물리와우리체크포인트를 동결했고 새학습/NN실행/fit/실기기0이다. 소비·AP·P95는 두 패턴 평균, 서비스는 전체도착을 분모로 합산하며 포기는 실패/미응답에 포함한다. P95는 응답한 요청의 조건부 통계다.

|부하|정책|예측소비 J*|전체정시 %|긴급정시 %|긴급P95 초|포기 건|
|---:|---|---:|---:|---:|---:|---:|
'''
    for g in summary['groups']:
        if g['policy'] not in names:continue
        a,u=g['service']['ALL'],g['service']['U']
        section+=f"|{g['load']}|{names[g['policy']]}|{g['common_J']:.3f}|{100*a['on']/a['n']:.2f}|{100*u['on']/u['n']:.2f}|{u['mean_session_P95_s']:.3f}|{g['dropped']}|\n"
    section+='''
부하0.4에서 우리정책은 기본LSF/Band적용판 대비 소비2.192/2.186% 낮지만 긴급P95는0.249/0.407초 길다. 기본LSF는EDF와모든장치·시각·응답이동일했다. 부하0.8에서 우리정책은 전량처리 기본LSF/Band적용판 대비 소비3.232/3.646% 낮지만 전체정시1.395%p·긴급2.045%p 낮고 긴급P95가0.691/0.779초길다.

부하1.2 전량처리에서는 우리정책이 기본LSF/Band적용판 대비 소비0.838/1.177%·AP0.237/0.315℃ 낮고 전체정시24.167/27.442%p·긴급26.515/29.015%p 높다. 그러나 포기허용 Band적용판은307/5160건(긴급235)을 포기하면서도 전체도착정시4791/5160·긴급1031/1320으로우리4072/5160·958/1320보다많았다. 소비도우리보다44.687J*·3.110%낮았다. 우리정책은5160건모두응답했고이적용판은4853건응답했다. 같은전량처리의서비스규칙이아니며 포기를숨긴성공률도아니다. 각정책의모든손해와응답수를함께보존한다.

Band적용판의 예상 납기 위반은 불가피한 실제 위반의 증명이 아니다. 부하0.8패턴0의 전량처리판은1520건모두정시였으나 포기허용판은긴급1건을포기했다. 또한 위9.5의 패턴0 손해와 단일패턴에 집중된 큰 서비스개선의 해석을 유지한다. 우리정책의 전조건 우위, ATC/롤링/BC의개별기여, 실기기 절감으로 확대하지 않는다.

[판정·전체비교](../results/A24_LSF_BAND_20261020_01/INTERPRETATION_KO.md) · [전체42행](../results/A24_LSF_BAND_20261020_01/REPORT_KO.md) · [저장궤적차이/포기참고](../results/A24_LSF_BAND_20261020_01/FINDINGS.json) · [사전설계/원문](../experiments/a24_lsf_band_20261020/PROTOCOL.md). 정책/합성엔진23검사·별도Node합성21상태589검사·818pins·저장30960선택/12677경로대기 재생·독립12385977검사(최대절대오차약1e-9) PASS다. 새18 START/COMPLETE·FAIL0, 과거24재실행/새NN/학습/fit/기기0이다.

'''
    p=R/'a24_simulator/docs/A24_POLICY_METHODOLOGY_KO.md';t=p.read_text(encoding='utf-8');assert '### 9.6' not in t
    p.write_text(t.replace('## 10. 검증 범위와 해석',section+'## 10. 검증 범위와 해석'),encoding='utf-8')
    print('LSF_BAND_ROOT_RECORDS_AND_METHOD_9_6_COMPLETE')

if __name__=='__main__':main()
