import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const origin=process.env.APP_URL||'http://127.0.0.1:8000';
const out=new URL('../artifacts/browser/',import.meta.url);
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
const check=name=>{checks.push(name);console.log('PASS',name);};
async function switchTo(period){
  await page.locator('[data-period='+period+']').click();
  await expect(page.locator('[data-period='+period+']')).toHaveAttribute('aria-pressed','true');
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
}
async function query(button,path){
  const response=page.waitForResponse(r=>new URL(r.url()).pathname===path);
  await page.locator(button).click();
  const res=await response;
  assert.equal(res.status(),200);
  assert.equal(new URL(res.url()).searchParams.get('period'),'month');
  const data=await res.json();
  assert.equal(data.period,'month');
  await expect(page.locator(button)).toBeEnabled();
  return data;
}
try{
  await page.goto(origin);
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
  await switchTo('month');
  await expect(page.locator('#ganzhi-statistics')).toBeVisible();
  await expect(page.locator('#statistics-heading')).toHaveText('干支月 · 筛选统计');
  await expect(page.locator('#statistics-description')).toContainText('按月起始日筛选');
  await expect(page.locator('#statistics-basis option[value=previous_close]')).toHaveText('收盘 vs 上月收盘');
  check('月线显示干支月筛选和遍历，文案、口径及日期规则正确');

  const ranking=await query('#statistics-rank','/api/statistics/ganzhi/rankings');
  assert.equal(ranking.totalGanzhi,60);
  for(const side of ['up','down']){
    await expect(page.locator('#statistics-rank-'+side+' tr')).toHaveCount(60);
    const rates=ranking[side+'Ranking'].filter(r=>r.sampleCount).map(r=>Number(r.probabilitiesPct[side]));
    assert.deepEqual(rates,[...rates].sort((a,b)=>b-a));
  }
  const candles=(await (await page.request.get(origin+'/api/candles?period=month')).json()).candles;
  // Independently classify chart monthly candles and compare every Ganzhi count.
  const counts=Object.fromEntries(ranking.upRanking.map(r=>[r.ganzhi,{up:0,down:0,flat:0}]));
  for(const c of candles){
    if(!c.metadata.isComplete) continue;
    const side=Number(c.close)>Number(c.open)?'up':Number(c.close)<Number(c.open)?'down':'flat';
    counts[c.metadata.displayGanzhi][side]++;
  }
  for(const row of ranking.upRanking) assert.deepEqual(row.counts,counts[row.ganzhi]);
  check('两个月干支榜各60行且递减，与真实月K独立分类计数一致');

  await page.locator('#statistics-ganzhi').fill('丁酉月');
  const ding=await query('#statistics-submit','/api/statistics/ganzhi');
  await expect(page.locator('#statistics-result-title')).toHaveText('丁酉月 · 历史统计');
  await expect(page.locator('#statistics-rows tr')).toHaveCount(ding.matchedCount);
  assert.ok(ding.matches.length>0);
  for(const row of ding.matches){
    const c=candles.find(c=>c.periodId===row.periodId);
    assert.ok(c);
    assert.equal(c.metadata.displayGanzhi,'丁酉');
    assert.equal(c.metadata.startDate,row.date);
    assert.equal(c.metadata.endDate,row.endDate);
    for(const key of ['open','high','low','close','volume']) assert.equal(c[key],row[key]);
  }
  await page.locator('#statistics-rows button').first().click();
  await expect(page.locator('#detail-id')).toHaveText(ding.matches[0].periodId);
  await expect(page.locator('#detail-title')).toHaveText('丁酉月');
  await expect(page.locator('#detail-start')).toHaveText(ding.matches[0].date);
  await expect(page.locator('#detail-end')).toHaveText(ding.matches[0].endDate);
  check('丁酉月筛选使用月干支，明细对应月OHLCV并可定位月K');

  await page.locator('#statistics-start').fill('2020-01-01');
  await page.locator('#statistics-end').fill('2025-12-31');
  await page.locator('#statistics-basis').selectOption('previous_close');
  const filtered=await query('#statistics-rank','/api/statistics/ganzhi/rankings');
  assert.equal(filtered.basis,'previous_close');
  const first=filtered.upRanking[0];
  // Drill-down must use the saved ranking scope, even if controls were edited.
  await page.locator('#statistics-start').fill('2099-01-01');
  const details=await query('#statistics-rank-up tr:first-child button','/api/statistics/ganzhi');
  assert.equal(details.ganzhi,first.ganzhi);
  assert.equal(details.start,'2020-01-01');
  assert.equal(details.end,'2025-12-31');
  assert.equal(details.basis,'previous_close');
  assert.deepEqual(details.counts,first.counts);
  await expect(page.locator('#statistics-start')).toHaveValue('2020-01-01');
  await expect(page.locator('#statistics-scope')).toContainText('收盘 vs 上月收盘');
  await page.locator('#ganzhi-statistics').screenshot({path:fileURLToPath(new URL('month-statistics.png',out))});
  check('月榜遵循日期范围和上月收盘口径，点击后保留榜单统计条件');

  await switchTo('day');
  await expect(page.locator('#statistics-heading')).toHaveText('干支日 · 筛选统计');
  await expect(page.locator('#statistics-rankings')).toBeHidden();
  await expect(page.locator('#statistics-results')).toBeHidden();
  await switchTo('month');
  await expect(page.locator('#statistics-results')).toBeHidden();
  check('日月切换清除旧周期结果，避免混用');

  await page.locator('#statistics-start').fill('2099-01-01');
  const empty=await query('#statistics-rank','/api/statistics/ganzhi/rankings');
  assert.equal(empty.totalSamples,0);
  assert.ok(empty.upRanking.every(r=>r.probabilitiesPct.up===null));
  await page.locator('#statistics-clear').click();
  await query('#statistics-rank','/api/statistics/ganzhi/rankings');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('#ganzhi-statistics').screenshot({path:fileURLToPath(new URL('month-statistics-mobile.png',out))});
  check('月线空样本正确显示，手机排行榜没有页面横向溢出');
  assert.deepEqual(errors,[]);
  await writeFile(new URL('../month-statistics-verification.json',out),JSON.stringify({passed:true,checks,errors,totalMonths:candles.length,samples:ranking.totalSamples,excluded:ranking.totalExcluded},null,2));
}finally{await browser.close();}
