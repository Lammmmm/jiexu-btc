import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { buildMarkers } from '../frontend/markers/daily-markers.js';

const origin=process.env.APP_URL||'http://127.0.0.1:8000';
const out=new URL('../artifacts/browser/',import.meta.url);
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050},deviceScaleFactor:1});
const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
const check=(name)=>{checks.push(name);console.log('PASS',name);};
async function verifyGanzhiPanel(period) {
  const qs=period==='week'?'&anchor=2026-01-01':'';
  const data=await (await page.request.get(origin+'/api/candles?period='+period+qs)).json();
  const id=await page.locator('#detail-id').textContent();
  const candle=data.candles.find(c=>c.periodId===id);
  assert.ok(candle);
  const suffix={day:'日',week:' · 七日',month:'月',year:'年'}[period];
  assert.equal(await page.locator('#detail-title').textContent(),candle.metadata.displayGanzhi+suffix);
  assert.equal(await page.locator('#detail-ganzhi').textContent(),candle.metadata.displayGanzhi);
  assert.equal(await page.locator('#calendar-detail').isVisible(),true);
  assert.equal(await page.locator('#detail-term').count(),0);
  assert.doesNotMatch(await page.locator('.detail-panel').textContent(),/节气|白露月|寒露月/);
}

try {
  await page.goto(origin);
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.querySelector('#last-price').textContent!=='—');
  assert.ok(await page.locator('#chart canvas').count()>0);
  assert.match(await page.locator('#data-count').textContent(),/3,319|[0-9,]+ 根/);
  await page.screenshot({path:fileURLToPath(new URL('daily.png',out)),fullPage:true});
  await verifyGanzhiPanel('day');
  check('真实日线与日干支显示正确');
  await page.locator('[data-period=week]').click();
  await page.locator('#message').filter({hasText:'请先设置'}).waitFor();
  assert.equal(await page.locator('[data-period=day]').getAttribute('aria-pressed'),'true');
  check('锚点未配置时明确提示，保持日线');

  await page.locator('#anchor').fill('2026-01-01');
  await page.locator('#anchor-form button[type=submit]').click();
  await page.waitForFunction(()=>document.querySelector('[data-period=week]').getAttribute('aria-pressed')==='true');
  assert.match(await page.locator('#detail-id').textContent(),/week:2026-01-01:/);
  assert.equal(await page.locator('#ganzhi-toggle').isDisabled(),true);
  await verifyGanzhiPanel('week');
  check('自定义七日线及起始日干支显示正确');

  for(const period of ['month','year']){
    await page.locator('[data-period='+period+']').click();
    await page.waitForFunction(p=>document.querySelector('[data-period='+p+']').getAttribute('aria-pressed')==='true',period);
    await page.locator('#chart-overlay').waitFor({state:'hidden'});
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
    const box=await page.locator('#chart').boundingBox();
    await page.mouse.click(box.x+box.width*0.5,box.y+170);
    await page.locator('#unpin').waitFor({state:'visible'});
    assert.match(await page.locator('#detail-start').textContent(),/^\d{4}-\d{2}-\d{2}$/);
    assert.match(await page.locator('#detail-end').textContent(),/^\d{4}-\d{2}-\d{2}$/);
    await verifyGanzhiPanel(period);
    await page.screenshot({path:fileURLToPath(new URL(period+'.png',out)),fullPage:true});
    await page.locator('#unpin').click();
    check(period==='month'?'节气月切换、点击固定详情与起止日期显示':'立春年切换、点击固定详情与起止日期显示');
  }
  await page.locator('[data-period=day]').click();
  await page.waitForFunction(()=>document.querySelector('[data-period=day]').getAttribute('aria-pressed')==='true');
  await page.locator('#ganzhi-toggle').uncheck();
  await page.locator('#term-toggle').uncheck();
  assert.equal(await page.locator('#ganzhi-toggle').isChecked(),false);
  await page.locator('#ganzhi-toggle').check();
  await page.locator('#term-toggle').check();
  const daily=await (await page.request.get(origin+'/api/candles?period=day')).json();
  const index=daily.candles.findIndex(c=>c.metadata.startDate==='2026-09-07');
  const markers=buildMarkers(daily.candles,{from:index,to:index+1},1000,{period:'day',showGanzhi:true,showTerms:true});
  assert.ok(markers.some(m=>m.text==='甲申'&&m.time==='2026-09-07'));
  assert.ok(markers.some(m=>m.text==='白露'&&m.time==='2026-09-07'));
  assert.equal(buildMarkers(daily.candles,{from:index,to:index+1},1000,{period:'day',showGanzhi:false,showTerms:false}).length,0);
  check('干支与节气开关、真实标记数据及日期对应正确');

  if(await page.locator('#debug-panel').isVisible()){
    await page.locator('#debug-date').fill('2026-09-07');
    await page.locator('#debug-form button').click();
    await page.waitForFunction(()=>document.querySelector('#debug-output').textContent.includes('甲申'));
    const debug=JSON.parse(await page.locator('#debug-output').textContent());
    assert.equal(debug.solar_month_id,'2026-bailu');
    assert.equal(debug.solar_year_id,2026);
    assert.ok(debug.custom_week_id.startsWith('week:2026-01-01:'));
    check('DEBUG 查询包含干支、节气、传统月/年、自定义周及原始行情');
  }
  await page.locator('#clear-anchor').click();
  assert.equal(await page.locator('#anchor').inputValue(),'');
  await page.reload();
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
  assert.equal(await page.locator('#anchor').inputValue(),'');
  check('测试锚点已清除，刷新后仍未配置');

  await page.locator('#sync').click();
  await page.waitForFunction(()=>!document.querySelector('#sync').disabled);
  check('手动增量同步按钮可用');
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:fileURLToPath(new URL('mobile.png',out)),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  check('手机宽度页面没有横向溢出');
  assert.deepEqual(errors,[]);
  check('浏览器无 JavaScript 运行错误');
  await writeFile(new URL('../browser-verification.json',out),JSON.stringify({origin,checks,errors,passed:true},null,2));
} finally {
  await browser.close();
}
