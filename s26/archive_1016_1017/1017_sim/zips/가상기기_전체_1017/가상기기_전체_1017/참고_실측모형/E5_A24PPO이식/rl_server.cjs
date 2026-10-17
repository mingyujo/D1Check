'use strict';
// Persistent S26 engine server for an external PPO actor (A24 learner, unmodified).
// Protocol (JSON lines): python -> {"cmd":"run","load":...,"stream":n} ; node -> {"type":"DECIDE","obs":...}* -> python {"kind":...}
// -> node {"type":"DONE","summary":...}. Engine physics untouched; only choose() is overridden (same pattern as ROLLING_ATC_ROUTE_V2).
const fs = require('node:fs');
const L = require('./lab.cjs');
const { v2, actions, NS } = L;
const LANE = { classification_CPU: 'CPU', classification_GPU: 'GPU', classification_NPU: 'NPU', detection_CPU: 'CPU' };
const ROUTE_OF = (task, lane) => task === 'D' ? 'detection_CPU' : 'classification_' + lane;
const QUEUE_CAP = 512; // A24 bridge contract; oldest-first truncation is registered (PREREG §3)
const WAIT_CAP_S = 2;  // S26 registered wait cap

let inBuf = '';
function readLine() {
  const b = Buffer.alloc(1 << 16);
  while (!inBuf.includes('\n')) {
    let n; try { n = fs.readSync(0, b, 0, b.length, null); } catch (e) { if (e.code === 'EAGAIN') continue; throw e; }
    if (n === 0) return null;
    inBuf += b.toString('utf8', 0, n);
  }
  const i = inBuf.indexOf('\n'), line = inBuf.slice(0, i); inBuf = inBuf.slice(i + 1); return line;
}
const send = o => fs.writeSync(1, JSON.stringify(o) + '\n');

