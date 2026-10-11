"""M5 Q1 · Q2 · Q3 host tests (no phone): am start translation · Q3 rule edges (등록 §3 Q3) · Q2 comparison on synthetic files.

  py -3 -m pytest -q s26/tools/quality20/test_m5_quality.py
"""
from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m5_quality as M  # noqa: E402
import q20_common as QC  # noqa: E402


def softmax(seed: int, jitter: float = 0.0) -> list[float]:
    raw = [((i * 7919 + seed * 104729) % 1000) / 1000.0 for i in range(1000)]
    for k, v in enumerate((5.0, 4.0, 3.5, 3.0, 2.5)):
        raw[(seed * (2 * k + 1) + k) % 1000] = v
    e = [math.exp(x) for x in raw]
    s = sum(e)
    return [struct.unpack("<f", struct.pack("<f", x / s + jitter * ((i % 3) - 1)))[0] for i, x in enumerate(e)]


SAMPLES = [(i, "%016x" % (0x1000 + i)) for i in range(20)]


def test_am_start_translation():
    argv = ["shell", "am", "start", "-W", "-n", "x/.Y", "--es", "d1_q20_manifest", "/q20.json", "--es", "d1_q20_backend", "GPU", "--es", "d1_q20_run_id", "r1"]
    q1 = M.rewrite_am_start(argv, "q1", "/q1.json", None)
    assert q1 == ["shell", "am", "start", "-W", "-n", "x/.Y", "--es", "d1_q1_manifest", "/q1.json", "--es", "d1_q1_backend", "GPU", "--es", "d1_q1_run_id", "r1"]
    q2 = M.rewrite_am_start(argv, "q2", None, "NONE")
    assert q2 == argv + ["--es", "d1_q2_gpu_precision", "NONE"]
    assert M.rewrite_am_start(["shell", "ls"], "q1", "/q1.json", None) == ["shell", "ls"]


def test_q3_rule_edges():
    cpu = {sid: softmax(i + 1) for i, sid in SAMPLES}
    same = {sid: softmax(i + 1, 1e-6) for i, sid in SAMPLES}
    r = M.q3(SAMPLES, same, cpu)
    assert r["verdict"] == M.Q3_PASS and r["top1_same"] == 20 and r["top5_set_same"] == 20 and r["cosine_ge_min"] == 20
    # one image's top-1 differs -> 불합격
    bad = dict(same)
    sid0 = SAMPLES[0][1]
    v = list(cpu[sid0])
    i1, i2 = QC.topk(v)[0][0], QC.topk(v)[1][0]
    v[i1], v[i2] = v[i2], v[i1]
    bad[sid0] = v
    assert M.q3(SAMPLES, bad, cpu)["verdict"] == M.Q3_FAIL
    # one missing image -> 불합격 (20장 전부 조건)
    miss = dict(same)
    miss[SAMPLES[3][1]] = None
    assert M.q3(SAMPLES, miss, cpu)["verdict"] == M.Q3_FAIL
    # top-5 set differs on exactly one image (top-1 kept) -> still 합격 (≥ 19/20) if cosine holds
    one = dict(same)
    sid1 = SAMPLES[1][1]
    w = list(cpu[sid1])
    t = QC.topk(w, 6)
    w[t[4][0]], w[t[5][0]] = w[t[5][0]], w[t[4][0]]
    one[sid1] = w
    r1 = M.q3(SAMPLES, one, cpu)
    assert r1["top5_set_same"] == 19 and r1["top1_same"] == 20
    assert r1["verdict"] == (M.Q3_PASS if r1["cosine_ge_min"] == 20 else M.Q3_FAIL)


def test_q2_compare(tmp_path):
    roots = {}
    for name, jitter in (("NONE", 1e-4), ("FP32", 0.0), ("FP16", 1e-4)):
        d = tmp_path / name / "GPU" / "device"
        d.mkdir(parents=True)
        for i, sid in SAMPLES:
            (d / f"{i:02d}_{sid}.run0.f32le").write_bytes(QC.f32le_bytes(softmax(i + 1, jitter)))
        roots[name] = tmp_path / name
    c = M.q2_compare(SAMPLES, roots)
    assert set(c["pairs"]) == {"NONE_vs_FP32", "NONE_vs_FP16"}
    assert c["pairs"]["NONE_vs_FP16"]["bit_equal"] == 20
    assert c["pairs"]["NONE_vs_FP32"]["bit_equal"] == 0 and c["pairs"]["NONE_vs_FP32"]["available"] == 20
    assert c["pairs"]["NONE_vs_FP32"]["max_abs_diff_max"] > 0


def test_request_runner_switch():
    saved = (QC.APP_PACKAGE, QC.APP_ACTIVITY, QC.APP_OUTPUT_DIR, QC.MIXREQ_APP_PACKAGE, QC.LOG_TAG)
    try:
        M.use_request_runner()
        assert QC.APP_ACTIVITY == "com.example.d1check.requestrunner/.InputListActivity"
        assert QC.APP_OUTPUT_DIR.endswith("com.example.d1check.requestrunner/files/q1") and QC.LOG_TAG == "D1Q1"
    finally:
        QC.APP_PACKAGE, QC.APP_ACTIVITY, QC.APP_OUTPUT_DIR, QC.MIXREQ_APP_PACKAGE, QC.LOG_TAG = saved
