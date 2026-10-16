"""One registered Node audit under the original frozen Python worker lease.

SOURCE ONLY until a separately registered NODE_VERIFY operation is invoked.
The frozen runtime guard holds G002's original one-byte lock, 8 GiB reserve,
source/input pins and all 351 originals while this Python leaf waits for Node.
There is no refit, optimizer, environment, HTTP, device or automation API.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys

FROZEN_GUARD_SHA = "d2583f2b6d3e92197893bb97736543723dd99c0e924a75a843a2cb3f08b83735"
BASE = Path("C:/Users/chomg/Documents/Codex/2026-10-11/dkfo")
ORIGINAL_LOCK = BASE / "outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock"
PYTHON_OPTIONS = frozenset(("-B", "-u", "-I", "-s", "-E"))
OWN_NODE = re.compile(r"a24-model-integration-|a24-integrated-sim-|s26-integrated-model-|s26-scheduling-causality-|s26-rolling-atc-rl-|s26-ie-rollout-", re.I)
_LEASE_JOB_HANDLE = None


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canonical_path(value):
    require(isinstance(value, str) and ntpath.isabs(value), "Absolute Windows path required")
    return ntpath.normcase(ntpath.normpath(value))


def windows_argv(command):
    """Pure CommandLineToArgvW-style quote/backslash parsing for exact paths.

    The caller subsequently allows only a direct .py entry plus --operation.
    -c/-m, additional scripts, and trailing arguments are rejected.
    """
    require(isinstance(command, str) and "\x00" not in command, "Invalid command line")
    out, index = [], 0
    while index < len(command):
        while index < len(command) and command[index].isspace():
            index += 1
        if index >= len(command):
            break
        token, quoted = [], False
        while index < len(command):
            char = command[index]
            if char.isspace() and not quoted:
                break
            if char == "\\":
                end = index
                while end < len(command) and command[end] == "\\":
                    end += 1
                count = end - index
                if end < len(command) and command[end] == '"':
                    token.extend("\\" * (count // 2))
                    if count % 2:
                        token.append('"')
                    else:
                        quoted = not quoted
                    index = end + 1
                else:
                    token.extend("\\" * count)
                    index = end
                continue
            if char == '"':
                quoted = not quoted
            else:
                token.append(char)
            index += 1
        require(not quoted, "Unclosed quoted command argument")
        out.append("".join(token))
        while index < len(command) and command[index].isspace():
            index += 1
    return out


def python_invocation(command, entry, operation_path):
    arguments = windows_argv(command)
    require(len(arguments) >= 4, "Python wrapper command too short")
    index = 1
    while index < len(arguments) and arguments[index] in PYTHON_OPTIONS:
        index += 1
    require(index < len(arguments) and canonical_path(arguments[index]) == canonical_path(entry),
            "Python ancestor is not the exact wrapper entry")
    require(arguments[index + 1:] == ["--operation", operation_path] or
            (len(arguments[index + 1:]) == 2 and arguments[index + 1] == "--operation" and
             canonical_path(arguments[index + 2]) == canonical_path(operation_path)),
            "Python ancestor operation argument differs")
    return arguments


def created_ms(row):
    value = row.get("CreatedUtc", row.get("CreationDate"))
    require(isinstance(value, str), "Missing process creation time")
    legacy = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", value)
    if legacy:
        return int(legacy.group(1))
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None, "Process creation time lacks timezone")
    return int(stamp.timestamp() * 1000)


def is_python(row):
    name = str(row.get("Name") or "").lower()
    return name.startswith("python") or name in ("py.exe", "pyw.exe")


def wrapper_chain(rows, wrapper_pid, entry, operation_path):
    """Pure identity proof used by preflight fixtures; no process reads here."""
    by_id = {int(r["ProcessId"]): r for r in rows}
    require(len(by_id) == len(rows), "Duplicate process IDs in snapshot")
    current = int(wrapper_pid)
    require(current in by_id and is_python(by_id[current]), "Actual wrapper Python missing")
    allowed, seen, child_created = [], set(), None
    while current in by_id and is_python(by_id[current]):
        require(current not in seen and len(seen) < 8, "Cyclic or excessive Python ancestry")
        seen.add(current)
        row = by_id[current]
        stamp = created_ms(row)
        require(child_created is None or stamp <= child_created, "Reused parent PID or reversed creation times")
        python_invocation(row.get("CommandLine"), entry, operation_path)
        allowed.append(current)
        child_created = stamp
        current = int(row.get("ParentProcessId") or 0)
    require(all(not is_python(r) or int(r["ProcessId"]) in allowed for r in rows),
            "Another Python leaf is alive outside the proven wrapper/shim chain")
    return allowed


def node_ancestry_fixture(rows, node_pid, entry, operation_path):
    """Pure fixture analogue of Node's independently implemented CIM proof."""
    by_id = {int(r["ProcessId"]): r for r in rows}
    require(len(by_id) == len(rows) and node_pid in by_id, "Node snapshot identity absent")
    node = by_id[node_pid]
    require(str(node.get("Name") or "").lower().startswith("node"), "Actual child is not Node")
    parent = int(node.get("ParentProcessId") or 0)
    require(parent in by_id and is_python(by_id[parent]), "Node lacks its direct Python lease parent")
    require(created_ms(by_id[parent]) <= created_ms(node), "Node parent PID was reused")
    return wrapper_chain(rows, parent, entry, operation_path)


