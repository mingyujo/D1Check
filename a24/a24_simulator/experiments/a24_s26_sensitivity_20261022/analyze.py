"""Finite differences and reweighting of saved/audited episodes. No simulator import."""
import json,math,csv,itertools,collections,statistics,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];A=R/'a24_simulator';O=A/'results/A24_S26_SENSITIVITY_20261022_01';V=A/'reviews/A24_S26_SENSITIVITY_20261022_01'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(n,x):
    with (O/n).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
def csvout(n,rr):
    with (O/n).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def text(n,s):
    with (O/n).open('x',encoding='utf-8') as f:f.write(s)
def mean(v):v=list(v);return math.fsum(v)/len(v)
policies=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_RISK','BC_NEURAL_URGENT'];names=dict(zip(policies,['FIFO','EDF','RR','교사규칙','롤링+ATC+BC']));metrics=['ALL_on_pct','U_on_pct','N_on_pct','AP','J_per_request','J_per_ontime','EDF_ALL_gain_pp','EDF_energy_saving_pct','EDF_AP_reduction_C']
reg=read(H/'OPERATION.json')
for p in reg['source_pins']:assert hashlib.sha256((R/p['path']).read_bytes()).hexdigest()==p['sha256']
episodes=[];identities=set();checks=0
for source in ['A24_S26_SCALE_20261022_01','A24_S26_JOINT_20261022_01']:
    parent=A/'results'/source;result=read(parent/'RESULT.json');audit=read(parent/'AUDIT_JS.json');assert audit['status']=='PASS';derived={v['label']:v for v in audit['derived']}
    for r in result['rows']:
        assert r['status']=='COMPLETE';identity=(r['bank']['sha256'],r['policy']);assert identity not in identities;identities.add(identity);m=r['metrics'];co=r['condition'];d=derived[r['label']];assert abs(m['J']-d['J'])<1e-6 and abs(m['AP']-d['AP'])<1e-8;checks+=3
        v={'source':source,'label':r['label'],'setting':co['setting'],'role':co['role'],'n':co['n'],'burst':co['burst'],'load':co['nominal_load'],'mix':co['mix'],'draw':co['draw'],'rate':co['requests_per_second'],'supply_s':co['supply_s'],'policy':r['policy'],'J':m['J'],'AP':m['AP'],'J_increment':m['increment_J'],'J_no_pre35':m['J']-m['pre35_baseline_J'],'J_supply':d['supply_J'],'J_own_completion':d['own_completion_J'],'raw_sha256':r['raw']['sha256'],'bank_sha256':r['bank']['sha256']}
        for g in ['ALL','U','N']:
            for k in ['n','on','missing','incomplete','P95']:v[g+'_'+k]=m['service'][g][k]
            v[g+'_on_pct']=100*v[g+'_on']/v[g+'_n']
        v['J_per_request']=v['J']/v['ALL_n'];v['J_per_ontime']=v['J']/v['ALL_on'];episodes.append(v)
assert len(episodes)==160
def sid(n,b,l):return f'N{n}_B{b}_L{int(l*100)}'
def aggregate(rr):
    v={'J':mean(r['J'] for r in rr),'AP':mean(r['AP'] for r in rr),'J_per_request':sum(r['J'] for r in rr)/sum(r['ALL_n'] for r in rr),'J_per_ontime':sum(r['J'] for r in rr)/sum(r['ALL_on'] for r in rr),'J_no_pre35':mean(r['J_no_pre35'] for r in rr),'J_supply':mean(r['J_supply'] for r in rr),'J_own_completion':mean(r['J_own_completion'] for r in rr) if all(r['J_own_completion'] is not None for r in rr) else None}
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:v[g+'_'+k]=sum(r[g+'_'+k] for r in rr)
        v[g+'_on_pct']=100*v[g+'_on']/v[g+'_n'];v[g+'_P95']=mean(r[g+'_P95'] for r in rr)
    return v
