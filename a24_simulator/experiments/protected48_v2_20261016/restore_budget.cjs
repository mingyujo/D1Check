// Restore the exact published consumption snapshot in a fresh clone, not runs.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),source=path.join(root,'results/PROTECTED48_V2_20261016_01/SAVED_SHARED_RECEIPTS.jsonl'),proof=JSON.parse(fs.readFileSync(path.join(root,'results/PROTECTED48_V2_20261016_01/PORTABLE_LEDGER_PROOF.json'),'utf8'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),bytes=fs.readFileSync(source);
if(sha(bytes)!==proof.sha256)throw Error('Published ledger SHA differs');
const rows=bytes.toString('utf8').trim().split(/\r?\n/).map(JSON.parse),starts=rows.filter(x=>x.event==='START');
if(starts.length!==397||new Set(starts.map(x=>x.identity)).size!==397)throw Error('397 unique consumed START required');
const target=path.join(root,'runtime/receipts.jsonl');
if(fs.existsSync(target)){
 if(sha(fs.readFileSync(target))!==proof.sha256)throw Error('Existing ledger differs; preserve it and inspect consumption, never delete/reset');
 console.log('PASS_EXISTING_EXACT397_SHARED502_REMAINING10');process.exit(0);
}
if(process.argv.includes('--verify-only'))throw Error('Runtime ledger absent');
const command='Get-CimInstance Win32_Process | Where-Object {$_.Name -match "python"} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress';
const inventory=cp.execFileSync('powershell',['-NoProfile','-Command',command],{encoding:'utf8',windowsHide:true}).trim();
if(inventory)throw Error('Python process present; restore only with workers stopped');
const free=Number(cp.execFileSync('powershell',['-NoProfile','-Command',"([IO.DriveInfo]::new('"+path.parse(root).root.replaceAll("'","''")+"')).AvailableFreeSpace"],{encoding:'utf8',windowsHide:true}).trim());
if(!(free>=8*1024**3))throw Error('8GiB reserve');
fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(source,target,fs.constants.COPYFILE_EXCL);
if(sha(fs.readFileSync(target))!==proof.sha256)throw Error('Restore readback SHA');
console.log('RESTORED_EXACT397_SHARED502_REMAINING10_NO_ENVIRONMENTS');
