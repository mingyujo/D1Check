'use strict';
// Restore existing release bytes omitted from the Git checkout; never fit or simulate.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const root = path.resolve(__dirname, '../S26-D1Check/s26_simulator');
const archive = path.join(root, 'archive/multiresource');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const core = read(path.join(root, 'CORE_MANIFEST.json'));
const catalog = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root, '.cache/s26-multi-final-catalog.json.gz'))));
function inside(base, relative) {
  const target = path.resolve(base, relative);
  if (!target.startsWith(path.resolve(base) + path.sep)) throw Error('Outside root: ' + relative);
  return target;
}
const plan = [];
for (const item of core.files) {
  const destination = inside(root, item.path);
  if (fs.existsSync(destination)) continue;
  const candidates = catalog.files.filter(f => f.sha256 === item.sha256 && f.bytes === item.bytes);
  const sourceItem = candidates.find(f => fs.existsSync(inside(archive, f.path)));
  if (!sourceItem) throw Error('Original archive source absent: ' + item.path);
  const source = inside(archive, sourceItem.path);
  const bytes = fs.readFileSync(source);
  if (bytes.length !== item.bytes || hash(bytes) !== item.sha256) throw Error('Source SHA: ' + item.path);
  plan.push({item, destination, source, bytes});
}
for (const row of plan) {
  fs.mkdirSync(path.dirname(row.destination), {recursive:true});
  fs.writeFileSync(row.destination, row.bytes, {flag:'wx'});
  if (hash(fs.readFileSync(row.destination)) !== row.item.sha256) throw Error('Readback SHA: ' + row.item.path);
}
const result = {
  status:'PASS', mode:'EXACT_RELEASE_BYTES_TO_DECLARED_CORE_PATHS',
  created_utc:new Date().toISOString(), copied:plan.length,
  new_policy_environments:0, new_fit:0, new_RL:0,
  root_cause:'Repository root .gitignore results/ excludes both new portable results directories.',
  upstream_packaging_fix_pending:true,
  files:plan.map(row => ({path:row.item.path, source:row.source, sha256:row.item.sha256, bytes:row.item.bytes}))
};
fs.writeFileSync(path.join(__dirname, 'S26_G004_CORE_HYDRATION.json'), JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:result.status,copied:result.copied,new_policy_environments:0,new_fit:0,new_RL:0}));