def compare(b,a):return {'ALL_gain_pp':b['ALL_on_pct']-a['ALL_on_pct'],'energy_saving_pct':100*(1-b['J']/a['J']),'AP_reduction_C':a['AP']-b['AP']}
def cell(rr):
    ps={p:aggregate([r for r in rr if r['policy']==p]) for p in policies};b=ps[policies[-1]];cc={p:compare(b,ps[p]) for p in policies[:-1]};mixes=[]
    for mix in [.5,.75]:
        qq=[r for r in rr if r['mix']==mix];pp={p:aggregate([r for r in qq if r['policy']==p]) for p in policies};mm={p:compare(pp[policies[-1]],pp[p]) for p in policies[:-1]};mixes.append({'mix':mix,'policies':pp,'comparisons':mm})
    return {'policies':ps,'comparisons':cc,'mixes':mixes,'aggregate_joint':all(c['ALL_gain_pp']>1e-9 and c['energy_saving_pct']>1e-9 and c['AP_reduction_C']>1e-9 for p,c in cc.items() if p in policies[:3]),'mixed_nonworse_joint':all(c['ALL_gain_pp']>=-1e-9 and c['energy_saving_pct']>1e-9 and c['AP_reduction_C']>1e-9 for m in mixes for p,c in m['comparisons'].items() if p in policies[:3]),'quality_gate':all(m['policies'][policies[-1]]['ALL_on_pct']>=95 and m['policies'][policies[-1]]['U_on_pct']>=99 and m['policies'][policies[-1]]['ALL_missing']==m['policies'][policies[-1]]['ALL_incomplete']==0 for m in mixes)}
cells=[];windows=[]
for role,setting in sorted({(r['role'],r['setting']) for r in episodes}):
    rr=[r for r in episodes if r['role']==role and r['setting']==setting];v={'role':role,'setting':setting,'n':rr[0]['n'],'burst':rr[0]['burst'],'load':rr[0]['load'],**cell(rr)};cells.append(v)
    b=v['policies'][policies[-1]]
    for p,a in v['policies'].items():
        if p==policies[-1]:continue
        windows.append({'role':role,'setting':setting,'reference':p,**{k+'_saving_pct':100*(1-b[k]/a[k]) if b[k] is not None and a[k] is not None else None for k in ['J','J_no_pre35','J_supply','J_own_completion']}})
# One-factor matched changes. DEV core only; the single sample/draw cannot supply inference.
index={(r['n'],r['burst'],r['load'],r['mix'],r['policy']):r for r in episodes if r['role']=='DEV'}
def vals(r):
    a=index[(r['n'],r['burst'],r['load'],r['mix'],'EDF_DYN')];return {**{k:r[k] for k in metrics if not k.startswith('EDF_')},'EDF_ALL_gain_pp':r['ALL_on_pct']-a['ALL_on_pct'],'EDF_energy_saving_pct':100*(1-r['J']/a['J']),'EDF_AP_reduction_C':a['AP']-r['AP']}
factors={'N':(0,[256,512]),'BURST':(1,[4,8]),'LOAD':(2,[.25,.5])};levels=[[256,512],[4,8],[.25,.5]];contrasts=[];interactions=[]
for factor,(axis,lv) in factors.items():
    others=[a for a in range(3) if a!=axis]
    for other in itertools.product(*(levels[a] for a in others)):
        low=[None]*3;high=[None]*3;low[axis]=lv[0];high[axis]=lv[1]
        for a,x in zip(others,other):low[a]=high[a]=x
        for mix,p in itertools.product([.5,.75],policies):
            a=index[(*low,mix,p)];b=index[(*high,mix,p)];va=vals(a);vb=vals(b);contrasts.append({'factor':factor,'mix':mix,'policy':p,'low':a['label'],'high':b['label'],'delta':{k:vb[k]-va[k] for k in metrics}})
