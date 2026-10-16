"""One append-only desktop task budget; no simulation, phone or training on import."""
import contextlib
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

TASK = "HETERO-DIRECT-PPO-03"
CAPS = dict(environments=5000, learning=3072, A24_learning=3072,
            S26_learning=0, active_seconds=10800, reserve_seconds=600)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Budget:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.reg = read(self.folder / "budget.json")
        if self.reg["task"] != TASK or self.reg["caps"] != CAPS:
            raise ValueError("immutable desktop task budget mismatch")
        self.clock = read(self.folder / "clock.json")
        self.rows = [json.loads(s) for s in (self.folder / "executions.jsonl").read_text("utf-8").splitlines()] if (self.folder / "executions.jsonl").exists() else []
        self.start = None
        self._depth = 0

    @classmethod
    def register(cls, folder, metadata):
        folder = Path(folder)
        if folder.exists():
            raise FileExistsError("task already exists; inspect/resume, never reset")
        folder.mkdir(parents=True)
        write(folder / "budget.json", dict(task=TASK, caps=CAPS,
              registered_utc=datetime.now(timezone.utc).isoformat(), metadata=metadata,
              old_amount512_reopened=False, device_commands=0))
        write(folder / "clock.json", dict(active_seconds=0., running_since=None))
        return cls(folder)

    def append(self, row):
        with (self.folder / "executions.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush(); os.fsync(f.fileno())
        self.rows.append(row)

    def used(self):
        starts = [r for r in self.rows if r["event"] == "start"]
        return dict(environments=len(starts), learning=sum(r["learning"] for r in starts),
                    A24_learning=sum(r["learning"] for r in starts if r["device"] == "A24"),
                    S26_learning=sum(r["learning"] for r in starts if r["device"] == "S26"),
                    failed=sum(r["event"] == "failure" for r in self.rows),
                    active_seconds=self.active(), caps=CAPS, device_commands=0)

    def active(self):
        return self.clock["active_seconds"] + (time.monotonic() - self.start if self.start is not None else 0.)

    @contextlib.contextmanager
    def session(self):
        lock = self.folder / "owner.lock"
        # Do not silently remove a lock or reset an unclosed clock.
        if self.clock["running_since"] is not None:
            raise RuntimeError("unclosed clock requires explicit crash audit")
        with lock.open("x", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        self.start = time.monotonic()
        self.clock["running_since"] = datetime.now(timezone.utc).isoformat()
        write(self.folder / "clock.json", self.clock)
        try:
            yield self
        finally:
            self.clock.update(active_seconds=self.active(), running_since=None)
            self.start = None
            write(self.folder / "clock.json", self.clock)
            write(self.folder / "consumption.json", self.used())
            lock.unlink()

    @contextlib.contextmanager
    def environment(self, identity, phase, learning=False, device="A24"):
        if self.start is None:
            raise RuntimeError("environment requires an active budget session")
        if self._depth:
            yield
            return
        if (self.folder / "REQUEST_STOP").exists():
            raise InterruptedError("REQUEST_STOP at environment boundary")
        used = self.used()
        if self.active() >= CAPS["active_seconds"] - CAPS["reserve_seconds"]:
            raise TimeoutError("immutable saving reserve")
        if used["environments"] >= CAPS["environments"] or (
                learning and (used["learning"] >= CAPS["learning"] or
                              used[device + "_learning"] >= CAPS[device + "_learning"])):
            raise TimeoutError("desktop environment/learning cap")
        if any(r["event"] == "start" and r["identity"] == identity for r in self.rows):
            raise ValueError("consumed identity cannot be collected again")
        start = time.perf_counter(); cpu = time.process_time()
        self.append(dict(event="start", identity=identity, phase=phase,
                         learning=bool(learning), device=device,
                         at_utc=datetime.now(timezone.utc).isoformat()))
        self._depth += 1
        try:
            yield
        except BaseException as error:
            self.append(dict(event="failure", identity=identity, error=repr(error),
                             seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu))
            raise
        else:
            self.append(dict(event="completion", identity=identity,
                             seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu))
        finally:
            self._depth -= 1
            write(self.folder / "consumption.json", self.used())
