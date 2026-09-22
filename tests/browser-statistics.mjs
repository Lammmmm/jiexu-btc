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
page.on('pageerror',error=>errors.push(error.message));
const check=name=>{checks.push(name);console.log('PASS',name);};
async function rankings(){
  const response=page.waitForResponse(r=>r.url().includes('/api/statistics/ganzhi/rankings'));
  await page.locator('#statistics-rank').click();
  const data=await (await response).json();
  await expect(page.locator('#statistics-rankings')).toBeVisible();
  await expect(page.locator('#statistics-rank')).toBeEnabled();
  return data;
}
async function single(){
  const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/statistics/ganzhi');
  await page.locator('#statistics-submit').click();
  const data=await (await response).json();
  await expect(page.locator('#statistics-results')).toBeVisible();
  return data;
}
try{
  await page.goto(origin);
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
  const data=await rankings();
  for(const side of ['up','down']){
    await expect(page.locator('#statistics-rank-'+side+' tr')).toHaveCount(60);
    const rates=data[side+'Ranking'].filter(r=>r.sampleCount).map(r=>Number(r.probabilitiesPct[side]));
    assert.deepEqual(rates,[...rates].sort((a,b)=>b-a));
    await expect(page.locator('#statistics-rank-'+side+' button').first()).toHaveText(data[side+'Ranking'][0].ganzhi);
  }
  check('干支输入为空时可遍历；两榜均含60行并按概率递减');
  const first=data.upRanking[0];
  await page.locator('#statistics-rank-up button').first().click();
  await expect(page.locator('#statistics-result-title')).toContainText(first.ganzhi);
  await expect(page.locator('#statistics-sample-count')).toHaveText(String(first.sampleCount));
  await expect(page.locator('#statistics-up-pct')).toHaveText(Number(first.probabilitiesPct.up).toFixed(2)+'%');
  check('排行榜点击联动单干支明细，样本和概率一致');
  await page.locator('#ganzhi-statistics').screenshot({path:fileURLToPath(new URL('statistics-ranking.png',out))});
  await page.locator('#statistics-clear').click();
  await page.locator('#statistics-ganzhi').fill('丁酉');
  const ding=await single();
  await expect(page.locator('#statistics-rows tr')).toHaveCount(ding.matchedCount);
  await expect(page.locator('#statistics-sample-count')).toHaveText(String(ding.sampleCount));
  const day=ding.matches[0].date;
  await page.locator('#statistics-rows button').first().click();
  await expect(page.locator('#detail-id')).toHaveText(day);
  await expect(page.locator('#detail-ganzhi')).toHaveText('丁酉');
  check('丁酉筛选和逐日表正确，点击日期定位K线并固定详情');
  await page.locator('#statistics-basis').selectOption('previous_close');
  const previous=await single();
  assert.equal(previous.basis,'previous_close');
  check('可切换收盘相对昨收口径');
  await page.locator('[data-period=year]').click();
  await expect(page.locator('#ganzhi-statistics')).toBeHidden();
  await page.locator('[data-period=day]').click();
  await expect(page.locator('#ganzhi-statistics')).toBeVisible();
  check('年线隐藏统计面板，回到日线恢复');
  await page.locator('#statistics-ganzhi').fill('丁酉');
  await page.locator('#statistics-start').fill('2099-01-01');
  await page.locator('#statistics-end').fill('2099-12-31');
  const empty=await single();
  assert.equal(empty.sampleCount,0);
  await expect(page.locator('#statistics-up-pct')).toHaveText('—');
  const emptyRank=await rankings();
  assert.ok(emptyRank.upRanking.every(r=>r.sampleCount===0));
  check('无样本显示横线，全部干支仍保留在榜中');
  await page.locator('#statistics-clear').click();
  await page.locator('#statistics-ganzhi').fill('甲丑');
  await page.locator('#statistics-submit').click();
  await expect(page.locator('#statistics-status')).toContainText('有效的六十甲子');
  check('非法干支给出明确提示');
  await page.locator('#statistics-clear').click();
  await page.locator('#statistics-start').fill('2026-01-01');
  await page.locator('#statistics-end').fill('2025-01-01');
  await page.locator('#statistics-rank').click();
  await expect(page.locator('#statistics-ranking-status')).toContainText('开始日期不能晚于结束日期');
  check('遍历拒绝颠倒日期范围');
  await page.locator('#statistics-clear').click();
  await rankings();
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('#ganzhi-statistics').screenshot({path:fileURLToPath(new URL('statistics-mobile.png',out))});
  assert.deepEqual(errors,[]);
  check('手机双榜布局无横向溢出，浏览器无运行错误');
  await writeFile(new URL('../statistics-browser-verification.json',out),JSON.stringify({passed:true,checks,errors},null,2));
}finally{await browser.close();}
