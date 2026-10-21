import { MarketChart } from './charts/market-chart.js';
import { showDetails } from './controls/details.js';
import { GanzhiStatistics } from './statistics/ganzhi-statistics.js';
import { GanzhiCalendar } from './calendar/ganzhi-calendar.js';

const $=id=>document.getElementById(id);
const number = n=>Number(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const descriptions={day:'UTC+8 自然日 · 00:00 至 23:59:59',week:'连续 7 个自然日 · 从配置锚点向前 / 向后划分',month:'十二节划月 · 当节当日零点至下节前一日',year:'立春划年 · 立春当日零点至下一立春前一日'};
let economicKey=null,economicBusy=false,economicReady=false;
let config, chart, statistics, calendarView, period='day', anchor=null, pinned=null, payload=null, requestId=0, dataVersion=null, statusBusy=false;
function message(text='') {$('message').textContent=text;$('message').hidden=!text;}
function overlay(text) {$('chart-overlay').textContent=text??'';$('chart-overlay').hidden=!text;}
async function api(url,options) {
  const res=await fetch(url,options);
  const body=await res.json();
  if(!res.ok) throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail??body));
  return body;
}
function withAnchor(url) {return anchor?url+(url.includes('?')?'&':'?')+'anchor='+encodeURIComponent(anchor):url;}
function select(c,click) {
  if(click) pinned=c.periodId;
  if(pinned && !click) return;
  showDetails(c,period,Boolean(pinned),chart.economicEvents.get(c.metadata.startDate)||[]);
}
function anchorNote() {
  $('anchor').value=anchor??'';
  $('anchor-note').textContent=anchor?'从 '+anchor+' 起算 · 向前历史使用负序号':'尚未设定 · 不默认采用星期一';
}
function updateQuote(c) {
  if(!c) return;
  const change=(Number(c.close)/Number(c.open)-1)*100;
  $('last-price').textContent=number(c.close);
  $('day-change').textContent='UTC+8 当日 '+(change>=0?'+':'')+change.toFixed(2)+'%';
  $('day-change').className=change>=0?'positive':'negative';
  $('day-high').textContent=number(c.high);$('day-low').textContent=number(c.low);$('day-volume').textContent=number(c.volume);
}
function economicControls(){
  for(const id of ['cpi-toggle','nfp-toggle']) $(id).disabled=period!=='day'||!economicReady;
}
async function refreshEconomicCalendar(key=null){
  if(economicBusy||(key!==null&&key===economicKey)) return;
  economicBusy=true;
  try{
    const data=await api('/api/economic-events');
    chart.setEconomicEvents(data.events);
    economicReady=true;
    economicKey=data.version+':'+(data.error||'');
    const confirmed=data.events.filter(e=>e.status==='released');
    for(const id of ['cpi-toggle','nfp-toggle'])
      $(id).closest('label').title='BLS官方公布日 · 历史 '+confirmed[0].date+' 至 '+confirmed.at(-1).date+' · 点击K线查看公布时间与原文';
    $('economic-calendar-note').textContent=data.error?'公布日期更新暂不可用，仍显示已核实的日期缓存。':'';
    $('economic-calendar-note').hidden=!data.error;
    const selected=payload?.candles.find(c=>c.periodId===pinned)??payload?.candles.at(-1);
    if(selected) showDetails(selected,period,Boolean(pinned),chart.economicEvents.get(selected.metadata.startDate)||[]);
  }catch(e){
    $('economic-calendar-note').textContent=economicReady?'公布日期暂时无法更新，仍显示上次标记。':'CPI/非农公布日期暂时无法载入，稍后自动重试。';
    $('economic-calendar-note').hidden=false;
  }finally{economicBusy=false;economicControls();}
}
async function load(nextPeriod=period,preserve=false) {
  if(nextPeriod==='week'&&!anchor){message('请先设置七日周期锚点，再查看自定义周线。');$('anchor').focus();return;}
  const id=++requestId;
  if(!preserve) overlay('正在载入周期数据…');
  try{
    const data=await api(withAnchor('/api/candles?period='+nextPeriod));
    if(id!==requestId) return false;
    period=nextPeriod;payload=data;
    if(!preserve) pinned=null;
    $('period-description').textContent=descriptions[period];
    document.querySelectorAll('[data-period]').forEach(b=>{b.classList.toggle('active',b.dataset.period===period);b.setAttribute('aria-pressed',String(b.dataset.period===period));});
    $('day14-toggle').disabled=period!=='day';
    economicControls();
    $('ganzhi-toggle').disabled=!['day','month'].includes(period);
    $('term-toggle').disabled=period!=='day';
    $('label-hint').textContent=period==='day'?'干支随缩放自动抽稀；点击 K 线固定详情':
      period==='month'?'流月干支标在月 K 下方；点击 K 线查看完整周期起止与 OHLCV':
      '点击 K 线查看完整周期起止与 OHLCV';
    chart.setData(data.candles,period,preserve);
    statistics?.setPeriod(period);
    calendarView?.setPeriod(period);
    if(data.candles.length){
      overlay(null);
      const selected=data.candles.find(c=>c.periodId===pinned)??data.candles.at(-1);
      showDetails(selected,period,Boolean(pinned),chart.economicEvents.get(selected.metadata.startDate)||[]);
      if(period==='day') updateQuote(data.candles.at(-1));
    }else overlay('本地尚无行情。点击「同步行情」从 Binance 下载。');
    $('anomalies').hidden=!data.sourceAnomalies.length;
    $('anomaly-summary').textContent=data.sourceAnomalies.length+' 条交易所原始时间异常 · 已保留并标记';
    $('anomaly-text').textContent=data.sourceAnomalies.join('、')+' 的 Binance 原始 closeTime 早于自然日结束。原始 OHLCV 与 closeTime 均保存在本地；受影响周期标为异常，未填补或伪造价格。';
    message('');
    return true;
  }catch(e){
    if(id===requestId){
      message((preserve?'行情更新失败，仍显示上次数据：':'')+e.message);
      if(!preserve) overlay('无法载入：'+e.message);
    }
    return false;
  }
}
async function refreshStatus(){
  if(statusBusy) return;statusBusy=true;
  try{
    const s=await api('/api/status');
    void refreshEconomicCalendar(s.economicCalendarVersion?s.economicCalendarVersion+':'+(s.economicCalendarError||''):null);
    const el=$('connection');
    el.textContent=s.error?'同步失败 · 使用缓存':s.syncing?'正在同步':s.stale?'缓存待更新':'本地缓存已同步';
    el.className='status '+(s.error?'error':!s.stale&&!s.syncing?'live':'');
    $('sync').disabled=s.syncing;
    $('sync').textContent=s.syncing?'正在同步…':'↻ 同步行情';
    $('data-range').textContent=s.count?s.firstDate+' → '+s.lastDate:'尚无本地行情';
    $('data-count').textContent=s.count.toLocaleString()+' 根 UTC+8 日线';
    $('last-sync').textContent=s.lastSync?'同步于 '+new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(s.lastSync)):'尚未同步';
    if(s.error) message(s.error);
    if(s.lastSync && dataVersion!==s.lastSync){
      const activePeriod=period;
      if(!await load(activePeriod,Boolean(payload))) return;
      const updates=await Promise.all([
        statistics?.refresh()??true,
        calendarView?.refresh({background:true})??true,
      ]);
      if(period!==activePeriod) return;
      if(period!=='day'){const daily=await api('/api/candles?period=day');updateQuote(daily.candles.at(-1));}
      if(updates.every(Boolean)) dataVersion=s.lastSync;
    }
  }catch(e){$('connection').textContent='本地服务连接中断';$('connection').className='status error';message(e.message);}
  finally{statusBusy=false;}
}
async function init(){
  try{
    config=await api('/api/config');
    try{anchor=localStorage.getItem('customWeekAnchor')||config.customWeekAnchor;}catch{anchor=config.customWeekAnchor;}
    if(anchor&&!/^\d{4}-\d{2}-\d{2}$/.test(anchor)) anchor=null;
    anchorNote();
    chart=new MarketChart($('chart'),select);
    statistics=new GanzhiStatistics({
      api,
      onHighlight:dates=>chart.setHighlightDates(dates),
      onLocate:(date,scrollToChart=true)=>{
        if(!['day','month'].includes(period)) return;
        const candle=payload?.candles.find(c=>c.metadata.startDate===date);
        if(!candle) return;
        chart.focusDate(date);select(candle,true);
        if(scrollToChart) $('chart').scrollIntoView({behavior:'smooth',block:'center'});
      },
    });
    calendarView=new GanzhiCalendar({
      api,
      basisInput:$('statistics-basis'),
      onSelect:row=>statistics.selectCalendarDay(row,{scrollToStatistics:false}),
    });
    document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>load(b.dataset.period)));
    $('fit').addEventListener('click',()=>chart.fit());
    $('cpi-toggle').addEventListener('change',()=>chart.setOptions({showCPI:$('cpi-toggle').checked}));
    $('nfp-toggle').addEventListener('change',()=>chart.setOptions({showNFP:$('nfp-toggle').checked}));
    $('day14-toggle').addEventListener('change',()=>chart.setOptions({showDay14:$('day14-toggle').checked}));
    $('ganzhi-toggle').addEventListener('change',()=>chart.setOptions({showGanzhi:$('ganzhi-toggle').checked}));
    $('term-toggle').addEventListener('change',()=>chart.setOptions({showTerms:$('term-toggle').checked}));
    $('unpin').addEventListener('click',()=>{pinned=null;$('unpin').hidden=true;if(payload?.candles.length)select(payload.candles.at(-1),false);});
    $('anchor-form').addEventListener('submit',async e=>{
      e.preventDefault();const value=$('anchor').value;
      if(!value){message('请输入周线起算日期。');return;}
      try{await api('/api/candles?period=week&anchor='+encodeURIComponent(value));}
      catch(err){message(err.message);return;}
      anchor=value;try{localStorage.setItem('customWeekAnchor',anchor);}catch{}
      anchorNote();message('');await load('week');
    });
    $('clear-anchor').addEventListener('click',async()=>{
      anchor=config.customWeekAnchor;try{localStorage.removeItem('customWeekAnchor');}catch{}
      anchorNote();message('');if(period==='week') await load(anchor?'week':'day');
    });
    $('sync').addEventListener('click',async()=>{
      $('sync').disabled=true;try{await api('/api/sync',{method:'POST'});await refreshStatus();}catch(e){message(e.message);$('sync').disabled=false;}
    });
    $('debug-panel').hidden=!config.debugMode;
    $('debug-date').value=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    $('debug-form').addEventListener('submit',async e=>{
      e.preventDefault();
      try{$('debug-output').textContent=JSON.stringify(await api(withAnchor('/api/debug/'+$('debug-date').value)),null,2);}
      catch(err){$('debug-output').textContent=err.message;}
    });
    economicControls();
    void refreshEconomicCalendar();
    await load();
    dataVersion=payload?.asOf??null;
    await refreshStatus();
    setInterval(refreshStatus,5000);
  }catch(e){overlay('启动失败：'+e.message);message('请确认本地服务和图表文件安装完整。');}
}
init();
