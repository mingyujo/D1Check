"""Bound A24 transport recovery; never repeats an ambiguous device mutation."""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
from pathlib import Path
from d1_a24_laptop_control import NativeAdbClient, ValidationError


def read_only_command(args: tuple[str, ...]) -> bool:
    if args[:2] == ("exec-out", "cat"): return True
    if len(args)>2 and args[:2]==("exec-out","run-as") and args[2] in {
        "com.example.d1check.benchmarkrunner.modelprobe","com.example.d1check.benchmarkrunner.a24measurement"}:
        return (len(args)>3 and args[3]=="cat") or args[3:6]==("tar","-cf","-")
    if args[:3]==("shell","settings","get"): return True
    if args[:3]==("shell","pm","path") or args[:2]==("shell","sha256sum"): return True
    if args[:2]==("shell","dumpsys"): return len(args)==3 and args[2] in {"battery","thermalservice"}
    return args[:2] in {("shell", "getprop"), ("shell", "cat"), ("shell", "pidof"), ("shell", "df")}


class ReconnectingAdbClient(NativeAdbClient):
    def __init__(self, adb: str, serial: str, hardware_serial: str, fingerprint: str,
                 log: Path, *, wait_seconds: float = 1200, sleep=time.sleep, clock=time.monotonic,
                 runner=subprocess.run):
        super().__init__(adb, serial)
        self.hardware_serial, self.fingerprint = hardware_serial, fingerprint
        self.log, self.wait_seconds = log, wait_seconds
        self.sleep, self.clock, self.runner = sleep, clock, runner
        self.disconnects = 0

    def _run(self, argv: list[str], input_bytes: bytes | None = None):
        before = time.time_ns(); self.actual_calls += 1
        try:
            timeout = 300 if len(argv)>3 and argv[3] in {"install","push"} else 30
            result = self.runner(argv, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=timeout, check=False)
            record = {"argv":argv,"start_wall_ns":before,"end_wall_ns":time.time_ns(),"exit":result.returncode,
                      "stdout_bytes":len(result.stdout),"stdout_sha256":hashlib.sha256(result.stdout).hexdigest(),
                      "stderr":result.stderr.decode("utf-8",errors="replace")}
        except subprocess.TimeoutExpired:
            record = {"argv":argv,"start_wall_ns":before,"end_wall_ns":time.time_ns(),"timeout_seconds":timeout}
            result = None
        with self.log.open("a",encoding="utf-8") as stream: stream.write(json.dumps(record)+"\n")
        return result

    def reconnect(self) -> None:
        self.disconnects += 1; deadline = self.clock()+self.wait_seconds
        print(json.dumps({"status":"RECONNECT_WAIT","maximum_seconds":self.wait_seconds}),flush=True)
        while self.clock() <= deadline:
            devices = self._run([self.prefix[0],"devices"])
            if devices and devices.returncode == 0:
                for line in devices.stdout.decode(errors="replace").splitlines()[1:]:
                    parts = line.split()
                    if len(parts)<2 or parts[1]!="device": continue
                    prefix=[self.prefix[0],"-s",parts[0]]
                    hardware=self._run(prefix+["shell","getprop","ro.serialno"])
                    fp=self._run(prefix+["shell","getprop","ro.build.fingerprint"])
                    if hardware and fp and hardware.returncode==fp.returncode==0 and \
                        hardware.stdout.decode().strip()==self.hardware_serial and fp.stdout.decode().strip()==self.fingerprint:
                        self.prefix=prefix
                        print(json.dumps({"status":"RECONNECTED_SAME_REGISTERED_A24"}),flush=True); return
            self.sleep(5)
        raise ValidationError("A24 did not reconnect within the authorized20 minutes; preserve attempt")

    def command(self, *args: str, input_bytes: bytes | None = None,
                accepted_codes: tuple[int,...]=(0,), reject_stderr: bool=False) -> bytes:
        result=self._run(self.prefix+list(args),input_bytes)
        if result is None or (result.returncode not in accepted_codes and any(s in result.stderr.lower()
            for s in (b"device offline",b"device not found",b"no devices",b"closed",b"disconnected",b"not found"))):
            # Check physical connectivity; ordinary missing app files are not a disconnect.
            state=self._run(self.prefix+["get-state"])
            if state is None or state.returncode!=0 or state.stdout.strip()!=b"device":
                self.reconnect()
                if not read_only_command(tuple(args)):
                    raise ValidationError("connection recovered after ambiguous mutation; never replay install/push/start/claim")
                result=self._run(self.prefix+list(args),input_bytes)
        if result is None or result.returncode not in accepted_codes:
            raise ValidationError("ADB command failed/timeout; preserve raw and never restart session: "+" ".join(args[:3]))
        if reject_stderr and result.stderr.strip(): raise ValidationError("ADB lookup stderr; cannot infer absent owner")
        return result.stdout

    def sleep_ns(self,nanoseconds:int)->None: self.sleep(nanoseconds/1_000_000_000)
