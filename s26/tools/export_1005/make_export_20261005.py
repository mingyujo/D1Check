# -*- coding: utf-8 -*-
"""make_export_20261005.py — S26 minimal export for 조민규 §6 (S26_SCOPE_AND_INTERFACE_20261004.md §6, 4 bundles). READ-ONLY on results/.

Bundles (his §6 numbering):
  1 run manifest/receipt/validation  -> b1_runs.csv · b1_runs.json        (repo)
  2 sensor tables (raw samples)      -> git-out  sensors/<exp>__thermal.csv · sensors/<exp>__d1check.csv
                                        + repo b2_sensor_inventory.csv (sample counts·intervals·gaps·units) · b2_files_sha256.csv
  3 segment / request tables         -> b3_segments.csv · b3_transitions.csv · b3_attribution.csv (repo); request ledger = missing
  4 model / policy + raw inventory   -> b4_raw_inventory.csv (repo: relpath · bytes · sha256; files themselves stay outside Git)
  C2 electrical raw time series      -> git-out c2_sensors/<run>__d1check.csv (+ sha256 list in repo)
Scope: 10/2 · 10/3 26 experiments = full bundles 1–3; 10/4 · 10/5 runs = inventory only (bundle 4 list, no tables).
No logcat text, no model binary, no address/serial is written (device.serial and fingerprint are never copied; device_anon_id = S26-1).

★ Segment attribution rule (bundle 3, fixed BEFORE the table is produced — 회신 1004 §2-2 promise):
  lines = raw/logcat.txt lines of the RUNNER PID (the PID that printed tag D1GPU), timestamp = device local time (KST, +09:00) of the run date
  window of segment 0 = [first runner event wall_ms (run_metadata), segment 0 end] ; segment i > 0 = [transition i start, segment i end]
  (wall clock of mono boundaries via the nearest runner event's (mono_ns, wall_ms) pair)
  counts per window: GPU = "Replacing N out of N node(s) with delegate (LITERT_CL)" · NPU = "... with delegate (DispatchDelegate)" ·
                     ENN = "SetGenAiPerfConfigFromSoc" · failure = case-insensitive "failed to create" | "fallback" | "fall back" | "falling back" |
                     "failed to apply"
  verdict: expected-accelerator replacement >= 1 AND other-accelerator replacement == 0 AND failure == 0 -> "PASS (구간 고유 증거)" ;
           NPU segments additionally report ENN (not part of the verdict — as promised: 기대 줄 >= 1 · 다른 가속기 줄 0 · fallback 0) ;
           no replacement line in the window AND transition model_initialized is False -> "재사용 — 구간 고유 증거 없음 (판정 안 함)" ;
           otherwise "FAIL (<reason>)". Single-run (non-chain) experiments: one window = whole run, expected = run resource.
  Segment 0 evidence is never carried to later segments.

  py s26\\tools\\export_1005\\make_export_20261005.py --repo-out s26\\exports\\20261005 --git-out <folder outside Git>
"""
import argparse, csv, datetime, glob, hashlib, json, os, re, statistics, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT)
from d1sim.tools import extract_traces_v1 as xt  # noqa: E402  (read_runner — unchanged)

KST = datetime.timezone(datetime.timedelta(hours=9))
EXP_1002 = ['S26_GPUcm_smoke_1002', 'S26_M1_gpu_1002', 'S26_M2_npu_C1_1002', 'S26_M2_npu_C2_1002', 'S26_M2_npu_H1_1002', 'S26_M2_npu_H2_1002',
            'S26_M2r_gpu_C1_1002', 'S26_M2r_gpu_C2_1002', 'S26_M2r_gpu_H1_1002', 'S26_M2r_gpu_H2_1002', 'S26_N1300_npu_1002',
            'S26_capsmoke_npu_1002', 'S26_chainsmoke_1002']
