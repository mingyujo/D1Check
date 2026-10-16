"""Fresh design report and append-only old learning-channel label erratum."""
import csv,gzip,hashlib,json,statistics
from pathlib import Path
from tools import d1_service_joint_rl_run as x

def table(path,rows):
    keys=list(dict.fromkeys(k for q in rows for k in q))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def erratum():
    folder=x.ROOT/'docs/results/overnight_rl_20261011';before=folder/'learning_updates.csv';after=folder/'learning_updates_corrected_labels.csv'
    mapping=dict(lambda_urgent_misses='lambda_incomplete',lambda_normal_misses='lambda_urgent_failure',lambda_urgent_p95='lambda_normal_failure',lambda_completion='lambda_urgent_P95')
    with before.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    corrected=[{mapping.get(k,k):v for k,v in q.items()} for q in rows];table(after,corrected)
    record=dict(status='corrected_labels_only_original_preserved',original_sha256=x.sha(before),corrected_sha256=x.sha(after),column_mapping=mapping,
        actual_old_cost_ABI=['signed_J_difference_vs_L0','positive_incomplete_count_difference_vs_L0','positive_urgent_failure_count_difference_vs_L0','positive_normal_failure_count_difference_vs_L0','positive_P95_difference_vs_L0_over1500ms'],unchanged_numeric_cells=True,old_training_and_weights_changed=False,
        old_objective_note='old service costs positive difference vsL0; ABI position unchanged, this correction does not change old objective toabsolute',energy_column_was_already_correct=True)
    x.write(folder/'learning_channel_labels_erratum.json',record);return record

def run():
    reg=x.check();z=x.read(x.LOCAL/'completion.json');rows=z['rows'];table(x.PUBLIC/'comparison.csv',rows);summaries=[];choices=[];updates=[];inventory=[]
    for role in dict.fromkeys(q['policy'] for q in rows if q.get('scope')=='confirmation'):
        s=[q for q in rows if q.get('scope')=='confirmation' and q['policy']==role]
        summaries.append(dict(policy=role,conditions=len(s),planned=sum(q['planned'] for q in s),completed=sum(q['completed'] for q in s),urgent_failure=sum(q['urgent_failure'] for q in s),normal_failure=sum(q['normal_failure'] for q in s),mean_P95=statistics.mean(q['urgent_p95_ms'] for q in s),mean_J=statistics.mean(q['energy_j'] for q in s),mean_AP=statistics.mean(q['peak_ap_c'] for q in s)))
    for q in rows:
        ident=(f'final_{q["policy"]}_{q["condition"]:02d}' if q.get('scope')=='confirmation' else f'dev_{q["policy"]}_{q["condition"]:02d}')
        raw=json.loads(gzip.decompress((x.LOCAL/'items'/(ident+'.json.gz')).read_bytes()));ss=raw['snapshots'];x.old.x.previous.audit(raw['result'],x.read(x.LOCAL/'inputs.json')['confirmation' if q.get('scope')=='confirmation' else 'development'][q['condition']]['tickets'])
        choices.append(dict(policy=q['policy'],scope=q.get('scope','development'),condition=q['condition'],decisions=len(ss),multiple_choices=sum(sum(v['mask'])>1 for v in ss),slot0=sum(v['chosen']==0 for v in ss),non_reference=sum(v['chosen']!=0 for v in ss),cooling=sum(v['actions'][v['chosen']]['kind']=='cool_wait' for v in ss),resource_wait=sum(v['actions'][v['chosen']]['kind']=='resource_wait' for v in ss)))
    for seed in x.SEEDS:
        log=x.read(x.LOCAL/f'learning_{seed}.json');ep=log['accepted_episodes'];path=x.LOCAL/'checkpoints'/f'seed{seed}_ep{ep}.pt';payload=x.r.torch.load(path,map_location='cpu',weights_only=False)
        inventory.append(dict(seed=seed,episodes=ep,updates=payload['update_count'],Adam_steps=payload['optimizer_steps'],sha256=x.sha(path),schema_id=payload['schema_id'],pending=len(payload['pending_episodes']),fresh_weights=True))
        for v in log['updates']:updates.append(dict(seed=seed,episodes=v['accepted_episodes'],update=v['update'],informative=v['sampled_choices'],lambda_J=v['lambda_after'][0],lambda_incomplete=v['lambda_after'][1],lambda_urgent_failure=v['lambda_after'][2],lambda_normal_failure=v['lambda_after'][3],lambda_P95=v['lambda_after'][4],actor_gradient_max=max(p['gradients']['actor'] for p in v['steps']),Adam_steps=v['optimizer_steps_cumulative']))
    table(x.PUBLIC/'summary.csv',summaries);table(x.PUBLIC/'choices.csv',choices);table(x.PUBLIC/'learning_updates.csv',updates);x.write(x.PUBLIC/'checkpoint_inventory.json',inventory)
    x.write(x.PUBLIC/'result.json',dict(status='completed',summary=summaries,consumption=z['consumption'],objective=reg['objective'],original_gate_changed=False,automatic_adoption=False,not_algorithm_superiority=True))
    x.write(x.PUBLIC/'verification.json',dict(status='PASS_source_input_model_and_response_lane_audits',source_sha256=reg['source_sha256'],label_only_revision=x.read(x.LOCAL/'label_only_revision.json'),inventory=inventory,new_device_commands=0,oldweights_modified=False))
    table_rows=''.join(f'<tr><td>{q["policy"]}</td><td>{q["normal_failure"]}</td><td>{q["mean_P95"]:.3f}</td><td>{q["mean_J"]:.6f}</td><td>{q["mean_AP"]:.6f}</td></tr>' for q in summaries)
    (x.PUBLIC/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>공동 리스트 fresh PPO</title><style>body{font:18px Arial;max-width:1100px;margin:35px auto}td,th{padding:14px;border-bottom:1px solid #ccc}</style><h1>공동 서비스 리스트 기반 새 PPO</h1><p>새 schema·weights·absolute 서비스 비용. 기존512 연장과 알고리즘 우열 비교가 아니다. 원실측/계수/최종판정은 유지.</p><table><tr><th>정책</th><th>일반실패</th><th>조건P95 평균ms</th><th>평균J</th><th>평균최고AP°C</th></tr>'+table_rows+'</table><p>Joint/Cost와같은833확인48. 성적표 원단위로판정하며 자동채택0·기기0이다.</p><p><a href="comparison.csv">전체CSV</a> · <a href="choices.csv">선택/기회</a> · <a href="learning_updates.csv">실제학습</a></p></html>',encoding='utf-8')
    print(json.dumps(dict(summary=summaries,consumption=z['consumption'],checkpoints=inventory),ensure_ascii=False,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('command',choices=('erratum','report'));a=p.parse_args();erratum() if a.command=='erratum' else run()
