"""Durable run-local commits and conservative recovery; never execute a simulator.

An identity with a prior START is consumed even when it failed. A protocol
upgrade must use a new identity. Recovery may finish a *prepared* disk commit,
but cannot invent an observation, an action, or an expected artifact hash.
"""
import gzip
import hashlib
import json
import os
import re
import time
from pathlib import Path


class RecoveryError(ValueError):
    pass


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_jsonl(path, repair_torn_tail=False):
    """Reject corrupt complete records; optionally preserve/remove a torn tail."""
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    values = []
    offset = 0
    for i, line in enumerate(lines):
        if not line.strip():
            offset += len(line)
            continue
        try:
            value = json.loads(line.decode("utf-8"))
            if not isinstance(value, dict):
                raise RecoveryError("journal record is not an object: " + str(path))
        except (UnicodeDecodeError, json.JSONDecodeError):
            torn = i == len(lines) - 1 and not line.endswith(b"\n")
            if not torn or not repair_torn_tail:
                raise RecoveryError("corrupt journal record: " + str(path))
            # The exact fragment remains available for diagnosis. Only the
            # incomplete append is removed, never a valid historical record.
            evidence = path.parent / "recovery_evidence" / (
                path.name + ".torn-" + hashlib.sha256(line).hexdigest() + ".bin")
            if not evidence.exists():
                _write_atomic(evidence, line)
            _write_atomic(path, data[:offset])
            break
        values.append(value)
        offset += len(line)
    return values


