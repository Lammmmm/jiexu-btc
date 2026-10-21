const set = (id,text) => {document.getElementById(id).textContent=text;};
export function showDetails(candle,period,pinned=false,economicEvents=[]) {
  const m=candle.metadata;
  const label = m.displayGanzhi ?? '—';
  const suffix = {day:'日',week:' · 七日',month:'月',year:'年'}[period];
  set('detail-title',label + suffix);
  set('detail-id',candle.periodId);
  set('detail-start',m.startDate);
  set('detail-end',m.endDate);
  set('detail-count',m.dayCount+' / '+m.expectedDays+' 天');
  set('detail-state',m.isComplete?'已收盘 · 数据完整':!m.isClosed?'形成中':'数据不完整 / 异常');
  document.getElementById('detail-state').className='badge'+(m.isComplete?'':' partial');
  for(const k of ['open','high','low','close','volume']) set('detail-'+k,candle[k]);
  const amplitudeRow=document.getElementById('detail-amplitude-row');
  amplitudeRow.hidden=period!=='day';
  if(period==='day'){
    const open=Number(candle.open),high=Number(candle.high),low=Number(candle.low);
    const valid=[open,high,low].every(Number.isFinite)&&open>0&&low>=0&&high>=low;
    set('detail-amplitude',valid?((high-low)/open*100).toFixed(2)+'%':'—');
    set('detail-amplitude-label',m.isClosed?'日内振幅':'日内振幅 · 当前');
    amplitudeRow.title='（最高价 − 最低价）÷ 开盘价 × 100%'+
      (m.isClosed?'':'；本日尚未收盘，随行情更新');
  }else{
    set('detail-amplitude','—');
    amplitudeRow.title='';
  }
  const economicPanel=document.getElementById('economic-detail');
  economicPanel.hidden=period!=='day'||!economicEvents.length;
  const economicList=document.getElementById('economic-detail-list');
  economicList.replaceChildren();
  if(period==='day') for(const event of economicEvents){
    const row=document.createElement('li'),link=document.createElement('a'),when=document.createElement('span');
    link.textContent=event.label+(event.status==='scheduled'?' · 计划':'');
    link.href=event.sourceUrl;link.target='_blank';link.rel='noopener noreferrer';
    when.className='economic-time';
    when.textContent=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(event.releaseAt));
    row.title='美国东部 '+event.releaseAtEt+'；北京时间 '+event.releaseAtShanghai+'；BLS官方来源';
    row.append(link,when);economicList.append(row);
  }
  document.getElementById('detail-close').className=Number(candle.close)>=Number(candle.open)?'positive':'negative';
  document.getElementById('calendar-detail').hidden=false;
  set('detail-ganzhi-label',{day:'日干支',week:'起始日干支',month:'月干支',year:'年干支'}[period]);
  set('detail-ganzhi',label);
  set('detail-month',m.ganzhiDate??m.startDate);set('detail-year',m.solar_year_id??'—');
  set('detail-warning',(m.warnings??[]).join('；'));
  document.getElementById('unpin').hidden=!pinned;
}
