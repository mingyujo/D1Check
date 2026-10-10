"""Separately registered development-only repair, sharing original counters."""
import argparse,copy,json,os
from datetime import datetime
from pathlib import Path
from tools import d1_list_candidate_service_list_study as original
from tools import d1_list_candidate_service_backlog as candidate
from tools.d1_list_candidate_rl_main_report import gate

r=original.r

class Budget(original.Budget):
    def __init__(self,output):
        self.output=Path(output);self.reg=r.read(self.output/'backlog_registration.json');self.phase='backlog_development'
        self.path=self.output/'execution.jsonl';self.rows=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if 'event' not in row:self.rows.append(row)
            else:self.rows[row['number']-1].update(row)
        self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+7200-300
        self.work_guard()
    def guard(self,learning=False):
        original.d.Budget.guard(self,learning)
        if sum(row['phase']==self.phase for row in self.rows)>=24:
            raise TimeoutError('backlog development stage cap24')

def register(output):
    if (output/'backlog_registration.json').exists():raise FileExistsError('repair already registered')
    v=copy.deepcopy(r.read(output/'candidate_registration.json'))
    if r.read(output/'candidate_development_gate.json')['promising']:raise ValueError('repair not needed')
    v.update(candidate_policy=candidate.POLICY,reason='V1 current-head service guard did not preserve queued normal service; normal failures76 vs24',
      repair_rule='positive wait forbidden when more than one arrived detection request is queued',
      policy_version_separate=True,evaluation_scope='development diagnosis only, not original48 independent adoption',
      no_coefficient_threshold_or_reward_tuning=True,confirmation_blocked_in_this_runner=True)
    for module in (candidate,):v['source_sha256'][Path(module.__file__).relative_to(r.ROOT).as_posix()]=r.sha(Path(module.__file__))
    v['source_sha256']['tools/d1_list_candidate_service_backlog_study.py']=r.sha(Path(__file__))
    r.write(output/'backlog_registration.json',v)

def evaluate(budget):
    frozen,initial,_=r.inputs()
    old=r.read(original.d.PRIOR/'evaluation_development_64.json')['rows']
    rows=[copy.deepcopy(row) for row in old if row['seed'] is None and row['policy'] in ('L0','Band','Triton')]
    for i,q in enumerate(budget.reg['development']):
        ctrl=candidate.BacklogList(frozen,initial,feature_variant='head2+C_next')
        item=budget.call(f'backlog_development_{i:03d}',ctrl,q)
        rows.append(dict(condition=i,case=q,policy=candidate.POLICY,seed=None,training_episodes=0,**item['row'],control=item.get('control')))
        r.write(budget.output/'fair_work_records'/f'backlog_{i:03d}.json',ctrl.fair_work_records)
    decision=gate(rows,candidate.POLICY,24);decision['learners']=0
    r.write(budget.output/'backlog_development_results.json',dict(status='completed',rows=rows,consumption=budget.consumption()))
    r.write(budget.output/'backlog_development_gate.json',decision)
    return dict(status='completed',gate={k:v for k,v in decision.items() if k!='differences'},consumption=budget.consumption())

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--phase',choices=('register','development'),required=True);a=p.parse_args()
    if a.phase=='register':register(a.output);print('registered V2 separately; budget/clock not reset');return
    if (a.output/'backlog_development_results.json').exists():raise FileExistsError('completed repair evidence preserved')
    owner=a.output/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    try:print(json.dumps(evaluate(Budget(a.output)),indent=2))
    finally:
        if owner.exists() and owner.read_text(encoding='ascii')==str(os.getpid()):owner.unlink()

if __name__=='__main__':main()
