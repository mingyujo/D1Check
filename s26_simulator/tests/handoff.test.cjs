'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const { path, fs, ROOT, json, safePath, sha256 } = require('../scripts/io.cjs');
test('registered core bytes and cached coverage', () => assert.equal(require('../scripts/verify.cjs').verify().status, 'PASS'));
test('CPU/GPU/NPU classification remains an available route contract', () => {
  const a = require('../src/rolling_action_v2.cjs');
  assert.deepEqual(a.ROUTES, ['classification_CPU', 'classification_GPU', 'classification_NPU', 'detection_CPU']);
  for (const r of a.ROUTES) assert.equal(a.legal(r, []), true);
  assert.equal(a.legal('classification_GPU', [{ route: 'detection_CPU' }]), true);
  assert.equal(a.legal('classification_NPU', [{ route: 'detection_CPU' }]), true);
  assert.equal(a.legal('classification_CPU', [{ route: 'detection_CPU' }]), false);
  assert.equal(a.legal('classification_GPU', [{ route: 'classification_NPU' }]), false);
  assert.equal(a.legal('detection_CPU', [{ route: 'classification_GPU' }, { route: 'classification_NPU' }]), false);
  const s = require('../src/s26_simulator_v2.cjs');
  assert.equal(s.validatePolicy('ROLLING_ATC_ROUTE_V2'), 'ROLLING_ATC_ROUTE_V2');
  assert.throws(() => s.validatePolicy('PPO_LATEST'), /Unimplemented/);
});
test('portable CLI reads stored results from a different working directory', () => {
  const run = spawnSync(process.execPath, [path.join(ROOT, 'cli/s26.cjs'), 'replay', '--policy', 'ROLLING_ATC_ROUTE_V2', '--bank', 'ALL'], { cwd: os.tmpdir(), encoding: 'utf8', windowsHide: true });
  assert.equal(run.status, 0, run.stderr);
  const r = JSON.parse(run.stdout); assert.equal(r.new_simulator_instances, 0);
  assert.equal(r.results[0].cases, 48); assert.equal(r.results[0].hard_feasible_cases, 48);
  const rows = json(path.join(ROOT, 'data/cached_view_data.json.gz')).fair.filter(x => x.policy === 'ROLLING_ATC_ROUTE_V2');
  assert.equal(r.results[0].API_J_mean, rows.reduce((s, x) => s + x.J_API0_180, 0) / rows.length);
});
test('archive destination rejects path traversal and absolute paths', () => {
  for (const name of ['../escape', 'work/../../escape', 'C:/secret', '/absolute']) assert.throws(() => safePath(path.join(ROOT, 'archive'), name));
  assert.ok(safePath(path.join(ROOT, 'archive'), 'work/S26/example.json').startsWith(ROOT));
});
test('served HTML is the exact archived view; other paths are inaccessible', async () => {
  const port = 20000 + require('node:crypto').randomInt(20000);
  const server = await require('../cli/s26.cjs').main(['serve', '--port', String(port)]);
  try {
    if (!server.listening) await require('node:events').once(server, 'listening');
    const response = await fetch('http://127.0.0.1:' + port);
    assert.equal(response.status, 200);
    assert.equal(sha256(Buffer.from(await response.arrayBuffer())), sha256(fs.readFileSync(path.join(ROOT, 'web/multiresource_v1.html'))));
    assert.equal((await fetch('http://127.0.0.1:' + port + '/data/engine_packet.json.gz')).status, 404);
  } finally { await new Promise((resolve, reject) => server.close(e => e ? reject(e) : resolve())); }
});
test('multi-resource stored CLI binds the audited original summary',()=>{
  const run=spawnSync(process.execPath,[path.join(ROOT,'cli/s26.cjs'),'replay','--comparison','multiresource-v1','--capacity','3','--model','CENTRAL'],{cwd:os.tmpdir(),encoding:'utf8',windowsHide:true});
  assert.equal(run.status,0,run.stderr);const r=JSON.parse(run.stdout),original=json(path.join(ROOT,'experiments/multiresource_v1/results/SUMMARY.json')).filter(r=>r.capacity===3&&r.model==='CENTRAL');
  assert.deepEqual(r.results,original);assert.equal(r.new_policy_environments,0);assert.equal(r.new_RL,0);
});
test('multi archive restores exact bytes, reuses matching files and refuses an overwrite',async()=>{
  const {zlib}=require('../scripts/io.cjs'),restore=require('../scripts/restore-multi.cjs').main;fs.mkdirSync(path.join(ROOT,'.cache'),{recursive:true});const dir=fs.mkdtempSync(path.join(ROOT,'.cache/multi-fixture-')),id=path.basename(dir),raw=Buffer.from('saved-byte-fixture\n'),gz=zlib.gzipSync(raw),h=sha256(raw),file='fixtures/'+id+'/proof.json',pack='fixture.pack';fs.writeFileSync(path.join(dir,pack),gz);
  const cat={schema:'S26_CONTENT_ADDRESSED_ARCHIVE_V1',files:[{path:file,bytes:raw.length,sha256:h}],blobs:{[h]:{pack,offset:0,stored_bytes:gz.length,bytes:raw.length,codec:'gzip'}}},catalogName='fixture-catalog.json.gz',catPath=path.join(dir,catalogName),manifestPath=path.join(dir,'manifest.json');
  function bind(){const b=zlib.gzipSync(Buffer.from(JSON.stringify(cat)));fs.writeFileSync(catPath,b);fs.writeFileSync(manifestPath,JSON.stringify({schema:cat.schema,catalog:{name:catalogName,bytes:b.length,sha256:sha256(b)},packs:[{name:pack,bytes:gz.length,sha256:sha256(gz)}],statistics:{included_files:1}}));}
  bind();const args=['--manifest',path.relative(ROOT,manifestPath),'--asset-dir',dir];assert.equal((await restore(args)).written,1);assert.equal((await restore(args)).reused,1);const target=path.join(ROOT,'archive/multiresource',file);fs.writeFileSync(target,'preserve changed local bytes');await assert.rejects(restore(args),/Refuse overwrite/);assert.equal(fs.readFileSync(target,'utf8'),'preserve changed local bytes');
  cat.files[0].path='../escape';bind();await assert.rejects(restore([...args,'--verify-only']),/Unsafe archive path/);
  cat.files[0].path=file;cat.files[0].sha256='0'.repeat(64);cat.blobs['0'.repeat(64)]=cat.blobs[h];bind();await assert.rejects(restore([...args,'--verify-only']),/Content SHA/);
});
