"""M7-A 정정 파생표 (2026-10-14, 조민규 답 10/14 §1 · §2 · §5 · 프롬프트 M8 준비 A부) — 원본 무변경 · 폰 0 · 계산 = 기술만 (J · 열 · 정책 비교 없음).

  py -3 -X utf8 s26/tools/mixreq/m7_derive_1014.py --results results --out s26/results/m7_1013/derived_1014

Reads (never writes) results\\S26_M7_* (device progress.jsonl · host session_log.json · hal.csv · validated.json), results\\S26_M7_HAL\\hal_cont_*.csv,
results\\S26_M7_runs.jsonl · S26_M7_driver_events.jsonl, s26/results/m7_1013/dev/tables/session_table_m7.csv and the M7 plans. Writes derived tables only:
  s_sessions_resolved.csv  S 8 시도 (S1~S5 · S6-C a1 실패 · a2 13:22 실패 · a2 13:38 추가 성공 · 조민규 01:5x #1 정정) = folder + command_id + device app start + host start 한 행씩 (session_id/attempt 로 묶지 않음) · registered_status · 소비 보존
  mixed_columns.md         기존 session_table_m7.csv · readout 21_C_a2 의 어느 열이 13:22 실패와 13:38 성공을 섞었는지 (고치지 않음 · 기록만)
  k_timeline.csv           K 9 + 준비 6: 같은 시계 (host epoch · device boottime = elapsedRealtime) 의 준비/K 경계 시각 + 차이 열 (조민규 216.6~219.5 · 251.5~253.8 · 91.8~92.7 대조)
  deviation_ledger.csv     46 실행 전부: 실제 시작 · 끝 시각 · NotificationShade · 시작 열 · 띠 · SOC (M7 하한 30 · 새 40~80 은 참고 열) · 충전 간격 · 재시도
  coverage_m7.csv          앱 power 첫/마지막 유효 표본 (common 기준) · 180 s 양측 표본 · 간격 · 결측 · host HAL/battery 첫/마지막 · AP35/AP180/I·V 0/180 양측 · 단위 · 부호 · 앱/host 분리
  provenance_m7.csv        세션마다 source commit · APK · 서명 · 계획 SHA · 매니페스트 SHA · 투영 SHA · 입력 목록 SHA · 빌드 · 설치 시각 · 원장 줄 번호
  derive_index.json        요약 · 조민규 값 대조 (기술만)
Clocks: device = progress.jsonl mono_ns (SystemClock.elapsedRealtimeNanos = CLOCK_BOOTTIME) = hal.csv device_boottime_s = hal_cont device_uptime_s (/proc/uptime);
host = PC epoch. host ↔ device offset per session = median(pc_ms/1000 − device_boottime_s) over the session's host/hal.csv rows (adb 읽기 지연 ≤ ~1 s 포함);
the M7 driver's "host start_time + mono offset" method is kept as a second column. 보간 0 · 추정 채움 0 (없으면 빈 칸).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402

REPO = HERE.parents[2]
PLAN_ROOT = REPO / "s26" / "results" / "m7_1013"
TABLE = PLAN_ROOT / "dev" / "tables" / "session_table_m7.csv"
FREEZE = PLAN_ROOT / "dev" / "docs" / "freeze_m7.txt"
SOURCE_COMMIT = "7ad2b18f27d97b5f40d84343fe9cecd616128bf5"
RESULT_COMMIT = "aaa7b87fca2d941746195ed8a9485758f57b484d"
APK_SHA = "878b10b7bc05300ddddc60fac0b2fb40eb020870841e473a8775827ef92bf092"
SIGNER_SHA = "6394e51f94c71bd6e9cc5d76ff66e503583c1dca7d50f7ed175dd2e444cfcd32"
BUILD_TIME = "2026-10-13T21:12:48+09:00 (깨끗한 빌드 1 · 작업 트리) / 21:4x (빌드 2 · 커밋 뒤 · 같은 SHA)"
INSTALL_TIME = "2026-10-13T21:45:30+09:00 (adb install -r · pm path sha256 = 빌드 SHA)"
APP_MAX_GAP_S = 2.5          # 앱 power_sample 양측 표본 허용 최대 간격 (900 ms 표본 · mixreq_readout our_integrate max_gap 2.5 s 와 같은 값 · 기술용)
HAL_MAX_GAP_S = 5.0          # host HAL (2.3 s 목표) 양측 표본 허용 최대 간격 (2 표본)
SOC_M7_MIN = 30              # M7 원기준 (영훈 결정 · SOC 하한 30 · 상한 없음)
SOC_NEW = (40, 80)           # 새 계약 (조민규 공통 계약) — 참고 열만 · 소급 적용 안 함
JO_REF = dict(last_available_to_k_app_start_s=(216.6, 219.5), last_available_to_k_common_s=(251.5, 253.8), runlog_end_to_k_app_start_s=(91.8, 92.7),
              p18_last_power_sample_s=(179.498, 179.930), app_180_both_sides="0/18", host_ap35_ap180_iv_0_180="18/18")


def jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []


def read_csv(p: Path) -> list[dict]:
    if not p.is_file():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def iso(epoch: float | None) -> str | None:
    return None if epoch is None else dt.datetime.fromtimestamp(epoch).isoformat(timespec="milliseconds")


def r3(x):
    return None if x is None else round(x, 3)


# ---------------------------------------------------------------------------------------------- device artefacts
class Session:
    """One result folder (device/ + host/ + validated.json). Everything is read; nothing is written."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.name = folder.name
        self.root = folder.parent.name
        self.host_log = C.read_json(folder / "host" / "session_log.json") if (folder / "host" / "session_log.json").is_file() else {}
        mp = folder / "device" / "manifest.json" if (folder / "device" / "manifest.json").is_file() else folder / "host" / "manifest_pushed.json"
        self.manifest = C.read_json(mp) if mp.is_file() else {}
        self.validated = C.read_json(folder / "validated.json") if (folder / "validated.json").is_file() else {}
        self.summary = C.read_json(folder / "device" / "summary.json") if (folder / "device" / "summary.json").is_file() else None
        self.cleanup = C.read_json(folder / "device" / "cleanup.json") if (folder / "device" / "cleanup.json").is_file() else None
        self.failure = C.read_json(folder / "device" / "session_failure.json") if (folder / "device" / "session_failure.json").is_file() else None
        self.requests = C.read_json(folder / "device" / "requests.json") if (folder / "device" / "requests.json").is_file() else None
        self.ev = self._events(folder / "device" / "progress.jsonl")
        self.hal = self._hal(folder / "host" / "hal.csv")
        self.offset = self._offset()

    @staticmethod
    def _events(p: Path) -> dict:
        out = dict(session_start=None, command_id=None, phase_start={}, phase_end={}, runtime_return=[], warmup_return=[], common_start=None, common_end=None,
                   arrivals=[], lane_available=[], power=[], app_cleanup=None, session_failed=None, first_event=None, last_event=None, kinds={})
        if not p.is_file():
            return out
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                k, t = e.get("kind"), e.get("mono_ns")
                if t is None:
                    continue
                t = int(t)
                out["kinds"][k] = out["kinds"].get(k, 0) + 1
                out["first_event"] = t if out["first_event"] is None else min(out["first_event"], t)
                out["last_event"] = t if out["last_event"] is None else max(out["last_event"], t)
                if k == "session_start":
                    out["session_start"] = t
                    out["command_id"] = e.get("command_id")
                elif k == "phase_start":
                    out["phase_start"].setdefault(e.get("phase"), t)
                elif k == "phase_end":
                    out["phase_end"][e.get("phase")] = t
                elif k == "runtime_return":
                    out["runtime_return"].append(t)
                elif k == "warmup_return":
                    out["warmup_return"].append(t)
                elif k == "common_start":
                    out["common_start"] = t
                elif k == "common_end":
                    out["common_end"] = t
                elif k == "arrival":
                    out["arrivals"].append(int(e.get("scheduled_arrival_ns") or t))
                elif k == "lane_available":
                    out["lane_available"].append(t)
                elif k == "power_sample":
                    out["power"].append(dict(t=t, current=e.get("current_raw"), current_valid=e.get("current_valid"), voltage=e.get("voltage_mV"),
                                             charge=e.get("charge_counter_raw"), level=e.get("battery_level"), bat=e.get("battery_temperature_deci_c"),
                                             plugged=e.get("plugged"), interactive=e.get("interactive")))
                elif k == "app_cleanup":
                    out["app_cleanup"] = t
                elif k == "session_failed":
                    out["session_failed"] = t
        return out

    @staticmethod
    def _hal(p: Path) -> list[dict]:
        rows = []
        for r in read_csv(p):
            pc, bt = num(r.get("pc_ms")), num(r.get("device_boottime_s"))
            rows.append(dict(host=pc / 1000.0 if pc is not None else None, boot=bt, SKIN=num(r.get("SKIN")), AP=num(r.get("AP")), BAT=num(r.get("BAT")),
                             status=r.get("thermal_status")))
        return rows

    def _offset(self) -> float | None:
        pairs = [r["host"] - r["boot"] for r in self.hal if r["host"] is not None and r["boot"] is not None]
        return statistics.median(pairs) if pairs else None

    # clocks
    def host_of(self, mono_ns: int | None) -> float | None:
        """device mono_ns → host epoch via the session hal.csv (pc_ms ↔ device_boottime_s) offset; hal.csv 가 비면 (앱 0.6 s 정지) 드라이버 방법으로."""
        if mono_ns is None:
            return None
        if self.offset is None:
            return self.host_of_driver_method(mono_ns)
        return mono_ns / 1e9 + self.offset

    def host_of_driver_method(self, mono_ns: int | None) -> float | None:
        """M7 driver method: host start_time + (mono − session_start mono)."""
        st = self.host_log.get("start_time")
        if mono_ns is None or not st or self.ev["session_start"] is None:
            return None
        return dt.datetime.fromisoformat(st).timestamp() + (mono_ns - self.ev["session_start"]) / 1e9

    def boot_s(self, mono_ns: int | None) -> float | None:
        return None if mono_ns is None else mono_ns / 1e9

    @property
    def common_start(self):
        return self.ev["common_start"]

    def rel(self, mono_ns: int | None) -> float | None:
        return None if (mono_ns is None or self.common_start is None) else (mono_ns - self.common_start) / 1e9


