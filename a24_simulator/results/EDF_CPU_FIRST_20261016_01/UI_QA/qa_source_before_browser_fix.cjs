const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/EDF_CPU_FIRST_20261016_01');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 const target=path.join(out,'index.html'),before=hash(path.join(root,'runtime/receipts.jsonl'));
 const q=path.join(out,'UI_QA');fs.mkdirSync(q,{recursive:false});
 const browser=await chromium.launch({headless:true,args:['--disable-background-networking','--disable-component-update']});
 const page=await browser.newPage(),errors=[],external=[];let checks=0;
 const need=(v,m)=>{if(!v)throw Error(m);checks++;};
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',r=>{if(r.request().url().startsWith('file:'))return r.continue();external.push(r.request().url());return r.abort();});
 await page.goto('file:///'+target.replace(/\\/g,'/'));
 await page.waitForFunction(()=>document.querySelectorAll('#energy tr').length===2);
 need(await page.locator('#case option').count()===15,'All conditions accessible');
 need(await page.locator('#allCases tr').count()===14,'All fourteen cases');
 for(let i=0;i<14;i++){
  await page.selectOption('#case',String(i));need(await page.locator('#heatChart svg').count()===1,'Paired AP chart '+i);
  need(!(await page.locator('#service').innerText()).includes('NaN'),'Finite displayed metrics '+i);
 }
 await page.selectOption('#case','all');
 for(const theme of ['light','dark'])for(const width of [360,736,1280]){
  await page.emulateMedia({colorScheme:theme});await page.setViewportSize({width,height:900});
  need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Overflow '+theme+width);
  await page.screenshot({path:path.join(q,theme+'_'+width+'.png'),fullPage:true});
 }
 need(errors.length===0,'JavaScript/console errors');need(external.length===0,'No external traffic');
 need(before===hash(path.join(root,'runtime/receipts.jsonl')),'No environment consumption');
 await browser.close();const result={status:'PASS_ACTUAL_BROWSER_14_CASES_6_VIEWS',checks,errors,external,html_sha256:hash(target),new_environment:0,utc:new Date().toISOString()};
 fs.writeFileSync(path.join(q,'RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
