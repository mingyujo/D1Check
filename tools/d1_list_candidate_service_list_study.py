"""One frozen equal-work selector candidate; shared residual budget, no learning."""
import argparse,copy,json,os,time
from datetime import datetime
from pathlib import Path
from tools import d1_list_candidate_rl_develop as d
from tools import d1_list_candidate_service_list as s
from tools.d1_list_candidate_rl_main_report import gate

r=d.r

class Budget(d.Budget):
    def __init__(self,output,phase):
        self.output=Path(output);self.reg=r.read(self.output/'candidate_registration.json');self.phase=phase
        self.path=self.output/'execution.jsonl';self.rows=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if 'event' not in row:self.rows.append(row)
            else:self.rows[row['number']-1].update(row)
        self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+7200-300
        self.work_guard()
    def guard(self,learning=False):
        super().guard(learning)
        limit=24 if self.phase=='candidate_development' else 192
        if sum(row['phase']==self.phase for row in self.rows)>=limit:raise TimeoutError('candidate stage native cap')

def register(output):
    parent=r.read(output/'registration.json')
    if (output/'candidate_registration.json').exists():raise FileExistsError('candidate already frozen')
    if not (output/'nowait_results.json').exists():raise ValueError('first diagnosis incomplete')
    proposal=copy.deepcopy(parent)
    proposal.update(candidate_policy=s.POLICY,candidate_config=dict(request_wait_cap=.25,urgent_head_predicted_response_nonworse_vs_L0=True,
      normal_head_predicted_tardiness_nonworse_vs_L0=True,equal_current_head_work=True,common_forecast_horizon=True,
      energy_proxy_nonworse_vs_L0=True,rank=['past/future peak AP','common end AP','common horizon J','L0 tie']),
      candidate_trials=1,hyperparameter_tuning_trials=0,confirmation=r.cases((819030101,819030102,819030103,819030104)),
      confirmation_only_if_development_gate_pass=True,new_learning_starts=0,clock_inherited_without_reset=True,
      development_native_cap=24,confirmation_native_cap=192)
    for module in (s,):proposal['source_sha256'][Path(module.__file__).relative_to(r.ROOT).as_posix()]=r.sha(Path(module.__file__))
    proposal['source_sha256']['tools/d1_list_candidate_service_list_study.py']=r.sha(Path(__file__))
    proposal['confirmation_input_sha256']=r.c.digest([dict(case=q,requests=r.external.old.workload(q['family'],q['seed'])) for q in proposal['confirmation']])
    r.write(output/'candidate_registration.json',proposal)
    return proposal

def evaluate(budget,label):
    frozen,initial,_=r.inputs();rows=[]
    qlist=budget.reg['development' if label=='candidate_development' else 'confirmation']
    if label=='confirmation':
        if not r.read(budget.output/'candidate_development_gate.json')['promising']:raise ValueError('development not eligible; confirmation blocked')
        for role in ('L0','Band','Triton'):
            for i,q in enumerate(qlist):
                item=budget.call(f'fresh_{role}_{i:03d}',r.base_controller(role,frozen,initial),q)
                rows.append(dict(condition=i,case=q,policy=role,seed=None,training_episodes=0,**item['row']))
    else:
        previous=r.read(d.PRIOR/'evaluation_development_64.json')['rows']
        rows=[copy.deepcopy(row) for row in previous if row['seed'] is None and row['policy'] in ('L0','Band','Triton')]
    for i,q in enumerate(qlist):
        controller=s.ServiceList(frozen,initial,feature_variant='head2+C_next')
        item=budget.call(f'{label}_equal_work_{i:03d}',controller,q)
        rows.append(dict(condition=i,case=q,policy=s.POLICY,seed=None,training_episodes=0,**item['row'],control=item.get('control')))
        r.write(budget.output/'fair_work_records'/f'{label}_{i:03d}.json',controller.fair_work_records)
    decision=gate(rows,s.POLICY,len(qlist));decision['learners']=0;decision['candidate_type']='nonlearning service-aware list'
    r.write(budget.output/f'{label}_results.json',dict(status='completed',rows=rows,consumption=budget.consumption()))
    r.write(budget.output/f'{label}_gate.json',decision)
    return dict(status='completed',candidate_conditions=len(qlist),gate={k:v for k,v in decision.items() if k!='differences'},consumption=budget.consumption())

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--phase',required=True,choices=('register','development','confirmation'));a=p.parse_args()
    if a.phase=='register':print(json.dumps(dict(status='registered',policy=register(a.output)['candidate_policy'])));return
    phase='candidate_development' if a.phase=='development' else 'confirmation'
    if (a.output/f'{phase}_results.json').exists():raise FileExistsError('completed candidate evidence preserved')
    owner=a.output/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    budget=None
    try:
        budget=Budget(a.output,phase);print(json.dumps(evaluate(budget,phase),indent=2))
    except BaseException as error:
        r.write(a.output/f'{phase}_error.json',dict(error=repr(error),consumption=budget.consumption() if budget else None));raise
    finally:
        if owner.exists() and owner.read_text(encoding='ascii')==str(os.getpid()):owner.unlink()

if __name__=='__main__':main()
