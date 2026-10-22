'use strict';
const fs=require('fs'),path=require('path'),d=__dirname;
let s=fs.readFileSync(path.join(d,'../deep_repair_20261018/learner.py'),'utf8');
s=s.replace('from nn_train import Net,digest','from packing_net import Net\nfrom nn_train import digest').replace("VERSION='DEEP_REPAIR_SPLIT_PPO_V1'","VERSION='PACKING_PRIVILEGED_CLASS_PPO_V1'");
const a=s.indexOf('    def __init__('),b=s.indexOf('    def set_anchor(',a);if(a<0||b<0)throw Error('Learner constructor');
s=s.slice(0,a)+`    def __init__(self,original,anchor=False):
        self.seed=original['seed']
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.seed);self.net=Net()
        self.temperature=.15;self.entropy_weight=.003;self.lambda_time_s=100.
        self.actor_parameters=[*self.net.encode.parameters(),*self.net.actor.parameters()]
        self.actor_optimizer=torch.optim.Adam(self.actor_parameters,lr=.00015,eps=1e-5);self.critic_optimizer=torch.optim.Adam(self.net.critic.parameters(),lr=.001,eps=1e-5)
        self.action_rng=torch.Generator().manual_seed(self.seed+10000);self.shuffle_rng=torch.Generator().manual_seed(self.seed+20000);self.bc_rng=torch.Generator().manual_seed(self.seed+30000)
        self.episodes=self.updates=self.steps=self.bc_steps=0;self.pending=[];self.logs=[];self.bc_logs=[];self.anchor=None
        if original.get('version')==VERSION:
            self.net.load_state_dict(original['network']);self.actor_optimizer.load_state_dict(copy.deepcopy(original['actor_optimizer']));self.critic_optimizer.load_state_dict(copy.deepcopy(original['critic_optimizer']))
            self.action_rng.set_state(original['action_rng']);self.shuffle_rng.set_state(original['shuffle_rng']);self.bc_rng.set_state(original['bc_rng'])
            for k in ('episodes','updates','steps','bc_steps','pending','logs','bc_logs'):setattr(self,k,copy.deepcopy(original[k]))
            if original['anchor'] is not None:self.set_anchor(original['anchor'])
        if anchor:self.set_anchor(self.net.state_dict())
`+s.slice(b);
s=s.replace('expand(-1,19,-1)','expand(-1,x.shape[1],-1)').replace('teacher=torch.tensor(teacher)','teacher=torch.tensor(teacher,dtype=torch.float32)');
s=s.replace("target=.02*mask[ids]/mask[ids].sum(-1,keepdim=True);target.scatter_add_(1,teacher[ids,None],torch.full((len(ids),1),.98))","target=.02*mask[ids]/mask[ids].sum(-1,keepdim=True)+.98*teacher[ids]/teacher[ids].sum(-1,keepdim=True)");
s=s.replace("ok=logits.argmax(-1)==teacher[ids]","ok=teacher[ids].gather(1,logits.argmax(-1)[:,None]).squeeze(1)>0");
if(s.includes('scatter_add_')||s.includes('expand(-1,19'))throw Error('All action ABI sites changed');
fs.writeFileSync(path.join(d,'packing_learner.py'),s,{flag:'wx'});
let t=fs.readFileSync(path.join(d,'../sustained_load_20261017/tensor_reader.cjs'),'utf8').replace('48*32','48*40').replace('a<19','a<35');fs.writeFileSync(path.join(d,'tensor_reader.cjs'),t,{flag:'wx'});
console.log('PACKING_LEARNER_AND_READER_BUILT');
