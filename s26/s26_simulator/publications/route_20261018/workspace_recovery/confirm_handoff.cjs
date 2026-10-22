// Local handoff receipt only. Does not execute training, audits, or the simulator.
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto'), cp = require('child_process');
const repo = path.resolve(__dirname, '../D1Check'), root = path.join(repo, 'a24_simulator');
const out = path.join(root, 'results/RL_COST_20261017_01');
const read = p => JSON.parse(fs.readFileSync(p, 'utf8').replace(/^\uFEFF/, ''));
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function local(pin) {
  const original = pin.path.replaceAll('\\', '/'), marker = '/a24_simulator/';
  const at = original.toLowerCase().lastIndexOf(marker);
  if (at < 0) throw Error('Unmapped evidence path');
  const p = path.resolve(root, original.slice(at + marker.length));
  if (!p.startsWith(root + path.sep)) throw Error('Path outside checkout');
  return p;
}
const proof = read(path.join(out, 'FINAL_HANDOFF_PROOF.json'));
const seal = read(path.join(out, 'SELECTION_FROZEN.json'));
const pins = [...Object.values(proof.audits).filter(v => v && v.path), ...proof.evidence, seal.selected.checkpoint];
const links = pins.map(pin => ({file: path.relative(root, local(pin)).replaceAll('\\', '/'),
  sha256: hash(local(pin)), pass: fs.statSync(local(pin)).size === pin.bytes && hash(local(pin)) === pin.sha256}));
if (links.some(v => !v.pass)) throw Error('Published evidence hash mismatch');
const receiptPath = path.join(out, 'receipts.jsonl');
const rows = fs.readFileSync(receiptPath, 'utf8').trim().split(/\r?\n/).map(JSON.parse);
const starts = rows.filter(r => r.event === 'START'), complete = rows.filter(r => r.event === 'COMPLETE');
const ledgerPin = proof.budget.ledgers.find(p => p.path.replaceAll('\\', '/').endsWith('/RL_COST_20261017_01/receipts.jsonl'));
if (!ledgerPin || hash(receiptPath) !== ledgerPin.sha256 || starts.length !== 223 || complete.length !== 223 ||
    new Set(starts.map(r => r.identity)).size !== 223 || rows.some(r => r.event === 'FAIL')) throw Error('Terminal receipt mismatch');
const nn = read(path.join(out, 'NN_AUDIT.json')), saved = read(path.join(out, 'SAVED_AUDIT.json'));
const ui = read(path.join(out, 'UI_QA/RESULT.json')), result = read(path.join(out, 'RESULT.json'));
const head = cp.execFileSync('git', ['rev-parse', 'HEAD'], {cwd: repo, encoding: 'utf8', windowsHide: true}).trim();
if (head !== '51117e2a1139a1532ba20f1efb8916fa335f6f38') throw Error('Unexpected checkout');
const report = {
  schema: 'A24-local-handoff-receipt-v1', checked_at_utc: new Date().toISOString(),
  status: 'PUBLISHED_COMPLETION_CONFIRMED', source_commit: head,
  supersedes: 'RECOVERY_STATUS.json (earlier missing-publication snapshot retained)',
  evidence_links: links, receipt_sha256: hash(receiptPath), START: starts.length, COMPLETE: complete.length, FAIL: 0,
  selected_episode: seal.selected.episode, updates: result.updates, Adam_steps: result.Adam_steps,
  published_audit_results: {NN_status: nn.status, NN_checks: nn.checks,
    saved_status: saved.status, saved_checks: saved.checks, UI_status: ui.status,
    UI_checks: ui.checks, UI_views: ui.views.length},
  DEV_qualified: proof.DEV_qualified, joint_goal_met: proof.nominal_joint_goal,
  interactive_default_replaced: proof.interactive_default_replaced,
  local_scope: 'Latest code, metadata, summaries, report, and selected EP096 checkpoint. Other cost-RL .gz replay files remain available in the pinned GitHub commit and are deliberately sparse.',
  active_runtime_ledger_restored: false, new_environment: 0, new_training: 0, audit_reruns: 0,
  automation_restarted: false, measured_J: null,
  report: path.join(out, 'REPORT.html'),
  next_research_candidate: 'In a separately registered generation, align the local cost prior with the causal 0.9-second history used by reward and evaluation; current results do not establish that this will improve performance.'
};
fs.writeFileSync(path.join(__dirname, 'RECOVERY_COMPLETE.json'), JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify({status: report.status, exact_evidence_links: links.length,
  completed: complete.length, audits_rerun: 0, selected_episode: report.selected_episode}));
