"""A24 2차 zip 대조 (R2 1-2, 등록 §11-1 ①②) — S26 S1 warmup 출력 vs 조민규 2차 zip `S26_mixreq_handoff_1008` 의 기준 자료.

  py -3 -X utf8 s26/tools/mixreq/mixreq_a24_compare.py --s1 <S1 결과 폴더> --handoff local_inputs/a24_handoff_1008 --out <json>
  py -3 -X utf8 s26/tools/mixreq/mixreq_a24_compare.py --selftest

① 탐지 (주 판정, 등록 §11-1 ②): S26 `detection_CPU` warmup **2회 각각** vs `a24_reference/detection_cpu_warmup.json`
   `records[0].result.results` (실제 A24 첫 등록 세션의 탐지 CPU warmup) — `mixreq_validate.compare_detection`
   (A24 `d1_probe_compare` 허용: 개수 · 순서 · 라벨 같음 · |Δscore| ≤ 1e-3 · box ≤ 2 px). 하나라도 실패 = FAIL.
   기록만: S26 탐지 입력 텐서 SHA == A24 record 의 `input_tensor_sha256` (e1ce665b…) · S26 raw 출력 SHA (A24 raw SHA 와 같을 필요
   없음 — 엔진 다름) · 두 A24 record 가 같은지 · S26 warmup 각각 vs records[1].
② 분류 (등록 §11-1 ①): S26 `classification_CPU` warmup 1회차 top-5 vs `host_classification_reference/reference.json` 의
   `reference.results` (class_index · label · score — host CPU 1000개 출력에서 뽑은 top-5) — `mixreq_validate.compare_classification`
   (label · index 같음 · |Δscore| ≤ 1e-3). 기록만: 입력 텐서 603328d0… · 디코드 RGB ca6c2e2b… · raw 출력 SHA == reference 의 raw (0df3d535…).

S1 결과 읽기는 `mixreq_smoke.s1_checks` 와 같은 방법 (`mixreq_validate.load_session` · warmup.json 의 key/index/result) — 새로 해석하지 않는다.
출력 `{"a24_detection": PASS|FAIL, "classification": PASS|FAIL, "verdict": PASS|FAIL, ...}` · FAIL 이면 exit 1.
KPI · 응답 시간은 읽지 않는다 (warmup 출력과 SHA 만).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_validate as V  # noqa: E402

SCHEMA = "s26-mixreq-a24-compare-v1"
DET_WARMUP_FILE = "a24_reference/detection_cpu_warmup.json"
CLS_REFERENCE_FILE = "host_classification_reference/reference.json"
MANIFEST_FILE = "manifest.json"


# ----------------------------------------------------------------------------------------------- handoff (2차 zip)
def load_handoff(handoff: Path) -> dict:
    det = C.read_json(handoff / DET_WARMUP_FILE)
    cls = C.read_json(handoff / CLS_REFERENCE_FILE)
    manifest = C.read_json(handoff / MANIFEST_FILE) if (handoff / MANIFEST_FILE).is_file() else None
    records = det["records"]
    if len(records) < 1:
        raise SystemExit(f"{DET_WARMUP_FILE}: no records")
    cls_ref = cls.get("reference") or {}
    cls_results = cls_ref.get("results")
    cls_source = f"{CLS_REFERENCE_FILE} -> reference.results"
    if not cls_results:
        raise SystemExit(f"{CLS_REFERENCE_FILE}: reference.results not found — fall back to R1 reference_pc.json by hand (record that fact)")
    for row in cls_results:
        if not all(k in row for k in ("class_index", "label", "score")):
            raise SystemExit(f"{CLS_REFERENCE_FILE}: reference.results row lacks class_index/label/score: {row}")
    return dict(
        handoff=str(handoff),
        manifest_sha256=C.sha256_file(handoff / MANIFEST_FILE) if manifest else None,
        det_file_sha256=C.sha256_file(handoff / DET_WARMUP_FILE),
        cls_file_sha256=C.sha256_file(handoff / CLS_REFERENCE_FILE),
        det_role=det.get("role"), det_session_id=det.get("session_id"), det_experiment_id=det.get("experiment_id"),
        det_records=[r["result"] for r in records],
        cls_results=cls_results, cls_source=cls_source,
        cls_raw_output_sha256=cls_ref.get("raw_output_sha256"), cls_input_tensor_sha256=cls_ref.get("input_tensor_sha256"),
        cls_role=cls_ref.get("status"),
    )


# ----------------------------------------------------------------------------------------------- S1 (same method as mixreq_smoke.s1_checks)
def load_s1_warmups(folder: Path) -> dict[str, list]:
    device = folder / "device"
    if not (device / "warmup.json").is_file():
        raise SystemExit(f"{device / 'warmup.json'} missing (S1 artifacts not pulled?)")
    data = V.load_session(folder, device)
    by_key: dict[str, list] = {}
    for w in data["warmup"] or []:
        by_key.setdefault(w["key"], []).append(w)
    for k in by_key:
        by_key[k].sort(key=lambda w: w["index"])
    return by_key


# ----------------------------------------------------------------------------------------------- evaluation (pure)
def evaluate(by_key: dict[str, list], handoff: dict) -> dict:
    out = dict(schema=SCHEMA, handoff={k: v for k, v in handoff.items() if k not in ("det_records", "cls_results")},
               a24_detection=None, classification=None, verdict=None, detection=dict(), classification_detail=dict())
    # ---- ① detection: S26 detection_CPU warmup 0 and 1, each vs A24 records[0]
    a24_0 = handoff["det_records"][0]
    a24_1 = handoff["det_records"][1] if len(handoff["det_records"]) > 1 else None
    det = out["detection"]
    det["a24_reference"] = dict(results=a24_0["results"], input_tensor_sha256=a24_0.get("input_tensor_sha256"),
                                raw_output_sha256=a24_0.get("raw_output_sha256"), actual_backend=a24_0.get("actual_backend"))
    if a24_1 is not None:
        det["a24_records_identical"] = dict(decoded_within_tolerance=V.compare_detection(a24_0["results"], a24_1["results"])["passed"],
                                            decoded_bit_equal=a24_0["results"] == a24_1["results"],
                                            raw_sha_equal=a24_0.get("raw_output_sha256") == a24_1.get("raw_output_sha256"))
    s26_det = by_key.get("detection_CPU", [])
    det["s26_warmup_count"] = len(s26_det)
    det["per_warmup"] = []
    det_pass = len(s26_det) == C.WARMUPS_PER_KEY
    if not det_pass:
        det["error"] = f"detection_CPU warmups = {len(s26_det)} (expected {C.WARMUPS_PER_KEY})"
    for w in s26_det:
        r = w["result"]
        cmp0 = V.compare_detection(a24_0["results"], r["results"])
        entry = dict(index=w["index"], s26_results=r["results"], vs_a24_record0=cmp0,
                     s26_input_tensor_sha256=r.get("input_tensor_sha256"),
                     input_tensor_equals_a24=r.get("input_tensor_sha256") == a24_0.get("input_tensor_sha256"),
                     s26_raw_output_sha256=r.get("raw_output_sha256"),
                     raw_output_equals_a24=r.get("raw_output_sha256") == a24_0.get("raw_output_sha256"))
        if a24_1 is not None:
            entry["vs_a24_record1"] = V.compare_detection(a24_1["results"], r["results"])
        det["per_warmup"].append(entry)
        det_pass = det_pass and cmp0["passed"]
    out["a24_detection"] = "PASS" if det_pass else "FAIL"
    # ---- ② classification: S26 classification_CPU warmup 0 top-5 vs host reference top-5
    cls = out["classification_detail"]
    cls["reference"] = dict(source=handoff["cls_source"], results=handoff["cls_results"], raw_output_sha256=handoff.get("cls_raw_output_sha256"))
    s26_cls = by_key.get("classification_CPU", [])
    cls["s26_warmup_count"] = len(s26_cls)
    if not s26_cls:
        cls["error"] = "classification_CPU warmup 0 missing"
        cls_pass = False
    else:
        r0 = s26_cls[0]["result"]
        cmp = V.compare_classification(handoff["cls_results"], r0["results"])
        cls["s26_top5"] = r0["results"]
        cls["compare"] = cmp
        cls["s26_input_tensor_sha256"] = r0.get("input_tensor_sha256")
        cls["input_tensor_sha_603328d0"] = r0.get("input_tensor_sha256") == C.CLS_INPUT_TENSOR_SHA256
        cls["s26_decoded_rgb_sha256"] = r0.get("decoded_rgb_sha256")
        cls["decoded_rgb_sha_ca6c2e2b"] = r0.get("decoded_rgb_sha256") == C.RGB_SHA256
        raw = r0.get("raw_output_sha256")
        cls["s26_raw_output_sha256"] = raw
        cls["raw_output_equals_reference"] = (raw[0] if isinstance(raw, list) and raw else raw) == handoff.get("cls_raw_output_sha256")
        cls_pass = cmp["passed"] and len(r0["results"]) == 5
    out["classification"] = "PASS" if cls_pass else "FAIL"
    out["verdict"] = "PASS" if (det_pass and cls_pass) else "FAIL"
    out["note"] = ("판정 = ① 탐지 (S26 detection_CPU warmup 2회 각각 vs A24 실제 탐지 CPU warmup, A24 허용) · ② 분류 (S26 classification_CPU "
                   "warmup 1회차 top-5 vs host CPU 참조). 입력 텐서 · RGB · raw SHA 는 기록만. KPI 없음.")
    return out


# ----------------------------------------------------------------------------------------------- selftest
def _fake_handoff() -> dict:
    a24 = dict(results=[dict(label="person", score=0.6962101459503174, box=[372.135776826232, 24.47343933266307, 576.7281844497841, 321.4590852799534]),
                        dict(label="bicycle", score=0.5589990019798279, box=[-11.354641724794732, 12.291336479462991, 495.5273370370457, 470.6138081300607])],
               input_tensor_sha256="e1ce665bedf565285adccc4098433e338b9cdb08d681e0c0d424cae521e273ad",
               raw_output_sha256=["109e7e72", "018ddba6"], actual_backend="CPU")
    cls = [dict(class_index=518, label="crash helmet", score=0.21342213451862335), dict(class_index=671, label="mountain bike", score=0.11249527335166931),
           dict(class_index=535, label="disk brake", score=0.0572345145046711), dict(class_index=870, label="tricycle", score=0.05507273972034454),
           dict(class_index=665, label="moped", score=0.05448594316840172)]
    return dict(handoff="<selftest>", manifest_sha256=None, det_file_sha256=None, cls_file_sha256=None, det_role="selftest", det_session_id=None,
                det_experiment_id=None, det_records=[a24, copy.deepcopy(a24)], cls_results=cls, cls_source="<selftest>",
                cls_raw_output_sha256="0df3d535", cls_input_tensor_sha256=C.CLS_INPUT_TENSOR_SHA256, cls_role="selftest")


def _fake_s1(handoff: dict, det_mut=None, cls_mut=None) -> dict[str, list]:
    def det_entry(i):
        res = copy.deepcopy(handoff["det_records"][0]["results"])
        if det_mut:
            det_mut(res)
        return dict(key="detection_CPU", index=i, result=dict(results=res, input_tensor_sha256=handoff["det_records"][0]["input_tensor_sha256"],
                                                                raw_output_sha256=["s26raw0", "s26raw1"]))

    def cls_entry(i):
        res = copy.deepcopy(handoff["cls_results"])
        if cls_mut:
            cls_mut(res)
        return dict(key="classification_CPU", index=i, result=dict(results=res, input_tensor_sha256=C.CLS_INPUT_TENSOR_SHA256,
                                                                     decoded_rgb_sha256=C.RGB_SHA256, raw_output_sha256=["0df3d535"]))
    return {"detection_CPU": [det_entry(0), det_entry(1)], "classification_CPU": [cls_entry(0), cls_entry(1)]}


def selftest() -> int:
    handoff = _fake_handoff()
    failures = []

    def case(name, expected, det_mut=None, cls_mut=None, s1=None):
        got = evaluate(s1 or _fake_s1(handoff, det_mut, cls_mut), handoff)
        ok = got["verdict"] == expected
        print(f"  [{'ok' if ok else 'XX'}] {name}: verdict={got['verdict']} (expected {expected}) det={got['a24_detection']} cls={got['classification']}")
        if not ok:
            failures.append(name)
        return got

    def score_plus(res):
        res[0]["score"] += 2e-3

    def score_small(res):
        res[0]["score"] += 5e-4

    def box_plus(res):
        res[1]["box"][2] += 3.0

    def box_small(res):
        res[1]["box"][2] += 1.5

    def extra(res):
        res.append(dict(label="dog", score=0.51, box=[1.0, 2.0, 3.0, 4.0]))

    def fewer(res):
        res.pop()

    def relabel(res):
        res[0]["label"] = "dog"

    def swap(res):
        res[0], res[1] = res[1], res[0]

    def cls_swap(res):
        res[0], res[1] = res[1], res[0]

    def cls_score(res):
        res[2]["score"] += 2e-3

    def cls_index(res):
        res[3]["class_index"] = 871

    print("selftest: mixreq_a24_compare")
    base = case("A24 record as S26 output -> PASS", "PASS")
    assert base["detection"]["a24_records_identical"]["decoded_bit_equal"] is True
    case("detection score +2e-3 -> FAIL", "FAIL", det_mut=score_plus)
    case("detection score +5e-4 (within 1e-3) -> PASS", "PASS", det_mut=score_small)
    case("detection box +3 px -> FAIL", "FAIL", det_mut=box_plus)
    case("detection box +1.5 px (within 2 px) -> PASS", "PASS", det_mut=box_small)
    case("one extra detection -> FAIL", "FAIL", det_mut=extra)
    case("one fewer detection -> FAIL", "FAIL", det_mut=fewer)
    case("detection label changed -> FAIL", "FAIL", det_mut=relabel)
    case("detection order swapped -> FAIL", "FAIL", det_mut=swap)
    case("classification top-5 order swapped -> FAIL", "FAIL", cls_mut=cls_swap)
    case("classification score +2e-3 -> FAIL", "FAIL", cls_mut=cls_score)
    case("classification index changed -> FAIL", "FAIL", cls_mut=cls_index)
    # second warmup only differs -> FAIL (each of the two is judged)
    s1 = _fake_s1(handoff)
    s1["detection_CPU"][1]["result"]["results"][0]["score"] += 2e-3
    case("only detection warmup 2 differs -> FAIL", "FAIL", s1=s1)
    # missing warmup -> FAIL
    s1 = _fake_s1(handoff)
    s1["detection_CPU"] = s1["detection_CPU"][:1]
    case("only one detection warmup -> FAIL", "FAIL", s1=s1)
    s1 = _fake_s1(handoff)
    del s1["classification_CPU"]
    case("classification warmup missing -> FAIL", "FAIL", s1=s1)
    print("SELFTEST", "PASS" if not failures else f"FAIL {failures}")
    return 0 if not failures else 1


# ----------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--s1", type=Path, help="S1 result folder (results\\S26_MIXREQ_SMOKE_1009\\S26_MIXREQ_SMOKE_S1_warmup_only_blockN_a1)")
    ap.add_argument("--handoff", type=Path, help="local_inputs\\a24_handoff_1008 (조민규 2차 zip 풀어 둔 폴더)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not (args.s1 and args.handoff):
        ap.error("--s1 and --handoff are required (or --selftest)")
    handoff = load_handoff(args.handoff)
    by_key = load_s1_warmups(args.s1)
    result = evaluate(by_key, handoff)
    result["s1_folder"] = str(args.s1)
    if args.out:
        C.write_json(args.out, result)
    print(json.dumps({k: result[k] for k in ("schema", "a24_detection", "classification", "verdict")}, ensure_ascii=False))
    for e in result["detection"]["per_warmup"]:
        print(f"  detection warmup {e['index']}: vs A24 record0 passed={e['vs_a24_record0']['passed']} pairs={e['vs_a24_record0']['pairs']} "
              f"input_tensor_equals_a24={e['input_tensor_equals_a24']} raw_equals_a24={e['raw_output_equals_a24']}")
    cd = result["classification_detail"]
    if "compare" in cd:
        print(f"  classification warmup 0: passed={cd['compare']['passed']} pairs={cd['compare']['pairs']} tensor_603328d0={cd['input_tensor_sha_603328d0']} "
              f"rgb_ca6c2e2b={cd['decoded_rgb_sha_ca6c2e2b']} raw_equals_reference={cd['raw_output_equals_reference']}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
