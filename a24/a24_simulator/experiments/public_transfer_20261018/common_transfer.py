"""Frozen A24 inputs/physics; new public-policy experiment only."""
from pathlib import Path
import sys,copy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'deep_repair_20261018'))
from common import B,ROOT,np,torch,read,saved,pt,loadpt
sys.path.insert(0,str(HERE.parent/'witness_gap_20261018_v3'))
from page_resources import wait_resources
sys.path.insert(0,str(HERE.parent/'packing_rl_20261018'))
from packing_encoder import PackingEncoder,tie
from fluid import VisibleFluid
sys.path.insert(0,str(HERE))
from event_engine import run as execute
NS=1_000_000_000
WIDTH=48
ACTIONS=36
def equal(a,b):
    if torch.is_tensor(a):assert torch.equal(a,b),'Tensor replay'
    elif isinstance(a,np.ndarray):assert np.array_equal(a,b),'Array replay'
    elif isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:equal(a[k],b[k])
    elif isinstance(a,(list,tuple)):
        assert len(a)==len(b)
        for u,v in zip(a,b):equal(u,v)
    else:assert a==b,'Scalar replay'
