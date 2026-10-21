"""Read-only production oracle for calendar and every training/validation direction count."""
from pathlib import Path
from decimal import Decimal
import sys,json,sqlite3
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parents[1]))
from backend.models import Candle
from backend.calendar.repository import CalendarRepository
from backend.statistics.ganzhi import GanzhiStatisticsService
src=json.loads((R/'snapshot.json').read_text('utf-8'));protocol=json.loads((R/'protocol.json').read_text('utf-8'))
rows=json.loads((R/'results/ganzhi_splits.json').read_text('utf-8'))
class FrozenMarket:
    def snapshot(self):return [Candle(r['timestamp'],r['close_time'],*(Decimal(r[k]) for k in ['open','high','low','close','volume']),r['date']) for r in src['daily']],src['metadata']
cal=CalendarRepository(R.parents[1]/'data/calendar.db');canonical=cal.range(src['daily'][0]['date'],src['daily'][-1]['date'])
checks=0
for r in src['calendar']:
    x=canonical[r['date']];assert (x['ganzhi_day'],x['ganzhi_index'])==(r['ganzhi_day'],r['ganzhi_index']);checks+=1
splits={s['id']:s for s in protocol['splits']}
for year in range(2021,2027):splits[f'Y{year}']=dict(train_start=f'{year-3}-01-01',train_end=f'{year-1}-12-31',test_start=f'{year}-01-01',test_end='2026-10-20' if year==2026 else f'{year}-12-31')
service=GanzhiStatisticsService(FrozenMarket(),cal);prepared=service._prepare('day')
for r in rows:
    split=splits[r['split']]
    for stage in ['train','test']:
        x=service._summarize(r['ganzhi'],prepared,start=split[stage+'_start'],end=split[stage+'_end'],basis='open' if r['basis']=='oc' else 'previous_close',period='day')
        assert x['sampleCount']==r[stage+'_n'];checks+=1
        for k in ['up','down','flat']:assert x['counts'][k]==r[stage+'_'+k];checks+=1
    chosen=1 if r['train_up']>r['train_down'] else -1 if r['train_down']>r['train_up'] else 0
    assert chosen==r['direction'];checks+=1
    if chosen:
        assert r['test_success']==r['test_up' if chosen>0 else 'test_down'];checks+=1
# Check the frozen completed candles against the current repository cache too.
conn=sqlite3.connect((R.parents[1]/'data/market.db').resolve().as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
actual={r['date']:dict(r) for r in conn.execute("SELECT * FROM daily_candles WHERE date <= '2026-10-20'")};conn.close();matched=0
for r in src['daily']:
    if r['date']>'2026-10-20':continue
    a=actual[r['date']]
    assert (a['timestamp'],a['close_time'])==(r['timestamp'],r['close_time'])
    for k in ['open','high','low','close','volume']:assert Decimal(a[k])==Decimal(r[k])
    matched+=1
out=dict(status='PASS',production_rule_checks=checks,calendar_dates=len(src['calendar']),training_validation_group_rows=len(rows),
    current_cache_completed_candles_matched=matched,databases_readonly=True,production_changes=False)
(R/'results/production_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
