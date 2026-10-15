"""Offline rejected-prestart diagnosis, never a policy thermal-performance result."""
import argparse,csv,json
from pathlib import Path
from d1_a24_laptop_validator import load_json


def export(job_path, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    plt.rcParams['font.family']=FontProperties(fname='C:/Windows/Fonts/malgun.ttf').get_name()
    plt.rcParams['axes.unicode_minus']=False
    job=load_json(job_path);root=Path(job['run_root']);summaries=[]
    for row in load_json(Path(job['plan']))['sessions']:
        outcome=root/(row['session_id']+'.outcome.json')
        if not outcome.exists() or load_json(outcome)['status']!='PRESTART_REJECT':continue
        raw=root/'raw'/row['session_id'];ready=load_json(raw/'ready.json')['ready_ns']
        gate=load_json(root/'bindings'/row['session_id']/'gate.json');samples=[]
        for line in (raw/'host_hal_partial.jsonl').read_text().splitlines():
            r=json.loads(line)
            if r['device_elapsed_before_ns']<ready:continue
            ap=[s['value_c'] for s in r['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
            if len(ap)==1:samples.append({'elapsed_after_ready_s':(r['device_elapsed_before_ns']-ready)/1e9,'reported_AP_c':ap[0]})
        reference=gate['Tref_c'];lo,hi=reference-.5,reference+.5
        summary={'session_id':row['session_id'],'arm':row['arm'],'status':'PRESTART_REJECT','reference_c':reference,
            'post_ready_AP_min_c':min(r['reported_AP_c'] for r in samples),'post_ready_AP_max_c':max(r['reported_AP_c'] for r in samples),
            'last_AP_c':samples[-1]['reported_AP_c'],'readouts_in_band':sum(lo<=r['reported_AP_c']<=hi for r in samples),
            'readout_count':len(samples),'START':0,'main_inference':0,'planned_unfinished':row['request_count'],'not_policy_performance':True}
        summaries.append(summary)
        with (directory/(row['arm']+'_prestart_AP.csv')).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
        fig,ax=plt.subplots(figsize=(12,4));ax.plot([r['elapsed_after_ready_s'] for r in samples],[r['reported_AP_c'] for r in samples],label='本요청 전 AP 읽기값'.replace('本','본'))
        ax.axhspan(lo,hi,color='#4a9b68',alpha=.15,label=f'공통 시작 범위 {lo:.1f}~{hi:.1f}℃')
        ax.set_xlabel('공통 준비 완료 뒤 대기 (초)');ax.set_ylabel('HAL AP 읽기값 (℃)');ax.set_title(row['arm']+' 시작 전 거절 진단 · 본요청0건');ax.legend();fig.tight_layout()
        name='07_'+row['arm']+'_시작전_온도대기';fig.savefig(directory/(name+'.png'),dpi=160);plt.close(fig)
        page=directory/'index.html'
        if page.exists():page.write_text(page.read_text(encoding='utf8')+f'<img src="{name}.png" alt="시작 전 온도 대기 진단">',encoding='utf8')
    (directory/'PRESTART_DIAGNOSTIC.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('directory',type=Path);a=p.parse_args();export(a.job,a.directory)
