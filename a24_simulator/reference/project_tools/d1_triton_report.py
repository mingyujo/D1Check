"""Offline report from saved CSV/ledgers. Does not execute an environment."""
import argparse
import copy
import html
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from tools import d1_triton_study as s
from tools import d1_external_rules_report as old

LABELS = dict(old.LABELS)
LABELS.update(dict(zip(s.rules.CONFIGS, ['Triton 제한 해제', 'Triton 1건·동일 배분',
    'Triton 2건·동일 배분', 'Triton 1건·분류 우대', 'Triton 2건·분류 우대'])))
NEW = list(s.rules.CONFIGS)
FOCUS = ['SHARED_EFT', 'ENERGY_AP_REQUEST_V1', s.rules.prior.joint.LABEL, s.rules.prior.BAND] + NEW
FIELDS = ('energy_j', 'peak_ap_c', 'thermal_degree_seconds', 'urgent_p95_ms', 'normal_mean_ms', 'overlap_s')


def paired(rows):
    lookup = {(x['seed'], x['family'], x['context'], x['policy']): x for x in rows}
    pairs = []
    for row in rows:
        for name in (s.rules.OFF, 'SHARED_EFT'):
            ref = lookup[row['seed'], row['family'], row['context'], name]
            pair = {k: row[k] for k in ('seed', 'family', 'context', 'policy')}
            pair.update(reference=name, planned=row['planned'], policy_completed=row['completed'],
                reference_completed=ref['completed'], policy_deadline_met=row['deadline_met'],
                reference_deadline_met=ref['deadline_met'],
                both_full_work=row['completed'] == row['planned'] and ref['completed'] == ref['planned'],
                both_full_timely=row['deadline_met'] == row['planned'] and ref['deadline_met'] == ref['planned'])
            for key in FIELDS:
                pair['delta_' + key] = row[key] - ref[key] if row[key] is not None and ref[key] is not None else None
            values = [pair['delta_' + key] for key in FIELDS[:3]]
            pair['joint_nonworsening'] = pair['both_full_timely'] and all(v is not None and v <= 1e-9 for v in values)
            pair['joint_strict'] = pair['joint_nonworsening'] and any(v < -1e-9 for v in values)
            pair['interpretation'] = ('service_loss' if not pair['both_full_timely'] else
                'joint_reduction' if pair['joint_strict'] else
                'model_equal' if all(v is not None and abs(v) <= 1e-9 for v in values) else 'tradeoff_or_increase')
            pairs.append(pair)
    return pairs


def schedule(item):
    keys = ('id', 'status', 'backend', 'dispatch_ns', 'lane_available_ns', 'response_ns')
    return [tuple(x.get(k) for k in keys) for x in item['ledger']]


