import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';

const origin=process.env.APP_URL||'http://127.0.0.1:8000';
const browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
let status=await (await page.request.get(origin+'/api/status')).json();
const cached=new Map(),counts=new Map();
let hold=false,fail=false,pending=[],revision=0;
await page.addInitScript(()=>{
  const original=window.setInterval;
  window.setInterval=(callback,delay,...args)=>{
    if(delay===5000){window.refreshPoll=callback;return 0;}
    return original(callback,delay,...args);
  };
});
await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname;
  counts.set(path,(counts.get(path)||0)+1);
  if(path==='/api/status'){await route.fulfill({json:status});return;}
  if(!['/api/candles','/api/calendar/days','/api/statistics/ganzhi','/api/statistics/ganzhi/rankings'].includes(path)){
    await route.continue();return;
  }
  const key=url.pathname+url.search;
  if(!cached.has(key)) cached.set(key,await (await route.fetch()).json());
  const data=structuredClone(cached.get(key));
  if(revision&&path==='/api/candles'){
    const last=data.candles.at(-1);
    last.close=String(Number(last.close)+revision);
    last.high=String(Math.max(Number(last.high),Number(last.close)));
  }
  if(revision&&path==='/api/calendar/days')
    for(const day of data.days) if(day.strength) day.strength.medianAbsoluteChangePct='2.345000';
  if(revision&&path==='/api/statistics/ganzhi') data.averageChangePct='1.234000';
  if(hold&&path!=='/api/candles') await new Promise(resolve=>pending.push(resolve));
  if(fail===true||(fail==='components'&&path!=='/api/candles')){await route.fulfill({status:503,json:{detail:'测试：暂时无法刷新'}});return;}
  await route.fulfill({json:data});
});
const pathCount=path=>counts.get(path)||0;
const settle=()=>page.waitForFunction(()=>
  window.refreshPoll&&document.querySelector('#ganzhi-calendar-status').textContent.includes('已显示')
);
try{
  await page.goto(origin);
  await settle();
  assert.equal(pathCount('/api/candles'),1,'启动时不应重复读取相同行情');
  assert.equal(pathCount('/api/calendar/days'),1,'启动时不应重复读取日历');
  // Capture the real chart instance through its existing date-location path.
  await page.evaluate(async()=>{
    const {MarketChart}=await import('/static/charts/market-chart.js');
    const original=MarketChart.prototype.focusDate;
    MarketChart.prototype.focusDate=function(...args){
      window.refreshChart=this;return original.apply(this,args);
    };
  });
  await page.locator('#ganzhi-calendar .fc-daygrid-day:not(.fc-day-other) .ganzhi-calendar-ganzhi').first().click();
  await expect(page.locator('#statistics-results')).toBeVisible();
  await expect(page.locator('#statistics-yearly')).toBeVisible();
  await page.locator('#statistics-rows button').first().click();
  await page.waitForFunction(()=>Boolean(window.refreshChart));
  await page.locator('#statistics-rank').click();
  await expect(page.locator('#statistics-rankings')).toBeVisible();
  await expect(page.locator('#statistics-rank')).toBeEnabled();
  await page.evaluate(()=>{
    const chart=window.refreshChart;
    window.chartCalls={full:0,update:0,emptyMarkers:0};
    for(const series of [chart.series,chart.volume]){
      const full=series.setData.bind(series),update=series.update.bind(series);
      series.setData=data=>{window.chartCalls.full++;return full(data);};
      series.update=data=>{window.chartCalls.update++;return update(data);};
    }
    const markers=chart.markerApi.setMarkers.bind(chart.markerApi);
    chart.markerApi.setMarkers=data=>{
      if(!data.length) window.chartCalls.emptyMarkers++;
      return markers(data);
    };
    window.refreshRange=chart.chart.timeScale().getVisibleLogicalRange();
  });
  await page.locator('#statistics-results').scrollIntoViewIfNeeded();
  const before=await page.evaluate(()=>({
    calendar:document.querySelector('#ganzhi-calendar .ganzhi-calendar-selected .ganzhi-calendar-cell').textContent,
    summary:document.querySelector('#ganzhi-calendar-month-summary').textContent,
    height:document.documentElement.scrollHeight,scroll:scrollY,
  }));
  const initialCalls=Object.fromEntries(counts);
  hold=true;revision=1;status={...status,lastSync:status.lastSync+1};
  await page.evaluate(()=>{window.refreshTask=window.refreshPoll();});
  await expect.poll(()=>pending.length).toBeGreaterThanOrEqual(3);
  const during=await page.evaluate(()=>({
    calendar:document.querySelector('#ganzhi-calendar .ganzhi-calendar-selected .ganzhi-calendar-cell').textContent,
    summary:document.querySelector('#ganzhi-calendar-month-summary').textContent,
    height:document.documentElement.scrollHeight,scroll:scrollY,
    highlighted:window.refreshChart.highlightDates.size,
  }));
  assert.equal(during.calendar,before.calendar,'后台刷新期间日历不应清空');
  assert.equal(during.summary,before.summary,'后台刷新期间月度统计不应消失');
  assert.equal(during.height,before.height,'后台刷新不应改变页面高度');
  assert.equal(during.scroll,before.scroll,'后台刷新不应改变阅读位置');
  assert.ok(during.highlighted>0,'后台刷新不应取消 K 线筛选高亮');
  for(const id of ['statistics-results','statistics-yearly','statistics-rankings','ganzhi-calendar-strength-detail'])
    await expect(page.locator('#'+id)).toBeVisible();
  hold=false;pending.splice(0).forEach(resolve=>resolve());
  await page.evaluate(()=>window.refreshTask);
  await expect(page.locator('#ganzhi-calendar .ganzhi-calendar-selected .ganzhi-calendar-amplitude')).toContainText('2.35%');
  await expect(page.locator('#statistics-summary')).toContainText('+1.23%');
  await expect(page.locator('#statistics-submit')).toBeEnabled();
  await expect(page.locator('#statistics-rank')).toBeEnabled();
  for(const path of ['/api/candles','/api/calendar/days','/api/statistics/ganzhi','/api/statistics/ganzhi/rankings'])
    assert.equal(pathCount(path)-(initialCalls[path]||0),1,path+' 每次行情同步只请求一次');
  const after=await page.evaluate(()=>({
    calls:window.chartCalls,
    range:window.refreshChart.chart.timeScale().getVisibleLogicalRange(),
    previousRange:window.refreshRange,
  }));
  assert.equal(after.calls.full,0,'末根 K 线更新应使用增量接口');
  assert.equal(after.calls.update,1,'只更新发生变化的价格 K 线');
  assert.equal(after.calls.emptyMarkers,0,'刷新期间不应清空干支和节气标记');
  assert.deepEqual(after.range,after.previousRange,'保留图表缩放位置');
  console.log('PASS 延迟刷新期间保留日历、详情、排行榜、筛选高亮和阅读位置；完成后更新数据');

  // A new sync snapshot with identical candle values should not redraw the series.
  const callsBefore=await page.evaluate(()=>({...window.chartCalls}));
  status={...status,lastSync:status.lastSync+1};
  await page.evaluate(()=>window.refreshPoll());
  await expect(page.locator('#statistics-submit')).toBeEnabled();
  assert.deepEqual(await page.evaluate(()=>window.chartCalls),callsBefore);
  console.log('PASS 相同行情不重绘图表，后台同步不重复请求日历');

  fail='components';status={...status,lastSync:status.lastSync+1};
  await page.evaluate(()=>window.refreshPoll());
  for(const id of ['statistics-results','statistics-yearly','statistics-rankings','ganzhi-calendar-strength-detail'])
    await expect(page.locator('#'+id)).toBeVisible();
  for(const id of ['statistics-status','statistics-ranking-status','ganzhi-calendar-status'])
    await expect(page.locator('#'+id)).toContainText('仍显示上次数据');
  fail=false;
  const failedCalendar=pathCount('/api/calendar/days');
  await page.evaluate(()=>window.refreshPoll());
  assert.equal(pathCount('/api/calendar/days'),failedCalendar+1);
  for(const id of ['statistics-status','statistics-ranking-status','ganzhi-calendar-status'])
    await expect(page.locator('#'+id)).not.toHaveClass(/statistics-error/);
  console.log('PASS 日历和统计更新失败时保留内容，随后自动重试并清除错误状态');

  // A temporary failure retains the last successful content and retries on next poll.
  const visibleBefore=await page.locator('#ganzhi-calendar .ganzhi-calendar-selected .ganzhi-calendar-cell').textContent();
  fail=true;status={...status,lastSync:status.lastSync+1};
  await page.evaluate(()=>window.refreshPoll());
  await expect(page.locator('#chart-overlay')).toBeHidden();
  await expect(page.locator('#statistics-results')).toBeVisible();
  await expect(page.locator('#ganzhi-calendar-strength-detail')).toBeVisible();
  assert.equal(await page.locator('#ganzhi-calendar .ganzhi-calendar-selected .ganzhi-calendar-cell').textContent(),visibleBefore);
  fail=false;
  const failedCandles=pathCount('/api/candles');
  await page.evaluate(()=>window.refreshPoll());
  assert.equal(pathCount('/api/candles'),failedCandles+1,'未成功的行情刷新应自动重试');
  await expect(page.locator('#message')).toBeHidden();
  console.log('PASS 暂时刷新失败保留画面，下一次状态轮询自动恢复');

  const chartRegression=await page.evaluate(async()=>{
    const chart=window.refreshChart,base=structuredClone(chart.candles);
    const before={...window.chartCalls};
    const corrected=structuredClone(base);corrected[0].high=String(Number(corrected[0].high)+1);
    chart.setData(corrected,'day',true);
    const repairedHigh=chart.series.data()[0].high;
    const correctionFull=window.chartCalls.full-before.full;
    const next=structuredClone(corrected),last=structuredClone(next.at(-1));
    const day=new Date(last.metadata.startDate+'T00:00:00Z');day.setUTCDate(day.getUTCDate()+1);
    const date=day.toISOString().slice(0,10);
    last.periodId=date;last.metadata.startDate=date;last.metadata.endDate=date;
    next.push(last);
    const appendBefore={...window.chartCalls};
    chart.setData(next,'day',true);
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    return {
      repairedHigh,expectedHigh:Number(corrected[0].high),correctionFull,
      appended:chart.series.data().length===next.length,
      appendFull:window.chartCalls.full-appendBefore.full,
      appendUpdates:window.chartCalls.update-appendBefore.update,
      range:chart.chart.timeScale().getVisibleLogicalRange(),previousRange:window.refreshRange,
    };
  });
  assert.equal(chartRegression.repairedHigh,chartRegression.expectedHigh);
  assert.equal(chartRegression.correctionFull,1,'历史价格修正必须更新完整数据');
  assert.equal(chartRegression.appended,true);
  assert.equal(chartRegression.appendFull,0);
  assert.equal(chartRegression.appendUpdates,2,'新增日期更新 K 线和成交量两个序列');
  assert.deepEqual(chartRegression.range,chartRegression.previousRange);
  console.log('PASS 新增 K 线采用增量更新；历史价格修正正确生效并保留缩放');
  assert.deepEqual(errors,[]);
}finally{
  hold=false;pending.splice(0).forEach(resolve=>resolve());
  await browser.close();
}