EXP_1003 = ['S26_EffB1_01_cpu50_1003', 'S26_EffB1_02_cpu100_1003', 'S26_EffB1_03_gpu50_1003', 'S26_EffB1_04_gpu100_1003',
            'S26_EffB1_05_gpu100_1003', 'S26_EffB1_06_gpu50_1003', 'S26_EffB1_07_cpu100_1003', 'S26_EffB1_08_cpu50_1003',
            'S26_EffN600_npu_1003', 'S26_GPUpace_1003', 'S26_M1_gpu_r2_1003', 'S26_M1_npu_1003', 'S26_M1_npu_r2_1003']
INVENTORY_ONLY = ['S26_N50P_1004', 'S26_G50P_1004', 'S26_GI300_1004', 'S26_NI300_1004', 'S26_EffN420_npu_1004'] + \
                 [f'S26_EffB2_0{i}_{k}_1004' for i, k in ((1, 'gpu50'), (2, 'gpu100'), (3, 'cpu50'), (4, 'cpu100'), (5, 'cpu100'), (6, 'cpu50'), (7, 'gpu100'), (8, 'gpu50'))] + \
                 ['S26_N50P2_1005', 'S26_NI300r2_1005', 'S26_G50P2_1005']
C2_DIR = 'S26_C2_efficientnet_npu_0928'
META_KEYS = ['run_id', 'resource', 'npu_accelerator_requested', 'npu_timed_resource_label', 'engine', 'litert_version', 'model_id', 'model_sha256', 'precision', 'limit_mode', 'requested_duration_s',
             'actual_load_duration_ns', 'termination_reason', 'completed_inference_count', 'experiment_valid', 'invalid_reason', 'cpu_threads',
             'warmup_count', 'baseline_s', 'achieved_duty_cycle_percent', 'npu_dispatch_lib_sha256', 'npu_input_spec', 'npu_input_sha256',
             'npu_latency_boundary', 'npu_model_partition', 'gpu_delegate_profile', 'gpu_compatibility_policy_id', 'gpu_compatibility_list_enforced',
             'chain_mode', 'chain_id', 'chain_sha256', 'chain_model_prepare', 'chain_segment_count', 'chain_segments_completed', 'pilot_battery_pct',
             'pilot_plugged', 'pilot_safety_pass', 'energy_measurement']
PAT_RE = re.compile(r'([0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}|R3KL[0-9A-Z]{7}')
REPL = re.compile(r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(([A-Za-z_]+)\)')
FAIL_RE = re.compile(r'failed to create|fallback|fall back|falling back|failed to apply', re.I)
LOG_RE = re.compile(r'^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+(\S+)\s*:\s?(.*)$')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 24), b''):
            h.update(c)
    return h.hexdigest()


def one_run(exp):
    rr = [d for d in sorted(glob.glob(os.path.join(ROOT, 'results', exp, 'runs', '*'))) if os.path.isdir(d)]
    if len(rr) != 1:
        raise RuntimeError(f'{exp}: {len(rr)} run folders')
    return rr[0]


def _clean(v):
    s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else ('' if v is None else str(v))
    if PAT_RE.search(s):
        raise RuntimeError('address/serial pattern in exported value')
    return s


def runner_events(path):
    """run_metadata, mono/wall anchors, segment/transition details, per-segment latencies (inference events)."""
    R = xt.read_runner(path)
    anchors = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if '"event":"inference"' in line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e.get('mono_ns'), int) and isinstance(e.get('wall_ms'), (int, float)):
                anchors.append((int(e['mono_ns']), float(e['wall_ms']), e.get('event')))
    tr_full = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if '"chain_transition_end"' in line:
                tr_full.append(xt.detail(json.loads(line)))
    return R, anchors, tr_full


def wall_of(anchors, mono):
    best = min(anchors, key=lambda a: abs(a[0] - mono))
    return best[1] + (mono - best[0]) / 1e6


def nearest_rank(v, q):
    if not v:
        return None
    s = sorted(v)
    import math
    return s[max(0, math.ceil(q * len(s)) - 1)]


