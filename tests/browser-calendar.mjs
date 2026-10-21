import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import {monthJudgement} from '../frontend/calendar/ganzhi-calendar.js';
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
const monthKey=title=>{
  const match=title.match(/(\d{4})年(\d{1,2})月/);
  assert.ok(match);
  return match[1]+'-'+match[2].padStart(2,'0');
};
const fakeDays=Array.from({length:30},(_,index)=>({
  date:'2026-09-'+String(index+1).padStart(2,'0'),
  signalDirection:'neutral',actualDirection:null,actualChangePct:null,
}));
fakeDays[0]={...fakeDays[0],signalDirection:'up',actualDirection:'up',actualChangePct:'1'};
fakeDays[1]={...fakeDays[1],signalDirection:'down',actualDirection:'down',actualChangePct:'-1'};
fakeDays[2]={...fakeDays[2],signalDirection:'up',actualDirection:'down',actualChangePct:'-1'};
fakeDays[3]={...fakeDays[3],signalDirection:'up',actualDirection:'flat',actualChangePct:'0'};
fakeDays[4]={...fakeDays[4],actualDirection:'up',actualChangePct:'1'};
const octoberStart=Date.parse('2026-10-01T00:00:00+08:00');
assert.deepEqual(monthJudgement(fakeDays,octoberStart-1,'2026-09',octoberStart-1),{state:'unfinished'});
assert.deepEqual(monthJudgement(fakeDays,octoberStart-1,'2026-09',octoberStart),{state:'stale'});
assert.deepEqual(monthJudgement(fakeDays,octoberStart,'2026-09',octoberStart),{
  state:'complete',correct:2,judged:4,excluded:26,accuracyPct:50,
});
check('月末边界正确；行情未同步单列，平盘和无方向判断按规则处理');
try{
  const firstResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days');
  await page.goto(origin);
  await page.locator('#chart-overlay').waitFor({state:'hidden'});
  const first=await (await firstResponse).json();
  await expect(page.locator('#ganzhi-calendar .fc-daygrid-day')).toHaveCount(first.days.length);
  await expect(page.locator('#ganzhi-calendar-status')).toContainText('全部本地历史有效样本');
  const sectionPosition=await page.evaluate(()=>{
    const calendar=document.querySelector('#ganzhi-calendar-panel').getBoundingClientRect();
    const stats=document.querySelector('#ganzhi-statistics').getBoundingClientRect();
    return calendar.bottom<=stats.top;
  });
  assert.equal(sectionPosition,true);
  const day=first.days.find(d=>d.ganzhi&&d.sampleCount&&d.solarTerm)||first.days.find(d=>d.ganzhi&&d.sampleCount);
  assert.ok(day);
  const cell=page.locator('#ganzhi-calendar .fc-daygrid-day[data-date="'+day.date+'"]');
  await expect(cell.locator('.ganzhi-calendar-ganzhi')).toHaveText(day.ganzhi);
  const expectedLabel=day.signalDirection==='up'?'上涨':day.signalDirection==='down'?'下跌':'';
  const expectedPct=day.signalPct===null?Number(day.upPct).toFixed(1)+'%':Number(day.signalPct).toFixed(1)+'%';
  await expect(cell.locator('.ganzhi-calendar-rate')).toContainText(expectedLabel+ ' '+expectedPct);
  if(day.solarTerm) await expect(cell.locator('.ganzhi-calendar-term')).toHaveText(day.solarTerm);
  assert.match(await cell.getAttribute('title'),new RegExp('有效样本 '+day.sampleCount));
  const finished=first.days.find(d=>d.actualChangePct!==null);
  assert.ok(finished);
  const finishedCell=page.locator('#ganzhi-calendar .fc-daygrid-day[data-date="'+finished.date+'"]');
  const signed=(Number(finished.actualChangePct)>0?'+':'')+Number(finished.actualChangePct).toFixed(2)+'%';
  await expect(finishedCell.locator('.ganzhi-calendar-actual')).toContainText('实际 '+signed);
  const pending=first.days.find(d=>d.actualChangePct===null);
  if(pending) await expect(page.locator('#ganzhi-calendar .fc-daygrid-day[data-date="'+pending.date+'"] .ganzhi-calendar-actual')).toHaveCount(0);
  await expect(page.locator('#ganzhi-calendar-threshold')).toHaveValue('3');
  await expect(page.locator('#ganzhi-calendar-window')).toHaveValue('all');
  await expect(cell.locator('.ganzhi-calendar-amplitude')).toContainText(
    Number(day.strength.medianAbsoluteChangePct).toFixed(2)+'%'
  );
  await expect(cell.locator('.ganzhi-calendar-large')).toContainText(
    Number(day.strength.largeMove.probabilitiesPct.total).toFixed(1)+'%'
  );
  await expect(cell.locator('.ganzhi-calendar-samples')).toHaveText('方向样本 '+day.sampleCount);
  assert.equal(day.strength.start,'2023-01-01');
  assert.ok(day.strength.sampleStart>='2023-01-01');
  assert.ok(day.strength.sampleCount<day.sampleCount);
  assert.equal(day.strength.largeMove.sampleCount,day.strength.sampleCount);
  await expect(cell.locator('.ganzhi-calendar-strength-samples')).toHaveText('幅度样本 '+day.strength.sampleCount);
  await expect(page.locator('#ganzhi-calendar-benchmark')).toContainText('2023-01-01 起');
  await expect(page.locator('#ganzhi-calendar-benchmark')).toContainText('幅度样本 '+first.benchmark.strength.sampleCount.toLocaleString()+' 根');

  await expect(page.locator('#ganzhi-calendar-benchmark')).toContainText(
    Number(first.benchmark.strength.medianAbsoluteChangePct).toFixed(2)+'%'
  );
  assert.ok(await cell.evaluate(el=>el.style.getPropertyValue('--ganzhi-strength-bg')));
  check('日历显示方向、典型幅度、大行情率、样本和实际涨跌，并按基准着色');

  const monthBefore=await page.locator('.fc-toolbar-title').textContent();
  const currentMonth=monthJudgement(first.days,first.asOf,monthKey(monthBefore));
  await expect(page.locator('#ganzhi-calendar-month-summary')).toContainText(
    currentMonth.state==='unfinished'?'未完成':'正确率 '+currentMonth.accuracyPct.toFixed(2)+'%'
  );
  const previous=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days');
  await page.locator('.fc-prev-button').click();
  const previousData=await (await previous).json();
  const pastMonth=monthJudgement(previousData.days,previousData.asOf,
    monthKey(await page.locator('.fc-toolbar-title').textContent()));
  assert.equal(pastMonth.state,'complete');
  await expect(page.locator('#ganzhi-calendar-month-summary')).toContainText(
    '正确率 '+pastMonth.accuracyPct.toFixed(2)+'%'
  );
  await expect(page.locator('#ganzhi-calendar-month-summary')).toContainText(
    '判断正确 '+pastMonth.correct+' / '+pastMonth.judged+' 天'
  );
  await page.locator('#ganzhi-calendar-panel').screenshot({path:fileURLToPath(new URL('ganzhi-calendar-completed-month.png',out))});
  check('未走完月份显示未完成；已结束月份统计方向判断正确率');
  assert.notEqual(await page.locator('.fc-toolbar-title').textContent(),monthBefore);
  const next=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days');
  await page.locator('.fc-next-button').click();
  await next;
  await expect(page.locator('.fc-toolbar-title')).toHaveText(monthBefore);
  check('FullCalendar上一月、下一月导航和可见日期加载正确');

  await cell.click();
  await expect(page.locator('#statistics-ganzhi')).toHaveValue(day.ganzhi);
  await expect(page.locator('#statistics-result-title')).toContainText(day.ganzhi);
  await expect(cell).toHaveClass(/ganzhi-calendar-selected/);
  await expect(page.locator('#ganzhi-calendar-strength-detail')).toBeVisible();
  await expect(page.locator('#ganzhi-calendar-strength-title')).toContainText(day.date+' · '+day.ganzhi);
  await expect(page.locator('#ganzhi-calendar-strength-cards>div')).toHaveCount(8);
  await expect(page.locator('#ganzhi-calendar-strength-cards')).toContainText('典型日内振幅');
  const strengthCards=page.locator('#ganzhi-calendar-strength-cards>div');
  for(const index of [0,1,2,3,4,5,6,7]) await expect(strengthCards.nth(index)).toContainText('2023-01-01 起');
  await expect(strengthCards.nth(1)).toContainText(day.strength.largeMove.counts.total+' / '+day.strength.sampleCount+' 根');
  await expect(strengthCards.nth(4)).toContainText(day.strength.largeMove.counts.up+' / '+day.strength.sampleCount+' 根');
  await expect(strengthCards.nth(5)).toContainText(day.strength.largeMove.counts.down+' / '+day.strength.sampleCount+' 根');
  await expect(page.locator('#ganzhi-calendar-strength-scope')).toContainText('幅度样本 '+day.strength.sampleCount+' 根');
  const intradayCard=page.locator('#ganzhi-calendar-strength-cards>div').last();
  await expect(intradayCard).toContainText(day.strength.intradayRangeStart+' 起');
  await expect(intradayCard).toContainText('振幅样本 '+day.strength.intradayRangeSampleCount+' 根');
  await expect(intradayCard.locator('strong')).toHaveText(
    day.strength.medianIntradayRangePct==null?'—':Number(day.strength.medianIntradayRangePct).toFixed(2)+'%'
  );
  check('点击日期展示强度详情，并保持同干支历史统计联动');

  const thresholdResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days'&&
    new URL(r.url()).searchParams.get('threshold')==='5');
  await page.locator('#ganzhi-calendar-threshold').selectOption('5');
  const thresholdData=await (await thresholdResponse).json();
  const thresholdDay=thresholdData.days.find(d=>d.date===day.date);
  assert.equal(thresholdDay.upPct,day.upPct);
  assert.equal(thresholdDay.strength.medianAbsoluteChangePct,day.strength.medianAbsoluteChangePct);
  assert.ok(Number(thresholdDay.strength.largeMove.probabilitiesPct.total)<=Number(day.strength.largeMove.probabilitiesPct.total));
  await expect(cell.locator('.ganzhi-calendar-large')).toContainText(
    Number(thresholdDay.strength.largeMove.probabilitiesPct.total).toFixed(1)+'%'
  );
  await expect(page.locator('#ganzhi-calendar-strength-cards')).toContainText('≥5%');

  const recentResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days'&&
    new URL(r.url()).searchParams.get('window')==='recent3');
  await page.locator('#ganzhi-calendar-window').selectOption('recent3');
  const recentData=await (await recentResponse).json();
  const recentDay=recentData.days.find(d=>d.date===day.date);
  assert.equal(recentDay.strength.start,recentData.windowStart);
  assert.equal(recentDay.strength.sampleCount,recentDay.sampleCount);
  await expect(cell.locator('.ganzhi-calendar-strength-samples')).toHaveText('幅度样本 '+recentDay.strength.sampleCount);

  assert.ok(recentDay.sampleCount<day.sampleCount);
  await expect(cell.locator('.ganzhi-calendar-samples')).toHaveText('方向样本 '+recentDay.sampleCount);
  await expect(page.locator('#ganzhi-calendar-strength-scope')).toContainText('近三年');
  await expect(intradayCard).toContainText(recentData.windowStart+' 起');
  await expect(intradayCard).toContainText('振幅样本 '+recentDay.strength.intradayRangeSampleCount+' 根');
  await expect(page.locator('#statistics-start')).toHaveValue(recentData.windowStart);
  await expect(page.locator('#statistics-sample-count')).toHaveText(String(recentDay.sampleCount));
  const resetWindow=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days'&&
    new URL(r.url()).searchParams.get('window')==='all');
  await page.locator('#ganzhi-calendar-window').selectOption('all');
  await resetWindow;
  const resetThreshold=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days'&&
    new URL(r.url()).searchParams.get('threshold')==='3');
  await page.locator('#ganzhi-calendar-threshold').selectOption('3');
  await resetThreshold;
  check('门槛切换更新大行情率；近三年窗口联动方向、基准与下方统计');

  const updated=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days'&&new URL(r.url()).searchParams.get('basis')==='previous_close');
  await page.locator('#statistics-basis').selectOption('previous_close');
  const updatedData=await (await updated).json();
  const updatedDay=updatedData.days.find(d=>d.date===day.date);
  if(updatedDay.signalDirection==='up'||updatedDay.signalDirection==='down'){
    await expect(cell.locator('.ganzhi-calendar-rate')).toContainText(
      (updatedDay.signalDirection==='up'?'上涨':'下跌')+' '+Number(updatedDay.signalPct).toFixed(1)+'%'
    );
  }else{
    await expect(cell.locator('.ganzhi-calendar-rate')).toContainText(
      updatedDay.sampleCount?Number(updatedDay.upPct).toFixed(1)+'%':'暂无样本'
    );
  }
  if(updatedDay.actualChangePct!==null){
    const change=(Number(updatedDay.actualChangePct)>0?'+':'')+Number(updatedDay.actualChangePct).toFixed(2)+'%';
    await expect(cell.locator('.ganzhi-calendar-actual')).toContainText(change);
  }
  await expect(cell.locator('.ganzhi-calendar-amplitude')).toContainText(
    Number(updatedDay.strength.medianAbsoluteChangePct).toFixed(2)+'%'
  );
  await expect(page.locator('#ganzhi-calendar-strength-scope')).toContainText('收盘 vs 昨收');
  check('日历方向与强度同步跟随收盘相对昨收口径');

  const previousBasis=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days'&&
    new URL(r.url()).searchParams.get('basis')==='previous_close');
  await page.locator('.fc-prev-button').click();
  const previousBasisData=await (await previousBasis).json();
  const pastBasis=monthJudgement(previousBasisData.days,previousBasisData.asOf,
    monthKey(await page.locator('.fc-toolbar-title').textContent()));
  assert.equal(pastBasis.state,'complete');
  await expect(page.locator('#ganzhi-calendar-month-summary')).toContainText(
    '正确率 '+pastBasis.accuracyPct.toFixed(2)+'%'
  );
  const returnCurrent=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/calendar/days');
  await page.locator('.fc-next-button').click();
  await returnCurrent;
  check('月度正确率随收盘对昨收口径重新计算');

  await page.locator('[data-period=month]').click();
  await expect(page.locator('#ganzhi-calendar-panel')).toBeHidden();
  await page.locator('[data-period=day]').click();
  await expect(page.locator('#ganzhi-calendar-panel')).toBeVisible();
  await expect(page.locator('.fc-toolbar-title')).toHaveText(monthBefore);
  await expect(page.locator('#ganzhi-calendar-status')).toContainText('已显示');
  check('月线隐藏日历，返回日线保留当前月份');

  await page.locator('#ganzhi-calendar-panel').screenshot({path:fileURLToPath(new URL('ganzhi-calendar-desktop.png',out))});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('#ganzhi-calendar .fc-daygrid-day').getBoundingClientRect().width<60);
  const mobileColumns=await page.locator('#ganzhi-calendar .fc-col-header-cell').count();
  assert.equal(mobileColumns,7);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const overflowingMetrics=await page.evaluate(()=>[...document.querySelectorAll(
    '.ganzhi-calendar-amplitude strong,.ganzhi-calendar-large strong,.ganzhi-calendar-actual strong'
  )].filter(el=>el.scrollWidth>el.clientWidth+1).length);
  assert.equal(overflowingMetrics,0);
  await page.locator('#ganzhi-calendar-panel').screenshot({path:fileURLToPath(new URL('ganzhi-calendar-mobile.png',out))});
  await page.setViewportSize({width:320,height:844});
  await page.waitForFunction(()=>document.querySelector('#ganzhi-calendar .fc-daygrid-day').getBoundingClientRect().width<45);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const narrowOverflow=await page.evaluate(()=>[...document.querySelectorAll(
    '.ganzhi-calendar-amplitude strong,.ganzhi-calendar-large strong,.ganzhi-calendar-actual strong'
  )].filter(el=>el.scrollWidth>el.clientWidth+1).length);
  assert.equal(narrowOverflow,0);
  assert.deepEqual(errors,[]);
  check('手机月历无横向溢出，浏览器无运行错误');
  await writeFile(new URL('../calendar-browser-verification.json',out),JSON.stringify({passed:true,checks,errors,library:'FullCalendar 6.1.21'},null,2));
}finally{await browser.close();}
