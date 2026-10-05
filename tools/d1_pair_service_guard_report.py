"""Saved guard experiment accounting and first-burst diagnosis; no reruns."""
import argparse
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import statistics
from tools import d1_pair_service_guard as g
from tools.d1_scheduler_conditions_report import read,group_result
p=g.p


def report(folder):
    out=Path(folder);contract=json.loads((out/'contract_before_run.json').read_text())
    for path,sha in contract['hashes'].items():assert p.digest(p.ROOT/path)==sha,path
    rows=read(out/'results.csv');index={(r['stage'],int(r['seed']),r['scenario'],r['policy']):r for r in rows}
    expected={(stage,seed,sc,pol) for stage,seeds in [('reproduction',[123001,123002]),('fresh',[124001,124002])]
        for seed in seeds for sc in g.s.a.old.SCENARIOS for pol in contract['spec']['policies']}
    assert set(index)==expected and len(rows)==36
    f,case=p.inputs(p.BUNDLE);initial=case['initial'];seen=set();maxdiff=0.;requests=0;rep={};guardrows=[]
    with (out/'local_records.jsonl').open(encoding='utf8') as stream:
        for line in stream:
            d=json.loads(line);r=d['meta'];ledger=d['ledger'];key=(r['stage'],r['seed'],r['scenario'],r['policy'])
            assert key not in seen;seen.add(key);assert len(ledger)==48;requests+=48
            for z in ledger:
                times=[z[k] for k in ('dispatch_ns',*g.s.a.old.engine.FIELDS)]
                assert times==sorted(times) and times[0]>=z['arrival_ns']
            for b in ('CPU','GPU'):
                jobs=sorted([z for z in ledger if z['backend']==b],key=lambda z:z['dispatch_ns'])
                assert all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:]))
            urgent=sorted(z['response_ns']/1e6 for z in ledger if z['priority']=='urgent')
            normal=[z['response_ns']/1e6 for z in ledger if z['priority']=='normal']
            metrics=dict(urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1],normal_mean_ms=statistics.mean(normal))
            rr,(segments,_,_,_)=g.rl.outcome(dict(ledger=ledger,metrics=metrics),initial,f)
            for field,v in rr.items():
                if field in ('actions','controllable_decisions'):continue
                w=index[key][field];assert (v is None and w is None) or abs(v-w)<1e-8,(key,field)
            j=120*initial['preload_power_w']+sum(max(0,min(120,z['end_s'])-z['start_s'])*f['energy_increment_w'][z['state']] for z in segments if z['state']!='idle')
            maxdiff=max(maxdiff,abs(j-r['energy_j']))
            for x in d['guard']:
                assert x['veto']==bool(g.worsens(x['proposed_lateness_s'],x['reference_lateness_s']))
                if x['veto']:
                    guardrows.append(dict(stage=r['stage'],seed=r['seed'],scenario=r['scenario'],now_s=x['now_ns']/1e9,
                        proposal_reason=x['proposal']['reason'],worsened_ids=x['worsened_ids'],
                        proposal_backend=x['proposal']['chosen_backend'],reference_backend=x['reference']['chosen_backend']))
            if r['seed']==123001 and r['scenario']=='mean':rep[r['policy']]=ledger[:8]
    assert seen==expected and maxdiff<1e-8
    comparisons=[]
    for stage in ('reproduction','fresh'):
        for pol in ('PAIR_COALESCE_V1',g.ID):
            xs=[r for r in rows if r['stage']==stage and r['policy']==pol]
            for ref in ('EFT_REFERENCE','PAIR_COALESCE_V1'):
                if ref==pol:continue
                bs=[index[stage,int(r['seed']),r['scenario'],ref] for r in xs]
                comparisons.append(dict(stage=stage,policy=pol,reference=ref,**group_result(xs,bs)))
    g.s.save_rows(out/'comparison.csv',comparisons);g.s.save_rows(out/'veto_events.csv',guardrows)
    old=read(out/'original_request_decomposition.csv');miss=[r for r in old if r['missed']=='True']
    assert len(miss)==16
    for r in old:
        assert abs(r['response_ms']-r['wait_ms']-r['own_response_ms'])<1e-6
        assert abs(r['response_delta_ms']-(r['wait_ms']-r['eft_wait_ms'])-(r['own_response_ms']-r['eft_own_response_ms']))<1e-6
    decomposition=dict(missed_requests=16,all_classification=all(r['task']=='classification' for r in miss),
        mean_extra_wait_ms=statistics.mean(r['wait_ms']-r['eft_wait_ms'] for r in miss),
        mean_extra_own_response_ms=statistics.mean(r['own_response_ms']-r['eft_own_response_ms'] for r in miss),
        mean_extra_response_ms=statistics.mean(r['response_delta_ms'] for r in miss),
        note='arithmetic decomposition, not a physical causal attribution; queue delay includes prior policy choices')
    p.write(out/'decomposition.json',decomposition)
    p.write(out/'verification.json',dict(result='PASS',utc=datetime.now(timezone.utc).isoformat(),base_head=contract['spec']['base_head'],
        uncommitted=True,ledgers=36,requests=requests,original_reproduction_ledgers=12,raw_sha256=p.digest(out/'local_records.jsonl'),
        source_and_physical_hashes_unchanged=True,max_energy_accounting_difference_j=maxdiff,device_commands=0))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(3,1,figsize=(11,7),sharex=True)
    for ax,(policy,ledger) in zip(axs,rep.items()):
        for z in ledger:
            y=0 if z['backend']=='CPU' else 1;a=z['dispatch_ns']/1e9-35;b=z['lane_available_ns']/1e9-35
            color='#bc8738' if z['task']=='detection' else '#29877d'
            ax.broken_barh([(a,b-a)],(y-.25,.5),facecolors=color)
            ax.text((a+b)/2,y,str(z['ordinal']),ha='center',va='center',color='white',fontsize=8)
            ax.plot((z['arrival_ns']+z['response_ns'])/1e9-35,y,'k.',markersize=5)
            if z['priority']=='urgent':ax.plot((z['arrival_ns']+z['deadline_offset_ns'])/1e9-35,y,'rx',markersize=5)
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(policy);ax.set_ylim(-.6,1.6)
    axs[-1].set_xlabel('Seconds since first arrival; bars end at lane_available; dot=response, red x=deadline')
    fig.suptitle('First burst / seed123001 mean / simulated, not device measurement');fig.tight_layout();fig.savefig(out/'first_burst.png',dpi=140);plt.close(fig)
    table=''.join('<tr>'+''.join(f'<td>{r[k]:.6f}</td>' if isinstance(r[k],float) else f'<td>{r[k]}</td>' for k in
        ('stage','policy','reference','deadline_met','planned','mean_delta_energy_j','mean_delta_peak_ap_c','mean_delta_urgent_p95_ms'))+'</tr>' for r in comparisons)
    (out/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>대기열 기한 보호</title><style>body{max-width:1200px;margin:32px auto;font:16px/1.6 sans-serif}td,th{border:1px solid #ccc;padding:5px}table{border-collapse:collapse}img{width:100%}</style><h1>병행 만들기보다 도착한 요청의 기한을 먼저 검사</h1><p>같은 실패 부하의 사후 보호계층. 기존 정책/물리모형 불변. 새seed는 같은 부하분포 PC 확인이며 미래 도착/실기기 기한 보장 아님.</p><img src="first_burst.png" alt="실패 조건의 실제 시뮬레이션 lane 점유"><table><tr><th>자료</th><th>정책</th><th>기준</th><th>기한충족</th><th>분모</th><th>ΔJ</th><th>Δ최고AP</th><th>Δ긴급P95 ms</th></tr>'''+table+'''</table><p>J 0–120초/AP 35–180초. 새로운 장치 관측/공동절감 PASS 아님.</p><a href="../README.md">판독·제약·재현</a> · <a href="original_request_decomposition.csv">원 실패16요청 분해</a> · <a href="veto_events.csv">거부 경계</a></html>''',encoding='utf8')
    print(json.dumps(dict(decomposition=decomposition,comparison=comparisons),indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--folder',required=True);args=ap.parse_args();report(args.folder)
