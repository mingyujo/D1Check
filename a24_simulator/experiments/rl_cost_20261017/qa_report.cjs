'use strict';
const fs=require('fs'),path=require('path'),url=require('url'),crypto=require('crypto');
const {chromium}=require('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/RL_COST_20261017_01'),qa=path.join(out,'UI_QA');
const data=JSON.parse(fs.readFileSync(path.join(out,'REPORT_DATA.json'),'utf8'));
const f=(x,d=3)=>x==null?'—':Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
if(fs.existsSync(qa))throw Error('QA namespace consumed');fs.mkdirSync(qa);
let checks=0;const need=(x,s)=>{checks++;if(!x)throw Error(s)};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),errors=[],network=[],views=[];
 try{
  for(const width of [360,736,1280]){
   const page=await browser.newPage({viewport:{width,height:1100},deviceScaleFactor:1});
   page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
   page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});
   await page.goto(url.pathToFileURL(path.join(out,'REPORT.html')).href);
   for(const light of [false,true]){
    if(light)await page.locator('#theme').click();
    need(await page.locator('#aggregate tbody tr').count()===5,'all aggregate policies');
    const aggregates=await page.locator('#aggregate tbody tr').allTextContents();
    for(let i=0;i<5;i++){const r=data.freshAggregate[i];need(aggregates[i].includes(r.on_time+'/'+r.planned),'aggregate denominators');
      for(const k of ['total_J_proxy','increment_J_proxy','mean_AP_c','peak_AP_c','P95_completed_response_s'])need(aggregates[i].includes(f(r[k])),'aggregate '+k);}
    for(const c of data.cases){
     await page.locator('#cohort').selectOption(c.id);
     need(await page.locator('#main tbody tr').count()===5,'all5 policies');
     need((await page.locator('#scope').textContent()).includes(c.kind),'historical/fresh boundary');
     const rows=await page.locator('#main tbody tr').allTextContents(),harms=await page.locator('#harms tbody tr').allTextContents();
     for(let i=0;i<5;i++){
      const m=c.rows.find(r=>r.policy===data.ids[i]).metrics;
      need(rows[i].includes(m.on_time+'/'+m.planned)&&rows[i].includes(m.urgent_on_time+'/'+m.urgent_planned),'whole and urgent');
      for(const k of ['total_J_proxy','baseline_J_proxy','increment_J_proxy','mean_AP_c','peak_AP_c','P95_completed_response_s'])need(rows[i].includes(f(m[k])),'case '+k);
      need(harms[i].includes(f(m.residual_AP_at_plus180_c)),'absolute residual AP');need(harms[i].includes(m.AVAILABLE_by_window_end+'/'+m.planned),'window completion denominator');
     }
    }
    need(await page.locator('#control tbody tr').count()===12,'all12 NN controls');
    await page.locator('#cohort').selectOption('history6');
    const geom=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,win:innerWidth,light:document.body.classList.contains('light')}));
    need(geom.doc<=width+1&&geom.light===light,'geometry/theme');
    await page.screenshot({path:path.join(qa,`${width}_${light?'light':'dark'}.png`),fullPage:true});views.push({width,light,geom,cases:data.cases.length});
   }
   await page.close();
  }
  need(errors.length===0&&network.length===0,'no JS/remote');
  const hash=crypto.createHash('sha256').update(fs.readFileSync(path.join(out,'REPORT.html'))).digest('hex');
  fs.writeFileSync(path.join(qa,'RESULT.json'),JSON.stringify({status:'PASS',checks,views,errors,network,html_sha256:hash},null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({status:'PASS',checks,views:6,cases:data.cases.length}));
 }catch(e){fs.writeFileSync(path.join(qa,'FAILURE.json'),JSON.stringify({checks,errors,network,error:String(e)}),{flag:'wx'});throw e}
 finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
