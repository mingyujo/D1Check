"""P tests for the Q20 host tools.  Run:  py -3 -m pytest s26/tools/quality20 -q

Covers: f32le round trip · tie rule · cosine (0-norm → None) · tolerance boundary · app manifest = the shape QualityManifest.parse/validate
expects (keys, integer types, one accelerator per runtime, CPU threads 1, GPU FP32, NPU AOT) · evidence selftest (21 synthetic cases) ·
judge selftest (synthetic reference, every 등록 §3 branch) · q20_run.py --dry-run (no adb) writes host/q20_manifest.json.
No real reference output value is read by these tests.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q20_common as C  # noqa: E402
import q20_evidence as E  # noqa: E402
import q20_judge as J  # noqa: E402


def test_f32le_round_trip(tmp_path):
    values = [1.0, -2.5, 0.0, 1e-7, 3.4e38]
    p = tmp_path / "x.f32le"
    p.write_bytes(C.f32le_bytes(values))
    assert p.stat().st_size == 20
    back = C.read_f32le(p, 5)
    assert back[0] == 1.0 and back[1] == -2.5 and back[2] == 0.0
    assert C.f32le_bytes([1.0]) == bytes([0, 0, 0x80, 0x3F])
    with pytest.raises(ValueError):
        C.read_f32le(p, 4)


def test_tie_rule_and_cosine_and_tolerance():
    v = [0.0] * 1000
    v[10] = v[3] = 0.5
    v[999] = 0.4
    assert [i for i, _ in C.topk(v)][:3] == [3, 10, 999]
    assert C.cosine([0.0] * 3, [1.0, 0.0, 0.0]) is None
    assert C.cosine([1.0, float("nan")], [1.0, 1.0]) is None
    assert abs(C.cosine([1.0, 2.0], [2.0, 4.0]) - 1.0) < 1e-15
    # tolerance at ref 0.5 = 1e-4 + 5e-4 = 6e-4 (double arithmetic; 0.5 + 6e-4 itself lands a few ulp above the bound, so test either side)
    assert C.tolerance_violations([0.5 + 5.9e-4], [0.5]) == 0
    assert C.tolerance_violations([0.5 + 6.1e-4], [0.5]) == 1
    assert C.tolerance_violations([1e-4], [0.0]) == 0 and C.tolerance_violations([1.1e-4], [0.0]) == 1


def _fake_manifest():
    return dict(schema="s26-tensor-transfer-v1", shape=[1, 224, 224, 3], dtype="float32", endianness="little", layout="NHWC_RGB",
                quality_reference_sha256="0" * 64, preprocessing="x",
                samples=[dict(sample_id="%016x" % (0x3000_0000_0000_0000 + i), input_file=f"inputs/{i}/input.f32le", input_bytes=C.INPUT_BYTES,
                              input_sha256="%064x" % (i + 1), reference_file=f"references/{i}/output_0.f32le", reference_sha256="1" * 64,
                              model_sha256=C.ORIGINAL_MODEL_SHA256, label_sha256=C.LABELS_SHA256) for i in range(20)])


def test_app_manifest_shape_matches_kotlin_parser():
    m = C.build_app_manifest(_fake_manifest(), "run_x", C.ORIGINAL_MODEL_SHA256, C.AOT_MODEL_SHA256)
    assert m["protocol"] == "s26-q20-manifest-v1"
    for k in ("input_elements", "input_bytes", "output_elements", "runs_per_image"):
        assert isinstance(m[k], int)
    assert m["input_elements"] * 4 == m["input_bytes"] == 602_112 and m["output_elements"] == 1000 and m["runs_per_image"] == 2
    assert set(m["runtimes"]) == {"CPU", "GPU", "NPU"}
    for b, r in m["runtimes"].items():
        assert r["key"] == f"classification_{b}" and r["task"] == "classification" and r["backend"] == b
        assert len(r["model_sha256"]) == 64
        assert ("cpu_threads" in r) == (b == "CPU") and ("gpu_precision" in r) == (b == "GPU")
    assert m["runtimes"]["CPU"]["cpu_threads"] == 1 and m["runtimes"]["GPU"]["gpu_precision"] == "FP32"
    assert m["runtimes"]["NPU"]["model_path"].endswith("efficientnet_lite0_Samsung_E9965.tflite")
    assert m["runtimes"]["CPU"]["model_sha256"] == m["runtimes"]["GPU"]["model_sha256"] == C.ORIGINAL_MODEL_SHA256
    assert m["runtimes"]["NPU"]["model_sha256"] == C.AOT_MODEL_SHA256
    assert len(m["samples"]) == 20
    for i, s in enumerate(m["samples"]):
        assert s["index"] == i and isinstance(s["input_bytes"], int) and s["input_bytes"] == 602_112
        assert s["input_path"].startswith("/data/local/tmp/quality20/inputs/") and len(s["input_sha256"]) == 64
    text = json.dumps(m, ensure_ascii=False)
    assert "NaN" not in text and "Infinity" not in text
    files = C.device_files(_fake_manifest(), Path("/in"), Path("/m/o.tflite"), Path("/m/a.tflite"))
    assert len(files) == 22 and files[0]["sha256"] == C.ORIGINAL_MODEL_SHA256 and files[1]["sha256"] == C.AOT_MODEL_SHA256


def test_evidence_selftest():
    assert E.selftest() == 0


def test_evidence_marks_translation():
    text, pid = E._case("NPU", "ok")
    rows = E.V.parse_log(text) if hasattr(E.V, "parse_log") else E.EVIDENCE.parse_log(text)
    p, marks, err = E.q20_marks(rows, "selftest", "NPU")
    assert err is None and p == str(pid)
    translated, window = E.translate_marks(marks, "classification_NPU")
    whats = [w for _, w, _ in translated]
    assert whats[:3] == ["session_start", "runtime create_start", "runtime create_end"]
    assert "warmup_start" in whats and "warmup_end" in whats and "common_start" in whats and whats[-1] == "drain_end"
    assert window is not None and window[0] < window[1]


def test_judge_selftest():
    assert J.selftest() == 0


def test_run_dry_run(tmp_path):
    inputs = tmp_path / "ref"
    m = _fake_manifest()
    for s in m["samples"]:
        p = inputs / s["input_file"]
        p.parent.mkdir(parents=True, exist_ok=True)
        data = bytes((i * 7) & 0xFF for i in range(C.INPUT_BYTES))
        p.write_bytes(data)
        s["input_sha256"] = C.sha256_bytes(data)
    C.write_json(inputs / "tensor_manifest.json", m)
    models = tmp_path / "models"
    models.mkdir()
    (models / "o.tflite").write_bytes(b"o")
    (models / "a.tflite").write_bytes(b"a")
    results = tmp_path / "results"
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "q20_run.py"), "--run-id", "dry_1", "--dry-run", "--inputs", str(inputs),
                        "--original-model", str(models / "o.tflite"), "--aot-model", str(models / "a.tflite"), "--results", str(results),
                        "--apk-sha", "0" * 64], capture_output=True, text=True, encoding="utf-8", timeout=120)
    # dry-run still verifies host file SHAs against the registered model hashes → the fake models must be rejected (fail closed)
    assert r.returncode != 0 and "sha" in (r.stdout + r.stderr).lower()
    # with the registered models present on this machine the dry run goes through; skip otherwise
    if not (C.DEFAULT_ORIGINAL_MODEL.is_file() and C.DEFAULT_AOT_MODEL.is_file()):
        pytest.skip("registered models not on this machine")
    results2 = tmp_path / "results2"
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "q20_run.py"), "--run-id", "dry_2", "--dry-run", "--inputs", str(inputs),
                        "--results", str(results2), "--apk-sha", "0" * 64], capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    rec = C.read_json(results2 / "host" / "run_record.json")
    assert set(rec["backends"]) == {"CPU", "GPU", "NPU"} and all(b["status"] == "done" for b in rec["backends"].values())
    app = C.read_json(results2 / "host" / "q20_manifest.json")
    assert app["protocol"] == "s26-q20-manifest-v1" and len(app["samples"]) == 20
    assert "DRY adb logcat" not in r.stdout  # dry-run never starts logcat
    assert "am start -W -n com.example.d1check.qualityrunner/.QualityActivity" in r.stdout
    assert r.stdout.index("d1_q20_backend CPU") < r.stdout.index("d1_q20_backend GPU") < r.stdout.index("d1_q20_backend NPU")
    assert "<SERIAL>" not in r.stdout or "ANDROID_SERIAL" not in r.stdout
    assert "npurunner" not in " ".join(l for l in r.stdout.splitlines() if "force-stop" in l)
