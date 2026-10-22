import copy,itertools,math
from scale_common import *

def hkey(s):return int(hashlib.sha256(s.encode()).hexdigest(),16)

def capacity(nominal,mix):
    best=None
    for a in range(201):
        for b in range(201):
            fc=a/200;fd=b/200;cpu=(mix*(1-fc)*sum(nominal['C_CPU'])+(1-mix)*(1-fd)*sum(nominal['D_CPU']))/3;gpu=mix*fc*sum(nominal['C_GPU'])+(1-mix)*fd*sum(nominal['D_GPU']);v=max(cpu,gpu)
            if best is None or v<best['demand']-1e-14:best={'demand':v,'capacity':1/v,'C_GPU_fraction':fc,'D_GPU_fraction':fd,'CPU_normalized_s':cpu,'GPU_s':gpu}
    return best

def pools():
    admitted=read(A/'experiments/common_count_20261021/INPUTS.json')['samples'];allowed={(s['key'],s['source']) for s in admitted if s['device']=='A24' and s['split']=='EVAL'};out={}
    for pattern in [0,1]:
        bank=read(A/f'experiments/a24_duration_040_20261019/banks/D040_T600_P{pattern}_S160.BANK.json.gz')
        for j in bank['jobs']:
            key=j['task']+'_ADMISSION';sid=j['admission']['sample_id']
            if (key,sid) in allowed:out.setdefault(key,{})[sid]={'id':sid,'delay_ns':j['admission']['scheduled_to_actual_ns']+j['admission']['actual_to_queue_ns']}
            for route,row in j['routes'].items():
                key=j['task']+'_'+route;sid=row['sample_id']
                if (key,sid) in allowed:out.setdefault(key,{})[sid]={'id':sid,'stages_ns':row['stages_ns'],'source':row.get('source'),'transfer':row.get('DG_transfer',False)}
    return {k:[v[s] for s in sorted(v)] for k,v in out.items()}

def make_case(setting,mix,phase,draw,pool,nominal,cap,prototype):
    n=setting['n'];burst=setting['burst'];rate=setting['load']*cap['capacity'];duration=n/rate;sid=f'SCALE_{phase}_{setting["id"]}_C{int(mix*100)}_D{draw}';public=copy.deepcopy(prototype);public['requests']=[];bank={'jobs':[],'nominal_vectors':{}};protos={t:next(q for q in prototype['requests'] if q['task']==t) for t in ['C','D']};spec=[]
    for i in range(n):
        group=i//burst;task='D' if (i%burst+group)%(4 if mix==.75 else 2)==0 else 'C';priority='U' if task=='C' else 'N';rid=f'scale-{i:06d}';arrival=round((35+group*burst/rate)*1e9);due=arrival+round((.8 if task=='C' else 2)*1e9);prefix=f'{phase}|{draw}|{mix}|{i}'
        seq=pool[task+'_ADMISSION'];ad=seq[hkey(prefix+'|ADMISSION')%len(seq)];entry=arrival+ad['delay_ns'];routes={}
        for route in ['CPU','GPU']:
            seq=pool[task+'_'+route];row=seq[hkey(prefix+'|'+route)%len(seq)];routes[route]={'stages_ns':row['stages_ns'],'sample_id':row['id'],'source':row['source'],'latent_work_coordinate':'OBSERVED_SERIAL_NS_OR_DECLARED_DG_TRANSFER','DG_transfer':row['transfer']};bank['nominal_vectors'][rid+'|'+route]=nominal[task+'_'+route]
        j={'request_id':rid,'ordinal':i,'task':task,'priority':priority,'scheduled_arrival_ns':arrival,'queue_entry_ns':entry,'deadline_ns':due,'admission':{'scheduled_to_actual_ns':ad['delay_ns'],'actual_to_queue_ns':0,'sample_id':ad['id'],'adapter':'PRESERVED_TOTAL_READY_DELAY'},'routes':routes};bank['jobs'].append(j);public['requests'].append({**protos[task],**{k:j[k] for k in ['request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns']}});spec.append({'ordinal':i,'profile':task+'_M128','priority':priority,'arrival_s':arrival/1e9,'deadline_s':due/1e9})
    stop=35+duration;dispatch=round((stop+45)*1e9);censor=round((stop+60)*1e9);end=round((stop+90)*1e9);case={'id':sid,'n':n,'temperature_c':26,'condition':{'role':phase,'setting':setting['id'],'n':n,'burst':burst,'mix':mix,'draw':draw,'nominal_load':setting['load'],'requests_per_second':rate,'rate_multiplier':rate,'load_kind':'S26_CRITERIA_SCALED_INPUT','supply_s':duration,'pattern':f'burst{burst}','seed_key':f'{phase}|{draw}|{mix}'},'supply_stop_s':stop,'service_stop_s':dispatch/1e9,'censor_s':censor/1e9,'drain_stop_s':end/1e9,'observation_end_s':end/1e9,'work_window':[35,dispatch/1e9],'common_potential_key':['A24_S26_SCALE_V1',phase,draw,mix],'input':{'requests':spec}}
    public.update(initial_ap_c=26,observations=[],service_stop_ns=dispatch,drain_stop_ns=end,observation_end_ns=end,public_scenario_sha256=B.L.digest(case['input']),public_initial_context_sha256=B.L.digest({'T':26,'z':0,'source':'PRESERVED_ORIGINAL_A24'}))
    return case,public,bank