def hal_cont_rows(p: Path) -> list[dict]:
    rows = []
    for r in read_csv(p):
        ms, up = num(r.get("host_ms")), num(r.get("device_uptime_s"))
        rows.append(dict(host=ms / 1000.0 if ms is not None else None, boot=up, AP=num(r.get("AP")), SKIN=num(r.get("SKIN")), BAT=num(r.get("BAT")),
                         level=num(r.get("level")), current=num(r.get("current_now_uA")), voltage=num(r.get("voltage_mV")), err=r.get("err") or ""))
    return rows


def both_sides(times: list[float], t: float, max_gap: float) -> dict:
    """양측 표본: t 이전 마지막 표본 · t 이후 첫 표본이 둘 다 있고 두 표본 사이 ≤ max_gap. 보간 없음 — 유무와 간격만."""
    before = [x for x in times if x <= t]
    after = [x for x in times if x >= t]
    b = max(before) if before else None
    a = min(after) if after else None
    gap = (a - b) if (a is not None and b is not None) else None
    return dict(before=r3(b), after=r3(a), gap_s=r3(gap), ok=(gap is not None and gap <= max_gap))


# ---------------------------------------------------------------------------------------------- tables
def collect(results: Path) -> dict[str, Session]:
    out = {}
    for root in ("S26_M7_K", "S26_M7_P", "S26_M7_S", "S26_M7_SMOKE", "S26_M7_S7", "S26_M7_M6REPRO"):
        d = results / root
        if not d.is_dir():
            continue
        for folder in sorted(p for p in d.iterdir() if p.is_dir()):
            if (folder / "host" / "session_log.json").is_file() or (folder / "device").is_dir():
                out[f"{root}/{folder.name}"] = Session(folder)
    return out


