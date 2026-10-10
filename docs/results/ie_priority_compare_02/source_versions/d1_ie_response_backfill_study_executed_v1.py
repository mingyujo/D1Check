"""Single development amendment sharing the original consumed budget and clock."""
import argparse,hashlib,json,os,time
from datetime import datetime,timezone
from tools import d1_ie_priority_compare_study as s
from tools import d1_ie_response_backfill as m
PHASE='response_development'
class Budget(s.Budget):
    def __init__(self,output):
        self.amend=s.read(output/'response_registration.json');super().__init__(output,PHASE)
    def guard(self,starting=True):
        super().guard(False)
        for path,h in self.amend['source_sha256'].items():
            if s.sha(s.ROOT/path)!=h:raise ValueError('amendment source changed: '+path)
        if starting and (len(self.rows)>=480 or sum(r['phase']==PHASE for r in self.rows)>=28):raise TimeoutError('shared/stage cap')
def run(output):
    output=output.resolve();amendfile=output/'response_registration.json'
    if amendfile.exists():raise FileExistsError('completed/started amendment cannot acquire fresh budget')
    prior=s.read(output/'progress.json')['consumption'];assert prior['new_environment_starts']==448
    assert s.read(output/'confirmation_completion.json')['status']=='completed' and not (output/'owner.lock').exists()
    reg=s.read(output/'registration.json')
    paths=('tools/d1_ie_response_backfill.py','tools/d1_ie_response_backfill_study.py','tools/test_d1_ie_response_backfill.py')
    amend=dict(task='IE-RESPONSE-GUARD-03',registered_utc=datetime.now(timezone.utc).isoformat(),
        source_sha256={p:s.sha(s.ROOT/p) for p in paths},parent_registration_sha256=s.sha(output/'registration.json'),
        parent_consumed=448,shared_cap=480,new_expected=28,extra_learning=0,original_clock_reset=False,
        deadline_utc=datetime.fromtimestamp(datetime.fromisoformat(reg['registered_utc']).timestamp()+2400,timezone.utc).isoformat(),
        rule='strict EDD head/CPU busy D/GPU empty: GPU-now response <= CPU-wait response; full arrived EDD suffix every response <= baseline',
        forecast_is_guarantee=False,setting_search=0,independent_confirmation=0,already_seen_confirmation_not_reused=True,
        development=reg['development'],gate_fixtures=reg['fixtures'],selected_as_final=False,
        common_realization=reg['actual_realization_seed'],energy_AP_service_coefficients_changed=False,
        representative_selected_before_amendment_results=dict(condition=20,reason='development public opportunity diagnosis'))
    s.write(amendfile,amend);budget=Budget(output);frozen,case=s.p.inputs(s.p.BUNDLE);rows=[]
    owner=output/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    try:
        gates=[]
        for i,q in enumerate(reg['fixtures']):
            item=budget.call(f'response_gate_{i}',m.Controller(frozen,case['initial']),q)
            old=json.loads(__import__('gzip').decompress((output/'items'/f'gate_EDD_{i}.json.gz').read_bytes()))
            gates.append(all(item['result'][k]==old['result'][k] for k in ('ledger','transitions','metrics')))
        if not all(gates):raise ValueError('unchanged small fixture regression')
        base=s.read(output/'development_results.json')['rows']
        for i,q in enumerate(reg['development']):
            item=budget.call(f'response_development_{i:03d}',m.Controller(frozen,case['initial']),q)
            corrections=sum(d.get('reason')==m.POLICY for d in item['result']['decisions'])
            rows.append(dict(identity=f'response_development_{i:03d}',condition=i,case=q,policy='ResponseGuard',seed=None,
                training_episodes=0,**item['row'],GPU_response_corrections=corrections))
        gates={name:s.gate_report.gate(base+rows,'ResponseGuard',24) for name in ['common_original_gate']}
        s.write(output/'response_results.json',dict(status='completed',rows=rows,gates=gates,fixture_exact=gates and all(gates),
            consumption=budget.consumption(),independent_confirmation=0,new_learning=0))
        print(json.dumps(dict(status='completed',corrections=sum(r['GPU_response_corrections'] for r in rows),consumption=budget.consumption())))
    finally:
        if owner.exists() and owner.read_text() == str(os.getpid()):owner.unlink()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',required=True,type=s.Path);args=a.parse_args();s.torch.set_num_threads(1);run(args.output)
