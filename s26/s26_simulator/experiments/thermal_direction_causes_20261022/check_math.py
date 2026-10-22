"""Independent numerical gradient of level/delta/direction-margin objective; no fits."""
from engine import *
from fit import hinge
rng=np.random.default_rng(226);n=11;D=np.zeros((4,n))
for j,(a,b) in enumerate([(0,3),(2,5),(4,7),(6,10)]):D[j,a]=-1;D[j,b]=1
labels=np.array([1,-1,0,0]);wl=np.full(n,1/n);wd=np.array([.1,.2,.3,.4]);wh=np.array([1.,2.,3.,4.]);p=rng.normal(size=n);y=rng.normal(size=n);prev=rng.normal(size=n);dy=rng.normal(size=4)
def independent_value(v):
    dd=D@v;hh=np.array([max(0,.22-dd[0]),max(0,dd[1]+.22),max(0,abs(dd[2])-.16),max(0,abs(dd[3])-.16)])
    return .5*float(wl@((v-y)**2+4*(v-prev)**2)+wd@((dd-dy)**2)+wh@(hh*hh))
err,active=hinge(D@p,labels);grad=wl*((p-y)+4*(p-prev))+D.T@(wd*(D@p-dy)+wh*err);eps=1e-6;finite=np.array([(independent_value(p+np.eye(n)[j]*eps)-independent_value(p-np.eye(n)[j]*eps))/(2*eps) for j in range(n)]);error=float(max(abs(grad-finite)));assert error<1e-7
# Explicit inactive and signed cases, including the STEADY dead zone.
e,a=hinge(np.array([.3,-.3,.1,-.1,.3,-.3]),np.array([1,-1,0,0,0,0]));assert np.allclose(e,[0,0,0,0,.14,-.14]) and np.array_equal(a,[False,False,False,False,True,True])
save(H/'MATH_CHECK.json',dict(status='PASS_INDEPENDENT_MARGIN_FINITE_DIFFERENCE',max_gradient_error=error,steady_dead_zone='PASS',rise_fall_signs='PASS',new_tree_fits=0));print(json.dumps(read(H/'MATH_CHECK.json')))
