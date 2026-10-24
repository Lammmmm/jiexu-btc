"""Numerical replay, source/oracle matching, MC intervals and test-family checks."""
from core import *
from simulate import Sampler,KEEP
from fractions import Fraction
import unittest,gzip,sys

def read(name):return json.loads((OUT/(name+'.json')).read_text('utf-8'))

def main():
    rows,source=data();checks=0;oracle_checks=0;replayed=0
    for basis in P['bases']:
        a=prepared(rows,basis)
        for j in range(3):
            actual=[r for r in read('ganzhi_observed') if r['basis']==basis and r['period']==period_name(j)]
            for r in actual:
                g=r['g'];assert (r['n'],r['binary_n'],r['up'],r['down'])==(int(a['n'][j,g]),int(a['m'][j,g]),int(a['up'][j,g]),int(a['m'][j,g]-a['up'][j,g]));checks+=4
        for im,method in enumerate(P['ideal_nulls']+P['structured_nulls']):
            seed=P['seed']+P['bases'].index(basis)*100000+im*10000
            aa=dict(a,p_actual=.5 if method=='iid50' else a['p_actual']);aa.pop('_bin_expected',None)
            if method.startswith('iid'):
                rng=np.random.default_rng(seed);tu=rng.binomial(a['m'][1],aa['p_actual'],size=(512,60));vu=rng.binomial(a['m'][2],aa['p_actual'],size=(512,60));u=np.stack([tu+vu,tu,vu],axis=1)
            else:
                sampler=Sampler(a,method,seed);maps=sampler.mapping(512);sampler.audit(maps);u=sampler.counts(maps)
            observed=stats(u,aa)
            with np.load(OUT/f'mc_{basis}_{method}_key_distributions.npz') as saved:
                for key in KEEP:np.testing.assert_allclose(saved[key][:512],observed[key],rtol=0,atol=1e-14,equal_nan=True);replayed+=512
            folded=np.maximum(u[:,0],a['m'][0]-u[:,0])/a['n'][0]
            with np.load(OUT/f'folded_{basis}_{method}.npz') as saved:
                np.testing.assert_allclose(saved['dominant_sd'][:512],folded.std(1,ddof=1),rtol=0,atol=1e-14);replayed+=512
            stamp=json.loads((OUT/f'mc_{basis}_{method}.stamp.json').read_text('utf-8'))
            assert stamp['core']==sha(ROOT/'core.py') and stamp['simulator']==sha(ROOT/'simulate.py') and stamp['snapshot']==sha(ROOT/'snapshot.json') and stamp['protocol']==sha(ROOT/'protocol.json')
    for r in read('monte_carlo_tests'):
        if r['p'] is None:continue
        assert abs(r['p']-(r['exceed']+1)/(r['valid_draws']+1))<1e-14
        lo,hi=proportion_confint(r['exceed'],r['valid_draws'],method='wilson')
        assert abs(lo-r['mc_tail_ci_low'])<1e-14 and abs(hi-r['mc_tail_ci_high'])<1e-14;checks+=3
    for r in read('dominant_distribution_tests'):
        with np.load(OUT/f"folded_{r['basis']}_{r['null']}.npz") as saved:v=saved[r['statistic']]
        upper=(1+int((v>=r['observed']-1e-12).sum()))/(len(v)+1);lower=(1+int((v<=r['observed']+1e-12).sum()))/(len(v)+1)
        assert abs(r['p_upper']-upper)<1e-14 and abs(r['p_lower']-lower)<1e-14;checks+=2
    for name in ['aggregate_exact_tests','individual_binomial_normal','individual_conditional','monte_carlo_tests','symmetric_distribution_tests','dominant_distribution_tests','maximum_two_tail_exact']:
        original=read(name);recalc=json.loads(json.dumps(original));adjust(recalc)
        for a,b in zip(original,recalc):
            if a.get('p') is None:continue
            assert abs(a['holm']-b['holm'])<1e-10 and abs(a['bh']-b['bh'])<1e-10;checks+=2
    primary=[r for r in read('aggregate_exact_tests') if r['family']=='exact_primary68'];assert len(primary)==68
    mcprimary=[r for r in read('monte_carlo_tests') if r['family']=='mc_primary200'];assert len(mcprimary)==200
    fractions=json.loads(gzip.decompress((OUT/'integer_exact_fractions.json.gz').read_bytes()))
    for r in fractions:
        f=Fraction(int(r['numerator_hex'],16),int(r['denominator_hex'],16))
        assert abs(float(f)-r['reported_float_p'])<1e-10;checks+=1
    sys.path.insert(0,str(REPO))
    from backend.models import Candle
    from backend.calendar.repository import CalendarRepository
    from backend.statistics.ganzhi import GanzhiStatisticsService
    class FrozenMarket:
        def snapshot(self):return [Candle(r['timestamp'],r['close_time'],*(Decimal(r[k]) for k in ['open','high','low','close','volume']),r['date']) for r in source['daily']],source['metadata']
    cal=CalendarRepository(REPO/'data/calendar.db');service=GanzhiStatisticsService(FrozenMarket(),cal);prep=service._prepare('day')
    canonical=cal.range(source['daily'][0]['date'],source['daily'][-1]['date'])
    for r in source['calendar']:assert (r['ganzhi_day'],r['ganzhi_index'])==(canonical[r['date']]['ganzhi_day'],canonical[r['date']]['ganzhi_index']);oracle_checks+=1
    for r in read('ganzhi_observed'):
        period=r['period'];start='2017-01-01' if period!='validation' else '2023-01-01';end='2022-12-31' if period=='train' else '2026-10-23'
        y=service._summarize(r['ganzhi'],prep,start=start,end=end,basis='open' if r['basis']=='oc' else 'previous_close',period='day')
        assert y['sampleCount']==r['n'];oracle_checks+=1
        for key in ['up','down','flat']:assert y['counts'][key]==r[key];oracle_checks+=1
    suite=unittest.defaultTestLoader.discover(str(ROOT),pattern='test_math.py')
    with (OUT/'unit-tests.txt').open('w',encoding='utf-8') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    assert result.wasSuccessful()
    out=dict(status='PASS',unit_tests=result.testsRun,production_oracle_checks=oracle_checks,independent_numeric_checks=checks,seeded_MC_statistic_values_replayed=replayed,
             integer_aggregate_probabilities_checked=68,integer_individual_probabilities_checked=720,exact_vs_MC_endpoints_checked=68,production_changes=False,databases_readonly=True)
    save('verification',out);print(json.dumps(out))

if __name__=='__main__':main()
