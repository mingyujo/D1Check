const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {chromium}=require('playwright');
const P=path.resolve(__dirname,'..'),O=P+'/results/UI_QA_PORTABLE';fs.mkdirSync(O,{recursive:true});
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{const before=hash(P+'/runtime/receipts.jsonl'),errors=[],remote=[];let checks=0;const need=(x,m)=>{if(!x)throw Error(m);checks++};
const browser=await chromium.launch({headless:true,...(process.env.CHROME?{executablePath:process.env.CHROME}:{}),args:['--disable-background-networking','--disable-component-update']});
const context=await browser.newContext();const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});await page.route('**/*',r=>{if(r.request().url().startsWith(`http://127.0.0.1:${process.env.PORT||8766}`))return r.continue();remote.push(r.request().url());return r.abort()});
await page.goto(`http://127.0.0.1:${process.env.PORT||8766}/`);await page.waitForFunction(()=>document.getElementById('routeCounts').children.length===7);
need((await page.locator('#bulkPreview').innerText()).includes('12조건'),'12-case preview');need((await page.locator('#rlSeed').inputValue())==='20261028','new actor default');
need((await page.locator('#scheduleDiagnosis').innerText()).includes('실제 일정'),'schedule group diagnosis');need(await page.locator('#activityDiagnosis tbody tr').count()===7,'seven work-window diagnostics');
await page.locator('#bulkRun').click();await page.waitForFunction(()=>document.getElementById('bulkCoverage').textContent.includes('완료 12'));
need(await page.locator('#bulkAggregate tr').count()===7,'seven aggregated policies');need(await page.locator('#bulkCases tr').count()===12,'all12 conditions');
for(const theme of ['light','dark'])for(const width of [360,736,1280]){
 await page.emulateMedia({colorScheme:theme});await page.setViewportSize({width,height:900});
 need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'global overflow '+theme+width);
 await page.screenshot({path:O+'/'+theme+'_'+width+'.png',fullPage:true});
}
const c=await page.locator('#bulkCases button').first();await c.click();await page.waitForFunction(()=>document.getElementById('routeCounts').children.length===7);
for(const p of ['ROLLING_ATC_RL','FIFO_FREE','EDD','ATC','MOBILE_DEADLINE_ENERGY']){await page.selectOption('#timelinePolicy',p);need(await page.locator('#timeline svg').count()===1,'timeline '+p);}
need(errors.length===0,'browser errors '+errors.join('|'));need(remote.length===0,'remote traffic');need(before===hash(P+'/runtime/receipts.jsonl'),'UI replay consumed environments');
await browser.close();const r={status:'PASS_ACTUAL_BROWSER_SAVED_ONLY',checks,viewports:6,conditions:12,policies:7,environment_START:0,ledger_unchanged:true,errors,remote};fs.writeFileSync(O+'/RESULT.json',JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify(r));
})().catch(e=>{fs.writeFileSync(O+'/FAILURE.json',JSON.stringify({message:e.message}));console.error(e.stack);process.exit(1)});