def logcat_lines(path, year):
    """(epoch_ms, pid, tag, msg) for every parseable logcat.txt line."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = LOG_RE.match(line.rstrip('\n'))
            if not m:
                continue
            mo, d, H, M, S, ms, pid, tid, lvl, tag, msg = m.groups()
            t = datetime.datetime(year, int(mo), int(d), int(H), int(M), int(S), int(ms) * 1000, tzinfo=KST)
            out.append((t.timestamp() * 1000.0, pid, tag, msg))
    return out


def attribution(exp, R, anchors, tr_full, logs):
    pids = {p for _, p, tag, _ in logs if tag == 'D1GPU'}
    lines = [(t, msg) for t, p, tag, msg in logs if p in pids]
    meta = R['meta']
    run_wall0 = next((w for m, w, ev in anchors if ev == 'run_metadata'), anchors[0][1])
    rows = []
    chain = meta.get('chain_mode') is True
    segs = R['segments']
    for i, s in enumerate(segs):
        if i == 0:
            a = run_wall0
        else:
            a = wall_of(anchors, R['transitions'][i - 1]['start_ns'])
        b = wall_of(anchors, s['end_ns'])
        win = [msg for t, msg in lines if a <= t <= b]
        cnt = dict(GPU=0, NPU=0, other=0, enn=0, failure=0)
        for msg in win:
            m = REPL.search(msg)
            if m:
                d = m.group(3)
                cnt['GPU' if d == 'LITERT_CL' else ('NPU' if d == 'DispatchDelegate' else 'other')] += 1
            if 'SetGenAiPerfConfigFromSoc' in msg:
                cnt['enn'] += 1
            if FAIL_RE.search(msg):
                cnt['failure'] += 1
        # [사후 수정 14:26 — 첫 실행 표 b3_attribution_run1_labelbug.csv 보존] npu-runner 단일 런의 run_metadata.resource 는 항상 'NPU' 라벨이다;
        # 규칙의 '런 자원' = 실제 요청 가속기 npu_accelerator_requested (CPU/GPU/NPU). 규칙 문장·판정식은 그대로.
        req = meta.get('npu_accelerator_requested')
        exp_acc = s['accelerator'] if chain else (req if req in ('CPU', 'GPU', 'NPU') else meta.get('resource'))
        model_init = None if i == 0 else (tr_full[i - 1].get('model_initialized') if i - 1 < len(tr_full) else None)
        if exp_acc in ('GPU', 'NPU'):
            other = cnt['NPU' if exp_acc == 'GPU' else 'GPU'] + cnt['other']
            if cnt[exp_acc] >= 1 and other == 0 and cnt['failure'] == 0:
                v = 'PASS (구간 고유 증거)'
            elif cnt[exp_acc] == 0 and cnt['GPU'] + cnt['NPU'] + cnt['other'] == 0 and model_init is False:
                v = '재사용 — 구간 고유 증거 없음 (판정 안 함)'
            else:
                why = []
                if cnt[exp_acc] < 1:
                    why.append('기대 가속기 교체 줄 0')
                if other:
                    why.append(f'다른 가속기 줄 {other}')
                if cnt['failure']:
                    why.append(f'실패·fallback 줄 {cnt["failure"]}')
                v = 'FAIL (' + ' · '.join(why) + ')'
        else:
            gpu_npu = cnt['GPU'] + cnt['NPU'] + cnt['other']
            v = 'PASS (CPU — 다른 가속기 교체 줄 0 · 실패 0)' if (gpu_npu == 0 and cnt['failure'] == 0) else f'FAIL (CPU 구간에 교체 줄 {gpu_npu} · 실패 {cnt["failure"]})'
        rows.append(dict(experiment=exp, run_id=meta.get('run_id'), segment=i, label=s.get('label'), expected_accelerator=exp_acc,
                         window_wall_start_ms=round(a, 1), window_wall_end_ms=round(b, 1), runner_pids=len(pids),
                         repl_GPU_LITERT_CL=cnt['GPU'], repl_NPU_Dispatch=cnt['NPU'], repl_other=cnt['other'], enn_lines=cnt['enn'],
                         failure_lines=cnt['failure'], transition_model_initialized=model_init, verdict=v))
    return rows


def segments_table(exp, R, anchors, tr_full):
    meta = R['meta']
    out, trs = [], []
    for s in R['segments']:
        m = (R['inf_start'] >= s['start_ns']) & (R['inf_end'] <= s['end_ns'])
        lat = list(R['inf_lat_ms'][m])
        L = (s['end_ns'] - s['start_ns']) / 1e9
        out.append(dict(experiment=exp, run_id=meta.get('run_id'), segment=s['index'], label=s['label'], accelerator=s['accelerator'],
                        requested_duty=s['duty'], planned_s=s['duration_s'], start_mono_ns=s['start_ns'], end_mono_ns=s['end_ns'],
                        start_wall_ms=round(wall_of(anchors, s['start_ns']), 1), actual_s=round(L, 6), inference_count=len(lat),
                        segment_end_inference_count=s.get('inference_count'), termination=s.get('termination'),
                        latency_definition=(meta.get('npu_latency_boundary') or 'runner latency_ns (engine timed span)'),
                        latency_p50_ms=(round(statistics.median(lat), 6) if lat else None), latency_p95_ms_nearest_rank=(round(nearest_rank(lat, 0.95), 6) if lat else None)))
    for d in tr_full:
        dur = (int(d['end_ns']) - int(d['start_ns']))
        parts = sum(int(d.get(k) or 0) for k in ('env_init_ns', 'model_init_ns', 'buffer_init_ns'))
        trs.append(dict(experiment=exp, run_id=meta.get('run_id'), to_segment=d.get('to_segment'), from_accelerator=d.get('from_accelerator'),
                        to_accelerator=d.get('to_accelerator'), backend_switch=d.get('backend_switch'), model_initialized=d.get('model_initialized'),
                        warmup_count=d.get('warmup_count'), duration_ms=round(dur / 1e6, 3), env_init_ms=round(int(d.get('env_init_ns') or 0) / 1e6, 3),
                        model_init_ms=round(int(d.get('model_init_ns') or 0) / 1e6, 3), buffer_init_ms=round(int(d.get('buffer_init_ns') or 0) / 1e6, 3),
                        unexplained_ms=round((dur - parts) / 1e6, 3)))
    return out, trs


def sensors(run_dir):
    th, d1 = [], []
    mp = os.path.join(run_dir, 'merged', 'events.jsonl')
    with open(mp, encoding='utf-8') as fh:
        for line in fh:
            if '"event":"sample"' not in line:
                continue
            if '"source":"thermalservice"' in line:
                s = json.loads(line)
                th.append({k: s.get(k) for k in ('mono_ns', 'sample_before_mono_ns', 'sample_after_mono_ns', 'sampling_uncertainty_ns', 'AP', 'BAT', 'PA', 'SKIN',
                                                 'thermal_status', 'parse_status', 'missing_sensors', 'analysis_phase')})
            elif '"source":"d1check"' in line:
                s = json.loads(line)
                d1.append({k: s.get(k) for k in ('mono_ns', 'wall_ms', 'elapsed_s', 'tick', 'current_raw', 'current_valid', 'voltage_mV', 'charge_counter_raw',
                                                 'charge_valid', 'plugged', 'battery_temp_C', 'thermal_status', 'headroom_now', 'analysis_phase')})
    th.sort(key=lambda r: r['mono_ns']); d1.sort(key=lambda r: r['mono_ns'])
    return th, d1


def interval_stats(rows):
    t = [int(r['mono_ns']) for r in rows if r.get('mono_ns') is not None]
    if len(t) < 2:
        return dict(n=len(t), median_interval_s=None, max_gap_s=None, gaps_gt_3x=None, nonmonotonic=None)
    d = [(b - a) / 1e9 for a, b in zip(t, t[1:])]
    med = statistics.median(d)
    return dict(n=len(t), median_interval_s=round(med, 6), max_gap_s=round(max(d), 3), gaps_gt_3x=sum(1 for x in d if x > 3 * med),
                nonmonotonic=sum(1 for x in d if x <= 0))


def write_csv(path, rows, fields=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = fields or (list(rows[0].keys()) if rows else ['empty'])
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: _clean(r.get(k)) for k in fields})


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo-out', required=True)
    ap.add_argument('--git-out', required=True)
    ap.add_argument('--skip-inventory', action='store_true')
    a = ap.parse_args()
    ro, go = os.path.abspath(a.repo_out), os.path.abspath(a.git_out)
    os.makedirs(ro, exist_ok=True); os.makedirs(go, exist_ok=True)
    b1, b3s, b3t, b3a, b2inv, files = [], [], [], [], [], []
    for exp in EXP_1002 + EXP_1003:
        rd = one_run(exp)
        jf = glob.glob(os.path.join(rd, 'gpu', '*.jsonl'))
        man = json.load(open(os.path.join(ROOT, 'results', exp, 'experiment_manifest.json'), encoding='utf-8'))
        rs = list(csv.DictReader(open(os.path.join(ROOT, 'results', exp, 'exports-v2', 'run_summary.csv'), encoding='utf-8'))) \
            if os.path.exists(os.path.join(ROOT, 'results', exp, 'exports-v2', 'run_summary.csv')) else []
        slot = (man.get('runs') or [{}])[0] if man.get('runs') else {}
        row = dict(experiment=exp, date_group=exp[-4:], device_anon_id='S26-1', device_model=(man.get('device') or {}).get('model'),
                   orchestrator_version=man.get('orchestrator_version'), experiment_status=man.get('status'), mode=(man.get('config') or {}).get('mode'),
                   role='pilot · 개발 자료 (확인·holdout 아님)', slot_status=slot.get('status'), validation_status=(rs[0].get('validation_status') if rs else None),
                   exclusion_or_flags=(rs[0].get('exclusion_reasons') if rs and 'exclusion_reasons' in rs[0] else None),
                   installed_apk_note='npu-runner 설치본 5ac485e3… (10-02 23:56:58 이후 — CLAUDE.md 1002 블록) · benchmark-runner 는 CPU 칸 — APK hash 는 manifest 에 없음 (미확인)')
        if not jf:
            row.update(runner_jsonl='없음', note='러너 JSONL 없음 (안전 중단 등) — 표 없음')
            b1.append(row)
            continue
        R, anchors, tr_full = runner_events(jf[0])
        meta = R['meta']
        for k in META_KEYS:
            row[f'meta_{k}'] = meta.get(k)
        row.update(load_start_mono_ns=R['load_start'], load_end_mono_ns=R['load_end'], load_start_wall_ms=round(wall_of(anchors, R['load_start']), 1),
                   load_end_wall_ms=round(wall_of(anchors, R['load_end']), 1), planned_s=meta.get('requested_duration_s'),
                   actual_load_s=round((R['load_end'] - R['load_start']) / 1e9, 6), completed_inference_count=meta.get('completed_inference_count'),
                   inference_events=int(len(R['inf_start'])))
        b1.append(row)
        st, tr = segments_table(exp, R, anchors, tr_full)
        b3s += st; b3t += tr
        year = datetime.datetime.fromtimestamp(anchors[0][1] / 1000.0, KST).year
        b3a += attribution(exp, R, anchors, tr_full, logcat_lines(os.path.join(rd, 'raw', 'logcat.txt'), year))
        th, d1 = sensors(rd)
        f1p, f2p = os.path.join(go, 'sensors', f'{exp}__thermal.csv'), os.path.join(go, 'sensors', f'{exp}__d1check.csv')
        write_csv(f1p, th); write_csv(f2p, d1)
        st_th, st_d1 = interval_stats(th), interval_stats(d1)
        b2inv.append(dict(experiment=exp, run_id=meta.get('run_id'), thermal_n=st_th['n'], thermal_median_interval_s=st_th['median_interval_s'],
                          thermal_max_gap_s=st_th['max_gap_s'], thermal_gaps_gt_3x=st_th['gaps_gt_3x'], thermal_parse_not_ok=sum(1 for r in th if r.get('parse_status') not in (None, 'ok')),
                          d1_n=st_d1['n'], d1_median_interval_s=st_d1['median_interval_s'], d1_max_gap_s=st_d1['max_gap_s'], d1_gaps_gt_3x=st_d1['gaps_gt_3x'],
                          d1_current_invalid=sum(1 for r in d1 if r.get('current_valid') is False), d1_charge_invalid=sum(1 for r in d1 if r.get('charge_valid') is False),
                          plugged_nonzero=sum(1 for r in d1 if r.get('plugged') not in (0, None)),
                          units='current_raw = 원 정수 (µA 로 읽음, 음수 = 방전 [E — 기기 문서 미확인: raw_unscaled_unit_unverified]) · voltage_mV · charge_counter_raw (µAh 로 읽음, 계단 4,275 [P C2 gcd]) · 온도 ℃ (HAL 문자열) · 보간 없음'))
        files += [(os.path.relpath(f1p, go), f1p), (os.path.relpath(f2p, go), f2p)]
        print(exp, 'segments', len(st), 'attr', [r['verdict'][:4] for r in b3a if r['experiment'] == exp], flush=True)
    # C2 electrical raw time series (20 runs)
    for rd in sorted(d for d in glob.glob(os.path.join(ROOT, 'results', C2_DIR, 'runs', '*')) if os.path.isdir(d)):
        if not os.path.exists(os.path.join(rd, 'merged', 'events.jsonl')):
            continue
        th, d1 = sensors(rd)
        p = os.path.join(go, 'c2_sensors', f'{os.path.basename(rd)}__d1check.csv')
        write_csv(p, d1)
        q = os.path.join(go, 'c2_sensors', f'{os.path.basename(rd)}__thermal.csv')
        write_csv(q, th)
        files += [(os.path.relpath(p, go), p), (os.path.relpath(q, go), q)]
    write_csv(os.path.join(ro, 'b1_runs.csv'), b1, sorted({k for r in b1 for k in r}, key=lambda k: (not k.startswith(('experiment', 'date', 'device', 'role')), k)))
    json.dump(b1, open(os.path.join(ro, 'b1_runs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    write_csv(os.path.join(ro, 'b2_sensor_inventory.csv'), b2inv)
    write_csv(os.path.join(ro, 'b3_segments.csv'), b3s)
    write_csv(os.path.join(ro, 'b3_transitions.csv'), b3t)
    write_csv(os.path.join(ro, 'b3_attribution.csv'), b3a)
    write_csv(os.path.join(ro, 'b2_files_sha256.csv'), [dict(path=r, bytes=os.path.getsize(p), sha256=sha256(p)) for r, p in files])
    if not a.skip_inventory:
        inv = []
        for exp in EXP_1002 + EXP_1003 + INVENTORY_ONLY + [C2_DIR]:
            base = os.path.join(ROOT, 'results', exp)
            for p in sorted(glob.glob(os.path.join(base, '**', '*'), recursive=True)):
                if os.path.isfile(p):
                    inv.append(dict(experiment=exp, scope=('full export' if exp in EXP_1002 + EXP_1003 else ('C2 electrical' if exp == C2_DIR else 'inventory only')),
                                    relpath=os.path.relpath(p, base).replace('\\', '/'), bytes=os.path.getsize(p), sha256=sha256(p),
                                    note=('logcat — 공유 금지 (iccid·eSIM 줄), 해시만' if 'logcat' in os.path.basename(p) else '')))
            print('inventory', exp, flush=True)
        write_csv(os.path.join(ro, 'b4_raw_inventory.csv'), inv)
    print('done', len(b1), 'runs', len(b3s), 'segments', len(b3a), 'attribution rows', len(files), 'sensor files')
    return 0


if __name__ == '__main__':
    sys.exit(main())
