'use strict';
// Saved public observations only: no Simulator construction, sampling, or fitting.
const fs=require('fs'),zlib=require('zlib'),readline=require('readline'),assert=require('assert');
const actions=require('./multi_actions.cjs'),timing=require('./multi_timing.cjs');
const packet=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),nom=timing.nominal(packet);
(async()=>{for await(const line of readline.createInterface({input:process.stdin,crlfDelay:Infinity})){
 const f=JSON.parse(line),r=JSON.parse(zlib.gunzipSync(fs.readFileSync(f.raw_path)));let checks=0,forecasts=0;
 for(const d of r.policy_decisions){assert.strictEqual(actions.digest(d.public_observation),d.action.public_digest);checks++;
  const a=actions.select(d.public_observation,packet,nom,r.config);assert.deepStrictEqual(a,d.action);checks++;forecasts+=a.forecast_calls;
 }
 assert.strictEqual(forecasts,r.forecast_calls);process.stdout.write(JSON.stringify({id:r.logical_identity,checks:checks+1,decisions:r.policy_decisions.length,forecast_replays:forecasts,new_policy_environments:0})+'\n');
}})().catch(e=>{console.error(e.stack);process.exit(1)});
