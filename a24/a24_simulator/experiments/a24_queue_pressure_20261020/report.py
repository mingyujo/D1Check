"""Report every predeclared condition, including failures and service losses."""
from study import H,O,R,read,new,stamp,MODES

def fmt(x,n=3):return '미정' if x is None else f'{x:.{n}f}'
def main():
    assert not (O/'REPORT_KO.md').exists()
    summary=read(O/'SUMMARY.json');rows=read(O/'DERIVED.json');groups=summary['groups']
    assert read(O/'AUDIT.json')['status']=='PASS' and read(O/'NN_AUDIT.json')['status']=='PASS'
    names={'FIFO_DYN':'FIFO+동적배정','EDF_DYN':'EDF+동적배정','RR_DYN':'요청군RR+동적배정','IDLE_BC':'우리정책(롤링+ATC+BC+대기보완)'}
    header='|부하|정책|예측소비 J*|평균AP ℃|전체정시|긴급정시|전체P95 초|긴급P95 초|미완료/미응답|최대대기열|\n|---:|---|---:|---:|---|---|---:|---:|---|---:|\n'
    def table(items):
        text=header
        for g in items:
            if g['failed']:text+=f"|{g['load']}|{names[g['policy']]}|미정|미정|미정|미정|미정|미정|guard FAIL{g['failed']}|미정|\n";continue
            sv=g['service'];a=sv['ALL'];u=sv['U'];text+=f"|{g['load']}|{names[g['policy']]}|{fmt(g['common_J'])}|{fmt(g['AP'])}|{a['on']}/{a['n']} ({100*a['on']/a['n']:.2f}%)|{u['on']}/{u['n']} ({100*u['on']/u['n']:.2f}%)|{fmt(a['mean_session_P95_s'])}|{fmt(u['mean_session_P95_s'])}|{g['incomplete']}/{a['missing']}|{g['supply_peak_ready']}|\n"
        return text
    intro='# A24 요청 적체 조건 비교 · 부하0.8/1.2\n\n600초·두패턴·CPU3/GPU1·ORIGINAL 모형·기존동결50특징 우리정책이다. FIFO/EDF/요청군RR은 동일한현재가용장치의최단예측응답 동적배정이며기준선에롤링/학습/자발적WAIT를추가하지않았다. 기존.4입력의도착간격만2배/3배압축하고상대납기·admission·양경로latent·공개명목은보존했다. 새16환경만실행했고.4참고8세션은저장원자료재사용이다. 새학습/BCfit/PPO/물리fit/실기기0이다.\n\n소비/AP/P95는두패턴세션평균,정시/미응답/미완료는두패턴합계,최대대기열은두패턴중최대다. J*는미교정예측소비이며실기기절감증거가아니다. 공통창은각입력네정책의마지막반환시각(최소공급종료),실패/미완료가있으면공통drain이다. 완료응답P95와누락을함께보며부하간은작업수가달라총소비를직접정책효과로비교하지않는다.\n\n'
    maintext=intro+table([g for g in groups if g['load']>.4])
    maintext+='\n## 우리정책−기준선: 소비와 서비스의 상충\n\n양수소비절감=우리정책이덜소비, AP/P95차는우리정책−기준선, 정시율차는우리정책−기준선의퍼센트포인트다.\n\n|부하|기준선|소비절감 J*|절감 %|평균AP차 ℃|전체정시율차 %p|긴급정시율차 %p|긴급P95차 초|자체꼬리절감 %|\n|---:|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for c in summary['IDLE_BC_comparisons']:
        if c['load']<=.4:continue
        if c.get('failed'):maintext+=f"|{c['load']}|{c['baseline']}|미정|미정|미정|미정|미정|미정|미정|\n";continue
        maintext+=f"|{c['load']}|{c['baseline']}|{fmt(c['saved_common_J'])}|{fmt(c['saving_pct'])}|{fmt(c['AP_delta'])}|{fmt(c['ALL_ontime_percentage_point_delta'])}|{fmt(c['U_ontime_percentage_point_delta'])}|{fmt(c['U_P95_delta_s'])}|{fmt(c['own_tail_saving_pct'])}|\n"
    maintext+='\n## 실제 적체와 요청 순서 선택\n\n복수ready와FIFO선두외선택은배정결정만집계한다. FIFO선두외선택은해당정책자기큐기준이며다른정책실행과차이난요청수와구분한다. 시간평균큐는공급600초에서실제입장/배정으로재구성했다.\n\n|부하|정책|최대대기열|시간평균대기열|복수ready 배정/전체|C·D동시ready 배정|자기큐FIFO선두외선택|대기P95 초|예측cap 수|\n|---:|---|---:|---:|---|---:|---:|---:|---:|\n'
    for g in groups:
        if g['failed']:continue
        maintext+=f"|{g['load']}|{names[g['policy']]}|{g['supply_peak_ready']}|{fmt(g['time_mean_ready'])}|{g['multi_ready_dispatches']}/{g['dispatch_decisions']}|{g['both_classes_ready_dispatches']}|{g['selected_not_FIFO_head']}|{fmt(g['queue_wait_P95_s'])}|{g['capped_forecasts']}|\n"
    maintext+='\n## 検証・범위\n\n입력보존8검사·출처pin·등록START/terminal·독립입력/물리/서비스/정책/큐검산·원Torch저장선택재생/전체checkpoint·두Adam/RNG불변·Float64NN검사를확인했다. 자세한수치와파일해시는최종증명을따른다. 우리정책은재학습없이높은도착빈도에적용했으며두패턴주기반복/가상CPU3/미교정J*·명의처리자료의한계를유지한다. 모든부하/손해/실패를함께보존하며추가탐색/최적부하선정/통계적유의성/실기기일반화를주장하지않는다.\n\n[전체24행](REPORT_KO.md) · [기계요약](SUMMARY.json) · [요청/서비스/큐 원계산](DERIVED.json) · [독립검산](AUDIT.json) · [NN검산](NN_AUDIT.json) · [원Torch/동적재생](REPLAY.json) · [사전설계](../../experiments/a24_queue_pressure_20261020/PROTOCOL.md).\n'
    maintext=maintext.replace('検証・','검증·').replace('명의처리','명목처리')
    (O/'INTERPRETATION_KO.md').write_text(maintext,encoding='utf-8')
    text=intro+table(groups)+'\n## 패턴별 전24행\n\n|부하|패턴|정책|공통창 초|소비 J*|평균AP ℃|전체정시|긴급정시|일반정시|긴급P95 초|공급창 J*|자체꼬리 J*|미완료/미응답|최대큐|시간평균큐|자료|\n|---:|---:|---|---:|---:|---:|---|---|---|---:|---:|---:|---|---:|---:|---|\n'
    for r in rows:
        if r.get('failed'):text+=f"|{r['load']}|{r['pattern']}|{r['policy']}|미정|미정|미정|미정|미정|미정|미정|미정|미정|FAIL|미정|미정|원부분자료보존|\n";continue
        sv=r['service'];qs=r['queueStats'];text+=f"|{r['load']}|{r['pattern']}|{r['policy']}|{fmt(r['common_end_ns']/1e9-35)}|{fmt(r['common']['J'])}|{fmt(r['common']['AP'])}|{sv['ALL']['on']}/{sv['ALL']['n']}|{sv['U']['on']}/{sv['U']['n']}|{sv['N']['on']}/{sv['N']['n']}|{fmt(sv['U']['P95'])}|{fmt(r['supply']['J'])}|{fmt(r['own_tail_J'])}|{r['incomplete']}/{sv['ALL']['missing']}|{qs['supply_peak_ready']}|{fmt(qs['supply_time_mean_ready'])}|{'저장재사용' if r['reused'] else '새평가'}|\n"
    text+='\n[해석/큐/서비스손해](INTERPRETATION_KO.md) · [모든정시/완료응답세션평균·pooled P95/병행/경로수/예측cap](DERIVED.json) · [요약](SUMMARY.json) · [독립감사](AUDIT.json). 최고AP는모든정책trace끝점의공통정의이며연속구간최고값은원자료에보존한다.\n'
    (O/'REPORT_KO.md').write_text(text,encoding='utf-8')
    result=read(O/'RESULT.json');(O/'CONTINUE_RUNNING.md').write_text('# 재개 안내\n\n이번고정부하.8/1.2×두패턴×네정책16환경을종료했다. 완료환경/실패환경을재시작하지않는다. INTERPRETATION_KO.md→REPORT_KO.md→SUMMARY.json→AUDIT.json/NN_AUDIT.json/REPLAY.json→FINAL_HANDOFF_PROOF.json을읽는다. 기존.4의8세션재사용·새학습/BCfit/PPO/물리fit/기기0,현재16단위·도출137741·자동추가/재시도0이다. 로컬미커밋/미게시이며별도후속지시가없으면추가실험하지않는다. PowerShell직접호출을사용하고Python로그wrapper를추가하지않는다.\n',encoding='utf-8')
    print('PRESSURE_REPORT_COMPLETE',result['START'],result['COMPLETE'],result['FAIL'])
if __name__=='__main__':main()
