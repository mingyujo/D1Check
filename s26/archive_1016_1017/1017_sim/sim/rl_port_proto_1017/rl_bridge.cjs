'use strict';
// PROTOTYPE (feasibility only): S26 engine subclass whose choose() asks an external
// Python PPO actor through blocking stdin/stdout JSON lines. Engine physics untouched.
const fs = require('node:fs'), zlib = require('node:zlib'), path = require('node:path');
const ROOT = process.env.S26_ROOT;
const v2 = require(path.join(ROOT, 'src/s26_simulator_v2.cjs'));
const actions = require(path.join(ROOT, 'src/rolling_action_v2.cjs'));

const LANE = { classification_CPU: 'CPU', classification_GPU: 'GPU', classification_NPU: 'NPU', detection_CPU: 'CPU' };
const ROUTE_OF = (task, lane) => task === 'D' ? 'detection_CPU' : 'classification_' + lane;
const NS = 1e9;
let inBuf = '';
function readLine() {
  const b = Buffer.alloc(65536);
  while (!inBuf.includes('\n')) {
    let n;
    try { n = fs.readSync(0, b, 0, b.length, null); } catch (e) { if (e.code === 'EAGAIN') continue; throw e; }
    if (n === 0) throw Error('controller closed');
    inBuf += b.toString('utf8', 0, n);
  }
  const i = inBuf.indexOf('\n'), line = inBuf.slice(0, i); inBuf = inBuf.slice(i + 1); return line;
}
const send = obj => fs.writeSync(1, JSON.stringify(obj) + '\n');

