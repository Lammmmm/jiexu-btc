"""Evaluate count persistence, fixed-trained-direction individuals, and future occurrence windows."""
from core import *

def tail(draws,value):
    values=np.asarray(draws);values=values[np.isfinite(values)]
    if value is None or not np.isfinite(value) or not len(values):return dict(p=1.,null_n=len(values),null_mean=None,null_low=None,null_high=None,p_mc_low=None,p_mc_high=None)
    extreme=int(np.sum(values>=value-1e-12));lo,hi=proportion_confint(extreme,len(values),method='wilson')
    return dict(p=(extreme+1)/(len(values)+1),null_n=len(values),null_mean=float(values.mean()),
        null_low=float(np.quantile(values,.025)),null_high=float(np.quantile(values,.975)),p_mc_low=float(lo),p_mc_high=float(hi))

def exact_stratified_tail(a,split,g,direction,k,regime=False):
    """Same IID-stratified null, evaluated analytically rather than by Monte Carlo.

    A given Ganzhi visits a weekday only once per calendar year (LCM=420 days),
    so its validation dates occupy distinct strata. One draw from each stratum
    gives independent Bernoulli terms under this specific permutation null.
    """
    if not direction or k is None:return 1.
    z=a['df'];test=z[(z.date>=split['test_start'])&(z.date<=split['test_end'])]
    own=test[test.g==g];seen=set();distribution=np.array([1.])
    for row in own.itertuples():
        key=(row.year,row.weekday)+(tuple([row.regime]) if regime else ())
        assert key not in seen;seen.add(key)
        pool=test[(test.year==row.year)&(test.weekday==row.weekday)]
        if regime:pool=pool[pool.regime==row.regime]
        probability=float(np.mean(pool.sign.to_numpy()==direction))
        distribution=np.convolve(distribution,[1-probability,probability])
    return float(distribution[int(k):].sum())