factorstats=[]
for factor,p in itertools.product(factors,policies):
    rr=[r for r in contrasts if r['factor']==factor and r['policy']==p];factorstats.append({'factor':factor,'policy':p,'pairs':len(rr),'metrics':{k:{'signed_mean':mean(r['delta'][k] for r in rr),'mean_abs':mean(abs(r['delta'][k]) for r in rr),'min':min(r['delta'][k] for r in rr),'max':max(r['delta'][k] for r in rr)} for k in metrics}})
for axes in itertools.combinations(range(3),2):
    remaining=next(a for a in range(3) if a not in axes)
    for z,mix,p in itertools.product(levels[remaining],[.5,.75],policies):
        vv={};labels={}
        for i,j in itertools.product([0,1],repeat=2):
            q=[None]*3;q[remaining]=z;q[axes[0]]=levels[axes[0]][i];q[axes[1]]=levels[axes[1]][j];r=index[(*q,mix,p)];vv[i,j]=vals(r);labels[str(i)+str(j)]=r['label']
        interactions.append({'axes':[list(factors)[a] for a in axes],'fixed_axis':list(factors)[remaining],'fixed_value':z,'mix':mix,'policy':p,'labels':labels,'DID':{k:vv[1,1][k]-vv[1,0][k]-vv[0,1][k]+vv[0,0][k] for k in metrics}})
draws=[]
for role,setting,draw in sorted({(r['role'],r['setting'],r['draw']) for r in episodes}):
    rr=[r for r in episodes if (r['role'],r['setting'],r['draw'])==(role,setting,draw)];draws.append({'role':role,'setting':setting,'draw':draw,**cell(rr)})
weights=[];thresholds=[]
for setting in [sid(256,8,.25),sid(512,8,.25)]:
    v=next(c for c in cells if c['role']=='CONF' and c['setting']==setting);ms={m['mix']:m for m in v['mixes']};bounds=[]
    for p in policies[:3]:
        a=ms[.5]['comparisons'][p]['ALL_gain_pp'];b=ms[.75]['comparisons'][p]['ALL_gain_pp'];root=-b/(a-b);bounds.append(root);thresholds.append({'setting':setting,'reference':p,'ALL_gain_at_w0_pp':b,'ALL_gain_at_w1_pp':a,'ALL_zero_w':root,'ALL_gain_positive_for_w_above_root':a>b,'energy_and_AP_positive_at_both_endpoints':all(ms[m]['comparisons'][p]['energy_saving_pct']>0 and ms[m]['comparisons'][p]['AP_reduction_C']>0 for m in [.5,.75])})
        for i in range(101):
            w=i/100;b50=ms[.5]['policies'][policies[-1]];b75=ms[.75]['policies'][policies[-1]];r50=ms[.5]['policies'][p];r75=ms[.75]['policies'][p];bj=w*b50['J']+(1-w)*b75['J'];rj=w*r50['J']+(1-w)*r75['J'];weights.append({'setting':setting,'reference':p,'w_C50_scenario':w,'ALL_gain_pp':w*a+(1-w)*b,'energy_saving_pct':100*(1-bj/rj),'AP_reduction_C':w*(r50['AP']-b50['AP'])+(1-w)*(r75['AP']-b75['AP'])})
grid=[]
for c in cells:
    b=c['policies'][policies[-1]];e=c['comparisons']['EDF_DYN'];grid.append({'role':c['role'],'setting':c['setting'],'n':c['n'],'burst':c['burst'],'load':c['load'],'BC_ALL_pct':b['ALL_on_pct'],'BC_U_pct':b['U_on_pct'],'EDF_ALL_pct':c['policies']['EDF_DYN']['ALL_on_pct'],'EDF_ALL_gain_pp':e['ALL_gain_pp'],'EDF_energy_saving_pct':e['energy_saving_pct'],'EDF_AP_reduction_C':e['AP_reduction_C'],'all3_aggregate_joint':c['aggregate_joint'],'mixed_nonworse_joint':c['mixed_nonworse_joint'],'quality_gate':c['quality_gate']})
