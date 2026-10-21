// FullCalendar owns the month grid and navigation. We only supply calendar metadata.
const keyOf=date=>[date.getFullYear(),String(date.getMonth()+1).padStart(2,'0'),String(date.getDate()).padStart(2,'0')].join('-');
const pct=value=>value==null?'—':Number(value).toFixed(1)+'%';
const magnitudePct=value=>value==null?'—':Number(value).toFixed(2)+'%';
const actualPct=value=>value==null?'—':(Number(value)>0?'+':'')+Number(value).toFixed(2)+'%';

export function monthJudgement(days,asOf,month,now=Date.now()){
  const [year,number]=month.split('-').map(Number);
  const nextMonth=number===12?String(year+1)+'-01':String(year)+'-'+String(number+1).padStart(2,'0');
  const endMs=Date.parse(nextMonth+'-01T00:00:00+08:00');
  if(now<endMs) return {state:'unfinished'};
  if(asOf===null||Number(asOf)<endMs) return {state:'stale'};
  const monthDays=days.filter(row=>row.date.startsWith(month+'-'));
  const expectedDays=new Date(Date.UTC(year,number,0)).getUTCDate();
  if(monthDays.length!==expectedDays) return {state:'missing'};
  const judged=monthDays.filter(row=>
    (row.signalDirection==='up'||row.signalDirection==='down')&&
    row.actualChangePct!==null&&row.actualDirection!==null
  );
  const correct=judged.filter(row=>row.signalDirection===row.actualDirection).length;
  return {
    state:judged.length?'complete':'empty',
    correct,judged:judged.length,excluded:monthDays.length-judged.length,
    accuracyPct:judged.length?correct/judged.length*100:null,
  };
}

