// Read saved files only. Does not import the simulator, restore ledgers, or run Python.
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const root = path.resolve(__dirname, '../D1Check/a24_simulator');
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const read = p => JSON.parse(fs.readFileSync(p, 'utf8').replace(/^\uFEFF/, ''));
const opPath = path.join(root, 'experiments/rl_cost_20261017/OPERATION.json');
const op = read(opPath);
const pins = op.pins.map(pin => {
  const original = pin.path.replaceAll('\\', '/');
  const marker = '/a24_simulator/';
  const at = original.toLowerCase().lastIndexOf(marker);
  if (at < 0) throw Error('Unmapped provenance pin: ' + original);
  const relative = original.slice(at + marker.length);
  const local = path.resolve(root, relative);
  if (!local.startsWith(root + path.sep)) throw Error('Pin escapes checkout');
  const exists = fs.existsSync(local);
  return {relative, exists, expected_sha256: pin.sha256,
    actual_sha256: exists ? hash(local) : null,
    pass: exists && fs.statSync(local).size === pin.bytes && hash(local) === pin.sha256};
});
const required = ['RESULT.json', 'COMPLETE.json', 'SELECTION_FROZEN.json', 'receipts.jsonl',
  'TRAIN_096.learning.json', 'PPO_COST_EP032.pt.gz', 'PPO_COST_EP064.pt.gz', 'PPO_COST_EP096.pt.gz'];
const out = path.join(root, op.output_dir);
const files = required.map(file => ({file: op.output_dir + '/' + file,
  present: fs.existsSync(path.join(out, file))}));
const rrPath = path.join(root, 'results/RR_20261017_01/RESULT.json');
const rrTerminal = read(path.join(root, 'results/RR_20261017_01/COMPLETE.json'));
const ledgerPath = path.join(root, 'results/COMPETITION_WITNESS_AUDIT_20261017_01/SAVED_SHARED_RECEIPTS.jsonl');
const ledger = fs.readFileSync(ledgerPath, 'utf8').trim().split(/\r?\n/).map(JSON.parse);
const starts = ledger.filter(r => r.event === 'START');
const report = {
  schema: 'A24-local-recovery-inspection-v1', inspected_at_utc: new Date().toISOString(),
  source_repository: 'mingyujo/D1Check', branch: 'codex/a24-simulator-handoff-20261016',
  restored_commit: '8ea30e4e884bbab1b7fcb791f2e49f740d4eae52',
  status: files.some(f => !f.present) ? 'AWAITING_UNPUBLISHED_ORIGINAL_ARTIFACTS' : 'ARTIFACTS_PRESENT_NOT_AUDITED',
  operation_sha256: hash(opPath), source_pins: pins,
  pin_pass_count: pins.filter(p => p.pass).length, pin_count: pins.length,
  RR_result_sha256: hash(rrPath), RR_terminal_link_matches: rrTerminal.result_sha256 === hash(rrPath),
  portable_old_ledger: {child_START: starts.length, unique_START: new Set(starts.map(r => r.identity)).size,
    sha256: hash(ledgerPath), parent_START: 105, historical_shared_START: 105 + starts.length,
    scope: 'Old interactive allocation only; excludes later long-scale, rules, RR, and cost-RL allocations'},
  active_ledger_restored: false,
  restore_attempt: 'Original restore script stopped before writing because another project has a live Python server. Preserved that process.',
  cost_RL_required_files: files,
  original_simulator_folder: 'C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/A24-GITHUB-HANDOFF-20261016/a24_simulator',
  recover_from_original: [
    'Entire results/RL_COST_20261017_01 including compressed traces, actor calls, frames, before/after snapshots, experiences, checkpoints, receipts and logs',
    'Latest experiments/rl_cost_20261017 and experiments/rr_20261017, including uncommitted finalization and QA scripts',
    'Latest CONTINUE.json, COMPLETED_AND_FILES.md, docs, and root docs/PROJECT_STATUS.md',
    'Exact original runtime consumption ledger and any final manifests; preserve all original provenance paths and hashes'
  ],
  next_steps: ['Receive original artifacts without running completed operations',
    'Check terminal, 223 unique START identities, hashes, selection seal, and existing audit markers',
    'Run only genuinely unfinished saved replay, arithmetic audit, report QA and publication work'],
  user_pasted_completion_report: {claimed_completed_environments: 223, claimed_train: 96,
    claimed_updates: 12, claimed_Adam_steps: 606, verification: 'NOT_INDEPENDENTLY_VERIFIED_WITH_ORIGINAL_ARTIFACTS'},
  new_environments: 0, new_training: 0, changed_model: false, restarted_automation: false,
  measured_J: null, physical_goal_verified: false
};
const destination = path.join(__dirname, 'RECOVERY_STATUS.json');
if (fs.existsSync(destination)) throw Error('Existing inspection preserved; choose a new output for a new inspection');
fs.writeFileSync(destination, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
console.log(JSON.stringify({status: report.status, pin_pass_count: report.pin_pass_count,
  pin_count: pins.length, RR_terminal_link_matches: report.RR_terminal_link_matches,
  missing_final_files: files.filter(f => !f.present).length, report: destination}));
if (pins.some(p => !p.pass) || !report.RR_terminal_link_matches) process.exitCode = 1;