def audit_and_representatives(rows):
    spec = s.check()
    inputs = s.read(s.BUNDLE / 'inputs.json')
    tickets = {(w['seed'], w['family']): w['tickets'] for w in inputs['workloads']}
    frozen, _ = s.rules.prior.p.inputs(s.rules.prior.p.BUNDLE)
    new_items = [s.read_item(path) for path in sorted((s.LOCAL / 'items').glob('*.gz'))]
    if len(new_items) != 240:
        raise ValueError('expected all 240 new records')
    representatives = {}
    new_lookup = {}
    count = 0
    max_j = max_ap = 0.
    for item in new_items:
        row = item['row']
        key = (row['seed'], row['family'], row['context'], row['policy'])
        if key in new_lookup:
            raise ValueError('duplicate condition')
        new_lookup[key] = item
        s.prior.audit(item, tickets[row['seed'], row['family']])
        count += len(item['ledger'])
        costs = s.rules.prior.p.model.costs(item['segments'], inputs['initial'], item['ap_times_s'],
                                          frozen, float(item['ap_end_s']))
        max_j = max(max_j, abs(costs['whole_120s_j'] - row['energy_j']))
        max_ap = max(max_ap, max(abs(a - b) for a, b in zip(costs['ap_path'], item['ap_path'])))
        complete = all(x['status'] == 'succeeded' for x in item['ledger'])
        if (row['peak_ap_c'] is not None) != complete:
            raise ValueError('incomplete AP treated as full-work peak')
        releases = [x for x in item['rate_events'] if x['event'] == 'release']
        ledger = {x['id']: x for x in item['ledger']}
        if any(x['at_ns'] < ledger[x['request_id']]['lane_available_ns'] for x in releases):
            raise ValueError('early release')
        if len(releases) != row['completed']:
            raise ValueError('completion accounting')
        allocations = [x for x in item['rate_events'] if x['event'] == 'allocate']
        if s.rules.CONFIGS[row['policy']]['capacity'] == 1 and any(x['occupied'] > 1 for x in allocations):
            raise ValueError('capacity violation')
        if row['seed'] == spec['representative']['seed'] and row['context'] == 'mean' and row['family'] in ('queue', 'sustained'):
            if row['policy'] in (NEW[0], NEW[1], NEW[3]):
                representatives[row['family'] + '|' + row['policy']] = item
    identical = 0
    for key, item in new_lookup.items():
        if key[-1] in (NEW[2], NEW[4]):
            if schedule(item) != schedule(new_lookup[(*key[:3], NEW[0])]):
                raise ValueError('cap2 unexpectedly changed the identical lower scheduling')
            identical += 1
    # Reuse old rows only with exact saved source/model/input contract and ledger audit.
    old_lookup = {(x['seed'], x['family'], x['context'], x['policy']): x
                  for x in rows if x['origin'] == 'reused_external_rules_01'}
    old_count = old_rows = 0
    old_folder = s.prior.LOCAL / 'comparison/items'
    for path in sorted(old_folder.glob('*.gz')):
        item = s.read_item(path)
        row = item['row']
        if row['scope'] != 'resource':
            continue
        key = (row['seed'], row['family'], row['context'], row['policy'])
        if key not in old_lookup or any(old_lookup[key][k] != v for k, v in row.items()):
            raise ValueError('old row differs from raw')
        s.prior.audit(item, tickets[row['seed'], row['family']])
        old_count += len(item['ledger'])
        old_rows += 1
        if row['seed'] == spec['representative']['seed'] and row['context'] == 'mean' and row['family'] in ('queue', 'sustained'):
            if row['policy'] in ('SHARED_EFT', 'ENERGY_AP_REQUEST_V1', s.rules.prior.BAND):
                representatives[row['family'] + '|' + row['policy']] = item
    if old_rows != 384 or len(rows) != 624 or count + old_count != sum(x['planned'] for x in rows):
        raise ValueError('full denominator/reuse incomplete')
    if max_j > 1e-10 or max_ap > 1e-10:
        raise ValueError('saved cost mismatch')
    if len(representatives) != 12:
        raise ValueError('preregistered representative set incomplete')
    return representatives, dict(status='PASSED', utc=s.stamp(), head=spec['head'], dirty=True,
        new_rows=240, reused_rows=384, new_requests=count, reused_requests=old_count,
        audited_requests=count + old_count, cost_recalculations=240, max_J_error_j=max_j,
        max_AP_error_c=max_ap, cap2_same_schedule_as_off_cases=identical,
        old_sources=len(spec['old_sources']), user_files=len(s.read(s.LOCAL / 'preserved_user_files.json')),
        source_sha256=s.digest(Path(__file__)), environment_runs=0, device_commands=0)


def save(fig, out, name):
    old.save(fig, out, name)
    # SVG path lines contain renderer-added trailing spaces. Keep geometry but
    # export deterministic LF without whitespace-check noise in this new bundle.
    path = out / (name + '.svg')
    path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf8').splitlines()) + '\n',
                    encoding='utf8', newline='\n')


