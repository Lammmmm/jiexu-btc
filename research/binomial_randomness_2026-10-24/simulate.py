"""Full reselection pipeline under IID and increasingly structured reference nulls."""
from core import *

KEEP=['full_either55','full_either60','full_max','full_sd','full_pearson','full_hist_chi','joint55','joint60','corr_up_pearson','top10_excess']

class Sampler:
    def __init__(self,a,method,seed):
        self.a=a;self.method=method;self.rng=np.random.default_rng(seed);self.groups=[];self.weeks=[]
        z=a['z'];nonflat=a['sign']!=0
        if method=='fixed_total':
            self.groups=[idx[nonflat[idx]] for idx in a['ids'][1:]]
        if method=='year_weekday':
            keys=sorted({(r['year'],r['weekday']) for r in z})
            self.groups=[np.array([i for i,r in enumerate(z) if nonflat[i] and (r['year'],r['weekday'])==key]) for key in keys]
        if method=='weekly_rotation':
            from datetime import date
            lookup={r['date']:i for i,r in enumerate(z) if nonflat[i]}
            for year in sorted({r['year'] for r in z}):
                weeks=[]
                for r in z:
                    if r['year']!=year or r['weekday']!=0:continue
                    days=[(date.fromisoformat(r['date'])+timedelta(days=j)).isoformat() for j in range(7)]
                    if all(d in lookup and d.startswith(str(year)) for d in days):weeks.append([lookup[d] for d in days])
                if weeks:self.weeks.append(np.array(weeks))
        self.order=[];self.starts=[]
        for idx in a['ids'][1:]:
            order=idx[np.argsort(a['g'][idx],kind='stable')];self.order.append(order);self.starts.append(np.r_[0,np.flatnonzero(np.diff(a['g'][order]))+1])

    def mapping(self,size):
        out=np.tile(np.arange(len(self.a['z'])),(size,1))
        for ids in self.groups:
            out[:,ids]=ids[self.rng.random((size,len(ids))).argsort(axis=1)]
        for weeks in self.weeks:
            offset=self.rng.integers(0,len(weeks),size=size)
            order=(np.arange(len(weeks))[None,:]+offset[:,None])%len(weeks)
            out[:,weeks.ravel()]=weeks[order].reshape(size,-1)
        return out

    def counts(self,maps):
        sign=self.a['sign'][maps];parts=[]
        for order,start in zip(self.order,self.starts):parts.append(np.add.reduceat((sign[:,order]>0).astype(np.int16),start,axis=1))
        return np.stack([parts[0]+parts[1],parts[0],parts[1]],axis=1)

    def audit(self,maps):
        a=self.a;n=len(a['z']);assert np.all(np.sort(maps,axis=1)==np.arange(n)[None,:])
        flat=a['sign']==0;assert np.all(maps[:,flat]==np.flatnonzero(flat))
        years=np.array([r['year'] for r in a['z']]);wd=np.array([r['weekday'] for r in a['z']])
        stage=np.array([r['date']>=P['validation_start'] for r in a['z']])
        assert np.all(stage[maps]==stage)
        if self.method!='fixed_total':assert np.all(years[maps]==years) and np.all(wd[maps]==wd)
        ts=np.array([r['timestamp'] for r in a['z']]);adj=np.diff(ts)==DAY
        retained=np.mean(np.diff(ts[maps],axis=1)[:,adj]==DAY)
        sign=a['sign'][maps];ab=np.abs(np.array([r[a['basis']+'_return'] for r in a['z']]))
        def ac(x):return np.nanmean(corr(x[:,:-1][:,adj],x[:,1:][:,adj]))
        phase=(a['g'][maps]-a['g'][None,:])%60
        return dict(basis=a['basis'],method=self.method,maps_audited=len(maps),exact_sample_sizes_and_flat_dates=True,
                    preserves_stage_totals=True,preserves_year_weekday=self.method!='fixed_total',
                    retained_calendar_neighbor_links=retained,sign_lag1_original=ac(a['sign'][None,:]),sign_lag1_null=ac(sign),
                    abs_return_lag1_original=ac(ab[None,:]),abs_return_lag1_null=ac(ab[maps]),
                    maps_constant_global_60phase=int(np.all(phase==phase[:,0,None],axis=1).sum()))

