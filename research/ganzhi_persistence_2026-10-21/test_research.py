import copy,json
import numpy as np
import pandas as pd
import pytest
from core import *
from simulate import Sampler,vector_result
from evaluate import exact_stratified_tail
from bootstrap import calendar_weights

@pytest.fixture(scope='module')
def data():return read_data()[0]

@pytest.fixture(scope='module')
def a(data):return prepare(data,'oc')

def test_source_closed_validity_and_calendar(data):
    assert data.loc[data.oc_valid,'date'].min()=='2017-08-18'
    assert data.loc[data.oc_valid,'date'].max()=='2026-10-20'
    assert data.oc_valid.sum()==3348 and data.cc_valid.sum()==3345
    assert not data.iloc[-1].oc_valid and data.iloc[-1].date=='2026-10-21'
    assert np.all(np.diff(data.g.to_numpy())%60==1)

def test_split_train_test_are_nonoverlapping_but_splits_overlap():
    for r in all_splits():assert r['train_end']<r['test_start']
    # S1 validation2023 is also S3 training2023: never independent replications.
    assert P['splits'][0]['test_start']<=P['splits'][2]['train_end']

def test_exact_threshold_integer_classification():
    assert 11*100>=55*20 and not 1100*100>=55*2001
    assert 18*100>=60*30 and not 17*100>=60*30
    assert 13*100>=65*20 and not 12*100>=65*20

def test_future_direction_does_not_change_train_choice(a):
    up=[];dn=[];mutup=[];mutdn=[];sign=a['df'].sign.to_numpy();other=sign.copy()
    other[a['df'].date.to_numpy()>='2023-01-01']=1
    for period in a['periods']:
        u,d=group_counts(sign,period);up.append(u);dn.append(d)
        u,d=group_counts(other,period);mutup.append(u);mutdn.append(d)
    x=split_arrays(a,up,dn,a['splits'][0]);y=split_arrays(a,mutup,mutdn,a['splits'][0])
    np.testing.assert_array_equal(x['side'],y['side']);np.testing.assert_array_equal(x['selected'],y['selected'])

@pytest.mark.parametrize('method',METHODS)
def test_randomization_bijection_strata_and_not_global_relabel(a,method):
    sampler=Sampler(a,method,12345);maps=sampler.mapping(12);sampler.audit(maps)
    delta=(a['df'].g.to_numpy()[maps]-a['df'].g.to_numpy()[None,:])%60
    assert not np.any(np.all(delta==delta[:,0,None],axis=1))

def test_bad_global_ganzhi_phase_only_renames_counts(data):
    a=prepare(data,'oc');bdf=data.copy();bdf['g']=(bdf.g+17)%60;b=prepare(bdf,'oc')
    x=vector_result(a,a['df'].sign.to_numpy()[None,:]);y=vector_result(b,b['df'].sign.to_numpy()[None,:])
    np.testing.assert_array_equal(x['candidates'],y['candidates']);np.testing.assert_array_equal(x['continued'],y['continued'])

def test_vector_pipeline_matches_scalar_full_rescreen(a):
    maps=Sampler(a,'weekly_rotation',567).mapping(3);values=a['df'].sign.to_numpy()[maps]
    result=vector_result(a,values)
    for draw in range(3):
        for si,split in enumerate(a['splits']):
            counts=np.zeros((3,3),int);candidates=np.zeros(3,int)
            train=a['periods'][split['train_period']]['ids'];test=a['periods'][split['test_period']]['ids'];gg=a['df'].g.to_numpy()
            for g in range(60):
                tr=values[draw,train[gg[train]==g]];va=values[draw,test[gg[test]==g]]
                u=int((tr>0).sum());d=int((tr<0).sum());side=1 if u>d else -1 if d>u else 0
                for ti,t in enumerate(TH):
                    if not side or 100*max(u,d)<t*len(tr):continue
                    candidates[ti]+=1;hits=int(np.sum(va==side))
                    for vi,v in enumerate(TH):counts[ti,vi]+=hits*100>=v*len(va)
            np.testing.assert_array_equal(candidates,result['candidates'][draw,si]);np.testing.assert_array_equal(counts,result['continued'][draw,si])

