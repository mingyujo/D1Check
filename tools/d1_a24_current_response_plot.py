"""Offline diagnostic figures in API raw values; never labels them calibrated mA/J."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from d1_a24_laptop_validator import sha256


def plot(root,analysis,out):
    data=json.loads((analysis/'analysis.json').read_text());rows=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
    origin=rows[0]['mono_ns'];samples=[s for s in rows if s['kind']=='sensor_sample' and s['current_raw'] is not None]
    t=[((s['current_read_start_ns']+s['current_read_end_ns'])/2-origin)/1e9 for s in samples]
    v=[-s['current_raw'] for s in samples]
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'svg.fonttype':'none'})
    out.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(13,4.5));ax.plot(t,v,lw=.65,color='#243f64')
    for p in data['pulses']:
        if 'on_s' in p:ax.axvspan(p['on_s'],p['off_s'],alpha=.22,color='#ef8535' if p['resource']=='CPU' else '#298473');ax.text(p['on_s'],ax.get_ylim()[1]*.98,p['resource'],va='top',fontsize=8)
    ax.set(xlabel='앱 단조 시계의 경과시간 (초)',ylabel='방전 방향 전류 API 원값 · 단위 미검증',title='부하 시작·종료와 전류 API 반응 — 합성 부하 진단')
    fig.tight_layout();fig.savefig(out/'01_전체_전류_반응.png',dpi=150);fig.savefig(out/'01_전체_전류_반응.svg');plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,7.5))
    for ax,p in zip(axes.flat,data['pulses']):
        if 'on_s' not in p:ax.text(.5,.5,'미완료',transform=ax.transAxes);continue
        a=p['on_s'];b=p['off_s'];pairs=[(x-a,y) for x,y in zip(t,v) if a-10<=x<=b+30]
        ax.plot([x for x,y in pairs],[y for x,y in pairs],lw=.9,color='#243f64');ax.axvspan(0,b-a,color='#ef8535' if p['resource']=='CPU' else '#298473',alpha=.2)
        for key,color in [('rise_t10_s','#aa6d0a'),('rise_t50_s','#b13d52')]:
            value=p.get(key)
            if value is not None:ax.axvline(value,color=color,ls='--',lw=1,label=key+f'={value:.3f}s')
        ax.set_title(f"{p['pulse']+1}. {p['resource']} · {p['period_ms']}ms · "+('검증용' if p['split']=='HELD_OUT' else '개발용'),fontsize=10)
        ax.set_xlabel('부하 시작부터 시간 (초)');ax.set_ylabel('방전 방향 API 원값');ax.grid(alpha=.2)
        if p.get('rise_t50_s') is not None:ax.legend(fontsize=7)
    fig.suptitle('반복별 관측 반응: 실제 소비 변화와 센서·HAL·API 효과가 합쳐진 값',fontsize=13)
    fig.tight_layout();fig.savefig(out/'02_반복별_전류_반응.png',dpi=150);fig.savefig(out/'02_반복별_전류_반응.svg');plt.close(fig)
    def value(x):return '미검출' if x is None else f'{x:.3f}'
    body=''.join('<tr>'+''.join(f'<td>{x}</td>' for x in [p['pulse']+1,p['resource'],p['period_ms'],p['split'],value(p.get('rise_t10_s')),value(p.get('rise_t50_s')),value(p.get('fall_t50_s')),p['status']])+'</tr>' for p in data['pulses'])
    html=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 전류 반응 진단</title><style>body{{font-family:Malgun Gothic,sans-serif;max-width:1300px;margin:24px auto;padding:0 15px;color:#17283a}}img{{width:100%}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #ddd;padding:7px}}</style><h1>A24 전류 반응 진단</h1><p>별도 합성CPU·GPU 부하 / 순수 센서 지연·전류 단위·절대J 검증이 아닙니다. 시간 보정 적용0. 전체 {data['completed_pulses']}/6반복, 전류 조회{data['sensor_reads']}회, 부적격 조회{data['invalid_reads']}회.</p><table><tr><th>반복</th><th>부하</th><th>조회ms</th><th>자료구분</th><th>상승10%초</th><th>상승50%초</th><th>하강50%초</th><th>판정</th></tr>{body}</table><img src="01_전체_전류_반응.png"><img src="02_반복별_전류_반응.png"><p>개발·검증 반복은 한 앱 세션에 포함되며 독립 세션 반복이 아닙니다. 미검출을0초로 바꾸지 않았습니다.</p></html>'''
    (out/'index.html').write_text(html,encoding='utf-8')
    (out/'PLOT_PROVENANCE.json').write_text(json.dumps({'source_sha256':sha256(Path(__file__)),'events_sha256':sha256(root/'events.jsonl'),'analysis_sha256':sha256(analysis/'analysis.json'),'physical_J_validated':False},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('analysis',type=Path);p.add_argument('output',type=Path);a=p.parse_args();plot(a.root,a.analysis,a.output)
