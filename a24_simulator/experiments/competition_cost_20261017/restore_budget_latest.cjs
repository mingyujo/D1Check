// Exact forward-only restoration of consumption, never simulations/checkpoints.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),folder=root+'/results/COMPETITION_WITNESS_AUDIT_20261017_01';
const proof=JSON.parse(fs.readFileSync(folder+'/AUDIT.json')),source=fs.readFileSync(folder+'/SAVED_SHARED_RECEIPTS.jsonl');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
if(sha(source)!==proof.portable_receipts_sha256)throw Error('Published ledger SHA differs');
const rows=source.toString('utf8').trim().split(/\r?\n/).map(JSON.parse),starts=rows.filter(r=>r.event==='START');
if(starts.length!==406||new Set(starts.map(r=>r.identity)).size!==406||proof.shared_START!==511)throw Error('Consumption proof');
const target=root+'/runtime/receipts.jsonl',current=fs.existsSync(target)?fs.readFileSync(target):Buffer.alloc(0);
if(sha(current)===sha(source)){console.log('PASS_EXACT_CHILD406_SHARED511_REMAINING1');process.exit(0);}
if(process.argv.includes('--verify-only'))throw Error('Runtime differs; inspect first, then explicit forward-only restoration');
if(current.length>source.length||!source.subarray(0,current.length).equals(current)||(current.length&&current.at(-1)!==10))throw Error('Existing divergent/newer ledger preserved; no reset/refund');
const inv=cp.execFileSync('powershell',['-NoProfile','-Command','Get-CimInstance Win32_Process | Where-Object {$_.Name -match "python"} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress'],{encoding:'utf8',windowsHide:true}).trim();
if(inv)throw Error('Python worker present; preserve ledger until idle');
const volume=path.parse(root).root.replaceAll("'","''");
const free=Number(cp.execFileSync('powershell',['-NoProfile','-Command',"([IO.DriveInfo]::new('"+volume+"')).AvailableFreeSpace"],{encoding:'utf8',windowsHide:true}).trim());
if(!(free>=8*1024**3))throw Error('8GiB reserve');
fs.mkdirSync(path.dirname(target),{recursive:true});fs.appendFileSync(target,source.subarray(current.length));
if(sha(fs.readFileSync(target))!==sha(source))throw Error('Readback mismatch; preserve exact boundary');
console.log('RESTORED_FORWARD_ONLY_CHILD406_SHARED511_REMAINING1_NO_EXECUTION');
