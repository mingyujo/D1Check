"""Saved-only diagnosis, transparent ablations and figures for direction repair."""
import csv,json
from collections import Counter,defaultdict
from prepare import H,R,A,O,PREV,FIRST,OLD,read,write,pin,sha

def fmt(x,n=3):return f'{x:.{n}f}'
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rows)
def textnew(p,t):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(t)
def csvwrite(p,rows):
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    f=read(O/'FINDINGS.json');data=read(O/'INPUTS.json');cases={c['session']:c for c in data['cases']};audit=read(O/'AUDIT.json');fit=read(O/'FIT_COMPLETE.json')
    def overall(policy,family='m8',scope='registered',phase='all'):return next(r for r in f['overall'] if (r['policy'],r['family'],r['scope'],r['phase'])==(policy,family,scope,phase))
    def direction(policy,d,family='m8',scope='registered',width=20,threshold=.2):return next(r for r in f['directions'] if (r['policy'],r['direction'],r['family'],r['scope'],r['width_s'],r['threshold_C'])==(policy,d,family,scope,width,threshold))
    name={'rise':'상승','fall':'하강','stable':'유지'};before=overall('CALIBRATED_V1_OOF');after=overall('CALIBRATED_OOF')
    with (O/'AP_WINDOWS.csv').open(encoding='utf-8-sig',newline='') as file:
        primary=[r for r in csv.DictReader(file) if r['family']=='m8' and r['scope']=='registered' and r['width_s']=='20' and r['threshold_C']=='0.2']
    by=defaultdict(dict)
    for r in primary:by[(r['session'],r['i'],r['j'])][r['policy']]=r
    changes=[]
    for key,policies in by.items():
        a=policies['CALIBRATED_V1_OOF'];b=policies['CALIBRATED_OOF'];sid=key[0];end=cases[sid]['last_work_s'];lo=float(a['lo_s']);hi=float(a['hi_s'])
        phase='after_work' if end is None or lo>=end else 'crosses_work_end' if hi>end else 'before_work_end'
        changes.append({'session':sid,'i':int(a['i']),'j':int(a['j']),'lo_s':lo,'hi_s':hi,'observed_direction':a['direction'],'phase':phase,
            'observed_delta_C':float(a['observed_delta_C']),'before_delta_C':float(a['predicted_delta_C']),'after_delta_C':float(b['predicted_delta_C']),
            'before_direction':a['predicted_direction'],'after_direction':b['predicted_direction'],'before_correct':a['direction_correct']=='True','after_correct':b['direction_correct']=='True'})
    assert len(changes)==428
    paired=[]
    for d in ['rise','fall','stable']:
        rr=[r for r in changes if r['observed_direction']==d];bad=[r for r in rr if not r['before_correct']];newbad=[r for r in rr if not r['after_correct']]
        paired.append({'direction':d,'windows':len(rr),'before_missed':len(bad),'after_missed':len(newbad),
            'recovered':sum(not r['before_correct'] and r['after_correct'] for r in rr),'new_errors':sum(r['before_correct'] and not r['after_correct'] for r in rr),
            'before_missed_as_stable':sum(r['before_direction']=='stable' for r in bad),'after_missed_as_stable':sum(r['after_direction']=='stable' for r in newbad),
            'before_missed_delta_le_0_3':sum(abs(r['observed_delta_C'])<=.3+1e-9 for r in bad),'after_missed_delta_le_0_3':sum(abs(r['observed_delta_C'])<=.3+1e-9 for r in newbad),
            'before_missed_crossing_work_end':sum(r['phase']=='crosses_work_end' for r in bad),'before_missed_after_work':sum(r['phase']=='after_work' for r in bad)})
    write(O/'DIAGNOSIS.json',{'paired':paired,'same_window_count':428,'all_observed_AP_on_0_1C_grid':all(abs(o['observed_c']*10-round(o['observed_c']*10))<1e-8 for c in cases.values() for o in c['observations']),
        'primary_predictions_rounded':False,'evaluation_threshold_unchanged':True,'physical_latency_identified':False,
        'normalization_first_variant':read(FIRST/'NORMALIZATION_FINDING.json')})
    csvwrite(O/'DIRECTION_PAIRED_WINDOWS.csv',changes);csvwrite(O/'DIRECTION_PAIRED_SUMMARY.csv',paired)
    report='# A24 상승·하강 방향 보완과 동일 실측조건 재검증\n\n2026-10-21 · A24-THERMAL-DIR-03 · 결과02 · 과거 결과 보존\n\n'
    report+=f"**상승 방향은 73.98→90.24%, 하강은79.31→81.03%로 개선됐다.** 유지92.59%는동일하고 전체428창 일치율은83.64→88.79%다. 최근71세션의 같은 원AP창35~180초에서 평균온도오차도 **{before['MAE_C']:.3f}→{after['MAE_C']:.3f}℃({100*(1-after['MAE_C']/before['MAE_C']):.2f}% 감소)**했다.\n\n"
    report+='하강 방향의 개선은 제한적이며 원래RC의98.28%까지 회복한 것은 아니다. 원래RC는 냉각량을 과하게 예측해 방향점수와 온도/속도 정확도가 달랐다. 현재도 작은 하강을 유지로 놓치는 문제가 남는다. 새 독립 실측이 아니라 같은 자료의 후속 개발 교차검증이며, 아래에 악화와 첫 구현의 정규화 문제도 보존한다.\n\n'
    report+='## 1. 원인을 어떻게 확인했는가\n\n'
    report+='V1이 놓친 상승32/하강24창 중54창은 반대방향이 아니라 유지로 예측했다. 그중50창의실측순변화는0.3℃ 이하였다. 모든관측AP는0.1℃격자지만V1은연속평균을추정하고, 수준75%/순변화25%의제곱오차에는±0.2℃의방향분류경계가없었다. 예를들어실측+0.2℃와예측+0.16℃의차이는작지만방향정답은상승/유지로갈린다. 평가문턱을바꿔해결하지않았다.\n\n'
    report+='또한상승오분류13창은마지막작업종료를가로지르고4창은종료뒤였다. V1의양의병렬1차열상태들은입력이사라지면바로감소하므로, 일이끝난뒤늦게나타나는AP상승을표현하기어려웠다. 실제원인이센서응답/열전달/다른배경발열중어떤것인지는미확정이다. [동일428창의전후판독](DIRECTION_PAIRED_WINDOWS.csv) · [원인수치](DIAGNOSIS.json).\n\n'
    report+='## 2. 보완한 내용과 구현 수정\n\n'
    report+='첫째, 기존빠른/느린열상태뒤에AP응답전송상태를추가했다. 전송상태가열상태를시간상수에따라따라가므로작업종료뒤에도지연된피크를표현할수있다. 후보0/5/15초중최근outer5개와최종전체자료선정은모두5초다. 이값이유일한기기물리시간상수라는뜻은아니다.\n\n'
    report+='둘째, 훈련자료에서만방향별동일가중의부드러운벌점을추가했다. 상승은+0.22℃이상,하강은−0.22℃이하,유지는절대0.18℃이하를권장하되평가에는기존±0.2℃를그대로썼다. 별도분류기로답을덮어쓰거나온도출력을반올림하지않았다.\n\n'
    report+='첫구현01은기본손실을세션합,방향항을클래스·세션평균으로계산해방향항의상대효과가학습세션수에따라약해졌다. 309fit와모든결과/원소스를보존하고,02에서방향항에학습세션수를곱해두항의규모를맞췄다. 변경영향이없는벌점0의동일학습109모형은검증후재사용했고02는200새fit만수행했다. 평가문턱/자료/분할/9후보/보호폭은바꾸지않았다. 이구현문제와수정이력을감추지않았다.\n\n'
    report+='## 3. 같은 실측조건의 주결과\n\n'
    report+='최근71세션/22수집그룹·5outer/3inner 분할, AP3,691표본,20초이상원표본창/±0.2℃/공백10초제외규칙을V1과동일하게사용했다. 해당수집그룹은계수적합과내부선정에서함께제외했다. 빠른/느린상수는V1에서그outer학습그룹안에서선정한값만동결재사용했다.\n\n'
    report+=table(['실측구간','창수','방향일치율 V1→보완','온도MAE℃ V1→보완','속도MAE℃/분 V1→보완'],[[name[d],direction('CALIBRATED_OOF',d)['windows'],fmt(direction('CALIBRATED_V1_OOF',d)['direction_accuracy_pct'],2)+'→'+fmt(direction('CALIBRATED_OOF',d)['direction_accuracy_pct'],2)+'%',fmt(direction('CALIBRATED_V1_OOF',d)['MAE_C'])+'→'+fmt(direction('CALIBRATED_OOF',d)['MAE_C']),fmt(direction('CALIBRATED_V1_OOF',d)['rate_MAE_C_min'])+'→'+fmt(direction('CALIBRATED_OOF',d)['rate_MAE_C_min'])] for d in ['rise','fall','stable']])
    report+='\n![방향/온도/속도의 전후 비교](DIRECTION_BEFORE_AFTER.png)\n\n'
    report+=table(['구간','이전오분류','보완후오분류','회복한창','새오분류창'],[[name[r['direction']],r['before_missed'],r['after_missed'],r['recovered'],r['new_errors']] for r in paired])
    report+='\n전체방향일치율83.64→88.79%,세방향동일가중81.96→87.96%다. 이두수치와클래스별점수를모두보고한다. [10/40초·±0.1/0.3℃까지모든민감도](AP_DIRECTIONS.csv).\n\n'
    report+='## 4. 무엇이 실제로 개선에 기여했는가\n\n'
    pols=[('CALIBRATED_V1_OOF','이전V1'),('CALIBRATED_OOF','보완02·선정된전체절차'),('NO_DIRECTION_LOSS','보완02에서방향벌점만제거'),('NO_TRANSPORT','보완02에서전송지연만제거'),('DIRECTION01_OOF','첫구현01·보존')]
    report+=table(['같은outer학습의대조','온도MAE℃','상승방향','하강방향','유지방향'],[[label,fmt(overall(policy)['MAE_C'],6),*[fmt(direction(policy,d)['direction_accuracy_pct'],2)+'%' for d in ['rise','fall','stable']]] for policy,label in pols])
    report+='\n**이번개선의주원인은AP응답지연이다.** 전송지연만제거하면상승74.80%·하강80.17%로돌아간다. 반면방향벌점을제거해도상승/하강점수는동일하고유지는1창더맞는다. 방향벌점정규화는구현을바르게맞춘것이지그자체의성능이득이확인된것은아니다. 최종최근전체자료선정은전송5초/방향벌점0이므로추가벌점을억지로채택하지않았다. 이최종모형의학습오차를OOF성적대신쓰지않는다.\n\n'
    report+='수정02가첫구현01보다모든지표에서더좋은것도아니다. 01의온도MAE0.110496℃·전체방향89.02%에비해02는0.111000℃·88.79%다. 학습그룹내선정을그대로평가한결과이며바깥평가를보고01/02/제거모형중최고점만골라주결과로바꾸지않았다.\n\n'
    report+='## 5. 남은 하강 오분류와 악화\n\n'
    badfall=next(r for r in paired if r['direction']=='fall');report+=f"하강{badfall['after_missed']}창을아직놓친다. 그중{badfall['after_missed_as_stable']}창은유지예측이고{badfall['after_missed_delta_le_0_3']}창은실측순변화0.3℃이하이다. 작은변화의폭과AP표본응답을정밀하게맞히는한계가남아있다. 이를해결했다고단정하지않는다.\n\n"
    report+=table(['최근원등록창','온도MAE℃ V1→보완','RMSE℃ V1→보완','편향℃ V1→보완'],[[label,fmt(overall('CALIBRATED_V1_OOF',phase=phase)['MAE_C'])+'→'+fmt(overall('CALIBRATED_OOF',phase=phase)['MAE_C']),fmt(overall('CALIBRATED_V1_OOF',phase=phase)['RMSE_C'])+'→'+fmt(overall('CALIBRATED_OOF',phase=phase)['RMSE_C']),fmt(overall('CALIBRATED_V1_OOF',phase=phase)['bias_C'])+'→'+fmt(overall('CALIBRATED_OOF',phase=phase)['bias_C'])] for phase,label in [('all','전체'),('work_present','마지막작업까지'),('recovery','마지막작업뒤')]])
    report+='\n평균온도오차는줄었으나최근9/71세션·과거5/35세션의개별MAE는악화했다. 최근최대악화는+0.0226℃,과거최대는+0.1753℃다. [전량악화표](WORSENING.csv), [모든세션](SESSION_COMPARISON.csv), [그룹별](GROUP_COMPARISON.csv)를보존했다. 보호폭은inner검증에서만적용하는개발규칙이고모든outer세션의무손실보장은아니다.\n\n'
    report+='## 6. 다른 판독범위도 보존\n\n'
    report+=table(['자료/창','온도MAE℃ V1→보완','상승방향 V1→보완','하강방향 V1→보완','유지방향 V1→보완'],[[label,fmt(overall('CALIBRATED_V1_OOF',family,scope)['MAE_C'])+'→'+fmt(overall('CALIBRATED_OOF',family,scope)['MAE_C']),*[fmt(direction('CALIBRATED_V1_OOF',d,family,scope)['direction_accuracy_pct'],2)+'→'+fmt(direction('CALIBRATED_OOF',d,family,scope)['direction_accuracy_pct'],2)+'%' for d in ['rise','fall','stable']]] for family,scope,label in [('m8','full','최근전체지원창·최대210초'),('old','full','과거35·별도계약전체창')]])
    report+='\n과거35는별도계수이며최근모형의장기검증으로쓰지않는다. 과거상승/하강은개선됐으나유지는97.22→91.36%로악화했다. 전체지원창의늦은추가AP상승과그원인미확정도그대로유지한다.\n\n'
    report+='## 7. 실측과 시간 꺾은선\n\n![실측/V1/보완의시간비교](MEASURED_BEFORE_AFTER.png)\n\n'
    report+='두긴과거세션전체와최근71의보완MAE중앙/최대세션을같은규칙으로선정했다. 곡선은원표본시각의연속온도예측이며평활화/온도반올림/offset0이다. 최대와남은편향도숨기지않는다. [그림선정규칙](FIGURES.json).\n\n'
    report+='## 8. 실행·검산·한계\n\n'
    report+=f"새profile의 `directionA24Profile(data,model,context)`는기존두열상태와AP전송상태를정확적분한다. 전체자료배포모형과OOF를분리했다. [실행계약](RUNTIME_CONTRACT.json), [최근모형](m8_DEPLOYMENT_MODEL.json), [과거모형](old_DEPLOYMENT_MODEL.json), [새factory](../../experiments/a24_thermal_direction_v2_20261021/calibrated_profile.cjs).\n\n"
    report+=f"02의200fit START/COMPLETE·FAIL0과01의309fit를모두보존했다. 109개고정벌점0모형은학습ID/상수/전송시간키로재사용했다. Python행렬/직접스칼라/JS runtime106세션의최대T차{audit['max_T_difference_C']:.2e}℃/온도적분차{audit['max_H_difference_C_s']:.2e}℃·초, 미래target변경불변/그룹분리/clone·복원·분할검산PASS다. [감사](AUDIT.json). 이는산술검증이며새독립실측정확도PASS가아니다.\n\n"
    report+='현재조건은실제일정→AP의조건부검증이다. 최근관측AP26~31℃/35~180초밖,600초지속부하,CPU3/D_GPU,절대J,열→처리시간/정책성과는미검증이다. 기존shared기본물리/BC/정책결과는보존됐고이새모형으로정책을다시평가하지않았다. 평가문턱이나허용오차를사후변경해성공으로만들지않았으며새독립확인은별도필요하다.\n'
    models={family:read(O/f'{family}_DEPLOYMENT_MODEL.json') for family in ['m8','old']}
    write(O/'RUNTIME_CONTRACT.json',{'schema':'A24-direction-aware-runtime-v2','factory':pin(H/'calibrated_profile.cjs'),'models':{family:pin(O/f'{family}_DEPLOYMENT_MODEL.json') for family in models},
        'selected_transport_s':{family:m['transport_s'] for family,m in models.items()},'selected_hinge_strength':{family:m['hinge_strength'] for family,m in models.items()},
        'initial_context_required':['initial_ap_c','pre_slope_C_s'],'continuous_AP_prediction':True,'evaluation_threshold_C':.2,'rounding_applied':False,
        'direct_states':['C_CPU','C_GPU','D_CPU','C_GPU+D_CPU'],'other_states':'unvalidated additive transfer inherited from V1',
        'primary_support':{'time_s':[35,180],'observed_AP_C':[26,31]},'existing_power_and_speed_coefficients_changed':False,'new_temperature_affects_power_speed_inputs':True,
        'default_model_replaced':False,'old_policy_results_recomputed':False,'fresh_confirmation':False})
    textnew(O/'REPORT_KO.md',report)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
    fig,axs=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
    for ax,key,title,ylabel in [(axs[0],'direction_accuracy_pct','방향 일치율','일치율(%)'),(axs[1],'MAE_C','온도 오차','MAE(℃)'),(axs[2],'rate_MAE_C_min','변화 속도 오차','MAE(℃/분)')]:
        for policy,offset,color,label in [('CALIBRATED_V1_OOF',-.18,'#cb8640','이전보완V1'),('CALIBRATED_OOF',.18,'#2678a8','방향보완02')]:
            values=[direction(policy,d)[key] for d in ['rise','fall','stable']];bars=ax.bar([k+offset for k in range(3)],values,width=.34,color=color,label=label)
            ax.bar_label(bars,labels=[fmt(v,2 if key=='direction_accuracy_pct' else 3) for v in values],fontsize=8,padding=3)
        ax.set_xticks(range(3),['상승','하강','유지']);ax.set_title(title);ax.set_ylabel(ylabel);ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
    axs[0].set_ylim(0,110);fig.suptitle('A24 같은실측71세션/35~180초 · 그룹제외OOF · 평가20초·±0.2℃ 불변')
    for ext in ['png','svg']:fig.savefig(O/f'DIRECTION_BEFORE_AFTER.{ext}',dpi=160)
    plt.close(fig)
    native=sorted([r for r in f['session_comparisons'] if r['family']=='m8'],key=lambda r:(r['after_MAE_C'],r['session']));chosen=['A24_confirmation_1_LOAD_A_LONG','A24_confirmation_0_C0_LONG',native[len(native)//2]['session'],native[-1]['session']]
    with (O/'AP_SAMPLES.csv').open(encoding='utf-8-sig',newline='') as file:sample=[r for r in csv.DictReader(file) if r['session'] in chosen and r['policy'] in ['CALIBRATED_V1_OOF','CALIBRATED_OOF']]
    fig,axs=plt.subplots(2,2,figsize=(14,8),layout='constrained')
    for ax,sid,title in zip(axs.flat,chosen,['긴과거LOAD·별도계약','긴과거C0·별도계약','최근·보완MAE중앙','최근·보완MAE최대']):
        scope='full' if sid.startswith('A24_') else 'registered';rr=[r for r in sample if r['session']==sid and r['scope']==scope];ref=[r for r in rr if r['policy']=='CALIBRATED_V1_OOF']
        ax.plot([float(r['t_s'])-35 for r in ref],[float(r['observed_C']) for r in ref],color='#111',label='실측AP',lw=1.5)
        for policy,color,label in [('CALIBRATED_V1_OOF','#cb8640','이전보완V1'),('CALIBRATED_OOF','#2678a8','방향보완02')]:
            vals=[r for r in rr if r['policy']==policy];ax.plot([float(r['t_s'])-35 for r in vals],[float(r['predicted_C']) for r in vals],color=color,label=label,lw=1.4)
        ax.set_title(title+'\n'+sid,fontsize=10);ax.set_xlabel('부하시작후 시간(초)');ax.set_ylabel('AP(℃)');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('AP 반응상태 추가 · 실측/이전보완/방향보완02 · 같은그룹 제외·미래AP 보정0',fontsize=14)
    for ext in ['png','svg']:fig.savefig(O/f'MEASURED_BEFORE_AFTER.{ext}',dpi=160)
    plt.close(fig)
    write(O/'FIGURES.json',{'sessions':chosen,'selection':['all long LOAD','all long C0','median native new OOF MAE','max native new OOF MAE'],'rounded_or_smoothed':False,'exports':4})
    textnew(O/'CONTINUE_RUNNING.md','# 재개정본\n\n방향보완01/02 계산·평가·수치감사는완료다. 정본은결과02 REPORT_KO.md/FINDINGS.json/DIAGNOSIS.json/AUDIT.json/RUNTIME_CONTRACT.json이다. 완료identity와기존RC/V1/정책/BC를재시작하지않는다. 01의309fit와정규화수정사유,02의200fit/109고정모형재사용을보존했다. 최근최종모형은전송5초/방향벌점0이고주개선요인은AP응답상태다. 하강은81.03%로불완전하며MAE악화최근9/과거5도남는다. 새독립실측/장기/CPU3/D_GPU/에너지/정책성과미검증이다.\n')
    write(O/'POST_SOURCES.json',{'sources':[pin(H/n) for n in ['evaluate.py','runtime_validate.cjs','audit.py','report.py']],'new_fits':0,'policy_environments':0,'new_measurements':0})
    print(json.dumps({'status':'REPORT_COMPLETE','paired':paired,'worsened':dict(Counter(r['family'] for r in f['worsening'])),'primary_MAE_C':after['MAE_C']},ensure_ascii=False))
if __name__=='__main__':main()
