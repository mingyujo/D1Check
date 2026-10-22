"""Create an isolated, finite route/capacity/reward study; never edit parents."""
import copy, datetime, hashlib, json, shutil
from pathlib import Path

W=Path(__file__).resolve().parent.parent
R=W/'S26-D1Check/s26_simulator'
P=R/'experiments/a24_stable_learning_v1'
N=R/'experiments/route_energy_v1'
assert not N.exists(), 'New namespace only'
N.mkdir()
for name in ['source','physics.cjs','public_observer.cjs','policy.cjs','result.cjs','server.cjs','nn_train.py','dynamics.py','controller.py']:
    source=P/name
    if source.is_dir(): shutil.copytree(source,N/name)
    else: shutil.copy2(source,N/name)

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(name,x): (N/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
base=read(P/'INPUTS.json')['cases']
cases=[]
for phase,replicates in [('TRAIN',[10]),('DEV',[11]),('EVAL',[12,13])]:
    for rep in replicates:
        for old in base:
            if old['phase']!=phase: continue
            if phase!='TRAIN' and old['nominal_load_ratio']==.4: continue
            c=copy.deepcopy(old)
            c['id']=old['id'].replace('_R'+str(old['replicate'])+'_','_R'+str(rep)+'_')
            c['replicate']=rep
            c['stream']=851000000+rep*100000+len(cases)*103
            # Preserve the registered burst16 arrivals, count, deadlines, load,
            # horizon and context. Only latent route sampling is fresh.
            cases.append(c)
for i in range(2):
    c=copy.deepcopy(cases[0]); c.update(id='P0_N64_C0.5_U0.4_R'+str(20+i),phase='P0',replicate=20+i,n=64,stream=859000000+i)
    c['requests']=c['requests'][:64]
    cases.append(c)
save('INPUTS.json',dict(schema='S26_ROUTE_ENERGY_INPUTS_V1',cases=cases,parent=str(P/'INPUTS.json'),fresh_actual_streams=True,arrival_pattern_reused_by_design=True))
save('BUDGET_RESERVATION.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),user_authority='2026-10-18 explicit route-choice bound, unprotected balanced RL, shared CPU constraint relaxation and results',known_conservative_before=128466,new_global_reservation=448,known_conservative_after=128914,shared_cap=137712,planned_START=420,cap=448,allocation=dict(P0=4,TRAIN_REFERENCE=32,TRAIN=96,DEV=96,EVAL=192),not_fresh_all_host_census=True,accounting='128238 S26 stable union includes deep-repair338; later A24 queue144+minmax72+witness12 added once. Existing failures/unspent preserved; no refunds.',automatic_retry=False))
save('PROTOCOL.json',dict(schema='S26_ROUTE_ENERGY_STUDY_V1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),primary_load=.85,loads=[.65,.85,1.05],models=['CENTRAL','CPU3'],seeds=[681081,681083,681087],parent_checkpoint=str(R/'experiments/a24_policy_repair_v1/artifacts/G001/REPAIR_S481083_EP032.pt.gz'),route_bound='Per-job counterfactual route draws, minimum inference over AP26..60, positive-system LP; includes CPU/route slot work and union constraints; continuous assignment relaxation ignores deadlines and ordering, not an achievable schedule or certified physical bound.',bound_gate='Report bound first; if optimistic margin >=5% at85%, perform finite balanced training. Feasible energy-only control also reports service losses.',CPU3='Same CENTRAL timing/interference and nonzero service work; up to3 concurrent CPU grants. Logical route slots CPU/GPU/NPU remain1 each. Extra core power is unidentified; report grant overlap and break-even power, no measured multithreading claim.',balanced_reward='TRAIN-frozen reference medians normalize incremental energy and excess AP. Urgent/normal miss cost normalized by each class; tail penalty reduced from.2 to.02. Lagrange multipliers adapt to TRAIN reference on-time target minus0.5pp, no action guard. Per-objective actor advantage RMS balancing prevents one cost unit from dominating.',training='16 episodes x3 seeds x2 CPU scenarios; identical parent weights, fresh Adam/RNG. 8 PPO updates each. Preserve all weights, frames, failures. Frozen parent and energy-only public rolling controls included.',evaluation='DEV 6 conditions and fresh EVAL 12 conditions,8 policies perCPU scenario. Freeze representative seed before EVAL; report all3 seeds, all inputs, class rates, response P95, allAVAILABLE, total API-J and temperatures.',selection='DEV only: minimize squared on-time deficits >0.5pp vs frozen RL separately for urgent/normal; then normalized energy+thermal, then seed. This selects checkpoints, never masks or replaces actions.',deadline_protection=False,post_NN_override=False,new_measurements=0,new_physical_fit=0,physical_validation=False,large_savings_claim_requires_equal_service=True,planned_START=420,environment_cap=448))
print(str(N))
