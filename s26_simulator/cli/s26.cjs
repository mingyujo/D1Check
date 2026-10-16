#!/usr/bin/env node
'use strict';
const { fs, path, ROOT, json, flag } = require('../scripts/io.cjs');
const http = require('node:http');
function replay(args) {
  const comparison = flag(args, '--comparison', 'legacy');
  if (comparison === 'fair-resource-v1') {
    const d = json(path.join(ROOT, 'experiments/fair_resource_v1/results/SUMMARY.json'));
    const policy = flag(args, '--policy', 'ALL'), bank = flag(args, '--bank', 'ALL');
    if (!['ALL','M128','SMOOTH128'].includes(bank)) throw Error('Unknown bank');
    const a = (bank === 'ALL' ? d.summaries : d.strata.filter(x => x.bank === bank)).filter(x => policy === 'ALL' || x.policy === policy);
    if (!a.length) throw Error('No stored fair comparison rows');
    const result = {mode:'AUDITED_SAME_RESOURCE_STORED_REPLAY',new_simulator_instances:0,new_training:0,
      results:a.map(x => ({policy:x.policy,bank,cases:x.cases,hard_feasible_cases:x.hard_feasible,on_time_rate:x.on_time_rate,
        API_J_mean:x.J.mean,AP_C_mean:x.AP.mean,route_counts:x.route_counts})),
      contrasts:bank === 'ALL' ? d.contrasts : [],limitation:d.limitation};
    console.log(JSON.stringify(result,null,2));return result.results;
  }
  if (comparison !== 'legacy') throw Error('Unknown stored comparison');
  const d = json(path.join(ROOT, 'data/cached_view_data.json.gz'));
  const policy = flag(args, '--policy', 'ALL'), bank = flag(args, '--bank', 'ALL');
  if (!['ALL', 'M128', 'SMOOTH128'].includes(bank)) throw Error('Bank must be ALL, M128 or SMOOTH128');
  const rows = d.fair.filter(r => (policy === 'ALL' || r.policy === policy) && (bank === 'ALL' || r.arm.startsWith(bank)));
  if (!rows.length) throw Error('No stored rows for policy/bank');
  const result = [...new Set(rows.map(r => r.policy))].map(p => {
    const a = rows.filter(r => r.policy === p), mean = key => a.reduce((s, r) => s + r[key], 0) / a.length;
    return { policy: p, bank, cases: a.length, hard_feasible_cases: a.filter(r => r.hard_feasible).length,
      API_J_mean: mean('J_API0_180'), AP_C_mean: mean('AP35_180_mean'), unfinished_mean: mean('unfinished'),
      planned: a.reduce((s, r) => s + r.service.all.planned, 0), on_time: a.reduce((s, r) => s + r.service.all.on_time, 0),
      action_space: p === 'ROLLING_ATC_ROUTE_V2' ? 'classification CPU/GPU/NPU automatic' : 'fixed reference; see policy contract' };
  });
  console.log(JSON.stringify({ mode: 'STORED_RESULT_REPLAY', new_simulator_instances: 0, new_training: 0,
    limitation: 'Conditional model predictions; unequal route spaces are not a fair ordering-policy comparison; API J is not externally calibrated', results: result }, null, 2));
  return result;
}
async function main(args) {
  const command = args[0] ?? 'help';
  if (command === 'verify') return console.log(JSON.stringify(require('../scripts/verify.cjs').verify(), null, 2));
  if (command === 'replay') return replay(args.slice(1));
  if (command === 'restore') return require('../scripts/restore-data.cjs').restore(args.slice(1));
  if (command === 'locate') {
    const query = args.slice(1).join(' ').toLowerCase(); if (!query) throw Error('Provide a path substring');
    const { cat } = await require('../scripts/restore-data.cjs').catalog({});
    const matches = cat.files.filter(f => f.path.toLowerCase().includes(query) || f.source.toLowerCase().includes(query));
    return console.log(JSON.stringify(matches, null, 2));
  }
  if (command === 'serve') {
    const port = Number(flag(args, '--port', '8788'));
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw Error('Invalid port');
    const html = fs.readFileSync(path.join(ROOT, 'web/index.html'));
    const server = http.createServer((req, res) => {
      if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); return res.end(); }
      const route = new URL(req.url, 'http://127.0.0.1').pathname;
      if (!['/', '/index.html'].includes(route)) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Content-Length': html.length, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
      res.end(req.method === 'HEAD' ? undefined : html);
    });
    server.on('error', e => { console.error(e.message); process.exitCode = 1; });
    server.listen(port, '127.0.0.1', () => console.log('S26 stored view: http://127.0.0.1:' + port + ' (Ctrl+C to stop)'));
    return server;
  }
  if (command !== 'help' && command !== '--help') throw Error('Unknown command: ' + command);
  console.log('S26 handoff | Node >=20\n  verify\n  replay [--comparison legacy|fair-resource-v1] [--policy ID|ALL] [--bank ALL|M128|SMOOTH128]\n  serve [--port 8788]\n  locate <path substring>\n  restore [--group current|measurements|policy_history|history|all]\nAll commands inspect or restore existing evidence. See HANDOFF.md before new simulation/training.');
}
module.exports = { main, replay };
if (require.main === module) main(process.argv.slice(2)).catch(e => { console.error(e.message); process.exitCode = 1; });
