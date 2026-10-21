
import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve('research/ganzhi_volatility_2026-10-21');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const records=[];
for(const file of ['REPORT.html','GANZHI_APPENDIX.html','REPRODUCE.html']){
 await page.goto(pathToFileURL(path.join(root,file)).href);await page.waitForLoadState('load');
 const s=await page.evaluate(()=>({
  width:document.documentElement.scrollWidth,viewport:innerWidth,
  title:document.querySelector('h1')?.textContent,
  tables:document.querySelectorAll('table').length,rows:document.querySelectorAll('tbody tr').length,
  images:[...document.images].map(x=>({src:x.getAttribute('src'),ok:x.complete&&x.naturalWidth>0})),
  localLinks:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(x=>x&&!x.startsWith('http')&&!x.startsWith('#')),
  textLength:document.body.innerText.length
 }));
 if(s.width>s.viewport+1)throw new Error(file+' desktop overflow');
 if(s.images.some(x=>!x.ok))throw new Error(file+' image failed');
 for(const href of s.localLinks)await fs.access(path.resolve(root,href));
 if(file==='GANZHI_APPENDIX.html'&&s.rows!==1020)throw new Error('Expected1020 appendix rows');
 records.push({file,desktop:s});
 if(file==='REPORT.html')await page.screenshot({path:path.join(root,'results/report-desktop.png')});
 await page.setViewportSize({width:390,height:844});
 const mobile=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));
 if(mobile.width>mobile.viewport+1)throw new Error(file+' mobile overflow');
 records.at(-1).mobile=mobile;
 if(file==='REPORT.html')await page.screenshot({path:path.join(root,'results/report-mobile.png')});
 await page.setViewportSize({width:1440,height:1000});
}
await browser.close();if(errors.length)throw new Error(errors.join('\n'));
await fs.writeFile(path.join(root,'results/report-qa.json'),JSON.stringify({status:'PASS',errors,records},null,2));
console.log(JSON.stringify({status:'PASS',records},null,2));