save('EPISODES.json',episodes);save('CELLS.json',cells);save('FACTORS.json',{'contrasts':contrasts,'summary':factorstats});save('INTERACTIONS.json',interactions);save('DRAW_STABILITY.json',draws);save('WEIGHT_THRESHOLDS.json',thresholds);save('ANALYTIC_WEIGHTING.json',weights);save('WINDOWS.json',windows);csvout('ALL_EPISODES.csv',episodes);csvout('GRID_SUMMARY.csv',grid);csvout('WEIGHT_THRESHOLDS.csv',thresholds);csvout('WINDOWS.csv',windows)
csvout('MATCHED_CONTRASTS.csv',[{k:v for k,v in r.items() if k!='delta'}|r['delta'] for r in contrasts]);csvout('INTERACTIONS.csv',[{'axes':'×'.join(r['axes']),'fixed_axis':r['fixed_axis'],'fixed_value':r['fixed_value'],'mix':r['mix'],'policy':r['policy'],**r['DID']} for r in interactions])
bcstats={r['factor']:r for r in factorstats if r['policy']==policies[-1]};important=sorted(bcstats,key=lambda k:-bcstats[k]['metrics']['ALL_on_pct']['mean_abs']);summary={'id':'A24-S26-SENS-03','unique_episodes':160,'DEV':100,'CONF':60,'balanced_core_episodes':80,'matched_factor_pairs':len(contrasts),'factor_interactions':len(interactions),'BC_abs_ALL_effect_order':important,'BC_factor_statistics':bcstats,'new_environments':0,'new_fits':0,'new_measurements':0,'no_population_CI':True};save('SUMMARY.json',summary)
# Standard scientific plots: no model inference or image-generation transformation.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
font_manager.fontManager.addfont('C:/Windows/Fonts/malgun.ttf');plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
F=O/'figures';F.mkdir(exist_ok=False);dev=[c for c in cells if c['role']=='DEV']
fig,axes=plt.subplots(2,2,figsize=(11.7,8.2));keys=['ALL_on_pct','U_on_pct','AP','J_per_request'];titles=['전체 정시율 변화 (%p)','긴급 정시율 변화 (%p)','평균 AP 변화 (℃)','요청당 소비 변화 (J*/건)'];flabel={'N':'요청 수\n256→512','BURST':'묶음\n4→8','LOAD':'명목 도착부하\n25→50%'}
for ax,k,title in zip(axes.flat,keys,titles):
    vs=[bcstats[f]['metrics'][k]['mean_abs'] for f in factors];ax.bar([flabel[f] for f in factors],vs,color=['#8ba8e5','#6484d7','#3559da']);ax.set_title(title,loc='left',weight='bold');ax.set_ylabel('평균 |유한 차이|');ax.set_ylim(0,max(vs)*1.25)
    for i,v in enumerate(vs):ax.text(i,v+max(vs)*.035,f'{v:.3f}',ha='center')
