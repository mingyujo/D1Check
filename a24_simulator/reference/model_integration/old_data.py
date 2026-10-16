"""A24 historical sensor projections and raw-lineage ledger, never a fit.

SOURCE ONLY preparation. Import has no reads, fitting or device side effects.
All older confirmation data are development here. Native raw, validated sensor
projections and previously fitted predictions have distinct provenance classes.
"""
from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "A24_INTEGRATED_SESSION_V1"
PREPARATION = "OLD_THERMAL_SOURCE_PREPARATION.json"
CORE_FIELDS = ("pre", "q", "ap", "actual", "power_t", "power_w", "last_lane_s")
RECIPES = (
    ("native_macro", "work/repo/docs/results/resident_identification_run_01/recorded_v3/inputs.json.gz"),
    ("old_archive", "work/repo/docs/results/model_refinement_01/inputs.json.gz"),
    ("history_archive", "work/repo/docs/results/history_model_refinement_01/inputs.json.gz"),
    ("long_tail", "work/repo/docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz"),
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _read(path):
    path = Path(path)
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8-sig"))


def required_paths(base):
    """Exact saved-input roster; no globbing into new intake/archive payloads."""
    prep = _read(Path(__file__).with_name(PREPARATION))
    return [Path(base) / row["path"] for row in prep["source_pins"]]


def inventory(base):
    """Check existing preparation pins and return the declared member ledger."""
    base = Path(base)
    prep = _read(Path(__file__).with_name(PREPARATION))
    pins = []
    for row in prep["source_pins"]:
        path = base / row["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != row["sha256"]:
            raise ValueError("historical source SHA mismatch: " + row["path"])
        pins.append(dict(row, actual_sha256=actual))
    return dict(schema="A24_OLD_SOURCE_INVENTORY_V1", source_pins=pins,
                sessions=copy.deepcopy(prep["session_inventory"]),
                raw_member_ledgers=copy.deepcopy(prep["raw_member_ledgers"]),
                compatibility=copy.deepcopy(prep["compatibility"]),
                status="PINS_CHECKED_NATIVE_MEMBER_BYTES_NOT_IMPLIED")


def _cohort(case):
    cid = case["id"]
    if cid.startswith("session_"):
        return "macro"
    if "LONG" in cid:
        return "long_idle"
    if "_180_" in cid:
        return "history180"
    if "_30_" in cid:
        return "history30"
    return "old_short"


def _finite(value):
    return value is not None and not isinstance(value, bool) and math.isfinite(float(value))


def _observations(pre, times, values, source_path, source_sha):
    if len(times) != len(values):
        raise ValueError("historical AP time/value length mismatch")
    rows = []
    for row in pre:
        if not _finite(row.get("ap")):
            continue
        rows.append(dict(t_s=float(row["t"]), ap_c=float(row["ap"]), channel="AP",
                         lo_s=row.get("lo"), hi_s=row.get("hi"),
                         initial_eligible=True, provenance_class="validated_sensor_projection"))
    for t, value in zip(times, values):
        rows.append(dict(t_s=float(t), ap_c=float(value) if _finite(value) else None,
                         channel="AP", lo_s=None, hi_s=None, initial_eligible=False,
                         provenance_class="validated_sensor_projection"))
    unique = {}
    for row in rows:
        key = row["t_s"]
        if key in unique:
            if unique[key]["ap_c"] != row["ap_c"]:
                raise ValueError("historical duplicate AP timestamp conflict")
            unique[key]["initial_eligible"] |= row["initial_eligible"]
            continue
        row.update(source_path=source_path, source_sha256=source_sha)
        unique[key] = row
    return [unique[key] for key in sorted(unique)]


def _normalize(case, source, source_sha, recipe, native_audit):
    cohort = _cohort(case)
    obs = _observations(case.get("pre", []), case["q"], case["ap"], source, source_sha)
    pre = [r for r in obs if r["initial_eligible"] and r["hi_s"] is not None and
           float(r["hi_s"]) < min(case["q"], default=math.inf)]
    initial = max(pre, key=lambda r: r["t_s"]) if pre else None
    intervals = copy.deepcopy(case["actual"])
    for row in intervals:
        row["state"] = "+".join(sorted(row["state"].replace(":", "_").split("+")))
    audit = native_audit.get(case["id"])
    # An audited core identity permits pooling only the explicitly audited cases.
    # Unreviewed archives stay in separate domains, never inferred equal to M8.
    domain = ("old-native13:" + audit["core_canonical_sha256"] if audit else
              "old-unverified:" + recipe + ":" + cohort)
    identity_fields = {key: case.get(key) for key in CORE_FIELDS}
    return dict(schema=SCHEMA, device="A24", session_id="A24_" + case["id"],
                cohort_id="old:" + cohort, source_family="old", source_generation=recipe,
                original_role=case.get("role"), role="PREVIOUSLY_SEEN_DEVELOPMENT",
                observations=obs, initial_ap_c=initial["ap_c"] if initial else None,
                initial_ap_time_s=initial["t_s"] if initial else None,
                initial_ap_hi_s=initial["hi_s"] if initial else None,
                forecast_origin_s=max(35., float(initial["hi_s"])) if initial else 35.,
                prehistory_start_s=min((r["t_s"] for r in pre), default=None),
                owner_intervals=[], state_intervals=intervals, requests=[],
                activity_coverage_s=[intervals[0]["start_s"], intervals[-1]["end_s"]],
                preconditioning_activity_coverage="UNKNOWN_NOT_ZERO",
                protocol="historical_validated_projection:" + recipe,
                compatibility=dict(ap_target="OLD_HOST_AP_VALIDATED_PROJECTION",
                                   ap_sensor_contract_qualified=False,
                                   sensor_path_expected="thermalservice Current temperatures from HAL",
                                   sensor_path_limit="legacy parser whole-text fallback if HAL section absent; mType not checked",
                                   ap_activity_domain=domain,
                                   activity_pool_qualified=bool(audit),
                                   within_domain_exploratory=not bool(audit),
                                   M8_activity_pool_qualified=False,
                                   core_audit=copy.deepcopy(audit)),
                target_eligibility=dict(ap_fit=bool(initial and obs), timing_fit=False,
                                        measured_energy_fit=False,
                                        reason="conditional AP development only; raw clocks/sensors/version remain ledgered"),
                provenance=dict(source_path=source, source_sha256=source_sha,
                                projection_content_sha256=_digest(identity_fields),
                                native_session_id=None, native_member_bytes_verified=False,
                                input_model_runtime_signature="UNKNOWN_UNLESS_CORE_AUDIT_PRESENT"),
                legacy_power=dict(t_s=case.get("power_t", []),
                                  gauge_conditional_values=case.get("power_w", []),
                                  historical_pre_w=case.get("pre_w"),
                                  measured_j=None, units_currently_qualified=False),
                coverage=dict(AP_s=[obs[0]["t_s"], obs[-1]["t_s"]] if obs else None,
                              AP_post_s=[min(case["q"]), max(case["q"])],
                              full_projected_window_retained=True,
                              native_raw_full_window_verified=False))


def _abba(base, native_audit):
    """Recover all recorded AP CSV rows, including after the old 180 s plot."""
    folder = Path(base) / "work/repo/docs/results/overnight_device_20261011"
    path = folder / "AP_curve.csv"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        ap = list(csv.DictReader(stream))
    with (folder / "requests.csv").open(encoding="utf-8-sig", newline="") as stream:
        requests = list(csv.DictReader(stream))
    prepared = _read(Path(base) / "outputs/EXISTING-DATA-DYNAMICS-35/THERMAL_PREPARED.json")
    result = []
    for index in range(4):
        c = next(r for r in prepared if r.get("identity") == "A24_ABBA_" + str(index))
        public = c["input"]["initial_public_state"]
        points = [r for r in ap if int(r["index"]) == index]
        times = [float(r["elapsed_s"]) for r in points]
        values = [float(r["ap_c"]) for r in points]
        pre = [dict(t=t, ap=v, lo=None, hi=None) for t, v in zip(times, values)
               if t <= float(public["anchor_s"])]
        # The summary preserves the latest completed actual pre-read bracket.
        if pre:
            pre[-1]["hi"] = float(public["input_end_s"])
        post = [(t, v) for t, v in zip(times, values) if t >= 35.]
        case = dict(id="ABBA_" + str(index), pre=pre,
                    q=[t for t, _ in post], ap=[v for _, v in post],
                    actual=c["intervals"], role="previously_seen_confirmation")
        session = _normalize(case, str(path), sha, "ABBA_saved_raw_csv", native_audit)
        session["cohort_id"] = "old:ABBA"
        session["forecast_origin_s"] = 35.
        # Preserve every original AP point while only completed pre-read rows
        # are eligible to initialize a future counterfactual prediction.
        session["observations"] = [dict(t_s=t, ap_c=v, channel="AP", lo_s=None,
                                        hi_s=float(public["input_end_s"]) if pre and t == pre[-1]["t"] else None,
                                        initial_eligible=bool(pre and t <= pre[-1]["t"]),
                                        source_path=str(path), source_sha256=sha,
                                        provenance_class="saved_AP_sensor_CSV")
                                   for t, v in zip(times, values)]
        session["coverage"]["AP_s"] = [min(times), max(times)]
        owners = []
        for ordinal, row in enumerate(r for r in requests if int(r["index"]) == index):
            owners.append(dict(start_s=float(row["dispatch_ms"]) / 1000,
                               end_s=float(row["lane_available_ms"]) / 1000,
                               task={"classification": "C", "detection": "D"}[row["task_id"]],
                               route=row["backend"], request_id="ABBA_CSV_ORDINAL_" + str(ordinal),
                               request_id_is_projection_ordinal=True))
        session["owner_intervals"] = owners
        session["state_intervals"] = []
        session["activity_coverage_s"] = [0., max(times)]
        session["provenance"]["native_member_bytes_verified"] = False
        session["compatibility"]["ap_activity_domain"] = "old:ABBA:unverified_core"
        session["compatibility"]["within_domain_exploratory"] = True
        result.append(session)
    return result


def _resolve_members(ledger, aliases):
    resolved = []
    for entry in ledger:
        alias = entry.get("raw_root_alias") or entry.get("external_root_alias") or entry["inventory_path"]
        root = Path(aliases[alias]).resolve() if alias in aliases else None
        for member in entry["members"]:
            path = (root / member["member_path"]).resolve() if root else None
            if path and not path.is_relative_to(root):
                raise ValueError("raw member escaped explicit alias root")
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path and path.is_file() else None
            expected = member["declared_sha256"]
            if actual is not None and actual != expected:
                raise ValueError("native raw SHA mismatch: " + str(path))
            # Declaration ledgers already contain local_raw_bytes_reverified.
            # Update that field explicitly rather than passing duplicate kwargs.
            resolved.append({**member, "alias": alias, "resolved_path": str(path) if path else None,
                             "actual_sha256": actual, "local_raw_bytes_reverified": actual is not None})
    return resolved


def extract(base, raw_root_aliases=None):
    """Read pinned historical inputs; all original sessions/exclusions survive.

    raw_root_aliases resolves exact inventory names only. It never scans disks,
    downloads, opens new intake ZIPs, or silently claims full native recovery.
    Native conditioning rows require their own clock/owner parser before use;
    hash recovery alone does not insert them into the thermal activity history.
    """
    base = Path(base)
    inv = inventory(base)
    audit = {row["case_id"]: row for row in inv["compatibility"]["native13_case_metadata"]}
    merged, duplicates = {}, []
    for recipe, relative in RECIPES:
        path = base / relative
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        for case in _read(path):
            key = case["id"]
            if key in merged:
                previous = merged[key]
                if any(case.get(k) != previous["case"].get(k) for k in CORE_FIELDS):
                    raise ValueError("duplicate historical session content conflict: " + key)
                previous["aliases"].append(dict(path=str(path), sha256=sha, recipe=recipe))
                duplicates.append(dict(session_id=key, duplicate_source=str(path), kind="identical_projection"))
                continue
            merged[key] = dict(case=case, recipe=recipe, path=str(path), sha=sha,
                               aliases=[dict(path=str(path), sha256=sha, recipe=recipe)])
    sessions = []
    for entry in merged.values():
        session = _normalize(entry["case"], entry["path"], entry["sha"], entry["recipe"], audit)
        session["provenance"]["projection_aliases"] = entry["aliases"]
        sessions.append(session)
    sessions.extend(_abba(base, audit))
    if len(sessions) != 39 or len({s["session_id"] for s in sessions}) != 39:
        raise ValueError("registered historical 39 observed-session roster drift")
    prepared = _read(base / "outputs/EXISTING-DATA-DYNAMICS-35/THERMAL_PREPARED.json")
    previous = {r["identity"]: r for r in prepared if r.get("device") == "A24"}
    for session in sessions:
        prior = previous[session["session_id"]]
        session["historical_saved_AP_prediction"] = dict(
            t_s=prior["times"], ap_c=prior["old_prediction"],
            role="PREVIOUSLY_FITTED_SAVED_DESCRIPTIVE_COMPARATOR",
            same_initial_boundary_as_new_model=False, fresh_validation=False)
    native_summary = _read(base / "work/repo/docs/results/resident_identification_run_01/recorded_v3/summary.json")
    exclusions = [dict(source_family="old", session_alias=r["session"], status=r["status"],
                       target="ALL", use="UNATTEMPTED_LEDGER_ONLY", AP_c=None)
                  for r in native_summary["sessions"] if r.get("status") == "unattempted"]
    members = _resolve_members(inv["raw_member_ledgers"], raw_root_aliases or {})
    return dict(schema="A24_OLD_DATASET_V1", sessions=sessions, source_inventory=inv,
                raw_members=members, duplicates=duplicates, exclusions=exclusions,
                status="SEEN_SENSOR_PROJECTIONS_EXTRACTED_NATIVE_COMPLETENESS_NOT_ASSUMED",
                observation_count=len(sessions), planned_unattempted_count=len(exclusions),
                full_native_prehistory_recovered=False, fresh_confirmation=False,
                measured_j=None, S26_coefficients_or_raw_used=False)
