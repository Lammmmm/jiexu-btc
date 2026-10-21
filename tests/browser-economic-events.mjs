import {chromium,expect} from '@playwright/test';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {buildMarkers} from '../frontend/markers/daily-markers.js';

const origin=process.env.APP_URL||'http://127.0.0.1:8000';
const out=new URL('../artifacts/browser/',import.meta.url);
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
const check=name=>{checks.push(name);console.log('PASS',name);};
const economic=await (await page.request.get(origin+'/api/economic-events')).json();
const daily=await (await page.request.get(origin+'/api/candles?period=day')).json();
const byDate=new Map(daily.candles.map(c=>[c.metadata.startDate,c]));
const grouped=new Map();
for(const event of economic.events){
  if(!grouped.has(event.date)) grouped.set(event.date,[]);
  grouped.get(event.date).push(event);
}
const options={period:'day',showCPI:true,showNFP:true,showDay14:false,showGanzhi:false,showTerms:false,economicEvents:grouped};
const all=buildMarkers(daily.candles,{from:0,to:daily.candles.length-1},100000,options);
const expected=economic.events.filter(e=>byDate.has(e.date));
assert.deepEqual(all.map(m=>m.id).sort(),expected.map(e=>e.id).sort());
assert.ok(all.some(m=>m.id==='nfp:2026-07-02'));
assert.ok(!all.some(m=>m.id==='nfp:2026-07-03'));
assert.ok(!all.some(m=>m.id==='nfp:2026-02-06'));
assert.ok(!all.some(m=>m.id==='nfp:2025-10-03'));
assert.ok(all.some(m=>m.id==='nfp:2025-11-20'));
assert.ok(all.some(m=>m.id==='cpi:2025-10-24'));
assert.ok(all.every(m=>m.shape==='arrowDown'&&m.position==='aboveBar'));
assert.equal(buildMarkers(daily.candles,null,1000,{...options,period:'month'}).length,0);
assert.equal(buildMarkers(daily.candles,null,1000,{...options,showCPI:false,showNFP:false}).length,0);
check('全部历史公布日逐根匹配；延期取消和节假日日期准确，不创建未来价格或标到月线');

