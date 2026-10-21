"""Full-pipeline, structure-aware null simulations; training selection rerun each draw."""
from core import *
from threadpoolctl import threadpool_limits

class Sampler:
    def __init__(self,a,method,seed):
        self.a=a;self.z=a['df'];self.n=a['n'];self.method=method;self.rng=np.random.default_rng(seed)
        self.strata=[];self.weeks=[];self.blocks=[]
        if method.startswith('year_weekday'):
            keys=['year','weekday']+(['regime'] if method.endswith('regime') else [])
            self.strata=[np.array(v) for v in self.z.groupby(keys).indices.values()]
        index={d:i for i,d in enumerate(self.z.date)}
        for yr,part in self.z.groupby('year'):
            mondays=part.loc[part.weekday==0,'date'].tolist();weeks=[]
            for monday in mondays:
                days=[(pd.Timestamp(monday)+pd.Timedelta(days=j)).strftime('%Y-%m-%d') for j in range(7)]
                if all(d in index and d.startswith(str(yr)) for d in days):weeks.append([index[d] for d in days])
            if weeks:self.weeks.append(np.array(weeks))
            if mondays:
                start=pd.Timestamp(mondays[0]);last=pd.Timestamp(part.date.iloc[-1]);blocks=[]
                while start+pd.Timedelta(days=27)<=last:
                    days=[(start+pd.Timedelta(days=j)).strftime('%Y-%m-%d') for j in range(28)]
                    if all(d in index and d.startswith(str(yr)) for d in days):blocks.append([index[d] for d in days])
                    start+=pd.Timedelta(days=28)
                if blocks:self.blocks.append(np.array(blocks))

    def mapping(self,batch):
        out=np.tile(np.arange(self.n),(batch,1))
        if self.method.startswith('year_weekday'):
            for ids in self.strata:
                order=self.rng.random((batch,len(ids))).argsort(axis=1)
                out[:,ids]=ids[order]
        elif self.method=='week_block28':
            for blocks in self.blocks:
                order=self.rng.random((batch,len(blocks))).argsort(axis=1)
                out[:,blocks.ravel()]=blocks[order].reshape(batch,-1)
        elif self.method=='weekly_rotation':
            for weeks in self.weeks:
                k=len(weeks);offset=self.rng.integers(0,k,size=batch)
                order=(np.arange(k)[None,:]+offset[:,None])%k
                out[:,weeks.ravel()]=weeks[order].reshape(batch,-1)
        else:raise ValueError(self.method)
        return out

    def audit(self,maps):
        assert np.all(np.sort(maps,axis=1)==np.arange(self.n)[None,:])
        for k in ['year','weekday']+(['regime'] if self.method.endswith('regime') else []):
            v=self.z[k].to_numpy();assert np.all(v[maps]==v[None,:]),k
        if self.method=='week_block28':assert np.all((self.z.g.to_numpy()[maps]-self.z.g.to_numpy()[None,:])%4==0)

def vector_result(a,signs):
    up=[];dn=[]
    for period in a['periods']:
        u,d=group_counts(signs,period);up.append(u);dn.append(d)
    candidates=[];continued=[];corr=[];individual=[]
    actual=a['df'].sign.to_numpy()
    for split in a['splits']:
        ar=split_arrays(a,up,dn,split);candidates.append(ar['candidates']);continued.append(ar['continued'])
        if split['kind']=='main':
            corr.append(correlations(ar))
            tu,td=group_counts(actual,a['periods'][split['train_period']]);side=np.sign(tu-td)
            individual.append(np.where(side>0,ar['vu'],np.where(side<0,ar['vd'],0)))
    return dict(candidates=np.stack(candidates,axis=1),continued=np.stack(continued,axis=1),
        correlations=np.stack(corr,axis=1),individual=np.stack(individual,axis=1),rolling=rolling_stats(a,signs))

def mapping_diagnostics(a,maps,method):
    z=a['df'];ts=z.timestamp.to_numpy();adj=np.diff(ts)==DAY
    preserved=np.mean(np.diff(ts[maps],axis=1)[:,adj]==DAY,axis=1)
    phase=(z.g.to_numpy()[maps]-z.g.to_numpy()[None,:])%60
    constant=np.all(phase==phase[:,0,None],axis=1)
    def corr(x):
        left=x[:,:-1][:,adj];right=x[:,1:][:,adj]
        return masked_corr(left,right,np.ones(left.shape,bool))
    sg=z.sign.to_numpy()[maps];ab=abs(z['return'].to_numpy()[maps])
    orig_s=corr(z.sign.to_numpy()[None,:])[0];orig_a=corr(abs(z['return'].to_numpy()[None,:]))[0]
    return dict(basis=a['basis'],method=method,sampled_mappings=len(maps),
        original_neighbor_links_preserved_mean=float(preserved.mean()),constant_global_phase_maps=int(constant.sum()),
        sign_lag1_original=float(orig_s),sign_lag1_null_mean=float(np.nanmean(corr(sg))),
        absolute_return_lag1_original=float(orig_a),absolute_return_lag1_null_mean=float(np.nanmean(corr(ab))),
        exact_year_weekday_totals=True,exact_regime_strata=method.endswith('regime'),
        caveat='28day blocks additionally preserve g modulo4; not an unrestricted null' if method=='week_block28' else 'Conditional reference distribution; not a reconstructed price process')

def run_one(a,method):
    stamp={'source':hashlib.sha256((ROOT/'snapshot.json').read_bytes()).hexdigest(),
        'protocol':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),
        'core':hashlib.sha256((ROOT/'core.py').read_bytes()).hexdigest(),
        'simulator':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'basis':a['basis'],'method':method,'draws':B}
    dest=OUT/f'null_{a["basis"]}_{method}.npz';meta=dest.with_suffix('.stamp.json')
    if dest.exists() and meta.exists() and json.loads(meta.read_text('utf-8'))==stamp:
        print('NULL_CACHE_VERIFIED',a['basis'],method,flush=True);return
    sampler=Sampler(a,method,P['seed']+METHODS.index(method)*10000+(0 if a['basis']=='oc' else 1000))
    store={k:[] for k in ['candidates','continued','correlations','individual','rolling']};audit_maps=[]
    for begin in range(0,B,256):
        count=min(256,B-begin);maps=sampler.mapping(count);sampler.audit(maps)
        if len(audit_maps)<2:audit_maps.append(maps.copy())
        result=vector_result(a,a['df'].sign.to_numpy()[maps])
        for k,v in result.items():store[k].append(v)
        if begin%4096==0:print('NULL_PROGRESS',a['basis'],method,begin+count,'/',B,flush=True)
    arrays={k:np.concatenate(v) for k,v in store.items()}
    np.savez_compressed(dest,**arrays);meta.write_text(json.dumps(stamp,indent=2),encoding='utf-8')
    save(f'null_audit_{a["basis"]}_{method}',mapping_diagnostics(a,np.concatenate(audit_maps),method))
    print('NULL_DONE',a['basis'],method,flush=True)

def main():
    df,_=read_data()
    for basis in ['oc','cc']:
        a=prepare(df,basis)
        for method in METHODS:run_one(a,method)
    print('ALL_NULLS_DONE',flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
