"""PC-only diagnostic summary. Reuses frozen integration; never fits coefficients."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from d1_energy_thermal import integrate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    read = lambda f: json.loads(f.read_text(encoding='utf-8'))
    receipt = read(a.run / 'FINAL_RECEIPT.json')
    sessions = list(a.run.glob('00_*'))
    assert len(sessions) == 1
    s = sessions[0]
    v = read(s / 'validated.json')
    for key, path in [('progress', s/'artifacts/progress.jsonl'), ('thermal', s/'thermal.jsonl')]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == v['input_hashes'][key]
    events = [json.loads(x) for x in (s/'artifacts/progress.jsonl').read_text().splitlines()]
    thermal = [json.loads(x) for x in (s/'thermal.jsonl').read_text().splitlines()]
    start, end = v['common_start_ns'], v['common_end_ns']
    power = v['power_path']
    total = integrate(power, start, end, 1000)
    assert abs(total['covered_energy_j']-v['common_window']['covered_energy_j']) < 1e-8
    times = sorted({start, end, *[x['mono_ns'] for x in power if start < x['mono_ns'] < end]})
    energy = [( (t-start)/1e9, integrate(power,start,t,1000)['full_energy_j']) for t in times]
    ap = [((x['mono_ns']-start)/1e9,float(x['AP'])) for x in thermal if start <= x['mono_ns'] <= end and x.get('AP') is not None]
    rows = []
    for b in v['blocks']:
        rows.append(dict(block=b['name'],state=b['state'],calls=b['calls'],duration_s=b['power']['duration_s'],
                         energy_j=b['power']['full_energy_j'],mean_whole_device_w=b['power']['mean_power_w'],
                         ap_start_c=b['ap_start_c'],ap_peak_c=b['ap_peak_c'],ap_end_c=b['ap_end_c'],
                         joint_lane_s=b.get('joint_lane_occupancy_s',0)))
    commands = [read(f) for f in sorted((a.run/'host_commands').glob('*/client/result.json'))]
    stops = [x for x in commands if 'force-stop' in x.get('command',[])]
    assert all('test' in x.get('command',[]) and '-e' in x['command'] and x.get('returncode') == 1
               for x in commands if x['status']=='nonzero_exit')
    assert len(stops) == 2 and all(x['status']=='returned' and x.get('returncode')==0 for x in stops)
    lanes = [x for x in events if x.get('kind')=='lane_available' and x.get('phase')=='load']
    assert len(lanes) == v['work_calls'] and all(x['terminal_status']=='succeeded' for x in lanes)
    # Host invocation intervals, not hardware execution or lane occupancy.
    pair = [x for x in lanes if x.get('block')=='pair']
    overlap = sum(max(0,min(x['invocation_end_ns'],y['invocation_end_ns'])-max(x['invocation_start_ns'],y['invocation_start_ns']))/1e9
                  for x in pair for y in pair if x['key']=='classification_GPU' and y['key']=='detection_CPU')
    summary = dict(status=receipt['status'],condition=v['condition'],formal_confirmation=False,
                   experiment_ready=False,independent_sessions=1,elapsed_seconds=receipt['elapsed_seconds'],
                   work_calls=v['work_calls'],eligibility_calls=v['eligibility_calls'],warmup_calls=v['warmup_calls'],
                   explicit_inference=receipt['explicit_inference'],adb_commands=len(commands),
                   adb_timeouts=sum(x['status']=='timeout' for x in commands),
                   nonzero_exits=[dict(status=x['status'],returncode=x.get('returncode'),purpose='preexisting_path_absence_test')
                                  for x in commands if x['status']=='nonzero_exit'],
                   host_force_stop_count=len(stops),host_force_stop_roles=['prelaunch_install_cleanup','post_session_cleanup'],
                   common_window=total,start_ap_c=v['start_ap_c'],peak_ap_c=max(y for _,y in ap),
                   actual_joint_lane_s=v['actual_joint_lane_occupancy_s'],pair_host_invocation_overlap_s=overlap,
                   power_samples=sum(x.get('kind')=='power_sample' for x in events),ap_samples=len(thermal),
                   input_hashes=v['input_hashes'],source_receipt_sha256=hashlib.sha256((a.run/'FINAL_RECEIPT.json').read_bytes()).hexdigest(),
                   limits=['raw current=mA conditional; absolute accuracy uncertified','protocol transition diagnostic; no frozen-model refit or accuracy PASS',
                           'no observed disconnect; resilience not established','preparation and cooling excluded from common energy'])
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name, data, fields in [('blocks.csv',rows,list(rows[0])),
                              ('energy.csv',[dict(time_s=t,cumulative_energy_j=e) for t,e in energy],['time_s','cumulative_energy_j']),
                              ('ap.csv',[dict(time_s=t,ap_c=c) for t,c in ap],['time_s','ap_c'])]:
        with (a.output/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
    def points(data,top,low,high):
        return ' '.join(f'{70+t/total["duration_s"]*800:.2f},{top+150-(y-low)/(high-low)*150:.2f}' for t,y in data if y is not None)
    # Refuse a continuous curve across missing energy; missing is not zero.
    assert total['missing_s'] < 1e-6
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="530" viewBox="0 0 960 530">
    <rect width="960" height="530" fill="white"/><g font-family="Malgun Gothic,sans-serif" font-size="15" fill="#172b4d">
    <text x="40" y="30">CG_DC 1세션 실측 — 프로토콜 전이 진단 (정식 확인 아님)</text>
    <text x="40" y="58">공통창 {total['duration_s']:.3f}초 · 준비/baseline/냉각 제외 · 재보정 없음</text>
    <text x="40" y="87">누적 기기 전체 에너지: {total['full_energy_j']:.3f} J (raw=mA 조건부, 절대 정확도 미인증)</text>
    <path d="M70 100V250H870" stroke="#aaa" fill="none"/>
    <polyline points="{points(energy,100,0,1000)}" stroke="#2474ac" stroke-width="2" fill="none"/>
    <text x="15" y="112">1000J</text><text x="35" y="250">0</text>
    <text x="40" y="291">AP 센서 mType=0 (°C): 시작 {v['start_ap_c']:.1f} · 최고 {summary['peak_ap_c']:.1f} · BAT/표면 온도 아님</text>
    <path d="M70 315V465H870" stroke="#aaa" fill="none"/>
    <polyline points="{points(ap,315,30,40)}" stroke="#cc6032" stroke-width="2" fill="none"/>
    <text x="25" y="328">40°C</text><text x="25" y="465">30°C</text>
    <text x="70" y="490">0</text><text x="455" y="490">300</text><text x="810" y="490">600초</text>
    <text x="40" y="518">센서 표본은 독립 반복이 아님 · 연결 소실 미관측 · 정책 절감/모형 예측 성능 미판정</text></g></svg>'''
    (a.output/'observed.svg').write_text(svg,encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('work_calls','explicit_inference','adb_commands','pair_host_invocation_overlap_s')},indent=2))


if __name__ == '__main__':
    main()