def run_records(results: Path) -> tuple[list[dict], list[dict]]:
    return jsonl(results / "S26_M7_runs.jsonl"), jsonl(results / "S26_M7_driver_events.jsonl")


def table_rows() -> list[dict]:
    return [r for r in read_csv(TABLE) if r.get("cycle") == "m7"]


def s_sessions(sessions: dict[str, Session], runs: list[dict], events: list[dict]) -> list[dict]:
    """S 세션 8 시도 (조민규 01:5x #1: S1~S5 정상 5 + S6-C 3 = 8 · "7시도" 정정) — folder + command_id + device app start + host start 가 키. session_id/attempt 로 묶지 않는다."""
    rows = []
    ends = [r for r in runs if r.get("event") == "end"]
    starts = [r for r in runs if r.get("event") == "start"]
    for key, s in sorted(sessions.items()):
        if s.root != "S26_M7_S":
            continue
        m, hl = s.manifest, s.host_log
        host_start = hl.get("start_time")
        hs_epoch = dt.datetime.fromisoformat(host_start).timestamp() if host_start else None
        # run-log start/end bracketing this folder's host start (same index · attempt · nearest start ≤ host start)
        cands = [r for r in starts if r.get("index") == m.get("session_index") and r.get("attempt") == m.get("attempt") and hs_epoch and r["epoch"] <= hs_epoch + 1]
        rs = max(cands, key=lambda r: r["epoch"]) if cands else None
        re_ = next((r for r in ends if rs and r.get("label") == rs.get("label") and r.get("attempt") == rs.get("attempt") and r["epoch"] > rs["epoch"]), None)
        run_s = (re_["epoch"] - rs["epoch"]) if (rs and re_) else None
        app_run_s = ((s.ev["last_event"] - s.ev["first_event"]) / 1e9) if (s.ev["first_event"] is not None and s.ev["last_event"] is not None) else None
        counts = (s.validated.get("counts") or {})
        p = s.ev["power"]
        soc0 = p[0]["level"] if p else None
        soc1 = p[-1]["level"] if p else None
        la = max(s.ev["lane_available"]) if s.ev["lane_available"] else None
        svc = None
        if s.requests and all(r.get("terminal_status") == "succeeded" for r in s.requests):
            urg = sorted((r["output_ready_ns"] - r["scheduled_arrival_ns"]) / 1e6 for r in s.requests if r.get("priority") == "urgent" and r.get("output_ready_ns"))
            svc = C.nearest_rank_p95(urg, len(urg)) if urg else None
        label = "S6-C" if m.get("session_index") == 21 else f"S{m.get('session_index', 0) - 15}-{m.get('m6_letter', '')}"
        if m.get("session_index") == 21:
            if m.get("attempt") == 1:
                status, reason = "invalid_1", "a1: post-window drain incomplete (앱 정지 · succeeded 0 / unfinished 3000)"
            elif "screenoff" in s.name:
                status, reason = "invalid_2 (invalid_twice)", "a2 13:22: environment/screen_off 0.6 s after app start (runtime_setup · summary 없음)"
            else:
                status, reason = "extra_dev_outside_retry_limit", "a2 13:38 (같은 a2 자리 재사용 · 영훈 결정 · 등록 §4-5 재시도 1회 밖 · 민감도 자료 · 원 등록 S = 완료 5/6 + 실패 이력)"
        else:
            status, reason = "valid", ""
        stop_reason = (s.cleanup or {}).get("stop_reason") or (s.failure or {}).get("error")
        start_hal = next((r for r in s.hal if r["SKIN"] is not None), None)
        rows.append(dict(
            label=label, session_index=m.get("session_index"), attempt=m.get("attempt"), session_id=m.get("session_id"), folder=key,
            command_id=hl.get("command_id") or s.ev["command_id"], device_app_start_boot_s=r3(s.boot_s(s.ev["session_start"])),
            device_app_start_host=iso(s.host_of(s.ev["session_start"])), host_start=host_start, host_end=hl.get("end_time"),
            runlog_start=(rs or {}).get("t"), runlog_end=(re_ or {}).get("t"), runlog_rc=(re_ or {}).get("rc"),
            eligible=s.validated.get("eligible"), reasons=";".join(s.validated.get("reasons") or []), registered_status=status, status_reason=reason,
            failure_phase=(s.failure or {}).get("phase"), stop_reason=stop_reason, summary_present=s.summary is not None,
            succeeded=counts.get("succeeded"), unfinished=counts.get("unfinished"), failed=counts.get("failed"), planned=counts.get("planned"),
            urgent_p95_ms=r3(svc), last_lane_available_s=r3(s.rel(la)), common_start_boot_s=r3(s.boot_s(s.common_start)),
            start_SKIN=(start_hal or {}).get("SKIN"), start_AP=(start_hal or {}).get("AP"), start_BAT=(start_hal or {}).get("BAT"), start_SOC=soc0,
            gate_last=json.dumps((hl.get("gate") or {}).get("last"), ensure_ascii=False) if hl.get("gate") else None, clock_method=("session hal.csv offset" if s.offset is not None else "driver method (host start_time + mono offset)"),
            hal_rows=len(s.hal), hal_coverage_after_last_available_s=r3((max(r["host"] for r in s.hal if r["host"]) - s.host_of(la)) if (la and s.hal and s.offset) else None),
            runlog_run_s=r3(run_s), app_active_s=r3(app_run_s), soc_start=soc0, soc_end=soc1, soc_delta=(soc1 - soc0) if (soc0 is not None and soc1 is not None) else None,
            power_samples=len(p), consumption_note="실패도 실제 실행 시간 · SOC 차 보존 (삭제 · 0 소비 처리 안 함)",
            apk_sha256=hl.get("apk_sha256"), manifest_sha256=hl.get("manifest_sha256"),
        ))
    return rows