def append_jsonl(path, value):
    """Synchronous append, including a separator after a valid newline-less tail."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    separator = b""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                separator = b"\n"
    with path.open("ab") as f:
        f.write(separator + _json_bytes(value) + b"\n")
        f.flush()
        os.fsync(f.fileno())


def _without_diagnostics(value, ignored):
    if isinstance(value, dict):
        return {k: _without_diagnostics(v, ignored) for k, v in value.items()
                if k not in ignored}
    if isinstance(value, list):
        return [_without_diagnostics(v, ignored) for v in value]
    return value


def append_idempotent(path, value, key_fields=("episode",),
                      ignored_fields=("recovered", "unix")):
    """Append once; repeated deterministic replay must agree with the old record.

    Use key_fields=('update',) for optimizer logs. After checkpoint load, sync
    every persisted learner.logs item with this helper; that closes the crash
    window between saving a checkpoint and appending its optimizer log.
    """
    key = tuple(value[k] for k in key_fields)
    matches = [r for r in read_jsonl(path, repair_torn_tail=True)
               if tuple(r[k] for k in key_fields) == key]
    canonical = _without_diagnostics(value, set(ignored_fields))
    if any(_without_diagnostics(r, set(ignored_fields)) != canonical for r in matches):
        raise RecoveryError("conflicting replay log at " + str(path) + ": " + repr(key))
    if matches:
        return False
    append_jsonl(path, value)
    return True


class IdempotentLog:
    """One-worker indexed form of append_idempotent for long training logs."""
    def __init__(self, path, key_fields=("episode",), ignored_fields=("recovered", "unix")):
        self.path = Path(path)
        self.key_fields = tuple(key_fields)
        self.ignored = set(ignored_fields)
        self.bykey = {}
        for row in read_jsonl(self.path, repair_torn_tail=True):
            key = tuple(row[k] for k in self.key_fields)
            canonical = _without_diagnostics(row, self.ignored)
            if key in self.bykey and self.bykey[key] != canonical:
                raise RecoveryError("conflicting historical replay log: " + repr(key))
            self.bykey[key] = canonical

    def append(self, value):
        key = tuple(value[k] for k in self.key_fields)
        canonical = _without_diagnostics(value, self.ignored)
        if key in self.bykey:
            if self.bykey[key] != canonical:
                raise RecoveryError("conflicting replay log: " + repr(key))
            return False
        append_jsonl(self.path, value)
        self.bykey[key] = canonical
        return True


def _identity_name(identity):
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", identity):
        raise RecoveryError("unsafe run identity")
    return identity


def verify_artifacts(artifacts):
    for item in artifacts:
        path = Path(item["path"])
        if not path.is_file() or file_sha(path) != item["sha"]:
            raise RecoveryError("required artifact missing or changed: " + str(path))


def _check_raw_path(out, identity, row):
    path = Path(row["raw_path"]).resolve()
    if not path.is_relative_to((Path(out) / "raw").resolve()) or path.name != identity + ".json.gz":
        raise RecoveryError("raw path escapes this run or has a different identity: " + identity)
    return path


def verify_row(row, expected_request_sha=None):
    """Validate disk bytes and their recorded physical/metrics proof."""
    path = Path(row["raw_path"])
    if not path.is_file() or file_sha(path) != row["raw_sha"]:
        raise RecoveryError("raw missing or SHA changed: " + row["identity"])
    with gzip.open(path, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    proof = raw.get("physical_audit", {})
    required = ("legal_events", "AVAILABLE", "response_separate", "no_future_input",
                "max2", "energy_heat_balance")
    if row.get("physical_PASS") is not True or any(proof.get(k) is not True for k in required):
        raise RecoveryError("physical proof absent or failed: " + row["identity"])
    if raw.get("metrics") != row["metrics"]:
        raise RecoveryError("raw/row metrics differ: " + row["identity"])
    if expected_request_sha is not None and raw.get("request_sha") != expected_request_sha:
        raise RecoveryError("raw/START requests differ: " + row["identity"])
    if raw.get("environment_seed") != row["environment_seed"]:
        raise RecoveryError("raw/row environment seed differs: " + row["identity"])
    verify_artifacts(row.get("required_artifacts", []))
    return raw


def assert_fresh(identity, rows, receipts):
    """Before START: an earlier attempt can be recovered, never simulated again."""
    committed = identity in rows if isinstance(rows, dict) else any(r["identity"] == identity for r in rows)
    if committed:
        raise RecoveryError("identity already committed: " + identity)
    relevant = receipts.get(identity, []) if isinstance(receipts, dict) else receipts
    if any(r.get("identity") == identity and r.get("event") == "START" for r in relevant):
        raise RecoveryError("identity already consumed by prior START: " + identity)


def commit_environment(out, row, raw, artifacts=(), rows=None, receipts=None,
                       receipt_index=None):
    """Prepare SHA-bound raw + optional rollout, then append row and COMPLETE.

    Caller must append a durable START first. For training, persist the causal
    rollout and its action_rng_after *before* calling this function, and pass
    its path/SHA in artifacts. The manifest closes raw-before-row/receipt gaps.
    For large runs pass rows=store.byid, receipts=store.receipts, and an
    identity-to-receipt-list receipt_index. No full journal reads or scans then
    occur. Passed receipts/index are updated by this function; caller adds the
    returned row to its row list/index.
    """
    out = Path(out)
    row = dict(row)
    identity = _identity_name(row["identity"])
    if rows is None:
        rows = read_jsonl(out / "rows.jsonl", repair_torn_tail=True)
    if receipts is None:
        receipts = read_jsonl(out / "receipts.jsonl", repair_torn_tail=True)
    committed = identity in rows if isinstance(rows, dict) else any(r["identity"] == identity for r in rows)
    if committed:
        raise RecoveryError("refusing duplicate environment commit: " + identity)
    relevant = receipt_index.get(identity, []) if receipt_index is not None else receipts
    starts = [r for r in relevant if r.get("identity") == identity and r.get("event") == "START"]
    if len(starts) != 1:
        raise RecoveryError("prepared commit requires exactly one START: " + identity)
    if any(r.get("identity") == identity and r.get("event") in ("FAIL", "COMPLETE") for r in relevant):
        raise RecoveryError("cannot prepare after a terminal receipt: " + identity)
    def emit(receipt):
        append_jsonl(out / "receipts.jsonl", receipt)
        receipts.append(receipt)
        if receipt_index is not None:
            receipt_index.setdefault(identity, []).append(receipt)
    final_path = _check_raw_path(out, identity, row)
    if final_path.exists():
        raise RecoveryError("refusing raw overwrite: " + str(final_path))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(final_path.name + ".prepared")
    if temp_path.exists():
        raise RecoveryError("prepared raw already exists; reconcile first: " + identity)
    verify_artifacts(artifacts)
    with temp_path.open("wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, compresslevel=3, mtime=0) as z:
            z.write(_json_bytes(raw))
        f.flush()
        os.fsync(f.fileno())
    row["raw_sha"] = file_sha(temp_path)
    if artifacts:
        row["required_artifacts"] = list(artifacts)
    manifest_path = out / "commits" / (identity + ".json")
    if manifest_path.exists():
        raise RecoveryError("commit manifest already exists; reconcile first: " + identity)
    manifest = dict(version=1, identity=identity, row=row,
                    temporary_raw_path=str(temp_path), request_sha=starts[0]["request_sha"])
    _write_atomic(manifest_path, _json_bytes(manifest))
    emit(dict(event="PREPARED", identity=identity,
        unix=time.time(), manifest_path=str(manifest_path), manifest_sha=file_sha(manifest_path)))
    os.replace(temp_path, final_path)
    verify_row(row, starts[0]["request_sha"])
    append_jsonl(out / "rows.jsonl", row)
    emit(dict(event="COMPLETE", identity=identity,
        unix=time.time(), raw_sha=row["raw_sha"], wall_s=row["wall_s"]))
    return row


def reconcile(out, verify_existing=True):
    """Finish valid prepared commits or missing COMPLETEs; retain all old FAILs.

    Uncommitted STARTs/FAILs remain consumed. Orphan raw without a prepared
    manifest is reported, never accepted as a fresh run or assigned a new SHA.
    Returns authoritative rows/receipts and a compact recovery report.
    """
    out = Path(out)
    rows_path, receipts_path = out / "rows.jsonl", out / "receipts.jsonl"
    rows = read_jsonl(rows_path, repair_torn_tail=True)
    receipts = read_jsonl(receipts_path, repair_torn_tail=True)
    byid = {}
    for row in rows:
        identity = row["identity"]
        if identity in byid:
            raise RecoveryError("duplicate row identity: " + identity)
        byid[identity] = row
    starts = {}
    completes = {}
    prepared = {}
    for receipt in receipts:
        identity = receipt.get("identity")
        event = receipt.get("event")
        if event == "START":
            starts.setdefault(identity, []).append(receipt)
        elif event == "COMPLETE":
            completes.setdefault(identity, []).append(receipt)
        elif event == "PREPARED":
            prepared.setdefault(identity, []).append(receipt)
    recovered_rows = []
    recovered_receipts = []
    for path in sorted((out / "commits").glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        identity = _identity_name(manifest["identity"])
        if path.stem != identity or manifest.get("version") != 1:
            raise RecoveryError("invalid commit manifest: " + str(path))
        for receipt in prepared.get(identity, []):
            if receipt["manifest_sha"] != file_sha(path):
                raise RecoveryError("prepared manifest SHA changed: " + identity)
        if len(starts.get(identity, [])) != 1:
            raise RecoveryError("prepared identity lacks unique START: " + identity)
        row = manifest["row"]
        if row["identity"] != identity or manifest["request_sha"] != starts[identity][0]["request_sha"]:
            raise RecoveryError("prepared manifest/START differs: " + identity)
        if identity in byid:
            if byid[identity] != row:
                raise RecoveryError("prepared/committed row differs: " + identity)
            continue
        final_path = _check_raw_path(out, identity, row)
        if not final_path.exists():
            temp = Path(manifest["temporary_raw_path"])
            if temp.resolve() != final_path.with_name(final_path.name + ".prepared"):
                raise RecoveryError("prepared temporary path differs: " + identity)
            if not temp.is_file() or file_sha(temp) != row["raw_sha"]:
                raise RecoveryError("prepared raw unavailable or changed: " + identity)
            verify_artifacts(row.get("required_artifacts", []))
            os.replace(temp, final_path)
        verify_row(row, manifest["request_sha"])
        append_jsonl(rows_path, row)
        rows.append(row)
        byid[identity] = row
        recovered_rows.append(identity)
    for identity, row in byid.items():
        if len(starts.get(identity, [])) != 1:
            raise RecoveryError("committed row lacks unique START: " + identity)
        if verify_existing or identity not in completes:
            verify_row(row, starts[identity][0]["request_sha"])
        if len(completes.get(identity, [])) > 1:
            raise RecoveryError("duplicate COMPLETE receipt: " + identity)
        if identity in completes:
            if completes[identity][0]["raw_sha"] != row["raw_sha"]:
                raise RecoveryError("row/COMPLETE SHA differs: " + identity)
            continue
        receipt = dict(event="COMPLETE", identity=identity, unix=time.time(),
                       raw_sha=row["raw_sha"], wall_s=row["wall_s"], recovered=True)
        append_jsonl(receipts_path, receipt)
        receipts.append(receipt)
        recovered_receipts.append(identity)
    if any(identity not in byid for identity in completes):
        raise RecoveryError("COMPLETE receipt has no valid recoverable row")
    known_raw = {str(Path(r["raw_path"]).resolve()) for r in rows}
    orphan_raw = [str(p) for p in (out / "raw").rglob("*.json.gz")
                  if str(p.resolve()) not in known_raw]
    consumed = sorted(identity for identity in starts if identity not in byid)
    return dict(rows=rows, receipts=receipts, recovered_rows=recovered_rows,
                recovered_receipts=recovered_receipts, consumed_uncommitted=consumed,
                untrusted_orphan_raw=orphan_raw)
