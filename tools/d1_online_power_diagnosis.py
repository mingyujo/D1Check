"""Post-hoc accounting and sampling-phase diagnosis; no fitting or device calls."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from tools import d1_arrival_plan as p
from tools import d1_online_policy_model as m


def phase_counts(times, period, start=35., bins=8):
    if period <= 0 or bins < 1:
        raise ValueError('invalid phase grid')
    return np.histogram(((np.asarray(times)-start) % period)/period,
                        bins=np.linspace(0, 1, bins+1))[0].tolist()


def diagnose(root, output):
    root, output = Path(root), Path(output)
    dev=p.read(root/'development_cases.json'); conf=p.read(root/'confirmation_cases.json')
    frozen=p.read(root/'model_freeze.json')['model']
    inc=np.array([frozen['energy_increment_w'][k] for k in m.STATES])
    rows=[]; phases=[]; windows=[]; x=[]; y=[]
    for c in dev+conf:
        step=500 if c['study_phase']=='development' else 550
        samples=[s for s in c['power_samples'] if 35 <= (s['mono_ns']-c['origin_ns'])/1e9 <= 80]
        ts=[(s['mono_ns']-c['origin_ns'])/1e9 for s in samples]
        hist=phase_counts(ts,4*step/1000)
        phases.extend(dict(id=c['id'],phase_bin=i,count=n) for i,n in enumerate(hist))
        base=c['preload_power_w']; exposure=m.exposure(c['inputs']['segments'],35,120)
        predicted=85*base+float(exposure@inc)
        for a,b in [(-20,0),(0,10),(10,30),(30,35),(35,60),(60,90),(90,120),(120,150),(150,175)]:
            e=m.energy_at(c,a,b)
            windows.append(dict(id=c['id'],role=c['study_phase'],start_s=a,end_s=b,observed_j=e,mean_w=e/(b-a),
                                pre_background_w=base,excess_over_pre_j=e-base*(b-a)))
        q=[s for s in c['power_samples'] if 0 <= (s['mono_ns']-c['origin_ns'])/1e9 <=120]
        differences=np.diff([s['charge_counter_raw'] for s in q])
        steps=sorted(set(abs(int(d)) for d in differences if d))
        rows.append(dict(id=c['id'],role=c['study_phase'],period_s=4*step/1000,samples=len(ts),
            occupied_phase_bins=sum(n>0 for n in hist),pre_background_w=base,
            future_observed_j=m.energy_at(c,35,120),future_predicted_j=predicted,
            future_error_j=predicted-m.energy_at(c,35,120),
            post_idle_w=m.energy_at(c,90,120)/30,
            charge_counter_smallest_observed_step_raw=min(steps) if steps else None,
            nominal_smallest_charge_step_j=(min(steps)*.0036*np.mean([s['voltage_mV'] for s in q])/1000) if steps else None,
            **{k+'_seconds':float(v) for k,v in zip(m.STATES,exposure)}))
        if c['study_phase']=='development':
            for a in range(35,120,5):
                x.append(m.exposure(c['inputs']['segments'],a,a+5)); y.append(m.energy_at(c,a,a+5)-5*base)
    x=np.array(x); y=np.array(y)
    omissions=[]
    for i,c in enumerate(dev):
        keep=np.ones(len(x),dtype=bool); keep[17*i:17*(i+1)]=False
        rank=int(np.linalg.matrix_rank(x[keep]))
        omissions.append(dict(omitted=c['id'],rank=rank,identifiable=rank==4,
                              diagnostic_nnls_coefficients=m.nnls(x[keep],y[keep]).tolist()))
    metadata=dict(source_hashes={name:p.digest(root/name) for name in
        ('development_cases.json','confirmation_cases.json','model_freeze.json')},
        fit_original_reproduced=bool(np.allclose(m.nnls(x,y),inc,rtol=0,atol=1e-12)),
        singular_values=np.linalg.svd(x,compute_uv=False).tolist(),leave_session_out=omissions,
        interpretation='Post-hoc sensitivity only. Phase locking is observed; aliasing magnitude/causality unknown. Charge raw units uncalibrated; no independent reference energy.',
        candidate_created=False,device_commands=0,experiment_ready=False)
    output.mkdir(parents=True,exist_ok=False)
    for name, data in [('cases.csv',rows),('phase_counts.csv',phases),('windows.csv',windows)]:
        with (output/name).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    (output/'diagnosis.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,3,figsize=(12,8),constrained_layout=True)
    for ax,c in zip(axes.flat,rows):
        values=[r['count'] for r in phases if r['id']==c['id']]
        ax.bar(range(8),values);ax.set_title(c['id'].replace('_ONLINE_V1',''),fontsize=8)
        ax.set_xlabel('Phase bin of repeating four-request cycle');ax.set_ylabel('Samples, 35..80 s')
    fig.suptitle('Measured sample times: concentration is evidence; bias magnitude remains unknown')
    fig.savefig(output/'sample_phases.svg');fig.savefig(output/'sample_phases.png',dpi=110);plt.close(fig)
    svg=output/'sample_phases.svg';svg.write_text('\n'.join(s.rstrip() for s in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    return metadata


if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--root',required=True);q.add_argument('--output',required=True)
    a=q.parse_args();print(json.dumps(diagnose(a.root,a.output),indent=2))