def mixed_columns(s_rows: list[dict]) -> str:
    """기존 session_table_m7.csv · readout 21_C_a2 · inventory 에서 13:22 (screenoff) 행이 13:38 값을 가진 열 — 기록만."""
    table = {r["folder"]: r for r in read_csv(TABLE) if r.get("label") == "S6-C"}
    ok = table.get("S26_M7_S/S26_MIXREQ_21_CPU_URGENT_ONLINE_V1_a2")
    so = table.get("S26_M7_S/S26_MIXREQ_21_CPU_URGENT_ONLINE_V1_a2_screenoff_1322")
    lines = ["# mixed_columns — S6-C a2 13:22 (screenoff) 와 13:38 (성공) 이 섞인 열 (조민규 §1 · 원본 고치지 않음 · 기록만)", "",
             "원인 (코드 사실): `S26_MIXREQ_21_…_a2_screenoff_1322\\validated.json` 은 폴더를 옆으로 옮기기 **전**에 쓰였고 `device_dir` 가 `…_a2\\device` (13:38 성공 폴더) 를 가리킨다.",
             "`mixreq_readout.read_session` 이 `validated.device_dir` 를 따라 13:38 의 device 산출물 (requests.json · summary · progress) 을 읽어 13:22 행에 넣었고, `m7_table.session_rows` 는 그 readout 과",
             "`start_band.jsonl` (label index21 · attempt 2 → 마지막 기록 = 13:38) · run log (같은 index · attempt 2 → 마지막 start) 를 attempt 로만 찾아 13:38 값을 13:22 행에 넣었다.",
             "`m6_readout` 은 세션 JSON 을 `21_C_a2.json` 한 이름으로 쓰므로 뒤에 처리된 screenoff 폴더 (folder 열만 13:22) 가 13:38 폴더의 JSON 을 덮어썼다 (readout_S26_M7_S/sessions/21_C_a2.json).", "",
             "| 열 | 13:22 행 값 (session_table_m7.csv) | 실제 13:22 (원시) | 비고 |", "|---|---|---|---|"]
    if ok and so:
        cases = [("start_time", "13:22:03 (host/session_log — 맞음)"), ("end_time", "13:22:05 (맞음)"),
                 ("start_SKIN", "27.0 (driver start_state 12:59:44) · 띠 마지막 폴 25.9 (13:22:00)"), ("start_AP", "25.2 / 23.7"), ("start_BAT", "24.4 / 22.7"), ("start_SOC", "75"),
                 ("band_result", "out_of_band_after_wait (13:22 띠 대기 끝 — 같음)"), ("previous_run", "S6-C a1 (11:05:09 끝)"), ("gap_s", "≈ 8,210 (11:05:09 → 13:21:59)"),
                 ("charge_end_to_start_s", "2,538.8 (12:39:44 분리 → 13:22:03)"), ("hal_cont_path", "같은 파일 이름 hal_cont_S6-C_a2.csv 에 12:59 ~ 13:22 구간이 이어 쓰임 (13:29 · 13:36 재시작 포함)"),
                 ("power_coverage_after_last_available_s", "null (lane_available 0)"), ("hal_coverage_after_last_available_s", "null"),
                 ("last_lane_available_s", "null (요청 0 dispatch)"), ("completed", "0"), ("urgent_p95_ms", "null"), ("normal_p95_ms", "null"), ("deadline_met", "null"),
                 ("focus_apps", "NotificationShade (phone_watch 13:22 — 맞음 · 화면 꺼짐)")]
        for col, actual in cases:
            v_so, v_ok = so.get(col, ""), ok.get(col, "")
            mixed = (v_so == v_ok and v_so != "") and col not in ("band_result",)
            lines.append(f"| {col} | {v_so} | {actual} | {'**섞임 (13:38 값)**' if mixed else '13:22 고유' if v_so != v_ok else '같은 값 (우연 · 섞임 아님)'} |")
    lines += ["", "readout_S26_M7_S/sessions/21_C_a2.json: `folder` 만 screenoff 폴더 · `service` (3000/3000 · 긴급 P95 451.25) · `last_lane_available_s` 710.51 · `energy` · `thermal` · `summary` · `validated_rules`(eligible false 는 screenoff) 가 13:38 device 산출물 — 한 파일에 두 시도가 섞임.",
              "readout_S26_M7_S/inventory.csv: index 21 attempt 2 행 2개 중 screenoff 행의 urgent_p95_ms · normal_p95_ms · deadline_met · completed · overlap_s · last_lane_available_s 가 13:38 값 (eligible False · reasons 는 13:22).",
              "", "정정 = `s_sessions_resolved.csv` (folder + command_id + device app start + host start 한 행씩 · 원시 두 폴더 그대로). 원본 CSV · readout · 폴더는 고치지 않았다."]
    return "\n".join(lines) + "\n"


