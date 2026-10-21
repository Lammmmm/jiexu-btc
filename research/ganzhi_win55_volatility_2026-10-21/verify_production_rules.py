"""Read-only comparison to the current production calendar/direction rules."""
from pathlib import Path
from decimal import Decimal
import json,sys
R=Path(__file__).resolve().parent;B=R.parent/'ganzhi_volatility_2026-10-21'
sys.path.insert(0,str(R.parents[1]))
from backend.models import Candle
from backend.calendar.repository import CalendarRepository
from backend.statistics.ganzhi import GanzhiStatisticsService
src=json.loads((B/'snapshot.json').read_text('utf-8'))
class FrozenMarket:
    def snapshot(self):
        return [Candle(r['timestamp'],r['close_time'],*(Decimal(r[k]) for k in ['open','high','low','close','volume']),r['date']) for r in src['daily']],src['metadata']
cal=CalendarRepository(R.parents[1]/'data/calendar.db')
actual_cal=cal.range(src['daily'][0]['date'],src['daily'][-1]['date']);checks=0
for r in src['calendar']:
    c=actual_cal[r['date']]
    assert (c['ganzhi_day'],c['ganzhi_index'])==(r['ganzhi_day'],r['ganzhi_index']);checks+=1
service=GanzhiStatisticsService(FrozenMarket(),cal);prepared=service._prepare('day')
pools=json.loads((R/'results/ganzhi_direction_pools.json').read_text('utf-8'))
for p in pools:
    end='2022-12-31' if p['pool']=='frozen_2022' else '2026-10-20'
    x=service._summarize(p['ganzhi'],prepared,start=None,end=end,basis={'oc':'open','cc':'previous_close'}[p['basis']],period='day')
    assert x['sampleCount']==p['n'];checks+=1
    for field in ['up','down','flat']:
        assert x['counts'][field]==p[field];checks+=1
    n=x['sampleCount'];u=x['counts']['up'];dn=x['counts']['down']
    side=1 if n and 100*u>=55*n else -1 if n and 100*dn>=55*n else 0
    assert side==p['side'];checks+=1
out=dict(status='PASS',checks=checks,calendar_label_checks=len(src['calendar']),direction_pool_checks=len(pools),
    direction_history_start='2017-08-18',calendar_connection='SQLite mode=ro',market_source='frozen snapshot; no market database writes')
(R/'results/production_rules_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
