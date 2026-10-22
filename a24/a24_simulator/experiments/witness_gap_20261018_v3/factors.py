"""Controlled information/candidate interventions; unchanged physical engine."""
from pathlib import Path
import copy,math,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'deep_repair_20261018'))
from common import B,ROOT,read,saved
sys.path.insert(0,str(HERE.parent/'density_headroom_20261018'))
from actors import Actor
from resources import wait_resources

def candidates(state,nominal,physics,turn):
    q=state['queue'];free=[r for r in ('CPU','GPU') if r not in {o['route'] for o in state['owners']}]
    now=state['now_ns']/1e9
    def tie(j):return j['scheduled_arrival_ns'],j['ordinal'],j['request_id']
    def occ(j,r):return sum(nominal.vector(j,r,state))/physics.speed(state['sensor']['temperature_c'],r,1)
    avg=sum(occ(j,r) for j in q for r in free)/(len(q)*len(free))
    def atc(j,r):
        d=occ(j,r);return math.log((2 if j['priority']=='U' else 1)/max(.001,d))-max(0.,j['deadline_ns']/1e9-now-d)/max(.2,2*avg)
    edf=sorted(q,key=lambda j:(j['deadline_ns'],*tie(j)));head=min(q,key=tie);rr=min([j for j in q if j['task']==turn] or q,key=tie)
    ranked=sorted(q,key=lambda j:max(atc(j,r) for r in free),reverse=True)
    def power(j,r):return physics.solo[('classification' if j['task']=='C' else 'detection')+'_'+r]
    energy=min(q,key=lambda j:(min(sum(nominal.vector(j,r,state))*power(j,r) for r in free),tie(j)))
    lowpower=min(q,key=lambda j:(min(power(j,r) for r in free),tie(j)))
    chosen={j['request_id']:j for j in [*edf[:3],head,rr,ranked[0],energy,lowpower]}
    assert len(chosen)<=8
    return sorted(chosen.values(),key=lambda j:(j['deadline_ns'],*tie(j)))

class FactorActor(Actor):
    def __init__(self,jobs,physics,nominal,preferred,protected,work_actual,protected_hindsight,lp_preferred,cap8=False):
        if not work_actual:
            # Only frozen public profile estimates are retained by this actor.
            jobs=[dict(request_id=j['request_id'],routes={r:dict(stages_ns=[x*1e9 for x in nominal.vector(j,r,{})]) for r in ('CPU','GPU')}) for j in jobs]
        super().__init__('LP_ROUTE' if lp_preferred else 'TOTAL',jobs,physics,nominal,preferred if lp_preferred else {},protected if protected_hindsight else [])
        self.public_protection=not protected_hindsight;self.cap8=cap8;self.turn='C'
        self.factors=dict(work_actual=work_actual,protected_hindsight=protected_hindsight,lp_preferred=lp_preferred,cap8=cap8)
    def __call__(self,state):
        visible=state if not self.cap8 else {**state,'queue':candidates(state,self.nominal,self.physics,self.turn)}
        if self.public_protection:self.protected={j['request_id'] for j in visible['queue']}
        action=super().__call__(visible)
        if action['kind']=='DISPATCH':
            j=next(j for j in state['queue'] if j['request_id']==action['request_id']);self.turn='D' if j['task']=='C' else 'C'
        self.calls[-1].update(factors=self.factors,original_queue_size=len(state['queue']),candidate_ids=[j['request_id'] for j in visible['queue']])
        return action

def definitions():
    return [dict(label=f'W{w}_H{h}_L{l}',work_actual=bool(w),protected_hindsight=bool(h),lp_preferred=bool(l),cap8=False) for w in (0,1) for h in (0,1) for l in (0,1)]+[
        dict(label='W1_H1_L1_CAP8',work_actual=True,protected_hindsight=True,lp_preferred=True,cap8=True),
        dict(label='W0_H0_L0_CAP8',work_actual=False,protected_hindsight=False,lp_preferred=False,cap8=True)]

def setup(op,case):
    catalog=read(B.L.pin(B.registration(op)['catalog_pin']));public,contexts=B.public_input(case,catalog);public['initial_ap_c']=case['temperature_c']
    jobs=read(op['bank_map'][case['id']]['path'])['jobs'];nominals=read(op['public_nominals']['path'])[case['id']]
    nominal=B.SavedNominal(public,[dict(nominal_vectors=nominals)])
    physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**op['physics']))
    original=read(op['original_RL']['path'])['result'];protected=[q['request_id'] for q in original['requests'] if q['response_ns']<=q['deadline_ns']]
    x=read(op['original_LP_certificate']['path'])['problem']['x']
    preferred={j['request_id']:max(('CPU','GPU'),key=lambda r:x[4*i+(0 if r=='CPU' else 2)]) for i,j in enumerate(jobs)}
    return public,B.BankModel(jobs,contexts),jobs,nominal,physics,preferred,protected

def make(spec,jobs,physics,nominal,preferred,protected):
    return FactorActor(jobs,physics,nominal,preferred,protected,**{k:spec[k] for k in ('work_actual','protected_hindsight','lp_preferred','cap8')})
