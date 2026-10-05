"""Frozen selector confirmation: retained tradeoffs, not a fitted winner."""
import argparse
import csv
import json
from pathlib import Path
from tools import d1_scheduler_conditions as s
from tools.d1_scheduler_conditions_report import read
p=s.p


def load_curves(folder):
    curves=json.loads((folder/'representative_curves.json').read_text())
    if curves:return curves
    # The first selector runner exported a fixed old seed. Recover the same
    # preregistered envelope from actual saved ledgers for the active seed set;
    # no new simulation, coefficient fitting or replacement measurement.
    freeze=json.loads((folder/'freeze_before_confirmation.json').read_text())
    seed=freeze['spec']['seeds'][0]
    frozen,case=p.inputs(p.BUNDLE)
    for line in (folder/'local_ledgers.jsonl').open(encoding='utf8'):
        item=json.loads(line);m=item['meta']
        if m['envelope']=='g0.45_c0.75_b4' and m['seed']==seed and m['scenario']=='mean':
            seg,costs,end=p.account(dict(ledger=item['ledger']),case['initial'],frozen)
            if end!=180:raise ValueError('representative incomplete; no invented curve')
            curves.append(dict(policy=m['policy'],energy_path=costs['energy_path'],ap_path=costs['ap_path'],segments=seg))
    if not curves:raise ValueError('no registered representative ledger')
    p.write(folder/'representative_curves_recovered.json',curves)
    return curves


def report(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=Path(folder);rows=list(csv.DictReader((folder/'selector_confirmation.csv').open()))
    summary={}
    for mode in ('energy','thermal'):
        summary[mode]={}
        for ref in s.a.BASELINES[1:]:
            xs=[r for r in rows if r['mode']==mode and r.get('reference')==ref]
            summary[mode][ref]=dict(evaluated_envelopes=len(xs),all_deadline_envelopes=sum(r['all_deadlines']=='True' for r in xs),
                joint_gain_envelopes=sum(r['joint_nonworse_gain']=='True' for r in xs),
                all_cases_both_lower_envelopes=sum(r['all_cases_J_and_heat_lower']=='True' for r in xs))
    p.write(folder/'mode_summary.json',summary)
    curves=load_curves(folder)
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    reference=next(x for x in curves if x['policy']=='SPLIT_REFERENCE')['energy_path']
    for x in curves:
        axes[0].plot([r['common_s'] for r in x['energy_path']],[r['predicted_j'] for r in x['energy_path']],label=x['policy'])
        axes[1].plot([r['common_s'] for r in x['energy_path']],
            [r['predicted_j']-b['predicted_j'] for r,b in zip(x['energy_path'],reference)],label=x['policy'])
        axes[2].plot(range(35,35+len(x['ap_path'])),x['ap_path'],label=x['policy'])
    axes[0].set(xlabel='Seconds',ylabel='Predicted whole-device J',title='Common 0-120s; includes resident baseline')
    axes[1].set(xlabel='Seconds',ylabel='Predicted J difference',title='Candidate - fixed split cumulative J')
    axes[1].axhline(0,color='grey',lw=.5)
    axes[2].set(xlabel='Seconds',ylabel='Predicted AP C',title='AP path 35-180s')
    axes[2].legend(fontsize=7)
    fig.suptitle('Frozen mode confirmation: gap0.45s / classification75% / burst4 / seed112001 / mean\nSimulation only; measured coefficients + service transfer assumption')
    for ext in ('png','svg'):fig.savefig(folder/f'mode_paths.{ext}',dpi=160)
    plt.close(fig)
    table=''.join(f'<tr><td>{m}</td><td>{ref}</td><td>{x["evaluated_envelopes"]}</td><td>{x["all_deadline_envelopes"]}</td><td>{x["joint_gain_envelopes"]}</td></tr>' for m,refs in summary.items() for ref,x in refs.items())
    (folder/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>목적별 조건 선택 확인</title>
<style>body{font-family:system-ui;max-width:1100px;margin:30px auto;line-height:1.6}img{width:100%}td,th{padding:10px;border-bottom:1px solid #ccc}</style>
<h1>에너지 우선·최고 AP 우선: 다른 답을 그대로 남기는 선택기</h1><p>실제 측정 결과가 아닌 PC 예측입니다. 개발에서 사전 지정 입력 조건별 정책을 선택하고 새 seed112001–112003으로 확인했습니다. 전체 27조건 중 개발 기한 적격 정책이 없던 조건은 선택 불가로 남겼습니다. 아래 공동 개선은 J·최고 AP·AP 면적의 비교이며 실기기 정확도 PASS가 아닙니다.</p>
<p><a href="../README.md">종합 보고서</a> | <a href="selector_confirmation.csv">모든 선택·실패·상충</a> | <a href="../run_v2/index.html">27조건 전체 정책 지도</a></p>
<table><tr><th>목적</th><th>비교 기준</th><th>평가 조건</th><th>모든 기한 충족</th><th>공동 개선 조건</th></tr>'''+table+'''</table><img src="mode_paths.png" alt="새 seed 대표 조건의 모델 경로"><p>급한 요청1.5초·일반6초의 전체 기한을 먼저 판정하고 P95 지연은 별도 공개합니다. 숫자를 보고 온도 상한을 새로 만들지 않았으며 S26·BAT·SOC·스로틀 모형으로 확대하지 않습니다. experiment_ready=false.</p></html>''',encoding='utf8')
    svg=folder/'mode_paths.svg'
    svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);report(parser.parse_args().folder)
