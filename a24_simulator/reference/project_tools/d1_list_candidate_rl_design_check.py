"""Static design audit only. No policy, learner, simulator or device imports."""
import hashlib,itertools,json,math,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/results/list_candidate_rl_design_01'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def affine_params(sizes):return sum(a*b+b for a,b in zip(sizes,sizes[1:]))

def abstract_bank(cq,dq,occupancy,credit,deadline):
    """Abstract design cases, not an implemented scheduler or environment."""
    cpu,gpu=occupancy
    cp=cq and cpu is None and gpu is None
    cg=cq and gpu is None and cpu in (None,'D')
    dp=dq and cpu is None
    actions=[]
    def add(kind,jobs,duration=0.):
        item=dict(kind=kind,jobs=jobs,duration=duration)
        signature=(tuple(jobs),duration)
        if not any((tuple(a['jobs']),a['duration'])==signature for a in actions):actions.append(item)
    if cp:add('C_CPU_NOW',[('C','CPU')])
    if cg and dp:
        add('PAIR_NOW',[('C','GPU'),('D','CPU')])
        for wait,label in ((.125,'SHORT'),(.25,'FULL')):
            delay=min(.25,wait,deadline)
            if delay>1e-9:
                add('C_GPU_DEFER_D_'+label,[('C','GPU')],delay)
                add('D_CPU_DEFER_C_'+label,[('D','CPU')],delay)
    elif cg:add('C_GPU_NOW',[('C','GPU')])
    elif dp:add('D_CPU_NOW',[('D','CPU')])
    if actions:
        for wait,label in ((.125,'SHORT'),(.25,'FULL')):
            delay=min(credit,wait,deadline)
            if delay>1e-9:add('DEFER_ALL_'+label,[],delay)
    return actions

def audit():
    c=read(B/'design_contract.json')
    for p,h in c['source_basis'].items():assert sha(ROOT/p)==h,p
    assert c['status']=='design_only' and not any(c['implemented'].values())
    a=c['architecture'];assert a['base_policy']==a['training_reference']=='LIST_SERVICE_FIRST_PC_V3'
    assert a['rl_policy']=='LIST_CANDIDATE_CONSTRAINED_PPO_V3' and 'Band_reference_reward' in a['excluded_online'] and 'rolling_horizon' in a['excluded_online']
    assert all('Band' not in x and 'rolling' not in x and 'CPSAT' not in x for x in a['online_components'])
    obs=c['observations'];assert len(obs['state_fields'])==obs['state_size']==56 and len(obs['candidate_fields'])==obs['candidate_size']==28
    assert len(set(obs['state_fields']))==56 and len(set(obs['candidate_fields']))==28
    assert not set(obs['state_fields']+obs['candidate_fields'])&set(obs['forbidden'])
    assert 'observed_urgent_P95_over_1500ms' in obs['state_fields'] and obs['p95_known_via_positive_observed_count']
    assert obs['unknown_tensor_fill']==0 and obs['unknown_reported_value'] is None and obs['unknown_validity_flag_required']
    n=c['network'];count=sum(affine_params(n[k]) for k in ('state_layers','candidate_layers','score_layers','critic_layers'))
    assert count==n['parameter_count']==16455 and not n['fixed_BASE_bonus'] and not n['old_weights_compatible'] and not n['reuse_old_optimizer']
    model=read(ROOT/'docs/results/online_policy_study_01/overnight_sustained_run01/model.json');assert model['ap']['g']==c['plant']['g']==0
    assert c['plant']['deadlines_s']==dict(classification=1.5,detection=6.) and c['plant']['max_owned_lanes']==2
    occupancy=[(None,None),('C',None),(None,'C'),('D',None),('D','C')];abstract_cases=[]
    for cq,dq,state,credit,deadline in itertools.product((False,True),(False,True),occupancy,(0.,.125,.25),(0.,.1,6.)):
        actions=abstract_bank(cq,dq,state,credit,deadline);assert len(actions)<=c['candidate_bank']['max_live']==8
        assert len({(tuple(a['jobs']),a['duration']) for a in actions})==len(actions)
        for action in actions:
            assert len(action['jobs'])<=2 and len({b for q,b in action['jobs']})==len(action['jobs'])
            for q,b in action['jobs']:
                assert (q=='C' and cq) or (q=='D' and dq)
                assert b!='GPU' or q=='C'
                assert state[0 if b=='CPU' else 1] is None
                assert not (q=='C' and b=='CPU' and state[1]=='C')
                assert not (q=='C' and b=='GPU' and state[0]=='C')
            assert 0<=action['duration']<=.25
            if not action['jobs']:assert action['duration']<=credit and action['duration']>1e-9
        abstract_cases.append(dict(C_head=cq,D_head=dq,CPU=state[0],GPU=state[1],credit_s=credit,deadline_remaining_s=deadline,candidates=len(actions)))
    assert max(r['candidates'] for r in abstract_cases)==8 and len(abstract_cases)==180
    # Algebraic reward cases and inserted zero-time observations; not samples.
    for initial,observed,end,reference in ((30.,[30.,31.,31.5],32.,31.8),(29.,[29.,29.,29.],29.5,30.),(31.,[31.,31.1],31.1,31.)):
        previous=initial;rewards=[]
        for peak in observed:rewards.append(-(peak-previous));previous=peak
        rewards[-1]+=reference-initial-(end-previous)
        assert abs(sum(rewards)-(reference-end))<1e-12
    obj=c['objective'];assert obj['gamma']==1 and obj['signed_dual_cost_not_positive_part_only'] and not obj['CPO_optimizer_or_guarantee']
    assert max(0.,min(100.,1.+.01*(-2)))<1. and max(0.,min(100.,1.+.01*2))>1.
    f=c['future_plan'];b=f['environment_proposal_breakdown']
    assert sum(b.values())==f['total_expected_environment_max']==1448 and sum(b[k] for k in ('implementation','L0_training_references','resume_learning_fixture','main_learning','development'))==512
    assert f['total_proposed_learning_cap']==32+192+192==416 and not f['execution_authorized_by_this_design']
    assert f['main_training_seeds']==[11,23,37] and f['episodes_per_seed']==64 and f['dev_conditions']==24 and f['final_conditions']==48
    assert c['consumption']['cumulative_environment_starts']+f['total_proposed_cap']<=20000 and c['consumption']['cumulative_learning_starts']+416<=6144
    assert c['consumption']['new_environment_starts']==c['consumption']['new_learning_starts']==c['consumption']['device_commands']==0
    assert c['preserved']['experiment_ready'] is False and c['preserved']['independent_AP_work_preserved']
    inventory=read(B/'prior_list_inventory.json')
    assert inventory['environment_starts']==0 and len(inventory['records'])==3
    for record in inventory['records']:
        assert record['same_task_FIFO'] and not record['FIFO_violations']
        assert record['planned']==record['completed']==192 and not record['decision_intents_available']
    if (B/'artifact_manifest.json').exists():
        for p,h in read(B/'artifact_manifest.json')['artifacts'].items():assert sha(ROOT/p)==h,p
    result=dict(status='PASS',scope='static design audit; not policy/simulator/training/device verification',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        checker_sha256=sha(Path(__file__)),contract_sha256=sha(B/'design_contract.json'),state_fields=56,candidate_fields=28,parameters=count,abstract_cases=180,
        maximum_abstract_candidates=8,reward_algebra_cases=3,prior_FIFO_records=3,proposed_budget_checked=True,environment_starts=0,learning_starts=0,device_commands=0)
    print(json.dumps(result,indent=2));return result
if __name__=='__main__':audit()
