'use strict';
const { fs, path, ROOT, json, sha256, zlib, safePath, flag } = require('./io.cjs');
const { pipeline } = require('node:stream/promises');
const { Readable } = require('node:stream');
const CACHE = path.join(ROOT, '.cache');
const RESERVE = 8 * 1024 ** 3;
function reserve(bytes = 0) {
  const s = fs.statfsSync(ROOT);
  if (s.bavail * s.bsize < bytes + RESERVE) throw Error('Need selected data/cache bytes plus 8GiB reserve');
}
async function asset(meta, options = {}) {
  const dest = options.assetDir ? safePath(path.resolve(options.assetDir), meta.name) : safePath(CACHE, meta.name);
  if (fs.existsSync(dest)) {
    const b = fs.readFileSync(dest);
    if (b.length !== meta.bytes || sha256(b) !== meta.sha256) throw Error('Existing asset failed SHA: ' + meta.name);
    return dest;
  }
  if (options.assetDir) throw Error('Local asset missing: ' + dest);
  fs.mkdirSync(CACHE, { recursive: true }); reserve(meta.bytes);
  const part = dest + '.part';
  if (fs.existsSync(part)) throw Error('Incomplete download exists; inspect/remove this exact .part before retry: ' + part);
  const u = new URL(meta.url);
  if (u.protocol !== 'https:' || u.hostname !== 'github.com') throw Error('Unexpected release URL');
  console.log('Downloading ' + meta.name);
  const response = await fetch(u);
  if (!response.ok) throw Error('Download HTTP ' + response.status + ': ' + meta.name);
  await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(part, { flags: 'wx' }));
  const b = fs.readFileSync(part);
  if (b.length !== meta.bytes || sha256(b) !== meta.sha256) throw Error('Downloaded SHA/size mismatch: ' + meta.name);
  fs.renameSync(part, dest); return dest;
}
async function catalog(options = {}) {
  const manifest = json(path.join(ROOT, 'data/ARCHIVES.json'));
  const cat = json(await asset(manifest.catalog, options));
  if (cat.schema !== manifest.schema || cat.files.length !== manifest.statistics.included_files) throw Error('Catalog/schema/count mismatch');
  return { manifest, cat };
}
async function restore(args = []) {
  const group = flag(args, '--group', 'current'), assetDir = flag(args, '--asset-dir', null), filter = flag(args, '--filter', null);
  const verifyOnly = args.includes('--verify-only'), options = { assetDir };
  const { manifest, cat } = await catalog(options);
  if (group !== 'all' && !cat.groups.includes(group)) throw Error('Unknown group: ' + group);
  const files = cat.files.filter(f => (group === 'all' || f.group === group) && (!filter || f.path.includes(filter)));
  if (!files.length) throw Error('Selection has no files');
  const destRoot = path.join(ROOT, 'archive');
  const selected = new Map();
  for (const f of files) {
    safePath(destRoot, f.path);
    const blob = cat.blobs[f.sha256];
    if (!blob || blob.bytes !== f.bytes || blob.codec !== 'gzip') throw Error('Invalid blob metadata: ' + f.path);
    if (!selected.has(f.sha256)) selected.set(f.sha256, { blob, files: [] });
    selected.get(f.sha256).files.push(f);
  }
  const needed = new Set([...selected.values()].map(x => x.blob.pack));
  let missingOutput = 0;
  if (!verifyOnly) for (const f of files) if (!fs.existsSync(safePath(destRoot, f.path))) missingOutput += f.bytes;
  const missingCache = assetDir ? 0 : manifest.packs.filter(p => needed.has(p.name) && !fs.existsSync(path.join(CACHE, p.name))).reduce((s, p) => s + p.bytes, 0);
  reserve(missingOutput + missingCache);
  let verified = 0, written = 0, reused = 0;
  for (const pack of manifest.packs.filter(p => needed.has(p.name))) {
    const p = await asset(pack, options), fd = fs.openSync(p, 'r');
    try {
      for (const [digest, item] of selected) {
        const b = item.blob; if (b.pack !== pack.name) continue;
        if (!Number.isSafeInteger(b.offset) || b.offset < 0 || b.offset + b.stored_bytes > pack.bytes) throw Error('Blob outside pack');
        const compressed = Buffer.alloc(b.stored_bytes);
        if (fs.readSync(fd, compressed, 0, compressed.length, b.offset) !== compressed.length) throw Error('Truncated pack');
        const raw = zlib.gunzipSync(compressed);
        if (raw.length !== b.bytes || sha256(raw) !== digest) throw Error('Blob content mismatch');
        verified++;
        if (verifyOnly) continue;
        for (const file of item.files) {
          const dest = safePath(destRoot, file.path);
          if (fs.existsSync(dest)) {
            if (!fs.lstatSync(dest).isFile() || sha256(fs.readFileSync(dest)) !== digest) throw Error('Existing file differs; refusing overwrite: ' + dest);
            reused++; continue;
          }
          fs.mkdirSync(path.dirname(dest), { recursive: true });
          const part = dest + '.part', out = fs.openSync(part, 'wx');
          try { fs.writeFileSync(out, raw); fs.fsyncSync(out); } finally { fs.closeSync(out); }
          fs.renameSync(part, dest); written++;
        }
      }
    } finally { fs.closeSync(fd); }
    console.log(JSON.stringify({ pack: pack.name, verified_unique_blobs: verified, written, reused }));
  }
  const result = { status: 'PASS', group, filter, verify_only: verifyOnly, selected_files: files.length, verified_unique_blobs: verified, written, reused, new_simulator_instances: 0, new_training: 0 };
  console.log(JSON.stringify(result, null, 2)); return result;
}
module.exports = { asset, catalog, restore };
if (require.main === module) restore(process.argv.slice(2)).catch(e => { console.error(e.message); process.exitCode = 1; });
