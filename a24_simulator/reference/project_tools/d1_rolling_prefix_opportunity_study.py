"""At most eight preregistered public-state diagnostics, <=792 projections.

Native simulation/training/device caps are zero. Starts, including failed
forecasts, are durable and the original registration clock is never reset.
"""
import argparse,copy,csv,gzip,hashlib,json,os,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from tools import d1_rolling_prefix_opportunity as m
from tools import d1_rolling_prefix_selection as selector
ROOT=m.p.ROOT;LOCAL=ROOT/'output/rolling_prefix_opportunity_20261010_v1'
PUBLIC=ROOT/'docs/results/rolling_prefix_opportunity_05'
POLICY=m.previous.POLICY
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def raw(p):return json.loads(gzip.decompress(Path(p).read_bytes()))
def loaded_sources():
    result={}
    for name,module in sys.modules.copy().items():
        path=getattr(module,'__file__',None)
        if name.startswith('tools.') and path:
            path=Path(path).resolve()
            if path.suffix=='.py' and path.is_relative_to(ROOT):result[path.relative_to(ROOT).as_posix()]=sha(path)
    result['tools/d1_rolling_prefix_opportunity_study.py']=sha(__file__);return result
def register():
    if LOCAL.exists():raise FileExistsError('same diagnostic cannot restart with a new budget')
    inputs=read(ROOT/'docs/results/rolling_prefix_01/inputs.json');states=[]
    for index,case in enumerate(inputs['cases']['development']):
        if case['context']!='mean':continue
        identity=f'development/{index}/{POLICY}'
        path=ROOT/'output/rolling_prefix_20261009_v1/items'/(identity.replace('/','__')+'.json.gz')
        item=raw(path);ds=item['result']['decisions']
        blocked=[i for i,d in enumerate(ds) if d.get('prefix_guard_blocked')]
        selected=[i for i,d in enumerate(ds) if d.get('action_kind') in ('single','bundle','cool_wait') and d.get('reason')==POLICY]
        chosen=blocked[0] if blocked else selected[0] if selected else None
        states.append(dict(case_index=index,seed=case['seed'],family=case['family'],context='mean',identity=identity,
            raw_path=path.relative_to(ROOT).as_posix(),raw_sha256=sha(path),callback_index=chosen,
            now_ns=ds[chosen]['now_ns'] if chosen is not None else None,
            selection='earliest_guard_blocked' if blocked else 'earliest_declared_nonBand_action' if selected else 'no_selected_state'))
    assert len(states)==8
    prior=read(ROOT/'output/rolling_expert_review_20261010_v1/WORKING_STATE.json')['consumption']
    assert prior['cumulative_policy_environment']==9749 and prior['cumulative_policy_learning']==1449
    LOCAL.mkdir(parents=True);PUBLIC.mkdir(parents=True,exist_ok=True)
    reg=dict(task='ROLLING-PREFIX-OPPORTUNITY-05',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        registered_utc=datetime.now(timezone.utc).isoformat(),active_seconds=2700,save_reserve_seconds=300,
        authorization='user: 진행해봐, after proposed eight-state diagnostic',states=states,
        projection_cap=792,screen_cap=576,prefix_reference_cap=216,native_environment_cap=0,learning_cap=0,device_cap=0,
        old_policy_environment_count=9749,old_policy_learning_count=1449,old_IE_cap_spent=480,old_IE_cap=480,old_budget_reopened=False,
        old_window=4,old_shortlist=8,old_candidate_space_and_coefficients_preserved=True,
        reconstruction_tolerance=dict(AP_c=1e-9,J=1e-9,P95_ms=1e-6,explanation='P951ns from recorded transition rounding, not policy margin; AP/J original arithmetic checks'),
        actual_admission_epsilon=selector.EPS,final_KPI_epsilon=0,
        future_arrivals_in_forecast=False,actual_future_costs_in_observation=False,confirmation_used=False,
        wait='timer or first predicted lane AVAILABLE then Band; conditional no new arrivals; no forced future target',
        source_sha256=loaded_sources(),inputs_sha256=sha(ROOT/'docs/results/rolling_prefix_01/inputs.json'),
        diagnostic_is_policy_performance=False)
    write(LOCAL/'registration.json',reg);write(PUBLIC/'registration.json',reg);return reg
