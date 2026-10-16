"""Frozen A24-only state cost bridge; no fitting or device access.

TREND27 and MEASURED35 retain historical gauge-conditional aggregate power.
The current A24 raw-current/charge unit issue is not repaired by this bridge.
Dispatch->AVAILABLE ownership is the original coarse cost boundary. Inner
phase events are recorded by the engine but do not create invented activity.
"""
from __future__ import annotations

import ast
import builtins
import copy
import dis
import hashlib
import json
import math
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

import numpy as np

BASE = Path("C:/Users/chomg/Documents/Codex/2026-10-11/dkfo")
MODEL_NAMES = ("TREND27", "MEASURED35")
BASELINE_MODE = "HISTORICAL_A24_FIXED_GAUGE_MODEL"
PINNED = {
    "profile": ("outputs/EXISTING-DATA-DYNAMICS-35/repro/profiles/A24_measured35.json", "e886b848a46231f0aa9ca988c4ac38449f825622c92703455d47c4a9b15731f3"),
    "trend_source": ("outputs/EXISTING-DATA-DYNAMICS-35/repro/tools/d1_dual_trend27_runtime.py", "642a55d22c6ef26794aa3de6c731d7faa6286105f0122d950f27d58a1fe47eed"),
    "measured_source": ("outputs/EXISTING-DATA-DYNAMICS-35/repro/tools/d1_measured35.py", "8584e8f30b785886e31f6b432608886e080490590015386b7bbfb1be4f7d27cd"),
}
STATES_A24 = ("classification_CPU", "detection_CPU", "classification_GPU", "classification_GPU+detection_CPU")
TASKS = {"C": "classification", "D": "detection", "classification": "classification", "detection": "detection"}


def _sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _digest(value):
    return _sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _selected_ast(source, names, scope, filename):
    tree = ast.parse(source, filename=filename)
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if {n.name for n in selected} != set(names):
        raise ValueError("frozen A24 source object selection")
    # Exact AST bodies, globals restricted to the A24 path. No source import
    # executes the original simulation wrappers or any S26 cost model.
    exec(compile(ast.Module(body=selected, type_ignores=[]), filename, "exec"), scope)


def _measured_version(source, filename):
    """Restore only the literal ABI constant omitted by the G001 AST loader."""
    tree = ast.parse(source, filename=filename)
    bindings = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else []
        if any(isinstance(item, ast.Name) and item.id == "VERSION" for target in targets for item in ast.walk(target)):
            bindings.append(node)
    if len(bindings) != 1 or not isinstance(bindings[0], ast.Assign):
        raise ValueError("unique measured35 VERSION assignment required")
    node = bindings[0]
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name) or node.targets[0].id != "VERSION":
        raise ValueError("direct measured35 VERSION assignment required")
    value = ast.literal_eval(node.value)
    if type(value) is not str or value != "measured-development-state-memory-v35":
        raise ValueError("frozen measured35 VERSION literal")
    return value


def _namespace_closure(scope, names):
    """Inspect selected bytecode recursively; no model instance or call."""
    functions = []
    for name in sorted(names):
        obj = scope[name]
        if isinstance(obj, FunctionType):
            functions.append((name, obj.__code__))
        elif isinstance(obj, type):
            functions.extend((name + "." + key, item.__code__) for key, item in sorted(vars(obj).items()) if isinstance(item, FunctionType))
        else:
            raise ValueError("selected source must define functions/classes")
    proof = []
    def visit(label, code):
        required = sorted({item.argval for item in dis.get_instructions(code) if item.opname == "LOAD_GLOBAL"})
        missing = [name for name in required if name not in scope and name not in vars(builtins)]
        if missing:
            raise ValueError("unclosed selected globals " + label + ": " + repr(missing))
        proof.append({"code": label, "global_names": required, "missing": missing})
        for index, value in enumerate(code.co_consts):
            if isinstance(value, CodeType):
                visit(label + ".const" + str(index) + ":" + value.co_name, value)
    for label, code in functions:
        visit(label, code)
    return {"status": "PASS", "method": "recursive LOAD_GLOBAL namespace-or-builtin closure", "objects": proof,
            "model_instances": 0, "model_calls": 0, "environment": 0, "NN": 0}


