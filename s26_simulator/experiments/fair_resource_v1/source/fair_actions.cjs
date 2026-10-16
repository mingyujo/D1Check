'use strict';
const base = require('./rolling_action_v2.cjs');
const POLICIES = ['FIFO_FREE_ROUTE_V1', 'EDF_FREE_ROUTE_V1'];
function select(obs, nom, options, policy) {
  if (!POLICIES.includes(policy)) throw Error('Unsupported fair policy: ' + policy);
  // Exact original nominal candidates, public information and WAIT predicate.
  const all = base.select(obs, nom, options);
  if (all.kind !== 'DISPATCH') return all;
  const allowed = all.candidates.filter(c => c.permitted);
  const eligible = new Set(allowed.map(c => c.ordinal));
  const ordered = obs.ready.filter(q => eligible.has(q.ordinal)).sort((a,b) =>
    (policy === 'EDF_FREE_ROUTE_V1' ? a.deadline-b.deadline : 0) || a.arrival-b.arrival || a.ordinal-b.ordinal);
  if (!ordered.length) return {kind:'NONE', candidates:all.candidates};
  const q = ordered[0], routes = allowed.filter(c => c.ordinal === q.ordinal);
  const rank = routes.slice().sort((a,b) => a.predicted_ready_misses-b.predicted_ready_misses || a.predicted_max_lateness_s-b.predicted_max_lateness_s)[0];
  const best = routes.filter(c => c.predicted_ready_misses === rank.predicted_ready_misses && Math.abs(c.predicted_max_lateness_s-rank.predicted_max_lateness_s)<1e-12)
    .sort((a,b) => a.normalized_energy_heat-b.normalized_energy_heat || a.response_estimate_s-b.response_estimate_s || a.route.localeCompare(b.route))[0];
  return {kind:'DISPATCH', ordinal:best.ordinal, route:best.route, selected:best, candidates:all.candidates,
    reason:policy+' among dispatchable ready requests; shared deadline/energy/heat route allocator'};
}
module.exports = { ...base, POLICIES, select };
