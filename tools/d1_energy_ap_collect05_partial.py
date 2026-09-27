"""Write a small, read-only diagnostic for a stopped state collection.

The source run directory is never changed. This is deliberately not a model
registration path: a partial confirmation set cannot extend supported scope.
"""

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_energy_thermal as energy
from tools import d1_energy_state_collection as state


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def paths_for_confirmation(stats, frozen):
    start, end = stats["common_start_ns"], stats["common_end_ns"]
    ordered, _ = energy.canonical_samples(stats["power_path"])
    power = frozen["whole_device_power_w"]

    def predicted_energy(hi):
        total = 0.0
        for left, right in zip(ordered, ordered[1:]):
            a = max(start, left["mono_ns"])
            b = min(hi, right["mono_ns"])
            if b <= a or right["mono_ns"] - left["mono_ns"] > 2_500_000_000:
                continue
            if energy.discharge_w(left, 1000) is None or energy.discharge_w(right, 1000) is None:
                continue
            for block in stats["blocks"]:
                seconds = max(0, min(b, block["end_ns"]) - max(a, block["start_ns"])) / 1e9
                total += power[block["state"]] * seconds
        return total

    energy_rows = []
    points = list(range(start + 10_000_000_000, end + 1, 10_000_000_000))
    if not points or points[-1] != end:
        points.append(end)
    for point in points:
        observed = energy.integrate(stats["power_path"], start, point, 1000)
        if observed["covered_s"] < 0.95 * observed["duration_s"]:
            continue
        energy_rows.append(dict(time_s=(point - start) / 1e9,
                                observed_energy_j=observed["covered_energy_j"],
                                predicted_energy_j=predicted_energy(point),
                                covered_s=observed["covered_s"]))

    ap_rows = []
    temperature = stats["start_ap_c"]
    beta = frozen["ap_cooling_rate_per_s"]
    for block in stats["blocks"]:
        equilibrium = frozen["ap_reference_c"] + frozen["ap_slope_at_30_c_per_s"][block["state"]] / beta
        for point in block["ap_path"]:
            seconds = (point["mono_ns"] - block["start_ns"]) / 1e9
            predicted = equilibrium + (temperature - equilibrium) * math.exp(-beta * seconds)
            ap_rows.append(dict(time_s=(point["mono_ns"] - start) / 1e9,
                                block=block["name"], observed_ap_c=point["ap_c"],
                                predicted_ap_c=predicted))
        duration = (block["end_ns"] - block["start_ns"]) / 1e9
        temperature = equilibrium + (temperature - equilibrium) * math.exp(-beta * duration)
    return energy_rows, ap_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root, output = Path(args.run_root), Path(args.output)
    receipt = read(root / "FINAL_RECEIPT.json")
    if receipt["status"] != "stopped_no_resume":
        raise ValueError("this diagnostic requires a stopped run")
    frozen = read(root / "development_freeze.json")
    if frozen["version"] != "energy-ap-state-regimen-fit-v1":
        raise ValueError("unexpected frozen model")
    sessions = [read(path) for path in sorted(root.glob("0?_*/*validated.json"))]
    development = [row for row in sessions if row["phase"] == "development"]
    confirmation = [row for row in sessions if row["phase"] == "confirmation"]
    if len(development) != 3 or len(confirmation) != 1 or len(sessions) != receipt["completed_sessions"]:
        raise ValueError("unexpected completed session boundary")
    stats = confirmation[0]
    errors = state.evaluate(stats, frozen, {})
    if errors != stats["confirmation_errors"]:
        raise ValueError("stored frozen evaluation differs")
    energy_rows, ap_rows = paths_for_confirmation(stats, frozen)
    if not energy_rows or not ap_rows:
        raise ValueError("missing diagnostic path")
    if abs(energy_rows[-1]["predicted_energy_j"] - errors["common_energy_predicted_on_observed_coverage_j"]) > 1e-6:
        raise ValueError("energy plot disagrees with frozen evaluation")
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "confirmation_energy_path.csv", energy_rows,
              ["time_s", "observed_energy_j", "predicted_energy_j", "covered_s"])
    write_csv(output / "confirmation_ap_path.csv", ap_rows,
              ["time_s", "block", "observed_ap_c", "predicted_ap_c"])
    summary = dict(status="partial_diagnostic_not_independent_validation",
                   completed_sessions=receipt["completed_sessions"],
                   attempted_sessions=receipt["session_attempts"],
                   development_sessions=len(development), confirmation_sessions=len(confirmation),
                   condition=stats["condition"], work_calls_completed=sum(s["work_calls"] for s in sessions),
                   confirmation_error=errors,
                   frozen_version=frozen["version"], whole_device_power_w=frozen["whole_device_power_w"],
                   ap_slope_at_30_c_per_s=frozen["ap_slope_at_30_c_per_s"],
                   ap_cooling_rate_per_s=frozen["ap_cooling_rate_per_s"],
                   ap_fit_rank=frozen["ap_fit_rank"],
                   ap_design_singular_ratio=frozen["ap_design_singular_ratio"],
                   ap_development_rmse_c_per_s=frozen["ap_development_rmse_c_per_s"],
                   initial_ap_development_range_c=frozen["initial_ap_development_range_c"],
                   ap_development_observed_range_c=frozen["ap_development_observed_range_c"],
                   confirmation_initial_ap_c=stats["start_ap_c"],
                   absolute_energy_accuracy_certified=False, experiment_ready=False)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot([r["time_s"] for r in energy_rows], [r["observed_energy_j"] for r in energy_rows], label="관측 (조건부 J)")
    axes[0].plot([r["time_s"] for r in energy_rows], [r["predicted_energy_j"] for r in energy_rows], label="개발 동결 모형", linestyle="--")
    axes[0].set_ylabel("기기 전체 누적 에너지 (J)")
    axes[0].legend()
    axes[1].plot([r["time_s"] for r in ap_rows], [r["observed_ap_c"] for r in ap_rows], label="AP 관측")
    axes[1].plot([r["time_s"] for r in ap_rows], [r["predicted_ap_c"] for r in ap_rows], label="개발 동결 모형", linestyle="--")
    axes[1].set_ylabel("AP 센서 (°C)")
    axes[1].set_xlabel("확인 DC_DG 공통창 시작 후 시간 (초)")
    axes[1].legend()
    fig.suptitle("COLLECT-05 중단 전 확인 1세션: 부분 진단 (독립 검증 아님)")
    fig.tight_layout()
    svg = output / "confirmation_path.svg"
    fig.savefig(svg, metadata={"Date": None})
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
                   encoding="utf-8")
    fig.savefig(output / "confirmation_path.png", dpi=150)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
