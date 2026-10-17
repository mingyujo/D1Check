'use strict';
// S26 RL experiment lab (our code; 조민규 engine files are required read-only, never modified).
const fs = require('node:fs'), zlib = require('node:zlib'), path = require('node:path');
const ROOT = process.env.S26_ROOT || '/home/claude/work/s26/s26_simulator';
const FAIR = path.join(ROOT, 'experiments/fair_resource_v1/source');
const ENG = process.env.S26_ENGINE_DIR || path.join(ROOT, 'src');
const v2 = require(path.join(ENG, 's26_simulator_v2.cjs'));
const fair = require(path.join(process.env.S26_ENGINE_DIR || FAIR, 'fair_simulator.cjs'));
const actions = require(path.join(ENG, 'rolling_action_v2.cjs'));
const NS = 1e9;

let PACKET = null;
function packet() {
  if (PACKET) return PACKET;
  PACKET = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(ROOT, 'data/engine_packet.json.gz'))));
  const VD = JSON.parse(process.env.S26_VD_JSON || '{}');
  if (VD.npu_ap_coef !== undefined) { // VIRTUAL DEVICE: NPU inference slowdown per 10 C (log scale); engine and policy read the same value
    const j = PACKET.timing.spec.labels.indexOf('AP:classification_NPU'); if (j < 0) throw Error('label');
    PACKET.timing.coef[j] = VD.npu_ap_coef; }
  return PACKET;
}

// Load = {kind:'R21', slot} uses the sealed request table as-is.
// Load = {kind:'GEN', slot, dur, gap, mixC, mixD, shape} builds bundles like M128/SMOOTH128:
// one bundle (mixC classification urgent 0.8 s + mixD detection normal 2 s) every `gap` s from 35 s, for `dur` s.
// Classification/detection order inside a bundle follows the M128 pattern (C..C D repeated).
function scenario(load) {
  const base = packet().scenarios.find(s => s.id === load.slot);
  if (!base) throw Error('unknown slot ' + load.slot);
  if (load.kind === 'R21') return base;
  const n = Math.round(load.dur / load.gap), per = load.mixC + load.mixD, reqs = [];
  const pattern = []; // interleave D evenly: e.g. 6C2D -> CCCDCCCD, 5C3D -> CCDCCDCD
  for (let i = 0; i < per; i++) pattern.push(Math.floor((i + 1) * load.mixD / per) > Math.floor(i * load.mixD / per) ? 'D' : 'C');
  for (let b = 0; b < n; b++) for (let i = 0; i < per; i++) {
    const t = 35 + b * load.gap + (load.shape === 'smooth' ? i * load.gap / per : 0);
    const d = pattern[i] === 'D';
    reqs.push({ ordinal: reqs.length, offset_ns: Math.round(t * NS), task_id: d ? 'detection' : 'classification', priority: d ? 'normal' : 'urgent', deadline_ms: d ? 2000 : 800 });
  }
  return { ...base, id: `GEN_${load.slot}_${load.dur}s_${load.gap}_${load.mixC}C${load.mixD}D_${load.shape}`, requests: reqs, policy_args: null, role: 'GENERATED_LOAD_EXTRAPOLATION' };
}

const CFG = (stream, extra = {}) => ({ phase: 'RESOURCE_DYNAMIC', stream, dt_s: .005, power_dt_s: .025, cost_model: 'FULL', timing_variant: 'CENTRAL',
  action_options: { classification_routes: ['classification_CPU', 'classification_GPU', 'classification_NPU'], allow_wait: true, wait_step_s: .05, wait_cap_s: 2 }, ...extra });

function summarize(r, sc, extra = {}) {
  const s = r.service, ap0 = sc.context.initial_context.targets.AP.anchor;
  const AP0 = ap0.AP_c ?? ap0.AP;
  let heat = 0; const c = r.curve || [];
  for (let i = 1; i < c.length; i++) { const a = c[i - 1], b = c[i]; const ta = a.t ?? a.time ?? a[0], tb = b.t ?? b.time ?? b[0], pa = a.AP ?? a.ap ?? a[1], pb = b.AP ?? b.ap ?? b[1];
    heat += (tb - ta) * (Math.max(pa - AP0, 0) + Math.max(pb - AP0, 0)) / 2; }
  return { scenario: sc.id, planned: s.all.planned, on_time: s.all.on_time, completed: s.all.completed,
    U_planned: s.urgent.planned, U_on: s.urgent.on_time, N_planned: s.normal.planned, N_on: s.normal.on_time,
    unfinished: r.unfinished, censored: r.right_censored_at150, J: r.J_API0_180, AP_mean: r.AP35_180_mean, AP_peak: r.AP_peak_sampled,
    AP180: r.AP180, heat_area: heat, wait_s: r.wait_s, routes: r.policy_route_counts ?? null, ...extra };
}

const RULES = {
  RULE: (sc, st) => new v2.Simulator(packet(), sc, CFG(st, { policy: 'ROLLING_ATC_ROUTE_V2' })),
  RULE_NOWAIT: (sc, st) => new v2.Simulator(packet(), sc, CFG(st, { policy: 'ROLLING_ATC_ROUTE_V2', action_options: { ...CFG(st).action_options, allow_wait: false } })),
  FIFO_FREE: (sc, st) => new fair.Simulator(packet(), sc, CFG(st, { policy: 'FIFO_FREE_ROUTE_V1' })),
  EDF_FREE: (sc, st) => new fair.Simulator(packet(), sc, CFG(st, { policy: 'EDF_FREE_ROUTE_V1' })),
  FIFO_PAIR_CN: (sc, st) => new v2.Simulator(packet(), sc, CFG(st, { policy: 'FIFO_PAIR_CN_V1' })),
  FIFO_PAIR_CG: (sc, st) => new v2.Simulator(packet(), sc, CFG(st, { policy: 'FIFO_PAIR_CG_V1' })),
};
function runRule(name, load, stream) {
  const sc = scenario(load), t = Date.now(), sim = RULES[name](sc, stream), r = sim.run();
  return summarize(r, sc, { policy: name, stream, wall_s: (Date.now() - t) / 1000 });
}

module.exports = { packet, scenario, CFG, summarize, runRule, RULES, v2, actions, NS };

if (require.main === module) {
  // node lab.cjs '<json list of {policy, load, stream}>' -> JSON lines
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  for (const j of jobs) { let out; try { out = runRule(j.policy, j.load, j.stream); } catch (e) { out = { policy: j.policy, stream: j.stream, load: j.load, error: String(e) }; }
    process.stdout.write(JSON.stringify({ ...out, load: j.load }) + '\n'); }
}