def k_timeline(sessions: dict[str, Session], runs: list[dict], events: list[dict], results: Path) -> list[dict]:
    rows = []
    run_end = {}
    for r in runs:
        if r.get("event") == "end":
            run_end[(r.get("label"), r.get("attempt"))] = r
    kev = {(e.get("label"), e.get("attempt")): e for e in events if e.get("what") == "run_end" and e.get("run_kind") == "k"}
    pev = {(e.get("label"), e.get("attempt")): e for e in events if e.get("what") == "run_end" and e.get("run_kind") == "prep"}
    ksess = {s.manifest.get("session_index"): s for s in sessions.values() if s.root == "S26_M7_K" and s.manifest.get("experiment_id") == "S26-M6-K"}
    psess = {s.manifest.get("session_index"): s for s in sessions.values() if s.root == "S26_M7_K" and s.manifest.get("experiment_id") == "S26-M6-P"}
    for (label, att), e in sorted(kev.items(), key=lambda kv: kv[1]["epoch"]):
        k = ksess.get(e["index"])
        if k is None:
            continue
        cond = e.get("condition")
        hal_cont = hal_cont_rows(Path(e["hal_csv"])) if e.get("hal_csv") else []
        pairs = [r["host"] - r["boot"] for r in hal_cont if r["host"] and r["boot"]]
        cont_offset = statistics.median(pairs) if pairs else None
        row = dict(k_label=label, k_index=e["index"], k_attempt=att, condition=cond, set=e.get("set"), k_session_id=k.manifest.get("session_id"), k_folder=k.name,
                   clock_note="host = PC epoch · boot = 기기 elapsedRealtime/boottime s (progress mono_ns = hal device_boottime = hal_cont device_uptime)",
                   host_minus_boot_offset_k_hal_s=r3(k.offset), host_minus_boot_offset_hal_cont_s=r3(cont_offset))
        prep = None
        if cond in ("B", "C"):
            pe = pev.get((e.get("prep_label"), e.get("prep_attempt")))
            prep = psess.get(e.get("prep_index"))
            if prep is not None:
                pr = run_end.get((e.get("prep_label"), e.get("prep_attempt")))
                p_last_la = max(prep.ev["lane_available"]) if prep.ev["lane_available"] else None
                p_last_ps = max(x["t"] for x in prep.ev["power"]) if prep.ev["power"] else None
                row.update(prep_label=e.get("prep_label"), prep_index=e.get("prep_index"), prep_attempt=e.get("prep_attempt"), prep_session_id=prep.manifest.get("session_id"),
                           prep_folder=prep.name, prep_host_minus_boot_offset_s=r3(prep.offset),
                           prep_app_start_boot_s=r3(prep.boot_s(prep.ev["session_start"])), prep_app_start_host=iso(prep.host_of(prep.ev["session_start"])), prep_app_start_host_sessionlog=prep.host_log.get("start_time"),
                           prep_common_start_boot_s=r3(prep.boot_s(prep.common_start)), prep_common_start_host=iso(prep.host_of(prep.common_start)),
                           prep_last_available_boot_s=r3(prep.boot_s(p_last_la)), prep_last_available_host=iso(prep.host_of(p_last_la)),
                           prep_last_available_host_driver_method=iso((pe or {}).get("times", {}).get("last_lane_available_host_epoch") if pe else None),
                           prep_last_power_sample_boot_s=r3(prep.boot_s(p_last_ps)), prep_last_power_sample_host=iso(prep.host_of(p_last_ps)),
                           prep_runlog_end_host=(pr or {}).get("t"), prep_runlog_end_epoch=r3((pr or {}).get("epoch")),
                           prep_app_cleanup_boot_s=r3(prep.boot_s(prep.ev["app_cleanup"])), prep_app_cleanup_host=iso(prep.host_of(prep.ev["app_cleanup"])))
        k_rt_end = max(k.ev["runtime_return"]) if k.ev["runtime_return"] else None
        k_wu_end = max(k.ev["warmup_return"]) if k.ev["warmup_return"] else None
        k_bl_start = k.ev["phase_start"].get("resident_baseline")
        k_bl_end = k.ev["phase_end"].get("resident_baseline")
        k_first_ps = min(x["t"] for x in k.ev["power"]) if k.ev["power"] else None
        row.update(k_app_start_boot_s=r3(k.boot_s(k.ev["session_start"])), k_app_start_host=iso(k.host_of(k.ev["session_start"])), k_app_start_host_sessionlog=k.host_log.get("start_time"),
                   k_runtime_create_end_boot_s=r3(k.boot_s(k_rt_end)), k_runtime_create_end_host=iso(k.host_of(k_rt_end)),
                   k_warmup_end_boot_s=r3(k.boot_s(k_wu_end)), k_warmup_end_host=iso(k.host_of(k_wu_end)),
                   k_baseline_start_boot_s=r3(k.boot_s(k_bl_start)), k_baseline_end_boot_s=r3(k.boot_s(k_bl_end)), k_baseline_end_host=iso(k.host_of(k_bl_end)),
                   k_common_start_boot_s=r3(k.boot_s(k.common_start)), k_common_start_host=iso(k.host_of(k.common_start)),
                   k_first_power_sample_boot_s=r3(k.boot_s(k_first_ps)), k_runlog_end_host=(run_end.get((label, att)) or {}).get("t"))
        # differences on the device clock (same boottime axis — no host offset involved)
        if prep is not None:
            p_la = max(prep.ev["lane_available"]) if prep.ev["lane_available"] else None
            p_ps = max(x["t"] for x in prep.ev["power"]) if prep.ev["power"] else None
            d = lambda a, b: r3((b - a) / 1e9) if (a is not None and b is not None) else None  # noqa: E731
            row.update(last_available_to_k_app_start_s=d(p_la, k.ev["session_start"]), last_available_to_k_common_s=d(p_la, k.common_start),
                       runlog_end_to_k_app_start_s=r3(k.host_of(k.ev["session_start"]) - row["prep_runlog_end_epoch"]) if (row.get("prep_runlog_end_epoch") and k.offset) else None,
                       runlog_end_to_k_app_start_s_driver=(e.get("gap_prep_to_k") or {}).get("gap_s"),
                       prep_last_available_to_prep_runlog_end_s=r3(row["prep_runlog_end_epoch"] - prep.host_of(p_la)) if (row.get("prep_runlog_end_epoch") and prep.offset and p_la) else None,
                       power_gap_from_boot_s=r3(prep.boot_s(p_ps)), power_gap_to_boot_s=r3(k.boot_s(k_first_ps)), power_gap_s=d(p_ps, k_first_ps),
                       power_gap_note="앱 power_sample 공백 (준비 cooling 끝 → K 앱 시작) · 보간 0 · 호스트 hal_cont 만 연속")
            ref = JO_REF
            row.update(jo_last_available_to_k_app_start_in_range=(ref["last_available_to_k_app_start_s"][0] <= (row["last_available_to_k_app_start_s"] or -1) <= ref["last_available_to_k_app_start_s"][1]),
                       jo_last_available_to_k_common_in_range=(ref["last_available_to_k_common_s"][0] <= (row["last_available_to_k_common_s"] or -1) <= ref["last_available_to_k_common_s"][1]),
                       jo_runlog_end_to_k_app_start_in_range=(ref["runlog_end_to_k_app_start_s"][0] <= (row["runlog_end_to_k_app_start_s_driver"] or -1) <= ref["runlog_end_to_k_app_start_s"][1]))
        else:
            prev = e.get("previous_run") or {}
            checks = e.get("stable_checks") or []
            last_check = checks[-1] if checks else {}
            row.update(idle_from_prev_runlog_end_s=e.get("idle_s"), previous_run_label=prev.get("label"), previous_run_end=prev.get("t"), stable=e.get("stable"),
                       ap_slope_c_per_min=last_check.get("ap_slope_c_per_min"), skin_slope_c_per_min=last_check.get("skin_slope_c_per_min"), slope_samples=last_check.get("samples"),
                       power_gap_from_boot_s=None, power_gap_to_boot_s=r3(k.boot_s(k_first_ps)), power_gap_note="직전 실행 뒤 앱 없음 (유휴) · 보간 0")
        row["interpretation"] = "요청 0 ≠ 열입력 0 — 준비 부하 · 초기 열 · 시간대 · runtime 재생성/warmup 이 섞인 이력 관찰 (CPU/NPU 잔열만의 순수 비교 아님)"
        rows.append(row)
    return rows


