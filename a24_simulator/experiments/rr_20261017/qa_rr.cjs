const fs=require('fs'),path=require('path'),url=require('url'),crypto=require('crypto');
const {chromium}=require('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/RR_20261017_01'),target=path.join(out,'UI_QA'),html=path.join(out,'REPORT.html');
const result=JSON.parse(fs.readFileSync(path.join(out,'RESULT.json'),'utf8')),ids=['ROLLING_ATC','EDF_CPU_FIRST','FIFO_CPU_FIRST','RR_CPU_FIRST'],f=(x,d=3)=>Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
if(fs.existsSync(target))throw Error('QA output consumed');fs.mkdirSync(target);let checks=0;function need(x,s){checks++;if(!x)throw Error(s)}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),errors=[],network=[],views=[];
 try{
  for(const width of [360,736,1280]){
   const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});
   await page.goto(url.pathToFileURL(html).href);
   for(const light of [false,true]){
    if(light)await page.locator('#theme').click();
    need(await page.locator('#main tbody tr').count()===4,'4 policies');need(await page.locator('#levels tbody tr').count()===7,'7 lengths');
    const main=await page.locator('#main tbody tr').allTextContents(),all=await page.locator('#levels tbody tr').allTextContents();
    for(let i=0;i<4;i++){const row=result.cases.at(-1).rows.find(r=>r.policy===ids[i]),m=row.metrics;for(const key of ['total_J_proxy','baseline_J_proxy','increment_J_proxy','mean_AP_c','peak_AP_c','P95_completed_response_s'])need(main[i].includes(f(m[key])),'main '+key);need(main[i].includes(m.on_time+'/3072'),'ontime whole denominator')}
    for(let i=0;i<7;i++){const c=result.cases[i];need(all[i].includes(f(c.n,0)),'length');for(const id of ids){const m=c.rows.find(x=>x.policy===id).metrics;for(const key of ['total_J_proxy','increment_J_proxy','mean_AP_c'])need(all[i].includes(f(m[key])),'all '+key);need(all[i].includes(f(m.on_time,0)),'all ontime')}}
    await page.locator('summary').click();need(await page.locator('details').getAttribute('open')!==null,'diagnostic expand');await page.locator('summary').click();
    const geom=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,win:innerWidth,light:document.body.classList.contains('light')}));need(geom.doc<=width+1,'no page overflow');need(geom.light===light,'theme');
    await page.screenshot({path:path.join(target,`${width}_${light?'light':'dark'}.png`),fullPage:true});views.push({width,light,geom});
   }
   await page.close();
  }
  need(errors.length===0&&network.length===0,'no JS/remote');const sha=crypto.createHash('sha256').update(fs.readFileSync(html)).digest('hex');fs.writeFileSync(path.join(target,'RESULT.json'),JSON.stringify({status:'PASS',checks,views,errors,network,html_sha256:sha},null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'PASS',checks,views:6}));
 }finally{await browser.close()}
})().catch(e=>{fs.writeFileSync(path.join(target,'FAILURE.json'),JSON.stringify({error:String(e),checks}),{flag:'wx'});console.error(e);process.exitCode=1});
