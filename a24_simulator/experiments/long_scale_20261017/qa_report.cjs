const fs=require('fs'),path=require('path'),url=require('url'),crypto=require('crypto');
const {chromium}=require('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../..'),folder=path.join(root,'results/LONG_SCALE_REPORT_20261017_01'),html=path.join(folder,'REPORT.html');
const result=JSON.parse(fs.readFileSync(path.join(folder,'RESULT.json'),'utf8')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const target=path.join(folder,'UI_QA');if(fs.existsSync(target))throw Error('QA output consumed');fs.mkdirSync(target);
let checks=0;function need(v,s){checks++;if(!v)throw Error(s)}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});const errors=[],network=[],views=[];
 try{
  for(const width of [360,736,1280]){
   const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});
   await page.goto(url.pathToFileURL(html).href);await page.locator('h1').waitFor();
   for(const light of [false,true]){
    if(light)await page.locator('#theme').click();
    need(await page.locator('#main-table tbody tr').count()===9,'9 lengths');need(await page.locator('#loss-table tbody tr').count()===9,'9 harm rows');
    const main=await page.locator('#main-table tbody tr').allTextContents(),loss=await page.locator('#loss-table tbody tr').allTextContents();
    for(let i=0;i<result.cases.length;i++){const c=result.cases[i],e=c.rows.find(x=>x.policy==='EDF').metrics,r=c.rows.find(x=>x.policy==='RL').metrics;
     need(main[i].includes(c.n.toLocaleString('en-US')),'count label');for(const m of [e,r]){need(main[i].includes(m.total_J_proxy.toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3})),'total cost');need(main[i].includes(m.increment_J_proxy.toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3})),'increment');need(main[i].includes(m.mean_AP_c.toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3})),'AP');need(main[i].includes(String(m.on_time)),'on_time');need(loss[i].includes(m.P95_completed_response_s.toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3})),'P95')}
    }
    const geom=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,win:innerWidth,table:document.querySelector('.scroll').scrollWidth,light:document.body.classList.contains('light')}));need(geom.doc<=width+1,'no page overflow');need(geom.light===light,'theme state');
    await page.screenshot({path:path.join(target,`${width}_${light?'light':'dark'}.png`),fullPage:true});views.push({width,light,geometry:geom});
   }
   await page.close();
  }
  need(errors.length===0 && network.length===0,'no JS/console/remote');fs.writeFileSync(path.join(target,'RESULT.json'),JSON.stringify({status:'PASS',checks,views,errors,network,html_sha256:hash(html)},null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'PASS',checks,views:views.length}));
 }finally{await browser.close()}
})().catch(e=>{fs.writeFileSync(path.join(target,'FAILURE.json'),JSON.stringify({error:String(e),checks}));console.error(e);process.exitCode=1});
