"""Read-only aggregation of recorded PC timing results; no new simulations."""
import argparse
import csv
import gzip
import html
import json
from pathlib import Path
import statistics
from tools import d1_detector_gpu_reference as r

ROOT = r.b.ROOT


def source_bytes(path):
    path = Path(path)
    return path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes())


def load(path):
    return json.loads(source_bytes(path).decode('utf-8-sig'))


def verify(root):
    import hashlib
    for folder in ('run_v1', 'reference_v1'):
        registration = load(root/folder/'registered_before_run.json')
        for relative, expected in registration['hashes'].items():
            data = source_bytes(r.b.f.x.p.ROOT/relative)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('registered source/result mismatch: '+relative)
    if r.b.f.x.p.digest(r.b.f.x.p.BUNDLE/'model.json') != r.b.f.x.p.MODEL_SHA:
        raise ValueError('frozen model changed')
    if r.b.f.x.p.digest(r.b.f.x.p.BUNDLE/'initial_inputs.json') != r.b.f.x.p.INITIAL_SHA:
        raise ValueError('frozen initial inputs changed')


def aggregate(records):
    groups = {}
    for record in records:
        meta = record['meta']
        key = meta['envelope'], meta['interference'], meta['policy']
        if meta['energy_j'] is not None or meta['ap_peak_c'] is not None:
            raise ValueError('unidentified current J/AP must remain null')
        if meta['planned'] != 48 or len(record['ledger']) != 48:
            raise ValueError('full request denominator changed')
        if meta['deadline_met'] != sum('response_ns' in q and q['response_ns'] <= q['deadline_offset_ns'] for q in record['ledger']):
            raise ValueError('deadline ledger mismatch')
        groups.setdefault(key, []).append(meta)
    rows = []
    for (envelope, factor, policy), metas in sorted(groups.items()):
        rows.append(dict(envelope=envelope, interference=factor, policy=policy,
            seed_cases=len(metas), planned=sum(m['planned'] for m in metas),
            completed=sum(m['completed'] for m in metas), deadline_met=sum(m['deadline_met'] for m in metas),
            mean_urgent_p95_ms=statistics.mean(m['urgent_p95_ms'] for m in metas),
            mean_normal_mean_ms=statistics.mean(m['normal_mean_ms'] for m in metas),
            unmeasured_concurrency_s=(sum(m['unmeasured_concurrency_s'] for m in metas)
                if all('unmeasured_concurrency_s' in m for m in metas) else None),
            energy_j=None, ap_peak_c=None, current_profile_supported=False))
    return rows


def render(root, rows, records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    cases = [z for z in records if z['meta']['seed']==623001 and
        z['meta']['envelope']=='g0.45_c0.75_b4' and z['meta']['interference']==1.]
    fig, axes = plt.subplots(4, 1, figsize=(12, 7), sharex=True)
    order = ['CPU_URGENT','LEGACY_STATIC_CG_DC','LEGACY_STATIC_CC_DG','LEGACY_FOUR_CELL_EFT']
    colors={'classification':'#3977ad','detection':'#d58626'}
    for ax, name in zip(axes, order):
        rec=next(z for z in cases if z['meta']['policy']==name)
        for q in rec['ledger']:
            if q['status']!='succeeded':continue
            ax.broken_barh([(q['dispatch_ns']/1e9,(q['lane_available_ns']-q['dispatch_ns'])/1e9)],
                (0 if q['backend']=='CPU' else 1, .6),facecolors=colors[q['task']])
        for seg in rec.get('segments',[]):
            if not seg['historical_fixed_state_exists']:
                ax.axvspan(seg['start_s'],seg['end_s'],color='red',alpha=.13)
        ax.set_yticks([.3,1.3],['CPU','GPU']);ax.set_title(name,loc='left',fontsize=10);ax.grid(axis='x',alpha=.25)
    axes[-1].set_xlim(34,65);axes[-1].set_xlabel('PC time (s); dispatch to lane_available')
    axes[-1].legend(handles=[Patch(color=colors['classification'],label='classification'),
        Patch(color=colors['detection'],label='detection')],loc='upper right',fontsize=8)
    fig.suptitle('Historical CAL03 timing transfer only; red = unmeasured classification CPU + GPU\nNo new device data, current energy/AP remain unidentified',fontsize=11)
    fig.tight_layout();fig.savefig(root/'timing_reference.png',dpi=135);fig.savefig(root/'timing_reference.svg');plt.close(fig)
    svg=root/'timing_reference.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    fields=list(rows[0]);headers=''.join('<th>'+html.escape(k)+'</th>' for k in fields)
    cells=''.join('<tr>'+''.join('<td>'+html.escape('계산 불가 / null' if z[k] is None else str(round(z[k],5) if type(z[k]) is float else z[k]))+'</td>' for k in fields)+'</tr>' for z in rows)
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>탐지 GPU 근거 재사용</title>
    <style>body{font:16px sans-serif;max-width:1250px;margin:30px auto;padding:0 20px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:6px}img{width:100%}.warning{padding:15px;background:#fff2cf}th{background:#eaf0f6}</style>
    <h1>탐지 GPU: 과거 시간 근거와 현재 비용 공백</h1>
    <p class="warning">현재 요청 모형의 탐지 GPU J/AP는 계산 불가입니다. 아래 일정은 과거 CAL03 시간 벡터의 PC 전이 탐색이며 새 실측·독립 예측 검증·정책 절감 결과가 아닙니다.</p>
    <p>48개 정적 기준 계산과 16개 기존 4-cell EFT 참고 계산. 1.0/1.5는 기존 간섭 가정이며 기기 감속 측정값이 아닙니다. 모든 예정 요청을 분모에 남겼습니다. EFT의 빨간 구간은 미측정 분류 CPU+GPU 병행입니다.</p>
    <p><a href="README.md">근거·완료 조건·재현</a> · <a href="timing_groups.csv">집계 CSV</a> · <a href="../method_followup_01/index.html">현재 3-cell 전체 요청 방법론 비교</a></p>
    <img src="timing_reference.png" alt="과거 시간 자료로 만든 PC 일정"><table><thead><tr>'''+headers+'</tr></thead><tbody>'+cells+'</tbody></table></html>'
    (root/'index.html').write_text(text,encoding='utf8')


def report(root):
    root=Path(root);verify(root)
    controls=load(root/'run_v1/timing_ledgers.json');reference=load(root/'reference_v1/timing_ledgers.json')
    records=controls+reference;rows=aggregate(records)
    for rec in reference:
        if r.occupancy(rec['ledger'])!=rec['segments']:
            raise ValueError('saved state mapping changed')
        seconds=sum(z['end_s']-z['start_s'] for z in rec['segments'])
        if abs(seconds-120)>1e-7:raise ValueError('common timing window changed')
    r.b.f.x.old.csv_write(root/'timing_groups.csv',rows);render(root,rows,records)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(ROOT));args=parser.parse_args()
    report(args.root)
