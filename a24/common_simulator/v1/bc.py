"""One feature ABI, set network, balanced compatible-label BC for both devices.

Old A24/S26 checkpoint versions are deliberately incompatible. No training on import.
"""
import copy
import hashlib
import math
import torch
from torch import nn

VERSION = 'DEVICE_COMMON_METHOD_V1'
WIDTH, ACTIONS = 50, 27

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.encode = nn.Sequential(nn.Linear(WIDTH, 48), nn.Tanh())
        self.actor = nn.Sequential(nn.Linear(144, 64), nn.Tanh(), nn.Linear(64, 1))
        self.critic = nn.Sequential(nn.Linear(96, 64), nn.Tanh(), nn.Linear(64, 5))
        nn.init.zeros_(self.actor[-1].weight)
        nn.init.zeros_(self.actor[-1].bias)

    def forward(self, x, mask):
        if x.shape[-2:] != (ACTIONS, WIDTH) or not mask.any(-1).all():
            raise ValueError('Common feature/mask ABI')
        e = self.encode(x)
        mean = (e * mask[..., None]).sum(1) / mask.sum(1, keepdim=True)
        maximum = e.masked_fill(~mask[..., None], -1e9).max(1).values
        ctx = torch.cat((mean, maximum), -1)
        logits = self.actor(torch.cat((e, ctx[:, None].expand(-1, ACTIONS, -1)), -1)).squeeze(-1)
        return logits.masked_fill(~mask, -1e9), self.critic(ctx.detach())

def network_hash(net):
    h = hashlib.sha256()
    for k, v in sorted(net.state_dict().items()):
        h.update(k.encode());h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()

def distill(frames, *, seed, registered_fit=None, synthetic=False, epochs=64):
    if not synthetic and not (registered_fit and registered_fit.get('fit_id') and registered_fit.get('authorized')):
        raise ValueError('Registered BC fit required')
    if not 1 <= epochs <= 64 or not frames:
        raise ValueError('Finite BC limit')
    if any(f['version'] != VERSION or f.get('split') != 'TRAIN' for f in frames):
        raise ValueError('Common TRAIN-only input required')
    if synthetic and any(f.get('source_kind') != 'SYNTHETIC' for f in frames):
        raise ValueError('Synthetic test mode cannot train on measured demonstration frames')
    x = torch.tensor([f['x'] for f in frames], dtype=torch.float32)
    mask = torch.tensor([f['mask'] for f in frames], dtype=torch.bool)
    target = torch.tensor([f['teacher_mask'] for f in frames], dtype=torch.bool)
    if not torch.isfinite(x).all() or not target.any(1).all() or (target & ~mask).any():
        raise ValueError('Finite features and physically legal teacher labels')
    groups = sorted({f['group'] for f in frames})
    counts = {g:sum(f['group'] == g for f in frames) for g in groups}
    weights = torch.tensor([len(frames)/(len(groups)*counts[f['group']]) for f in frames])
    # Local RNGs; initializing this learner does not change a running learner's RNG.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed);net = Net()
    rng = torch.Generator().manual_seed(seed+30000)
    parameters = [*net.encode.parameters(), *net.actor.parameters()]
    opt = torch.optim.Adam(parameters, lr=1e-3, eps=1e-5)
    logs=[]
    for epoch in range(epochs):
        losses=[]
        for ids in torch.randperm(len(frames), generator=rng).split(256):
            logits, _ = net(x[ids], mask[ids]);logits=logits/.35
            loss=((logits.logsumexp(-1)-logits.masked_fill(~target[ids], -1e9).logsumexp(-1))*weights[ids]).mean()
            if not torch.isfinite(loss):raise ValueError('Nonfinite BC loss')
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(parameters, 1.);opt.step();losses.append(float(loss.detach()))
        with torch.no_grad():
            pred=net(x,mask)[0].argmax(-1);good=target.gather(1,pred[:,None]).squeeze(1)
            per={g:float(good[torch.tensor([f['group']==g for f in frames])].float().mean()) for g in groups}
        log=dict(epoch=epoch+1,loss=sum(losses)/len(losses),accuracy=float(good.float().mean()),per_group=per);logs.append(log)
        if log['accuracy']>=.995 and min(per.values())>=.99 and log['loss']<=.05:break
    return dict(version=VERSION,feature_width=WIDTH,actions=ACTIONS,network=copy.deepcopy(net.state_dict()),network_sha256=network_hash(net),optimizer=copy.deepcopy(opt.state_dict()),bc_rng=rng.get_state().clone(),seed=seed,logs=logs,groups=counts,synthetic_only=synthetic)

def restore(state, *, allow_synthetic=False):
    if state.get('version')!=VERSION or state.get('feature_width')!=WIDTH or state.get('actions')!=ACTIONS:
        raise ValueError('Different policy/feature schema; re-encoding and new BC required')
    if state.get('synthetic_only') and not allow_synthetic:
        raise ValueError('Synthetic unit-test checkpoint is not a research policy')
    with torch.random.fork_rng(devices=[]):
        net=Net()
    net.load_state_dict(state['network'])
    if network_hash(net)!=state['network_sha256']:raise ValueError('Checkpoint hash')
    return net

def choose(net, bank):
    if bank['version']!=VERSION:raise ValueError('Common bank version')
    with torch.no_grad():
        x=torch.tensor([bank['x']],dtype=torch.float32);mask=torch.tensor([bank['mask']],dtype=torch.bool)
        index=int(net(x,mask)[0][0].argmax())
    if not bank['mask'][index]:raise ValueError('Illegal model choice')
    return index