def figures(out, rows, groups, pairs, reps):
    old.setup_plots()
    plt.rcParams['svg.hashsalt'] = 'd1-external-rules-12'
    fig, ax = plt.subplots(figsize=(13, 5.3))
    ax.axis('off')
    data = [['Triton 제한 해제', '모델별 FIFO', '분류GPU·탐지CPU', '인스턴스가 비면 시작'],
            ['Triton 자원 제한', '완료횟수 × 배분값의 최솟값', '동일한 고정 배정', 'token1/2, lane 반환까지 점유'],
            ['강한 예상 응답 우선', '기존 공유 큐 우선순위', '예상 응답시간 비교', '기존 규칙'],
            ['우리 에너지·AP 규칙', '기존 큐 및 기한 예측', '예상 J/AP로 선택', '조건부 대기'],
            ['Band 요청 적용', '최소 예상 지연이 가장 큰 요청', '예상 완료계획 비교', '바쁜 최선 worker이면 yield'],
            ['StarPU DMDA', '시간·전송·에너지 비용', 'worker별 큐', '입력 대응 미확정 → 이번 보류']]
    tab = ax.table(cellText=data, colLabels=['규칙', '실행 선택', '자원 배정', '대기와 재판단'], loc='center',
                   colWidths=[.18, .31, .20, .31], cellLoc='left')
    tab.auto_set_font_size(False)
    tab.set_fontsize(10)
    tab.scale(1, 2.5)
    ax.set_title('공개 규칙과 우리 규칙이 판단하는 차이', fontsize=17, pad=25)
    fig.text(.02, .03, '외부 제품 전체 실행이 아닌 요청 단위 적용 · 원 기본 priority1 / 실험 분류1·탐지2', fontsize=10)
    save(fig, out, '01_판단규칙차이')

    fig, axes = plt.subplots(6, 1, figsize=(13, 12))
    selections = [('queue', NEW[0]), ('queue', NEW[1]), ('queue', 'SHARED_EFT'),
                  ('sustained', NEW[0]), ('sustained', NEW[3]), ('sustained', 'SHARED_EFT')]
    for ax, (family, policy) in zip(axes, selections):
        item = reps[family + '|' + policy]
        for row in item['ledger']:
            if 'dispatch_ns' in row:
                a = row['dispatch_ns'] / 1e9
                b = row.get('lane_available_ns', 120e9) / 1e9
                y = 1 if row['backend'] == 'GPU' else 0
                ax.broken_barh([(a, b - a)], (y - .3, .6),
                              facecolors='#2487a3' if row['task'] == 'classification' else '#ad8054')
        ax.set_yticks([0, 1], ['CPU', 'GPU'])
        ax.set_xlim(35, 58 if family == 'queue' else 120)
        ax.set_title(old.FAMILIES[family] + ' · ' + LABELS[policy], loc='left', fontsize=11)
        ax.grid(axis='x', alpha=.2)
    axes[-1].set_xlabel('공통 시각 (초)')
    fig.suptitle('같은 대표 요청의 실행 시간표', fontsize=17)
    fig.tight_layout(rect=[0, 0, 1, .97])
    save(fig, out, '02_같은요청시간표')

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for col, family in enumerate(('low', 'sustained')):
        gs = [next(x for x in groups if x['family'] == family and x['policy'] == policy) for policy in FOCUS]
        for ax, key, title in [(axes[0, col], 'urgent_p95_ms', '긴급 응답 P95 평균 (ms)'),
                               (axes[1, col], 'timely_rate', '전체 예정 요청의 기한 충족률 (%)')]:
            vals = [x[key] * (100 if key == 'timely_rate' else 1) for x in gs]
            ax.barh(range(len(gs)), vals, color=['#507481' if x['policy'] not in NEW else '#ba763b' for x in gs])
            ax.set_yticks(range(len(gs)), [LABELS[x['policy']] for x in gs], fontsize=9)
            ax.invert_yaxis()
            ax.set_title(old.FAMILIES[family] + ' · ' + title)
            if key == 'timely_rate':
                ax.set_xlim(0, 105)
                for i, x in enumerate(gs):
                    ax.text(2, i, f"완료 {x['completed']}/{x['planned']}", fontsize=8, va='center')
    fig.suptitle('응답과 전체 완료 요구를 먼저 확인', fontsize=17)
    fig.tight_layout(rect=[0, 0, 1, .96])
    save(fig, out, '03_응답과완료')

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    gs = [next(x for x in groups if x['family'] == 'sustained' and x['policy'] == policy) for policy in FOCUS]
    for ax, key, title in [(axes[0], 'energy_j', '공통120초 기기 전체 에너지 (J)'),
                           (axes[1], 'peak_ap_c', '완전 작업의 AP 최고값 (°C)')]:
        for i, x in enumerate(gs):
            value = x[key]
            if value is None:
                ax.text(30, i, f"계산 불가: 전량 완료 {x['full_work_cases']}/12조건", va='center', fontsize=9)
            else:
                bar = ax.barh(i, value, color='#2487a3' if x['completed'] == x['planned'] else '#dca254')
                if x['completed'] < x['planned']:
                    bar[0].set_hatch('//')
                    ax.text(141, i, f"부분작업 {x['completed']}/{x['planned']}", va='center', fontsize=8)
        ax.set_yticks(range(len(gs)), [LABELS[x['policy']] for x in gs], fontsize=9)
        ax.invert_yaxis()
        ax.set_title(title)
        ax.set_xlim((140, 190) if key == 'energy_j' else (30, 33))
    fig.suptitle('지속 부하: 에너지와 온도 · 미완료를 함께 표시', fontsize=17)
    fig.tight_layout(rect=[0, 0, 1, .95])
    save(fig, out, '04_에너지와온도')

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for ax, family in zip(axes, ('queue', 'sustained')):
        for policy in (NEW[0], NEW[1], NEW[3], 'SHARED_EFT', 'ENERGY_AP_REQUEST_V1'):
            item = reps[family + '|' + policy]
            suffix = ' · 부분 경로' if item['ap_end_s'] != 180 else ''
            ax.plot(item['ap_times_s'], item['ap_path'], label=LABELS[policy] + suffix,
                    linestyle='--' if item['ap_end_s'] != 180 else '-')
        ax.set_title(old.FAMILIES[family] + ' · 사전 선정 대표')
        ax.set_xlabel('공통 시각 (초)')
        ax.set_ylabel('모형 AP (°C)')
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.suptitle('같은 시작 상태의 AP 온도 경로', fontsize=17)
    fig.tight_layout(rect=[0, 0, 1, .95])
    save(fig, out, '05_같은시작온도경로')

    fig, ax = plt.subplots(figsize=(14, 4.5))
    conditions = sorted({(x['family'], x['seed'], x['context']) for x in rows},
                        key=lambda x: (list(old.FAMILIES).index(x[0]), x[1], ['mean', 'short_context', 'long_context'].index(x[2])))
    lookup = {(x['policy'], x['family'], x['seed'], x['context']): x for x in pairs if x['reference'] == NEW[0]}
    codes = {'model_equal': 0, 'joint_reduction': 1, 'tradeoff_or_increase': 2, 'service_loss': 3}
    data = [[codes[lookup[(policy, *condition)]['interpretation']] for condition in conditions] for policy in NEW]
    from matplotlib.colors import ListedColormap, BoundaryNorm
    ax.imshow(data, aspect='auto', cmap=ListedColormap(['#c6d1d8', '#328354', '#deaa48', '#ca6663']),
              norm=BoundaryNorm([-.5, .5, 1.5, 2.5, 3.5], 4))
    ax.set_yticks(range(5), [LABELS[x] for x in NEW])
    ax.set_xticks([5.5, 17.5, 29.5, 41.5], [old.FAMILIES[x] for x in old.FAMILIES])
    for x in (11.5, 23.5, 35.5):
        ax.axvline(x, color='white', linewidth=2)
    ax.set_title('48조건 지도 · 같은 하위 배정의 제한 해제 대비', fontsize=16, pad=18)
    fig.text(.12, .03, '회색=동률   초록=기한·전량 유지한 J/AP 공동감소   노랑=상충/증가   빨강=기한 또는 전량 미충족', fontsize=10)
    fig.tight_layout(rect=[0, .08, 1, 1])
    save(fig, out, '06_전체조건지도')


