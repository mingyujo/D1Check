"""Pure public-state/ABI/physics/learner contracts; environment START zero."""
import ast,copy,time
from common_transfer import *
from transfer_policy import Policy
from transfer_learner import Learner,digest
from transfer_rewards import labels
def main():
    op=read(HERE.parent/'deadline_event_20261018/OPERATION.json');design=read(op['inputs']['path']);case=next(c for c in design['evaluation'] if c['id']=='DENSITY_050_0');cat=read(B.L.pin(B.registration(op)['catalog_pin']));public,contexts=B.public_input(case,cat);bank=read(op['bank_map'][case['id']]['path']);vectors=read(op['public_nominals']['path'])[case['id']];nominal=B.SavedNominal(public,[dict(nominal_vectors=vectors)]);physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**op['physics']))
    raw=read(ROOT/'results/THERMAL_COEFFICIENTS_20261018_01/BASE__DENSITY_050_0__PACKING_PUBLIC.raw.json.gz');states=[d['public_state'] for d in raw['result']['decisions'] if d['action']['kind']=='DISPATCH'];states=states[:6]+[s for s in states if s['owners']][:6];checks=0;fixtures=[];begin=time.monotonic()
    for stage in (1,2,3,4):
        actor=Policy(nominal,physics,case,stage=stage)
        for st in states:
            before=copy.deepcopy(st);b,actions,*_=actor.encode(st);assert st==before;assert b['x'].shape==(36,48) and b['mask'].shape==(36,) and np.isfinite(b['x']).all();assert int(b['mask'].sum())==len(actions);checks+=5
            assert all(a['route'] not in {o['route'] for o in st['owners']} for a in actions if a['kind']=='DISPATCH');assert any(a['kind']=='DISPATCH' for a in actions);checks+=2
            dirty=copy.deepcopy(st);dirty['future_arrivals']=[dict(secret=999)];dirty['actual_remaining_work']=-999;b2,*_=actor.encode(dirty);assert np.array_equal(b['x'],b2['x']) and np.array_equal(b['mask'],b2['mask']);checks+=2
            assert any(a['kind']=='WAIT_EVENT' for a in actions)==(stage>=3 and bool(st['owners']) and st['wait_used_ns']<12*NS);checks+=1
            if stage==4:fixtures.append(dict(state=st,actions=actions,x=b['x'].tolist()))
    for balanced in (False,True):
        learner=Learner(981001,balanced);snap=learner.snapshot();replica=Learner(state=snap);actor=Policy(nominal,physics,case,stage=1);b,*_=actor.encode(states[0]);i,a=learner.choose(b,True);j,c=replica.choose(b,True);assert i==j and a['old_logp']==c['old_logp'];equal(learner.snapshot(),replica.snapshot());checks+=3
        # A meaningful nonzero update and exact optimizer/RNG restoration contract.
        frames=[]
        for k,st in enumerate(states[:4]):
            bb,*_=actor.encode(st);idx,f=learner.choose(bb,True);f['time_ns']=35*NS+k*100_000_000;frames.append(f)
        after_actions=learner.snapshot();cost=np.zeros((len(frames),5));cost[:,0]=np.arange(1,len(frames)+1)*.1;cost[:,2]=.03
        learner.add(frames,cost);learner.add(frames,cost);replay=Learner(state=after_actions);replay.add(frames,cost);replay.add(frames,cost);equal(learner.snapshot(),replay.snapshot());assert digest(learner.net)!=snap['network_sha256'];checks+=2
    sources=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'));sources.append(dict(path=str(p),sha256=B.G.sha(p)))
    B.G.write_new(HERE/'PREFLIGHT_FIXTURES.json',dict(rows=fixtures,public_nominals_path=op['public_nominals']['path'],case=case['id']))
    B.G.write_new(HERE/'PREFLIGHT.json',dict(status='PASS',checks=checks,public_state_fixtures=len(states),rolling_fixtures=len(fixtures),AST=sources,new_environment_START=0,new_training_environments=0,synthetic_optimizer_contracts=2,elapsed_s=time.monotonic()-begin));print('PUBLIC_TRANSFER_PREFLIGHT_PASS',checks,round(time.monotonic()-begin,3))
if __name__=='__main__':main()
