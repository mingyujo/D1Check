"""Score stored predictions using the unchanged measured windows and retention gates."""
from engine import *
import csv,collections,datetime
spec=importlib.util.spec_from_file_location('accuracy_metrics',E/'simulator_accuracy_rise_fall_20261021/audit.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
O=H/'artifacts/G001';sys.stdout.reconfigure(encoding='utf-8')
KINDS=['BASELINE','HISTGB_RESIDUAL','TREND_BALANCED','MARGIN_BALANCED','MARGIN_STEADY_GUARD']
def point(rows,lo=0):
    stats=[];pts=0
    for r in rows:
        mask=np.array(r['times'])>=lo
        if not any(mask):continue
        err=np.array(r['predicted'])[mask]-np.array(r['observed'])[mask];stats.append([np.mean(abs(err)),np.mean(err*err),np.mean(err)]);pts+=int(sum(mask))
    return dict(sessions=len(stats),points=pts,MAE_C=float(np.mean([x[0] for x in stats])),RMSE_C=float(np.sqrt(np.mean([x[1] for x in stats]))),bias_C=float(np.mean([x[2] for x in stats])))
def main():
    protocol=read(H/'PROTOCOL.json');fit=read(O/'FIT_RESULT.json');original=read(E/'pipeline_thermal_v1/artifacts/G001/OOF_ROWS.json.gz');by={r['id']:r for r in original};previous=read(N/'artifacts/G001/OOF_ROWS.json.gz');trend=[r for r in read(T/'artifacts/G001/OOF_ROWS.json.gz') if r['candidate']=='TREND_BALANCED'];prevby={r['id']:r for r in trend};fresh=read(O/'OOF_ROWS.json.gz');rows=[{**r,'candidate':'BASELINE'} for r in original]+previous+trend+fresh
    assert fit['fit_START']==56 and fit['fit_COMPLETE']+fit['fit_FAIL']==56
    for r in fresh:assert max(abs(np.array(r['baseline'])-prevby[r['id']]['predicted']))<1e-8
    summary=[];points=[];coverage=[];confusion={};allwindows={};session=[]
    for kind in KINDS:
        rr=[r for r in rows if r['candidate']==kind];seen={r['id'] for r in rr};assert len(seen)==len(rr);ww=[]
        for r in rr:
            old=by[r['id']];assert r['times']==old['times'] and r['observed']==old['observed'];ws=A.windows({**r,'parent':old['predicted']})[0];ww.extend(ws)
            err=np.array(r['predicted'])-np.array(r['observed']);late=np.array(r['times'])>=256;rec=dict(candidate=kind,id=r['id'],group=r['group'],pool=r['pool'],overall_MAE=float(np.mean(abs(err))))
            if any(late):rec['late_MAE']=float(np.mean(abs(err[late])))
            for cat,selected in [('ALL',ws),('LATE',[w for w in ws if w['start']>=256])]:
                for cl in ['RISE','FALL','STEADY']:
                    ss=[w for w in selected if w['direction']==cl]
                    if not ss:continue
                    m=A.metrics(ss,'predicted')['session_macro'];rec[cat+'_'+cl+'_MAE']=m['MAE_C'];rec[cat+'_'+cl+'_direction']=m['direction_percent']
            session.append(rec)
        coverage.append(dict(candidate=kind,sessions=len(rr),missing=sorted(set(by)-seen),windows=len(ww)));allwindows[kind]=ww
        for cat in ['ALL','OLD','M8','R21','LATE_GE256']:
            sr=[r for r in rr if cat in ['ALL','LATE_GE256'] or r['pool']==cat or cat=='R21' and r['group'].startswith('M8_R21_')];points.append(dict(candidate=kind,category=cat,**point(sr,256 if cat=='LATE_GE256' else 0)))
            sw=[w for w in ww if cat=='ALL' or w['pool']==cat or cat=='R21' and w['group'].startswith('M8_R21_') or cat=='LATE_GE256' and w['start']>=256]
            for cl in ['ALL','RISE','FALL','STEADY']:summary.append(dict(candidate=kind,category=cat,direction=cl,**A.metrics([w for w in sw if cl=='ALL' or w['direction']==cl],'predicted')))
        for cat,sw in [('ALL',ww),('LATE',[w for w in ww if w['start']>=256])]:
            order=['RISE','FALL','STEADY'];mat=[[sum(w['direction']==a and w['models']['predicted']['predicted_direction']==b for w in sw) for b in order] for a in order];confusion[kind+'__'+cat]=dict(order=order,counts=mat,row_percent=[[100*n/sum(row) for n in row] for row in mat])
    def pt(k,cat='ALL'):return next(v for v in points if v['candidate']==k and v['category']==cat)['MAE_C']
    def wm(k,cl,cat='ALL'):return next(v for v in summary if v['candidate']==k and v['direction']==cl and v['category']==cat)['session_macro']
    previous_result=read(N/'artifacts/G001/COMPARISON_ALL.json')
    for kind in ['BASELINE','HISTGB_RESIDUAL']:
        for cat in ['ALL','LATE_GE256']:
            assert abs(pt(kind,cat)-next(v for v in previous_result['point_summary'] if v['candidate']==kind and v['category']==cat)['MAE_C'])<1e-12
    comparisons=[];ref='TREND_BALANCED'
    for kind in KINDS[3:]:
        ratio=dict(overall=pt(kind)/pt(ref),RISE=wm(kind,'RISE')['MAE_C']/wm(ref,'RISE')['MAE_C'],FALL=wm(kind,'FALL')['MAE_C']/wm(ref,'FALL')['MAE_C'],late=pt(kind,'LATE_GE256')/pt(ref,'LATE_GE256'))
        gain={cl:wm(kind,cl,'LATE_GE256')['direction_percent']-wm(ref,cl,'LATE_GE256')['direction_percent'] for cl in ['RISE','FALL']}
        checks=dict(complete_coverage=not next(v for v in coverage if v['candidate']==kind)['missing'],temperature_retention=all(v<=1.03 for v in ratio.values()),late_RISE_gain_positive=gain['RISE']>0,late_FALL_gain_positive=gain['FALL']>0,global_direction_drop_le1pp=all(wm(kind,cl)['direction_percent']>=wm(ref,cl)['direction_percent']-1 for cl in ['RISE','FALL']),steady_direction_drop_le0p5pp=wm(kind,'STEADY')['direction_percent']>=wm(ref,'STEADY')['direction_percent']-.5,late_steady_drop_le0p5pp=wm(kind,'STEADY','LATE_GE256')['direction_percent']>=wm(ref,'STEADY','LATE_GE256')['direction_percent']-.5)
        comparisons.append(dict(candidate=kind,joint_goal_met=all(checks.values()),checks=checks,MAE_ratio_vs_previous=ratio,late_direction_gain_pp=gain,stronger_ge5pp_each=all(v>=5 for v in gain.values())))
    sensitivity=[]
    for kind in KINDS[1:]:
        for width,threshold in [(10,.1),(10,.5),(20,.4)]:
            ww=[w for r in rows if r['candidate']==kind for w in A.windows({**r,'parent':by[r['id']]['predicted']},width,threshold)[0]]
            for cat,sw in [('ALL',ww),('LATE',[w for w in ww if w['start']>=256])]:
                for cl in ['RISE','FALL','STEADY']:sensitivity.append(dict(candidate=kind,category=cat,window_s=width,threshold_C=threshold,direction=cl,**A.metrics([w for w in sw if w['direction']==cl],'predicted')))
    fields=list(dict.fromkeys(k for r in session for k in r))
    with (O/'PAIRED_SESSIONS.csv').open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(session)
    save(O/'COMPARISON.json',dict(status='COMPLETE_FIXED_TREND_COMPARISON',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),fit=fit,primary=protocol['primary'],point_summary=points,summary=summary,coverage=coverage,comparisons=comparisons,confusion=confusion,sensitivity=sensitivity,previous_candidate_and_original_unchanged=True,old_physics_gate='FAIL_PRESERVED',independent_confirmation=False,adopted=False))
    for k in KINDS:print(json.dumps(dict(candidate=k,overall=pt(k),rise=wm(k,'RISE')['MAE_C'],fall=wm(k,'FALL')['MAE_C'],late=pt(k,'LATE_GE256'),rise_direction=wm(k,'RISE')['direction_percent'],fall_direction=wm(k,'FALL')['direction_percent'],late_rise_direction=wm(k,'RISE','LATE_GE256')['direction_percent'],late_fall_direction=wm(k,'FALL','LATE_GE256')['direction_percent'],steady_direction=wm(k,'STEADY')['direction_percent']),ensure_ascii=False))
    print('GOALS',json.dumps(comparisons,ensure_ascii=False))
if __name__=='__main__':main()