export class GanzhiCalendar {
  constructor({api,onSelect,basisInput}){
    this.api=api;
    this.onSelect=onSelect;
    this.basisInput=basisInput;
    this.panel=document.getElementById('ganzhi-calendar-panel');
    this.el=document.getElementById('ganzhi-calendar');
    this.status=document.getElementById('ganzhi-calendar-status');
    this.monthSummary=document.getElementById('ganzhi-calendar-month-summary');
    this.thresholdInput=document.getElementById('ganzhi-calendar-threshold');
    this.windowInput=document.getElementById('ganzhi-calendar-window');
    this.benchmark=document.getElementById('ganzhi-calendar-benchmark');
    this.strengthDetail=document.getElementById('ganzhi-calendar-strength-detail');
    this.rows=new Map();
    this.sequence=0;
    this.visible=false;
    this.rendered=false;
    this.selectedDate=null;
    basisInput.addEventListener('change',()=>this.refresh());
    this.thresholdInput.addEventListener('change',()=>this.refresh());
    this.windowInput.addEventListener('change',()=>this.refresh());
  }
  setPeriod(period){
    const wasVisible=this.visible;
    this.visible=period==='day';
    this.panel.hidden=!this.visible;
    if(!this.visible){
      this.sequence++;this.abort?.abort();this.loadingScope=null;
      this.panel.setAttribute('aria-busy','false');
      return;
    }
    if(wasVisible&&this.rendered) return;
    if(!this.rendered){
      if(!window.FullCalendar) {
        this.status.textContent='日历组件未能载入，请检查本地文件。';
        return;
      }
      this.calendar=new FullCalendar.Calendar(this.el,{
        initialView:'dayGridMonth',
        initialDate:new Intl.DateTimeFormat('en-CA',{
          timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'
        }).format(new Date()),
        locale:'zh-cn',
        firstDay:0,
        fixedWeekCount:false,
        height:'auto',
        headerToolbar:{left:'prev,next today',center:'title',right:''},
        buttonText:{today:'今天'},
        validRange:{start:'1900-01-01',end:'2101-01-01'},
        datesSet:info=>this.loadRange(info),
        dayCellContent:info=>String(info.date.getDate()),
        dayCellDidMount:info=>{
          const frame=info.el.querySelector('.fc-daygrid-day-frame');
          if(!frame) return;
          const detail=document.createElement('div');
          detail.className='ganzhi-calendar-cell';
          frame.insertBefore(detail,frame.querySelector('.fc-daygrid-day-events'));
          this.paintCell(info.el,info.el.dataset.date||keyOf(info.date));
        },
        dateClick:info=>{
          const row=this.rows.get(info.dateStr);
          if(!row?.ganzhi) return;
          this.selectedDate=info.dateStr;
          this.paintCells();
          this.paintStrengthDetail();
          this.notifySelection(row);
          this.strengthDetail.scrollIntoView({behavior:'smooth',block:'nearest'});
        },
      });
      this.rendered=true;
      this.calendar.render();
    }else{
      this.calendar.updateSize();
      this.refresh();
    }
  }
  refresh({background=false}={}){
    if(!this.visible||!this.rendered) return Promise.resolve(true);
    const view=this.calendar.view;
    return this.loadRange({startStr:keyOf(view.activeStart),endStr:keyOf(view.activeEnd)},{background});
  }
  loadRange(info,{background=false}={}){
    const start=info.startStr.slice(0,10),end=info.endStr.slice(0,10);
    const params=new URLSearchParams({
      start,end,basis:this.basisInput.value,threshold:this.thresholdInput.value,window:this.windowInput.value,
    });
    const scope=params.toString();
    if(background&&this.loadingScope===scope) return this.pending;
    this.loadingScope=scope;
    this.pending=this.fetchRange(params,scope,background);
    return this.pending;
  }
  async fetchRange(params,scope,background){
    const basis=params.get('basis');
    const month=keyOf(this.calendar.view.currentStart).slice(0,7);
    const keepContent=background&&this.loadedScope===scope&&Boolean(this.payload);
    const sequence=++this.sequence;
    this.abort?.abort();
    this.abort=new AbortController();
    this.panel.setAttribute('aria-busy','true');
    if(!keepContent){
      this.status.textContent='正在读取历法和历史胜率…';
      this.monthSummary.textContent='正在计算月度判断…';this.monthSummaryKey=null;
      this.rows.clear();this.paintCells();this.strengthDetail.hidden=true;
      this.benchmark.textContent='';
    }
    try{
      const payload=await this.api('/api/calendar/days?'+params,{signal:this.abort.signal});
      if(sequence!==this.sequence||!this.visible) return false;
      this.payload=payload;this.loadedScope=scope;
      this.rows=new Map(payload.days.map(row=>[row.date,row]));
      this.paintCells();
      this.paintStrengthDetail();
      const selected=this.rows.get(this.selectedDate);
      if(selected&&this.selectionScope!==basis+':'+(payload.windowStart||''))
        this.notifySelection(selected);
      const base=payload.benchmark;
      this.benchmark.textContent='普通 BTC 日线 · '+base.strength.start+' 起 · 幅度样本 '+
        base.strength.sampleCount.toLocaleString()+' 根 · 典型幅度 '+magnitudePct(base.strength.medianAbsoluteChangePct)+
        ' · 大行情率 '+pct(base.strength.largeMove.probabilitiesPct.total)+'（≥'+payload.thresholdPct+'%）';
      this.paintMonthSummary(monthJudgement(payload.days,payload.asOf,month),month);
      const counted=payload.days.filter(row=>row.ganzhi).length;
      this.status.textContent='已显示 '+counted+' 天 · '+(basis==='open'?'收盘 vs 开盘':'收盘 vs 昨收')+
        ' · '+(payload.window==='all'?'全部本地历史有效样本':payload.windowStart?'近三年有效样本（自 '+payload.windowStart+'）':'近三年有效样本（暂无同步快照）');
      this.status.className='statistics-note';
      return true;
    }catch(error){
      if(sequence!==this.sequence||error.name==='AbortError') return false;
      this.status.textContent=(keepContent?'更新失败，仍显示上次数据：':'')+error.message;
      if(!keepContent){
        this.monthSummary.textContent='月度统计暂不可用';this.monthSummaryKey=null;
        this.rows.clear();this.paintCells();this.strengthDetail.hidden=true;
        this.benchmark.textContent='';
      }
      this.status.className='statistics-note statistics-error';
      return false;
    }finally{
      if(sequence===this.sequence){
        this.loadingScope=null;this.pending=null;
        this.panel.setAttribute('aria-busy','false');
      }
    }
  }
  notifySelection(row){
    this.selectionScope=this.payload.basis+':'+(this.payload.windowStart||'');
    this.onSelect({...row,statisticsStart:this.payload.windowStart||''});
  }
  paintStrengthDetail(){
    const row=this.rows.get(this.selectedDate);
    this.strengthDetail.hidden=!row?.strength;
    if(!row?.strength) return;
    const strength=row.strength,large=strength.largeMove,base=this.payload.benchmark;
    const renderKey=JSON.stringify([row,base,this.payload.window,this.payload.basis]);
    if(this.strengthRenderKey===renderKey) return;
    this.strengthRenderKey=renderKey;
    document.getElementById('ganzhi-calendar-strength-title').textContent=
      row.date+' · '+row.ganzhi+'日 · 强度详情';
    document.getElementById('ganzhi-calendar-strength-scope').textContent=
      (this.payload.window==='all'?'全部历史':'近三年')+' · '+
      (this.payload.basis==='open'?'收盘 vs 开盘':'收盘 vs 昨收')+' · '+strength.start+' 起 · 幅度样本 '+strength.sampleCount+' 根'+
      (strength.sampleStart?' · '+strength.sampleStart+' → '+strength.sampleEnd:'');
    const metrics=[
      ['典型幅度',magnitudePct(strength.medianAbsoluteChangePct),
        strength.start+' 起 · 绝对涨跌幅中位数 · 样本 '+strength.sampleCount+' 根 · 普通日线 '+magnitudePct(base.strength.medianAbsoluteChangePct),''],
      ['大行情率',pct(large.probabilitiesPct.total),
        large.start+' 起 · |涨跌幅| ≥'+large.thresholdPct+'% · '+large.counts.total+' / '+large.sampleCount+
        ' 根 · 普通日线 '+pct(base.strength.largeMove.probabilitiesPct.total),''],
      ['上涨时中位涨幅',actualPct(strength.upMedianChangePct),strength.start+' 起 · 上涨样本 '+strength.upSampleCount+' 根','positive'],
      ['下跌时中位跌幅',actualPct(strength.downMedianChangePct),strength.start+' 起 · 下跌样本 '+strength.downSampleCount+' 根','negative'],
      ['大涨率',pct(large.probabilitiesPct.up),
        large.start+' 起 · 涨幅 ≥'+large.thresholdPct+'% · '+large.counts.up+' / '+large.sampleCount+' 根','positive'],
      ['大跌率',pct(large.probabilitiesPct.down),
        large.start+' 起 · 跌幅 ≤−'+large.thresholdPct+'% · '+large.counts.down+' / '+large.sampleCount+' 根','negative'],
      ['平均涨跌幅',actualPct(strength.averageChangePct),strength.start+' 起 · 样本 '+strength.sampleCount+' 根的带符号均值',''],
      ['典型日内振幅',magnitudePct(strength.medianIntradayRangePct),
        strength.intradayRangeStart+' 起 · 振幅样本 '+strength.intradayRangeSampleCount+
        ' 根 · 普通日线 '+magnitudePct(base.strength.medianIntradayRangePct),''],
    ];
    const cards=metrics.map(([label,value,note,className])=>{
      const card=document.createElement('div');
      const heading=document.createElement('span');heading.textContent=label;
      const number=document.createElement('strong');number.textContent=value;number.className=className;
      const detail=document.createElement('small');detail.textContent=note;
      card.append(heading,number,detail);
      return card;
    });
    document.getElementById('ganzhi-calendar-strength-cards').replaceChildren(...cards);
  }
  paintMonthSummary(result,month){
    const renderKey=JSON.stringify([result,month]);
    if(this.monthSummaryKey===renderKey) return;
    this.monthSummaryKey=renderKey;
    const [year,number]=month.split('-');
    const heading=document.createElement('span');
    heading.className='ganzhi-calendar-month-label';
    heading.textContent=year+'年'+Number(number)+'月 · 判断核对';
    const value=document.createElement('strong');
    const detail=document.createElement('small');
    if(result.state==='unfinished'){
      value.textContent='未完成';
      detail.textContent='月末收盘后统计正确率';
    }else if(result.state==='stale'){
      value.textContent='等待行情同步';
      detail.textContent='本月已结束，数据尚未覆盖月末';
    }else if(result.state==='missing'){
      value.textContent='数据不完整';
      detail.textContent='当前月份未完整载入';
    }else if(result.state==='empty'){
      value.textContent='暂无正确率';
      detail.textContent='无可核对的方向判断';
    }else{
      value.textContent='正确率 '+result.accuracyPct.toFixed(2)+'%';
      detail.textContent='判断正确 '+result.correct+' / '+result.judged+
        ' 天 · 未计入 '+result.excluded+' 天';
    }
    this.monthSummary.replaceChildren(heading,value,detail);
  }
  paintCells(){
    for(const cell of this.el.querySelectorAll('.fc-daygrid-day[data-date]'))
      this.paintCell(cell,cell.dataset.date);
  }
  paintCell(cell,date){
    const content=cell.querySelector('.ganzhi-calendar-cell');
    if(!content) return;
    const row=this.rows.get(date);
    const actualLargeMove=row?.actualChangePct!=null?row.actualLargeMoveDirection:null;
    cell.classList.toggle('ganzhi-calendar-big-up',actualLargeMove==='up');
    cell.classList.toggle('ganzhi-calendar-big-down',actualLargeMove==='down');
    cell.classList.toggle('ganzhi-calendar-selected',date===this.selectedDate);
    const renderKey=JSON.stringify([row,this.payload?.benchmark.strength.medianAbsoluteChangePct,this.payload?.thresholdPct]);
    if(content.renderKey===renderKey) return;
    content.renderKey=renderKey;
    content.replaceChildren();
    cell.style.removeProperty('--ganzhi-strength-bg');
    cell.title='';
    if(!row?.ganzhi) return;
    const typical=Number(row.strength?.medianAbsoluteChangePct);
    const baseline=Number(this.payload?.benchmark.strength.medianAbsoluteChangePct);
    if(row.sampleCount&&row.strength?.medianAbsoluteChangePct!=null){
      const ratio=baseline>0?typical/baseline:typical>0?2:0;
      const alpha=0.025+0.21*Math.min(ratio/2,1);
      cell.style.setProperty('--ganzhi-strength-bg','rgba(78,128,180,'+alpha.toFixed(3)+')');
    }
    const ganzhi=document.createElement('span');
    ganzhi.className='ganzhi-calendar-ganzhi';
    ganzhi.textContent=row.ganzhi;
    content.append(ganzhi);
    if(row.solarTerm){
      const term=document.createElement('span');
      term.className='ganzhi-calendar-term';
      term.textContent=row.solarTerm;
      content.append(term);
    }
    const rate=document.createElement('span');
    rate.className='ganzhi-calendar-rate direction-'+row.signalDirection;
    const addRate=(labelText,valueText)=>{
      const line=document.createElement('span');
      line.className='ganzhi-calendar-rate-line';
      const label=document.createElement('span');
      label.className='ganzhi-calendar-rate-label';
      label.textContent=labelText;
      const value=document.createElement('strong');
      value.textContent=valueText;
      line.append(label,value);
      rate.append(line);
    };
    if(row.signalDirection==='up') addRate('上涨 ',pct(row.signalPct));
    else if(row.signalDirection==='down') addRate('下跌 ',pct(row.signalPct));
    else if(row.sampleCount){
      addRate('上涨 ',pct(row.upPct));
      addRate('下跌 ',pct(row.downPct));
    }else addRate('暂无样本','');
    content.append(rate);
    const metric=(className,label,value)=>{
      const line=document.createElement('span');line.className=className;
      const name=document.createElement('span');name.className='ganzhi-calendar-metric-label';name.textContent=label+' ';
      const number=document.createElement('strong');number.textContent=value;
      line.append(name,number);content.append(line);
    };
    metric('ganzhi-calendar-amplitude','典型幅度',magnitudePct(row.strength?.medianAbsoluteChangePct));
    metric('ganzhi-calendar-large','大行情率',pct(row.strength?.largeMove.probabilitiesPct.total));
    const strengthSample=document.createElement('span');strengthSample.className='ganzhi-calendar-strength-samples';
    strengthSample.textContent='幅度样本 '+row.strength.sampleCount;content.append(strengthSample);
    const sample=document.createElement('span');sample.className='ganzhi-calendar-samples';
    sample.textContent='方向样本 '+row.sampleCount;content.append(sample);
    if(row.actualChangePct!==null){
      const actual=document.createElement('span');
      actual.className='ganzhi-calendar-actual actual-'+row.actualDirection;
      const label=document.createElement('span');
      label.className='ganzhi-calendar-actual-label';
      label.textContent='实际 ';
      const value=document.createElement('strong');
      value.textContent=actualPct(row.actualChangePct);
      actual.append(label,value);
      content.append(actual);
    }
    cell.title=date+' '+row.ganzhi+'；历史上涨率 '+pct(row.upPct)+
      '，下跌率 '+pct(row.downPct)+'；典型幅度（绝对值中位数） '+magnitudePct(row.strength?.medianAbsoluteChangePct)+
      '；大行情率 '+pct(row.strength?.largeMove.probabilitiesPct.total)+'（≥'+this.payload.thresholdPct+'% · '+
      row.strength.largeMove.start+' 起 · 大行情样本 '+row.strength.largeMove.sampleCount+' 根）'+
      '；方向有效样本 '+row.sampleCount+' 根；幅度样本 '+row.strength.sampleCount+' 根（'+row.strength.start+' 起）'+
      (row.actualChangePct===null?'':'；当日实际涨跌幅 '+actualPct(row.actualChangePct))+
      (actualLargeMove?'；已完成大行情：'+(actualLargeMove==='up'?'上涨常亮绿色':'下跌常亮红色'):'');
  }
}
