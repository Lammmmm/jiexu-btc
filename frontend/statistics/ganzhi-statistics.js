const reasons={
  unclosed:'未收盘 / 尚无收盘快照',source_anomaly:'原始数据异常',
  listing_day:'上市首个周期可能不完整',invalid_previous_close:'缺少可用的上期收盘价',
  incomplete_period:'周期日线数据不完整',
};
const directions={up:'上涨',down:'下跌',flat:'平盘'};
const pct=n=>n===null||n===undefined?'—':Number(n).toFixed(2)+'%';
const signed=n=>n===null||n===undefined?'—':(Number(n)>0?'+':'')+Number(n).toFixed(2)+'%';

export class GanzhiStatistics {
  constructor({api,onHighlight,onLocate}){
    this.api=api;this.onHighlight=onHighlight;this.onLocate=onLocate;
    this.root=document.getElementById('ganzhi-statistics');
    this.period='day';this.query=null;this.data=null;this.selectedDate=null;this.sequence=0;
    this.rankQuery=null;this.rankData=null;this.rankSequence=0;this.rankLoading=false;
    this.$=id=>document.getElementById(id);
    this.$('statistics-form').addEventListener('submit',e=>{
      e.preventDefault();
      this.selectedDate=null;this.hideYearly();
      this.query={
        period:this.period,
        ganzhi:this.$('statistics-ganzhi').value.trim(),
        start:this.$('statistics-start').value,
        end:this.$('statistics-end').value,
        basis:this.$('statistics-basis').value,
      };
      this.fetch();
    });
    this.$('statistics-clear').addEventListener('click',()=>this.clear());
    this.$('statistics-rank').addEventListener('click',()=>this.fetchRankings(this.filters()));
    this.root.addEventListener('click',e=>{
      const button=e.target.closest('button[data-ganzhi]');
      if(button&&this.rankData) this.drillDown(button.dataset.ganzhi);
    });
    this.$('statistics-rows').addEventListener('click',e=>{
      const button=e.target.closest('button[data-date]');
      if(button){
        this.selectedDate=button.dataset.date;
        this.showYearly(this.selectedDate);
        this.onLocate(this.selectedDate,this.period==='month');
        if(this.period==='day') this.$('statistics-yearly').scrollIntoView({behavior:'smooth',block:'nearest'});
      }
    });
    this.loadOptions();
  }
  async loadOptions(){
    try{
      const {options}=await this.api('/api/statistics/ganzhi/options');
      this.$('statistics-options').replaceChildren(...options.map(value=>{
        const el=document.createElement('option');el.value=value;return el;
      }));
    }catch{ /* Free-text input remains usable; submit reports request errors. */ }
  }
  get supported(){return ['day','month'].includes(this.period);}
  get unit(){return this.period==='month'?'月':'日';}
  basisLabel(basis){return basis==='open'?'收盘 vs 开盘':this.period==='month'?'收盘 vs 上月收盘':'收盘 vs 昨收';}
  initialStatus(){return '输入干支，查看它在全部本地'+this.unit+'线中的历史涨跌分布。';}
  setPeriod(period){
    const changed=this.period!==period;
    this.period=period;
    if(changed) this.clear();
    this.root.hidden=!this.supported;
    if(!this.supported) return;
    const monthly=period==='month';
    this.$('statistics-heading').textContent='干支'+this.unit+' · 筛选统计';
    this.$('statistics-eyebrow').textContent=monthly?'GANZHI MONTH STATISTICS':'GANZHI DAY STATISTICS';
    this.$('statistics-period-tag').textContent=this.unit+'线 · UTC+8';
    this.$('statistics-description').textContent=monthly
      ?'按月干支统计节气月 K 线；日期范围按月起始日筛选，仅计入完整且已收盘的月份。'
      :'查找同一干支日，观察历史日线的涨跌分布。';
    this.$('statistics-basis').querySelector('[value="previous_close"]').textContent=this.basisLabel('previous_close');
    this.$('statistics-sample-label').textContent=monthly?'完整已收盘月线':'已收盘日线';
    this.$('statistics-date-heading').textContent=monthly?'月周期起止 ↗':'日期 ↗';
    this.$('statistics-empty').textContent='所选日期范围没有匹配'+this.unit+'线。';
    this.onHighlight(this.data?this.data.matches.map(r=>r.date):[]);
  }
  async refresh(){
    const updates=[];
    if(this.query&&this.supported&&!this.loading) updates.push(this.fetch({background:true}));
    if(this.rankQuery&&this.supported&&!this.rankLoading)
      updates.push(this.fetchRankings(this.rankQuery,{background:true}));
    return (await Promise.all(updates)).every(Boolean);
  }
  clear(){
    this.selectedDate=null;this.hideYearly();
    this.$('statistics-results').setAttribute('aria-busy','false');
    this.$('statistics-rankings').setAttribute('aria-busy','false');
    this.sequence++;this.abort?.abort();this.query=null;this.data=null;this.loading=false;
    this.rankSequence++;this.rankAbort?.abort();this.rankQuery=null;this.rankData=null;this.rankLoading=false;
    this.$('statistics-rankings').hidden=true;this.$('statistics-ranking-status').hidden=true;
    this.$('statistics-rank').disabled=false;this.$('statistics-rank').textContent='遍历全部干支';
    this.$('statistics-form').reset();this.$('statistics-results').hidden=true;
    this.$('statistics-submit').disabled=false;
    this.$('statistics-submit').textContent='筛选统计';
    this.$('statistics-status').textContent=this.initialStatus();
    this.$('statistics-status').className='statistics-note';
    this.onHighlight([]);
  }
  async selectCalendarDay(row,{scrollToStatistics=true}={}){
    const basis=this.$('statistics-basis').value;
    this.clear();
    this.$('statistics-basis').value=basis;
    this.$('statistics-ganzhi').value=row.ganzhi;
    this.$('statistics-start').value=row.statisticsStart||'';
    this.selectedDate=row.date;
    this.query={period:'day',ganzhi:row.ganzhi,start:row.statisticsStart||'',end:'',basis};
    await this.fetch();
    if(scrollToStatistics) this.root.scrollIntoView({behavior:'smooth',block:'start'});
  }
  async fetch({background=false}={}){
    if(!this.query) return true;
    const keepContent=background&&Boolean(this.data);
    const sequence=++this.sequence;
    this.abort?.abort();this.abort=new AbortController();this.loading=true;
    if(!keepContent){
      this.data=null;
      this.$('statistics-results').hidden=true;this.hideYearly();this.onHighlight([]);
      this.$('statistics-submit').textContent='正在统计…';
      this.$('statistics-status').textContent='正在核对已收盘'+this.unit+'线…';
      this.$('statistics-status').className='statistics-note';
    }
    this.$('statistics-submit').disabled=true;
    this.$('statistics-results').setAttribute('aria-busy','true');
    const params=new URLSearchParams(Object.entries(this.query).filter(([,v])=>v));
    try{
      const data=await this.api('/api/statistics/ganzhi?'+params,{signal:this.abort.signal});
      if(sequence!==this.sequence) return false;
      this.data=data;this.render(data);
      if(this.supported) this.onHighlight(data.matches.map(r=>r.date));
      return true;
    }catch(error){
      if(sequence!==this.sequence||error.name==='AbortError') return false;
      this.$('statistics-status').textContent=(keepContent?'更新失败，仍显示上次数据：':'')+error.message;
      this.$('statistics-status').className='statistics-note statistics-error';
      return false;
    }finally{
      if(sequence===this.sequence){
        this.loading=false;this.$('statistics-submit').disabled=false;
        this.$('statistics-submit').textContent='筛选统计';
        this.$('statistics-results').setAttribute('aria-busy','false');
      }
    }
  }
  filters(){
    return {
      period:this.period,
      start:this.$('statistics-start').value,
      end:this.$('statistics-end').value,
      basis:this.$('statistics-basis').value,
    };
  }
  async fetchRankings(query,{background=false}={}){
    const keepContent=background&&Boolean(this.rankData);
    this.rankQuery={...query};
    const sequence=++this.rankSequence;
    this.rankAbort?.abort();this.rankAbort=new AbortController();this.rankLoading=true;
    const status=this.$('statistics-ranking-status');status.hidden=false;
    if(!keepContent){
      this.rankData=null;
      this.$('statistics-rank').textContent='正在遍历…';
      this.$('statistics-rankings').hidden=true;
      status.className='statistics-note';status.textContent='正在使用同一份行情快照统计全部 60 个干支…';
    }
    this.$('statistics-rank').disabled=true;
    this.$('statistics-rankings').setAttribute('aria-busy','true');
    try{
      const params=new URLSearchParams(Object.entries(query).filter(([,v])=>v));
      const data=await this.api('/api/statistics/ganzhi/rankings?'+params,{signal:this.rankAbort.signal});
      if(sequence!==this.rankSequence) return false;
      this.rankData=data;this.renderRankings(data);
      return true;
    }catch(error){
      if(sequence!==this.rankSequence||error.name==='AbortError') return false;
      status.textContent=(keepContent?'更新失败，仍显示上次数据：':'')+error.message;
      status.className='statistics-note statistics-error';
      return false;
    }finally{
      if(sequence===this.rankSequence){
        this.rankLoading=false;this.$('statistics-rank').disabled=false;
        this.$('statistics-rank').textContent='遍历全部干支';
        this.$('statistics-rankings').setAttribute('aria-busy','false');
      }
    }
  }
  drillDown(ganzhi){
    const data=this.rankData;
    this.selectedDate=null;this.hideYearly();
    this.query={ganzhi,period:data.period,start:data.start||'',end:data.end||'',basis:data.basis};
    this.$('statistics-ganzhi').value=ganzhi;
    for(const key of ['start','end','basis']) this.$('statistics-'+key).value=this.query[key];
    this.fetch();
  }
  renderRankings(data){
    this.$('statistics-ranking-status').className='statistics-note';
    this.$('statistics-rankings').hidden=false;
    this.$('statistics-ranking-scope').textContent=
      (data.start||data.availableStart||'—')+' → '+(data.end||data.availableEnd||'—')+
      ' · '+this.basisLabel(data.basis);
    const asOf=data.asOf?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(data.asOf)):'尚无成功同步';
    this.$('statistics-ranking-status').textContent=
      '已遍历 '+data.totalGanzhi+' 个干支；计入 '+data.totalSamples+' 根'+this.unit+'线，排除 '+data.totalExcluded+' 根。快照：'+asOf+'。';
    for(const side of ['up','down']){
      const other=side==='up'?'down':'up';
      const rows=data[side+'Ranking'].map(row=>{
        const tr=document.createElement('tr');
        const rank=document.createElement('td');rank.textContent=row.rank;tr.append(rank);
        const name=document.createElement('td'),button=document.createElement('button');
        button.type='button';button.className='statistics-date';button.dataset.ganzhi=row.ganzhi;
        button.textContent=row.ganzhi;button.title='查看 '+row.ganzhi+this.unit+'的 K 线明细';name.append(button);tr.append(name);
        for(const direction of [side,other,'flat']){
          const td=document.createElement('td');td.textContent=pct(row.probabilitiesPct[direction]);
          td.title=row.counts[direction]+' / '+row.sampleCount+' 根有效'+this.unit+'线';
          td.className=direction==='up'?'positive':direction==='down'?'negative':'';
          tr.append(td);
        }
        const count=document.createElement('td');count.textContent=row.sampleCount;
        count.title='匹配 '+row.matchedCount+' 根，排除 '+row.excludedCount+' 根';
        tr.append(count);return tr;
      });
      this.$('statistics-rank-'+side).replaceChildren(...rows);
    }
  }
  render(data){
    this.$('statistics-status').className='statistics-note';
    this.$('statistics-results').hidden=false;
    this.$('statistics-result-title').textContent=data.ganzhi+this.unit+' · 历史统计';
    this.$('statistics-sample-count').textContent=data.sampleCount;
    for(const key of ['up','down','flat']){
      this.$('statistics-'+key+'-pct').textContent=pct(data.probabilitiesPct[key]);
      this.$('statistics-'+key+'-count').textContent=data.counts[key]+' 次';
      this.$('statistics-'+key+'-bar').style.width=(Number(data.probabilitiesPct[key])||0)+'%';
    }
    const scope=(data.start||data.availableStart||'—')+' → '+(data.end||data.availableEnd||'—');
    this.$('statistics-scope').textContent=scope+' · '+this.basisLabel(data.basis);
    this.$('statistics-summary').textContent=
      '幅度统计：'+data.strength.start+' 起 · 幅度样本 '+data.strength.sampleCount+' 根　平均涨跌 '+signed(data.averageChangePct)+'　中位数 '+signed(data.medianChangePct)+
      '　最高涨跌 '+signed(data.bestChangePct)+'　最低涨跌 '+signed(data.worstChangePct);
    const excluded=Object.entries(data.excluded).filter(([,n])=>n).map(([k,n])=>reasons[k]+' '+n+' 根');
    const time=data.asOf?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(data.asOf)):'尚无成功同步';
    this.$('statistics-status').textContent=
      '匹配 '+data.matchedCount+' 根，计入 '+data.sampleCount+' 根'+
      (excluded.length?'；排除：'+excluded.join('、'):'')+'。数据快照：'+time+'。'+
      (!data.sampleCount?'没有可用的已收盘样本，概率显示为“—”。':'');
    this.$('statistics-rows').replaceChildren(...data.matches.map(row=>{
      const tr=document.createElement('tr');
      const dateCell=document.createElement('td');
      const button=document.createElement('button');button.type='button';button.dataset.date=row.date;
      button.className='statistics-date';button.textContent=this.period==='month'?row.date+' → '+row.endDate:row.date;button.title='定位到这'+(this.period==='month'?'个月':'一天')+'的 K 线';
      dateCell.append(button);tr.append(dateCell);
      for(const key of ['open','high','low','close']){
        const td=document.createElement('td');td.textContent=Number(row[key]).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
        td.title=row[key];tr.append(td);
      }
      const change=document.createElement('td');change.textContent=signed(row.changePct);
      change.className=row.direction==='up'?'positive':row.direction==='down'?'negative':'';
      tr.append(change);
      const state=document.createElement('td');state.textContent=row.included?directions[row.direction]:'不计入';
      state.title=row.included?'已收盘有效样本':reasons[row.excludedReason];state.className=change.className;
      tr.append(state);return tr;
    }));
    this.$('statistics-empty').hidden=data.matches.length>0;
    if(this.selectedDate&&data.period==='day'&&data.matches.some(row=>row.date===this.selectedDate))
      this.showYearly(this.selectedDate);
    else this.hideYearly();
  }
  hideYearly(){this.$('statistics-yearly').hidden=true;}
  showYearly(date){
    const data=this.data;
    if(this.period!=='day'||!data?.yearly?.length) return this.hideYearly();
    const year=Number(date.slice(0,4));
    const active=data.yearly.find(row=>row.year===year);
    if(!active) return this.hideYearly();
    this.$('statistics-yearly-title').textContent=data.ganzhi+'日 · 当前 '+year+' 年（'+date+'）';
    const rows=data.yearly.map(item=>{
      const tr=document.createElement('tr');
      tr.className=item.year===year?'statistics-year-active':'';
      tr.title=item.start+' 至 '+item.endExclusive+'（不含）；匹配 '+item.matchedCount+' 次，排除 '+item.excludedCount+' 次';
      for(const [value,cls] of [
        [String(item.year), ''],
        [pct(item.probabilitiesPct.up), 'positive'],
        [pct(item.probabilitiesPct.down), 'negative'],
        [String(item.counts.flat), ''],
        [String(item.sampleCount), ''],
      ]){
        const td=document.createElement('td');
        td.textContent=value;td.className=cls;tr.append(td);
      }
      return tr;
    });
    this.$('statistics-yearly-rows').replaceChildren(...rows);
    this.$('statistics-yearly').hidden=false;
  }
}
