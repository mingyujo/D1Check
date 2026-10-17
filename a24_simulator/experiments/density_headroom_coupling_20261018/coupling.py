"""Strengthen the original relaxation; NEVER change the physical model.

Let A=integral(T-idle), E=increment energy, D=window duration, U=upper-idle.
RC gives A=R E-tau*(T_end-T_start), hence R E-tau U <= A <= R E.
For <=2 owners and active native steps <=tick, with |T'|<=L:
  sum_k (lo-idle)*W_k/fmax <= 2A + L*tick*D + eps.
  2A <= 2U*D + sum_k ((hi-idle)/fmin-U/fmax)*W_k
                         + L*tick*D + eps.
The second bound allocates the unoccupied time the favorable upper T=idle+U;
nonexecution time cancels. eps covers native nanosecond phase-end surplus.
For thermal LPs, upper/lower RC deposition kernels bound the true A from
the actual bin energy. All these are necessary inequalities for any schedule.
"""

def phase_upper(jobs,physics,env):
    """Bound hot nonexecution bursts using nonpreemptive job phase lengths.

    In any route interval, nonexecution time <=rho*duration+2*Nmax,
    since complete jobs satisfy that ratio and at most two boundary jobs are
    partial. Exponential RC convolution then bounds their excess forcing.
    The source engine's left-temperature steps add the Lipschitz*tick guard.
    """
    import math
    c=physics.c;U=env['upper_c'];H=physics.shared
    L=max(U-c.idle_c,c.thermal_resistance*env['power_upper'])/c.thermal_tau_s+1e-8
    eta=L*c.tick_s;routes={};extra=0
    for r in ('CPU','GPU'):
        slope=c.cpu_slope if r=='CPU' else c.gpu_slope
        f=physics.speed(U,r,1)
        derivative=-3*(1-c.leakage_fraction)*slope*f**4+c.leakage_fraction*c.leakage_per_c*math.exp(c.leakage_per_c*(U-c.reference_c))
        if f<=c.minimum_speed or derivative>=0:raise ValueError('Execution power monotonic proof outside scope')
        A=max(v-H for k,v in physics.solo.items() if k.endswith('_'+r))
        delta=A*(1-c.leakage_fraction)*(1-f**3)
        rho=burst=0.
        for j in jobs:
            v=[x/1e9 for x in j['routes'][r]['stages_ns']];non=sum(v)-v[1]+4e-9
            rho=max(rho,non/(non+max(0.,v[1]-1e-12)));burst=max(burst,2*non)
        routes[r]=dict(A=A,rho=rho,burst=burst,delta=delta,derivative_upper=derivative)
        extra+=delta*rho
    def mapping(B):
        T=B-eta;P=H
        for r,d in routes.items():
            f=physics.speed(T,r,1)
            P+=d['A']*((1-c.leakage_fraction)*f**3+c.leakage_fraction*math.exp(c.leakage_per_c*(T-c.reference_c)))
        return c.idle_c+c.thermal_resistance*(P+extra)
    lo=c.onset_c+eta;hi=U
    if mapping(hi)>hi:return dict(upper=U,original_upper=U,strengthened=False,routes=routes,eta=eta)
    if mapping(lo)<lo:B=lo
    else:
        for _ in range(100):
            mid=(lo+hi)/2
            if mapping(mid)>mid:lo=mid
            else:hi=mid
        B=hi
    burst=c.thermal_resistance/c.thermal_tau_s*sum(d['delta']*d['burst'] for d in routes.values())
    refined=min(U,B+burst+1e-6)
    return dict(upper=refined,original_upper=U,strengthened=refined<U,routes=routes,eta=eta,
                crossing_temperature=B,convolution_burst_c=burst,map_at_crossing=mapping(B),
                scope='All nonpreemptive jobs from this frozen route bank, including arbitrary ordering/waits, initial26C. No temperature clipping.')


def strengthen(problem,meta,jobs,physics,env):
    c=physics.c;U=env['upper_c']-c.idle_c
    lipschitz=max(U,c.thermal_resistance*env['power_upper'])/c.thermal_tau_s+1e-8
    err=lipschitz*c.tick_s
    epsilon=1e-3+U/c.minimum_speed*(len(jobs)+1)*1e-9
    low={};high={}
    for (task,r,k),idx in meta['modes'].items():
        lo,hi,fmax,fmin=env['modes'][r][k]
        low[idx]=(lo-c.idle_c)/fmax
        high[idx]=(hi-c.idle_c)/fmin-U/fmax
    extra=dict(U=U,lipschitz=lipschitz,step_error_per_second=err,rounding_slack=epsilon)
    if meta['thermal_end'] is None:
        old=list(problem.cost);T=meta['finish']
        e=problem.var('actual_increment',0,env['power_upper']*(meta['finish_limit']-35),1)
        for i in range(len(old)):
            if i!=T:problem.cost[i]=0
        allocated={i:v for i,v in enumerate(old) if i!=T and v}
        problem.atmost({**allocated,e:-1},0,'true energy >= allocated work bound')
        problem.atmost({e:1,T:-env['power_upper']},-35*env['power_upper'],'true bounded power')
        problem.atmost({**low,e:-2*c.thermal_resistance,T:-err},-35*err+epsilon,'thermal exposure cannot be free')
        rate=2*U+err
        problem.atmost({**{i:-v for i,v in high.items()},e:2*c.thermal_resistance,T:-rate},
                       2*c.thermal_tau_s*U-35*rate+epsilon,'cold execution cannot hide heat')
        extra['energy_variable']=e
    else:
        import math
        D=meta['thermal_end']-35;n=len(meta['deposit']);width=D/n
        upper={idx:c.thermal_resistance*(-math.expm1(-(D-k*width)/c.thermal_tau_s)) for k,idx in enumerate(meta['deposit'])}
        lower={idx:problem.cost[idx]*D for idx in meta['deposit']}
        problem.atmost({**low,**{i:-2*v for i,v in upper.items()}},err*D+epsilon,'temperature exposure vs upper deposition kernel')
        problem.atmost({**{i:-v for i,v in high.items()},**{i:2*v for i,v in lower.items()}},(2*U+err)*D+epsilon,'deposition heat vs occupied thermal work')
        # Actual temperatures obey the same phase-derived invariant at every
        # bin end. Move each bin's heat to its START to underestimate that
        # endpoint temperature, yielding another favorable necessary bound.
        for j in range(n):
            row={idx:c.thermal_resistance/c.thermal_tau_s*math.exp(-(j+1-k)*width/c.thermal_tau_s)
                 for k,idx in enumerate(meta['deposit'][:j+1])}
            problem.atmost(row,U,'phase barrier at deposition endpoints')
        extra['deposition_temperature_cap_rows']=n
    return extra
