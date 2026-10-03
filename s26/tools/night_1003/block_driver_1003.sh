#!/usr/bin/env bash
# Night 1003 EffNet block driver: for each run spec "label|outname|accel|duty" do gate -> launch -> wait -> validate (retry once).
# Reads $ANDROID_SERIAL (never written to files). Optional $WAIT_PID: wait for that orchestrator first and validate $WAIT_OUT.
set -u
cd /c/Users/rhoyo/AndroidStudioProjects/D1Check_v4
H=results/S26_night_1003_host
EFF="--npu-model-path /data/local/tmp/efficientnet_lite0.tflite --npu-model-sha256 6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0 --npu-model-size 18582189 --npu-timed-input-spec lcg-rgb-127-128 --npu-run-only-span"
TAIL="--duration 60 --warmup 20 --repeat 1 --seed 20261003 --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 1800 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
GATEARGS="--npu-input-spec lcg-rgb-127-128 --npu-reference-path /data/local/tmp/efficientnet_lite0.tflite --gpu-profile gpu-fp32-strict-v1"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %z')] $*" | tee -a "$H/block_driver_log.txt"; }

wait_pid() { local pid=$1; while tasklist //FI "PID eq $pid" //FO CSV 2>/dev/null | grep -q '"py.exe"'; do sleep 15; done; }

validate() { # $1 = outname -> prints valid|invalid|missing
  py -X utf8 -c "
import json,sys
try:
    m=json.load(open('results/$1/experiment_manifest.json',encoding='utf-8'))
    r=m['runs'][0]; v=(r.get('validation') or {})
    print('valid' if (r.get('status')=='completed' and v.get('valid')) else 'invalid', r.get('status'), v.get('failed_checks'), r.get('error'))
except Exception as e:
    print('missing', repr(e))
"
}

launch() { # $1 label $2 outname $3 accel $4 duty
  local acc=$3 duty=$4 args
  if [ "$acc" = "CPU" ]; then args="--mode pilot --resources NPU --npu-accelerator CPU $EFF --accuracy-preflight off --duty-cycles $duty $TAIL";
  else args="--mode pilot --resources NPU --npu-accelerator GPU --npu-gpu-precision FP32 $EFF $GATEARGS --accuracy-preflight off --duty-cycles $duty $TAIL"; fi
  out=$(powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PWD/$H/launch_cell_1003.ps1" -Label "$1" -OutName "$2" -Args "$args" 2>&1)
  echo "$out" | sed "s/$ANDROID_SERIAL/<SERIAL>/g"
  echo "$out" | grep -oE "pid=[0-9]+" | tail -1 | cut -d= -f2
}

if [ -n "${WAIT_PID:-}" ]; then
  log "waiting for pid $WAIT_PID ($WAIT_OUT)"; wait_pid "$WAIT_PID"; v=$(validate "$WAIT_OUT"); log "DONE $WAIT_OUT -> $v"
fi

for spec in "$@"; do
  IFS='|' read -r label outname acc duty <<< "$spec"
  attempt=1
  while [ $attempt -le 2 ]; do
    tgt="$outname"; [ $attempt -eq 2 ] && tgt="${outname}_retry"
    log "GATE $label (attempt $attempt)"
    py -X utf8 s26/tools/s26_start_gate.py "$ANDROID_SERIAL" "$label" "$H/gate_log_1003.csv" | tail -1 | tee -a "$H/block_driver_log.txt"
    rc=${PIPESTATUS[0]}
    if [ "$rc" != "0" ]; then log "GATE BLOCKED (rc=$rc) -> stop driver"; exit 2; fi
    pid=$(launch "$label" "$tgt" "$acc" "$duty" | tail -1)
    log "LAUNCHED $label -> $tgt pid=$pid"
    sleep 5; wait_pid "$pid"
    v=$(validate "$tgt"); log "DONE $tgt -> $v"
    case "$v" in valid*) break;; esac
    log "RUN FAILED $label attempt $attempt"
    attempt=$((attempt+1))
  done
  [ $attempt -gt 2 ] && log "MISSING $label (2 attempts failed) -> continue block order"
done
log "DRIVER END"
