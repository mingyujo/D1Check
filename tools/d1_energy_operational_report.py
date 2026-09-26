"""Small shareable tables/figure for the fixed CC_DG operational episodes."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tools.d1_energy_operational_sim import folder_for, identity, read, require


def rows_for(plan_path, run_root, evaluation):
    plan, _ = identity(plan_path, run_root)
    rows = []
    for entry in plan["entries"]:
        stats = read(folder_for(run_root, entry) / "validated.json")
        require(stats["status"] == "eligible_descriptive_only", "ineligible session")
        metrics = stats["metrics"]
        phase = stats["phases"]
        pred = (evaluation["outcomes"][entry["mode"]]["prediction"]
                if entry["phase"] == "confirmation" else None)
        rows.append(dict(block=entry["phase"], order=entry["index"] + 1,
            session_id=entry["session_id"], mode=entry["mode"],
            work_requests=stats["work_requests"],
            start_ap_c=phase["temperature_preparation"]["ap_start_c"],
            resident_idle_power_w_conditional=phase["resident_baseline"]["energy"]["mean_power_w"],
            work_completion_s=metrics["equal_work"]["duration_s"],
            work_energy_j_conditional=metrics["equal_work"]["full_energy_j"],
            common_window_energy_j_conditional=metrics["common_window"]["full_energy_j"],
            load_ap_peak_c=phase["load"]["ap_peak_c"],
            temperature_preparation_energy_j_conditional=phase["temperature_preparation"]["energy"]["full_energy_j"],
            resident_baseline_energy_j_conditional=phase["resident_baseline"]["energy"]["full_energy_j"],
            resident_cooling_energy_j_conditional=phase["resident_cooling"]["energy"]["full_energy_j"],
            predicted_work_completion_s=pred["work_completion_s"] if pred else "",
            predicted_work_energy_j_conditional=pred["work_energy_j_conditional"] if pred else "",
            predicted_common_energy_j_conditional=pred["common_window_energy_j_conditional"] if pred else "",
            predicted_load_ap_peak_c=pred["load_ap_peak_c"] if pred else ""))
    return rows


def write_report(plan_path, run_root, evaluation_path, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    evaluation = read(evaluation_path)
    require(evaluation["accuracy_pass"] is None, "unexpected validation claim")
    rows = rows_for(plan_path, run_root, evaluation)
    confirmation = {row["mode"]: row for row in rows if row["block"] == "confirmation"}
    for field, reported in (("work_completion_s", -126.319),
                            ("work_energy_j_conditional", -143.341),
                            ("common_window_energy_j_conditional", 4.559),
                            ("load_ap_peak_c", 1.9)):
        observed = confirmation["parallel"][field] - confirmation["serial"][field]
        require(abs(observed - reported) <= 0.0005,
                f"published confirmation contrast mismatch: {field}")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "comparison.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    panels = [
        ("work_completion_s", "Work completion (s)"),
        ("work_energy_j_conditional", "Energy to own completion (J*)"),
        ("common_window_energy_j_conditional", "Common 480 s energy (J*)"),
        ("load_ap_peak_c", "Peak AP during work (°C)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    colors = {"serial": "#2962a3", "parallel": "#d65a31"}
    for ax, (field, label) in zip(axes.flat, panels):
        for block_index, block in enumerate(("development", "confirmation")):
            for mode, offset in (("serial", -0.18), ("parallel", 0.18)):
                row = next(r for r in rows if r["block"] == block and r["mode"] == mode)
                ax.bar(block_index + offset, row[field], width=0.32,
                       color=colors[mode], label=mode if block_index == 0 else None)
        ax.set_xticks([0, 1], ["Dev", "Confirm"])
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.2)
    axes.flat[0].legend()
    fig.suptitle("A24 CC_DG fixed episode: serial vs parallel (one session/condition/block)\n"
                 "J*: whole-device, A24 current raw=mA hypothesis; descriptive, not causal.")
    fig.savefig(output / "tradeoff.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_report(args.plan, args.run, args.evaluation, args.output)


if __name__ == "__main__":
    main()
