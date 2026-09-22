const set = (id,text) => {document.getElementById(id).textContent=text;};
export function showDetails(candle,period,pinned=false) {
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
  document.getElementById('detail-close').className=Number(candle.close)>=Number(candle.open)?'positive':'negative';
  document.getElementById('calendar-detail').hidden=false;
  set('detail-ganzhi-label',{day:'日干支',week:'起始日干支',month:'月干支',year:'年干支'}[period]);
  set('detail-ganzhi',label);
  set('detail-month',m.ganzhiDate??m.startDate);set('detail-year',m.solar_year_id??'—');
  set('detail-warning',(m.warnings??[]).join('；'));
  document.getElementById('unpin').hidden=!pinned;
}