fig.suptitle('A24 BC · 균형 DEV 격자에서 다른 조건을 고정한 민감도',fontsize=14);fig.text(.5,.012,'요인별 두배 변화·BC 8쌍 평균 | 인과순위/모집단 추론 아님 | 묶음은 작업순서 변화도 포함',ha='center',fontsize=9);fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(F/'FACTOR_EFFECTS.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5.8))
for ax,n in zip(axes,[256,512]):
    matrix=np.full((3,2),np.nan)
    for i,b in enumerate([4,8,16]):
        for j,l in enumerate([.25,.5]):
            c=next((c for c in dev if c['n']==n and c['burst']==b and c['load']==l),None)
            if c:matrix[i,j]=c['policies'][policies[-1]]['ALL_on_pct']
    cm=plt.colormaps['RdYlGn'].copy();cm.set_bad('#dddddd');im=ax.imshow(np.ma.masked_invalid(matrix),cmap=cm,vmin=0,vmax=100,aspect='auto');ax.set_xticks([0,1],['명목25%','명목50%']);ax.set_yticks([0,1,2],['묶음4','묶음8','묶음16']);ax.set_title(f'N{n} · BC 전체 정시율')
    for (i,j),v in np.ndenumerate(matrix):ax.text(j,i,'미실행' if np.isnan(v) else f'{v:.2f}%',ha='center',va='center',fontsize=13)
fig.colorbar(im,ax=axes.ravel().tolist(),label='전체 정시율 (%)',shrink=.75);fig.suptitle('DEV 전체 규모 격자 · 두 혼합 동일가중',fontsize=14);fig.savefig(F/'SCALE_GRID.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(2,3,figsize=(12.7,7.7));colors=['#888888','#3559da','#a273ba']
for axs,n in zip(axes,[256,512]):
    for ax,k,title in zip(axs,['ALL_gain_pp','energy_saving_pct','AP_reduction_C'],['전체 정시 개선 (%p)','예측 소비 감소 (%)','평균 AP 감소 (℃)']):
        for p,color in zip(policies[:3],colors):
            rr=[r for r in weights if r['setting']==sid(n,8,.25) and r['reference']==p];ax.plot([r['w_C50_scenario'] for r in rr],[r[k] for r in rr],color=color,label=names[p]+' 대비')
        ax.axhline(0,color='black',lw=.7);ax.axvline(.5,color='#666666',ls=':');ax.set_title(f'N{n} · {title}');ax.set_xlabel('분류50% 시나리오의 평가가중치 w');ax.grid(alpha=.12)
handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=3);fig.suptitle('확인 자료의 분석적 재가중 · 점선 w=.5가 본 S26식 집계',fontsize=14);fig.tight_layout(rect=[0,.06,1,.95]);fig.savefig(F/'SCENARIO_WEIGHTING.png',dpi=170);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(12.7,4.8));conf=[c for c in cells if c['role']=='CONF' and c['burst']==8]
for ax,k,title in zip(axes,['ALL_on_pct','EDF_energy_saving_pct','EDF_AP_reduction_C'],['BC 전체 정시율 (%)','EDF 대비 소비 감소 (%)','EDF 대비 AP 감소 (℃)']):
    for n,color in [(256,'#4771d5'),(512,'#c47d32')]:
        rr=sorted([d for d in draws if d['setting']==sid(n,8,.25)],key=lambda d:d['draw']);yy=[d['policies'][policies[-1]][k] if k=='ALL_on_pct' else d['comparisons']['EDF_DYN']['energy_saving_pct' if k=='EDF_energy_saving_pct' else 'AP_reduction_C'] for d in rr];ax.plot([0,1,2],yy,'o-',label=f'N{n}',color=color)
    ax.set_xticks([0,1,2],['DEV0','CONF1','CONF2']);ax.set_title(title);ax.grid(alpha=.15)
axes[0].legend();fig.suptitle('동일 실측pool의 draw별 성적 · 독립 실측 반복/신뢰구간 아님',fontsize=13);fig.tight_layout(rect=[0,0,1,.92]);fig.savefig(F/'DRAW_STABILITY.png',dpi=170);plt.close(fig)
# Korean report: descriptive finite-grid sensitivity, never causal ranking or general validation.
def gridtable(rr):
    return '\n'.join(['| 단계 | 요청수 | 묶음 | 명목부하 | BC 전체 정시 | BC 긴급 정시 | EDF 전체 정시 | EDF비 소비감소 | EDF비 AP감소 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']+[f"| {g['role']} | {g['n']} | {g['burst']} | {g['load']*100:.0f}% | {g['BC_ALL_pct']:.2f}% | {g['BC_U_pct']:.2f}% | {g['EDF_ALL_pct']:.2f}% | {g['EDF_energy_saving_pct']:.3f}% | {g['EDF_AP_reduction_C']:.3f}℃ |" for g in rr])