def main():
    df,_=read_data();groups=json.loads((OUT/'ganzhi_splits.json').read_text('utf-8'))
    observed_counts=json.loads((OUT/'persistence_counts.json').read_text('utf-8'))
    obs_corr=json.loads((OUT/'correlations_observed.json').read_text('utf-8'))
    obs_roll=json.loads((OUT/'rolling_summary.json').read_text('utf-8'))
    countrows=[];corrows=[];indrows=[];rollrows=[];hist=[];main_draws=[];audits=[];fixedpool=[]
    for basis in ['oc','cc']:
        a=prepare(df,basis)
        for method in METHODS:
            with np.load(OUT/f'null_{basis}_{method}.npz') as archive:
                null={k:archive[k] for k in archive.files}
            audit=json.loads((OUT/f'null_audit_{basis}_{method}.json').read_text('utf-8'));audits.append(audit)
            for si,split in enumerate(a['splits']):
                for ti,t in enumerate(TH):
                    nn=null['candidates'][:,si,ti]
                    for vi,v in enumerate(TH):
                        obs=next(r for r in observed_counts if r['basis']==basis and r['split']==split['id'] and r['train_threshold']==t and r['test_threshold']==v)
                        counts=null['continued'][:,si,ti,vi];stats=tail(counts,obs['continued'])
                        fraction=np.divide(counts,nn,out=np.full(len(nn),np.nan),where=nn>0);fst=tail(fraction,obs['fraction'])
                        matched=nn==obs['selected'];conditional=tail(counts[matched],obs['continued'])
                        row=dict(**obs,method=method,draws=B,**stats,null_selected_mean=float(nn.mean()),null_selected_low=int(np.quantile(nn,.025)),null_selected_high=int(np.quantile(nn,.975)),
                            fraction_null_mean=fst['null_mean'],fraction_null_low=fst['null_low'],fraction_null_high=fst['null_high'],fraction_p=fst['p'],
                            exact_n_conditional_draws=int(matched.sum()),exact_n_conditional_p=conditional['p'],exact_n_conditional_mean=conditional['null_mean'],
                            exact_n_conditional_low=conditional['null_low'],exact_n_conditional_high=conditional['null_high'],
                            exact_n_conditional_mc_low=conditional['p_mc_low'],exact_n_conditional_mc_high=conditional['p_mc_high'])
                        countrows.append(row)
                        values,freq=np.unique(counts,return_counts=True)
                        for value,n in zip(values,freq):hist.append(dict(method=method,basis=basis,split=split['id'],train_threshold=int(t),test_threshold=int(v),continued=int(value),draws=int(n),probability=float(n/B)))
                if split['kind']=='main':
                    for train_threshold in TH:
                        actual_pool=[r for r in groups if r['basis']==basis and r['split']==split['id'] and r['direction'] and 100*r['train_success']>=train_threshold*r['train_n']]
                        gg=np.array([r['g'] for r in actual_pool],int);nn=np.array([r['test_n'] for r in actual_pool],int)
                        values=null['individual'][:,si,gg]
                        for test_threshold in TH:
                            simulated=np.sum(values*100>=nn[None,:]*test_threshold,axis=1)
                            real=sum(100*r['test_success']>=test_threshold*r['test_n'] for r in actual_pool)
                            fixedpool.append(dict(split=split['id'],basis=basis,method=method,train_threshold=int(train_threshold),test_threshold=int(test_threshold),
                                selected=len(actual_pool),continued=real,**tail(simulated,real),
                                caveat='Secondary validation-only test: actual training-selected names AND directions fixed. Primary full-flow test separately reselects each trial.'))
                    for ci,cohort in enumerate(CORR_COHORTS):
                        for cj,stat in enumerate(['pearson','spearman']):
                            obs=next(r for r in obs_corr if r['basis']==basis and r['split']==split['id'] and r['cohort']==cohort and r['statistic']==stat)
                            corrows.append(dict(**obs,method=method,**tail(null['correlations'][:,si,ci*2+cj],obs['value'])))
                    for g in range(60):
                        obs=next(r for r in groups if r['basis']==basis and r['split']==split['id'] and r['g']==g)
                        values=null['individual'][:,si,g];st=tail(values,obs['test_success'])
                        reverse=tail(-values,-obs['test_success'])['p'] if obs['test_success'] is not None else 1.
                        exact=exact_stratified_tail(a,split,g,obs['direction'],obs['test_success'],method.endswith('regime')) if method.startswith('year_weekday') else None
                        indrows.append(dict(split=split['id'],basis=basis,g=g,ganzhi=obs['ganzhi'],method=method,direction=obs['direction'],
                            selected55=obs['selected55'],test_success=obs['test_success'],test_n=obs['test_n'],test_rate=obs['test_rate'],
                            **st,p_reverse=reverse,p_exact=exact,validation_null_rate=st['null_mean']/obs['test_n'] if st['null_mean'] is not None else None))
            for j,(h,mode) in enumerate(ROLL_SPECS):
                obs=next(r for r in obs_roll if r['basis']==basis and r['horizon']==h and r['policy']==mode)
                n=null['rolling'][:,j,0]
                rates=np.divide(null['rolling'][:,j,1],n*h,out=np.full(len(n),np.nan),where=n>0)
                excess=np.divide(null['rolling'][:,j,3],n*h,out=np.full(len(n),np.nan),where=n>0)
                st=tail(excess,obs['excess_rate']);rate_stats=tail(rates,obs['hit_rate'])
                rollrows.append(dict(**obs,method=method,**st,hit_rate_p=rate_stats['p'],hit_rate_null_mean=rate_stats['null_mean'],
                    hit_rate_null_low=rate_stats['null_low'],hit_rate_null_high=rate_stats['null_high'],
                    null_selected_windows_mean=float(n.mean()),null_selected_windows_low=float(np.quantile(n,.025)),null_selected_windows_high=float(np.quantile(n,.975))))
            for i in range(B):main_draws.append(dict(method=method,basis=basis,draw=i,candidates55=int(null['candidates'][i,0,0]),
                continued55=int(null['continued'][i,0,0,0]),continued60=int(null['continued'][i,0,0,1]),continued65=int(null['continued'][i,0,0,2])))
            print('EVALUATED',basis,method,flush=True)

    # Main54 endpoints per method ->216 total; annual rolling108 per method ->432 total.
    for kind in ['main','annual_rolling']:
        subset=[r for r in countrows if r['kind']==kind]
        adjust(subset);adjust(subset,'fraction_p','fraction_p_holm');adjust(subset,'exact_n_conditional_p','exact_n_conditional_p_holm')
    adjust(corrows)
    adjust(fixedpool);save('fixed_training_pool_validation_tests',fixedpool)
    adjust(indrows,out='p_holm_all1440');adjust(indrows,'p_reverse','p_reverse_holm_all1440')
    for method in METHODS:
        sub=[r for r in indrows if r['method']==method];adjust(sub,out='p_holm_method360')
        adjust(sub,'p_exact','p_exact_holm_method360')
        adjust([r for r in sub if r['split']=='S1'],out='p_holm_method_main120')
        for split in P['splits']:
            for basis in ['oc','cc']:
                cells=[r for r in sub if r['split']==split['id'] and r['basis']==basis]
                adjust(cells,out='p_holm_split_basis60');adjust(cells,'p_exact','p_exact_holm_split_basis60')
    adjust(indrows,'p_exact','p_exact_holm_all720')
    adjust([r for r in indrows if r['split']=='S1'],out='p_holm_main480')
    supported=[r for r in rollrows if r['available_anchor_windows']>0]
    adjust(supported)
    for r in rollrows:
        if not r['available_anchor_windows']:r['p_holm']=None;r['p']=None
    intervals=json.loads((OUT/'group_block_intervals.json').read_text('utf-8'))
    for row in groups:
        if row['kind']!='main':continue
        related=[r for r in indrows if r['basis']==row['basis'] and r['split']==row['split'] and r['g']==row['g']]
        row['best_raw_randomization_p']=min(r['p'] for r in related)
        row['best_global_holm_p']=min(r['p_holm_all1440'] for r in related)
        row['worst_global_holm_p']=max(r['p_holm_all1440'] for r in related)
        for r in related:
            row[r['method']+'_p']=r['p'];row[r['method']+'_holm_p']=r['p_holm_all1440']
        for block in [60,180]:
            rr=next(r for r in intervals if r['basis']==row['basis'] and r['split']==row['split'] and r['g']==row['g'] and r['block']==block)
            for field in ['rate_low','rate_high','matched_excess_low','matched_excess_high']:row[f'block{block}_'+field]=rr[field]
    save('ganzhi_splits',groups);save('null_persistence_tests',countrows);save('null_count_histograms',hist)
    save('correlation_tests',corrows);save('individual_randomization',indrows);save('rolling_null_tests',rollrows);save('null_structure_audit',audits)
    pd.DataFrame(main_draws).to_csv(OUT/'null_main55_draws.csv.gz',index=False,compression='gzip')
    save('main60_details',[r for r in groups if r['split']=='S1'])
    save('main_selected55',[r for r in groups if r['split']=='S1' and r['selected55']])
    save('main_persistent55',[r for r in groups if r['split']=='S1' and r['persistent55']])
    save('main_both60',[r for r in groups if r['split']=='S1' and r['selected60'] and r['continues60']])
    save('main_reversed',[r for r in groups if r['split']=='S1' and r['reversal']])
    # S1 frozen-pool prefix curves. This is a descriptive curve, never a selected best horizon.
    prefixes=json.loads((OUT/'frozen_pool_prefixes.json').read_text('utf-8'));curve=[]
    for basis in ['oc','cc']:
        for k in [1,5,10,15,20,24,30]:
            rr=[r for r in prefixes if r['basis']==basis and r['step']==k and r['complete']]
            curve.append(dict(basis=basis,step=k,groups=len(rr),success=sum(r['success'] for r in rr),n=sum(r['n'] for r in rr),
                pooled_rate=sum(r['success'] for r in rr)/sum(r['n'] for r in rr) if rr else None,
                groups_still55=sum(r['success']*100>=55*r['n'] for r in rr)))
    save('frozen_pool_prefix_curve',curve)
    print('EVALUATION_DONE',flush=True)

if __name__=='__main__':main()
