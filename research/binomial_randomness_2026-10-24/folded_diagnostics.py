"""Supplementary folded win-rate dispersion, replaying the SAME seeded null draws."""
from core import *
from simulate import Sampler

def main():
    rows,_=data();out=[];moments=[]
    for ib,basis in enumerate(P['bases']):
        a=prepared(rows,basis);n=a['n'][0];m=a['m'][0]
        observed=np.maximum(a['up'][0],m-a['up'][0])/n
        for im,method in enumerate(P['ideal_nulls']+P['structured_nulls']):
            p=.5 if method=='iid50' else a['p_actual'];mu=[];var=[];hist_expected=np.zeros(len(BINS)-1)
            for nn,mm in zip(n,m):
                k=np.arange(mm+1);pm=binom.pmf(k,mm,p);w=np.maximum(k,mm-k)/nn
                mean=(pm*w).sum();mu.append(mean);var.append((pm*(w-mean)**2).sum());hist_expected+=np.histogram(w,BINS,weights=pm)[0]
            mu=np.array(mu);var=np.array(var)
            rms=np.sqrt(var.mean()+np.sum((mu-mu.mean())**2)/59)
            target_sd=float(observed.std(ddof=1));obs_hist=np.histogram(observed,BINS)[0]
            target_chi=float(np.sum((obs_hist-hist_expected)**2/np.maximum(hist_expected,1e-12)))
            seed=P['seed']+ib*100000+im*10000;B=P['iid_draws_per_basis_null'] if method.startswith('iid') else P['structured_draws_per_basis_null']
            rng=np.random.default_rng(seed);sampler=None if method.startswith('iid') else Sampler(a,method,seed);sds=[];chis=[]
            for begin in range(0,B,512):
                size=min(512,B-begin)
                if sampler:u=sampler.counts(sampler.mapping(size))[:,0]
                else:
                    tu=rng.binomial(a['m'][1],p,size=(size,60));vu=rng.binomial(a['m'][2],p,size=(size,60));u=tu+vu
                folded=np.maximum(u,m-u)/n;sds.append(folded.std(1,ddof=1))
                hist=np.stack([((folded>=lo)&(folded<hi)).sum(1) for lo,hi in zip(BINS[:-1],BINS[1:])],axis=1)
                chis.append(np.sum((hist-hist_expected)**2/np.maximum(hist_expected,1e-12),axis=1))
            sd=np.concatenate(sds);chi=np.concatenate(chis)
            for key,values,target in [('dominant_sd',sd,target_sd),('dominant_hist_chi',chi,target_chi)]:
                upper=(1+int((values>=target-1e-12).sum()))/(B+1);lower=(1+int((values<=target+1e-12).sum()))/(B+1)
                out.append(dict(basis=basis,null=method,statistic=key,observed=target,null_mean=float(values.mean()),null_q025=float(np.quantile(values,.025)),null_q975=float(np.quantile(values,.975)),
                                p_upper=upper,p_lower=lower,p=min(1,2*min(lower,upper)) if key=='dominant_sd' else upper,family='folded_distribution20',draws_replayed=B))
            moments.append(dict(basis=basis,null=method,observed_mean=observed.mean(),observed_sd=target_sd,iid_expected_mean=mu.mean(),iid_rms_expected_sd=rms,
                                 caution='IID moment formula is not a moment claim for structured conditional nulls; their moments come from replayed draws'))
            np.savez_compressed(OUT/f'folded_{basis}_{method}.npz',dominant_sd=sd,dominant_hist_chi=chi)
            print('FOLDED_REPLAY_DONE',basis,method,flush=True)
    adjust(out);save('dominant_distribution_tests',out);save('dominant_distribution_moments',moments)

if __name__=='__main__':main()
