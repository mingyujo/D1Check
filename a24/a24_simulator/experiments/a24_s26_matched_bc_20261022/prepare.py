import copy,itertools,ast
from matched_common import *
from a24_s26_matched_bc_20261022.policy import protect_waits
from a24_s26_scale_20261022.prepare import make_case

def pools(split):
    allsamples=read(A/'experiments/common_count_20261021/INPUTS.json')['samples'];allowed={(s['key'],s['source']) for s in allsamples if s['device']=='A24' and s['split']==split};out={}
    for pattern in [0,1]:
        bank=read(A/f'experiments/a24_duration_040_20261019/banks/D040_T600_P{pattern}_S160.BANK.json.gz')
        for j in bank['jobs']:
            k=j['task']+'_ADMISSION';sid=j['admission']['sample_id']
            if (k,sid) in allowed:out.setdefault(k,{})[sid]={'id':sid,'delay_ns':j['admission']['scheduled_to_actual_ns']+j['admission']['actual_to_queue_ns']}
            for route,row in j['routes'].items():
                k=j['task']+'_'+route;sid=row['sample_id']
                if (k,sid) in allowed:out.setdefault(k,{})[sid]={'id':sid,'stages_ns':row['stages_ns'],'source':row.get('source'),'transfer':row.get('DG_transfer',False)}
    out={k:[v[i] for i in sorted(v)] for k,v in out.items()};assert set(out)=={'C_ADMISSION','D_ADMISSION','C_CPU','C_GPU','D_CPU','D_GPU'} and all(out.values());return out

def check_guard():
    import numpy as np
    s={'queue':[{'request_id':'q','priority':'U','task':'C','deadline_ns':1_000_000_000}]};b={'idle_mask':np.array([True,True,True]+[False]*33),'actions':[{'kind':'DISPATCH','request_id':'q','route':'CPU'},{'kind':'WAIT','wait_ns':50_000_000},{'kind':'WAIT_EVENT','max_wait_ns':500_000_000}],'forecasts':[{'responses_s':{'q':.8},'H_s':10},{},{}]};m,r=protect_waits(s,b,{'C':.02,'D':.1},.001);assert m[:3].tolist()==[True,True,False] and r['blocked_wait_indices']==[2]
    b['forecasts'][0]['responses_s']['q']=1.;m,r=protect_waits(s,b,{'C':.02,'D':.1},.001);assert m[:3].tolist()==[True,False,False]
    s['queue'][0]['priority']='N';m,r=protect_waits(s,b,{'C':.02,'D':.1},.001);assert m[:3].all() and not r['blocked_wait_indices'];return 6

