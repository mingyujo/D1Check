"""Geometry of measured state occupancy; no coefficient fitting or device commands."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from tools import d1_pooled_energy_candidate as candidate
from tools import d1_online_policy_model as m
from tools import d1_arrival_plan as p


def geometry(x):
    x=np.asarray(x,dtype=float)
    singular=np.linalg.svd(x,compute_uv=False)
    out=[]
    for j in range(x.shape[1]):
        col=x[:,j];other=np.delete(x,j,axis=1)
        residual=col-other@np.linalg.lstsq(other,col,rcond=None)[0]
        norm=float(np.linalg.norm(residual));total=float(np.linalg.norm(col))
        out.append(dict(column=j,residual_norm=norm,column_norm=total,
            independent_fraction=norm/total if total else None,
            coefficient_change_bound_per_unit_l2_energy=1/norm if norm>1e-10 else None))
    return dict(rank=int(np.linalg.matrix_rank(x)),singular_values=singular.tolist(),
        condition=float(singular[0]/singular[-1]) if singular[-1]>1e-10 else None,columns=out)


def audit(cases):
    rows=[];windows=[]
    names=('resident_intercept',)+m.STATES
    for c in cases:
        seg=c['inputs']['segments'];tot=m.exposure(seg,0,120)
        for j,state in enumerate(m.STATES):
            lengths=[]
            for s in seg:
                if m.states.state_key(s['state'])==state:
                    dt=max(0,min(120,s['end_s'])-max(0,s['start_s']))
                    if dt:lengths.append(dt)
            rows.append(dict(id=c['id'],policy=c['policy'],state=state,seconds=float(tot[j]),
                visits=len(lengths),max_contiguous_s=max(lengths,default=0),
                visits_at_least_1s=sum(t>=1 for t in lengths),visits_at_least_5s=sum(t>=5 for t in lengths)))
        for a in range(0,120,5):
            exposure=m.exposure(seg,a,a+5)
            windows.append(dict(id=c['id'],start_s=a,end_s=a+5,
                observed_j=m.energy_at(c,a,a+5),**dict(zip(names,[5.,*exposure.tolist()]))))
    x=np.array([[r[n] for n in names] for r in windows])
    g=geometry(x)
    for r,n in zip(g['columns'],names):r['name']=n
    # Per-session intercepts diagnose whether occupancy identifies state effects
    # after allowing session background differences. This does not fit a model.
    nuisance=np.zeros((len(windows),len(cases)))
    for i in range(len(cases)):nuisance[i*24:(i+1)*24,i]=5
    occupied=x[:,1:];residual=occupied-nuisance@np.linalg.lstsq(nuisance,occupied,rcond=None)[0]
    session_geometry=geometry(residual)
    for r,n in zip(session_geometry['columns'],m.STATES):r['name']=n
    summary=dict(cases=len(cases),windows=len(windows),window_s=5,pooled_geometry=g,
        session_background_removed_geometry=session_geometry,
        interpretation='Design geometry only: no new coefficients, no independent-noise or accuracy assumption. Bounds multiply a unit L2 window-energy perturbation, not an empirical confidence interval.',
        individual_request_power_identified=False,device_commands=0,experiment_ready=False)
    return summary,rows,windows


def run(archive,output):
    output=Path(output)
    if output.exists():raise ValueError('fresh output required')
    cases,_,evidence=candidate.inputs(archive)
    summary,rows,windows=audit(cases);output.mkdir(parents=True)
    for n,v in [('summary.json',summary),('source_inventory.json',evidence)]:
        (output/n).write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
    for n,v in [('occupancy.csv',rows),('windows.csv',windows)]:
        with (output/n).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(v[0]));w.writeheader();w.writerows(v)
    return summary


def legacy_geometry(archive,output):
    """Reuse old raw lane records; regimen averages are not occupied-state W."""
    root=Path(archive)/'energy_ap_state_run_v5';freeze=p.read(root/'development_freeze.json')
    if p.digest(root/'development_freeze.json')!='35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54':raise ValueError('legacy freeze drift')
    rows=[];excluded=[];sources={}
    for i,pair in enumerate(('CC_DG','CG_DC','DC_DG')):
        folders=list(root.glob(f'{i:02d}_*'))
        if len(folders)!=1:raise ValueError('legacy folder ambiguity')
        folder=folders[0];art=folder/'artifacts'
        for key,file in [('manifest',art/'manifest.json'),('progress',art/'progress.jsonl'),('thermal',folder/'thermal.jsonl')]:
            h=p.digest(file)
            if h!=freeze['input_hashes'][pair][key]:raise ValueError('legacy raw drift')
            sources[str(file)]=h
        if p.read(art/'cleanup.json')['status']!='completed':raise ValueError('legacy incomplete')
        ev=[json.loads(s) for s in (art/'progress.jsonl').read_text(encoding='utf8').splitlines()]
        origin=[s['mono_ns'] for s in ev if s['kind']=='phase_start' and s['phase']=='load']
        if len(origin)!=1:raise ValueError('legacy origin')
        origin=origin[0]
        req=[s for s in ev if s['kind']=='lane_available' and s['phase']=='load']
        bounds={0.,600.}
        for q in req:
            if q['terminal_status']!='succeeded':raise ValueError('legacy request')
            bounds.update([(q['dispatch_ns']-origin)/1e9,(q['lane_available_ns']-origin)/1e9])
        edges=sorted(t for t in bounds if 0<=t<=600);segments=[]
        for a,b in zip(edges,edges[1:]):
            mid=origin+(a+b)/2*1e9
            keys=sorted(q['key'] for q in req if q['dispatch_ns']<=mid<q['lane_available_ns'])
            state='+'.join(keys) if keys else 'resident_idle'
            segments.append((a,b,state))
        for a in range(0,600,5):
            x=np.zeros(4);unsupported=0.
            for start,end,state in segments:
                dt=max(0.,min(a+5,end)-max(a,start))
                if state in m.STATES:x[m.STATES.index(state)]+=dt
                elif state!='resident_idle':unsupported+=dt
            if unsupported>1e-8:
                excluded.append(dict(pair=pair,start_s=a,end_s=a+5,unsupported_s=unsupported));continue
            rows.append(dict(pair=pair,start_s=a,end_s=a+5,**dict(zip(m.STATES,x.tolist()))))
    x=np.array([[5.,*[r[n] for n in m.STATES]] for r in rows]);g=geometry(x)
    for r,n in zip(g['columns'],('resident_intercept',)+m.STATES):r['name']=n
    summary=dict(included_5s_windows=len(rows),excluded_5s_windows=len(excluded),geometry=g,
        protocol_transfer_verified=False,new_coefficients=False,whole_window_energy_not_calculated=True,
        interpretation='Supported state occupancy only; excluded detection_GPU combinations retained in exclusion table. Old block mean W includes gaps and must not be used as instantaneous occupied-state W.')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    for n,v in [('summary.json',summary),('source_inventory.json',sources)]:
        (output/n).write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
    for n,v in [('windows.csv',rows),('excluded.csv',excluded)]:
        with (output/n).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(v[0]));w.writeheader();w.writerows(v)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--archive',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--legacy',action='store_true')
    a=parser.parse_args();print(json.dumps((legacy_geometry if a.legacy else run)(a.archive,a.output),indent=2))
