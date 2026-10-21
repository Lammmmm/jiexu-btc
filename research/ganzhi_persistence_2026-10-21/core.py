"""Independent direction-only research; no previous analysis or production imports."""
import os
for _k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[_k]='1'
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone,timedelta
import json,hashlib
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from statsmodels.stats.proportion import proportion_confint
from statsmodels.stats.multitest import multipletests

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results'
P=json.loads((ROOT/'protocol.json').read_text('utf-8'));TH=np.array(P['thresholds']);DAY=86400000
METHODS=list(P['null_methods']);B=19999

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
    return x

def save(name,x):
    x=clean(x);(OUT/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if isinstance(x,list):
        pd.DataFrame([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in x]).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    return x

def adjust(rows,name='p',out='p_holm'):
    good=[r for r in rows if r.get(name) is not None]
    if good:
        for r,q in zip(good,multipletests([r[name] for r in good],method='holm')[1]):r[out]=float(q)
    return rows

def read_data(source=None):
    if source is None:
        m=json.loads((ROOT/'manifest.json').read_text('utf-8'))
        assert hashlib.sha256((ROOT/'snapshot.json').read_bytes()).hexdigest()==m['source_sha256']
        assert hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest()==m['protocol_sha256']
        source=json.loads((ROOT/'snapshot.json').read_text('utf-8'))
    cal={r['date']:r for r in source['calendar']};cut=int(source['metadata']['last_sync_ms']);rows=[]
    for i,r in enumerate(source['daily']):
        o,h,l,c,v=[Decimal(r[k]) for k in ['open','high','low','close','volume']]
        dt=datetime.fromisoformat(r['date']);stamp=int(dt.replace(tzinfo=timezone(timedelta(hours=8))).timestamp()*1000)
        assert stamp==r['timestamp'] and all(x.is_finite() for x in [o,h,l,c,v]) and min(o,h,l,c)>0 and v>=0
        assert l<=min(o,c)<=max(o,c)<=h and stamp<=r['close_time']<stamp+DAY
        if i:assert stamp==source['daily'][i-1]['timestamp']+DAY
        reason='unclosed' if stamp+DAY-1>=cut else 'source_anomaly' if r['close_time']!=stamp+DAY-1 else 'listing_day' if r['date']==source['metadata']['first_available_date'] else ''
        cc_reason=reason or ('invalid_previous_close' if not i or source['daily'][i-1]['close_time']!=source['daily'][i-1]['timestamp']+DAY-1 else '')
        prev=Decimal(source['daily'][i-1]['close']) if i else c
        oc=c/o-1;cc=c/prev-1
        rows.append(dict(date=r['date'],year=dt.year,weekday=dt.weekday(),g=int(cal[r['date']]['ganzhi_index']),ganzhi=cal[r['date']]['ganzhi_day'],
            timestamp=stamp,close_time=r['close_time'],close=float(c),oc_sign=int(c>o)-int(c<o),cc_sign=int(c>prev)-int(c<prev),
            oc_return=float(oc),cc_return=float(cc),intraday_range=float((h-l)/o),oc_valid=not reason,cc_valid=not cc_reason,
            oc_reason=reason,cc_reason=cc_reason))
    df=pd.DataFrame(rows);regimes=[]
    for i,r in df.iterrows():
        hist=df[(df.oc_valid&df.cc_valid)&(df.close_time<r.timestamp)].close.to_numpy()
        if len(hist)<200:regime='unknown'
        else:
            ret=hist[-1]/hist[-91]-1;ma=hist[-200:].mean()
            regime='bull' if hist[-1]>ma and ret>.10 else 'bear' if hist[-1]<ma and ret<-.10 else 'sideways'
        regimes.append(regime)
    df['regime']=regimes
    return df,source

def all_splits():
    out=[dict(x,kind='main') for x in P['splits']]
    for y in range(2021,2027):
        out.append(dict(id=f'Y{y}',kind='annual_rolling',train_start=f'{y-3}-01-01',train_end=f'{y-1}-12-31',test_start=f'{y}-01-01',test_end='2026-10-20' if y==2026 else f'{y}-12-31'))
    return out

def prepare(df,basis):
    z=df[df[basis+'_valid']].reset_index(drop=True).copy()
    z['sign']=z[basis+'_sign'];z['return']=z[basis+'_return'];z['stratum']=z.year.astype(str)+'_'+z.weekday.astype(str)
    n=len(z);periods=[];lookup={};splitdefs=[]
    for split in all_splits():
        ids=[]
        for stage in ['train','test']:
            key=(split[stage+'_start'],split[stage+'_end'])
            if key not in lookup:
                idx=np.flatnonzero((z.date>=key[0])&(z.date<=key[1]));order=idx[np.argsort(z.g.to_numpy()[idx],kind='stable')]
                gg=z.g.to_numpy()[order];starts=np.r_[0,np.flatnonzero(np.diff(gg))+1]
                assert len(starts)==60
                count=np.bincount(z.g.to_numpy()[idx],minlength=60)
                lookup[key]=len(periods);periods.append(dict(start=key[0],end=key[1],ids=idx,order=order,starts=starts,n=count))
            ids.append(lookup[key])
        splitdefs.append(dict(**split,train_period=ids[0],test_period=ids[1]))
    groups=[np.flatnonzero(z.g.to_numpy()==g) for g in range(60)]
    strata=z.groupby('stratum').indices
    pup=np.zeros(n);pdn=np.zeros(n)
    for idx in strata.values():pup[idx]=np.mean(z.sign.to_numpy()[idx]>0);pdn[idx]=np.mean(z.sign.to_numpy()[idx]<0)
    return dict(df=z,basis=basis,n=n,periods=periods,splits=splitdefs,groups=groups,pup=pup,pdn=pdn)

def group_counts(signs,period):
    if signs.ndim==1:signs=signs[None,:]
    ordered=signs[:,period['order']]
    up=np.add.reduceat((ordered>0).astype(np.int16),period['starts'],axis=1)
    dn=np.add.reduceat((ordered<0).astype(np.int16),period['starts'],axis=1)
    return up,dn

def split_arrays(a,up,dn,split):
    tu,td=up[split['train_period']],dn[split['train_period']];vu,vd=up[split['test_period']],dn[split['test_period']]
    nt=a['periods'][split['train_period']]['n'];nv=a['periods'][split['test_period']]['n']
    side=np.where(tu>td,1,np.where(td>tu,-1,0));tk=np.maximum(tu,td)
    vk=np.where(side>0,vu,np.where(side<0,vd,0));selected=(tk[...,None]*100>=nt[None,:,None]*TH)&(side[...,None]!=0)
    continued=np.sum(selected[:,:,:,None]&(vk[:,:,None,None]*100>=nv[None,:,None,None]*TH),axis=1)
    candidates=selected.sum(axis=1)
    return dict(tu=tu,td=td,vu=vu,vd=vd,nt=nt,nv=nv,side=side,tk=tk,vk=vk,selected=selected,candidates=candidates,continued=continued)

def masked_corr(x,y,mask):
    n=mask.sum(1);den=np.maximum(n,1)
    xx=(x-(x*mask).sum(1)[:,None]/den[:,None])*mask
    yy=(y-(y*mask).sum(1)[:,None]/den[:,None])*mask
    scale=np.sqrt((xx*xx).sum(1)*(yy*yy).sum(1))
    return np.divide((xx*yy).sum(1),scale,out=np.full(len(n),np.nan),where=(n>=3)&(scale>1e-14))

CORR_COHORTS=['raw_up_all','frozen_majority_all','selected55','selected60','selected65']
def correlations(arr):
    tr=arr['tk']/arr['nt'];vr=arr['vk']/arr['nv'];out=[]
    for j,cohort in enumerate(CORR_COHORTS):
        if j==0:x=arr['tu']/arr['nt'];y=arr['vu']/arr['nv'];mask=np.ones(x.shape,bool)
        else:
            x=tr;y=vr;mask=arr['side']!=0 if j==1 else arr['selected'][:,:,j-2]
        out.append(masked_corr(x,y,mask))
        rx=rankdata(np.where(mask,x,2.),axis=1);ry=rankdata(np.where(mask,y,2.),axis=1)
        out.append(masked_corr(rx,ry,mask))
    return np.column_stack(out)

ROLL_SPECS=[(h,mode) for h in [10,20,30] for mode in ['overlap','nonoverlap']]
def rolling_stats(a,signs,details=False):
    if signs.ndim==1:signs=signs[None,:]
    result=np.zeros((len(signs),len(ROLL_SPECS),5));rows=[]
    for g,idx in enumerate(a['groups']):
        values=signs[:,idx];up=np.column_stack([np.zeros(len(signs)),np.cumsum(values>0,axis=1)])
        dn=np.column_stack([np.zeros(len(signs)),np.cumsum(values<0,axis=1)])
        pu=np.r_[0,np.cumsum(a['pup'][idx])];pdn=np.r_[0,np.cumsum(a['pdn'][idx])]
        for j,(h,mode) in enumerate(ROLL_SPECS):
            anchors=np.arange(30,len(idx)-h+1,1 if mode=='overlap' else h)
            if not len(anchors):continue
            tu=up[:,anchors]-up[:,anchors-30];td=dn[:,anchors]-dn[:,anchors-30]
            side=np.where(tu>td,1,-1);selected=np.maximum(tu,td)>=18
            vu=up[:,anchors+h]-up[:,anchors];vd=dn[:,anchors+h]-dn[:,anchors]
            wins=np.where(side>0,vu,vd);expected=np.where(side>0,(pu[anchors+h]-pu[anchors])[None,:],(pdn[anchors+h]-pdn[anchors])[None,:])
            result[:,j,0]+=selected.sum(1);result[:,j,1]+=(wins*selected).sum(1)
            result[:,j,2]+=((wins*100>=60*h)&selected).sum(1)
            result[:,j,3]+=((wins-expected)*selected).sum(1);result[:,j,4]+=len(anchors)
            if details:
                z=a['df']
                for k,anchor in enumerate(anchors):
                    if not selected[0,k]:continue
                    rows.append(dict(basis=a['basis'],g=g,ganzhi=z.ganzhi.iloc[idx[0]],horizon=h,policy=mode,
                        train_first=z.date.iloc[idx[anchor-30]],train_last=z.date.iloc[idx[anchor-1]],test_first=z.date.iloc[idx[anchor]],test_last=z.date.iloc[idx[anchor+h-1]],
                        direction=int(side[0,k]),train_success=int(max(tu[0,k],td[0,k])),train_n=30,test_success=int(wins[0,k]),test_n=h,
                        test_rate=float(wins[0,k]/h),benchmark_rate=float(expected[0,k]/h),excess_rate=float((wins[0,k]-expected[0,k])/h),
                        continues60=bool(wins[0,k]*100>=60*h)))
    return (result,rows) if details else result

def observed(a):
    z=a['df'];sign=z.sign.to_numpy();up=[];dn=[]
    for p in a['periods']:
        u,d=group_counts(sign,p);up.append(u);dn.append(d)
    groups=[];summary=[];corr=[];years=[];regimes=[];bins=[]
    labels=z.groupby('g').ganzhi.first().to_dict()
    for split in a['splits']:
        ar=split_arrays(a,up,dn,split);test=z.iloc[a['periods'][split['test_period']]['ids']]
        nt,nv=ar['nt'],ar['nv'];side=ar['side'][0];tk=ar['tk'][0];vk=ar['vk'][0]
        for g in range(60):
            rate=tk[g]/nt[g];post=vk[g]/nv[g] if side[g] else None
            loc=test[test.g==g];success=(loc.sign.to_numpy()==side[g]).astype(int)
            baseline=float(np.mean(test.sign.to_numpy()==side[g])) if side[g] else None
            expected=[]
            for rr in loc.itertuples():
                pool=test[(test.year==rr.year)&(test.weekday==rr.weekday)&(test.g!=g)]
                expected.append(float(np.mean(pool.sign.to_numpy()==side[g])))
            matched=float(np.mean(expected)) if side[g] else None
            trlo,trhi=proportion_confint(int(tk[g]),int(nt[g]),method='wilson')
            vlo,vhi=proportion_confint(int(vk[g]),int(nv[g]),method='wilson') if side[g] else (None,None)
            # Conservative IID difference interval: 97.5% Wilson intervals in each stage.
            tl,th=proportion_confint(int(tk[g]),int(nt[g]),alpha=.025,method='wilson')
            vl,vh=proportion_confint(int(vk[g]),int(nv[g]),alpha=.025,method='wilson') if side[g] else (None,None)
            row=dict(split=split['id'],kind=split['kind'],basis=a['basis'],g=g,ganzhi=labels[g],direction=int(side[g]),
                train_up=int(ar['tu'][0,g]),train_down=int(ar['td'][0,g]),train_flat=int(nt[g]-ar['tu'][0,g]-ar['td'][0,g]),
                train_success=int(tk[g]) if side[g] else None,train_n=int(nt[g]),train_rate=float(rate) if side[g] else None,
                test_up=int(ar['vu'][0,g]),test_down=int(ar['vd'][0,g]),test_flat=int(nv[g]-ar['vu'][0,g]-ar['vd'][0,g]),
                test_success=int(vk[g]) if side[g] else None,test_n=int(nv[g]),test_rate=post,
                train_wilson_low=float(trlo),train_wilson_high=float(trhi),test_wilson_low=vlo,test_wilson_high=vhi,
                rate_change=post-rate if side[g] else None,difference_iid_low=vl-th if side[g] else None,difference_iid_high=vh-tl if side[g] else None,
                btc_same_direction_rate=baseline,matched_leave_group_rate=matched,matched_excess=post-matched if side[g] else None,
                selected55=bool(ar['selected'][0,g,0]),selected60=bool(ar['selected'][0,g,1]),selected65=bool(ar['selected'][0,g,2]),
                persistent55=bool(side[g] and rate>=.55 and 100*vk[g]>=55*nv[g]),
                marked_reversal=bool(ar['selected'][0,g,0] and 100*vk[g]<=40*nv[g]),
                reversal=bool(ar['selected'][0,g,0] and 100*vk[g]<50*nv[g]))
            for threshold in TH:row['continues'+str(threshold)]=bool(side[g] and 100*vk[g]>=threshold*nv[g])
            groups.append(row)
            if split['kind']=='main' and side[g]:
                for year,sub in loc.groupby('year'):
                    ref=test[(test.year==year)&(test.g!=g)];k=int((sub.sign==side[g]).sum())
                    years.append(dict(split=split['id'],basis=a['basis'],g=g,ganzhi=labels[g],direction=int(side[g]),selected55=row['selected55'],year=int(year),success=k,n=len(sub),rate=k/len(sub),baseline=float((ref.sign==side[g]).mean())))
                for regime,sub in loc.groupby('regime'):
                    ref=test[(test.regime==regime)&(test.g!=g)];k=int((sub.sign==side[g]).sum())
                    regimes.append(dict(split=split['id'],basis=a['basis'],g=g,ganzhi=labels[g],direction=int(side[g]),selected55=row['selected55'],regime=regime,success=k,n=len(sub),rate=k/len(sub),baseline=float((ref.sign==side[g]).mean())))
        for j,t in enumerate(TH):
            mask=ar['selected'][0,:,j]
            for k,v in enumerate(TH):summary.append(dict(split=split['id'],kind=split['kind'],basis=a['basis'],train_threshold=int(t),test_threshold=int(v),selected=int(ar['candidates'][0,j]),continued=int(ar['continued'][0,j,k]),fraction=float(ar['continued'][0,j,k]/ar['candidates'][0,j]) if ar['candidates'][0,j] else None))
        if split['kind']=='main':
            cc=correlations(ar)[0]
            for j,cohort in enumerate(CORR_COHORTS):
                for k,stat in enumerate(['pearson','spearman']):corr.append(dict(split=split['id'],basis=a['basis'],cohort=cohort,statistic=stat,value=float(cc[2*j+k])))
            for lo,hi in [(55,60),(60,65),(65,101)]:
                mask=(tk*100>=lo*nt)&(tk*100<hi*nt)&(side!=0)
                bins.append(dict(split=split['id'],basis=a['basis'],train_bin=f'[{lo},{hi})',groups=int(mask.sum()),
                    train_rate_mean=float((tk/nt)[mask].mean()) if mask.any() else None,
                    test_rate_mean=float((vk/nv)[mask].mean()) if mask.any() else None,
                    test_success=int(vk[mask].sum()),test_n=int(nv[mask].sum()),test_micro_rate=float(vk[mask].sum()/nv[mask].sum()) if mask.any() else None))
    rr,detail=rolling_stats(a,sign,True)
    roll=[]
    for j,(h,mode) in enumerate(ROLL_SPECS):
        n,hits,cont,excess,available=rr[0,j]
        roll.append(dict(basis=a['basis'],horizon=h,policy=mode,available_anchor_windows=int(available),selected_windows=int(n),
            success=int(hits),n=int(n*h),hit_rate=float(hits/(n*h)) if n else None,persistent60_windows=int(cont),excess_rate=float(excess/(n*h)) if n else None,
            max_group_occurrences=max(len(x) for x in a['groups']),status='available' if available else 'insufficient_complete_future_horizon'))
    return dict(groups=groups,summary=summary,correlations=corr,yearly=years,regimes=regimes,training_bins=bins,rolling=roll,rolling_windows=detail)
