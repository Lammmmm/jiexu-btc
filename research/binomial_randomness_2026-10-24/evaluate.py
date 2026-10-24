"""Reconcile exact/MC answers and add symmetric distribution diagnostics."""
from core import *

def read(name):return json.loads((OUT/(name+'.json')).read_text('utf-8'))

def main():
    rows,_=data();mc=read('monte_carlo_tests');ex=read('aggregate_exact_tests');comparisons=[];two=[];errors=[]
    for r in mc:
        if not r['null'].startswith('iid'):continue
        key=r['statistic'];match=None
        if key.startswith('full_'):
            for side in ['up','down','either']:
                if key.startswith('full_'+side):
                    h=int(key[len('full_'+side):]);match=next(x for x in ex if x.get('period')=='full' and x.get('side')==side and x.get('threshold')==h and x['basis']==r['basis'] and x['null']==r['null'])
            if key=='full_max':match=next(x for x in ex if 'maximum_rate' in x and x.get('period')=='full' and x['basis']==r['basis'] and x['null']==r['null'])
        if key.startswith('joint'):
            h=int(key[5:]);match=next(x for x in ex if x['family']=='exact_primary68' and x.get('threshold')==h and 'observed_both' in x and x['basis']==r['basis'] and x['null']==r['null'])
        if match:
            pe=match['p'];se=np.sqrt(pe*(1-pe)/r['draws'])
            # Fixed conservative numerical QA tolerance; no simulation is rerun to chase a p-value.
            assert abs(r['p']-pe)<=6*se+6/r['draws'],(key,r['basis'],r['null'],pe,r['p'])
            comparisons.append(dict(basis=r['basis'],null=r['null'],statistic=key,exact_p=pe,mc_p=r['p'],mc_tail_low=r['mc_tail_ci_low'],mc_tail_high=r['mc_tail_ci_high'],
                                    error=r['p']-pe,mc_se_at_exact=se,within_six_sigma_tolerance=True))
    for basis in P['bases']:
        for method in P['ideal_nulls']+P['structured_nulls']:
            with np.load(OUT/f'mc_{basis}_{method}_key_distributions.npz') as z:
                for key in ['full_max','full_sd']:
                    v=z[key];r=next(x for x in mc if x['basis']==basis and x['null']==method and x['statistic']==key);obs=r['observed']
                    lower=(1+int((v<=obs+1e-12).sum()))/(len(v)+1)
                    two.append(dict(basis=basis,null=method,statistic=key,observed=obs,p_lower=lower,p_upper=r['p'],p=min(1,2*min(lower,r['p'])),family='symmetric_distribution20',
                                    note='Equal-tail two-sided diagnostic, no post-hoc choice of low/high tail'))
    adjust(two)
    for basis in P['bases']:
        for null in P['ideal_nulls']:
            for period in ['full','train','validation']:
                rr=[x for x in read('individual_binomial_normal') if x['basis']==basis and x['null']==null and x['period']==period]
                errors.append(dict(basis=basis,null=null,period=period,rows=len(rr),mean_absolute_error_uncorrected=np.mean([abs(x['error_uncorrected']) for x in rr]),
                    mean_absolute_error_cc=np.mean([abs(x['error_cc']) for x in rr]),max_absolute_error_cc=max(x['absolute_error_cc'] for x in rr),
                    max_absolute_error_uncorrected=max(abs(x['error_uncorrected']) for x in rr),normal_cc_changes_raw_005_decision=sum((x['p']<.05)!=(x['normal_cc']<.05) for x in rr)))
    save('exact_vs_monte_carlo',comparisons);save('symmetric_distribution_tests',two);save('normal_approximation_error',errors)
    summary=dict(exact_mc_comparisons=len(comparisons),all_within_prespecified_six_sigma=True,
                 simulations=sum(P['iid_draws_per_basis_null'] if method.startswith('iid') else P['structured_draws_per_basis_null'] for basis in P['bases'] for method in P['ideal_nulls']+P['structured_nulls']),
                 significant_exact_primary=sum(x['family']=='exact_primary68' and x['holm']<.05 for x in ex),
                 significant_mc_primary=sum(x['family']=='mc_primary200' and x['holm']<.05 for x in mc),
                 significant_full_individual=sum(x['family']=='individual_full240' and x['holm']<.05 for x in read('individual_binomial_normal')),
                 significant_conditional_individual=sum(x['holm']<.05 for x in read('individual_conditional')),
                 significant_symmetric_distribution=sum(x['holm']<.05 for x in two))
    save('evaluation_summary',summary);print(json.dumps(summary))

if __name__=='__main__':main()
