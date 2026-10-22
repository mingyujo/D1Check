import warnings
import numpy as np
from scipy.optimize import linprog,OptimizeWarning
from scipy.sparse import csr_matrix,eye,bmat,vstack
def solve(x,y,w,low,high,ridge,guard=None,limit=None):
    n,p=x.shape;xx=csr_matrix(x);ii=eye(n,format='csr');ip=eye(p,format='csr');a=bmat([[xx,-ii,None],[-xx,-ii,None],[ip,None,-ip],[-ip,None,-ip]],format='csr');rhs=np.r_[y,-y,np.zeros(2*p)]
    ng=0
    if guard is not None and len(guard):
        guard=np.array(guard);limit=np.array(limit);assert guard.shape[1]==p;ng=len(guard);a=vstack([a,csr_matrix(np.column_stack([guard,np.zeros((ng,n+p))]))],format='csr');rhs=np.r_[rhs,limit]
    cost=np.r_[np.zeros(p),w,np.full(p,ridge)]
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected',category=OptimizeWarning)
        ans=linprog(cost,A_ub=a,b_ub=rhs,bounds=[*zip(low,high),*([(0,None)]*(n+p))],method='highs',options={'threads':1,'parallel':False,'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
    assert ans.success,(ans.status,ans.message);b=ans.x[:p];objective=float(w@abs(x@b-y)+ridge*sum(abs(b)));dual=ans.ineqlin.marginals;lo=ans.lower.marginals[:p];hi=ans.upper.marginals[:p];dualobj=float(rhs@dual+low@lo+high@hi);assert abs(objective-dualobj)<1e-7
    return b,{'objective':objective,'dual_objective':dualobj,'dual':dual.tolist(),'lower':lo.tolist(),'upper':hi.tolist(),'nrows':n,'ncoeff':p,'nguards':ng,'threads':1,'message':ans.message}
