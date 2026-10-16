const fs=require('fs'),path=require('path'),c=require('crypto'),{pathToFileURL}=require('url');
const {chromium}=require('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../..'),report=root+'/results/COMPETITION_COST_REPORT_20261017_01',out=report+'/QA_ACTUAL_01';
const read=p=>JSON.parse(fs.readFileSync(p)),pin=p=>{let b=fs.readFileSync(p);return {path:path.relative(root,p).replaceAll('\\','/'),sha256:c.createHash('sha256').update(b).digest('hex'),bytes:b.length};};
if(fs.existsSync(out))throw Error('Consumed QA output');fs.mkdirSync(out);
const source=pin(__filename),html=pin(report+'/REPORT.html'),data=read(report+'/PRESENTATION_DATA.json');
fs.writeFileSync(out+'/OPERATION.json',JSON.stringify({schema:'A24-competition-cost-browser-QA-v1',source,html,viewports:[360,736,1280],themes:['light','dark'],new_START:0,utc:new Date().toISOString()},null,2)+'\n',{flag:'wx'});
let checks=0;const need=(v,s)=>{if(!v)throw Error(s);checks++;};
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});let views=[],errors=[],remote=[];
 for(const colorScheme of ['light','dark'])for(const width of [360,736,1280]){
  const context=await browser.newContext({viewport:{width,height:900},colorScheme,acceptDownloads:true}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url());});
  await page.goto(pathToFileURL(report+'/REPORT.html').href);await page.waitForSelector('#tbody tr');
  for(const condition of ['all','0','3','5','10'])for(const observer of ['new','old','native']){
   await page.selectOption('#condition',condition);await page.selectOption('#observer',observer);
   const cs=condition==='all'?data.cases:data.cases.filter(c=>String(c.index)===condition),rows=await page.locator('#tbody tr').allTextContents();need(rows.length===2,'Two policies');
   for(let j=0;j<2;j++){
    const ms=cs.map(c=>c.metrics[j]),total=observer==='native'?null:ms.reduce((s,m)=>s+(observer==='new'?m.new_state_cost.total_J_proxy:m.total_J_proxy),0)/ms.length;
    const cells=await page.locator('#tbody tr').nth(j).locator('td').allTextContents();
    need(cells[1]===(total===null?'미검증':total.toFixed(4)),'Actual displayed energy value');
    need(cells[7]===ms.reduce((s,m)=>s+m.on_time,0)+'/'+ms.reduce((s,m)=>s+m.planned,0),'Actual deadline numerator and denominator');
    need(cells[9]==='0','Missing kept');
   }
   need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No page overflow');
   need(!(await page.locator('body').innerText()).match(/undefined|NaN|__SCRIPT__|__INPUTS__/),'No unresolved output');
  }
  await page.selectOption('#observer','new');await page.selectOption('#condition','all');
  if(width===1280&&colorScheme==='light'){
   need(await page.locator('#inputSelect option').count()===28,'28 input lists including preserved retired seed');
   for(let i=0;i<28;i++){
    await page.selectOption('#inputSelect',String(i));need(await page.locator('#inputPreview tr').count()===49,'48 request rows');
    need(await page.locator('#download').isDisabled()===(i>=12&&i<24),'Retired seed cannot be exported for execution');
   }
   await page.selectOption('#inputSelect','24');const downloading=page.waitForEvent('download');await page.click('#download');let d=await downloading;
   await d.saveAs(out+'/INPUT_DOWNLOAD.json');let input=read(out+'/INPUT_DOWNLOAD.json');need(input.seed===20261741&&input.requests.length===48,'Download exact new public request input');
  }
  await page.screenshot({path:out+'/'+colorScheme+'_'+width+'.png',fullPage:true});views.push({colorScheme,width,conditions:5,observers:3});await context.close();
 }
 need(errors.length===0,'No JS/console errors');need(remote.length===0,'No remote requests');need(pin(report+'/REPORT.html').sha256===html.sha256,'HTML unchanged');
 fs.writeFileSync(out+'/QA.json',JSON.stringify({status:'PASS_ACTUAL_CHROME',checks,views,errors,remote,source,html,input_download:pin(out+'/INPUT_DOWNLOAD.json'),new_START:0,utc:new Date().toISOString()},null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:'PASS_ACTUAL_CHROME',checks,views:views.length,HTML:html}));
}catch(e){fs.writeFileSync(out+'/FAILURE.json',JSON.stringify({error:String(e),checks,automatic_retry:false},null,2)+'\n',{flag:'wx'});throw e;}finally{if(browser)await browser.close();}})();
