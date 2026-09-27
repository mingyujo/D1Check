"""Post-hoc fixed-episode diagnostics and a strict arrival-model support gate.

This module does not refit the frozen development profile. Its output is not an
independent validation: the confirmation summary preceded this v2 diagnostic.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_energy_operational_sim as episode
from tools import d1_energy_thermal as energy
from tools import d1_energy_collection as collection

VERSION = "energy-ap-bridge-pc-v2"
EXPLORATORY_AP_THRESHOLD_C = 30.0  # diagnostic axis, not a safety limit
STATES = ("resident_idle", "classification_CPU", "detection_GPU",
          "classification_CPU+detection_GPU")


def engine_support(result, horizon_ns):
    """Report actual joint occupancy; refuse to borrow 870-job phase coefficients."""
    segments = energy.ledger_segments(result, horizon_ns)
    dwell = {}
    for row in segments:
        state = row["state"] + ("|queued" if row["waiting"] else "")
        dwell[state] = dwell.get(state, 0.0) + row["end_s"] - row["start_s"]
    return dict(version=VERSION, status="UNSUPPORTED_STATE_COSTS",
                whole_device_energy_j=None, ap_path_c=None,
                independent_prediction_validated=False,
                observed_fixed_episode_state="CC_DG_870_jobs_serial_or_parallel_only",
                reason="fixed-episode phase averages cannot identify arbitrary request transitions, model-specific solo power, queue idle, or joint-state AP dynamics",
                required_joint_states_s=dict(sorted(dwell.items())))


def _interpolate(rows, t_ns, value):
    for a, b in zip(rows, rows[1:]):
        if a["mono_ns"] <= t_ns <= b["mono_ns"]:
            dt = b["mono_ns"] - a["mono_ns"]
            if dt <= 0 or dt > 10_000_000_000 or a.get(value) in (None, "") or b.get(value) in (None, ""):
                return None
            u = (t_ns-a["mono_ns"])/dt
            return float(a[value]) + u*(float(b[value])-float(a[value]))
    return None


def common_prediction(prediction, t_s):
    """Whole-device J from load start, preserving the same 480 s boundary."""
    if not 0 <= t_s <= 480:
        raise ValueError("OUT_OF_SUPPORT: common window")
    phases = {row["phase"]: row for row in prediction["phase_trace"]}
    load = phases["load"]
    post = phases["post_work_wait"]
    load_w = load["whole_device_energy_j_conditional"]/(load["end_s"]-load["start_s"])
    post_w = post["whole_device_energy_j_conditional"]/(post["end_s"]-post["start_s"])
    load_s = load["end_s"]-load["start_s"]
    return load_w*min(t_s, load_s) + post_w*max(0.0, t_s-load_s)


def development_state_power(plan_path, run_root):
    """Four occupied states, with no confirmation inputs and no invented reverse pair."""
    plan, freeze = episode.identity(plan_path, run_root)
    by_state = {name: [] for name in STATES}
    sources = []
    for entry in plan["entries"][:2]:
        folder = episode.folder_for(run_root, entry)
        stats = episode.read(folder / "validated.json")
        if stats != freeze["conditions"][f"{episode.PAIR}_{entry['mode']}"]:
            raise ValueError("development state lineage")
        sources.append(dict(session_id=entry["session_id"], validated_sha256=episode.digest(folder / "validated.json")))
        for state, values in stats["metrics"]["occupancy_states"].items():
            if state in by_state:
                # A 0.12 s lone CPU tail is too short to identify solo power.
                if state == "classification_CPU" and entry["mode"] == "parallel":
                    continue
                if state == "classification_CPU+detection_GPU" and entry["mode"] != "parallel":
                    continue
                if values["complete_energy_j"] is None or values["covered_s"] < 10:
                    raise ValueError("insufficient development state coverage")
                by_state[state].append(values)
    if not all(by_state.values()):
        raise ValueError("unidentified required state")
    power = {name: sum(r["covered_energy_j"] for r in rows)/sum(r["covered_s"] for r in rows)
             for name, rows in by_state.items()}
    return dict(version=VERSION, role="posthoc_development_state_mean_not_arrival_prediction",
                whole_device_power_w=power,
                observed_duration_s={name: sum(r["covered_s"] for r in rows)
                                     for name, rows in by_state.items()},
                source_sessions=sources, plan_sha256=episode.digest(plan_path),
                current_ua_per_raw_hypothesis=1000, absolute_energy_certified=False,
                thermal_state_coefficients=None, supported_pair="CC_DG_only_fixed_870_episode")


def schedule_conditioned_energy(intervals, power, start_ns, end_ns):
    """Measured occupancy boundaries are inputs; this is not an open-loop forecast."""
    if not intervals or intervals[0]["start_ns"] != start_ns or intervals[-1]["end_ns"] != end_ns:
        raise ValueError("incomplete state partition")
    total = 0.0
    previous = start_ns
    for row in intervals:
        if row["start_ns"] != previous or row["state"] not in power:
            raise ValueError("unsupported or noncontiguous state")
        total += (row["end_ns"]-row["start_ns"])/1e9*power[row["state"]]
        previous = row["end_ns"]
    return total


def diagnose(profile_path, spec_path, plan_path, run_root):
    profile = episode.read(profile_path)
    spec = episode.read(spec_path)
    if spec != episode.evaluation_spec(profile_path):
        raise ValueError("frozen evaluation specification mismatch")
    plan, _ = episode.identity(plan_path, run_root)
    if profile["plan_sha256"] != episode.digest(plan_path):
        raise ValueError("frozen profile lineage mismatch")
    state_profile = development_state_power(plan_path, run_root)
    series, summary = [], []
    for entry in plan["entries"][2:]:
        folder = episode.folder_for(run_root, entry)
        stats = episode.read(folder / "validated.json")
        if stats["status"] != "eligible_descriptive_only" or stats["work_requests"] != 870:
            raise ValueError("ineligible confirmation")
        initial, thermal = episode.measured_initial_ap(folder, stats)
        pred = episode.predict(profile, mode=entry["mode"], initial_ap_c=initial,
                               fingerprint=plan["device_fingerprint"],
                               model_sha256=profile["model_sha256"], input_sha256=profile["input_sha256"],
                               work_counts=episode.COUNTS, initial_ap_source="observed_same_episode_preload")
        with (folder / "artifacts" / "progress.jsonl").open(encoding="utf-8") as stream:
            samples = [r for r in map(json.loads, stream) if r["kind"] == "power_sample"]
        load_ns = stats["phases"]["load"]["start_ns"]
        prep_ns = stats["phases"]["temperature_preparation"]["start_ns"]
        common_end_ns = stats["phases"]["post_work_wait"]["end_ns"]
        requests = episode.read(folder / "artifacts" / "load.requests.json")
        intervals = collection.state_intervals(requests, load_ns, common_end_ns)
        state_energy = schedule_conditioned_energy(intervals,
            state_profile["whole_device_power_w"], load_ns, common_end_ns)
        errors_e, errors_ap = [], []
        observed_over = predicted_over = covered_ap_s = 0
        for second in range(481):
            at_ns = load_ns + second*1_000_000_000
            measured_e = energy.integrate(samples, load_ns, at_ns, 1000)
            obs_j = measured_e["full_energy_j"] if second else 0.0
            pred_j = common_prediction(pred, second)
            obs_ap = _interpolate(thermal, at_ns, "AP")
            pred_ap = episode.at_time(pred, (at_ns-prep_ns)/1e9)
            if obs_j is not None:
                errors_e.append(pred_j-obs_j)
            if obs_ap is not None and pred_ap is not None:
                errors_ap.append(pred_ap-obs_ap)
                if second < 480:
                    covered_ap_s += 1
                    observed_over += obs_ap > EXPLORATORY_AP_THRESHOLD_C
                    predicted_over += pred_ap > EXPLORATORY_AP_THRESHOLD_C
            series.append(dict(session_id=entry["session_id"], mode=entry["mode"],
                               common_elapsed_s=second, observed_energy_j_conditional=obs_j,
                               predicted_energy_j_conditional=pred_j,
                               energy_error_j=(pred_j-obs_j if obs_j is not None else None),
                               observed_ap_c=obs_ap, predicted_ap_c=pred_ap,
                               ap_error_c=(pred_ap-obs_ap if obs_ap is not None and pred_ap is not None else None)))
        if not errors_e or not errors_ap:
            raise ValueError("no aligned energy/AP comparison")
        final_e = stats["metrics"]["common_window"]["full_energy_j"]
        original_boundary = energy.integrate(samples, load_ns, common_end_ns, 1000)
        if not math.isclose(original_boundary["full_energy_j"], final_e,
                            rel_tol=0, abs_tol=1e-6):
            raise ValueError("raw integration differs from original common-window summary")
        if not math.isclose(common_prediction(pred, 480),
                            pred["common_window_energy_j_conditional"], rel_tol=0, abs_tol=1e-6):
            raise ValueError("template common-window energy boundary mismatch")
        summary.append(dict(session_id=entry["session_id"], mode=entry["mode"],
                            initial_ap_c=initial, energy_error_480s_j=pred["common_window_energy_j_conditional"]-final_e,
                            energy_abs_error_480s_j=abs(pred["common_window_energy_j_conditional"]-final_e),
                            state_schedule_conditioned_energy_j=state_energy,
                            state_schedule_conditioned_error_j=state_energy-final_e,
                            energy_path_mae_j=sum(map(abs, errors_e))/len(errors_e),
                            energy_path_max_abs_error_j=max(map(abs, errors_e)),
                            energy_path_points=len(errors_e),
                            ap_path_mae_c=sum(map(abs, errors_ap))/len(errors_ap),
                            ap_path_max_abs_error_c=max(map(abs, errors_ap)),
                            ap_path_points=len(errors_ap),
                            ap_threshold_c_exploratory=EXPLORATORY_AP_THRESHOLD_C,
                            ap_threshold_covered_s=covered_ap_s,
                            observed_over_threshold_covered_s=observed_over,
                            predicted_over_threshold_covered_s=predicted_over,
                            over_threshold_error_covered_s=predicted_over-observed_over,
                            full_480s_threshold_supported=(covered_ap_s == 480)))
    return summary, series, state_profile


def _csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    summary, series, state_profile = diagnose(args.profile, args.spec, args.plan, args.run)
    _csv(out / "confirmation_errors.csv", summary)
    _csv(out / "confirmation_paths.csv", series)
    (out / "development_state_power.json").write_text(json.dumps(state_profile, indent=2)+"\n", encoding="utf-8")
    (out / "support.json").write_text(json.dumps(dict(version=VERSION,
        fixed_episode="development_fit_confirmation_posthoc_diagnostic",
        arrival_state_model="UNSUPPORTED_STATE_COSTS", independent_validation=False,
        threshold_c_exploratory=EXPLORATORY_AP_THRESHOLD_C,
        source_profile_sha256=episode.digest(args.profile),
        source_spec_sha256=episode.digest(args.spec),
        source_plan_sha256=episode.digest(args.plan)), indent=2)+"\n", encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["svg.hashsalt"] = VERSION
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for mode in episode.MODE_ORDER:
        rows = [r for r in series if r["mode"] == mode]
        x = [r["common_elapsed_s"] for r in rows]
        for ax, key, label, color in ((axes[0], "energy", "J (conditional)", "tab:blue"),
                                       (axes[1], "ap", "AP °C", "tab:red")):
            observed = "observed_energy_j_conditional" if key == "energy" else "observed_ap_c"
            predicted = "predicted_energy_j_conditional" if key == "energy" else "predicted_ap_c"
            ax.plot(x, [r[observed] for r in rows], label=f"{mode} observed", color=color, linestyle="-" if mode == "serial" else ":")
            ax.plot(x, [r[predicted] for r in rows], label=f"{mode} dev-template", color=color, linestyle="--" if mode == "serial" else "-.")
            ax.set_ylabel(label)
            ax.legend(fontsize=8, ncol=2)
    axes[1].set_xlabel("Seconds since load start; 480 s common window")
    fig.suptitle("A24 CC_DG confirmation: observed vs post-hoc development template")
    fig.tight_layout()
    fig.savefig(out / "confirmation_paths.png", dpi=150)
    fig.savefig(out / "confirmation_paths.svg", metadata={"Date": None})
    svg = out / "confirmation_paths.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines())+"\n",
                   encoding="utf-8")
    plt.close(fig)
    import html
    header = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 에너지·AP 모형 경계</title>
<style>body{font:16px/1.6 system-ui,'Malgun Gothic';max-width:1100px;margin:2em auto;padding:0 1em;color:#183246}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd8e1;padding:.45em;text-align:right}td:first-child,th:first-child{text-align:left}img{max-width:100%}.warn{background:#fff0cf;padding:1em}</style>
<h1>A24 고정 CC_DG: 실측과 개발 모형</h1><p class="warn">4세션 중 개발 2세션으로 적합한 고정 870건 모형의 확인 2세션 사후 진단입니다. 확인 요약을 이미 본 뒤 추가한 지표이므로 독립 사전등록 검증이 아닙니다. J는 A24 전류 raw=mA 가정의 기기 전체 소비이며 절대 정확도 미인증입니다. AP는 배터리/표면 온도가 아닙니다.</p>
<p><a href="../arrival_policy_screen_01/dashboard.html">기존 통합 정책 탐색으로 돌아가기</a> · <a href="confirmation_errors.csv">오차 CSV</a> · <a href="confirmation_paths.csv">시간축 CSV</a> · <a href="development_state_power.json">개발 상태 전력</a></p><img src="confirmation_paths.svg" alt="확인 직렬/병행 480초 누적 에너지와 AP 경로: 실측 대 개발 템플릿">
<h2>확인 세션별 오차</h2><table><tr><th>조건</th><th>480초 J 오차 (예측−관측)</th><th>누적 J 경로 MAE</th><th>AP 경로 MAE °C</th><th>AP 최대 절대오차 °C</th><th>30°C 초과 오차/비교 가능 시간</th></tr>"""
    body = "".join(f"<tr><td>{html.escape(r['mode'])}</td><td>{r['energy_error_480s_j']:+.3f}</td><td>{r['energy_path_mae_j']:.3f}</td><td>{r['ap_path_mae_c']:.3f}</td><td>{r['ap_path_max_abs_error_c']:.3f}</td><td>{r['over_threshold_error_covered_s']:+d} / {r['ap_threshold_covered_s']} s</td></tr>" for r in summary)
    footer = """</table><p>30°C는 그림을 읽기 위한 탐색 축이며 안전 한도가 아닙니다. 병행 AP 1초는 예측 phase 경계의 미계측 gap 때문에 제외됐습니다. 전체 480초 초과시간으로 읽지 마십시오.</p>
<h2>지원 상태</h2><p>개발 상태 평균 W: resident idle, 분류 CPU, 탐지 GPU, 분류 CPU+탐지 GPU만 식별했습니다. 확인 세션의 <em>실제</em> 점유 구간에 대입한 J는 일정 조건부 사후 재생이며, 임의 도착의 처리시간·전력·AP 예측이 아닙니다. 분류 GPU, 탐지 CPU, 역방향 병행, 동일 과업 병행과 상태별 AP 응답은 미지원입니다. 기존 합성 정책 화면의 에너지/AP는 탐색 가정입니다.</p>
<p>BAT·SKIN·NPU·다른 기기·열 throttling·배터리 잔량/사용시간 예측은 미지원. 센서 표본은 독립 세션 반복이 아닙니다.</p></html>"""
    (out / "dashboard.html").write_text(header+body+footer, encoding="utf-8")


if __name__ == "__main__":
    main()