factortable='\n'.join(['| 요인 두배 변화 | BC 전체정시 평균변화 | 평균 절대변화 | BC AP 평균변화 | 요청당J* 평균변화 |','|---|---:|---:|---:|---:|']+[f"| {flabel[f].replace(chr(10),' ')} | {bcstats[f]['metrics']['ALL_on_pct']['signed_mean']:+.3f}%p | {bcstats[f]['metrics']['ALL_on_pct']['mean_abs']:.3f}%p | {bcstats[f]['metrics']['AP']['signed_mean']:+.3f}℃ | {bcstats[f]['metrics']['J_per_request']['signed_mean']:+.4f} |" for f in factors])
ct=next(c for c in cells if c['role']=='CONF' and c['n']==512 and c['burst']==8);te=next(t for t in thresholds if t['setting']==sid(512,8,.25) and t['reference']=='EDF_DYN');t256=next(t for t in thresholds if t['setting']==sid(256,8,.25) and t['reference']=='EDF_DYN');win=[w for w in windows if w['role']=='CONF' and w['setting']==sid(512,8,.25) and w['reference']=='EDF_DYN'][0]
stability=[]
for n in [256,512]:
    dd=[d for d in draws if d['setting']==sid(n,8,.25)];cf=[d for d in dd if d['role']=='CONF'];stability.append({'N':n,'draws':len(dd),'aggregate_joint_pass_draws':sum(d['aggregate_joint'] for d in dd),'CONF_BC_ALL_min':min(d['policies'][policies[-1]]['ALL_on_pct'] for d in cf),'CONF_BC_ALL_max':max(d['policies'][policies[-1]]['ALL_on_pct'] for d in cf),'CONF_EDF_energy_saving_min':min(d['comparisons']['EDF_DYN']['energy_saving_pct'] for d in cf),'CONF_EDF_energy_saving_max':max(d['comparisons']['EDF_DYN']['energy_saving_pct'] for d in cf)})
