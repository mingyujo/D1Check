"""Meaningful public-input, candidate, fluid, ABI and restore contracts."""
import ast,copy,hashlib,json,math,subprocess
from run_packing import *
from fluid import optimum

def main():
    base=read(HERE.parent/'minmax_joint_20261018/OPERATION.json');case=next(c for c in read(base['inputs']['path'])['evaluation'] if c['id']=='DENSITY_300_0');jobs=read(base['bank_map'][case['id']]['path'])['jobs'];vectors=read(HERE.parent/'guard_learning_20261018/PUBLIC_NOMINAL_CATALOG.json.gz')[case['id']]
    nominal=B.SavedNominal(dict(requests=[dict(request_id=j['request_id']) for j in jobs]),[dict(nominal_vectors=vectors)]);physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**base['physics']))
    public=lambda j:{k:j[k] for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','queue_entry_ns','deadline_ns')}
    states=[]
    for count,owner in [(12,False),(80,False),(80,True)]:
        chosen=jobs[:count];queue=[public(j) for j in chosen[1 if owner else 0:]];now=max(j['queue_entry_ns'] for j in chosen)+1_000_000;owners=[]
        if owner:
            j=chosen[0];owners=[dict(**public(j),route='CPU',dispatch_ns=now-100_000_000,stage=1,phase_start_ns=now-90_000_000,public_progress_s=.09,response_ns=None)]
        states.append(dict(now_ns=now,queue=queue,owners=owners,sensor=dict(temperature_c=34.,shared_z=.8,peak_c=35.,increment_so_far=10.),wait_used_ns=0,initial_ap_c=26.,queue_count=len(queue)))
    fixtures=[];allx=[];allm=[];allteacher=[]
    for state in states:
        a=PackingEncoder(nominal,physics,case);bank,actions,chosen,details,fluid=a.encode(state)
        assert bank['x'].shape==(35,40) and bank['mask'].shape==(35,) and bank['mask'].any() and np.isfinite(bank['x']).all()
        assert len(chosen)<=16 and (len(state['queue'])>16 or {j['request_id'] for j in chosen}=={j['request_id'] for j in state['queue']})
        for task in ('C','D'):
            for priority in ('U','N'):
                for fit in (True,False):
                    group=[j for j in state['queue'] if j['task']==task and j['priority']==priority and fluid.feasible[j['request_id']]==fit]
                    if group:assert any(j in chosen for j in group),'All public semantic groups represented'
        # Check the analytical fluid minimum against a two-dimensional grid.
        best=fluid.base['objective'];g=fluid.groups
        for i in range(11):
            for k in range(11):
                gpu={'C':g['C']['n']*i/10.,'D':g['D']['n']*k/10.};lc=fluid.owner_loads['CPU']+sum((g[t]['n']-gpu[t])*g[t]['CPU']['duration'] for t in ('C','D'));lg=fluid.owner_loads['GPU']+sum(gpu[t]*g[t]['GPU']['duration'] for t in ('C','D'));energy=sum((g[t]['n']-gpu[t])*g[t]['CPU']['energy']+gpu[t]*g[t]['GPU']['energy'] for t in ('C','D'));assert best<=energy+fluid.rate*max(lc,lg)+1e-8
        other=copy.deepcopy(state);other['hidden_future_jobs']=[dict(routes='corrupted')];b=PackingEncoder(nominal,physics,case).encode(other);assert np.array_equal(bank['x'],b[0]['x']) and actions==b[1],'No future/latent inputs read'
        target=np.zeros(35,bool);target[np.flatnonzero(bank['mask'])[0]]=True;allx.append(bank['x']);allm.append(bank['mask']);allteacher.append(target)
    # A full-queue expert may choose a different ID in the same public class.
    state=states[1];group=state['queue'][len(state['queue'])//2];free='CPU'
    class Fake:
        def __call__(self,s):return dict(kind='DISPATCH',request_id=group['request_id'],route=free)
    expert=PackingEncoder(nominal,physics,case,expert=Fake());assert expert(state)['request_id']==group['request_id'] and expert.frames[0]['teacher_mask'].any()
    initial=Learner(dict(seed=base['learner_seed']));initial.distill(np.stack(allx),np.stack(allm),np.stack(allteacher),2);snapshot=initial.snapshot();restored=Learner(copy.deepcopy(snapshot));equal(snapshot,restored.snapshot())
    for state in states:
        actor=PackingEncoder(nominal,physics,case,restored,False);action=actor(state);call=actor.calls[-1];f=actor.frames[-1];call.update(old_logp=f['old_logp'],critic_value=f['value'].tolist(),collect=False)
        with torch.no_grad():logits,_=restored.forward(torch.from_numpy(f['x'])[None],torch.from_numpy(f['mask'])[None])
        fixtures.append(dict(state=state,case_n=case['n'],call=call,logits=logits[0].tolist()))
    pt(HERE/'PREFLIGHT_NET.pt.gz',snapshot);B.G.write_new(HERE/'PREFLIGHT_FIXTURES.json',dict(rows=fixtures,network_sha256=digest(restored.net),nominal_catalog_path=str(HERE.parent/'guard_learning_20261018/PUBLIC_NOMINAL_CATALOG.json.gz'),case='DENSITY_300_0',physics=base['physics']))
    source=(HERE/'run_packing.py').read_text(encoding='utf8');tree=ast.parse(source);receipts=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='dict' and {'event','identity','durable_START_consumed'}<={k.arg for k in n.keywords}];assert len(receipts)==1 and 'start_id' in {k.arg for k in receipts[0].keywords}
    parsed=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'));parsed.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    node=[]
    for p in HERE.glob('*.cjs'):subprocess.run([base['node_executable'],'--check',str(p)],check=True);node.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    subprocess.run([base['node_executable'],str(HERE/'preflight.cjs')],check=True)
    B.G.write_new(HERE/'PREFLIGHT.json',dict(status='PASS',contracts=8,ABI=[35,40],candidate_cap=16,public_only_fixture_states=3,fluid_grid_checks=363,actual_engine_receipt_contract=True,synthetic_test_BC_epochs=2,synthetic_test_BC_optimizer_steps=initial.bc_steps,new_environment_START=0,new_scientific_training_data=0,new_physical_fit=0,AST=parsed,Node_check=node,producer_import_pass=True))
    print('PACKING_PREFLIGHT_PASS',flush=True)
if __name__=='__main__':main()
