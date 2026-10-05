"""Share the completed development subset beside the preserved partial block; PC only."""
import argparse
import csv
import json
from pathlib import Path


def share(previous, current, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    summaries = [("v4_partial", json.loads(Path(previous).read_text(encoding="utf-8"))),
                 ("v6_followup", json.loads(Path(current).read_text(encoding="utf-8")))]
    metrics = []
    for block, data in summaries:
        for s in data["sessions"]:
            activity = s["system_cpu_activity"]
            if activity is None:
                raise ValueError("CPU activity unavailable; never substitute zero")
            row = dict(block=block, condition=s["condition"], role=s["role"],
                       completed=s["completed"], start_ap_c=s["common_start_ap_c"],
                       observed_120s_j=s["observed_energy_j"], predicted_120s_j=s["predicted_energy_j"],
                       signed_error_j=s["signed_energy_error_j"], ap_mae_c=s["ap_scores"]["mae_c"],
                       ap_max_error_c=s["ap_scores"]["max_absolute_error_c"],
                       ap_score_start_s=s["ap_score_window_s"][0], ap_score_end_s=s["ap_score_window_s"][1],
                       parallel_s=s["state_seconds"].get("classification_GPU+detection_CPU", 0),
                       initial_in_original_range=s["initial_in_original_development_range"],
                       independent_validation=False, accuracy_pass=None)
            for key in ("benchmark", "tracer", "other", "unknown", "idle"):
                row[key+"_cpu_s"] = sum(b[key+"_cpu_seconds"] for b in activity["bins"])
            metrics.append(row)
    with (output/"metrics.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(metrics[0])); w.writeheader(); w.writerows(metrics)
    (output/"combined_summary.json").write_text(json.dumps(dict(
        status="separate_development_blocks_descriptive_only", previous_block_completed=False,
        current_block_completed=True, original_block_denominator=4,
        completed_eligible_sessions=4, blocks={k:v for k,v in summaries},
        coefficient_fit=False, independent_confirmation_sessions=0,
        experiment_ready=False), indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4, 3, figsize=(14, 11), constrained_layout=True)
    offset = 0
    for block, path in [("v4_partial", previous), ("v6_followup", current)]:
        base = Path(path).parent
        energy = list(csv.DictReader((base/"energy_paths.csv").open(encoding="utf-8")))
        ap = list(csv.DictReader((base/"ap_paths.csv").open(encoding="utf-8")))
        for s in dict(summaries)[block]["sessions"]:
            er = [r for r in energy if r["condition"] == s["condition"]]
            ar = [r for r in ap if r["condition"] == s["condition"]]
            for ax in axes[offset]:
                ax.set_title(block+" / "+s["condition"]); ax.grid(alpha=.2); ax.set_xlabel("Common-origin seconds")
            for key, label in [("observed_j", "Observed"), ("predicted_j", "Conditional prediction")]:
                axes[offset, 0].plot([float(r["common_s"]) for r in er], [float(r[key]) for r in er], label=label)
            for key, label in [("observed_ap_c", "Observed"), ("predicted_ap_c", "Conditional prediction")]:
                axes[offset, 1].plot([float(r["common_s"]) for r in ar], [float(r[key]) for r in ar], label=label)
            bins = s["system_cpu_activity"]["bins"]
            for key in ("benchmark", "tracer", "other"):
                axes[offset, 2].plot([b["start_s"] for b in bins], [b[key+"_cpu_seconds"] for b in bins], label=key)
            axes[offset, 0].set_ylabel("Cumulative energy J"); axes[offset, 1].set_ylabel("AP C")
            axes[offset, 2].set_ylabel("CPU seconds / 5-second bin")
            for ax in axes[offset]: ax.legend(fontsize=8)
            offset += 1
    fig.suptitle("Separate development blocks; conditional/extrapolation; no accuracy PASS")
    fig.savefig(output/"paths.png", dpi=120); plt.close(fig)
    return metrics


if __name__ == "__main__":
    q = argparse.ArgumentParser(description=__doc__)
    for key in ("previous", "current", "output"): q.add_argument("--"+key, required=True)
    a = q.parse_args(); share(a.previous, a.current, a.output)
