'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..');
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const prior=JSON.parse(fs.readFileSync(path.join(__dirname,'OPERATION.json')));
if(fs.existsSync(path.join(root,prior.output_dir)))throw Error('V1 unexpectedly consumed');
const updated={...prior,schema:'A24-shared-cost-policy-operation-v2',created_utc:new Date().toISOString(),
 sources:[...prior.sources.map(p=>pin(p.path)),pin(__filename),pin(path.join(__dirname,'prestart_v1/FAILURE.json'))],
 output_dir:'results/SHARED_COST_POLICY_V2_20261017_01',
 prestart_failure:pin(path.join(__dirname,'prestart_v1/FAILURE.json')),prestart_environment_START:0,
 budget_allocation_reused_not_incremented:true,retired_operation:pin(path.join(__dirname,'OPERATION.json'))};
fs.writeFileSync(path.join(__dirname,'OPERATION_V2.json'),JSON.stringify(updated,null,2)+'\n',{flag:'wx'});
console.log('Prestart import fix archived; V2 same finite8 allocation, old environment START0.');