class Budget:
    def __init__(self):
        self.reg=read(LOCAL/'registration.json');self.rows=[]
        for line in (LOCAL/'projections.jsonl').read_text().splitlines() if (LOCAL/'projections.jsonl').exists() else []:
            row=json.loads(line)
            if row.get('event'):self.rows[row['number']-1].update(row)
            else:self.rows.append(row)
        self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+2400
    def used(self):return dict(model_projection_starts=len(self.rows),projection_cap=792,
        failed=sum(r['status']=='failed' for r in self.rows),native_environment_starts=0,learning_starts=0,device_commands=0,
        cumulative_policy_environment_starts=9749,cumulative_policy_learning_starts=1449)
    def append(self,row):
        with (LOCAL/'projections.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def call(self,identity,kind,fn):
        path=LOCAL/'projections'/(identity+'.json');old=next((r for r in self.rows if r['identity']==identity),None)
        if old:
            if old['status']!='completed' or sha(path)!=old['sha256']:raise ValueError('failed/changed consumed projection')
            return read(path)
        if time.time()>=self.deadline or len(self.rows)>=792:raise TimeoutError('shared projection/clock cap')
        limit=576 if kind=='screen' else 216
        if sum(r['kind']==kind for r in self.rows)>=limit:raise TimeoutError('stage projection cap')
        for name,h in self.reg['source_sha256'].items():
            if sha(ROOT/name)!=h:raise ValueError('registered diagnostic source changed: '+name)
        row=dict(number=len(self.rows)+1,identity=identity,kind=kind,status='started');self.rows.append(row);self.append(row)
        try:
            result=fn();write(path,result);row.update(status='completed',sha256=sha(path));self.append(dict(event='completion',**row));write(LOCAL/'progress.json',self.used());return result
        except BaseException as error:
            row.update(status='failed',error=repr(error));self.append(dict(event='failure',**row));write(LOCAL/'progress.json',self.used());raise
def state_key(controller,queue,lanes,now):
    value=dict(now_ns=now,queue=queue,lanes=lanes,t=controller.t,h=controller.h,grid=controller.grid,
        estimates=controller.estimates,credit=controller.credit,observed_responses=controller.observed_responses,
        band_expected=controller.band.expected,band_running=controller.band.running,hold=controller.hold,pending=controller.pending)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def diagnose(budget,index,state):
    row=dict(index=index,seed=state['seed'],family=state['family'],context='mean',selection=state['selection'],
        now_s=state['now_ns']/1e9 if state['now_ns'] is not None else None,status='unknown',reason='',unique_prefixes=0,admissible=0,opportunity=False)
    if state['callback_index'] is None:row['reason']='no_selected_state';return row
    if sha(ROOT/state['raw_path'])!=state['raw_sha256']:raise ValueError('raw source changed')
    item=raw(ROOT/state['raw_path']);frozen,_=m.p.inputs(m.p.BUNDLE);initial=read(ROOT/'docs/results/rolling_prefix_01/inputs.json')['initial']
    controller=m.previous.Controller(frozen,initial);tape=m.PublicTape(item)
    try:queue,lanes,now=tape.restore(controller,state['callback_index'])
    except (ValueError,StopIteration) as error:row['reason']='public_restore:'+str(error);return row
    if not controller.response_counters_valid:row['reason']='public_response_phase_unavailable';return row
    key=state_key(controller,queue,lanes,now);row.update(state_key=key,queued=len(queue),rounded_transition_records=tape.rounded_only)
    expected=next((r for r in item['prefix_guards'] if r['now_ns']==now),None)
    record=next((r for r in item['plans'] if r['now_ns']==now and r['selected_plan'] is not None),None)
    if expected is None or record is None:row['reason']='ambiguous_or_missing_selected_plan';return row
    references={c:budget.call(f's{index}_reference_{c}','prefix',lambda c=c:m.old.fast.forecast(controller,queue,lanes,now,dict(jobs=[]),c)) for c in selector.CONTEXTS}
    errors={}
    for c in selector.CONTEXTS:
        if not references[c]['valid']:row['reason']='reference_unavailable:'+references[c].get('reason','');return row
        for k,tol in [('peak_ap_c',1e-9),('global_peak_ap_c',1e-9),('remaining_increment_j',1e-9),('urgent_p95_ms',1e-6)]:
            a,b=references[c].get(k),expected['references'][c].get(k)
            if (a is None)!=(b is None):row['reason']='reference_null_mismatch';return row
            if a is not None:
                errors[c+'.'+k]=abs(a-b)
                if abs(a-b)>tol:row.update(reason='saved_reference_not_recovered',reconstruction_errors=errors);return row
        for k in ('urgent_misses','normal_misses'):
            if references[c][k]!=expected['references'][c][k]:row['reason']='reference_miss_count_mismatch';return row
        references[c]['state_key']=key
    row['reconstruction_errors']=errors
    window=m.old.window_requests(controller,queue,lanes,now);plans=m.old.candidate_plans(window,controller.credit,controller.allow_wait);screened=[]
    for ordinal,plan in enumerate(plans):
        f=budget.call(f's{index}_screen_{ordinal:02d}','screen',lambda plan=plan:m.old.forecast_plan(controller,window,lanes,now,plan,'mean'))
        if not f['valid']:continue
        first=(plan[0]['request_id'],plan[0]['backend'],plan[0]['delay_ns'])
        score=(f['urgent_misses'],f['normal_misses'],f['remaining_increment_j'],f['peak_ap_c'],f['urgent_p95_ms'] or 0.,ordinal)
        screened.append((score,first,ordinal,plan))
    counts={};short=[]
    for _,first,ordinal,plan in sorted(screened,key=lambda x:x[0]):
        if counts.get(first,0)>=2:continue
        counts[first]=counts.get(first,0)+1;short.append((ordinal,plan))
        if len(short)==8:break
    if len(plans)!=record['candidate_count'] or len(screened)!=record['screen_valid'] or len(short)!=record['full_plan_count']:
        row['reason']='original_shortlist_counts_not_recovered';return row
    if record['selected_plan'] not in [plan for _,plan in short]:row['reason']='original_winner_not_in_restored_shortlist';return row
    baseline=controller.band.decide({},queue,lanes,now,{},None,None)
    band_action=dict(kind='single',jobs=[baseline['selected']]) if baseline['selected'] else dict(kind='band_event_wait')
    unique={};plan_actions=[]
    for ordinal,plan in short:
        action=m.actual_action(controller,plan,queue,lanes,now)
        if action is None:continue
        signature=selector.signature(action);unique.setdefault(signature,(ordinal,action));plan_actions.append(dict(ordinal=ordinal,plan=plan,signature=signature))
    candidates=[]
    for ordinal,action in unique.values():
        fs={c:budget.call(f's{index}_action_{ordinal:02d}_{c}','prefix',lambda c=c,action=action:m.forecast(controller,queue,lanes,now,action,c,key)) for c in selector.CONTEXTS}
        candidates.append(dict(ordinal=ordinal,action=action,state_key=key,semantics=selector.DISPATCH if action['kind'] in ('single','bundle') else selector.WAIT,forecasts=fs))
    past=max(controller.grid.values(),default=controller.t)
    chosen=selector.select(candidates,references,band_action,past_peak_c=past,state_key=key,now_ns=now)
    row.update(status='diagnosed',reason=chosen['reason'],unique_prefixes=len(unique),admissible=chosen['admissible'],opportunity=chosen['chosen'] is not None)
    if chosen.get('score'):row.update(delta_global_AP=chosen['score'][0],delta_increment_J=chosen['score'][1])
    write(LOCAL/f'states/state_{index}.json',dict(row=row,public_queue=queue,public_lanes=lanes,snapshot_state_key=key,
        past_peak_c=past,controller_observation=dict(t=controller.t,h=controller.h,credit=controller.credit,observed_responses=controller.observed_responses,band_expected=controller.band.expected),
        restored_shortlist=plan_actions,references=references,candidates=candidates,selection=chosen,
        unknown_future_arrival_assumption=True,not_policy_performance=True))
    return row
def run():
    reg=read(LOCAL/'registration.json');budget=Budget();owner=LOCAL/'owner.lock';rows=[]
    if (LOCAL/'completion.json').exists():raise FileExistsError('completed diagnostic preserved')
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    try:
        # Fail loudly if any helper accidentally starts a native environment.
        with patch.object(m.old.fast.old.external.old.engine,'simulate',side_effect=AssertionError('native environment forbidden')):
            for index,state in enumerate(reg['states']):
                row=diagnose(budget,index,state);rows.append(row);write(LOCAL/'state_rows.json',rows)
                print(json.dumps(dict(done=index+1,row=row,consumption=budget.used())),flush=True)
        result=dict(status='completed_diagnostic',rows=rows,consumption=budget.used(),
            opportunities=sum(r['opportunity'] for r in rows),unknown=sum(r['status']=='unknown' for r in rows),
            performance_claim=False,independent_confirmation=0,policy_connected=False)
        write(LOCAL/'completion.json',result);write(PUBLIC/'summary.json',result)
        fields=['index','seed','family','context','selection','now_s','status','reason','queued','unique_prefixes','admissible','opportunity','delta_global_AP','delta_increment_J']
        with (PUBLIC/'state_summary.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(rows)
        write(LOCAL/'WORKING_STATE.json',dict(task=reg['task'],phase='completed',consumption=budget.used(),result='diagnostic_only',next_action='report all states; no automatic policy simulation or learning'))
    finally:
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['register','run']);args=parser.parse_args()
    if args.phase=='register':print(json.dumps(register(),ensure_ascii=False,indent=2))
    else:run()
