import { buildMarkers } from '../markers/daily-markers.js';

export class MarketChart {
  constructor(container, onSelect) {
    const L = window.LightweightCharts;
    this.container = container;
    this.candles = [];
    this.byDate = new Map();
    this.highlightDates = new Set();
    this.options = {period:'day',showGanzhi:true,showTerms:true};
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
    const oldRange = preserve ? this.chart.timeScale().getVisibleLogicalRange() : null;
    this.candles = candles; this.options.period=period;
    this.byDate = new Map(candles.map(c=>[c.metadata.startDate,c]));
    this.markerApi.setMarkers([]);
    this.series.setData(this.candlePoints());
    this.volume.setData(candles.map(c=>({time:c.metadata.startDate,value:Number(c.volume),color:Number(c.close)>=Number(c.open)?'#33584f':'#5e3942'})));
    if(oldRange) this.chart.timeScale().setVisibleLogicalRange(oldRange);
    else {
      const visible = period==='day'?65:period==='week'?60:period==='month'?42:15;
      this.chart.timeScale().setVisibleLogicalRange({from:Math.max(-1,candles.length-visible),to:candles.length+3});
    }
    this.scheduleMarkers();
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
      return point;
    });
  }
  setHighlightDates(dates) {
    const next=new Set(dates);
    if(next.size===this.highlightDates.size&&[...next].every(d=>this.highlightDates.has(d))) return;
    this.highlightDates=next;
    this.series.setData(this.candlePoints());
  }
  focusDate(date) {
    const i=this.candles.findIndex(c=>c.metadata.startDate===date);
    if(i<0) return;
    this.chart.timeScale().setVisibleLogicalRange({from:i-15,to:i+15});
    this.chart.setCrosshairPosition(Number(this.candles[i].close),date,this.series);
  }
  scheduleMarkers() {
    cancelAnimationFrame(this.markerFrame);
    this.markerFrame=requestAnimationFrame(()=>{
      this.markerApi.setMarkers(buildMarkers(this.candles,this.chart.timeScale().getVisibleLogicalRange(),this.container.clientWidth-80,this.options));
    });
  }
  setOptions(options) { Object.assign(this.options,options); this.scheduleMarkers(); }
  fit() { this.chart.timeScale().fitContent(); }
}
