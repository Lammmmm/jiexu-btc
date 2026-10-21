"""Causality, exact filtering, calendar inference, and delivered-output checks."""
import copy
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest
import study as s

@pytest.fixture(scope='module')
def data():return s.parent.read_source()

def test_inputs_match_locked_hashes():s.verify_inputs()

def test_exact_55_threshold_and_flat_denominator():
    assert s.choice(20,11,9)==1
    assert s.choice(20,9,11)==-1
    assert s.choice(20,10,10)==0
    assert s.choice(20,10,9)==0  # one flat must not be removed
    assert s.choice(0,0,0)==0
    assert s.choice(2001,1100,901)==0  # rounded 55.0% is below 55%

def test_source_signs_use_original_decimal(data):
    signs=s.direction_arrays(data)
    for i in [50,500,1000,2000,3000]:
        r=data['source']['daily'][i];c=Decimal(r['close']);o=Decimal(r['open']);p=Decimal(data['source']['daily'][i-1]['close'])
        assert signs['oc'][i]==int(c>o)-int(c<o)
        assert signs['cc'][i]==int(c>p)-int(c<p)

def test_current_or_future_return_does_not_change_gate(data):
    signs=s.direction_arrays(data);orig=s.selections(data,signs)
    k=int(np.flatnonzero(data['dates']=='2023-07-01')[0]);changed={b:v.copy() for b,v in signs.items()}
    for b in changed:changed[b][k:]=-1
    other=s.selections(data,changed)
    columns=['date','basis','history_n','history_up','history_down','side','selected','last_history_close']
    pd.testing.assert_frame_equal(orig.loc[orig.date<='2023-07-01',columns],other.loc[other.date<='2023-07-01',columns])

def test_gate_counts_match_independent_scalar_prefix(data):
    signs=s.direction_arrays(data);sel=s.selections(data,signs)
    for row in sel.iloc[::41].itertuples():
        ids=[i for i,d in enumerate(data['dates']) if data['valid_'+row.basis][i] and data['ct'][i]<row.decision and data['g'][i]==row.g]
        up=sum(int(signs[row.basis][i]>0) for i in ids);dn=sum(int(signs[row.basis][i]<0) for i in ids)
        assert (len(ids),up,dn)==(row.history_n,row.history_up,row.history_down)
        assert all(data['ct'][i]<row.decision for i in ids)

def test_frozen_pool_ignores_post2022_prices(data):
    signs=s.direction_arrays(data);a=s.fixed_and_current(data,signs)
    changed={b:v.copy() for b,v in signs.items()}
    for b in changed:changed[b][data['dates']>='2023-01-01']=1
    b=s.fixed_and_current(data,changed)
    assert [r for r in a if r['pool']=='frozen_2022']==[r for r in b if r['pool']=='frozen_2022']

def test_calendar_bootstrap_resamples_gate_and_gaps():
    values=np.arange(15.)[:,None];mask=np.array([1,0,0,1,1,0,0,0,1,0,0,1,0,1,0],bool)
    block=4;reps=9;seed=901
    actual=s.masked_bootstrap(values,mask,block,reps,seed)[:,0]
    rng=np.random.default_rng(seed+block);q,r=divmod(len(mask),block)
    starts=rng.integers(0,len(mask),size=(reps,q));tail=rng.integers(0,len(mask),size=reps)
    expected=[]
    for j in range(reps):
        ids=np.concatenate([(st+np.arange(block))%len(mask) for st in starts[j]]+[(tail[j]+np.arange(r))%len(mask)])
        use=ids[mask[ids]];expected.append(values[use,0].mean())
    np.testing.assert_allclose(actual,expected)

def test_constant_target_preserved_by_calendar_bootstrap():
    mask=np.arange(100)%3==0
    draws=s.masked_bootstrap(np.full((100,2),3.5),mask,14,100,81)
    np.testing.assert_allclose(draws,3.5)

def test_all_models_share_selected_dates_and_outcomes(data):
    pred=pd.read_csv(s.BASE/'results/predictions.csv.gz');sel=pd.read_csv(s.OUT/'selection_daily.csv')
    for basis in ['oc','cc']:
        expected=set(sel[(sel.basis==basis)&sel.selected&(sel.date>=s.P['test_start'])].date)
        for t in s.TARGETS:
            frames,dates=s.frames_for(pred,t);mask=s.selection_mask(sel,basis,dates)
            assert set(dates[mask])==expected
            for model,x in frames.items():
                assert len(x[mask])==len(expected)
                np.testing.assert_array_equal(x.actual.to_numpy()[mask],frames['A'].actual.to_numpy()[mask])

def test_delivered_primary_family_and_threshold_membership():
    rows=pd.read_json(s.OUT/'paired_60.json')
    assert len(rows)==176
    assert np.all(rows.calendar_n==1389)
    assert np.all((rows.p_holm>=rows.p)&(rows.p_holm<=1))
    sel=pd.read_csv(s.OUT/'selection_daily.csv')
    assert np.all(sel.selected==((100*sel.history_up>=55*sel.history_n)|(100*sel.history_down>=55*sel.history_n)))
    assert np.all(sel.last_history_close<sel.decision)

def test_selected_export_exact_join():
    sel=pd.read_csv(s.OUT/'selection_daily.csv');p=pd.read_csv(s.OUT/'selected_predictions.csv.gz')
    assert len(p)==int(sel.selected.sum())*len(s.MODELS)*len(s.TARGETS)
    assert np.all(p.last_train_close<p.decision)
    for basis in ['oc','cc']:
        keys=sel[(sel.basis==basis)&sel.selected].set_index('date')
        pp=p[p.basis==basis]
        assert set(pp.date)==set(keys.index)
        assert np.all(pp.side.to_numpy()==keys.loc[pp.date,'side'].to_numpy())

def test_exported_ganzhi_candles_start_in_2017_and_are_closed(data):
    x=pd.read_csv(s.OUT/'daily_ganzhi_candles_2017.csv')
    assert x.date.iloc[0]=='2017-08-18' and x.date.iloc[-1]=='2026-10-20'
    assert len(x)==3348 and int(x.valid_cc.sum())==3345
    assert set(x.g)==set(range(60))
    assert np.all(x.close_time<int(data['source']['metadata']['last_sync_ms']))
    assert set(x.date)==set(data['dates'][data['valid_oc']])