def deviation(sessions: dict[str, Session], runs: list[dict], events: list[dict]) -> list[dict]:
    rows = []
    trows = {r["folder"]: r for r in table_rows()}
    run_end = {(r.get("label"), r.get("attempt")): r for r in runs if r.get("event") == "end"}
    for key, s in sorted(sessions.items(), key=lambda kv: kv[1].host_log.get("start_time") or ""):
        t = trows.get(key, {})
        m, hl = s.manifest, s.host_log
        st = hl.get("start_time")
        hour = dt.datetime.fromisoformat(st).hour if st else None
        p = s.ev["power"]
        soc0 = p[0]["level"] if p else num(t.get("start_SOC"))
        start_hal = next((r for r in s.hal if r["SKIN"] is not None), None)
        focus = t.get("focus_apps", "")
        rows.append(dict(
            label=t.get("label") or m.get("m6_run") or m.get("m7_label") or f"{m.get('m6_load')}-{m.get('m6_letter')}", kind=t.get("kind"), idx=m.get("session_index"), attempt=m.get("attempt"),
            folder=key, command_id=hl.get("command_id"), experiment_id=m.get("experiment_id"), role=m.get("role"), policy=m.get("policy"),
            start_actual=st, end_actual=hl.get("end_time"), start_hour_local=hour, halfday_label="쓰지 않음 (실제 시각만)",
            notification_shade=("NotificationShade" in focus), focus_apps=focus, focus_non_session_rows=t.get("focus_non_session_rows"),
            start_SKIN=(start_hal or {}).get("SKIN") if start_hal else t.get("start_SKIN"), start_AP=(start_hal or {}).get("AP") if start_hal else t.get("start_AP"),
            start_BAT=(start_hal or {}).get("BAT") if start_hal else t.get("start_BAT"), band_result=t.get("band_result"),
            start_SOC=soc0, soc_in_m7_band=(soc0 is not None and soc0 >= SOC_M7_MIN), soc_in_new_band_reference_only=(soc0 is not None and SOC_NEW[0] <= soc0 <= SOC_NEW[1]),
            soc_rule_note=f"M7 원기준 SOC ≥ {SOC_M7_MIN} (상한 없음) · 새 40~80 은 참고 열 · 소급 적용 안 함",
            charge_end_to_start_s=t.get("charge_end_to_start_s"), last_power_disconnected=t.get("last_power_disconnected"), in_block_charge=t.get("in_block_charge") or "False",
            retry=(m.get("attempt", 1) > 1), eligible=s.validated.get("eligible"), reasons=";".join(s.validated.get("reasons") or []),
            previous_run=t.get("previous_run"), gap_from_previous_s=t.get("gap_s"), stable=t.get("stable"), idle_s=t.get("idle_s"),
            runlog_rc=(run_end.get((t.get("label"), m.get("attempt"))) or {}).get("rc"),
            case_stand_wind=t.get("case_stand_wind"), room_c=t.get("room_c"), apk_sha256=hl.get("apk_sha256"),
        ))
    return rows


