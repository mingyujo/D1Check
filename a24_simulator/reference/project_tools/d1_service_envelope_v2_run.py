"""New finite V2 development/confirmation, V1 evidence is preserved."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from tools import d1_service_envelope_run as parent
from tools import d1_service_envelope_v2_policy as x
ROOT=parent.ROOT;LOCAL=ROOT/'output/service_envelope_v2_20261011_v1';PUBLIC=ROOT/'docs/results/service_envelope_v2_20261011'
ROLES=('Band','Triton','CostV2');IDS=dict(parent.IDS,CostV2=x.COST)
read=parent.read;write=parent.write;sha=parent.sha;serial=parent.serial
def sources():
    paths={Path(m.__file__).resolve() for n,m in sys.modules.copy().items() if n.startswith('tools.') and getattr(m,'__file__',None)}
    paths|={ROOT/'tools/d1_service_envelope_v2_run.py',ROOT/'tools/test_d1_service_envelope_v2_policy.py'}
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths) if p.suffix=='.py'}
def register():
    if LOCAL.exists():raise FileExistsError('original V2 cap/clock retained')
    seeds=(835110101,835110102,835110103,835110104)
    for p in (ROOT/'output').glob('*/registration*.json'):
        if any(str(s) in p.read_text(encoding='utf-8') for s in seeds):raise ValueError('new confirmation seed previously registered')
    v1=read(ROOT/'output/service_envelope_20261011_v1/inputs.json');data=dict(development=v1['development'],fixtures=v1['fixtures'],confirmation=parent.native.prior.cases(seeds),representative=v1['representative'])
    reg=dict(task='IE-SERVICE-ENVELOPE-V2-02',registered_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),native_cap=192,learning_cap=0,active_seconds=900,save_reserve_seconds=180,expected_native=171,phase_caps=dict(gate=2,development=24,confirmation=144,representative=1),source_sha256=sources(),inputs_sha256=x.x.r.c.digest(data),exported_model_sha256=sha(x.x.r.h.MODEL),common_settings=x.x.r.h.prior.external.settings(),realization_seed=201,roles=ROLES,policy_ids=IDS,schema=x.SCHEMA,
        authorization='root explicit conditional V2 approval after273 stored-forecast CPU-only-only exclusions; original V1/learner source unchanged',guard_evidence_sha256=sha(ROOT/'docs/results/service_envelope_20261011/guard_attribution.json'),
        changed='P95 before queue-drainECT; remove only CPU-only individual response nonworsening, keep current miss/lateness/P95 equality protections and original R1waiting',
        limitations='current-prefix P95 is not full-trace guarantee; shared finite service/ECT suffix is approximate, not recursive V2 policy; no future arrivals',
        development_reused_baseline_sha256=sha(ROOT/'output/overnight_ie_20261011_v1/development_rows.json'),development_rule='stop confirmation if any development urgent/normal/incomplete count worsens vs Band or Triton; record P95 separately; no setting changes',
        final_gate='unchanged strict epsilon0 full completion/service/P95/J/AP nonworse and low/sustained absolute deadlines,primary-family one-axis strict gain',new_learning=0,device_commands=0,model_fit_calls=0,automatic_adoption=False,experiment_ready=False)
    LOCAL.mkdir();write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',data);write(PUBLIC/'execution_contract.json',reg);write(PUBLIC/'cases.json',data);return reg
def check():
    reg=read(LOCAL/'registration.json')
    for p,s in reg['source_sha256'].items():
        if sha(ROOT/p)!=s:raise ValueError('locked V2 source changed '+p)
    if x.x.r.c.digest(read(LOCAL/'inputs.json'))!=reg['inputs_sha256'] or sha(x.x.r.h.MODEL)!=reg['exported_model_sha256']:raise ValueError('model/input changed')
    return reg
def agent(role):
    if role=='CostV2':
        f,i,_=x.x.r.h.load();return x.Controller(f,i['initial'])
    return parent._agent(role)
native=parent.native;native.LOCAL=LOCAL;native.PUBLIC=PUBLIC;native.agent=agent;native.check=check;native.write=write
class Budget(parent.Budget):
    def __init__(self):super().__init__();self.deadline=datetime.fromisoformat(self.reg['registered_utc']).timestamp()+720
    def used(self):return dict(native_starts=len(self.rows),native_cap=192,new_learning=0,failed=sum(q['status']=='failed' for q in self.rows),device_commands=0,model_fit_calls=0)
    def call(self,*args,**kwargs):
        if len(self.rows)>=192 and not any(q['identity']==args[0] for q in self.rows):raise TimeoutError('new192 cap')
        return super().call(*args,**kwargs)
def row(raw,case,role):return dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,policy_id=IDS[role],**raw['row'])
def run():
    b=Budget();data=read(LOCAL/'inputs.json');lock=LOCAL/'owner.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    try:
        for q in data['fixtures']:b.call('gate_CostV2_'+str(q['condition']),'gate',q,'CostV2')
        dev=[]
        for q in data['development']:dev.append(row(b.call(f'development_CostV2_{q["condition"]:02d}','development',q,'CostV2'),q,'CostV2'))
        refs=[q for q in read(ROOT/'output/overnight_ie_20261011_v1/development_rows.json') if q['policy'] in ('Band','Triton')];reference={(q['condition'],q['policy']):q for q in refs}
        losses=[dict(condition=q['condition'],reference=r,metric=k,delta=q[k]-reference[q['condition'],r][k]) for q in dev for r in ('Band','Triton') for k in ('incomplete','urgent_failure','normal_failure') if q[k]>reference[q['condition'],r][k]]
        write(PUBLIC/'development_comparison.json',dev+refs);write(PUBLIC/'development_gate.json',dict(service_count_losses=losses,reused_baselines_native_starts=0))
        if losses:
            write(PUBLIC/'consumption.json',b.used());write(LOCAL/'WORKING_STATE.json',dict(phase='development_rejected_confirmation_not_started',consumption=b.used(),reason=losses));return dict(stopped='development service count loss',used=b.used())
        rows=[]
        for q in data['confirmation']:
            for role in ROLES:rows.append(row(b.call(f'confirmation_{role}_{q["condition"]:02d}','confirmation',q,role),q,role))
            write(LOCAL/'confirmation_rows.json',rows);print(json.dumps(dict(phase='confirmation',condition=q['condition'],used=b.used())),flush=True)
        verdict=native.verdict(rows,'CostV2',48);write(PUBLIC/'confirmation_comparison.json',rows);write(PUBLIC/'confirmation_verdict.json',verdict)
        rep=b.call('representative_CostV2','representative',data['representative'],'CostV2');write(PUBLIC/'representative_rows.json',[row(rep,data['representative'],'CostV2')])
        write(PUBLIC/'consumption.json',b.used());write(LOCAL/'WORKING_STATE.json',dict(phase='completed',consumption=b.used(),verdict=verdict));return verdict
    except BaseException:
        write(LOCAL/'WORKING_STATE.json',dict(phase='failed_or_budget_stopped',consumption=b.used()));raise
    finally:lock.unlink(missing_ok=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run'));a=p.parse_args();print(json.dumps(serial(globals()[a.command]()),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
