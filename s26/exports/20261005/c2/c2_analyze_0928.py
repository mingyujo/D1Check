# -*- coding: utf-8 -*-
"""C2 (EfficientNet-Lite0 × NPU formal 20런) 정리 — 읽기 전용.
런마다 1-6 보존 검사(throttle_curve_0928.conservation, 고정판 그대로 import) + formal_npu_valid + run_summary,
duty 별 5런 중앙 지연·CV·열, MobileNet NPU (9/25 formal 0925b) 와 비교.
  py c2_analyze_0928.py <C2 결과 폴더> <MobileNet NPU formal 결과 폴더> [--out f.json]
"""
import argparse, csv, glob, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import throttle_curve_0928 as T


def rows(d):
    return {r["run_id"]: r for r in csv.DictReader(open(os.path.join(d, "exports-v2", "run_summary.csv"), encoding="utf-8"))}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def per_duty(rs):
    out = {}
    for duty in ("25", "50", "75", "100"):
        g = [r for r in rs if r["requested_duty_cycle_percent"] == duty and r["validation_status"] == "valid"]
        lat = [f(r["latency_median_ms"]) for r in g]
        lat = [x for x in lat if x is not None]
        out[duty] = dict(n=len(g), lat_median_of_runs=st.median(lat) if lat else None,
                         lat_min=min(lat) if lat else None, lat_max=max(lat) if lat else None,
                         cv_pct=(st.pstdev(lat) / st.mean(lat) * 100) if len(lat) > 1 else None,
                         count_median=st.median([int(r["completed_inference_count"]) for r in g]) if g else None,
                         skin_start=[f(r["skin_load_start_temperature_c"]) for r in g],
                         skin_rise_median=st.median([f(r["skin_load_change_c"]) for r in g if f(r["skin_load_change_c"]) is not None]) if g else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("c2"); ap.add_argument("mobilenet"); ap.add_argument("--out")
    a = ap.parse_args()
    R2 = rows(a.c2)
    results = []
    print("| slot | run | 보존 | 1 duty 계산 % | 2 추론 | 4 자원 | 5 전원 | validation | formal_npu_valid | 지연 중앙 ms | SKIN 시작→끝 | 밴드 |")
    print("|---|---|---|---:|---:|---|---|---|---|---:|---|---|")
    for run_dir in sorted(glob.glob(os.path.join(a.c2, "runs", "*"))):
        rid = os.path.basename(run_dir)
        row = R2.get(rid)
        if row is None:
            print(f"| (run_summary 에 없음) | {rid[:8]} | — |")
            results.append(dict(run_id=rid, orphan=True))
            continue
        duty = float(row["requested_duty_cycle_percent"])
        cons, R, M = T.conservation(run_dir, row, "NPU", 60, duty)
        sm = json.load(open(os.path.join(run_dir, "merged", "summary.json"), encoding="utf-8"))
        s0, s1 = f(row["skin_load_start_temperature_c"]), f(row["skin_load_end_temperature_c"])
        band = s0 is not None and T.BAND[0] <= s0 <= T.BAND[1]
        rec = dict(run_id=rid, slot=row["slot_id"], duty=duty, conservation_ok=cons["ok"],
                   c1=cons["1_load_duty"], c2=cons["2_count"], c4=cons["4_resource"], c5=cons["5_power"], c3=cons["3_telemetry"],
                   validation=row["validation_status"], slot_status=row["slot_status"], termination=row["termination_reason"],
                   formal_npu_valid=sm.get("formal_npu_valid"), formal_npu_conditions=sm.get("formal_npu_conditions"),
                   latency_median_ms=f(row["latency_median_ms"]), n=int(row["completed_inference_count"]),
                   skin_start=s0, skin_end=s1, band=band, model_sha256=(R["meta"] or {}).get("model_sha256"),
                   input_spec=(R["meta"] or {}).get("npu_input_spec"), pilot_battery_pct=(R["meta"] or {}).get("pilot_battery_pct"),
                   quality=(sm.get("npu_quality_preflight") or {}).get("quality_gate", {}).get("verdict"))
        results.append(rec)
        print(f"| {row['slot_id']} | {rid[:8]} | {'OK' if cons['ok'] else '보존 불일치'} | {cons['1_load_duty']['computed_active_pct']:.2f} | "
              f"{cons['2_count']['jsonl']} (merged {cons['2_count']['merged']}) | {'OK' if cons['4_resource']['ok'] else 'FAIL ' + ';'.join(cons['4_resource']['notes'])} | "
              f"{'OK' if cons['5_power']['ok'] else 'FAIL'} | {row['validation_status']} | {sm.get('formal_npu_valid')} | {rec['latency_median_ms']:.4f} | "
              f"{s0}→{s1} | {'안' if band else '밖'} |")
        if not cons["ok"]:
            for k in ("1_load_duty", "2_count", "3_telemetry", "4_resource", "5_power"):
                if not cons[k]["ok"]:
                    print(f"    {k}: {json.dumps(cons[k], ensure_ascii=False, default=str)}")
    ok = [r for r in results if not r.get("orphan")]
    print(f"\n런 {len(ok)} · 보존 OK {sum(r['conservation_ok'] for r in ok)} · valid {sum(r['validation'] == 'valid' for r in ok)} · "
          f"formal_npu_valid {sum(r['formal_npu_valid'] is True for r in ok)} · 밴드 안 {sum(r['band'] for r in ok)} · 고아 run 폴더 {sum(1 for r in results if r.get('orphan'))}")
    print(f"model_sha256 {sorted(set(r['model_sha256'] for r in ok))} · input_spec {sorted(set(str(r['input_spec']) for r in ok))} · 품질 {sorted(set(str(r['quality']) for r in ok))}")
    c2d = per_duty(list(R2.values()))
    mbd = per_duty(list(rows(a.mobilenet).values()))
    print("\n| duty | C2 EfficientNet 지연 (5런 중앙, 범위) ms | CV % | 추론 수 중앙 | SKIN 상승 중앙 ℃ | MobileNet NPU (0925b) 지연 ms | 추론 수 중앙 | SKIN 상승 중앙 | 지연 비 |")
    print("|---:|---|---:|---:|---:|---|---:|---:|---:|")
    for duty in ("25", "50", "75", "100"):
        c, m = c2d[duty], mbd[duty]
        ratio = c["lat_median_of_runs"] / m["lat_median_of_runs"] if c["lat_median_of_runs"] and m["lat_median_of_runs"] else None
        print(f"| {duty} | {c['lat_median_of_runs']} ({c['lat_min']}~{c['lat_max']}) n={c['n']} | {c['cv_pct']} | {c['count_median']} | {c['skin_rise_median']} | "
              f"{m['lat_median_of_runs']} ({m['lat_min']}~{m['lat_max']}) n={m['n']} | {m['count_median']} | {m['skin_rise_median']} | {ratio} |")
    if a.out:
        json.dump(dict(runs=results, c2_duty=c2d, mobilenet_duty=mbd), open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
