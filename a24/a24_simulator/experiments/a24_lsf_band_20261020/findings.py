"""Post-run descriptive analysis of saved rows only; no predictions or environments."""
from study import H,O,R,read,new,pin,stamp,MODES

def main():
    assert read(O/'AUDIT.json')['status']=='PASS' and not (O/'FINDINGS.json').exists()
    summary=read(O/'SUMMARY.json');rows=read(O/'DERIVED.json')
    groups={(g['load'],g['policy']):g for g in summary['groups']}
    def raw(row):return read(R/row['raw']['path'])
    differences=[];drop_reference=[];wait_checks=[]
    for case in sorted({r['case'] for r in rows}):
        local={r['policy']:r for r in rows if r['case']==case}
        for a,b in (('LSF_DYN','EDF_DYN'),('BAND_LSF_ALL','LSF_DYN')):
            aa=raw(local[a])['result']['requests'];bb=raw(local[b])['result']['requests']
            assert len(aa)==len(bb) and all(x['request_id']==y['request_id'] for x,y in zip(aa,bb))
            fields=('route','dispatch_ns','response_ns','available_ns')
            differences.append(dict(case=case,load=local[a]['load'],a=a,b=b,n=len(aa),
                differing_requests=sum(any(x[k]!=y[k] for k in fields) for x,y in zip(aa,bb)),
                differing_fields={k:sum(x[k]!=y[k] for x,y in zip(aa,bb)) for k in fields}))
        all_raw=raw(local['BAND_LSF_ALL'])['result']
        reference={q['request_id']:q for q in all_raw['requests']}
        drop_raw=raw(local['BAND_LSF_DROP'])['result']
        dropped=[q for q in drop_raw['requests'] if 'dropped_ns' in q]
        reference_on=sum(reference[q['request_id']]['response_ns'] is not None and
                         reference[q['request_id']]['response_ns']<=reference[q['request_id']]['deadline_ns'] for q in dropped)
        drop_reference.append(dict(case=case,load=local['BAND_LSF_DROP']['load'],dropped=len(dropped),
            urgent_dropped=sum(q['priority']=='U' for q in dropped),same_ID_ontime_in_no_drop_run=reference_on,
            different_trajectory_not_same_state_counterfactual=True))
        for mode in MODES:
            saved=raw(local[mode]);waits=saved.get('wait_calls',[])
            assert all(w['free_routes'] and w['public_state']['queue'] for w in waits)
            wait_checks.append(dict(case=case,policy=mode,resource_wait_calls=len(waits),
                all_with_free_other_route=True,all_with_visible_queued_request=True))
    savings=[]
    for load in (.4,.8,1.2):
        ours=groups[load,'IDLE_BC']
        for mode in MODES:
            b=groups[load,mode]
            savings.append(dict(load=load,baseline=mode,baseline_minus_ours_J=b['common_J']-ours['common_J'],
                baseline_saving_vs_ours_pct=100*(1-b['common_J']/ours['common_J']),
                baseline_ALL_ontime_minus_ours_pp=100*(b['service']['ALL']['on']/b['service']['ALL']['n']-ours['service']['ALL']['on']/ours['service']['ALL']['n'])))
    new(O/'FINDINGS.json',dict(status='PASS',utc=stamp(),source=pin(H/'findings.py'),post_run_descriptive_only=True,
        new_environment=0,new_NN_execution=0,source_results=[pin(O/n) for n in ('SUMMARY.json','DERIVED.json','AUDIT.json')],
        saved_trajectory_differences=differences,drop_ID_reference=drop_reference,resource_wait_checks=wait_checks,
        baseline_relative_to_ours=savings))
    conclusion='''
## 결과 판정

- 부하0.4: 네 비교대상 모두 전체/긴급 정시100%다. 우리정책은 기본LSF 대비 소비2.192%, Band-LSF 적용판 대비2.186% 적지만 긴급P95는 각각0.249초/0.407초 길다. 기본LSF와EDF는 저장 요청의 장치/배정/응답/반환이 모두 같다. 포기허용판의 실제 포기는0건이다.
- 부하0.8: 우리정책은 전량처리 기본LSF/Band-LSF 대비 소비3.232%/3.646%, AP0.764/0.865℃ 낮지만 전체정시1.395%p·긴급2.045%p 낮고 긴급P95가0.691/0.779초 길다. 포기허용판은55건 모두 긴급요청을 포기했고 전체정시98.40%다. 패턴0에서는 전량처리Band가760이 아닌1,520건 모두 정시였지만 포기허용판은긴급1건을포기했다. 예측상 SLO 위반을 실제 불가피한 위반으로 단정할 수 없다.
- 부하1.2 전량처리: 우리정책은 기본LSF/Band-LSF 대비 소비0.838%/1.177%, AP0.237/0.315℃ 낮고 전체정시24.167/27.442%p, 긴급26.515/29.015%p 높다. 긴급P95도3.437/4.280초 짧다. 이는 두 패턴 합산 판정이며 패턴0 전체정시/지연의 손해까지 없어진 것은 아니다.
- 부하1.2 포기허용: Band-LSF 적용판이307/5,160건(5.95%, 긴급235건)을 포기하면서도 전체도착 기준정시4,791건(92.85%)·긴급1,031건(78.11%)으로 우리정책4,072건(78.91%)·958건(72.58%)보다 높다. 소비1392.021J*로우리1436.708J*보다44.687J*·3.110% 낮고 AP도0.762℃ 낮다. 응답조건부 긴급P95는1.568초로우리2.600초보다짧다. 포기만 숨겨서 좋아진 통계는 아니며, 전체분모 성공도 개선됐다. 다만 우리정책은5,160건 모두 응답했고 이 적용판은4,853건 응답했다. 납기지난 요청도 처리할지, 예측상 실패요청을 포기할지의 서비스 규칙 차이가 있다.

따라서 우리정책의 전조건 최우수는 주장하지 않는다. 전량처리 고부하에서는 결합정책의 이득이 있고, 중간부하에서는 소비·열과 서비스 사이의 손해가 있다. 포기 허용 Band-LSF 적용판은 고부하에서 강한 비교대상이며 그 결과도 그대로 보존한다. 이는 Band 전체 프레임워크 또는 실기기 소비에 대한 결론이 아니다.

기본LSF와EDF는 부하0.4에서 실행이 정확히 같고 고부하에서 달라졌다. LSF가 FIFO/EDF와 항상 다른 결과를 내야 하는 것은 아니다. Band 경로대기는 빈 다른 장치가 있는 공개ready상태에서 발생했음을 저장기록으로 확인했다. [차이·포기ID 참고·대기 검산](FINDINGS.json)을 보존한다. 포기ID가 전량처리의 다른 궤적에서 정시였는지 여부는 참고이며 같은 상태의 반사실 성공을 증명하지 않는다.
'''
    conclusion=conclusion.replace('760이 아닌1,520건','1,520건')
    p=O/'INTERPRETATION_KO.md';p.write_text(p.read_text(encoding='utf-8')+conclusion,encoding='utf-8')
    p=O/'REPORT_KO.md';p.write_text(p.read_text(encoding='utf-8')+'\n[판정·상충·포기 허용의 서비스 차이](INTERPRETATION_KO.md#결과-판정) · [저장 궤적 차이·참고](FINDINGS.json).\n',encoding='utf-8')
    print('LSF_BAND_FINDINGS_SAVED_ONLY',len(differences),'trajectory comparisons')
if __name__=='__main__':main()
