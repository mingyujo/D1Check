from pathlib import Path
import gzip,io,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/guard_learning_20261018'))
import run_learning_v2 as B
sys.path.insert(0,str(HERE))
import numpy as np
import torch
torch.set_num_threads(1)
B.G.OWN_TOKENS+=('deep_repair_20261018',)
def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def pt(p,x):
    b=io.BytesIO();torch.save(x,b);B.save_binary(p,gzip.compress(b.getvalue(),mtime=0))
def loadpt(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
def saved(p,x):B.save_binary(p,gzip.compress(B.G.canonical(x).encode(),mtime=0))
def selector(bank,kind):
    x=np.asarray(bank['x']);ids=np.flatnonzero(bank['mask'])
    if kind=='BANK_ATC':
        ids=[i for i in ids if x[i,4]==0]
        return int(max(ids,key=lambda i:(x[i,10],x[i,6],x[i,2],-i)))
    if kind=='WEIGHTED':return int(min(ids,key=lambda i:(bank['scores'][i],i)))
    if kind in ('LEX_EDF','LEX_ATC'):
        return int(min(ids,key=lambda i:(x[i,27],x[i,25]+x[i,26],x[i,25],.5*x[i,23]+.5*x[i,24],i)))
    raise ValueError(kind)
class Selector:
    def __init__(self,kind):self.kind=kind
    def choose(self,bank,collect):
        i=selector(bank,self.kind)
        return i,dict(x=bank['x'].copy(),mask=bank['mask'].copy(),scores=bank['scores'].copy(),index=i,old_logp=0.,value=np.zeros(5),collect=False,learn_actor=False,network_sha256=None)