def main():
    assert not O.exists() and not (H/'OPERATION.json').exists();V.mkdir(parents=True,exist_ok=True);(H/'banks').mkdir();checks=check_guard()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'));checks+=1
    prior=read(A/'experiments/a24_s26_scale_20261022/OPERATION.json');verify(prior);pools_by={split:pools(split) for split in ['TRAIN','EVAL']};members={s:{(k,r['id']) for k,v in p.items() for r in v} for s,p in pools_by.items()};assert not (members['TRAIN']&members['EVAL']);checks+=1
    source=read(A/'experiments/a24_s26_scale_20261022/INPUTS.json');nominal=read(A/'experiments/a24_s26_common_20261020/PROFILES.json')['A24']['nominal'];prototype=read(R/source['cases'][0]['public']['path'])['public'];training=[];evaluation=[]
    specs=[('TRAIN','TRAIN',n,l,m,101,26) for n,l,m in itertools.product([256,512],[.25,.5],[.5,.75])]+[('TRAIN','HOT',256,.25,m,101,42) for m in [.5,.75]]
    specs += [('EVAL','PRIMARY',512,.25,m,d,26) for d,m in itertools.product([201,202],[.5,.75])]+[('EVAL','SMALL',256,.25,m,201,26) for m in [.5,.75]]+[('EVAL','STRESS',512,.5,m,201,26) for m in [.5,.75]]
    for split,cohort,n,load,mix,draw,temp in specs:
        setting={'id':f'N{n}_B8_L{int(load*100)}','n':n,'burst':8,'load':load};c,p,b=make_case(setting,mix,'MATCH_'+split,draw,pools_by[split],nominal,source['capacities'][str(mix)],prototype);c['id']=c['id'].replace('SCALE_','MATCHED_')+f'_T{temp}';c['temperature_c']=temp;c['condition'].update(role=split,cohort=cohort,initial_temperature_c=temp);p['initial_ap_c']=temp;p['public_initial_context_sha256']=B.L.digest({'T':temp,'z':0,'source':'PRESERVED_ORIGINAL_A24'});assert len(b['jobs'])==len(p['requests'])==n
        for j in b['jobs']:
            assert (j['task']+'_ADMISSION',j['admission']['sample_id']) in members[split]
            for route,r in j['routes'].items():assert (j['task']+'_'+route,r['sample_id']) in members[split];checks+=1
        bp=H/'banks'/(c['id']+'.BANK.json.gz');pp=H/'banks'/(c['id']+'.PUBLIC.json.gz');save(bp,b);save(pp,{'public':p});item={'case':c,'bank':pin(bp),'public':pin(pp)};(training if split=='TRAIN' else evaluation).append(item)
    assert len(training)==10 and len(evaluation)==8;state=loadpt(CHECKPOINT);net=legacy.Learner(state=state);equal(net.snapshot(),state);assert state['network_sha256']==NETWORK;checks+=3
    write(H/'INPUTS.json',{'training':training,'evaluation':evaluation,'pool_members':pools_by,'canonical_TRAIN_EVAL_key_members_disjoint':True,'same_device_sessions_may_overlap':True,'max_scientific_units':105,'new_measurements':0})
    known=A/'results/A24_S26_JOINT_20261022_01/SCALE_CONF_N512_B8_L25_C75_D2__TEACHER_RISK.raw.json.gz';raw=read(known);late=[q for q in raw['result']['requests'] if q['response_ns'] is not None and q['response_ns']>q['deadline_ns']];diag=[]
    for q in late:
        calls=[c for c in raw['calls'] if q['queue_entry_ns']<=c['time_ns']<=q['dispatch_ns']];waits=[c for c in calls if c['action']['kind']!='DISPATCH' and any(a.get('request_id')==q['request_id'] for a in c['actions'])];diag.append({'request_id':q['request_id'],'task':q['task'],'deadline_s':q['deadline_ns']/1e9,'ready_s':q['queue_entry_ns']/1e9,'dispatch_s':q['dispatch_ns']/1e9,'response_s':q['response_ns']/1e9,'late_s':(q['response_ns']-q['deadline_ns'])/1e9,'waits_while_dispatch_candidate':len(waits),'source':pin(known)})
    write(V/'PRECHANGE_REVIEW.json',{'known_benchmark_review_not_independent':True,'late_examples':diag,'reason':'Fixed-horizon optimistic continuation can repeatedly permit WAIT despite urgent ready dispatch. Guard bounds WAIT using public latest-start slack.','new_environment':0})
    write(V/'PREFLIGHT.json',{'status':'PASS','checks':checks,'TRAIN_cases':10,'EVAL_cases':8,'new_science_START':0,'pool_counts':{s:{k:len(v) for k,v in p.items()} for s,p in pools_by.items()},'source_members_disjoint':True,'resources':resources(True)})
    paths=[R/p['path'] for p in prior['source_pins']]+list(H.glob('*.py'))+[H/'PROTOCOL.md',H/'INPUTS.json',OLD_RISK,known,V/'PRECHANGE_REVIEW.json',V/'PREFLIGHT.json']+list((H/'banks').iterdir())
    for module in list(sys.modules.values()):
        f=getattr(module,'__file__',None)
        if f:
            f=Path(f).resolve()
            if f.is_file() and f.is_relative_to(R) and f.suffix=='.py':paths.append(f)
    write(H/'OPERATION.json',{'id':'A24-S26-MATCH-04','unix':time.time(),'source_pins':[pin(p) for p in dict.fromkeys(paths)],'checkpoint':pin(CHECKPOINT),'network_sha256':NETWORK,'max_scientific_units':105,'planned_environments':102,'planned_residual_calibration':1,'planned_NN_fits':2,'NN_epochs':128,'fit_selection':'Second fixed fit, no EVAL selection','new_measurements':0,'new_physical_fit':0,'new_PPO':0,'old_completed_rerun':0,'automatic_retry':False,'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty':True,'authorization':'User asks to review matched S26 teacher/TRAIN differences and improve A24 result with existing neural BC.','adopted':False})
    for i,p in enumerate(CONTROLS):
        before=p.read_bytes();(V/f'CONTROL_BEFORE_{i}.bin').write_bytes(before);href='../results/A24_S26_MATCHED_BC_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/experiments/a24_s26_matched_bc_20261022/PROTOCOL.md';block=f'## 2026-10-22 A24-S26-MATCH-04 · S26조건 교사·BC 보완 등록\n\n[규약/예정결과]({href}). 사용자 후속지시로 TRAIN분포 차이와 교사 반복대기를 검토했다. 공개 긴급latest-start보다 긴 WAIT를 사전제외하고 현재C긴급.8/D일반2·N256/512·두혼합의TRAIN10개로여유추정/교사자료·원BC50신경망2회 학습을 준비했다. 원모형/기준선/완료결과 보존·실측/물리fit/PPO0이다.\n\n동결후새EVAL8입력×9정책으로 위험여유/guard/구NN/재학습효과를 분리한다. 최대105새START(환경102+여유1+BCfit2), EVAL사전pin·epoch128/fit2차선택고정·과학START0. 같은pool후속개발검증이며 새독립실측 아님. 다음: 공유잠금아래유한학습·평가→독립검산/모든손해→보고/봉인. HEAD ac3a5af+미커밋. 아래는이전이력이다.\n\n';p.write_bytes(block.encode()+before)
    print(json.dumps({'state':'PREPARED','checks':checks,'TRAIN':10,'EVAL':8,'max_START':105,'pools':{s:{k:len(v) for k,v in p.items()} for s,p in pools_by.items()}},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