save('STABILITY_SUMMARY.json',stability)
stabtable='\n'.join(['| N | DEV0/CONF1/CONF2 합산 공동우위 | CONF draw별 BC 전체정시 범위 | CONF EDF비 소비감소 범위 |','|---|---:|---:|---:|']+[f"| {s['N']} | {s['aggregate_joint_pass_draws']}/{s['draws']} | {s['CONF_BC_ALL_min']:.3f}~{s['CONF_BC_ALL_max']:.3f}% | {s['CONF_EDF_energy_saving_min']:.3f}~{s['CONF_EDF_energy_saving_max']:.3f}% |" for s in stability])
report=f'''# A24 입력규모 민감도 분석

**이 관측격자에서 BC 정시율은 {', '.join({'LOAD':'도착률','BURST':'동시 도착 묶음','N':'요청 수'}[f] for f in important)} 순으로 큰 평균 절대변화를 보였다.** 모든 요인을 두배로 바꾼 균형격자의 기술 통계다. 조건을 조금 바꿔도 언제나 우위가 유지된다는 결과는 아니다. 특히 명목부하25→50%와 묶음8→16에서 절대 정시율이 크게 떨어진다.

분석은 완료 **160행(DEV100·CONF60)**의 저장 재사용이며 새 시뮬레이션/학습/fit/실측0이다. S26 납기·전체도착 분모·응답/P95 집계·고정 소비/AP 창은 바꾸지 않았다. 기존 롤링+ATC+BC 정책·물리모형도 동결했다.

## 요인별 영향과 상호작용

N256/512×묶음4/8×명목부하25/50%의 균형 DEV80행만 사용했다. 다른 요인·혼합·정책을 고정한 각 요인40쌍(BC8쌍)의 유한 차이를 계산했다. 아래는 BC8쌍의 평균이다. 부호평균과 평균절대값을 구별한다.

{factortable}

단위가 다른 세 요인의 ‘두배 변화’ 범위 안에서만 비교한다. 요인별 표본 독립성이나 인과우선순위를 뜻하지 않는다. 묶음을 바꾸면 기존 템플릿에서 C/D 순서도 일부 변하므로 묶음만의 인과효과는 아니다. N/도착률 비교는 묶음을 고정하면 같은 잠재 prefix다. N증가는 요청량과 관측길이, 도착률증가는 공급/관측길이도 바꾼다.

두 요인의 상호작용은 차이의 차이(DID)60개로 전량 공개했다. [대응120쌍](MATCHED_CONTRASTS.csv), [상호작용60개](INTERACTIONS.csv), [기계판독 요인통계](FACTORS.json)를 참조한다. 수치가 큰 요인이라도 다른 요인의 수준에 따라 영향이 달라진다. Sobol지수·분산설명률·유의확률로 해석하지 않는다.

## 전체 규모 격자와 별도 확인

{gridtable(grid)}

DEV는 각설정 두혼합·draw0, CONF는 해당설정 네입력(draw1/2×두혼합)이다. 단계별 집계를 섞지 않았다. N256·묶음16은 미실행이므로 그림에 ‘미실행’으로 표시한다.

512건·묶음4·25%의 모두100%는 정시율 차이가 없는 영역이다. 묶음8·25%에서는 거의 전량정시를 유지하면서 기준선과의 차이가 드러난다. 묶음16 또는 명목50%에서는 기준선보다 낫더라도 BC 자체의 절대 정시율이 낮아진다. 상대 우위와 서비스 품질을 별도로 판단해야 한다. 명목부하는 실측 CPU이용률이나 지속처리용량 인증이 아니다.

## 혼합·표본에 대한 민감도

{stabtable}

세 draw에서 같은 결론이 나와도 새 독립 기기세션 세 번을 뜻하지 않는다. 같은 실측pool·동일 Nprefix를 공유하며 각 draw의 혼합은 둘뿐이다. 모집단 신뢰구간이나 통계적 유의성을 만들지 않았다.

N512·묶음8·25% 확인에서 분류50% 시나리오의 EDF대비 전체정시 개선은 {ct['mixes'][0]['comparisons']['EDF_DYN']['ALL_gain_pp']:+.6f}%p, 분류75% 시나리오는 {ct['mixes'][1]['comparisons']['EDF_DYN']['ALL_gain_pp']:+.6f}%p다. 분류75%·draw2의 긴급1건 지각 때문에 혼합별 비악화 gate는 실패한다. 두혼합 합산 공동우위와 모든혼합 비악화를 구분한다. N256에서도 분류75% 확인에 같은1건 손해가 있다. 교사/BC의 성과는 거의 같고 BC가 교사보다 더 좋다는 증거는 없다.

완료 확인자료를 분석적으로 재가중하면, N512에서 분류50% **시나리오의 평가가중치** w가 {100*te['ALL_zero_w']:.6f}%보다 클 때 EDF대비 전체정시 개선이 양수다. N256 경계는 {100*t256['ALL_zero_w']:.6f}%다. 에너지/AP 감소는 두 끝점 모두 양수이므로 그 가중범위에서도 유지된다. S26식 본집계는 w=.5다. **이는 두 시나리오 평가비중을 바꾼 산술이며 실제 요청의 분류비율·도착을 새로 바꾼 시뮬레이션이 아니다.** 기존 draw와 실측pool에만 조건부다. [경계값](WEIGHT_THRESHOLDS.csv)·[전체 재가중](ANALYTIC_WEIGHTING.json)에 각 기준선 수치를 남겼다.

## 소비 계산창에 대한 민감도

N512·묶음8·25% 확인의 EDF비 소비 절감률은 원 고정창 {win['J_saving_pct']:.6f}%, 35초 이전 기저 제외 {win['J_no_pre35_saving_pct']:.6f}%, 공급창 {win['J_supply_saving_pct']:.6f}%, 개별완료창 {win['J_own_completion_saving_pct']:.6f}%다. 주기준을 바꾸지 않고 보조수치만 비교했다. 개별완료창은 정책마다 종료시각이 달라 주비교로 대체할 수 없다. [전량 창비교](WINDOWS.csv)를 공개한다.

요청수/도착률을 바꾸면 총 요청·시간도 달라져 총J*만으로 효율을 평가하면 안 된다. 요청당 J*와 **정시완료 요청당 J***를 함께 계산했다. 고부하에서 총 소비가 작아져도 납기 위반이 늘면 좋은 운영조건이라는 뜻이 아니다. 모형 J*는 미교정 전력 적분이고 실측 배터리J 정확도 인증이 아니다.

## 판정과 한계

발표는 ‘묶음8·명목25%·요청256/512·두혼합 동일가중의 확인에서 합산 정시·소비·AP가 세 기준선보다 좋았다’로 한정할 수 있다. 모든 부하·모든 작업구성에서 낫다고 쓰면 안 된다. 기존 gate와 결과는 바꾸지 않았다.

물리계수(전력·열저항·시간상수), CPU슬롯/경합, 초기온도, 기한 또는 중간 도착률은 이번 저장자료에 변화가 없어 민감도를 알 수 없다. 입력규모 민감도를 시뮬레이터의 물리 정확도나 해당 계수에 대한 강건성으로 해석하지 않는다. CPU3·D_GPU전이·초기26℃·판단비용제외·기존자료 재사용 한계는 유지한다.

- [요인별 민감도 그림](figures/FACTOR_EFFECTS.png), [전체 규모 격자](figures/SCALE_GRID.png), [평가가중치 변화](figures/SCENARIO_WEIGHTING.png), [draw별 변화](figures/DRAW_STABILITY.png)
- [160행 CSV](ALL_EPISODES.csv), [격자표 CSV](GRID_SUMMARY.csv), [요약 JSON](SUMMARY.json), [draw별 전량](DRAW_STABILITY.json)
- [분석규약](../../experiments/a24_s26_sensitivity_20261022/PROTOCOL.md), [소스등록](../../experiments/a24_s26_sensitivity_20261022/OPERATION.json), [독립 JS 검산](AUDIT_JS.json), [최종 증거](FINAL_PROOF.json)

검증대상은 2026-10-22·브랜치codex/a24-simulator-handoff-20261016·HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf+미커밋이다. 실행명령은 experiments/a24_s26_sensitivity_20261022/prepare.py·analyze.py와 reviews/A24_S26_SENSITIVITY_20261022_01/audit.cjs·finalize.py다. 계산 검증과 실기기 검증은 구분한다.
'''
text('REPORT_KO.md',report);text('CONTINUE_RUNNING.md','# A24-S26-SENS-03 저장자료 분석 종료\n\n새환경/학습/fit/실측0이다. 기존160완료행만 분석했다. [정본](REPORT_KO.md)·전체요인/상호작용/혼합별 손해·한계를 확인한다. 완료실험이나 분석출력 identity를 자동 재실행하지 않는다. 미실행 셀/물리계수 민감도는 이번 분석으로 채우지 않았다. 최종봉인은 FINAL_PROOF.json을 따른다.\n')
save('BUILD.json',{'status':'PASS','source_metric_binding_checks':checks,'episodes':len(episodes),'contrasts':len(contrasts),'interactions':len(interactions),'new_environments':0,'new_fits':0,'new_measurements':0,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
print(json.dumps({'state':'SAVED_ANALYSIS_BUILT','episodes':len(episodes),'contrasts':len(contrasts),'interactions':len(interactions),'BC_factor_ALL_abs_order':important,'BC_factor_ALL_effects':{f:bcstats[f]['metrics']['ALL_on_pct'] for f in factors},'weight_threshold_EDF_N512':te['ALL_zero_w']},ensure_ascii=False))
