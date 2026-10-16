"""PC-only publication of a terminal resident-identification run; never fits or runs a device."""
import argparse
import csv
import gzip
import hashlib
import html
import json
from pathlib import Path

import numpy as np
from tools import d1_resident_identification_analysis as a


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, v):
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def table(p, rows):
    if not rows:
        return
    with Path(p).open('w', encoding='utf8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader(); w.writerows(rows)


def publish(plan_file, output):
    plan_file = Path(plan_file); plan = read(plan_file); root = Path(plan['output_root'])
    receipt = read(root/'FINAL_RECEIPT.json')  # Active runs must not publish a final result.
    original_file = Path(plan['original_model']['path'])
    if digest(original_file) != plan['original_model']['sha256']:
        raise ValueError('original model changed')
    original = read(original_file)
    frozen = read(root/'development_freeze.json') if (root/'development_freeze.json').exists() else None
    if frozen and digest(root/'development_freeze.json') != read(root/'freeze_receipt.json')['sha256']:
        raise ValueError('candidate freeze changed')
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    sessions = []; metrics = []; curves = []; inputs = []; inventory = {}; segments = []
    for entry in plan['entries']:
        label = f"session_{entry['index']:02d}"
        folder = root/f"{entry['index']:02d}_{entry['session_id']}"
        valid = folder/'validated.json'
        s = dict(session=label, profile=entry['identification_profile'] if 'identification_profile' in entry else '',
                 role='development' if entry['index'] < 4 else 'confirmation',
                 status='unattempted', work_calls=None, eligibility_calls=None, warmup_calls=None, runtimes=None)
        manifest = read(plan_file.parent/entry['manifest']); s['profile'] = manifest['identification_profile']
        if folder.exists():
            s['status'] = 'attempted_not_validated'
        for f in ('validated.json', 'input_manifest.json', 'thermal.jsonl', 'host_cleanup.json',
                  'artifacts/progress.jsonl', 'artifacts/cleanup.json', 'artifacts/start_ap.accepted.json'):
            if (folder/f).is_file():
                inventory[label+'/'+f] = digest(folder/f)
        if not valid.exists():
            sessions.append(s); continue
        stats = read(valid); c = stats['analysis_case']; inputs.append(dict(c, id=label))
        s.update({k:stats.get(k) for k in ('status','work_calls','eligibility_calls','warmup_calls','runtimes','elapsed_seconds')})
        approval = read(folder/'artifacts/start_ap.accepted.json')
        s['start_ap_c'] = approval['ap_c']; s['ap_legacy_start_range_annotation'] = 32.5 <= approval['ap_c'] <= 34.0
        s['strict_support_promoted'] = False
        s['state_exposure_s'] = json.dumps(a.j.m.base.exposure(c['actual'],35,c['common_end_s']).tolist())
        s['host_cleanup_status'] = read(folder/'host_cleanup.json')['status']
        s['app_cleanup_status'] = read(folder/'artifacts/cleanup.json')['status']
        s['ap_samples'] = len(c['q']); s['power_samples'] = len(c['power_t'])
        s['max_ap_gap_s'] = max(np.diff(c['q'])); s['max_power_gap_s'] = max(np.diff(c['power_t']))
        sessions.append(s)
        segments.extend(dict(session=label,**seg) for seg in c['actual'])
        predictions = {'original': a.j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]}
        if frozen:
            predictions['candidate'] = a.j.m.thermal.predict(a.j.m.case_input(c,c['actual']),frozen['model']['ap'])[0]
        def energy(name,t):
            if name == 'original':
                return a.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),t)
            e = frozen['model']['energy']
            return c['pre_w']*t+max(0,t-35)*e['idle_bias_w']+float(a.j.m.base.exposure(c['actual'],0,t)@np.array([e['increments'][k] for k in a.j.m.base.STATES]))
        for name, ap in predictions.items():
            score = dict(session=label,role=s['role'],profile=s['profile'],model=name,
                         assessment=('development_in_sample' if name=='candidate' and s['role']=='development' else
                                     'new_session_confirmation' if name=='candidate' else 'original_protocol_transfer_diagnostic'),
                         ap_start_s=c['q'][0],ap_end_s=c['q'][-1],accuracy_pass=None,
                         **a.j.m.base.common.score(c['ap'],ap),**a.j.h.direction(c,ap))
            for tag,left,right in [('common120',0,120),('registered_reference',0,c['common_end_s']),
                                   ('official_load_window',35,c['common_end_s']),
                                   ('work_span',35,c['last_lane_s']),('post_work',c['last_lane_s'],c['common_end_s'])]:
                observed = a.j.m.integral(c,left,right); predicted = energy(name,right)-energy(name,left)
                score.update({tag+'_start_s':left,tag+'_end_s':right,tag+'_observed_j':observed,
                              tag+'_predicted_j':predicted,tag+'_signed_j':predicted-observed,
                              tag+'_absolute_j':abs(predicted-observed),tag+'_relative_pct':100*(predicted-observed)/observed if observed else None})
            metrics.append(score)
        fig,axes=plt.subplots(2,1,figsize=(10,6.5),sharex=True,constrained_layout=True)
        axes[0].plot(c['q'],c['ap'],label='Observed AP')
        for name,ap in predictions.items():
            axes[0].plot(c['q'],ap,label=name)
            for t,obs,pred in zip(c['q'],c['ap'],ap):
                curves.append(dict(session=label,model=name,kind='AP',t_s=t,observed=obs,predicted=pred,residual=pred-obs))
        axes[0].set_ylabel('AP (C)'); axes[0].legend()
        grid=sorted(set([0.,120.,float(c['common_end_s'])]+list(np.arange(0,c['common_end_s'],5.))))
        observed=[a.j.m.integral(c,0,t) for t in grid]
        axes[1].plot(grid,observed,label='Observed energy')
        for name in predictions:
            pred=[energy(name,t) for t in grid]; axes[1].plot(grid,pred,label=name)
            for t,o,p in zip(grid,observed,pred):
                curves.append(dict(session=label,model=name,kind='cumulative_energy',t_s=t,observed=o,predicted=p,residual=p-o))
        for ax in axes:
            for seg in c['actual']:
                if seg['state']!='idle':ax.axvspan(seg['start_s'],seg['end_s'],alpha=.08,color='gray')
            ax.axvline(35,ls=':',color='black'); ax.grid(alpha=.2)
        axes[1].set_ylabel('Cumulative J'); axes[1].set_xlabel('Reference time (s); load at 35 s, energy curve ends at registered boundary'); axes[1].legend()
        axes[1].set_xlim(0,max(c['q'][-1],c['common_end_s']))
        for ax in axes:ax.axvline(c['common_end_s'],ls='--',color='gray')
        fig.suptitle(label+' '+s['profile']+' | actual schedule conditional; no accuracy PASS')
        fig.savefig(out/(label+'.png'),dpi=140);plt.close(fig)
    table(out/'sessions.csv',sessions);table(out/'metrics.csv',metrics);table(out/'curves.csv',curves);table(out/'states.csv',segments)
    with gzip.open(out/'inputs.json.gz','wt',encoding='utf8') as f:json.dump(inputs,f,allow_nan=False)
    inventory['FINAL_RECEIPT.json']=digest(root/'FINAL_RECEIPT.json')
    if frozen:
        write(out/'candidate.json',dict(model=frozen['model'],development_ids=frozen['development_ids'],
                                      default=False,accuracy_pass=None,experiment_ready=False))
        cv=[]
        for fold in frozen['folds']:
            for name,score in fold['score'].items():cv.append(dict(session=fold['id'],profile=fold['profile'],model=name,**score))
        table(out/'development_holdout.csv',cv)
        inventory['development_freeze.json']=digest(root/'development_freeze.json')
    write(out/'inventory.json',inventory)
    write(out/'summary.json',dict(status=receipt['status'],plan_sha256=digest(plan_file),original_model_sha256=digest(original_file),
         original_model_unchanged=True,candidate_frozen=frozen is not None,completed_sessions=sum(x['status'].startswith('eligible') for x in sessions),
         sessions=sessions,metrics=metrics,experiment_ready=False,accuracy_pass=None,
         prediction_layer='actual_schedule_conditional',end_to_end_verified=False))
    body=''.join('<article><h2>'+html.escape(s['session']+' '+s['profile'])+'</h2><p>'+html.escape(s['role']+' / '+s['status'])+'</p>'+
                 ('<img src="'+s['session']+'.png" style="max-width:100%">' if (out/(s['session']+'.png')).exists() else '<p>유효 비교 자료 없음. 0으로 채우지 않음.</p>')+'</article>' for s in sessions)
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>Resident 식별 실행 결과</title><style>body{max-width:1100px;margin:30px auto;font:16px/1.7 sans-serif}article{border-top:1px solid #bbb}</style><h1>Resident 식별·확인 실행 결과</h1><p>'+html.escape(receipt['status'])+' · 실제 일정 조건부 예측. 개발/확인 분리 · strict/기본 유지 · 정확도 PASS/정책 우월성 아님.</p><p><a href="sessions.csv">전체 8세션 분모</a> · <a href="metrics.csv">오차/구간 표</a> · <a href="curves.csv">곡선 수치</a></p>'+body,encoding='utf8')
    return dict(status=receipt['status'],sessions=len(inputs),output=str(out))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(publish(args.plan,args.output),ensure_ascii=False))