def coverage(sessions: dict[str, Session], events: list[dict]) -> list[dict]:
    rows = []
    hal_by = {}
    for e in events:   # key = (folder name, host start_time) — the screenoff and the 13:38 run share folder name/attempt, their host_start differs
        if e.get("what") == "run_end" and e.get("hal_csv") and (e.get("times") or {}).get("folder"):
            hal_by[(Path(e["times"]["folder"]).name, (e["times"] or {}).get("host_start"))] = e["hal_csv"]
    trows = {r["folder"]: r for r in table_rows()}
    for key, s in sorted(sessions.items()):
        t = trows.get(key, {})
        if t.get("kind") not in ("P", "PREP", "K", "S"):
            continue
        if s.common_start is None:
            rows.append(dict(label=t.get("label"), kind=t.get("kind"), idx=s.manifest.get("session_index"), attempt=s.manifest.get("attempt"), folder=key,
                             note="common_start 없음 (앱 정지) — 창 기준 coverage 없음 · 표본 수만", app_samples=len(s.ev["power"])))
            continue
        cs = s.common_start
        p = s.ev["power"]
        valid = [x for x in p if x.get("current_valid") is True and x.get("current") is not None]
        ts = [s.rel(x["t"]) for x in valid]
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        common_s = int(s.manifest.get("phases", {}).get("common_s") or 120)
        la = max(s.ev["lane_available"]) if s.ev["lane_available"] else None
        hal_csv = hal_by.get((s.name.replace("_screenoff_1322", ""), s.host_log.get("start_time")))
        cont = hal_cont_rows(Path(hal_csv)) if hal_csv else []
        pairs = [r["host"] - r["boot"] for r in cont if r["host"] and r["boot"]]
        cont_off = statistics.median(pairs) if pairs else None
        def cont_rel(r):
            return (r["boot"] - cs / 1e9) if r["boot"] is not None else None
        ap_ts = [cont_rel(r) for r in cont if r["AP"] is not None and r["boot"] is not None]
        iv_ts = [cont_rel(r) for r in cont if r["current"] is not None and r["voltage"] is not None and r["boot"] is not None]
        sess_hal_ts = [(r["boot"] - cs / 1e9) for r in s.hal if r["AP"] is not None and r["boot"] is not None]
        row = dict(label=t.get("label"), kind=t.get("kind"), idx=s.manifest.get("session_index"), attempt=s.manifest.get("attempt"), folder=key, common_s=common_s,
                   clock="common 기준 s (device boottime · 앱/host 같은 축 = 기기 /proc/uptime)",
                   app_unit="current_raw µA (BatteryManager CURRENT_NOW · 방전 음수) · charge_counter µAh · voltage mV · 900 ms 표본", app_sign_discharge_negative=all((x["current"] or 0) <= 0 for x in valid) if valid else None,
                   app_samples=len(p), app_valid_samples=len(valid), app_missing_samples=len(p) - len(valid),
                   app_first_valid_s=r3(ts[0]) if ts else None, app_last_valid_s=r3(ts[-1]) if ts else None,
                   app_sample_interval_median_s=r3(statistics.median(gaps)) if gaps else None, app_sample_gap_max_s=r3(max(gaps)) if gaps else None,
                   app_max_gap_allowed_s=APP_MAX_GAP_S)
        for name, tt in (("0", 0.0), ("120", float(common_s)), ("180", 180.0), ("35", 35.0)):
            b = both_sides(ts, tt, APP_MAX_GAP_S)
            row[f"app_{name}_before_s"], row[f"app_{name}_after_s"], row[f"app_{name}_both_sides"] = b["before"], b["after"], b["ok"]
        row.update(app_last_available_s=r3(s.rel(la)), app_coverage_after_last_available_s=r3(ts[-1] - s.rel(la)) if (ts and la) else None,
                   host_hal_cont_file=Path(hal_csv).name if hal_csv else None, host_unit="HAL ℃ 0.1 단위 (dumpsys thermalservice Current temperatures from HAL) · dumpsys battery current_now µA · voltage mV · 2.3 s 목표 · 갱신 시각 미제공",
                   host_hal_cont_rows=len(cont), host_hal_cont_err_rows=sum(1 for r in cont if r["err"]), host_ap_first_s=r3(min(ap_ts)) if ap_ts else None, host_ap_last_s=r3(max(ap_ts)) if ap_ts else None,
                   host_session_hal_first_s=r3(min(sess_hal_ts)) if sess_hal_ts else None, host_session_hal_last_s=r3(max(sess_hal_ts)) if sess_hal_ts else None,
                   host_max_gap_allowed_s=HAL_MAX_GAP_S, host_minus_boot_offset_s=r3(cont_off))
        for name, tt, src in (("ap35", 35.0, ap_ts), ("ap180", 180.0, ap_ts), ("iv0", 0.0, iv_ts), ("iv180", 180.0, iv_ts)):
            b = both_sides(src, tt, HAL_MAX_GAP_S)
            row[f"host_{name}_before_s"], row[f"host_{name}_after_s"], row[f"host_{name}_both_sides"] = b["before"], b["after"], b["ok"]
        row.update(app_host_separation="앱 power 와 host HAL/battery 는 따로 (이어붙임 0) · host J180 은 계산하지 않음 (조민규 몫)",
                   app_180_note="앱 power 는 cooling 60 s 로 끝나 180 s 양측 표본이 없으면 false (호스트 값으로 메우지 않음)")
        rows.append(row)
    return rows


