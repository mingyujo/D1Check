const fs=require('fs'),path=require('path'),crypto=require('crypto'),{pathToFileURL}=require('url');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),base=path.join(root,'results/PROTECTED48_V2_20261016_01'),out=path.join(base,'UI_QA');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 if(fs.existsSync(out))throw Error('QA output consumed; no overwrite');fs.mkdirSync(out);
 const html=path.join(base,'index.html'),before=hash(html),d=JSON.parse(fs.readFileSync(path.join(base,'RESULT.json'),'utf8'));
 const browser=await chromium.launch({headless:true,executablePath:process.env.A24_QA_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 let checks=0,remote=[],errors=[],views=0,filters=0;const need=(x,m)=>{if(!x)throw Error(m);checks++};
 try{
 for(const scheme of ['light','dark'])for(const width of [360,736,1280]){
  const page=await browser.newPage({viewport:{width,height:1000},colorScheme:scheme});
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('request',r=>{if(/^https?:/i.test(r.url()))remote.push(r.url());});
  await page.goto(pathToFileURL(html).href);await page.locator('#energy tr').first().waitFor();
  need((await page.locator('#energy tr').count())===3,'Initial3 policies');
  need(await page.locator('#selected').textContent()===String(d.selected.episode),'Selected checkpoint');
  need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No document overflow');
  await page.screenshot({path:path.join(out,scheme+'_'+width+'.png'),fullPage:true});views++;
  for(const group of ['fresh','historical','mechanism']){
   await page.selectOption('#group',group);const cases=d[group+'_cases'];
   for(const val of ['all',...cases.map((_,i)=>String(i))]){
    await page.selectOption('#case',val);const rows=val==='all'?d.aggregate[group]:cases[Number(val)].metrics;
    const texts=await page.locator('#energy tr').allTextContents();need(texts.length===rows.length,'Policy row count');
    for(let i=0;i<rows.length;i++)for(const k of ['total_J_proxy','increment_J_proxy','baseline_J_proxy'])need(texts[i].includes(rows[i][k].toFixed(3)),'Energy cell '+k);
    const heat=await page.locator('#service tr').allTextContents();
    for(let i=0;i<rows.length;i++){need(heat[i].includes(rows[i].mean_AP_c.toFixed(4)),'AP exact cell');need(heat[i].includes(rows[i].on_time+'/'+rows[i].planned),'Planned service cell');}
    need(await page.locator('#all tr').count()===cases.length,'All losses retained');
    need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Filter overflow');filters++;
   }
  }
  await page.close();
 }
 need(errors.length===0,'Browser errors0 '+errors.join(';'));need(remote.length===0,'Remote0');need(hash(html)===before,'Exact HTML unchanged');
 const r={status:'PASS_ACTUAL_CHROME_ALL_CONDITIONS_6_VIEWS',checks,views,filters,errors,remote,
  html_sha256:before,result_sha256:hash(path.join(base,'RESULT.json')),source_sha256:hash(__filename),new_environment:0,NN_training:0,utc:new Date().toISOString()};
 fs.writeFileSync(path.join(out,'UI_QA.json'),JSON.stringify(r,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(r));
 }catch(e){fs.writeFileSync(path.join(out,'FAILURE.json'),JSON.stringify({error:String(e),checks,utc:new Date().toISOString()})+'\n',{flag:'wx'});throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