def modelsload(base=BASE):
    """Read and SHA-check three existing files; constructs no CostState."""
    base = Path(base)
    blobs, source_proof = {}, {}
    for key, (rel, expected) in PINNED.items():
        path = base / rel
        raw = path.read_bytes()
        actual = _sha_bytes(raw)
        if actual != expected:
            raise ValueError(f"frozen cost SHA mismatch: {key}")
        blobs[key] = raw
        source_proof[key] = {"path": str(path), "sha256": actual}
    profile = json.loads(blobs["profile"])
    if profile["device"] != "A24" or profile["measured35"]["device"] != "A24":
        raise ValueError("A24 profile required")
    if profile["measured35"]["power"]["selected"]:
        raise ValueError("historical retained A24 power required")
    scope = {"copy": copy, "math": math, "np": np, "STATES": STATES_A24}
    _selected_ast(blobs["trend_source"].decode("utf-8"), {"initialize_a24", "convolution", "A24Cost"}, scope, source_proof["trend_source"]["path"])
    measured_source = blobs["measured_source"].decode("utf-8")
    version = _measured_version(measured_source, source_proof["measured_source"]["path"])
    measured_scope = {"copy": copy, "math": math, "np": np, "STATES": {"A24": STATES_A24}, "trend": SimpleNamespace(convolution=scope["convolution"]), "VERSION": version}
    _selected_ast(measured_source, {"transition", "CompactCost"}, measured_scope, source_proof["measured_source"]["path"])
    namespace_proof = {
        "TREND27": _namespace_closure(scope, {"initialize_a24", "convolution", "A24Cost"}),
        "MEASURED35": _namespace_closure(measured_scope, {"transition", "CompactCost"}),
        "restored_literal": {"name": "VERSION", "value": version, "source_path": source_proof["measured_source"]["path"], "source_sha256": source_proof["measured_source"]["sha256"]},
    }
    return {
        "names": MODEL_NAMES,
        "profile": profile,
        "A24Cost": scope["A24Cost"],
        "CompactCost": measured_scope["CompactCost"],
        "namespace_proof": namespace_proof,
        "source_proof": source_proof,
        "binding_sha256": _digest(source_proof),
        "baseline_w": profile["measured35"]["baseline_w"],
        "status": "HISTORICAL_A24_CONDITIONAL_DEVELOPMENT_MODEL",
        "new_measurement_energy_unit_resolved": False,
        "S26_physical_coefficients_used": False,
    }


load_frozen_models = modelsload


def validate_initial(public_initial):
    """Reject unavailable, future, unbracketed or fabricated initial inputs."""
    x = copy.deepcopy(public_initial)
    if x.get("device") != "A24" or not x.get("context_id"):
        raise ValueError("A24 named initial context required")
    if x.get("energy_baseline_mode") != BASELINE_MODE:
        raise ValueError("explicit historical fixed gauge-model baseline required")
    pre = x.get("pre", [])
    if len(pre) < 8:
        raise ValueError("at least eight completed precommon AP samples required")
    last = -math.inf
    for row in pre:
        if set(("t", "lo", "hi", "ap")) - set(row):
            raise ValueError("actual AP clock bracket required")
        t, lo, hi, ap = (float(row[k]) for k in ("t", "lo", "hi", "ap"))
        if not all(math.isfinite(z) for z in (t, lo, hi, ap)) or not lo <= t <= hi <= 0 or t <= last:
            raise ValueError("finite, strictly ordered, completed precommon AP only")
        last = t
    if float(pre[-1]["t"]) - float(pre[0]["t"]) < 20:
        raise ValueError("at least twenty seconds of completed AP history required")
    p = x.get("provenance", {})
    for key in ("source_path", "source_sha256", "session_id", "common_ns", "temperature_channel", "clock", "source_role"):
        if key not in p or p[key] is None:
            raise ValueError(f"initial provenance missing: {key}")
    if len(str(p["source_sha256"])) != 64 or p["temperature_channel"] != "AP" or p["source_role"] != "completed_precommon":
        raise ValueError("actual A24 HAL AP provenance required")
    x["pre"] = [{k: float(row[k]) for k in ("t", "lo", "hi", "ap")} for row in pre]
    return x


def nominal_energy_proxy(task, route, occupancy_ns, model_name="MEASURED35", models=None):
    """Incremental single-owner J proxy, excludes common baseline and pairing.

    It is an online action feature, not a forecast of a complete queue or an
    independently measured accelerator energy. Both fixed models retain W.
    """
    if model_name not in MODEL_NAMES:
        raise ValueError("unknown A24 cost model")
    if isinstance(occupancy_ns, bool) or not isinstance(occupancy_ns, int) or occupancy_ns < 0:
        raise ValueError("nonnegative integer occupancy ns required")
    models = models if models is not None else modelsload()
    key = TASKS[task] + "_" + route
    if key not in ("classification_CPU", "classification_GPU", "detection_CPU"):
        raise ValueError("unsupported A24 route")
    return models["profile"]["cost_anchor"]["energy_increment_w"][key] * (occupancy_ns / 1e9)