class RLSimulator extends v2.ResourceSimulator {
  constructor(packet, scenario, config) {
    super(packet, scenario, { ...config, policy: v2.OWN_POLICY }); // OWN_POLICY only to get publicNominalModel
    this.rlKey = null; this.lastRelease = { CPU: 0, GPU: 0, NPU: 0 }; this.prevLanes = new Set(); this.myDispatch = []; this.rlDecisions = 0;
  }
  obsForBank() {
    const nom = this.publicNominalModel, AP = this.heldAP, t = this.time;
    const rid = q => 'r' + q.ordinal, task = q => q.task === 'detection' ? 'D' : 'C', pr = q => q.priority === 'urgent' ? 'U' : 'N';
    const queue = this.ready.map(q => ({ request_id: rid(q), task: task(q), priority: pr(q), ordinal: q.ordinal,
      scheduled_arrival_ns: Math.round(q.arrival * NS), deadline_ns: Math.round(q.deadline * NS) }));
    const estimates = {};
    for (const q of this.ready) {
      const e = {}, lanes = task(q) === 'D' ? ['CPU'] : (this.config.action_options?.classification_lanes ?? ['CPU', 'GPU', 'NPU']);
      for (const lane of lanes) {
        const route = ROUTE_OF(task(q), lane), est = actions.estimate(nom, route, AP, Number(this.owners.length > 0), q.priority);
        e[lane] = { occupancy_ns: Math.max(1, Math.round(est.occupied_s * NS)), response_ns: Math.round(est.response_s * NS),
          energy_proxy_j: nom.routes[route].incremental_J_proxy, heat_proxy: nom.routes[route].AP_area_proxy };
      }
      estimates[rid(q)] = e;
    }
    const owners = {};
    for (const o of this.owners) owners[LANE[o.route]] = { request_id: rid(o), task: task(o), priority: pr(o), dispatch_ns: Math.round(o.times.dispatch * NS) };
    const recent = {};
    for (const lane of ['CPU', 'GPU', 'NPU']) recent[lane] = this.myDispatch.filter(d => d.lane === lane && d.t > t - 5).length / 5;
    const hist = { planned_U: 0, planned_N: 0, failed_U: 0, failed_N: 0, responded_U: 0, responded_N: 0 };
    for (const q of [...this.ready, ...this.owners, ...this.done]) hist['planned_' + pr(q)]++;
    for (const q of this.done) { hist['responded_' + pr(q)]++; if (q.response > q.deadline) hist['failed_' + pr(q)]++; }
    const sh = this.sensorTrace.slice(-2), slope = sh.length === 2 && sh[1].time > sh[0].time ? (sh[1].AP - sh[0].AP) / (sh[1].time - sh[0].time) : 0;
    return { now_ns: Math.round(t * NS), queue, owners, estimates,
      last_release_ns: Object.fromEntries(Object.entries(this.lastRelease).map(([k, v]) => [k, Math.round(Math.min(v, t) * NS)])),
      history: hist, wait_used_ns: Math.round(this.waitDose * NS), horizon_ns: 120 * NS,
      sensor: { AP_c: AP, power_w: 0, age_s: Math.max(0, t - this.heldTime), recent_activity: recent, ap_slope_c_s: slope, power_slope_w_s: 0 },
      engine_owner_count: this.owners.length };
  }
  choose() {
    if (!this.ready.length || this.time >= 120 - 1e-9) return null;
    const key = JSON.stringify([this.ready.map(q => q.ordinal), this.owners.map(o => o.ordinal), this.heldTime]);
    if (this.rlKey === key) return null; this.rlKey = key;
    // record releases (owners that disappeared since last call)
    const nowLanes = new Set(this.owners.map(o => LANE[o.route]));
    for (const lane of this.prevLanes) if (!nowLanes.has(lane)) this.lastRelease[lane] = this.time;
    send({ type: 'DECIDE', obs: this.obsForBank() });
    const a = JSON.parse(readLine()); this.rlDecisions++;
    this.decisionTrace.push({ time: this.time, action: a });
    this.prevLanes = nowLanes;
    if (a.kind === 'RESOURCE_WAIT' || a.kind === 'NONE') return null;
    if (a.kind === 'WAIT') {
      if (this.owners.length) throw Error('WAIT with owner (mask contract broken)');
      const dose = Math.min(a.wait_ns / NS, Math.max(0, 2 - this.waitDose)); if (dose <= 0) return null;
      this.waitDose += dose; this.waitUntil = Math.min(120, this.time + dose); this.rlKey = null;
      this.events.push([this.time, 'WAIT_START', null, this.waitUntil - this.time]); return 'WAIT';
    }
    const ordinal = Number(a.request_id.slice(1)), q = this.ready.find(x => x.ordinal === ordinal);
    const route = ROUTE_OF(q.task === 'detection' ? 'D' : 'C', a.route);
    if (!q || !v2.legal(route, this.owners)) throw Error('Invalid RL action ' + JSON.stringify(a));
    this.myDispatch.push({ t: this.time, lane: a.route }); this.prevLanes = new Set([...nowLanes, a.route]);
    return { q, route };
  }
}

const [scenarioId, stream, outFile] = process.argv.slice(2);
const packet = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(ROOT, 'data/engine_packet.json.gz'))));
const scenario = packet.scenarios.find(s => s.id === scenarioId);
const cfg = { phase: 'RESOURCE_DYNAMIC', stream: Number(stream), dt_s: .005, power_dt_s: .025, cost_model: 'FULL', timing_variant: 'CENTRAL', action_options: { allow_wait: true, wait_step_s: .05, wait_cap_s: 2 } };
const t0 = Date.now(), sim = new RLSimulator(packet, scenario, cfg), r = sim.run();
const summary = { scenario: scenarioId, stream: Number(stream), decisions: sim.rlDecisions, wall_s: (Date.now() - t0) / 1000,
  hard_feasible: r.hard_feasible, service: r.service, J_API0_180: r.J_API0_180, AP35_180_mean: r.AP35_180_mean, AP_peak_sampled: r.AP_peak_sampled,
  AP180: r.AP180, wait_s: r.wait_s, unfinished: r.unfinished, route_counts: r.policy_route_counts, curve: r.curve };
fs.writeFileSync(outFile, JSON.stringify(summary));
send({ type: 'DONE', summary: { ...summary, curve: undefined } });
