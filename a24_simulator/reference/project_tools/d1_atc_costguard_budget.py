"""Immutable isolated worker budgets; starts count, old budgets never reopened."""
import contextlib,hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path

TASK="ATC-COST-GUARD-13"
PROFILES={"model":dict(environments=None,learning=None,active_seconds=72000,reserve_seconds=300),
          "control":dict(environments=None,learning=0,active_seconds=21600,reserve_seconds=300)}
AGGREGATE=dict(environments=None,learning=None,model_workers=1,control_workers=1)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text("utf8"))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",encoding="utf8",newline="\n") as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write("\n");f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

class ControlledStop(Exception):
    """Reserve stop before consuming a new environment, never an environment failure."""


class Budget:
    def __init__(self,folder):
        self.folder=Path(folder);self.reg=read(self.folder/"budget.json");self.kind=self.reg["kind"]
        if self.reg["task"]!=TASK or self.reg["caps"]!=PROFILES[self.kind]:raise ValueError("immutable worker budget")
        self.caps=PROFILES[self.kind];self.clock=read(self.folder/"clock.json")
        self.rows=[json.loads(x) for x in (self.folder/"executions.jsonl").read_text("utf8").splitlines()] if (self.folder/"executions.jsonl").exists() else []
        self.start=None
    @classmethod
    def register(cls,folder,kind,metadata):
        folder=Path(folder)
        if folder.exists():raise FileExistsError("inspect/resume; never reset worker")
        folder.mkdir(parents=True)
        write(folder/"budget.json",dict(task=TASK,kind=kind,caps=PROFILES[kind],registered_utc=datetime.now(timezone.utc).isoformat(),metadata=metadata,device=0,S26=0))
        write(folder/"clock.json",dict(active_seconds=0.,running_since=None))
        return cls(folder)
    def append(self,row):
        with (self.folder/"executions.jsonl").open("a",encoding="utf8",newline="\n") as f:
            f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+"\n");f.flush();os.fsync(f.fileno())
        self.rows.append(row)
    def active(self):return self.clock["active_seconds"]+(time.monotonic()-self.start if self.start is not None else 0.)
    def used(self):
        starts=[r for r in self.rows if r["event"]=="start"]
        return dict(environments=len(starts),learning=sum(r["learning"] for r in starts),failed=sum(r["event"]=="failure" for r in self.rows),active_seconds=self.active(),caps=self.caps,device=0,S26=0)
    @contextlib.contextmanager
    def session(self):
        if self.clock["running_since"] is not None:raise RuntimeError("unclosedclock needs crashaudit")
        lock=self.folder/"owner.lock"
        with lock.open("x",encoding="utf8") as f:f.write(str(os.getpid()))
        self.start=time.monotonic();self.clock["running_since"]=datetime.now(timezone.utc).isoformat();write(self.folder/"clock.json",self.clock)
        try:yield self
        finally:
            self.clock.update(active_seconds=self.active(),running_since=None);self.start=None
            write(self.folder/"clock.json",self.clock);write(self.folder/"consumption.json",self.used());lock.unlink()
    def can_begin(self,phase):
        import shutil
        meta=self.reg["metadata"]
        reserve=0 if phase=="confirmation" else meta.get("final_reserve_seconds",1800)
        if time.time()>=meta["deadline_unix"]-reserve:return False,"wall_final_reserve"
        if shutil.disk_usage(self.folder).free<8*1024**3:return False,"raw_disk_reserve"
        if (self.folder/"REQUEST_STOP").exists():return False,"requested_boundary_stop"
        return True,None
    @contextlib.contextmanager
    def environment(self,identity,phase,learning=False):
        if self.start is None:raise RuntimeError("environment requires budget session")
        ready,reason=self.can_begin(phase)
        if not ready:raise ControlledStop(reason)
        u=self.used()
        import shutil
        if shutil.disk_usage(self.folder).free<8*1024**3:raise OSError("checkpoint and raw preservation requires 8GiB disk reserve")
        if (self.folder/"REQUEST_STOP").exists():raise InterruptedError("stop at environment boundary")
        if (self.caps["environments"] is not None and u["environments"]>=self.caps["environments"]) or (learning and self.caps["learning"] is not None and u["learning"]>=self.caps["learning"]) or self.active()>=self.caps["active_seconds"]-self.caps["reserve_seconds"]:raise TimeoutError("immutable cap/reserve")
        if any(r["event"]=="start" and r["identity"]==identity for r in self.rows):raise ValueError("consumed identity")
        began=time.perf_counter();cpu=time.process_time()
        self.append(dict(event="start",identity=identity,phase=phase,learning=bool(learning),at_utc=datetime.now(timezone.utc).isoformat()))
        try:yield
        except BaseException as error:
            self.append(dict(event="failure",identity=identity,error=repr(error),seconds=time.perf_counter()-began,cpu_seconds=time.process_time()-cpu));raise
        else:self.append(dict(event="completion",identity=identity,seconds=time.perf_counter()-began,cpu_seconds=time.process_time()-cpu))
        finally:write(self.folder/"consumption.json",self.used())