def test_exact_stratified_tail_matches_closed_form_11_of12(a):
    split=a['splits'][1];z=a['df'];test=z[(z.date>=split['test_start'])&(z.date<=split['test_end'])]
    g=int(z.loc[z.ganzhi=='癸亥','g'].iloc[0]);prob=[]
    for r in test[test.g==g].itertuples():
        pool=test[(test.year==r.year)&(test.weekday==r.weekday)&(test.regime==r.regime)];prob.append(float((pool.sign==-1).mean()))
    assert len(prob)==12
    brute=np.prod(prob)+sum((1-p)*np.prod([q for j,q in enumerate(prob) if j!=i]) for i,p in enumerate(prob))
    assert abs(exact_stratified_tail(a,split,g,-1,11,True)-brute)<1e-15

def test_occurrence_future_labels_not_used_for_direction(a):
    source=a['df'].sign.to_numpy();_,details=rolling_stats(a,source,True);old=next(r for r in details if r['horizon']==10 and r['policy']=='overlap')
    idx=a['groups'][old['g']];start=int(np.flatnonzero(a['df'].date.to_numpy()==old['test_first'])[0]);changed=source.copy();changed[start:]=-source[start:]
    _,rows=rolling_stats(a,changed,True)
    new=next(r for r in rows if r['g']==old['g'] and r['test_first']==old['test_first'] and r['horizon']==10 and r['policy']=='overlap')
    assert (new['direction'],new['train_success'],new['train_last'])==(old['direction'],old['train_success'],old['train_last'])

def test_nonoverlap_windows_and_missing30_horizon():
    z=pd.read_csv(OUT/'rolling_windows.csv')
    for _,rows in z[z.policy=='nonoverlap'].groupby(['basis','g','horizon']):
        rows=rows.sort_values('test_first');assert all(a<b for a,b in zip(rows.test_last.iloc[:-1],rows.test_first.iloc[1:]))
    missing=[r for r in json.loads((OUT/'rolling_summary.json').read_text('utf-8')) if r['horizon']==30]
    assert all(r['available_anchor_windows']==0 and r['hit_rate'] is None for r in missing)

def test_calendar_bootstrap_uses_calendar_counts_and_exact_lengths():
    n=71;reps=8;block=60;seed=453;w=calendar_weights(n,reps,block,seed)
    assert np.all(w.sum(1)==n)
    rng=np.random.default_rng(seed);starts=rng.integers(0,n,size=(reps,2))
    for i in range(reps):
        ids=np.r_[(starts[i,0]+np.arange(60))%n,(starts[i,1]+np.arange(11))%n]
        np.testing.assert_array_equal(w[i],np.bincount(ids,minlength=n))

def test_delivered_family_sizes_and_reselecting_null_variation():
    rows=json.loads((OUT/'null_persistence_tests.json').read_text('utf-8'))
    assert sum(r['kind']=='main' for r in rows)==216 and sum(r['kind']=='annual_rolling' for r in rows)==432
    assert len(json.loads((OUT/'individual_randomization.json').read_text('utf-8')))==1440
    assert len(json.loads((OUT/'correlation_tests.json').read_text('utf-8')))==240
    for method in METHODS:
        for b in ['oc','cc']:
            with np.load(OUT/f'null_{b}_{method}.npz') as x:
                assert len(x['continued'])==19999
                assert np.unique(x['continued'][:,0,0,0]).size>10
                assert np.unique(x['candidates'][:,0,0]).size>10

def test_cached_simulation_first_batch_reproduces_exactly(a):
    method='weekly_rotation';sampler=Sampler(a,method,P['seed']+METHODS.index(method)*10000)
    maps=sampler.mapping(256);expected=vector_result(a,a['df'].sign.to_numpy()[maps])
    with np.load(OUT/f'null_oc_{method}.npz') as archive:
        for key in expected:np.testing.assert_allclose(expected[key],archive[key][:256],rtol=0,atol=0,equal_nan=True)
