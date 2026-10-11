"""Static follow-up: reads saved audit and fixed Git trees; no environment/fit/device calls."""
import argparse
import collections
import csv
import hashlib
import json
import statistics
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--prior-audit", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    prior = json.loads(a.prior_audit.read_text(encoding="utf-8"))
    a.out.mkdir(parents=True, exist_ok=True)
    roots = {name: a.workspace / ("s26-" + name) for name in prior["trees"]}
    receipts = []

    def git(root, *args):
        return subprocess.check_output(["git", *args], cwd=root)

    for name, root in roots.items():
        assert git(root, "rev-parse", "HEAD").decode().strip() == prior["trees"][name]["commit"]

    def local_receipt(root, path):
        relative = path.relative_to(root).as_posix()
        receipts.append(dict(tree=root.name, path=relative, bytes=path.stat().st_size,
                             sha256=digest(path), representation="local saved bytes"))

    def public_json(root, relative):
        raw = git(root, "show", "HEAD:" + relative)
        receipts.append(dict(tree=root.name, path=relative, bytes=len(raw),
                             sha256=hashlib.sha256(raw).hexdigest(), representation="Git blob bytes",
                             git_blob=git(root, "rev-parse", "HEAD:" + relative).decode().strip()))
        return json.loads(raw.decode("utf-8-sig"))

    inventory = []
    for s in prior["sessions"]:
        inventory.append(dict(path=s["path"], session=s["session"], experiment=s["experiment"],
                              original_role=s["role"], block=s["block"], pair=s["pair"], policy=s["policy"],
                              planned=s["planned"], journal_rows=s["journal_rows"],
                              requests_json_present=s["request_journal_present"],
                              original_validation_eligible=s["original_validation_eligible"],
                              prior_exact_adapter_pass=s["interval_adapter_pass"],
                              new_policy_eligible=False))
    assert len(inventory) == 69 and sum(s["journal_rows"] for s in inventory) == 48480
    table(a.out / "session_inventory.csv", inventory)

    mix = roots["mixreq"]
    base = mix / "s26/results/mixreq_1008"
    kinds = ["arrival", "dispatch", "request_start", "output_ready", "persist_complete", "worker_release", "lane_available"]
    failed = []
    for s in prior["sessions"]:
        if not (s["path"].startswith("R4S_blocks/") and not s["request_journal_present"]):
            continue
        folder = base / s["path"]
        manifest_path = folder / "device/manifest.json"
        progress_path = folder / "device/progress.jsonl"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        planned = {r["request_id"]: r for r in manifest["requests"]}
        assert len(planned) == len(manifest["requests"]) == 3000
        events = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()]
        assert len(events) == len({e["sequence"] for e in events})
        ids = {kind: [e["id"] for e in events if e["kind"] == kind] for kind in kinds}
        assert all(len(v) == len(set(v)) and set(v).issubset(planned) for v in ids.values())
        assert set(ids["arrival"]) == set(planned)
        assert all(set(ids[k]) == set(ids["dispatch"]) for k in kinds[2:])
        assert sum(e["kind"] == "session_failed" for e in events) == 1
        assert sum(e["kind"] == "app_cleanup" for e in events) == 1
        failure = public_json(mix, (folder / "device/session_failure.json").relative_to(mix).as_posix())
        assert "drain incomplete" in failure["error"]
        row = dict(path=s["path"], session=s["session"], planned=len(planned))
        row.update({k + "_unique_ids": len(ids[k]) for k in kinds})
        row.update(no_dispatch_observed=len(set(planned) - set(ids["dispatch"])),
                   observed_urgent_dispatch=sum(planned[i]["priority"] == "urgent" for i in ids["dispatch"]),
                   observed_normal_dispatch=sum(planned[i]["priority"] == "normal" for i in ids["dispatch"]),
                   session_failed_events=1, app_cleanup_events=1, original_eligible=False,
                   exact_journal_recovered=False, quality_revalidated=False, failure=failure["error"])
        failed.append(row)
        local_receipt(mix, manifest_path)
        local_receipt(mix, progress_path)
    assert [r["dispatch_unique_ids"] for r in failed] == [2800, 2830, 2839, 2842]
    assert sum(r["no_dispatch_observed"] for r in failed) == 689
    table(a.out / "failed_prefix.csv", failed)

    # EventLog event time follows row updates; measure differences only in a saved complete session.
    s = next(s for s in prior["sessions"] if s["path"] == "R4C_blocks/S26_MIXREQ_00_B2_PARALLEL_ONLINE_V1_a1")
    device = base / s["path"] / "device"
    rows = {r["request_id"]: r for r in json.loads((device / "requests.json").read_text(encoding="utf-8"))}
    mapping = dict(request_start="execution_start_ns", host_inference_start="host_inference_start_ns",
                   host_inference_return="host_inference_return_ns", output_ready="output_ready_ns",
                   persist_complete="persist_complete_ns", worker_release="worker_release_ns",
                   lane_available="lane_available_ns")
    differences = collections.defaultdict(list)
    for line in (device / "progress.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["kind"] in mapping and e.get("id") in rows:
            differences[e["kind"]].append(e["mono_ns"] - rows[e["id"]][mapping[e["kind"]]])
    deltas = []
    for kind, field in mapping.items():
        v = differences[kind]
        assert len(v) == len(rows) == 192
        deltas.append(dict(session_path=s["path"], progress_kind=kind, row_field=field, n=len(v),
                           min_ns=min(v), median_ns=statistics.median(v), max_ns=max(v),
                           meaning="progress mono_ns minus exact request row timestamp; one-session diagnostic"))
    table(a.out / "event_timestamp_deltas.csv", deltas)
    for path in (device / "requests.json", device / "progress.jsonl", mix / "request-runner/src/main/java/SessionEngine.kt"):
        local_receipt(mix, path)

    readout = public_json(mix, "s26/results/mixreq_1008/R4S_readout/readout.json")
    assert readout["sessions"] == 18 and len(readout["skipped"]) == 2
    public_presence = {}
    for name, root, relative in [
        ("R4S_files_inventory", mix, "s26/results/mixreq_1008/R4S_readout/files_inventory.csv"),
        ("R4S_driver_state", mix, "s26/results/mixreq_1008/R4S_blocks/driver_state_blockN.json"),
        ("Q20_CPU_outputs", roots["quality20"], "s26/results/quality20_1008/q20_1009a/CPU"),
        ("Q20_GPU_outputs", roots["quality20"], "s26/results/quality20_1008/q20_1009a/GPU"),
    ]:
        paths = git(root, "ls-tree", "-r", "--name-only", "HEAD", relative).decode().splitlines()
        public_presence[name] = dict(paths=len(paths), f32le_files=sum(x.endswith(".f32le") for x in paths))
        if name.startswith("Q20"):
            assert len(paths) == 21 and not any(x.endswith(".f32le") for x in paths)
        else:
            assert paths
    for root, relative in [(roots["quality20"], "quality-runner/src/main/java/Runtimes.kt"),
                           (mix, "request-runner/src/main/java/Runtimes.kt"),
                           (roots["quality20"], "s26/results/quality20_1008/q20_1009a/q20_judgement.md")]:
        path = root / relative
        if path.exists():
            local_receipt(root, path)

    verification = dict(task="S26-MATERIALS-PREP-01", base_repository_head="13137fb499990cd2b31dc9ede2c4a927690b745b",
                        fixed_trees=prior["trees"], prior_audit_sha256=digest(a.prior_audit),
                        analyzer_sha256=digest(__file__), existing_manifest_count=69, existing_exact_journal_rows=48480,
                        failed_attempt_count=4, failed_planned=12000, observed_return_ids=11311,
                        no_dispatch_observed=689, exact_journal_recovery=False, failed_original_judgement_preserved=True,
                        full_request_output_sha_audit=False, q20_binary_outputs_replayed=False,
                        failed_source_receipts=receipts, public_presence=public_presence,
                        skipped_preparation_stops=readout["skipped"],
                        new_learning=0, new_simulation_experiments=0, new_physical_fit=0,
                        apk_builds=0, installs=0, device_commands=0,
                        scope="static saved-data analysis only; not a rerun of native study or device validation")
    dump(a.out / "verification.json", verification)
    print(json.dumps({k: verification[k] for k in ("task", "existing_manifest_count", "existing_exact_journal_rows", "observed_return_ids", "no_dispatch_observed", "new_learning", "new_simulation_experiments", "device_commands")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
