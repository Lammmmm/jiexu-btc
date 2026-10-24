"""Finite binomial, Poisson-binomial, conditional and selection calculations."""
from core import *

def main():
    freeze();rows,source=data();save('daily_source_audit',rows)
    observed=[];individual=[];conditional=[];thresholds=[];joint=[];top=[];distribution=[];maxima=[];theory=[];audit=[];splits=[];illustrative=[];annual=[];lowermax=[]
    for basis in P['bases']:
        a=prepared(rows,basis);n,m,up=a['n'],a['m'],a['up'];down=m-up
        for year in sorted({r['year'] for r in a['z']}):
            yr=[r for r in a['z'] if r['year']==year];ss=np.array([r[basis+'_sign'] for r in yr])
            annual.append(dict(basis=basis,year=year,n=len(yr),up=int((ss>0).sum()),down=int((ss<0).sum()),flat=int((ss==0).sum()),up_rate_all=float(np.mean(ss>0))))
        for j in range(3):
            pn=period_name(j);pactual=up[j].sum()/m[j].sum()
            audit.append(dict(basis=basis,period=pn,n=int(n[j].sum()),up=int(up[j].sum()),down=int(down[j].sum()),flat=int((n[j]-m[j]).sum()),
                              up_rate_all=up[j].sum()/n[j].sum(),binary_up_probability=pactual,n_min=int(n[j].min()),n_max=int(n[j].max()),
                              dates_first=a['z'][a['ids'][j][0]]['date'],dates_last=a['z'][a['ids'][j][-1]]['date'],last_closed=a['z'][-1]['date']))
            for g in range(60):
                k=int(up[j,g]);d=int(down[j,g]);nn=int(n[j,g]);mm=int(m[j,g]);major=max(k,d)
                observed.append(dict(basis=basis,period=pn,g=g,ganzhi=a['labels'][g],n=nn,binary_n=mm,up=k,down=d,flat=nn-mm,
                                     up_rate=k/nn,down_rate=d/nn,dominant_direction='up' if k>d else 'down' if d>k else 'tie',dominant_rate=major/nn))
                hpm=hypergeom.pmf(np.arange(mm+1),int(m[j].sum()),int(up[j].sum()),mm)
                hp=float(hpm[hpm<=hpm[k]*(1+1e-7)].sum())
                conditional.append(dict(basis=basis,period=pn,g=g,ganzhi=a['labels'][g],p=hp,family='conditional_individual360',method='two-sided hypergeometric probability-order',
                                        pooled_nonflat=int(m[j].sum()),pooled_up=int(up[j].sum()),group_nonflat=mm,up=k))
                for null,p in [('iid50',.5),('iid_actual',a['p_actual'])]:
                    ex,no,cc=exact_normal(k,mm,p)
                    tails=float(binom.sf(major-1,mm,p)+binom.cdf(mm-major,mm,p)) if major*2>mm else 1.
                    ci=binomtest(k,mm).proportion_ci(method='exact')
                    individual.append(dict(basis=basis,period=pn,g=g,ganzhi=a['labels'][g],null=null,p_reference=p,n=nn,binary_n=mm,up=k,down=d,
                                           p=ex,probability_exact_observed_count=float(binom.pmf(k,mm,p)),normal_uncorrected=no,normal_cc=cc,
                                           error_uncorrected=no-ex,error_cc=cc-ex,absolute_error_cc=abs(cc-ex),
                                           either_direction_current_rate_tail=tails,ci_up_conditional_binary_low=ci.low,ci_up_conditional_binary_high=ci.high,
                                           family='individual_full240' if j==0 else 'individual_stages480'))
                    theory.append(dict(basis=basis,period=pn,g=g,ganzhi=a['labels'][g],null=null,n=nn,binary_n=mm,
                                       expected_up_rate=mm*p/nn,sd_up_rate=np.sqrt(mm*p*(1-p))/nn,
                                       probability_ge55_up=float(qrate(nn,mm,p,55,'up')),probability_ge60_up=float(qrate(nn,mm,p,60,'up')),
                                       probability_ge65_up=float(qrate(nn,mm,p,65,'up')),probability_ge70_up=float(qrate(nn,mm,p,70,'up')),
                                       probability_ge55_either=float(qrate(nn,mm,p,55)),probability_ge60_either=float(qrate(nn,mm,p,60)),
                                       probability_ge65_either=float(qrate(nn,mm,p,65)),probability_ge70_either=float(qrate(nn,mm,p,70))))
            for null,p in [('iid50',.5),('iid_actual',a['p_actual'])]:
                for side,values in [('up',up[j]),('down',down[j]),('either',np.maximum(up[j],down[j]))]:
                    for h in TH:
                        q=qrate(n[j],m[j],p,h,side);actual=int((values*100>=h*n[j]).sum());pm=pb_pmf(q)
                        thresholds.append(dict(basis=basis,period=pn,null=null,p_reference=p,side=side,threshold=h,observed=actual,expected=q.sum(),
                                               expected_count_sd=np.sqrt((q*(1-q)).sum()),p=float(pm[actual:].sum()),count_interval_low=int(np.searchsorted(np.cumsum(pm),.025)),
                                               count_interval_high=int(np.searchsorted(np.cumsum(pm),.975)),prob_any=float(1-pm[0]),
                                               family='exact_primary68' if j==0 else 'exact_secondary',pmf=pm.tolist()))
                r=max(Fraction(int(max(u,d)),int(nn)) for u,d,nn in zip(up[j],down[j],n[j]))
                maxima.append(dict(basis=basis,period=pn,null=null,maximum_rate=float(r),exact_fraction=str(r),p=max_tail(n[j],m[j],p,r),family='exact_primary68' if j==0 else 'exact_secondary'))
                cstrict=np.array([int(nn)*r.numerator//r.denominator+1 for nn in n[j]])
                qstrict=binom.sf(cstrict-1,m[j],p)+binom.cdf(m[j]-cstrict,m[j],p)
                lower=float(np.prod(1-qstrict));upper=max_tail(n[j],m[j],p,r)
                lowermax.append(dict(basis=basis,period=pn,null=null,maximum_rate=float(r),p_lower=lower,p_upper=upper,p=min(1.,2*min(lower,upper)),family='maximum_two_tail12'))
                exp_up=np.zeros(len(BINS)-1);exp_dom=np.zeros_like(exp_up)
                for nn,mm in zip(n[j],m[j]):
                    kk=np.arange(mm+1);pm=binom.pmf(kk,mm,p)
                    exp_up+=np.histogram(kk/nn,BINS,weights=pm)[0]
                    exp_dom+=np.histogram(np.maximum(kk,mm-kk)/nn,BINS,weights=pm)[0]
                for mode,exps,values in [('up',exp_up,up[j]/n[j]),('dominant',exp_dom,np.maximum(up[j],down[j])/n[j])]:
                    actual=np.histogram(values,BINS)[0]
                    for lo,hi,ex,ob in zip(BINS[:-1],BINS[1:],exps,actual):distribution.append(dict(basis=basis,period=pn,null=null,mode=mode,lower=lo,upper=hi,expected=ex,observed=int(ob)))
                mus=m[j]*p/n[j];var=m[j]*p*(1-p)/n[j]**2
                rms=np.sqrt(var.mean()+((mus-mus.mean())**2).sum()/59)
                theory.append(dict(basis=basis,period=pn,g='all',ganzhi='aggregate',null=null,n=int(n[j].sum()),binary_n=int(m[j].sum()),expected_up_rate=mus.mean(),
                                   rms_expected_sample_sd=rms,observed_sample_sd=float((up[j]/n[j]).std(ddof=1))))
            r=max(Fraction(int(max(u,d)),int(nn)) for u,d,nn in zip(up[j],down[j],n[j]))
            maxima.append(dict(basis=basis,period=pn,null='fixed_total_conditional',maximum_rate=float(r),exact_fraction=str(r),
                               p=conditioned_max_tail(n[j],m[j],up[j],r,float(pactual)),family='exact_secondary'))
        side=np.sign(up[1]-down[1]);tk=np.maximum(up[1],down[1]);vk=np.where(side>0,up[2],np.where(side<0,down[2],0))
        for g in range(60):
            splits.append(dict(basis=basis,g=g,ganzhi=a['labels'][g],direction=int(side[g]),train_n=int(n[1,g]),train_up=int(up[1,g]),train_down=int(down[1,g]),
                               train_success=int(tk[g]),train_rate=tk[g]/n[1,g],validation_n=int(n[2,g]),validation_up=int(up[2,g]),validation_down=int(down[2,g]),
                               validation_success=int(vk[g]),validation_frozen_rate=vk[g]/n[2,g] if side[g] else None,
                               **{f'both{h}':bool(side[g] and tk[g]*100>=h*n[1,g] and vk[g]*100>=h*n[2,g]) for h in TH}))
        for null,p in [('iid50',.5),('iid_actual',a['p_actual'])]:
            for h in TH:
                c1=critical(n[1],h);c2=critical(n[2],h)
                q_up=binom.sf(c1-1,m[1],p)*binom.sf(c2-1,m[2],p)
                q_down=binom.cdf(m[1]-c1,m[1],p)*binom.cdf(m[2]-c2,m[2],p)
                q=q_up+q_down;mask=(tk*100>=h*n[1])&(side!=0);ob=int((mask&(vk*100>=h*n[2])).sum())
                pm=pb_pmf(q)
                joint.append(dict(basis=basis,null=null,threshold=h,train_selected=int(mask.sum()),observed_both=ob,expected_both=q.sum(),
                                  expected_up_both=q_up.sum(),expected_down_both=q_down.sum(),p=float(pm[ob:].sum()),
                                  family='exact_primary68',pmf=pm.tolist(),definition='Same train-selected direction in both disjoint stages'))
                qv=np.where(side[mask]>0,binom.sf(c2[mask]-1,m[2,mask],p),binom.cdf(m[2,mask]-c2[mask],m[2,mask],p))
                joint.append(dict(basis=basis,null=null,threshold=h,train_selected=int(mask.sum()),observed_both=ob,expected_both=qv.sum(),
                                  p=pb_tail(qv,ob),family='exact_secondary',definition='Conditional on actual frozen train-selected group names and directions',pmf=pb_pmf(qv).tolist()))
                for g in range(60):theory.append(dict(basis=basis,period='joint',null=null,g=g,ganzhi=a['labels'][g],threshold=h,
                    train_up_tail=float(binom.sf(c1[g]-1,m[1,g],p)),train_down_tail=float(binom.cdf(m[1,g]-c1[g],m[1,g],p)),
                    validation_up_tail=float(binom.sf(c2[g]-1,m[2,g],p)),validation_down_tail=float(binom.cdf(m[2,g]-c2[g],m[2,g],p)),
                    same_direction_both_probability=float(q[g]),both_up_probability=float(q_up[g]),both_down_probability=float(q_down[g])))
            order=sorted(range(60),key=lambda g:(-Fraction(int(tk[g]),int(n[1,g])),g))
            for k in P['selection_top_k']:
                ids=np.array(order[:k]);mu=int(m[2,ids][side[ids]>0].sum());md=int(m[2,ids][side[ids]<0].sum())
                pm=np.convolve(binom.pmf(np.arange(mu+1),mu,p),binom.pmf(np.arange(md+1),md,1-p))
                success=int(vk[ids].sum());nn=int(n[2,ids].sum());expected=mu*p+md*(1-p)
                top.append(dict(basis=basis,null=null,k=k,groups=[a['labels'][g] for g in ids],directions=side[ids].tolist(),
                                validation_success=success,validation_n=nn,validation_rate=success/nn,expected_rate=expected/nn,
                                p=float(pm[success:].sum()),family='exact_secondary',success_pmf=pm.tolist(),
                                expected_rate_sd=float(np.sqrt(mu*p*(1-p)+md*(1-p)*p)/nn)))
        for null,p in [('iid50',.5),('iid_actual',a['p_actual'])]:
            for h in TH:
                c1=int(critical(32,h));c2=int(critical(23,h));one1=float(binom.sf(c1-1,32,p));one2=float(binom.sf(c2-1,23,p))
                du1=float(binom.cdf(32-c1,32,p));du2=float(binom.cdf(23-c2,23,p))
                q=one1*one2+du1*du2
                illustrative.append(dict(basis=basis,null=null,n_train=32,n_validation=23,threshold=h,required_train=c1,required_validation=c2,
                    train_up_probability=one1,validation_up_probability=one2,train_either_probability=one1+du1,validation_either_probability=one2+du2,
                    train_up_and_validation_up_probability=one1*one2,same_direction_both_probability=q,expected_same_direction_both_among60=60*q,
                    label='Illustrative fixed 32/23 only; main results use every actual denominator'))
    individual=adjust(individual);conditional=adjust(conditional);adjust(lowermax)
    aggregate=thresholds+joint+maxima+top;adjust(aggregate)
    for r in individual+conditional+aggregate+lowermax:
        if r.get('p') is not None:r['p']=float(np.clip(r['p'],0,1))
    save('period_totals',audit);save('ganzhi_observed',observed);save('individual_binomial_normal',individual);save('individual_conditional',conditional)
    save('threshold_counts_exact',thresholds);save('cross_period_exact',joint);save('maximum_exact',maxima);save('topk_frozen_exact',top)
    save('theoretical_distribution_bins',distribution);save('theoretical_probabilities',theory);save('split60',splits)
    save('aggregate_exact_tests',aggregate)
    save('illustrative_32_23',illustrative);save('annual_market_totals',annual);save('maximum_two_tail_exact',lowermax)
    # Full rankings retain all sixty, without choosing only statistically attractive cases.
    rankings=[]
    for basis in P['bases']:
        block=[r for r in observed if r['basis']==basis and r['period']=='full']
        for rank,r in enumerate(sorted(block,key=lambda r:(-Fraction(max(r['up'],r['down']),r['n']),r['g'])),1):
            ie=next(x for x in individual if x['basis']==basis and x['period']=='full' and x['g']==r['g'] and x['null']=='iid_actual')
            rankings.append(dict(rank=rank,**r,p_iid_actual_two_sided=ie['p'],holm_full240=ie['holm']))
    save('rankings60',rankings)
    print(json.dumps(clean(dict(totals=audit,primary_exact_family=Counter(r['family'] for r in aggregate) if False else {k:sum(r['family']==k for r in aggregate) for k in set(r['family'] for r in aggregate)})),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
