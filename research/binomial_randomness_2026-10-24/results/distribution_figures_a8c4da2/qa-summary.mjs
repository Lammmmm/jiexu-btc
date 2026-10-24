import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve('research/binomial_randomness_2026-10-24/results/distribution_figures_a8c4da2');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
await page.goto(pathToFileURL(path.join(root,'SUMMARY.html')).href);await page.waitForLoadState('load');
const desktop=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,
 tables:document.querySelectorAll('table').length,
 images:[...document.images].map(x=>({src:x.getAttribute('src'),ok:x.complete&&x.naturalWidth>=4800})),
 textLength:document.body.innerText.length}));
if(desktop.width>desktop.viewport||desktop.images.length!==3||desktop.images.some(x=>!x.ok))throw new Error('Desktop/image verification failed');
await page.setViewportSize({width:390,height:844});
const mobile=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));
if(mobile.width>mobile.viewport)throw new Error('Mobile overflow');
await browser.close();
await fs.writeFile(path.join(root,'html-verification.json'),JSON.stringify({status:'PASS',desktop,mobile},null,2));
console.log(JSON.stringify({status:'PASS',desktop,mobile}));
