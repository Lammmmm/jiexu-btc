export function buildMarkers(candles, range, width, options) {
  if (!['day', 'month'].includes(options.period) || !candles.length) return [];
  const from = Math.max(0, Math.floor(range?.from ?? 0));
  const to = Math.min(candles.length - 1, Math.ceil(range?.to ?? candles.length - 1));
  const count = Math.max(1, (range?.to ?? to) - (range?.from ?? from));
  const pixelsPerBar = width / count;
  const markers = [];
  if (options.period === 'month') {
    if (!options.showGanzhi) return markers;
    // Label every visible month when it fits; anchor sparse labels at the newest visible candle.
    const step = Math.max(1, Math.ceil(22 / Math.max(0.1, pixelsPerBar)));
    for (let i = from; i <= to; i++) {
      if ((to - i) % step !== 0) continue;
      const m = candles[i].metadata;
      markers.push({
        time:m.startDate, position:'belowBar', color:'#a8cfc4',
        shape:'circle', size:0, text:m.displayGanzhi,
      });
    }
    return markers;
  }
  const step = Math.max(1, Math.ceil(45 / Math.max(0.1, pixelsPerBar)));
  let lastTermIndex = -Infinity;
  for (let i = from; i <= to; i++) {
    const c = candles[i], m = c.metadata;
    if (options.showGanzhi && i % step === 0) {
      markers.push({time:m.startDate, position:'belowBar', color:'#8cb9b2', shape:'circle', size:0, text:m.ganzhi_day});
    }
    if (options.showDay14 && m.startDate.endsWith('-14')) {
      markers.push({
        time:m.startDate, position:'aboveBar', color:'#f2c879',
        shape:'circle', size:1, text:pixelsPerBar*28>=40?'14号':'',
      });
    }
    for(const event of options.economicEvents?.get(m.startDate)||[]){
      if(!(event.kind==='cpi'?options.showCPI:options.showNFP)) continue;
      markers.push({
        id:event.id,time:m.startDate,position:'aboveBar',
        color:event.kind==='cpi'?'#82baff':'#c5a1ff',shape:'arrowDown',size:1,
        text:pixelsPerBar*7>=35?(event.label+(event.status==='scheduled'?'·计划':'')):'',
      });
    }
    if (options.showTerms && m.solar_term && (i-lastTermIndex)*pixelsPerBar >= 45) {
      markers.push({time:m.startDate, position:'aboveBar', color:'#d8b570', shape:'circle', size:0.6, text:m.solar_term});
      lastTermIndex = i;
    }
  }
  return markers;
}
