'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const ROOT = path.resolve(__dirname, '..');
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function json(file) {
  let b = fs.readFileSync(file);
  if (file.endsWith('.gz')) b = zlib.gunzipSync(b);
  return JSON.parse(b.toString('utf8').replace(/^\uFEFF/, ''));
}
function safePath(root, relative) {
  if (!relative || /(^|[\\/])\.\.([\\/]|$)/.test(relative) || path.isAbsolute(relative) || relative.includes(':')) throw Error('Unsafe archive path: ' + relative);
  const target = path.resolve(root, relative);
  if (!target.startsWith(path.resolve(root) + path.sep)) throw Error('Path escapes destination');
  let parent = target;
  while (parent.startsWith(path.resolve(root))) {
    if (fs.existsSync(parent) && fs.lstatSync(parent).isSymbolicLink()) throw Error('Symlink in destination: ' + parent);
    const next = path.dirname(parent); if (next === parent) break; parent = next;
  }
  return target;
}
function flag(args, name, fallback) { const n = args.indexOf(name); if (n < 0) return fallback; if (!args[n + 1] || args[n + 1].startsWith('--')) throw Error('Missing argument for ' + name); return args[n + 1]; }
module.exports = { fs, path, zlib, ROOT, json, sha256, safePath, flag };
