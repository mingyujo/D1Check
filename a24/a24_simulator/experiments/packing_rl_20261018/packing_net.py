"""A larger public set ABI, with no fixed action logits."""
import torch
from torch import nn
from packing_encoder import WIDTH,ACTIONS
class Net(nn.Module):
    def __init__(self):
        super().__init__();self.encode=nn.Sequential(nn.Linear(WIDTH,48),nn.Tanh());self.actor=nn.Sequential(nn.Linear(144,64),nn.Tanh(),nn.Linear(64,1));self.critic=nn.Sequential(nn.Linear(96,64),nn.Tanh(),nn.Linear(64,5));nn.init.zeros_(self.actor[-1].weight);nn.init.zeros_(self.actor[-1].bias)
    def forward(self,x,mask):
        e=self.encode(x);mean=(e*mask[:,:,None]).sum(1)/mask.sum(1,keepdim=True).clamp_min(1);maximum=e.masked_fill(~mask[:,:,None],-1e9).max(1).values;context=torch.cat((mean,maximum),-1)
        logits=self.actor(torch.cat((e,context[:,None,:].expand(-1,ACTIONS,-1)),-1)).squeeze(-1)
        return logits.masked_fill(~mask,-1e9),self.critic(context)
