"""Algebraic equal-work J/heating-input relaxation of the frozen A24 plant.

Integrated input is NOT physical heat, AP peak, rectified AP area, ambient, or
an empirical limit. Arrival/deadline/packing feasibility is deliberately relaxed.
"""
import argparse
import gzip
import json
from pathlib import Path
from tools import d1_method_followup as f


def coefficients(frozen,initial,tickets,scenario):
    profile=f.x.p.profile(frozen,scenario)
    C=sum(profile['classification_CPU_urgent'])/1e9
    G=sum(profile['classification_GPU_urgent'])/1e9
    D=sum(profile['detection_CPU_normal'])/1e9
    w=frozen['energy_increment_w'];s=frozen['ap']['parameters']['ap_slope_at_30_c_per_s'];idle=s['resident_idle']
    uc,ug,ud,up=(s[k]-idle for k in ('classification_CPU','classification_GPU','detection_CPU','classification_GPU+detection_CPU'))
    nc=sum(q['task']=='classification' for q in tickets);nd=len(tickets)-nc
    for q in tickets:f.x.p.backends(q)
    return dict(nc=nc,nd=nd,class_cpu_s=C,class_gpu_s=G,det_cpu_s=D,
        base_j=120*initial['preload_power_w']+nd*D*w['detection_CPU']+nc*C*w['classification_CPU'],
        base_input_c=nd*D*ud+nc*C*uc,
        gpu_assignment_extra_j=G*w['classification_GPU']-C*w['classification_CPU'],
        gpu_assignment_extra_input_c=G*ug-C*uc,
        overlap_discount_w=w['classification_GPU']+w['detection_CPU']-w['classification_GPU+detection_CPU'],
        overlap_extra_input_c_per_s=up-ug-ud)


def bound(c,energy_cap_j):
    discount=c['overlap_discount_w'];added=c['overlap_extra_input_c_per_s']
    if discount<=0 or added<0:raise ValueError('relaxation branch not supported; do not infer a different device')
    options=[]
    for ng in range(c['nc']+1):
        overlap=max(0.,(c['base_j']+ng*c['gpu_assignment_extra_j']-energy_cap_j)/discount)
        maxoverlap=min(ng*c['class_gpu_s'],c['nd']*c['det_cpu_s'])
        if overlap>maxoverlap+1e-7:continue
        overlap=min(overlap,maxoverlap)
        drive=c['base_input_c']+ng*c['gpu_assignment_extra_input_c']+overlap*added
        options.append((drive,ng,overlap))
    if not options:return dict(minimum_integrated_input_c=None,status='infeasible_relaxation')
    value,ng,overlap=min(options)
    return dict(minimum_integrated_input_c=value,relaxed_gpu_jobs=ng,relaxed_overlap_s=overlap,
        status='relaxed_bound',arrival_deadline_packing_relaxed=True)


def evaluate(record,frozen,initial):
    meta=record['meta'];qs=f.tickets(record);c=coefficients(frozen,initial,qs,meta['scenario'])
    s=frozen['ap']['parameters']['ap_slope_at_30_c_per_s'];idle=s['resident_idle']
    drive=sum((seg['end_s']-seg['start_s'])*(s[seg['state']]-idle) for seg in record['segments'] if seg['state']!='idle')
    energy=meta['energy_j'];b=bound(c,energy)
    gap=drive-b['minimum_integrated_input_c'] if b['minimum_integrated_input_c'] is not None else None
    if gap is not None and gap < -1e-6:raise ValueError('actual drive violates its equal-work lower bound')
    factor=frozen['ap']['k']/frozen['ap']['beta']
    if frozen['ap']['g']!=0:raise ValueError('infinite signed-response identity requires registered g0')
    return dict(stage=meta['stage'],envelope=meta['envelope'],seed=meta['seed'],scenario=meta['scenario'],policy=meta['policy'],
        energy_j=energy,integrated_input_c=drive,**b,drive_gap_to_relaxation_c=gap,
        near_bound_numeric_1e_6_c=gap is not None and abs(gap)<=1e-6,
        temperature_difference_integral_factor_s=factor,
        interpretation='same initial state: full infinite signed AP difference = k/beta times integrated-input difference; not finite rectified area/peak or device heat')


def run(root):
    root=Path(root);frozen,case=f.x.p.inputs(f.x.p.BUNDLE);initial=case['initial'];rows=[]
    for folder in ('run_v1','beam_v1','beam_v2'):
        records=[json.loads(line) for line in gzip.decompress((root/folder/'records.jsonl.gz').read_bytes()).decode().splitlines()]
        for record in records:
            if record['meta']['policy']=='EFT_REFERENCE':rows.append(dict(study=folder,**evaluate(record,frozen,initial)))
    f.x.old.csv_write(root/'energy_heat_bounds.csv',rows)
    c=coefficients(frozen,initial,f.tickets(records[0]),'mean')
    f.x.p.write(root/'energy_heat_identity.json',dict(mean_coefficients=c,
        fully_overlapped_one_class_gpu_vs_cpu_delta_j=c['gpu_assignment_extra_j']-c['class_gpu_s']*c['overlap_discount_w'],
        fully_overlapped_one_class_gpu_vs_cpu_delta_input_c=c['gpu_assignment_extra_input_c']+c['class_gpu_s']*c['overlap_extra_input_c_per_s'],
        fully_overlapped_temperature_difference_integral_c_s=(c['gpu_assignment_extra_input_c']+c['class_gpu_s']*c['overlap_extra_input_c_per_s'])*frozen['ap']['k']/frozen['ap']['beta'],
        physical_heat=False,empirical_optimality=False,source_sha256=f.x.p.digest(Path(__file__)),device_commands=0))
    return rows


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(f.ROOT));args=ap.parse_args();run(args.root)