def dashboard(out, rows, groups, pairs):
    payload = json.dumps(dict(rows=rows, groups=groups, pairs=pairs, labels=LABELS, families=old.FAMILIES),
                         ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>D1Check 공개 규칙 열·에너지 비교</title>
<style>body{font:15px "Malgun Gothic",sans-serif;margin:28px;background:#f5f7fa;color:#243345}h1{font-size:25px}
.note{padding:16px;background:#fff3d4;border-radius:8px}select{padding:8px;margin:10px 12px 10px 0}table{border-collapse:collapse;background:white;width:100%;font-size:12px}th,td{border:1px solid #dce2e8;padding:7px;text-align:right}td:first-child,th:first-child{text-align:left}th{background:#e9eef3;position:sticky;top:0}img{max-width:100%;background:white;margin-top:20px}.scroll{max-height:600px;overflow:auto}.bad{background:#fff1ef}a{color:#126577}button{padding:8px}</style>
<h1>공개 규칙의 열·에너지 효과 비교</h1><p>동일 A24 모형 · 48조건 · Triton 5설정 신규240행 + 완료 정책 재사용384행</p>
<div class="note">Triton whole-request 제한적 재현 B. StarPU는 입력 대응 미확정으로 보류.<br>
예정 전량·기한을 먼저 확인합니다. 미완료의 J는 부분 작업 비용이며 AP180은 계산 불가입니다.<br>
기기 실행0 · 새 독립 실측0 · 이미 공개된 trace 재사용 · 결과후 튜닝0 · AP 안전 한도 미지원.</div>
<p><a href="README.md">보고서</a> · <a href="mapping.md">사전 대응</a> · <a href="sources.json">고정 출처</a> · <a href="results.csv">전체 CSV</a> · <a href="paired_differences.csv">같은 조건 차이 CSV</a></p>
<label>부하 <select id="family"></select></label><label>정책 <select id="policy"></select></label>
<label>차이 기준 <select id="reference"></select></label><p id="count"></p>
<h2>정책별 요약</h2><div class="scroll"><table><thead><tr><th>규칙</th><th>부하</th><th>전기한 조건</th><th>완료/예정</th><th>기한 충족 %</th><th>긴급P95 평균 ms</th><th>J120 평균</th><th>AP최고 평균 °C</th></tr></thead><tbody id="groups"></tbody></table></div>
<h2>전체 조건의 원형 결과</h2>
<div class="scroll"><table><thead><tr><th>규칙</th><th>부하</th><th>seed/문맥</th><th>완료/예정</th><th>기한/예정</th><th>긴급P95 ms</th><th>일반평균 ms</th><th>J120</th><th>AP최고 °C</th><th>AP면적 °C·s</th><th>차이 J</th><th>차이 AP</th><th>병행 s</th><th>근거</th></tr></thead><tbody id="rows"></tbody></table></div>
<div id="figures"></div><script>const D=PAYLOAD;
const family=document.querySelector('#family'),policy=document.querySelector('#policy'),reference=document.querySelector('#reference');
function option(el,value,label){let o=document.createElement('option');o.value=value;o.textContent=label;el.append(o)}
option(family,'all','전체');for(let [k,v] of Object.entries(D.families))option(family,k,v);family.value='sustained';
option(policy,'all','전체');for(let k of [...new Set(D.rows.map(x=>x.policy))])option(policy,k,D.labels[k]);
for(let k of [...new Set(D.pairs.map(x=>x.reference))])option(reference,k,D.labels[k]);
const fmt=x=>x==null?'계산 불가':Number(x).toFixed(3);
function render(){let rs=D.rows.filter(x=>(family.value==='all'||x.family===family.value)&&(policy.value==='all'||x.policy===policy.value));
let ps=D.pairs.filter(x=>x.reference===reference.value);let lookup=new Map(ps.map(x=>[[x.seed,x.family,x.context,x.policy].join('|'),x]));
document.querySelector('#count').textContent=`표시 ${rs.length}행 · 완료 ${rs.reduce((a,x)=>a+x.completed,0)}/${rs.reduce((a,x)=>a+x.planned,0)} · 신규/재사용을 근거 열에 표시`;
let gs=D.groups.filter(x=>(family.value==='all'||x.family===family.value)&&(policy.value==='all'||x.policy===policy.value));let gt=document.querySelector('#groups');gt.replaceChildren();
for(let x of gs){let tr=document.createElement('tr');if(x.full_timely_cases<x.cases)tr.className='bad';for(let v of [D.labels[x.policy],D.families[x.family],x.full_timely_cases+'/'+x.cases,x.completed+'/'+x.planned,fmt(100*x.timely_rate),fmt(x.urgent_p95_ms),fmt(x.energy_j)+(x.completed<x.planned?' (부분)':''),fmt(x.peak_ap_c)]){let td=document.createElement('td');td.textContent=v;tr.append(td)}gt.append(tr)}
let tbody=document.querySelector('#rows');tbody.replaceChildren();for(let x of rs){let p=lookup.get([x.seed,x.family,x.context,x.policy].join('|'));let tr=document.createElement('tr');if(x.deadline_met<x.planned)tr.className='bad';
let vals=[D.labels[x.policy],D.families[x.family],x.seed+'/'+x.context,x.completed+'/'+x.planned,x.deadline_met+'/'+x.planned,fmt(x.urgent_p95_ms),fmt(x.normal_mean_ms),fmt(x.energy_j)+(x.completed<x.planned?' (부분)':''),fmt(x.peak_ap_c),fmt(x.thermal_degree_seconds),fmt(p.delta_energy_j),fmt(p.delta_peak_ap_c),fmt(x.overlap_s),x.origin==='new_triton'?'신규':'기존 완료'];
for(let v of vals){let td=document.createElement('td');td.textContent=v;tr.append(td)}tbody.append(tr)}}
for(let el of [family,policy,reference])el.addEventListener('change',render);render();
for(let name of ['01_판단규칙차이','02_같은요청시간표','03_응답과완료','04_에너지와온도','05_같은시작온도경로','06_전체조건지도']){let img=document.createElement('img');img.src=name+'.png';img.alt=name;document.querySelector('#figures').append(img)}
</script></html>'''.replace('PAYLOAD', payload)
    (out / 'index.html').write_text(page, encoding='utf8')


def run(out=None, shared=False):
    out = Path(out or s.BUNDLE)
    out.mkdir(parents=True, exist_ok=True)
    if out.resolve() != s.BUNDLE.resolve():
        import shutil
        for name in ('README.md', 'mapping.md', 'sources.json', 'contract.json', 'inputs.json',
                     'NOTICE.md', 'TRITON_LICENSE.txt', 'tests_verification.json',
                     'integrity_verification.json', 'completion.json', 'dashboard_verification.json',
                     'shared_reproduction_verification.json'):
            source = s.BUNDLE / name
            if source.exists():
                shutil.copyfile(source, out / name)
    if shared:
        rows = old.typed_rows(s.BUNDLE / 'results.csv')
        reps = s.read(s.BUNDLE / 'representatives.json')
    else:
        rows = old.typed_rows(s.LOCAL / 'new_results.csv')
        reused = old.typed_rows(s.OLD / 'results.csv')
        for row in reused:
            if row['scope'] == 'resource':
                row['origin'] = 'reused_external_rules_01'
                rows.append(row)
        reps, integrity = audit_and_representatives(rows)
        s.write(out / 'integrity_verification.json', integrity)
    if len(rows) != 624:
        raise ValueError('registered row count')
    groups = old.group_summary(rows)
    pairs = paired(rows)
    differences = []
    for family in ('queue', 'sustained'):
        ref = reps[family + '|' + NEW[0]]
        for policy in (NEW[1], NEW[3], 'SHARED_EFT', 'ENERGY_AP_REQUEST_V1', s.rules.prior.BAND):
            target = reps[family + '|' + policy]
            for a, b in zip(ref['ledger'], target['ledger']):
                if (a.get('backend'), a.get('dispatch_ns')) != (b.get('backend'), b.get('dispatch_ns')):
                    differences.append(dict(family=family, policy=policy, request_id=a['id'], task=a['task'],
                        reference_backend=a.get('backend'), policy_backend=b.get('backend'),
                        reference_start_s=a.get('dispatch_ns', 0) / 1e9 if 'dispatch_ns' in a else None,
                        policy_start_s=b.get('dispatch_ns', 0) / 1e9 if 'dispatch_ns' in b else None,
                        reference_response_ms=a.get('response_ns', 0) / 1e6 if 'response_ns' in a else None,
                        policy_response_ms=b.get('response_ns', 0) / 1e6 if 'response_ns' in b else None))
    s.csv_write(out / 'results.csv', rows)
    s.csv_write(out / 'policy_summary.csv', groups)
    s.csv_write(out / 'paired_differences.csv', pairs)
    s.csv_write(out / 'representative_differences.csv', differences)
    compact = {key: {name: item[name] for name in
        ('row', 'ledger', 'segments', 'ap_times_s', 'ap_path', 'ap_end_s', 'reference_ap_c')}
        for key, item in reps.items()}
    s.write(out / 'representatives.json', compact)
    summary = dict(rows=624, new_rows=240, reused_rows=384, conditions=48,
        total_logical_planned_requests=sum(x['planned'] for x in rows),
        new_planned_requests=sum(x['planned'] for x in rows if x['origin'] == 'new_triton'),
        source_level='B', tuning=0, device_commands=0, experiment_ready=False,
        groups=groups, joint_cases=[dict(policy=policy, reference=reference,
            full_timely_pairs=sum(x['both_full_timely'] for x in pairs if x['policy'] == policy and x['reference'] == reference),
            strict_joint_pairs=sum(x['joint_strict'] for x in pairs if x['policy'] == policy and x['reference'] == reference))
            for policy in NEW for reference in (NEW[0], 'SHARED_EFT')])
    s.write(out / 'summary.json', summary)
    figures(out, rows, groups, pairs, reps)
    dashboard(out, rows, groups, pairs)
    s.write(out / 'report_verification.json', dict(utc=s.stamp(), environment_runs=0,
        report_sha256=s.digest(Path(__file__)), shared=shared, rows=624,
        png={x.name: s.digest(x) for x in sorted(out.glob('*.png'))}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    parser.add_argument('--shared', action='store_true')
    args = parser.parse_args()
    run(args.output, args.shared)
