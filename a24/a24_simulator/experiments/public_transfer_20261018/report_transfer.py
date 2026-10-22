"""Audited saved-only tables, scientific plots, all rows and handoff proof."""
from pathlib import Path
import json,hashlib,subprocess,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];REPO=ROOT.parent
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];audit=read(out/'AUDIT.json');assert audit['status']=='PASS';rows=read(out/'WORK_METRICS.json')['rows'];ref={(r['case'],r['policy']):r for r in rows if r['kind']=='REUSED_EVAL'}
    for r in rows:
        r['remarks']=[];r['deltas']={}
        if r['kind'] not in ('EVAL','BC_EVAL','REUSED_EVAL'):r['remarks'].append(r['kind']+' 행: 정책우위 선정 제외; 수치는 보존')
        if not r['common_complete']:r['remarks'].append('EDF공통창 내 전체AVAILABLE 미달: 공동우위 선정 제외')
        if r['completion'] is None:r['remarks'].append('전체AVAILABLE 미달: 완료소비 미정의')
        for p in ('EDF','FIFO'):
            b=ref.get((r['case'],p))
            if not b:continue
            service=r['original']['on_time']>=b['original']['on_time'] and r['original']['urgent_on_time']>=b['original']['urgent_on_time'] and r['normal_on_time']>=b['normal_on_time'] and r['original']['response_missing']==0 and r['original']['incomplete']==0
            saving=None if r['completion'] is None or b['completion'] is None else 100*(1-r['completion']['total_J_proxy']/b['completion']['total_J_proxy']);mean=r['common']['mean_AP_c']-b['common']['mean_AP_c'];peak=r['original']['peak_AP_c']-b['original']['peak_AP_c']
            r['deltas'][p]=dict(completion_saving_percent=saving,mean_AP_delta_c=mean,peak_AP_delta_c=peak,on_time_delta=r['original']['on_time']-b['original']['on_time'],urgent_delta=r['original']['urgent_on_time']-b['original']['urgent_on_time'],normal_delta=r['normal_on_time']-b['normal_on_time'],service_nonworse=service,joint_nonworse=service and r['common_complete'] and b['common_complete'] and saving is not None and saving>=-1e-7 and mean<=1e-7 and peak<=1e-7)
            if not service:r['remarks'].append(p+' 전체/긴급/일반 납기 손해 또는 미완료: 서비스보존 선정 제외')
    evaluation=[r for r in rows if r['kind'] in ('EVAL','BC_EVAL','REUSED_EVAL')];classify=read(ROOT/'results/MODERATE_LOAD_20261018_01/LOAD_CLASSIFICATION.json')['rows'];sets={'ALL30':None,'MODERATE16':[r['case'] for r in classify if r['classification']=='중간후보'],'SATURATION4':[r['case'] for r in classify if r['classification']=='포화후보']};summaries=[]
    def aggregate(a,name,group):
        n=sum(r['n'] for r in a);un=sum(r['original']['urgent_planned'] for r in a);nn=sum(r['normal_planned'] for r in a);complete=all(r['completion'] is not None for r in a)
        s=dict(policy=name,group=group,rows=len(a),unique_inputs=len({r['case'] for r in a}),seeds=sorted({r['seed'] for r in a if r['seed'] is not None}),n=n,on_time=sum(r['original']['on_time'] for r in a),urgent_planned=un,urgent_on_time=sum(r['original']['urgent_on_time'] for r in a),normal_planned=nn,normal_on_time=sum(r['normal_on_time'] for r in a),completion_total_J_proxy=sum(r['completion']['total_J_proxy'] for r in a) if complete else None,mean_AP_c=sum(r['common']['mean_AP_c'] for r in a)/len(a),mean_peak_AP_c=sum(r['original']['peak_AP_c'] for r in a)/len(a),pooled_P95_s=sorted(t for r in a for t in r['response_times_s'])[__import__('math').ceil(.95*sum(len(r['response_times_s']) for r in a))-1] if any(r['response_times_s'] for r in a) else None,missing=sum(r['original']['response_missing'] for r in a),incomplete=sum(r['original']['incomplete'] for r in a),common_complete=sum(r['common_complete'] for r in a))
        s['on_percent']=100*s['on_time']/n;s['urgent_percent']=100*s['urgent_on_time']/un;s['normal_percent']=100*s['normal_on_time']/nn
        for p in ('EDF','FIFO'):
            b=[ref[(r['case'],p)] for r in a];s[p]=dict(completion_saving_percent=100*(1-s['completion_total_J_proxy']/sum(r['completion']['total_J_proxy'] for r in b)) if complete and all(r['completion'] for r in b) else None,mean_AP_delta_c=sum(r['deltas'][p]['mean_AP_delta_c'] for r in a)/len(a),mean_peak_delta_c=sum(r['deltas'][p]['peak_AP_delta_c'] for r in a)/len(a),service_nonworse=sum(r['deltas'][p]['service_nonworse'] for r in a),joint_nonworse=sum(r['deltas'][p]['joint_nonworse'] for r in a))
        return s
    for group,ids in sets.items():
        subset=[r for r in evaluation if ids is None or r['case'] in ids]
        for policy in sorted({r['policy'] for r in subset}):summaries.append(aggregate([r for r in subset if r['policy']==policy],policy,group))
        for stage in (1,2,3,4):summaries.append(aggregate([r for r in subset if r['kind']=='EVAL' and r['stage']==stage],f'S{stage}_3SEED_MEAN',group))
    save(out/'SUMMARY.json',dict(rows=summaries,paired_inputs=True,independent_phone_replicates=False,statistical_significance_not_tested=True));save(out/'ALL_ROWS_WITH_REASONS.json',dict(rows=rows,removed_rows=0,new_numeric_rows=562,reused_numeric_rows=120,prior_completed_report='results/WITNESS_CLOSEOUT_20261018_01/REPORT.md',stopped_thermal_preserved='results/THERMAL_COEFFICIENTS_20261018_01/USER_STOP.json'))
    def f(v,d=4):return '—' if v is None else f'{v:.{d}f}'
    header='|구간|정책|정시%|긴급%|일반%|완료절감vsEDF%|완료절감vsFIFO%|평균AP차vsEDF℃|평균AP차vsFIFO℃|최고AP평균차vsEDF℃|완료응답pooledP95초|EDF/FIFO서비스비악화|EDF공통창완료|미응답/미완료|\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|\n'
    def table(items):return header+'\n'.join('|'+ '|'.join([s['group'],s['policy'],f(s['on_percent'],3),f(s['urgent_percent'],3),f(s['normal_percent'],3),f(s['EDF']['completion_saving_percent']),f(s['FIFO']['completion_saving_percent']),f(s['EDF']['mean_AP_delta_c'],5),f(s['FIFO']['mean_AP_delta_c'],5),f(s['EDF']['mean_peak_delta_c'],5),f(s['pooled_P95_s'],3),str(s['EDF']['service_nonworse'])+'/'+str(s['FIFO']['service_nonworse'])+' of '+str(s['rows']),str(s['common_complete'])+'/'+str(s['rows']),str(s['missing'])+'/'+str(s['incomplete'])])+'|' for s in items)+'\n'
    full='|종류|정책|输入|seed|정시/전체|긴급정시/긴급|일반정시/일반|완료J*|기저J*|증분J*|완료기간초|공통평균AP℃|최고AP℃|P95초|비고|\n|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|\n'
    for r in rows:
        m=r['original'];cc=r['completion'];full+='|'+'|'.join([r['kind'],r['policy'],r['case'],str(r['seed']),str(m['on_time'])+'/'+str(r['n']),str(m['urgent_on_time'])+'/'+str(m['urgent_planned']),str(r['normal_on_time'])+'/'+str(r['normal_planned']),f(cc['total_J_proxy'] if cc else None),f(cc['baseline_J_proxy'] if cc else None),f(cc['increment_J_proxy'] if cc else None),f(cc['duration_s'] if cc else None,3),f(r['common']['mean_AP_c'],5),f(m['peak_AP_c'],5),f(r['P95_s'],3),'; '.join(r['remarks']) or '수치보존'])+'|\n'
    comparison=[s for s in summaries if s['group']=='ALL30' and ('3SEED_MEAN' in s['policy'] or not s['policy'].startswith('S'))]
    text='# S26 공개정책 보완의 A24 단계별 비교\n\n'+f'신규562환경/3개BCfit·96TRAIN/48PPO update를 완료했다. 독립{audit["checks"]}검사와 새NN {audit["independent_new_NN_banks"]}bank 검산, BC/PPO/network/두Adam/RNG exact replay PASS다. 기존 BASE120개는 저장일정을 SHA로 고정해 새감사했으며, 중단 열계수 실험 전체의 완료를 뜻하지 않는다.\n\n'+ '[사전설계](../../experiments/public_transfer_20261018/README.md)의 순서대로 S1 공개교사·경로군BC/고정가중PPO, S2 목표별RMS·군별soft dual, S3 사건대기, S4 명목 열피드백예측을 누적했다. 단계별3seed는 같은8TRAIN/4update의 고정EP8이며 평가로checkpoint/seed를 고르지 않았다. S1/S2 공통BC, S3/S4 저장TRAIN 재부호화BC를 사용했으므로 S3/S4 개별요소의 독립인과효과로 해석하지 않는다. 모든BC고정판도 평가했다.\n\n'+ 'A24 BASE 물리/기저/도착/납기/latent/CPU1GPU1은 같다. S26 CPU3/NPU·계수·가중치는 이식하지 않았다. 새실측/물리fit/LP/latent추첨0이다. J*/AP는 미교정 가설모형값이며 실제 기기절감 인증이 아니다.\n\n![전체30조건](COMPARISON.png)\n\n## 전체30·모든단계\n\n에너지 절감 양수는 개선, 온도차 양수는 더따뜻함이다. 완료총소비는 자기마지막AVAILABLE까지 기저포함이며 공통AP/소비창은 같은입력의 원EDF 종료시각이다. 미완료 행은 남기고 공동우위 선정에서만 제외했다. 3seed 평균의 건수 분모는 같은입력의3회평가를 합친 값이지 새독립실측3회가 아니다.\n\n'+table(comparison)+'\n## 모든seed·중간16·포화4\n\n'+table(summaries)+'\n## 모든682행과 선정제외 사유\n\n'+full+'\n## 한계·이전결과 보존\n\n기존[1254행/실패·중단](../WITNESS_CLOSEOUT_20261018_01/REPORT.md)과 [중단 열계수439START/438COMPLETE/중단1](../THERMAL_COEFFICIENTS_20261018_01/USER_STOP.json)을 보존했다. 이미 본30입력·유한8TRAIN/4update/seed의 진단이며 통계유의성·수렴·새도착분포 일반화·온라인최적·실기기우위를 주장하지 않는다. WAIT/상세예측의 휴대전화 제어소비·지연은 미측정이다. S26의6.654%와 다른기기·경로·모형·평가창이므로 직접 개선율을 비교하지 않는다. 나쁜결과/미완료/학습행/제외사유를 삭제하지 않았다. 잔여예약 자동실행0이다.\n'
    (out/'REPORT.md').write_text(text,encoding='utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=[s['policy'].replace('_3SEED_MEAN','').replace('FROZEN_EVENT_JOINT','Old RL').replace('PACKING_PUBLIC','Public') for s in comparison];fig,axs=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    vals=[[s['on_percent'] for s in comparison],[s['urgent_percent'] for s in comparison],[s['EDF']['completion_saving_percent'] for s in comparison],[s['EDF']['mean_AP_delta_c'] for s in comparison]]
    for ax,v,title in zip(axs.flat,vals,['All-arrival on-time (%)','Urgent on-time (%)','Completion energy saving vs EDF (%)','Mean AP minus EDF (C)']):ax.bar(names,v);ax.tick_params(axis='x',rotation=55,labelsize=8);ax.set_title(title);ax.grid(axis='y',alpha=.25)
    fig.suptitle('A24 public-policy transfer: fixed physics, paired 30 inputs\nBC anchors and 3-seed staged PPO; model proxies, no device validation');fig.savefig(out/'COMPARISON.png',dpi=160);fig.savefig(out/'COMPARISON.svg');plt.close(fig)
    note='## 2026-10-18 S26 공개정책 단계별 A24 실험 완료\n\n[모든결과](../a24_simulator/results/PUBLIC_TRANSFER_20261018_01/REPORT.md). 신규562환경/3BCfit/96TRAIN/48PPO와 원BASE120저장일정의 새감사를 마쳤다. FIFO/EDF/공개규칙/원NN/BC고정3개/4단계×3seed의 전체30·중간16·포화4와 모든682행/손해/제외비고를 보존했다. 원물리/도착/납기/latent·CPU1GPU1불변·새CPU3/NPU/실측/fit/LP0이며 수렴/실기기우위 미주장이다. 중단 열계수439START는 재개하지 않았다. 다음은결과해석/공유·잔여예약 자동실행0이다.\n\n'
    for n in ('PROJECT_STATUS.md','PROJECT_PLAN.md','DECISIONS.md'):
        p=REPO/'docs'/n;p.write_text(note+p.read_text(encoding='utf8'),encoding='utf8')
    cont=ROOT/'CONTINUE.json';state=read(cont);state['previous_comparison']=state.get('current_comparison');state['current_comparison']=op['output_dir']+'/REPORT.md';state['maintainer_read_first']=state['current_comparison'];state['status']='COMPLETED_PUBLIC_TRANSFER_STAGED_20261018';cont.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for n in ('README.md','docs/HANDOFF.md','docs/LATEST_EXECUTION_FILES.md'):
        p=ROOT/n;link=op['output_dir']+'/REPORT.md' if n=='README.md' else '../'+op['output_dir']+'/REPORT.md';p.write_text('최신: [S26 공개정책 보완의 A24 단계별 FIFO/EDF 비교]('+link+'). 모든seed·BC고정·손해·제외사유를 보존한다.\n\n'+p.read_text(encoding='utf8'),encoding='utf8')
    files=[p for p in out.iterdir() if p.is_file()]+[p for p in HERE.iterdir() if p.is_file()]+[REPO/'docs'/n for n in ('PROJECT_STATUS.md','PROJECT_PLAN.md','DECISIONS.md')]+[ROOT/n for n in ('CONTINUE.json','README.md','docs/HANDOFF.md','docs/LATEST_EXECUTION_FILES.md')]
    save(out/'FINAL_HANDOFF_PROOF.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),files=[dict(path=str(p.relative_to(REPO)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)) for p in files]));print(json.dumps(dict(status='PUBLIC_TRANSFER_REPORTED',summary=comparison),ensure_ascii=False))
if __name__=='__main__':main()
