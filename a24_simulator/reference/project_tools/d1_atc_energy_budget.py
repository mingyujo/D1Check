"""One isolated serial worker; environment-boundary wall/disk stops."""
import contextlib
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.d1_atc_waitlong_budget import digest, read, write, ControlledStop

TASK = "ATC-ENERGY-GUARD-13"
CAPS = dict(environments=None, learning=None, active_seconds=21600, reserve_seconds=0)


class Budget:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.reg = read(self.folder / "budget.json")
        if self.reg["task"] != TASK or self.reg["caps"] != CAPS:
            raise ValueError("immutable energy budget")
        self.caps = CAPS
        self.clock = read(self.folder / "clock.json")
        path = self.folder / "executions.jsonl"
        self.rows = [__import__("json").loads(line) for line in path.read_text("utf8").splitlines()] if path.exists() else []
        self.start = None

    @classmethod
    def register(cls, folder, metadata):
        folder = Path(folder)
        if folder.exists():
            raise FileExistsError("never reset registered/consumed worker")
        folder.mkdir(parents=True)
        write(folder / "budget.json", dict(task=TASK, caps=CAPS, metadata=metadata,
              registered_utc=datetime.now(timezone.utc).isoformat(), workers=1, device=0, S26=0))
        write(folder / "clock.json", dict(active_seconds=0., running_since=None))
        return cls(folder)

    def active(self):
        return self.clock["active_seconds"] + (time.monotonic() - self.start if self.start is not None else 0.)

    def used(self):
        starts = [row for row in self.rows if row["event"] == "start"]
        return dict(environments=len(starts), learning=sum(row["learning"] for row in starts),
                    failed=sum(row["event"] == "failure" for row in self.rows), active_seconds=self.active(),
                    caps=CAPS, model_workers=1, device=0, S26=0)

    def append(self, row):
        import json
        with (self.folder / "executions.jsonl").open("a", encoding="utf8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush(); os.fsync(stream.fileno())
        self.rows.append(row)

    @contextlib.contextmanager
    def session(self):
        if self.clock["running_since"] is not None:
            raise RuntimeError("unclosed clock requires crash audit")
        lock = self.folder / "owner.lock"
        with lock.open("x", encoding="utf8") as stream:
            stream.write(str(os.getpid()))
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

    def can_begin(self, phase):
        meta = self.reg["metadata"]
        reserve = 0 if phase == "confirmation" else meta["final_reserve_seconds"]
        if time.time() >= meta["deadline_unix"] - reserve:
            return False, "wall_final_reserve"
        if shutil.disk_usage(self.folder).free < 8 * 1024 ** 3:
            return False, "raw_disk_reserve"
        if (self.folder / "REQUEST_STOP").exists():
            return False, "requested_boundary_stop"
        return True, None

    @contextlib.contextmanager
    def environment(self, identity, phase, learning=False):
        if self.start is None:
            raise RuntimeError("environment requires exclusive worker session")
        ready, reason = self.can_begin(phase)
        if not ready:
            raise ControlledStop(reason)
        if any(row["event"] == "start" and row["identity"] == identity for row in self.rows):
            raise ValueError("consumed identity")
        began, cpu = time.perf_counter(), time.process_time()
        self.append(dict(event="start", identity=identity, phase=phase, learning=bool(learning),
                         at_utc=datetime.now(timezone.utc).isoformat()))
        try:
            yield
        except BaseException as error:
            self.append(dict(event="failure", identity=identity, error=repr(error),
                             seconds=time.perf_counter() - began, cpu_seconds=time.process_time() - cpu))
            raise
        else:
            self.append(dict(event="completion", identity=identity, seconds=time.perf_counter() - began,
                             cpu_seconds=time.process_time() - cpu))
        finally:
            write(self.folder / "consumption.json", self.used())