def run(a,method,seed,B):
    stem=f"{a['basis']}_{method}";dest=OUT/f'mc_{stem}.json'
    stamp=dict(snapshot=sha(ROOT/'snapshot.json'),protocol=sha(ROOT/'protocol.json'),core=sha(ROOT/'core.py'),simulator=sha(Path(__file__)),method=method,basis=a['basis'],seed=seed,draws=B)
    stamp_path=OUT/f'mc_{stem}.stamp.json'
    if dest.exists() and stamp_path.exists() and json.loads(stamp_path.read_text('utf-8'))==stamp:
        print('MC_CACHE_VERIFIED',stem,flush=True);return
    aa=dict(a,p_actual=.5 if method=='iid50' else a['p_actual']);aa.pop('_bin_expected',None)
    obs=stats(a['up'],aa);store={k:[] for k in obs};sampler=None;audits=[]
    if not method.startswith('iid'):sampler=Sampler(a,method,seed)
    rng=np.random.default_rng(seed)
    for begin in range(0,B,512):
        size=min(512,B-begin)
        if sampler:
            maps=sampler.mapping(size)
            if begin==0:audits.append(sampler.audit(maps[:128]))
            # Always check basic stage sign totals; detailed map bijection audited on seeded sample.
            up=sampler.counts(maps)
            assert np.all(up.sum(axis=2)==a['up'].sum(axis=1)[None,:])
        else:
            train=rng.binomial(a['m'][1],aa['p_actual'],size=(size,60));val=rng.binomial(a['m'][2],aa['p_actual'],size=(size,60))
            up=np.stack([train+val,train,val],axis=1)
        result=stats(up,aa)
        for k,v in result.items():store[k].append(v)
        if begin%8192==0:print('MC_PROGRESS',stem,begin+size,'/',B,flush=True)
    arrays={k:np.concatenate(v) for k,v in store.items()};out=[];hist=[]
    for key,v in arrays.items():
        valid=np.isfinite(v);vv=v[valid];value=float(obs[key][0]);hits=int((vv>=value-1e-12).sum()) if np.isfinite(value) else None
        if hits is not None:
            lo,hi=proportion_confint(hits,len(vv),method='wilson');pv=(hits+1)/(len(vv)+1)
        else:lo=hi=pv=None
        family='mc_primary200' if key.startswith('full_') or key.startswith('joint') else 'mc_secondary'
        row=dict(basis=a['basis'],null=method,seed=seed,statistic=key,observed=value,draws=B,valid_draws=len(vv),exceed=hits,p=pv,
                 mc_tail_ci_low=lo,mc_tail_ci_high=hi,null_mean=float(vv.mean()),null_sd=float(vv.std(ddof=1)),
                 null_q025=float(np.quantile(vv,.025)),null_q975=float(np.quantile(vv,.975)),family=family)
        out.append(row)
        if key.startswith(('full_up','full_down','full_either','joint','train_selected')) or key.endswith('_continued55'):
            values,counts=np.unique(vv,return_counts=True)
            hist.extend(dict(basis=a['basis'],null=method,statistic=key,value=float(v),count=int(c)) for v,c in zip(values,counts))
    dump(dest,out);dump(OUT/f'mc_{stem}_histograms.json',hist);dump(stamp_path,stamp)
    if audits:dump(OUT/f'mc_{stem}_audit.json',audits[0])
    np.savez_compressed(OUT/f'mc_{stem}_key_distributions.npz',**{k:arrays[k] for k in KEEP})
    print('MC_DONE',stem,flush=True)

def main():
    rows,_=data()
    for ib,basis in enumerate(P['bases']):
        a=prepared(rows,basis)
        for im,method in enumerate(P['ideal_nulls']+P['structured_nulls']):
            B=P['iid_draws_per_basis_null'] if method.startswith('iid') else P['structured_draws_per_basis_null']
            run(a,method,P['seed']+ib*100000+im*10000,B)
    allrows=[];hists=[];audits=[]
    for basis in P['bases']:
        for method in P['ideal_nulls']+P['structured_nulls']:
            stem=f'{basis}_{method}'
            allrows+=json.loads((OUT/f'mc_{stem}.json').read_text('utf-8'))
            hists+=json.loads((OUT/f'mc_{stem}_histograms.json').read_text('utf-8'))
            if method in P['structured_nulls']:audits.append(json.loads((OUT/f'mc_{stem}_audit.json').read_text('utf-8')))
    adjust(allrows);save('monte_carlo_tests',allrows);save('monte_carlo_count_histograms',hists);save('randomization_structure_audit',audits)
    print('ALL_SIMULATIONS_DONE',flush=True)

if __name__=='__main__':main()