def _exp_area(rate, dt):
    return -math.expm1(-rate * dt) / rate


def _conv_area(rate, tau, dt):
    delta = rate - 1 / tau
    if abs(delta) < 1e-10:
        return (1 - math.exp(-rate * dt) * (1 + rate * dt)) / (rate * rate)
    return (_exp_area(1 / tau, dt) - _exp_area(rate, dt)) / delta


def _trend_ap_area(state, dt):
    """Analytic integral of the unchanged A24Cost temperature expression."""
    b, tau, p = state.beta, state.tau, state.initial
    elapsed = state.now - p["anchor_s"]
    ab = _exp_area(b, dt)
    at = _exp_area(1 / tau, dt)
    initial_area = p["initial_c"] * dt
    delta = b - 1 / 30
    if abs(delta) < 1e-10:
        raise ValueError("unregistered initial thermal rate degeneracy")
    conv = (math.exp(-elapsed / 30) * _exp_area(1 / 30, dt) - math.exp(-b * elapsed) * ab) / delta
    initial_area += state.coefficients[5] * ((p["reference_c"] - p["initial_c"]) * (dt - math.exp(-b * elapsed) * ab) + p["h_last"] * conv)
    key = state.key()
    u = np.zeros(4)
    power = 0.0
    if key != "resident_idle":
        u[STATES_A24.index(key)] = 1.0
        power = state.cost["energy_increment_w"][key]
    fast_area = state.fast * ab + u * (dt - ab) / b
    slow_area = state.slow * at + power * tau * (dt - at)
    return float(initial_area + fast_area @ state.coefficients[:4] + slow_area * state.coefficients[4])


def _ap_area(state, dt, model_name):
    if model_name == "TREND27":
        return _trend_ap_area(state, dt)
    tc = state.cfg["thermal"]
    original = _trend_ap_area(state.original, dt)
    if not tc["selected"]:
        return original
    b, tau, coef = tc["beta"], tc["slow_tau_s"], np.asarray(tc["coefficients"])
    ab, at = _exp_area(b, dt), _exp_area(1 / tau, dt)
    u = np.zeros(4)
    key = state.key()
    active = float(key != "idle")
    if active:
        u[STATES_A24.index(key)] = 1.0
    const = np.r_[u * (1 - active), u * active]
    expo = np.r_[-u * (state.th - active), u * (state.th - active)]
    if tc["memory"]:
        fast_area = state.tfast * ab + const * (dt - ab) / b + expo * _conv_area(b, 20.0, dt)
    else:
        fast_area = state.tfast * ab + u * (dt - ab) / b
    slow_area = state.tslow * at + active * tau * (dt - at)
    idle_area = _trend_ap_area(state.idle, dt)
    new_area = state.initial_ap * dt + (idle_area - state.initial_ap * dt) * coef[-1] + float(np.r_[fast_area, slow_area] @ coef[:-1])
    mix = tc.get("mix", 1.0)
    return (1 - mix) * original + mix * new_area


