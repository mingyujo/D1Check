'use strict';
const assert = require('node:assert/strict');
const { fs, path, ROOT, json, sha256, zlib } = require('./io.cjs');
function verify() {
  const manifest = json(path.join(ROOT, 'CORE_MANIFEST.json'));
  let bytes = 0;
  for (const f of manifest.files) {
    const b = fs.readFileSync(path.join(ROOT, f.path));
    assert.equal(b.length, f.bytes, f.path + ' size');
    assert.equal(sha256(b), f.sha256, f.path + ' SHA256'); bytes += b.length;
  }
  const provenance = json(path.join(ROOT, 'data/CORE_PROVENANCE.json'));
  for (const f of provenance.source_files) {
    const b = fs.readFileSync(path.join(ROOT, f.path));
    assert.equal(sha256(b), f.sha256, f.path + ' original copy');
    if (f.uncompressed_sha256) assert.equal(sha256(zlib.gunzipSync(b)), f.uncompressed_sha256, f.path + ' uncompressed');
  }
  const d = json(path.join(ROOT, 'data/cached_view_data.json.gz'));
  assert.equal(d.fair.length, 240);
  const own = d.fair.filter(x => x.policy === 'ROLLING_ATC_ROUTE_V2');
  assert.equal(own.length, 48);
  assert.ok(own.every(x => x.hard_feasible && x.service.all.planned === 128 && x.service.all.completed === 128 && x.service.all.on_time === 128));
  const p = json(path.join(ROOT, 'data/engine_packet.json.gz'));
  assert.equal(new Set(p.templates.map(x => x.route)).size, 4);
  assert.equal(p.templates.length, 8636);
  return { status: 'PASS', core_files: manifest.files.length, core_bytes: bytes, cached_cases: d.fair.length, own_cases: own.length, phase_templates: p.templates.length, new_simulator_instances: 0, new_training: 0 };
}
module.exports = { verify };
if (require.main === module) { try { console.log(JSON.stringify(verify(), null, 2)); } catch (e) { console.error(e.message); process.exitCode = 1; } }
