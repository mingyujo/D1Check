"""Descriptive PC report; no fit, policy tuning, or new simulation."""
import argparse
import csv
import gzip
import html
import json
from pathlib import Path

from tools import d1_industrial_scheduling as x
from tools import d1_scheduler_alternatives as existing


def energy_at(segments,t,initial,frozen):
    value=t*initial['preload_power_w']
    for s in segments:
        if s['state']=='idle': continue
        if s['state'] not in frozen['energy_increment_w']: raise ValueError('unsupported power state')
        value+=max(0.,min(t,s['end_s'])-max(0.,s['start_s']))*frozen['energy_increment_w'][s['state']]
    return value


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def read_records(output):
    out=Path(output);plain=out/'records.jsonl'
    if plain.exists():
        raw=plain.read_bytes()
        (out/'records.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
    else:
        raw=gzip.decompress((out/'records.jsonl.gz').read_bytes())
    return [json.loads(line) for line in raw.decode('utf8').splitlines()]


def build(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(output)
    records=read_records(out)
    registered=json.loads((out/'registered_before_run.json').read_text(encoding='utf8'))
    for file,digest in registered['hashes'].items():
        if x.p.digest(x.p.ROOT/file)!=digest: raise ValueError('report source/frozen mismatch '+file)
    data=json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial']
    summary=json.loads((out/'summary.json').read_text(encoding='utf8'))
    pairs=[]; exposure=[]; curves=[]; request_deltas=[]; bounds=[]
    refs={(d['meta']['envelope'],d['meta']['scenario']):d for d in records if d['meta']['policy']=='EFT_REFERENCE'}
    all_metrics=[]
    for d in records:
        m=d['meta'];ref=refs[m['envelope'],m['scenario']];r=ref['meta']
        if m['planned']!=8 or len(d['ledger'])!=8: raise ValueError('full denominator')
        if m['completed']!=8: raise ValueError('incomplete calculation: do not render complete curves')
        if len(d['predicted_ap_path'])!=146: raise ValueError('AP common query grid')
        if abs(energy_at(d['segments'],120.,initial,frozen)-m['energy_j'])>1e-7:
            raise ValueError('energy accounting duplication/missing interval')
        p95=sorted(q['response_ns']/1e6 for q in d['ledger'] if q['priority']=='urgent')[-1]
        if abs(p95-m['urgent_p95_ms'])>1e-7: raise ValueError('small-n P95 consistency')
        peak=max(d['predicted_ap_path'])
        if abs(peak-m['peak_ap_c'])>1e-10: raise ValueError('peak consistency')
        all_metrics.append(dict(m))
        bound=existing.energy_lower_bound(data['cases'][m['envelope']]['tickets'],frozen,initial,m['scenario'])
        gap=m['energy_j']-bound['lower_bound_j']
        if gap < -1e-7: raise ValueError('energy lower-bound violation')
        bounds.append(dict(envelope=m['envelope'],scenario=m['scenario'],policy=m['policy'],
            relaxed_lower_bound_j=bound['lower_bound_j'],gap_j=gap,
            tight_within_numeric_1e_6_j=abs(gap)<=1e-6,
            scope='same linear power/scenario/full120work relaxation; not AP or device optimality'))
        if m['policy']!='EFT_REFERENCE':
            diffs=[b-a for a,b in zip(ref['predicted_ap_path'],d['predicted_ap_path'])]
            pairs.append(dict(envelope=m['envelope'],scenario=m['scenario'],policy=m['policy'],
                information=m['information'],deadline_met=m['deadline_met'],
                delta_j=m['energy_j']-r['energy_j'],relative_j_pct=100*(m['energy_j']-r['energy_j'])/r['energy_j'],
                delta_peak_ap_c=peak-r['peak_ap_c'],max_absolute_ap_path_difference_c=max(map(abs,diffs)),
                delta_urgent_p95_ms=m['urgent_p95_ms']-r['urgent_p95_ms'],
                delta_normal_mean_ms=m['normal_mean_ms']-r['normal_mean_ms'],
                same_lane_ledger=all((q['backend'],q['dispatch_ns'],q['lane_available_ns'])==
                    (z['backend'],z['dispatch_ns'],z['lane_available_ns']) for q,z in zip(d['ledger'],ref['ledger']))))
            for q,z in zip(d['ledger'],ref['ledger']):
                if q['id']!=z['id']: raise ValueError('request pairing')
                request_deltas.append(dict(envelope=m['envelope'],scenario=m['scenario'],policy=m['policy'],
                    ordinal=q['ordinal'],task=q['task'],arrival_s=q['arrival_ns']/1e9,
                    backend=q['backend'],eft_backend=z['backend'],
                    dispatch_delta_ms=(q['dispatch_ns']-z['dispatch_ns'])/1e6,
                    response_delta_ms=(q['response_ns']-z['response_ns'])/1e6,
                    lane_release_delta_ms=(q['lane_available_ns']-z['lane_available_ns'])/1e6))
        for state in ('idle',*sorted(frozen['energy_increment_w'])):
            duration=sum(max(0.,min(120.,s['end_s'])-max(0.,s['start_s'])) for s in d['segments'] if s['state']==state)
            power=0. if state=='idle' else frozen['energy_increment_w'][state]
            exposure.append(dict(envelope=m['envelope'],scenario=m['scenario'],policy=m['policy'],
                state=state,occupancy_s=duration,incremental_energy_j=duration*power,
                baseline_whole120_j=initial['preload_power_w']*120))
        for t in range(181):
            curves.append(dict(envelope=m['envelope'],scenario=m['scenario'],policy=m['policy'],time_s=t,
                predicted_cumulative_j=energy_at(d['segments'],t,initial,frozen) if t<=120 else None,
                predicted_ap_c=d['predicted_ap_path'][t-35] if t>=35 else None,
                observed_j=None,observed_ap_c=None,evidence='PC model calculation; no new measurement'))
    write_csv(out/'comparisons.csv',pairs);write_csv(out/'state_exposure.csv',exposure)
    write_csv(out/'request_deltas.csv',request_deltas);write_csv(out/'curves.csv',curves)
    write_csv(out/'energy_bound_check.csv',bounds)

    chosen=[d for d in records if d['meta']['envelope']==x.CASES[-1] and d['meta']['scenario']=='mean']
    colors=['#64748b','#c2410c','#15803d','#2563eb','#9333ea']
    names=['EFT','ATC + queue guard','CPU bottleneck + guard','Offline J reference','Offline AP reference']
    fig,axes=plt.subplots(5,1,figsize=(11,13),layout='constrained')
    for index,(d,col,name) in enumerate(zip(chosen,colors,names)):
        for row in d['ledger']:
            y=2*index+(row['backend']=='GPU')
            axes[0].broken_barh([(row['dispatch_ns']/1e9,(row['lane_available_ns']-row['dispatch_ns'])/1e9)],
                (y-.35,.7),facecolors=col,alpha=.9)
            axes[0].text(row['dispatch_ns']/1e9,y,str(row['ordinal']),fontsize=7,va='center')
        ts=range(121)
        axes[1].plot(ts,[energy_at(d['segments'],t,initial,frozen) for t in ts],color=col,label=name)
        axes[2].plot(ts,[energy_at(d['segments'],t,initial,frozen)-energy_at(chosen[0]['segments'],t,initial,frozen) for t in ts],color=col,label=name)
        axes[3].plot(range(35,181),d['predicted_ap_path'],color=col,label=name)
        axes[4].plot(range(35,181),[a-b for a,b in zip(d['predicted_ap_path'],chosen[0]['predicted_ap_path'])],color=col,label=name)
    axes[0].set_yticks(range(10),[f'{name} {b}' for name in names for b in ('CPU','GPU')]);axes[0].set_xlim(34.95,38.)
    axes[0].set_title('PC schedules: 8-ticket prefix, burst, mean service (not phone measurements)')
    axes[1].set(xlabel='Common time (s)',ylabel='Predicted cumulative J',xlim=(0,120))
    axes[2].set(xlabel='Common time (s)',ylabel='Cumulative J difference vs EFT',xlim=(0,120))
    axes[3].set(xlabel='Common time (s)',ylabel='Predicted AP (C)',xlim=(35,180))
    axes[4].set(xlabel='Common time (s)',ylabel='AP difference vs EFT (C)',xlim=(35,180))
    for ax in axes: ax.grid(alpha=.2)
    axes[1].legend(fontsize=8,ncol=2)
    fig.savefig(out/'burst_mean.png',dpi=140);fig.savefig(out/'burst_mean.svg');plt.close(fig)
    # Matplotlib leaves spaces at SVG path line ends; normalize generated
    # formatting only, preserving path coordinates and registered model data.
    svg=out/'burst_mean.svg'
    svg.write_bytes(('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n').encode('utf8'))

    means=[m for m in all_metrics if m['scenario']=='mean']
    def label(env):return dict(zip(x.CASES,('low prefix','queue prefix','burst prefix')))[env]
    table=[]
    for m in means:
        r=refs[m['envelope'],m['scenario']]['meta']
        table.append('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in (
            label(m['envelope']),m['policy'],f"{m['deadline_met']}/8",f"{m['energy_j']:.6f}",
            f"{m['energy_j']-r['energy_j']:+.6f}",f"{m['peak_ap_c']-r['peak_ap_c']:+.6f}",
            f"{m['urgent_p95_ms']:.3f}",f"{m['normal_mean_ms']:.3f}"))+'</tr>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>산업공학 스케줄링 PC 비교</title>
<style>body{max-width:1200px;margin:32px auto;padding:0 20px;font:16px/1.6 system-ui;color:#17243b}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ccd3dd;padding:8px}img{width:100%}.note{background:#fff4dd;padding:16px}a{color:#245aca}</style>
<h1>산업공학 방식의 제한 비교</h1><p>저장된 세 입력의 첫8요청 × 처리시간3문맥. 온라인27계산 + offline 일정18재생. 새 실측 없음.</p>
<div class="note">모형 계산과 실기기 검증을 구분합니다. 평균 처리시간은 온라인 추정, short/long은 고정된 PC 실현 민감도입니다. Offline은 미래 도착과 해당 처리시간을 아는 참고값이며 beam 탐색의 최적성 증명은 없습니다. 입력·초기 조건은 이미 본 자료라 사후 탐색입니다.</div>
<p>모든 경우8/8 기한 충족. burst에서 ATC/병목은 EFT 대비 약−0.135J(−0.10%)지만 긴급P95 약+417ms. queue의 병목은 약−0.043J/일반평균−110ms. low는 동일합니다.</p>
<p>AP 최고값은 모두180초 끝에서 나오며 유효 유휴 기준보다 낮아 양의 열부담은0입니다. 따라서 이 작은 입력의 AP 최고값 차이를 열 절감 효과로 쓰지 않습니다. burst의 경로 차이는 최대 약0.143°C입니다.</p>
<table><tr><th>입력</th><th>방식</th><th>기한</th><th>J 0–120</th><th>ΔJ vs EFT</th><th>Δ최고AP</th><th>긴급P95 ms</th><th>일반평균 ms</th></tr>'''+''.join(table)+'''</table>
<h2>저장 PC 일정과 모형 경로</h2><img src="burst_mean.png" alt="PC lane schedules, cumulative predicted energy, predicted AP and AP differences"><p>CPU/GPU 점유는 dispatch→lane_available. AP는35–180초, J는0–120초. 관측 곡선이 아닙니다.</p>
<p><a href="comparisons.csv">모든 문맥의 상대차</a> · <a href="request_deltas.csv">요청별 변화</a> · <a href="state_exposure.csv">상태 점유/에너지</a> · <a href="curves.csv">계산 곡선</a> · <a href="energy_bound_check.csv">기존 에너지 완화 하한 대조</a> · <a href="reference_search.json">탐색 범위/절단</a> · <a href="../README.md">근거·한계·재현</a></p>
<p>Strict 지원·experiment_ready=false·동결 계수 유지. 온라인 B2·폰 절감·열 피드백 정책의 우월성을 검증한 결과가 아닙니다.</p></html>'''
    (out/'index.html').write_text(page,encoding='utf8')
    verification=dict(records=len(records),requests=sum(len(d['ledger']) for d in records),
        full_energy_accounting=True,all_deadline_met=sum(d['meta']['deadline_met'] for d in records),
        online_requests=sum(len(d['ledger']) for d in records if d['meta']['information']=='online_arrived_queue'),
        all_positive_ap_burden_zero=all(d['meta']['thermal_degree_seconds']==0 for d in records),
        all_peak_time_s=[35+d['predicted_ap_path'].index(max(d['predicted_ap_path'])) for d in records],
        candidate_same_as_EFT_cases={pol:sum(v['same_lane_ledger'] for v in pairs if v['policy']==pol) for pol in (x.ATC,x.BOTTLENECK)},
        source_hashes_preserved=True,device_commands=0,strict_supported=False,experiment_ready=False,
        report_sources={file.relative_to(x.p.ROOT).as_posix():x.p.digest(file) for file in (Path(__file__),Path(existing.__file__))})
    x.p.write(out/'report_verification.json',verification)
    return pairs,exposure,bounds


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();build(args.output)