class OnlineCost:
    """Integer-ns owner-state bridge, independently callable by the engine.

    AP area is analytic. Peak is explicitly sampled at .5 s plus every actual
    event boundary, not a continuous physical peak or sensor-resolution claim.
    """
    def __init__(self, models, public_initial, model_name="MEASURED35"):
        if model_name not in models["names"]:
            raise ValueError("unknown A24 model")
        self.models = models
        self.model_name = model_name
        self.public_initial = validate_initial(public_initial)
        self.initial_binding_sha256 = _digest(self.public_initial)
        profile = copy.deepcopy(models["profile"])
        public = copy.deepcopy(profile["trend27_anchor"]["public_boundary"])
        public["pre"] = self.public_initial["pre"]
        public["pre_w"] = models["baseline_w"]
        profile["measured35"]["baseline_w"] = models["baseline_w"]
        original = models["A24Cost"](profile["cost_anchor"], profile["trend27_anchor"]["thermal"]["AP"], public)
        self._state = original if model_name == "TREND27" else models["CompactCost"](original, profile)
        self.now_ns = 0
        self.baseline_w = models["baseline_w"]
        self.initial_AP_c = float(self.public_initial["pre"][-1]["ap"])
        self.model_AP0_c = float(self._state.snapshot()["temperature_c"]["AP"])
        self._ap_area_35_180 = 0.0
        self._window_ns = 0
        self._peak_0_180 = self.model_AP0_c
        self._energy = {0: 0.0}
        self._ap = {0: self.model_AP0_c}
        self._owners = {}
        self._phases = {}

    def advance(self, ns):
        if isinstance(ns, bool) or not isinstance(ns, int) or ns < self.now_ns:
            raise ValueError("monotonic integer ns required")
        if ns > 210_000_000_000:
            raise ValueError("registered A24 cost horizon is 210 seconds")
        while self.now_ns < ns:
            next_grid = (self.now_ns // 500_000_000 + 1) * 500_000_000
            marks = [ns, next_grid]
            marks.extend(t for t in (35_000_000_000, 120_000_000_000, 180_000_000_000) if t > self.now_ns)
            target = min(marks)
            dt = (target - self.now_ns) / 1e9
            if self.now_ns >= 35_000_000_000 and target <= 180_000_000_000:
                self._ap_area_35_180 += _ap_area(self._state, dt, self.model_name)
                self._window_ns += target - self.now_ns
            self._state.advance(target / 1e9)
            self.now_ns = target
            snap = self._state.snapshot()
            ap = float(snap["temperature_c"]["AP"])
            if target <= 180_000_000_000:
                self._peak_0_180 = max(self._peak_0_180, ap)
            if target in (35_000_000_000, 120_000_000_000, 180_000_000_000):
                self._energy[target] = float(snap["energy_window_j"])
                self._ap[target] = ap
        return self.snapshot()

    def dispatch(self, rid, task, route):
        if rid in self._owners:
            raise ValueError("duplicate A24 request owner")
        task = TASKS[task]
        self._state.dispatch(rid, task, route)
        self._owners[rid] = (task, route)
        self._phases[rid] = "DISPATCH"
        return self.snapshot()

    def phase(self, rid, kind):
        if rid not in self._owners:
            raise ValueError("phase for nonowner request")
        self._phases[rid] = str(kind)
        # No inner-stage activity multipliers are identified by this model.
        return self.snapshot()

    def available(self, rid, route):
        if rid not in self._owners or self._owners[rid][1] != route:
            raise ValueError("A24 AVAILABLE owner identity")
        self._state.available(rid, route)
        del self._owners[rid]
        self._phases.pop(rid, None)
        return self.snapshot()

    def snapshot(self):
        snap = self._state.snapshot()
        t, window = self.now_ns / 1e9, self._window_ns / 1e9
        energy = float(snap["energy_window_j"])
        reward_t = min(t, 180.0)
        reward_energy = energy if self.now_ns < 180_000_000_000 else self._energy[180_000_000_000]
        return {
            "time_ns": str(self.now_ns), "time_s": t,
            "AP_c": float(snap["temperature_c"]["AP"]), "SKIN_c": None,
            "initial_AP_c": self.initial_AP_c, "model_AP0_c": self.model_AP0_c,
            "power_w": float(snap["power_w"]), "continuous_power_w": float(snap["power_w"]),
            "continuous_energy_j": energy,
            "cost_cumulative2": [(reward_energy - self.baseline_w * reward_t) / 20.0, (self._ap_area_35_180 - self.initial_AP_c * window) / 72.5],
            "energy_reward_window_s": [0.0, reward_t],
            "ap_window_elapsed_s": window,
            "energy_status": "historical_A24_gauge_conditional_prediction_not_new_measured_J",
            "energy_baseline_mode": BASELINE_MODE,
            "model_name": self.model_name,
            "initial_binding_sha256": self.initial_binding_sha256,
            "model_binding_sha256": self.models["binding_sha256"],
            "inner_phase_activity_identified": False,
            "thermal_to_timing_feedback": False,
        }

    def totals(self):
        e120 = self._energy.get(120_000_000_000)
        e180 = self._energy.get(180_000_000_000)
        e35 = self._energy.get(35_000_000_000)
        ap180 = self._ap.get(180_000_000_000)
        complete = self.now_ns >= 180_000_000_000
        return {
            **self.snapshot(),
            "continuous_J0_120": e120,
            "continuous_J0_180": e180,
            "continuous_J35_180": (e180 - e35) if e180 is not None and e35 is not None else None,
            "AP35_180_mean_c": self._ap_area_35_180 / 145 if complete else None,
            "AP0_180_peak_c": self._peak_0_180 if complete else None,
            "AP0_180_peak_method": "0.5_second_grid_and_all_event_boundaries",
            "AP180_c": ap180,
            "AP180_residual_from_initial_c": ap180 - self.initial_AP_c if ap180 is not None else None,
            "baseline_w": self.baseline_w,
            "all_owner_released": not self._owners,
            "new_measurement_energy_unit_resolved": False,
            "physical_or_independent_policy_delta_accuracy_confirmed": False,
        }

