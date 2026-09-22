import { MarketChart } from './charts/market-chart.js';
import { showDetails } from './controls/details.js';

const $=id=>document.getElementById(id);
const number = n=>Number(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const descriptions={day:'UTC+8 自然日 · 00:00 至 23:59:59',week:'连续 7 个自然日 · 从配置锚点向前 / 向后划分',month:'十二节划月 · 当节当日零点至下节前一日',year:'立春划年 · 立春当日零点至下一立春前一日'};
let config, chart, period='day', anchor=null, pinned=null, payload=null, requestId=0, dataVersion=null, statusBusy=false;
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
  showDetails(c,period,Boolean(pinned));
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
async function load(nextPeriod=period,preserve=false) {
  if(nextPeriod==='week'&&!anchor){message('请先设置七日周期锚点，再查看自定义周线。');$('anchor').focus();return;}
  const id=++requestId;
  if(!preserve) overlay('正在载入周期数据…');
  try{
    const data=await api(withAnchor('/api/candles?period='+nextPeriod));
    if(id!==requestId) return;
    period=nextPeriod;payload=data;
    if(!preserve) pinned=null;
    $('period-description').textContent=descriptions[period];
    document.querySelectorAll('[data-period]').forEach(b=>{b.classList.toggle('active',b.dataset.period===period);b.setAttribute('aria-pressed',String(b.dataset.period===period));});
    for(const id of ['ganzhi-toggle','term-toggle']) $(id).disabled=period!=='day';
    $('label-hint').textContent=period==='day'?'干支随缩放自动抽稀；点击 K 线固定详情':'点击 K 线查看完整周期起止与 OHLCV';
    chart.setData(data.candles,period,preserve);
    if(data.candles.length){
      overlay(null);
      const selected=data.candles.find(c=>c.periodId===pinned)??data.candles.at(-1);
      showDetails(selected,period,Boolean(pinned));
      if(period==='day') updateQuote(data.candles.at(-1));
    }else overlay('本地尚无行情。点击「同步行情」从 Binance 下载。');
    $('anomalies').hidden=!data.sourceAnomalies.length;
    $('anomaly-summary').textContent=data.sourceAnomalies.length+' 条交易所原始时间异常 · 已保留并标记';
    $('anomaly-text').textContent=data.sourceAnomalies.join('、')+' 的 Binance 原始 closeTime 早于自然日结束。原始 OHLCV 与 closeTime 均保存在本地；受影响周期标为异常，未填补或伪造价格。';
    message('');
  }catch(e){if(id===requestId){message(e.message);overlay('无法载入：'+e.message);}}
}
async function refreshStatus(){
  if(statusBusy) return;statusBusy=true;
  try{
    const s=await api('/api/status');
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
      dataVersion=s.lastSync;
      await load(period,Boolean(payload));
      if(period!=='day'){const daily=await api('/api/candles?period=day');updateQuote(daily.candles.at(-1));}
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
    document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>load(b.dataset.period)));
    $('fit').addEventListener('click',()=>chart.fit());
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
    await load();
    await refreshStatus();
    setInterval(refreshStatus,5000);
  }catch(e){overlay('启动失败：'+e.message);message('请确认本地服务和图表文件安装完整。');}
}
init();
