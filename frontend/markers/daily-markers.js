export function buildMarkers(candles, range, width, options) {
  if (options.period !== 'day' || !candles.length) return [];
  const from = Math.max(0, Math.floor(range?.from ?? 0));
  const to = Math.min(candles.length - 1, Math.ceil(range?.to ?? candles.length - 1));
  const count = Math.max(1, (range?.to ?? to) - (range?.from ?? from));
  const pixelsPerBar = width / count;
  const step = Math.max(1, Math.ceil(45 / Math.max(0.1, pixelsPerBar)));
  const markers = [];
  let lastTermIndex = -Infinity;
  for (let i = from; i <= to; i++) {
    const c = candles[i], m = c.metadata;
    if (options.showGanzhi && i % step === 0) {
      markers.push({time:m.startDate, position:'belowBar', color:'#8cb9b2', shape:'circle', size:0, text:m.ganzhi_day});
    }
    if (options.showTerms && m.solar_term && (i-lastTermIndex)*pixelsPerBar >= 45) {
      markers.push({time:m.startDate, position:'aboveBar', color:'#d8b570', shape:'circle', size:0.6, text:m.solar_term});
      lastTermIndex = i;
    }
  }
  return markers;
}
