from pathlib import Path
W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_energy_v1'
def edit(name,pairs):
    p=H/name;s=p.read_text(encoding='utf-8')
    for a,b in pairs:
        assert s.count(a)==1,(name,a,s.count(a));s=s.replace(a,b)
    p.write_text(s,encoding='utf-8')
edit('policy.cjs',[("Number(d>1e-9)+.2*Math.min(5,d/Math.max(.05,r.relative_deadline))", "Number(d>1e-9)+(state.balance?.tail??.2)*Math.min(5,d/Math.max(.05,r.relative_deadline))")])
edit('nn_train.py',[
("self.pending=[];self.logs=[]", "self.pending=[];self.logs=[];self.balance=None"),
("advantage=torch.tensor(-np.stack([f['adv'] for f in frames])@np.array(WEIGHTS),dtype=torch.float32)", """component_adv=np.stack([f['adv'] for f in frames]);component_RMS=None
        if self.balance is not None:
            learning=np.array([f['learn_actor'] for f in frames],bool)
            centered=component_adv-component_adv[learning].mean(0) if learning.any() else component_adv
            rms=np.sqrt(np.mean(centered[learning]**2,axis=0)).clip(1e-4) if learning.any() else np.ones(5)
            component_adv=centered/rms
            objective_weights=np.array([1.,1.,*self.balance['dual'],3.])
            component_RMS=rms.tolist()
        else: objective_weights=np.array(WEIGHTS)
        advantage=torch.tensor(-component_adv@objective_weights,dtype=torch.float32)"""),
("losses=[];kls=[];aux_weight=.05*math.exp(-self.updates/32.)", "losses=[];kls=[];aux_weight=(.15 if self.balance is not None else .05)*math.exp(-self.updates/32.)"),
("max_KL=max(kls),aux_weight=aux_weight,network_sha256=digest(self.net)", "max_KL=max(kls),aux_weight=aux_weight,component_RMS=component_RMS,objective_weights=objective_weights.tolist(),network_sha256=digest(self.net)")])
print('BALANCED_LABELED_COSTS_AND_ACTOR_RMS_READY')
