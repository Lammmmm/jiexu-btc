import { buildMarkers } from '../markers/daily-markers.js';

const samePoint=(left,right)=>JSON.stringify(left)===JSON.stringify(right);
function applySeriesData(series,next,previous=[],incremental=false){
  if(samePoint(next,previous)) return next;
  // Binance normally changes the last bar or appends bars. Earlier corrections
  // still replace the full series so repaired history is never skipped.
  const tailOnly=incremental&&previous.length>0&&next.length>=previous.length&&
    previous.every((point,index)=>point.time===next[index].time&&
      (index===previous.length-1||samePoint(point,next[index])));
  if(tailOnly){
    if(!samePoint(previous.at(-1),next[previous.length-1])) series.update({...next[previous.length-1]});
    for(let index=previous.length;index<next.length;index++) series.update({...next[index]});
  }else series.setData(next.map(point=>({...point})));
  // The library normalizes time in update(); keep our comparison snapshot intact.
  return next;
}

export class MarketChart {
  constructor(container, onSelect) {
    const L = window.LightweightCharts;
    this.container = container;
    this.candles = [];
    this.byDate = new Map();
    this.highlightDates = new Set();
    this.economicEvents = new Map();
    this.options = {period:'day',showCPI:false,showNFP:false,showDay14:false,showGanzhi:true,showTerms:true};
    this.chart = L.createChart(container, {
      autoSize:true,
      layout:{background:{color:'#111c27'},textColor:'#8c9caa',fontSize:11,fontFamily:'Consolas, Microsoft YaHei, sans-serif',attributionLogo:true},
      grid:{vertLines:{color:'#1a2834'},horzLines:{color:'#1a2834'}},
      rightPriceScale:{borderColor:'#2a3946',scaleMargins:{top:0.17,bottom:0.12}},
      timeScale:{borderColor:'#2a3946',rightOffset:4,barSpacing:12,minBarSpacing:0.15,timeVisible:false},
      crosshair:{mode:L.CrosshairMode.Normal,vertLine:{color:'#647c8d',labelBackgroundColor:'#314656'},horzLine:{color:'#647c8d',labelBackgroundColor:'#314656'}},
      localization:{locale:'zh-CN'},
    });
    this.series = this.chart.addSeries(L.CandlestickSeries,{
      upColor:'#67d7b4',downColor:'#ef7e89',wickUpColor:'#67d7b4',wickDownColor:'#ef7e89',
      borderVisible:false,priceFormat:{type:'price',precision:2,minMove:0.01},
    });
    this.volume = this.chart.addSeries(L.HistogramSeries,{priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false},1);
    this.chart.panes()[1].setHeight(90);
    this.markerApi = L.createSeriesMarkers(this.series,[]);
    this.chart.subscribeCrosshairMove(p => { const c=this.lookup(p.time); if(c) onSelect(c,false); });
    const pin = p => { const c=this.lookup(p.time); if(c) onSelect(c,true); };
    this.chart.subscribeClick(pin);
    this.chart.subscribeDblClick(pin);
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => this.scheduleMarkers());
    this.resizeObserver = new ResizeObserver(() => this.scheduleMarkers());
    this.resizeObserver.observe(container);
  }
  lookup(time) {
    if (!time) return null;
    const key = typeof time==='string' ? time : typeof time==='object' ? [time.year,String(time.month).padStart(2,'0'),String(time.day).padStart(2,'0')].join('-') : null;
    return this.byDate.get(key);
  }
  setData(candles, period, preserve=false) {
    const incremental=preserve&&period===this.options.period;
    const oldRange = preserve ? this.chart.timeScale().getVisibleLogicalRange() : null;
    const sameDates=incremental&&candles.length>=this.candles.length&&
      this.candles.every((c,index)=>c.metadata.startDate===candles[index].metadata.startDate);
    if(!sameDates){this.markerApi.setMarkers([]);this.markerKey=null;}
    this.candles = candles; this.options.period=period;
    this.byDate = new Map(candles.map(c=>[c.metadata.startDate,c]));
    this.pricePoints=applySeriesData(this.series,this.candlePoints(),this.pricePoints,incremental);
    const volumes=candles.map(c=>({
      time:c.metadata.startDate,value:Number(c.volume),
      color:Number(c.close)>=Number(c.open)?'#33584f':'#5e3942',
    }));
    this.volumePoints=applySeriesData(this.volume,volumes,this.volumePoints,incremental);
    if(oldRange) this.chart.timeScale().setVisibleLogicalRange(oldRange);
    else {
      const visible = period==='day'?65:period==='week'?60:period==='month'?36:15;
      this.chart.timeScale().setVisibleLogicalRange({from:Math.max(-1,candles.length-visible),to:candles.length+3});
    }
    this.paintMarkers();
  }
  candlePoints() {
    const highlighting=['day','month'].includes(this.options.period)&&this.highlightDates.size>0;
    return this.candles.map(c=>{
      const point={time:c.metadata.startDate,open:Number(c.open),high:Number(c.high),low:Number(c.low),close:Number(c.close)};
      if(highlighting){
        const matched=this.highlightDates.has(c.metadata.startDate);
        const up=Number(c.close)>=Number(c.open);
        point.color=matched?(up?'#67d7b4':'#ef7e89'):(up?'rgba(103,215,180,0.2)':'rgba(239,126,137,0.2)');
        point.wickColor=matched?'#e9ca88':point.color;
        point.borderColor=matched?'#e9ca88':point.color;
      }
      if(this.options.period==='day'&&this.options.showDay14&&c.metadata.startDate.endsWith('-14'))
        point.wickColor='#f2c879';
      if(this.options.period==='day'){
        const events=this.economicEvents.get(c.metadata.startDate)||[];
        const hasCPI=this.options.showCPI&&events.some(e=>e.kind==='cpi');
        const hasNFP=this.options.showNFP&&events.some(e=>e.kind==='nfp');
        if(hasCPI||hasNFP) point.wickColor=hasCPI&&hasNFP?'#e4c5ff':hasCPI?'#82baff':'#c5a1ff';
      }
      return point;
    });
  }
  setEconomicEvents(events) {
    const grouped=new Map();
    for(const event of events){
      if(!grouped.has(event.date)) grouped.set(event.date,[]);
      grouped.get(event.date).push(event);
    }
    this.economicEvents=grouped;
    if(this.options.showCPI||this.options.showNFP)
      this.pricePoints=applySeriesData(this.series,this.candlePoints(),this.pricePoints);
    this.scheduleMarkers();
  }
  setHighlightDates(dates) {
    const next=new Set(dates);
    if(next.size===this.highlightDates.size&&[...next].every(d=>this.highlightDates.has(d))) return;
    this.highlightDates=next;
    this.pricePoints=applySeriesData(this.series,this.candlePoints(),this.pricePoints);
  }
  focusDate(date) {
    const i=this.candles.findIndex(c=>c.metadata.startDate===date);
    if(i<0) return;
    this.chart.timeScale().setVisibleLogicalRange({from:i-15,to:i+15});
    this.chart.setCrosshairPosition(Number(this.candles[i].close),date,this.series);
  }
  paintMarkers(){
    cancelAnimationFrame(this.markerFrame);
    const markers=buildMarkers(this.candles,this.chart.timeScale().getVisibleLogicalRange(),this.container.clientWidth-80,{...this.options,economicEvents:this.economicEvents});
    const key=JSON.stringify(markers);
    if(key===this.markerKey) return;
    this.markerKey=key;this.markerApi.setMarkers(markers);
  }
  scheduleMarkers() {
    cancelAnimationFrame(this.markerFrame);
    this.markerFrame=requestAnimationFrame(()=>this.paintMarkers());
  }
  setOptions(options) {
    const repaintCandles=['showDay14','showCPI','showNFP'].some(key=>key in options&&options[key]!==this.options[key]);
    Object.assign(this.options,options);
    if(repaintCandles) this.pricePoints=applySeriesData(this.series,this.candlePoints(),this.pricePoints);
    this.scheduleMarkers();
  }
  fit() { this.chart.timeScale().fitContent(); }
}
