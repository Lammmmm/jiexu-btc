import copy,json
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest
import study as s

@pytest.fixture(scope='module')
def data():return s.e.read_source()

def test_frozen_inputs():s.verify_inputs()

def test_2017_first_repeat_and_no_invented_history(data):
    z=pd.read_csv(s.OUT/'selection_daily.csv')
    assert z.date.min()=='2017-08-18'
    assert not z[z.history_n==0].selected.any()
    assert z[(z.basis=='oc')&z.simple_ready].date.min()=='2017-10-17'
    assert np.all(z[z.simple_ready].common_history_n>=30)
    assert np.all(z[z.simple_ready].common_same_n>=1)

def test_exact_gate_and_future_prices_not_used(data):
    a=s.select_daily(data)
    changed=copy.deepcopy(data)
    i=int(np.flatnonzero(data['dates']=='2020-01-01')[0])
    for row in changed['source']['daily'][i:]:row['close']=str(Decimal(row['open'])*2)
    b=s.select_daily(changed)
    keys=['date','basis','history_n','up','down','side','selected','simple_ready']
    pd.testing.assert_frame_equal(a.loc[a.date<='2020-01-01',keys],b.loc[b.date<='2020-01-01',keys])
    assert np.all(a.selected==((a.history_n>0)&((100*a.up>=55*a.history_n)|(100*a.down>=55*a.history_n))))

def test_55_boundary_and_flat_count():
    assert s.gate.choice(20,11,9)==1
    assert s.gate.choice(20,9,11)==-1
    assert s.gate.choice(20,10,9)==0
    assert s.gate.choice(2001,1100,901)==0

def test_all_60_history_ranking_and_exact_range(data):
    rows=json.loads((s.OUT/'ranking_history_all_oc.json').read_text('utf-8'))
    assert len(rows)==60 and {r['g'] for r in rows}==set(range(60))
    for a,b in zip(rows,rows[1:]):assert a['median_range']>=b['median_range']
    for row in rows:
        vals=[]
        for i,r in enumerate(data['source']['daily']):
            if data['valid_oc'][i] and data['g'][i]==row['g']:
                vals.append(float((Decimal(r['high'])-Decimal(r['low']))/Decimal(r['open'])))
        assert len(vals)==row['n']
        assert abs(np.median(vals)-row['median_range'])<1e-14
        assert abs(np.mean(vals)-row['mean_range'])<1e-14

def test_rankings_follow_separate_mean_and_median_order():
    allrows=pd.read_csv(s.OUT/'ganzhi_rankings.csv')
    for _,x in allrows.groupby(['basis','scope']):
        assert x.sort_values('rank_median').median_range.is_monotonic_decreasing
        assert x.sort_values('rank_mean').mean_range.is_monotonic_decreasing

def test_complex_warmup_is_fixed_availability(data):
    audit=json.loads((s.OUT/'summary.json').read_text('utf-8'))[0]
    features=np.load(s.BASE/'results/causal_features.npz')['range']
    okay=data['valid']&np.isfinite(features).all(1)
    i=int(np.flatnonzero(data['dates']==audit['complex_start'])[0])
    assert len(s.e.eligible(data,i,okay))==180
    prev=int(np.flatnonzero(data['valid']&(data['dates']<audit['complex_start']))[-1])
    assert len(s.e.eligible(data,prev,okay))<180

def test_calendar_padding_retains_missing_days():
    rows=[]
    for m in ['A','C']:
        rows.extend([dict(date='2020-01-01',target='range',model=m,actual=.1,pred=.09),dict(date='2020-01-03',target='range',model=m,actual=.2,pred=.1)])
    sel=pd.DataFrame([dict(date=d,basis=b,selected=True,side=1) for b in ['oc','cc'] for d in ['2020-01-01','2020-01-03']])
    pp,ss=s.calendar_pad(pd.DataFrame(rows),sel)
    assert len(pp)==6 and len(ss)==6
    assert not ss[ss.date=='2020-01-02'].selected.any()
    assert np.all(pp[pp.date=='2020-01-02'].actual==0)

def test_complex_forecasts_are_same_dates_and_closed(data):
    p=pd.read_csv(s.OUT/'predictions.csv.gz',low_memory=False)
    assert (p.last_train_close<p.decision).all()
    expected=p[(p.target=='range')&(p.model=='A')].date.tolist()
    for (t,m),x in p.groupby(['target','model']):
        assert x.date.tolist()==expected
        ids=np.searchsorted(data['dates'],x.date.to_numpy())
        np.testing.assert_allclose(x.actual.to_numpy(),data['y'][ids,s.TARGETS.index(t)],atol=1e-14)

def test_early_models_do_not_claim_2017_complex_prediction():
    p=pd.read_csv(s.OUT/'simple_predictions.csv.gz')
    assert p.date.min()=='2017-10-17'
    assert 'C' not in p.model.unique() and 'F' not in p.model.unique()
    assert (p.group_n>=1).all() and (p.last_train_close<p.decision).all()

def test_exante_top_group_is_determined_only_from_past_predictions():
    p=pd.read_csv(s.OUT/'predictions.csv.gz',low_memory=False)
    f=p[(p.target=='range')&(p.model=='F')].sort_values('date')
    r=pd.read_json(s.OUT/'exante_top10_daily.json',convert_dates=False)
    for row in r.iloc[::97].itertuples():
        past=f[(f.date<row.date)&(f.date>=(pd.Timestamp(row.date)-pd.Timedelta(days=365)).strftime('%Y-%m-%d'))]
        group=past.groupby('g').apply(lambda z:pd.Series({'n':len(z),'sum':(z.actual/z.pred).sum()}),include_groups=False).reindex(range(60))
        assert group.n.min()>=5
        pooled=(past.actual/past.pred).mean();expected=(group['sum']+20*pooled)/(group.n+20)
        order=np.lexsort((np.arange(60),-expected.to_numpy()))[:10]
        assert list(order)==row.chosen_g
        assert row.top10==(row.g in order) and row.last_history_date<row.date

def test_primary_family_complete():
    a=json.loads((s.OUT/'paired_60.json').read_text('utf-8'))
    assert len(a)==176
    assert all(r['p_holm']>=r['p'] for r in a)
