'use strict';
// A24 rolling+ATC rule (조민규 a24_simulator, rules_no_rl_20261017 'ROLLING_ATC' -> interactive_kernel._rule_action('ATC'))
// ported onto the unmodified S26 engine. Only choose() is overridden (same pattern as ROLLING_ATC_ROUTE_V2 and our RL server).
//
// A24 spec (rules.py SPEC['ROLLING_ATC']):
//   score = log(w/p_occ) - max(deadline - now - p_response, 0) / (2 * mean_p_occ),  w = 2 urgent / 1 normal
//   joint selection over (every ready request) x (every currently free, legal route); mean_p_occ over all those candidates
//   ties: scheduled arrival -> ordinal -> request id, then route by (response, occupancy, route name)
//   no voluntary WAIT, no thermal/energy term in the action, no deadline screen, no future information.
// S26 adaptation (only where the device differs): routes = classification CPU/GPU/NPU, detection CPU;
//   "free" = S26 legal() (max 2 owners, only C_GPU|D_CPU and C_NPU|D_CPU pairs); p_occ / p_response = the S26
//   public nominal estimate (same estimate() the S26 rule uses, peer = 1 if any owner, AP = held public sensor).
const path = require('node:path');
const L = require(process.env.LAB || '/home/claude/work/rlexp/lab.cjs');
const { v2, actions } = L;

const ROUTES_OF = q => q.task === 'detection' ? ['detection_CPU'] : ['classification_CPU', 'classification_GPU', 'classification_NPU'];

function selectA24(obs, nom) {
  const now = obs.time, AP = obs.sensor.AP, peer = Number(obs.owners.length > 0), cands = [];
  for (const q of obs.ready) for (const route of ROUTES_OF(q)) {
    if (!actions.legal(route, obs.owners)) continue;
    const e = actions.estimate(nom, route, AP, peer, q.priority);
    cands.push({ q, route, occ: e.occupied_s, resp: e.response_s });
  }
  if (!cands.length) return null;
  const meanOcc = cands.reduce((s, c) => s + c.occ, 0) / cands.length;
  for (const c of cands) {
    const w = c.q.priority === 'urgent' ? 2 : 1;
    c.score = Math.log(w / Math.max(c.occ, 1e-12)) - Math.max(c.q.deadline - now - c.resp, 0) / (2 * meanOcc);
  }
  cands.sort((a, b) => (b.score - a.score) || (a.q.arrival - b.q.arrival) || (a.q.ordinal - b.q.ordinal)
    || (a.resp - b.resp) || (a.occ - b.occ) || (a.route < b.route ? -1 : a.route > b.route ? 1 : 0));
  return cands[0];
}

class A24ATCSimulator extends v2.ResourceSimulator {
  constructor(packet, scenario, config) { super(packet, scenario, { ...config, policy: v2.OWN_POLICY }); this.a24Trace = 0; }
  choose() {
    if (!this.ready.length || this.time >= 120 - 1e-9) return null;
    const obs = this.publicObservation(), c = selectA24(obs, this.publicNominalModel);
    if (!c) return null;
    const q = this.ready.find(x => x.ordinal === c.q.ordinal);
    if (!q || !v2.legal(c.route, this.owners)) throw Error('A24 port chose an illegal action');
    this.a24Trace++;
    return { q, route: c.route };
  }
}

function runA24(load, stream) {
  const sc = L.scenario(load), t0 = Date.now();
  const r = new A24ATCSimulator(L.packet(), sc, L.CFG(stream)).run();
  const late = r.requests.filter(q => q.response > q.deadline + 1e-9).length;
  if (r.service.all.on_time + late + r.unfinished !== r.service.all.planned) throw Error('conservation');
  return L.summarize(r, sc, { policy: 'ATC_A24', stream, wall_s: (Date.now() - t0) / 1000 });
}

module.exports = { selectA24, A24ATCSimulator, runA24 };

if (require.main === module) {
  const fs = require('node:fs');
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), out = process.argv[3];
  for (const j of jobs) {
    let o; try { o = runA24(j.load, j.stream); } catch (e) { o = { policy: 'ATC_A24', stream: j.stream, load: j.load, error: String(e) }; }
    fs.appendFileSync(out, JSON.stringify({ ...o, load: j.load }) + '\n');
  }
}