def _snapshot():
    command = ('[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); '
               'Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,'
               '@{Name="CreatedUtc";Expression={$_.CreationDate.ToUniversalTime().ToString("o")}},'
               'CommandLine | ConvertTo-Json -Compress')
    raw = subprocess.check_output(["powershell", "-NoProfile", "-Command", command],
                                  creationflags=0x08000000)
    value = json.loads(raw.decode("utf-8-sig"))
    return value if isinstance(value, list) else [value]


def _pin_in(spec, roster):
    return any(canonical_path(row["path"]) == canonical_path(spec["path"]) and
               row["sha256"] == spec["sha256"] for row in roster)


def _manifest_paths(value):
    result = []
    if isinstance(value, dict):
        if isinstance(value.get("path"), str):
            result.append(value["path"])
        for item in value.values():
            result.extend(_manifest_paths(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_manifest_paths(item))
    return result


def hold_process_tree_job():
    """Windows kills inherited Node/PS children if this real wrapper dies.

    Keep the noninheritable raw job handle until process exit. Closing it inside
    the guard would kill the wrapper before COMPLETE/protection checks finish.
    The child uses no BREAKAWAY flag, so it inherits the wrapper's job. Nested
    assignment failure is fatal before Node creation; no fallback launches.
    """
    global _LEASE_JOB_HANDLE
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Counters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    require(_LEASE_JOB_HANDLE is None, "Process tree lease job already exists")
    handle = kernel.CreateJobObjectW(None, None)
    require(bool(handle), "CreateJobObjectW failed before Node launch")
    info = Extended()
    info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise OSError(error, "SetInformationJobObject failed before Node launch")
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise OSError(error, "AssignProcessToJobObject failed before Node launch")
    _LEASE_JOB_HANDLE = handle
    return dict(status="WRAPPER_JOB_ASSIGNED_BEFORE_CHILD", kill_on_wrapper_exit=True,
                child_inherits_job=True, handle_closed_only_by_OS_on_wrapper_exit=True)


def load_frozen_guard():
    source = Path(__file__).with_name("runtime_guard.py")
    require(hashlib.sha256(source.read_bytes()).hexdigest() == FROZEN_GUARD_SHA,
            "Frozen runtime_guard source changed")
    spec = importlib.util.spec_from_file_location("a24_node_lease_exact_frozen_guard", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True)
    args = parser.parse_args()
    require(os.name == "nt", "Registered lease requires Windows")
    require(sys.dont_write_bytecode, "Launch the registered wrapper with -B or PYTHONDONTWRITEBYTECODE=1")
    guard = load_frozen_guard()
    operation_path = str(Path(args.operation).absolute())
    with guard.operation(operation_path, __file__) as (op, out):
        require(op["mode"] == "NODE_VERIFY", "Exact NODE_VERIFY lease mode required")
        require(op.get("new_fit") == 0 and op.get("NN") == 0 and op.get("optimizer") == 0,
                "Audit lease cannot fit or optimize")
        require(canonical_path(op["worker_lock_path"]) == canonical_path(str(ORIGINAL_LOCK)),
                "Use the original G002 one-byte worker lock")
        require(len(op["protected_pins"]) == 351, "All 351 original protection pins required")
        manifest_pin, node_pin = op["node_manifest_pin"], op["node_executable_pin"]
        require(_pin_in(manifest_pin, op["input_pins"]) and _pin_in(node_pin, op["input_pins"]),
                "Manifest and exact Node executable must be operation input-pinned")
        manifest_path, node_exe = guard.pin(manifest_pin), guard.pin(node_pin)
        manifest = guard.read(manifest_path)
        entry_pin = manifest["lease_wrapper_entry_pin"]
        require(canonical_path(entry_pin["path"]) == canonical_path(str(Path(__file__).absolute())) and
                _pin_in(entry_pin, op["source_pins"]), "Exact wrapper entry source pin required")
        guard.pin(entry_pin)
        require(canonical_path(manifest["expected_lease_operation_path"]) == canonical_path(operation_path),
                "Manifest names a different future lease operation")
        verifier_pin = manifest["operator_pin"]
        require(_pin_in(verifier_pin, op["source_pins"]), "Node verifier must be operation source-pinned")
        verifier = guard.pin(verifier_pin)
        require(canonical_path(str(Path(manifest["output_dir"]).absolute())) ==
                canonical_path(str((out / "node").absolute())), "Node outputs must be the fresh lease namespace/node")
        require(any(canonical_path(s["path"]) == canonical_path(str(Path(__file__).with_name("runtime_guard.py")))
                    and s["sha256"] == FROZEN_GUARD_SHA for s in op["source_pins"]),
                "Exact frozen runtime guard must be source-pinned")
        # The unchanged guard covers registered sources/inputs plus every nested
        # Node input and output path for reparse/symlink and C:/D: reserve checks.
        extra_paths = [*(_manifest_paths(manifest)), manifest["output_dir"], operation_path,
                       op["worker_lock_path"], *[s["path"] for s in op["source_pins"]]]
        volumes = guard.free_guard(extra_paths)
        rows = _snapshot()
        allowed = wrapper_chain(rows, os.getpid(), str(Path(__file__).absolute()), operation_path)
        require(not any(str(r.get("Name") or "").lower().startswith("node") and
                        OWN_NODE.search(str(r.get("CommandLine") or "")) for r in rows),
                "An own Node producer is alive before child launch")
        process_tree_job = hold_process_tree_job()
        actual = next(r for r in rows if int(r["ProcessId"]) == os.getpid())
        guard.write_new(out / "LEASE_READY.json", dict(status="LOCK_HELD_BEFORE_NODE_LAUNCH",
            operation_sha256=guard.sha(operation_path), manifest_sha256=manifest_pin["sha256"],
            wrapper_pid=os.getpid(), wrapper_created_utc=actual["CreatedUtc"],
            proven_python_wrapper_and_shims=allowed, worker_lock_path=op["worker_lock_path"],
            node_executable_pin=node_pin, wrapper_entry_pin=entry_pin, extra_volume_guard=volumes,
            process_tree_job=process_tree_job,
            new_fit=0, new_environment=0, HTTP=0, device_commands=0))
        command = [str(node_exe), "--max-old-space-size=4096", str(verifier), "--manifest", str(manifest_path)]
        environment = dict(os.environ)
        environment.pop("NODE_OPTIONS", None)
        environment.pop("NODE_PATH", None)
        child_process = None
        with (out / "node.stdout.log").open("xb") as stdout, (out / "node.stderr.log").open("xb") as stderr:
            try:
                child_process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    cwd=str(Path(__file__).parent), env=environment, creationflags=0x08000000)
                guard.write_new(out / "NODE_CHILD.json", dict(pid=child_process.pid,
                    parent_pid=os.getpid(), command=command, started_utc=guard.now(),
                    manifest_sha256=manifest_pin["sha256"], new_fit=0, new_environment=0))
                return_code = child_process.wait()
            finally:
                if child_process is not None and child_process.poll() is None:
                    child_process.terminate()
                    try:
                        child_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child_process.kill()
                        child_process.wait(timeout=5)
        result_path = out / "node/RESULT.json"
        require(result_path.is_file(), "Node did not save RESULT; preserve logs, no retry")
        result = guard.read(result_path)
        accepted = (return_code == 0 and result.get("status") == "PASS_SOFTWARE_MODEL_ARITHMETIC_ONLY"
                    and result.get("failed_checks") == 0 and not result.get("failures")
                    and result.get("full_independent_feature_reconstruction") is True
                    and result.get("manifest_sha256") == manifest_pin["sha256"]
                    and result.get("new_fit") == 0 and result.get("new_environment") == 0
                    and result.get("HTTP") == 0 and result.get("device_commands") == 0
                    and result.get("measured_J") is None and result.get("physical_goal_pass") is False)
        receipt = dict(status="PASS_SOFTWARE_MODEL_ARITHMETIC_ONLY" if accepted else "NODE_RESULT_NOT_ACCEPTED",
            child_return_code=return_code, child_result_status=result.get("status"),
            child_result_pin=dict(path=str(result_path), sha256=guard.sha(result_path), bytes=result_path.stat().st_size),
            manifest_pin=manifest_pin, node_executable_pin=node_pin, new_fit=0, new_environment=0,
            NN=0, optimizer=0, HTTP=0, device_commands=0, measured_J=None,
            physical_goal_pass=False, automatic_retry=False)
        if accepted:
            report_path = out / "node/REPORT_DATA.json"
            require(report_path.is_file() and guard.sha(report_path) == result.get("report_sha256"),
                    "Child report SHA binding differs")
            receipt["child_report_pin"] = dict(path=str(report_path), sha256=guard.sha(report_path),
                                              bytes=report_path.stat().st_size)
        guard.write_new(out / "LEASE_RESULT.json", receipt)
        require(accepted, "Node software arithmetic did not pass; original result and logs retained, no automatic retry")


if __name__ == "__main__":
    main()
