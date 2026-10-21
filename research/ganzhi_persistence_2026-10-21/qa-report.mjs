import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve('research/ganzhi_persistence_2026-10-21');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));const records=[];
for(const file of ['REPORT.html','GANZHI_DETAILS.html','REPRODUCE.html']){
 await page.goto(pathToFileURL(path.join(root,file)).href);await page.waitForLoadState('load');
 const state=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,
  heading:document.querySelector('h1')?.textContent,tables:document.querySelectorAll('table').length,
  rows:document.querySelectorAll('tbody tr').length,textLength:document.body.innerText.length,
  images:[...document.images].map(x=>({src:x.getAttribute('src'),ok:x.complete&&x.naturalWidth>0})),
  links:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(x=>x&&!x.startsWith('http')&&!x.startsWith('#'))}));
 if(state.width>state.viewport+1)throw new Error(file+' desktop overflow');
 if(state.images.some(x=>!x.ok))throw new Error(file+' image failed');
 for(const href of state.links)await fs.access(path.resolve(root,href));
 if(file==='GANZHI_DETAILS.html'&&state.rows!==1080)throw new Error('Expected1080 full group rows');
 if(file==='REPORT.html')await page.screenshot({path:path.join(root,'results/report-desktop.png')});
 await page.setViewportSize({width:390,height:844});
 const mobile=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));
 if(mobile.width>mobile.viewport+1)throw new Error(file+' mobile overflow');
 if(file==='REPORT.html')await page.screenshot({path:path.join(root,'results/report-mobile.png')});
 records.push({file,desktop:state,mobile});await page.setViewportSize({width:1440,height:1000});
}
await browser.close();if(errors.length)throw new Error(errors.join('\n'));
await fs.writeFile(path.join(root,'results/report-qa.json'),JSON.stringify({status:'PASS',errors,records},null,2));
console.log(JSON.stringify({status:'PASS',records}));