class RLSimulator extends v2.ResourceSimulator {
  constructor(packet, scenario, config) {
    super(packet, scenario, { ...config, policy: v2.OWN_POLICY });
    this.rlKey = null; this.lastRelease = { CPU: 0, GPU: 0, NPU: 0 }; this.prevLanes = new Set(); this.myDispatch = [];
    this.stats = { decisions: 0, multi_legal: 0, dispatch: 0, wait: 0, resource_wait: 0, truncated: 0 };
  }
  obs() {
    const nom = this.publicNominalModel, AP = this.heldAP, t = this.time;
    const rid = q => 'r' + q.ordinal, task = q => q.task === 'detection' ? 'D' : 'C', pr = q => q.priority === 'urgent' ? 'U' : 'N';
    let ready = this.ready.slice().sort((a, b) => a.arrival - b.arrival || a.ordinal - b.ordinal);
    if (ready.length > QUEUE_CAP) { ready = ready.slice(0, QUEUE_CAP); this.stats.truncated++; }
    const queue = ready.map(q => ({ request_id: rid(q), task: task(q), priority: pr(q), ordinal: q.ordinal,
      scheduled_arrival_ns: Math.round(q.arrival * NS), deadline_ns: Math.round(q.deadline * NS) }));
    const estimates = {}, peer = Number(this.owners.length > 0);
    for (const q of ready) {
      const e = {};
      for (const lane of (task(q) === 'D' ? ['CPU'] : ['CPU', 'GPU', 'NPU'])) {
        const route = ROUTE_OF(task(q), lane), est = actions.estimate(nom, route, AP, peer, q.priority);
        e[lane] = { occupancy_ns: Math.max(1, Math.round(est.occupied_s * NS)), response_ns: Math.min(Math.round(est.response_s * NS), Math.max(1, Math.round(est.occupied_s * NS))),
          energy_proxy_j: nom.routes[route].incremental_J_proxy };
      }
      estimates[rid(q)] = e;
    }
    const owners = {};
    for (const o of this.owners) owners[LANE[o.route]] = { request_id: rid(o), task: task(o), priority: pr(o), dispatch_ns: Math.round(o.times.dispatch * NS) };
    const recent = {};
    for (const lane of ['CPU', 'GPU', 'NPU']) recent[lane] = this.myDispatch.filter(d => d.lane === lane && d.t > t - 5).length / 5;
    const hist = { planned_U: 0, planned_N: 0, failed_U: 0, failed_N: 0, responded_U: 0, responded_N: 0 };
    for (const q of [...this.ready, ...this.owners, ...this.done]) hist['planned_' + pr(q)]++;
    for (const q of this.done) { hist['responded_' + pr(q)]++; if (q.response > q.deadline + 1e-9) hist['failed_' + pr(q)]++; }
    const sh = this.sensorTrace.slice(-2), slope = sh.length === 2 && sh[1].time > sh[0].time ? (sh[1].AP - sh[0].AP) / (sh[1].time - sh[0].time) : 0;
    return { now_ns: Math.round(t * NS), queue, owners, estimates,
      last_release_ns: Object.fromEntries(Object.entries(this.lastRelease).map(([k, v]) => [k, Math.round(Math.min(v, t) * NS)])),
      history: hist, wait_used_ns: Math.round(this.waitDose * NS), wait_cap_ns: WAIT_CAP_S * NS, horizon_ns: 120 * NS,
      sensor: { AP_c: AP, power_w: 0, age_s: Math.max(0, t - this.heldTime), recent_activity: recent, ap_slope_c_s: slope, power_slope_w_s: 0 },
      engine_owner_count: this.owners.length };
  }
  choose() {
    if (!this.ready.length || this.time >= 120 - 1e-9) return null;
    const key = JSON.stringify([this.ready.map(q => q.ordinal), this.owners.map(o => o.ordinal), this.heldTime]);
    if (this.rlKey === key) return null; this.rlKey = key;
    const nowLanes = new Set(this.owners.map(o => LANE[o.route]));
    for (const lane of this.prevLanes) if (!nowLanes.has(lane)) this.lastRelease[lane] = this.time;
    this.prevLanes = nowLanes;
    send({ type: 'DECIDE', obs: this.obs() });
    const a = JSON.parse(readLine()); this.stats.decisions++; if (a.legal_count > 1) this.stats.multi_legal++;
    if (a.kind === 'RESOURCE_WAIT' || a.kind === 'NONE') { this.stats.resource_wait++; return null; }
    if (a.kind === 'WAIT') {
      if (this.owners.length) throw Error('WAIT with owner (mask contract broken)');
      const dose = Math.min(a.wait_ns / NS, WAIT_CAP_S - this.waitDose);
      if (!(dose > 1e-12)) throw Error('WAIT beyond registered cap (mask contract broken)');
      this.stats.wait++; this.waitDose += dose; this.waitUntil = Math.min(120, this.time + dose); this.rlKey = null;
      this.events.push([this.time, 'WAIT_START', null, this.waitUntil - this.time]); return 'WAIT';
    }
    const ordinal = Number(a.request_id.slice(1)), q = this.ready.find(x => x.ordinal === ordinal);
    if (!q) throw Error('RL chose a non-ready request');
    const route = ROUTE_OF(q.task === 'detection' ? 'D' : 'C', a.route);
    if (!v2.legal(route, this.owners)) throw Error('Illegal RL route ' + route);
    this.stats.dispatch++; this.myDispatch.push({ t: this.time, lane: a.route }); this.prevLanes = new Set([...nowLanes, a.route]);
    return { q, route };
  }
}

for (;;) {
  const line = readLine(); if (line === null) break;
  const cmd = JSON.parse(line);
  if (cmd.cmd === 'rule') { send({ type: 'DONE', summary: L.runRule(cmd.policy, cmd.load, cmd.stream) }); continue; }
  const sc = L.scenario(cmd.load), t0 = Date.now();
  const sim = new RLSimulator(L.packet(), sc, L.CFG(cmd.stream)), r = sim.run();
  // conservation: every planned request is on-time, late, or unfinished exactly once
  const late = r.requests.filter(q => q.response > q.deadline + 1e-9).length, on = r.service.all.on_time;
  if (on + late + r.unfinished !== r.service.all.planned) throw Error('conservation: on+late+unfinished != planned');
  send({ type: 'DONE', summary: L.summarize(r, sc, { policy: 'RL', stream: cmd.stream, wall_s: (Date.now() - t0) / 1000, rl_stats: sim.stats }) });
}
