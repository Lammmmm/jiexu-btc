"""Pointwise calendar-block intervals with leave-group benchmark re-estimated in each draw."""
from core import *
from threadpoolctl import threadpool_limits

def calendar_weights(n,reps,block,seed):
    rng=np.random.default_rng(seed);q,r=divmod(n,block);w=np.zeros((reps,n),np.int16)
    for begin in range(0,reps,128):
        count=min(128,reps-begin);starts=rng.integers(0,n,size=(count,q+(r>0)))
        ids=((starts[:,:q,None]+np.arange(block)[None,None,:])%n).reshape(count,-1)
        if r:ids=np.concatenate([ids,(starts[:,-1,None]+np.arange(r)[None,:])%n],axis=1)
        for j,row in enumerate(ids):w[begin+j]=np.bincount(row,minlength=n)
    assert np.all(w.sum(1)==n)
    return w

def intervals(a,split,block,reps):
    z=a['df'];train=z[(z.date>=split['train_start'])&(z.date<=split['train_end'])]
    test=z[(z.date>=split['test_start'])&(z.date<=split['test_end'])].reset_index(drop=True)
    direction=[]
    for g in range(60):
        sg=train.loc[train.g==g,'sign'];direction.append(int((sg>0).sum()>(sg<0).sum())-int((sg>0).sum()<(sg<0).sum()))
    direction=np.array(direction);calendar=pd.date_range(split['test_start'],split['test_end']).strftime('%Y-%m-%d')
    wfull=calendar_weights(len(calendar),reps,block,P['seed']+block+int(split['id'][-1])*100+(0 if a['basis']=='oc' else 10))
    positions=calendar.get_indexer(test.date);w=wfull[:,positions]
    count=np.zeros((reps,60));success=np.zeros_like(count);expected=np.zeros_like(count);fallback=0
    sign=test.sign.to_numpy();groups=test.g.to_numpy()
    for ids in test.groupby(['year','weekday']).indices.values():
        gg=groups[ids];assert len(np.unique(gg))==len(gg)  # lcm(60,7)=420 exceeds a calendar year
        ww=w[:,ids].astype(float);total=ww.sum(1);up=ww@(sign[ids]>0);down=ww@(sign[ids]<0)
        hit=(sign[ids]==direction[gg]).astype(float);wins=ww*hit[None,:]
        numerator=np.where(direction[gg][None,:]>0,up[:,None],down[:,None])-wins
        denominator=total[:,None]-ww
        original=[]
        for g in gg:
            others=ids[groups[ids]!=g];original.append(float(np.mean(sign[others]==direction[g])))
        ref=np.broadcast_to(np.array(original),(reps,len(ids))).copy()
        fallback+=int(np.sum((denominator<=0)&(ww>0)))
        np.divide(numerator,denominator,out=ref,where=denominator>0)
        count[:,gg]+=ww;success[:,gg]+=wins;expected[:,gg]+=ww*ref
    with np.errstate(invalid='ignore',divide='ignore'):
        rates=success/count;excess=(success-expected)/count
    out=[]
    for g in range(60):
        okay=np.isfinite(rates[:,g])
        lo,hi=np.quantile(rates[okay,g],[.025,.975]);el,eh=np.quantile(excess[okay,g],[.025,.975])
        out.append(dict(split=split['id'],basis=a['basis'],g=g,block=block,reps=reps,valid_draws=int(okay.sum()),
            rate_low=lo if direction[g] else None,rate_high=hi if direction[g] else None,
            matched_excess_low=el if direction[g] else None,matched_excess_high=eh if direction[g] else None,
            benchmark_fallback_cells_total=fallback,
            caveat='Pointwise percentile interval conditional on frozen training direction, not simultaneous across60. Benchmark reestimated; empty other-group stratum uses original leave-group probability.'))
    return out

def main():
    df,_=read_data();out=[]
    for basis in ['oc','cc']:
        a=prepare(df,basis)
        for split in a['splits'][:3]:
            for block,reps in [(60,5000),(180,3000)]:
                out+=intervals(a,split,block,reps);print('BOOTSTRAP_DONE',basis,split['id'],block,flush=True)
    save('group_block_intervals',out)

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