def provenance(sessions: dict[str, Session]) -> list[dict]:
    rows = []
    freeze = FREEZE.read_text(encoding="utf-8").splitlines() if FREEZE.is_file() else []
    ln = {}
    for i, l in enumerate(freeze, 1):
        if "878b10b7" in l and "[앱 빌드" in l:
            ln.setdefault("build", i)
        if "[2단계-1 설치" in l:
            ln.setdefault("install", i)
        if "[빌드 재현]" in l:
            ln.setdefault("build2", i)
    plans = {}
    for d in ("plan_m7p", "plan_m7prep", "plan_m7k", "plan_m7s"):
        pd = PLAN_ROOT / d
        if (pd / "plan.json").is_file():
            plan = C.read_json(pd / "plan.json")
            plans[d] = dict(plan_sha256=(pd / "plan_sha256.txt").read_text(encoding="utf-8").strip(), device_inputs_sha256=C.sha256_file(pd / "device_inputs.json"),
                            sessions={e["session_id"]: e for e in plan["sessions"] + plan["smoke"]})
    trows = {r["folder"]: r for r in table_rows()}
    for key, s in sorted(sessions.items()):
        t = trows.get(key, {})
        sid = s.manifest.get("session_id")
        plan_name, entry = None, None
        for d, pl in plans.items():
            if sid in pl["sessions"]:
                plan_name, entry = d, pl["sessions"][sid]
                break
        rows.append(dict(label=t.get("label"), kind=t.get("kind"), idx=s.manifest.get("session_index"), attempt=s.manifest.get("attempt"), folder=key, session_id=sid,
                         source_commit=SOURCE_COMMIT, result_commit=RESULT_COMMIT, apk_sha256_session=s.host_log.get("apk_sha256"), apk_sha256_registered=APK_SHA,
                         apk_matches=(s.host_log.get("apk_sha256") == APK_SHA), signer_sha256=SIGNER_SHA, plan=plan_name, plan_sha256=(plans.get(plan_name) or {}).get("plan_sha256"),
                         manifest_sha256_plan=(entry or {}).get("manifest_sha256"), manifest_sha256_pushed=s.host_log.get("manifest_sha256"),
                         manifest_sha256_device=(s.summary or {}).get("manifest_sha256"), projection_sha256=(entry or {}).get("projection_sha256"),
                         device_inputs_sha256=(plans.get(plan_name) or {}).get("device_inputs_sha256"), registration_sha256=(s.manifest.get("registration") or {}).get("sha256"),
                         build_time=BUILD_TIME, install_time=INSTALL_TIME, ledger_line_build=ln.get("build"), ledger_line_build2=ln.get("build2"), ledger_line_install=ln.get("install"),
                         ledger_file="sim/out_m7/freeze_m7.txt (레포 사본 s26/results/m7_1013/dev/docs/freeze_m7.txt)",
                         zip_note="M7-A 전체 ZIP 0f094a92… 에 APK · 전체 소스 없음 (조민규 독립 재빌드 아직 아님) — APK 사본 results/m7_build/ (커밋 안 함) · 소스 = 커밋 7ad2b18f"))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=REPO / "results")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sessions = collect(args.results)
    runs, events = run_records(args.results)
    s_rows = s_sessions(sessions, runs, events)
    write_csv(args.out / "s_sessions_resolved.csv", list(s_rows[0].keys()), s_rows)
    (args.out / "mixed_columns.md").write_text(mixed_columns(s_rows), encoding="utf-8", newline="\n")
    k_rows = k_timeline(sessions, runs, events, args.results)
    k_fields = []
    for r in k_rows:
        for k in r:
            if k not in k_fields:
                k_fields.append(k)
    write_csv(args.out / "k_timeline.csv", k_fields, k_rows)
    d_rows = deviation(sessions, runs, events)
    write_csv(args.out / "deviation_ledger.csv", list(d_rows[0].keys()), d_rows)
    c_rows = coverage(sessions, events)
    c_fields = []
    for r in c_rows:
        for k in r:
            if k not in c_fields:
                c_fields.append(k)
    write_csv(args.out / "coverage_m7.csv", c_fields, c_rows)
    p_rows = provenance(sessions)
    write_csv(args.out / "provenance_m7.csv", list(p_rows[0].keys()), p_rows)
    p18 = [r for r in c_rows if r.get("kind") == "P"]
    k_bc = [r for r in k_rows if r.get("condition") in ("B", "C")]
    index = dict(
        schema="s26-m7-derived-1014-v1", source_table=str(TABLE.relative_to(REPO)), sessions_read=len(sessions), s_rows=len(s_rows), k_rows=len(k_rows), deviation_rows=len(d_rows),
        coverage_rows=len(c_rows), provenance_rows=len(p_rows), originals_modified=0,
        checks=dict(
            p18_last_valid_power_sample_s=dict(min=min(r["app_last_valid_s"] for r in p18), max=max(r["app_last_valid_s"] for r in p18), jo=JO_REF["p18_last_power_sample_s"]),
            p18_app_180_both_sides=f"{sum(1 for r in p18 if r['app_180_both_sides'])}/{len(p18)}", jo_app_180=JO_REF["app_180_both_sides"],
            p18_host_ap35=f"{sum(1 for r in p18 if r['host_ap35_both_sides'])}/{len(p18)}", p18_host_ap180=f"{sum(1 for r in p18 if r['host_ap180_both_sides'])}/{len(p18)}",
            p18_host_iv0=f"{sum(1 for r in p18 if r['host_iv0_both_sides'])}/{len(p18)}", p18_host_iv180=f"{sum(1 for r in p18 if r['host_iv180_both_sides'])}/{len(p18)}",
            jo_host="18/18 (AP35/180 · I/V 0/180)",
            k_bc_last_available_to_k_app_start_s=[r["last_available_to_k_app_start_s"] for r in k_bc], jo_range=JO_REF["last_available_to_k_app_start_s"],
            k_bc_last_available_to_k_common_s=[r["last_available_to_k_common_s"] for r in k_bc], jo_range_common=JO_REF["last_available_to_k_common_s"],
            k_bc_runlog_end_to_k_app_start_s_driver=[r["runlog_end_to_k_app_start_s_driver"] for r in k_bc], jo_range_runlog=JO_REF["runlog_end_to_k_app_start_s"],
            s6c_statuses={r["folder"]: r["registered_status"] for r in s_rows if r["session_index"] == 21}),
        note="기술만 · 원본 CSV · readout · 폴더 무변경 · 보간 0 · J/열/정책 비교 계산 0")
    C.write_json(args.out / "derive_index.json", index)
    print(json.dumps(index["checks"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