try{
  await page.goto(origin);
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
  await expect(page.locator('#cpi-toggle')).toBeEnabled();
  await expect(page.locator('#nfp-toggle')).toBeEnabled();
  await expect(page.locator('#cpi-toggle')).not.toBeChecked();
  await expect(page.locator('#nfp-toggle')).not.toBeChecked();
  assert.deepEqual(await page.locator('.switches input').evaluateAll(nodes=>nodes.map(n=>n.id)),
    ['cpi-toggle','nfp-toggle','day14-toggle','ganzhi-toggle','term-toggle']);
  await page.evaluate(async()=>{
    const {MarketChart}=await import('/static/charts/market-chart.js');
    const original=MarketChart.prototype.setOptions;
    MarketChart.prototype.setOptions=function(...args){window.economicChart=this;return original.apply(this,args);};
  });
  await page.locator('#cpi-toggle').check();
  await page.waitForFunction(()=>window.economicChart&&JSON.parse(window.economicChart.markerKey||'[]').some(m=>m.id?.startsWith('cpi:')));
  let markers=await page.evaluate(()=>JSON.parse(window.economicChart.markerKey));
  assert.ok(markers.some(m=>m.id==='cpi:2026-09-11'));
  assert.ok(!markers.some(m=>m.id?.startsWith('nfp:')));
  assert.equal(await page.evaluate(()=>window.economicChart.pricePoints.find(p=>p.time==='2026-09-11').wickColor),'#82baff');
  await page.locator('#nfp-toggle').check();
  await page.waitForFunction(()=>JSON.parse(window.economicChart.markerKey).some(m=>m.id==='nfp:2026-10-02'));
  assert.equal(await page.evaluate(()=>window.economicChart.pricePoints.find(p=>p.time==='2026-10-02').wickColor),'#c5a1ff');
  check('红框位置两个默认关闭的勾选项；CPI蓝色、非农紫色标记和影线独立开关');

  // Zoom to a period with both national releases, then move over a real candle.
  const target=economic.events.find(e=>e.kind==='cpi'&&e.date==='2026-09-11');
  await page.evaluate(()=>{
    const chart=window.economicChart;
    const i=chart.candles.findIndex(c=>c.metadata.startDate==='2026-09-11');
    chart.chart.timeScale().setVisibleLogicalRange({from:i-22,to:i+27});
  });
  await page.waitForFunction(()=>JSON.parse(window.economicChart.markerKey).some(m=>m.text==='CPI'));
  await page.locator('#chart').scrollIntoViewIfNeeded();
  const xy=await page.evaluate(()=>{
    const chart=window.economicChart,day=chart.byDate.get('2026-09-11'),box=chart.container.getBoundingClientRect();
    return {x:box.x+chart.chart.timeScale().timeToCoordinate('2026-09-11'),y:box.y+chart.series.priceToCoordinate(Number(day.close))};
  });
  await page.mouse.move(xy.x,xy.y);
  await expect(page.locator('#detail-id')).toHaveText('2026-09-11');
  await expect(page.locator('#economic-detail')).toBeVisible();
  await expect(page.locator('#economic-detail-list')).toContainText('20:30');
  await expect(page.locator('#economic-detail-list a')).toHaveAttribute('href',target.sourceUrl);
  await page.locator('.workspace').screenshot({path:fileURLToPath(new URL('economic-events-desktop.png',out))});
  check('公布日K线侧栏显示北京时间与BLS发布原文链接，实际图表标记位置正确');

  await page.locator('#day14-toggle').check();
  await page.waitForFunction(()=>JSON.parse(window.economicChart.markerKey).some(m=>m.text==='14号'));
  markers=await page.evaluate(()=>JSON.parse(window.economicChart.markerKey));
  assert.ok(markers.some(m=>m.id?.startsWith('cpi:')));
  assert.ok(markers.some(m=>m.id?.startsWith('nfp:')));
  assert.ok(markers.some(m=>m.text==='14号'));
  assert.ok(markers.some(m=>m.text==='甲申'||m.text==='白露'));
  await page.locator('[data-period=month]').click();
  await expect(page.locator('#cpi-toggle')).toBeDisabled();
  await expect(page.locator('#nfp-toggle')).toBeDisabled();
  await page.waitForFunction(()=>window.economicChart.options.period==='month');
  assert.ok(!(await page.evaluate(()=>JSON.parse(window.economicChart.markerKey))).some(m=>m.id?.startsWith('cpi:')||m.id?.startsWith('nfp:')));
  await page.locator('[data-period=day]').click();
  await expect(page.locator('#cpi-toggle')).toBeEnabled();
  await expect(page.locator('#cpi-toggle')).toBeChecked();
  await expect(page.locator('#nfp-toggle')).toBeChecked();
  await page.waitForFunction(()=>JSON.parse(window.economicChart.markerKey).some(m=>m.id==='nfp:2026-10-02'));
  check('与14号、干支、节气共存；非日线禁用，返回日线保留勾选状态');

  const before=await page.evaluate(()=>({range:window.economicChart.chart.timeScale().getVisibleLogicalRange(),markers:window.economicChart.markerKey}));
  await page.evaluate(()=>{
    const chart=window.economicChart;
    chart.setData(chart.candles,'day',true);
    chart.setEconomicEvents([...chart.economicEvents.values()].flat());
  });
  await expect.poll(()=>page.evaluate(()=>window.economicChart.markerKey)).toBe(before.markers);
  assert.deepEqual(await page.evaluate(()=>window.economicChart.chart.timeScale().getVisibleLogicalRange()),before.range);
  await page.locator('#cpi-toggle').uncheck();
  await page.waitForFunction(()=>!JSON.parse(window.economicChart.markerKey).some(m=>m.id?.startsWith('cpi:')));
  await page.locator('#nfp-toggle').uncheck();
  await page.waitForFunction(()=>!JSON.parse(window.economicChart.markerKey).some(m=>m.id?.startsWith('nfp:')));
  assert.equal(await page.evaluate(()=>window.economicChart.pricePoints.find(p=>p.time==='2026-09-11').wickColor),undefined);
  check('数据刷新保留缩放和经济事件标记；取消勾选恢复原始影线');

  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('#cpi-toggle')).toBeVisible();
  await expect(page.locator('#nfp-toggle')).toBeVisible();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('.chart-options').screenshot({path:fileURLToPath(new URL('economic-events-mobile-controls.png',out))});
  assert.deepEqual(errors,[]);
  check('手机按钮无溢出，浏览器无运行错误');
  await writeFile(new URL('economic-events-verification.json',out),JSON.stringify({passed:true,checks,errors,matchedHistoricalCandles:expected.length},null,2));
}finally{await browser.close();}