def main():
    assert not O.exists() and not (H/'OPERATION.json').exists();(H/'banks').mkdir();V.mkdir(parents=True,exist_ok=True);pool=pools();nominal=read(A/'experiments/a24_s26_common_20261020/PROFILES.json')['A24']['nominal'];caps={str(m):capacity(nominal,m) for m in [.5,.75]};origin=read(A/'experiments/a24_bc_s26_requests_20261021/INPUTS.json')['cases'][0];prototype=read(R/origin['public']['path'])['public'];settings=[]
    for n,burst,load in itertools.product([256,512],[4,8],[.25,.5]):settings.append({'id':f'N{n}_B{burst}_L{int(load*100)}','n':n,'burst':burst,'load':load})
    for load in [.25,.5]:settings.append({'id':f'N512_B16_L{int(load*100)}','n':512,'burst':16,'load':load})
    cases=[];checks=0
    # All CONF inputs are prepared and pinned before DEV; only selected settings will be consumed.
    for setting in settings:
        for phase,draw in [('DEV',0),('CONF',1),('CONF',2)]:
            for mix in [.5,.75]:
                c,p,b=make_case(setting,mix,phase,draw,pool,nominal,caps[str(mix)],prototype);assert len(b['jobs'])==c['n'] and sum(q['task']=='C' for q in b['jobs'])==mix*c['n'];checks+=2
                for q,j in zip(p['requests'],b['jobs']):assert q['deadline_ns']-q['scheduled_arrival_ns']==(800000000 if q['task']=='C' else 2000000000) and j['queue_entry_ns']>=q['scheduled_arrival_ns'];checks+=1
                bp=H/'banks'/(c['id']+'.BANK.json.gz');pp=H/'banks'/(c['id']+'.PUBLIC.json.gz');save(bp,b);save(pp,{'public':p});cases.append({'case':c,'bank':pin(bp),'public':pin(pp)})
    state=legacy.loadpt(CHECKPOINT);assert state['network_sha256']==NETWORK;net=legacy.Learner(state=state);legacy.equal(net.snapshot(),state);checks+=2
    ph=P.physics();assert ph.cpu_slots==3 and ph.profile=='ORIGINAL';assert all(abs(ph.speed(26,r,1,t)-1)<1e-12 for r in ['CPU','GPU'] for t in ['C','D']);checks+=2
    for item in cases:
        public=read(R/item['public']['path'])['public'];bank=read(R/item['bank']['path']);model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']})
        for q in public['requests'][:4]:model.request_context(public,q);checks+=1
    write(H/'INPUTS.json',{'settings':settings,'cases':cases,'capacities':caps,'pool_members':pool,'new_training':0,'max_scientific_units':120})
    # Imported dependencies are read-only; freeze every actually loaded repository Python source.
    paths=[*H.glob('*.py'),H/'PROTOCOL.md',CHECKPOINT,A/'results/A24_NN_URGENT_TIE_20261021_01/RISK_CALIBRATION.json',A/'results/A24_NN_URGENT_TIE_20261021_01/INFERENCE_CONTRACT.json',A/'experiments/common_count_20261021/INPUTS.json',A/'experiments/a24_s26_common_20261020/PROFILES.json',R/origin['public']['path'],A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',A/'experiments/a24_parallel_20261018/OPERATION.json']
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            path=Path(path).resolve()
            if path.is_relative_to(R) and path.suffix=='.py' and path.is_file():paths.append(path)
    paths += list((H/'banks').iterdir())+[H/'INPUTS.json',P.old.PORT/'SHAPE.json']+[A/f'experiments/a24_duration_040_20261019/banks/D040_T600_P{i}_S160.BANK.json.gz' for i in [0,1]]
    write(V/'PREFLIGHT.json',{'status':'PASS','checks':checks,'prepared_cases':len(cases),'DEV_environments':100,'selected_CONFIRM_environments':20,'new_fit':0,'environment_START':0,'resources':resources(True),'capacity':caps})
    paths.append(V/'PREFLIGHT.json');write(H/'OPERATION.json',{'schema':'A24_S26_SCALE_V1','unix':time.time(),'source_pins':[pin(p) for p in dict.fromkeys(paths)],'checkpoint':pin(CHECKPOINT),'network_sha256':NETWORK,'max_scientific_units':120,'DEV':100,'CONF_selected':20,'new_fits':0,'new_measurements':0,'old_results_rerun':0,'automatic_retry':False,'adopted':False,'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'dirty':True,'authorization':'Same evaluation criteria; adjust A24 scale and find best metrics.','previous_local_derived':138095,'derived_local_cap':138215,'not_global_census':True})
    print(json.dumps({'state':'PREPARED','checks':checks,'cases':len(cases),'capacity':caps,'max_eval':120}),flush=True)
if __name__=='__main__':main()
