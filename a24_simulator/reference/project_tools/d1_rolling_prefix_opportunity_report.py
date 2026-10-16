"""Audit completed forecasts and compare new choices with stored actual replies."""
import argparse,csv,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
from tools import d1_rolling_prefix_opportunity_study as s
m=s.m;selector=s.selector
def same_action(a,b):return selector.signature(a)==selector.signature(b)
def report():
    reg=s.read(s.LOCAL/'registration.json');completion=s.read(s.LOCAL/'completion.json');starts={};ends={}
    for line in (s.LOCAL/'projections.jsonl').read_text(encoding='utf-8').splitlines():
        value=json.loads(line);table=ends if value.get('event') else starts
        assert value['number'] not in table;table[value['number']]=value
    assert set(starts)==set(ends) and len(starts)<=792
    for number,row in starts.items():
        assert ends[number]['status']=='completed'
        assert s.sha(s.LOCAL/'projections'/(row['identity']+'.json'))==ends[number]['sha256']
    for name,h in reg['source_sha256'].items():assert s.sha(s.ROOT/name)==h,name
    assert not (s.LOCAL/'owner.lock').exists()
    frozen,_=m.p.inputs(m.p.BUNDLE);initial=s.read(s.ROOT/'docs/results/rolling_prefix_01/inputs.json')['initial']
    comparisons=[];forecast_rows=[]
    for index,state in enumerate(reg['states']):
        data=s.read(s.LOCAL/f'states/state_{index}.json');original=s.raw(s.ROOT/state['raw_path'])
        controller=m.previous.Controller(frozen,initial);queue,lanes,now=m.PublicTape(original).restore(controller,state['callback_index'])
        assert s.state_key(controller,queue,lanes,now)==data['snapshot_state_key']
        baseline=controller.band.decide({},queue,lanes,now,{},None,None)
        band=dict(kind='single',jobs=[baseline['selected']]) if baseline['selected'] else dict(kind='band_event_wait')
        reply=original['result']['decisions'][state['callback_index']]
        if reply.get('action_kind')=='cool_wait':
            old=dict(kind='cool_wait',until_ns=reply['wait_until_ns'],hold_signature=controller.signature(queue,lanes))
        elif reply.get('selected'):
            jobs=[reply['selected']]
            next_index=state['callback_index']+1
            if next_index<len(original['result']['decisions']):
                nxt=original['result']['decisions'][next_index]
                if nxt['now_ns']==now and nxt.get('action_kind')=='bundle_commit' and nxt.get('selected'):jobs.append(nxt['selected'])
            old=dict(kind='bundle' if len(jobs)==2 else 'single',jobs=jobs)
        elif reply.get('reason')=='rolling_selected_resource_wait':old=dict(kind='resource_wait',until_ns=None,hold_signature=controller.signature(queue,lanes))
        else:old=band
        chosen=data['selection'].get('chosen');new=chosen['action'] if chosen else band
        additional=bool(chosen and not same_action(new,old))
        row=dict(data['row'],same_as_old_actual_action=same_action(new,old),additional_admissible_action=additional,
            old_action=old['kind'],new_action=new['kind'],old_guard_blocked=bool(reply.get('prefix_guard_blocked')))
        comparisons.append(row)
        for candidate in data['candidates']:
            for context,forecast in candidate['forecasts'].items():
                ref=data['references'][context]
                forecast_rows.append(dict(state=index,ordinal=candidate['ordinal'],kind=candidate['action']['kind'],context=context,valid=forecast['valid'],
                    delta_AP=forecast.get('global_peak_ap_c',0)-ref['global_peak_ap_c'] if forecast['valid'] else None,
                    delta_J=forecast.get('remaining_increment_j',0)-ref['remaining_increment_j'] if forecast['valid'] else None,
                    delta_urgent_misses=forecast.get('urgent_misses',0)-ref['urgent_misses'] if forecast['valid'] else None,
                    delta_normal_misses=forecast.get('normal_misses',0)-ref['normal_misses'] if forecast['valid'] else None,
                    delta_P95_ms=forecast.get('urgent_p95_ms',0)-ref['urgent_p95_ms'] if forecast['valid'] and forecast.get('urgent_p95_ms') is not None and ref['urgent_p95_ms'] is not None else None))
    additional=[r for r in comparisons if r['additional_admissible_action']]
    facts=dict(status='PASS',utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        states=len(comparisons),restored=sum(r['status']=='diagnosed' for r in comparisons),unknown=completion['unknown'],
        local_gains_vs_Band=completion['opportunities'],additional_choices_vs_old=len(additional),
        same_actual_actions=sum(r['same_as_old_actual_action'] for r in comparisons),consumption=completion['consumption'],
        source_sha256=reg['source_sha256'],raw_sources_preserved=True,source_tolerance_is_not_policy_margin=True,
        counterfactual_only=True,policy_connected=False,independent_confirmation=0,full_trace_performance_claim=False)
    for name,rows in [('action_comparison.csv',comparisons),('candidate_forecasts.csv',forecast_rows)]:
        fields=list(rows[0])
        if name=='action_comparison.csv':fields=[k for k in fields if k not in ('reconstruction_errors',)]+['delta_global_AP','delta_increment_J']
        fields=list(dict.fromkeys(fields))
        with (s.PUBLIC/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    s.write(s.PUBLIC/'verification.json',facts)
    for index in range(8):(s.PUBLIC/f'state_{index}.json').write_bytes((s.LOCAL/f'states/state_{index}.json').read_bytes())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():plt.rcParams['font.family']=FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(12,4.6))
    labels=['선정한 상태','공개 상태 복원','Band 대비 국소 이득','기존 행동과 다른 이득']
    axes[0].bar(labels,[8,8,4,len(additional)],color=['#8397ab','#33786c','#33786c','#c68132'])
    axes[0].set_ylim(0,9);axes[0].tick_params(axis='x',labelrotation=20);axes[0].set_ylabel('상태 수')
    axes[1].bar(range(8),[r.get('delta_global_AP',0.) for r in comparisons]);axes[1].set_xticks(range(8),[str(i) for i in range(8)])
    axes[1].set_xlabel('사전 선정 상태 번호');axes[1].set_ylabel('선택 prefix의 최악 AP 차이 (°C)');axes[1].axhline(0,color='black',lw=.5)
    fig.suptitle('저장 개발8상태의 조건부 예측 진단 · 전체 정책 성능 아님');fig.tight_layout();fig.savefig(s.PUBLIC/'01_기존행동과_새대안.png',dpi=160);plt.close(fig)
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>롤링 첫 행동 기회 진단</title><style>body{font:16px system-ui;max-width:1200px;margin:30px auto;padding:0 16px;line-height:1.6}img{max-width:100%}td,th{border:1px solid #ddd;padding:8px}table{border-collapse:collapse}</style><h1>공동 롤링: 기존 절차가 놓친 첫 행동이 있는가</h1><p>개발8상태 복원8·불명0. Band 대비 국소 예측 이득4, 기존 실행 행동과 다른 이득1. 예측170/상한792·새환경/학습/기기0. 전체 실행 성능·실제 폰 절감은 미확인.</p><p><a href="README.md">판독·범위·재현</a> · <a href="action_comparison.csv">8상태 대조</a> · <a href="candidate_forecasts.csv">모든 후보 예측</a> · <a href="verification.json">검증</a></p><img src="01_기존행동과_새대안.png" alt="조건부 이득4와 새 행동 이득1을 구분"><table><tr><th>상태</th><th>부하</th><th>기존 행동</th><th>새 선택</th><th>Band 대비 AP 차이</th><th>추가 대안</th></tr>'''
    names=dict(low='낮은 부하',queue='큐 몰림',burst='순간 몰림',sustained='지속 부하',single='즉시 단건',cool_wait='유한 대기',resource_wait='자원 대기',band_event_wait='Band 사건 대기',bundle='동시 쌍')
    for row in comparisons:
        html+='<tr>'+''.join('<td>'+str(v)+'</td>' for v in [row['index'],names[row['family']],names[row['old_action']],names[row['new_action']],f"{row.get('delta_global_AP',0.):.6f}",'있음' if row['additional_admissible_action'] else '없음'])+'</tr>'
    html+='</table><p>새 대안은 상태6의 0.25초 대기다. 현재 도착 탐지4건의 예상 응답은 각각 약250ms 늦지만 현재 기한 실패·긴급P95·J는 그대로이며 AP 예측은 약0.0142°C 낮다. 미도착 요청의 서비스와 전체trace 결과는 알 수 없다. 뒤에 실제 도착한 요청을 예측 입력으로 쓰지 않았다.</p></html>'
    (s.PUBLIC/'index.html').write_text(html,encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='PASS',states=8,additional=len(additional),consumption=facts['consumption'])))
if __name__=='__main__':report()
