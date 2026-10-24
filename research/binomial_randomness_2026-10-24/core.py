"""Independent raw-data parsing and exact finite-distribution calculations."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fractions import Fraction
import hashlib,json,csv,sqlite3,subprocess
import numpy as np
from scipy.stats import binom,binomtest,norm,hypergeom,rankdata
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OUT=ROOT/'results'
P=json.loads((ROOT/'protocol.json').read_text('utf-8'))
TH=P['thresholds_pct'];BINS=np.array(P['distribution_bins'])
DAY=86400000;TZ=timezone(timedelta(hours=8))

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x

def dump(path,x):
    Path(path).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def save(name,rows):
    OUT.mkdir(exist_ok=True)
    dump(OUT/(name+'.json'),rows)
    if isinstance(rows,list) and rows:
        fields=list(dict.fromkeys(k for r in rows for k in r))
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader()
            wr.writerows([{k:json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(dict,list,tuple,np.ndarray)) else clean(v) for k,v in r.items()} for r in rows])
    return rows

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def freeze():
    OUT.mkdir(exist_ok=True)
    if (ROOT/'snapshot.json').exists():return
    con=sqlite3.connect((REPO/'data/market.db').resolve().as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row;con.execute('BEGIN')
    daily=[dict(r) for r in con.execute('select * from daily_candles order by timestamp')]
    metadata=dict(con.execute('select key,value from market_metadata'));con.close()
    cal=sqlite3.connect((REPO/'data/calendar.db').resolve().as_uri()+'?mode=ro',uri=True);cal.row_factory=sqlite3.Row
    calendar=[dict(r) for r in cal.execute('select date,ganzhi_day,ganzhi_index from calendar_days where date between ? and ? order by date',(daily[0]['date'],daily[-1]['date']))];cal.close()
    dump(ROOT/'snapshot.json',dict(daily=daily,calendar=calendar,metadata=metadata,captured_ms=int(datetime.now(timezone.utc).timestamp()*1000)))
    dump(ROOT/'manifest.json',dict(snapshot_sha256=sha(ROOT/'snapshot.json'),protocol_sha256=sha(ROOT/'protocol.json'),git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),source='Read-only transaction on repository Binance UTC+8 daily cache and calendar database'))

def data():
    meta=json.loads((ROOT/'manifest.json').read_text('utf-8'))
    assert sha(ROOT/'snapshot.json')==meta['snapshot_sha256'] and sha(ROOT/'protocol.json')==meta['protocol_sha256']
    s=json.loads((ROOT/'snapshot.json').read_text('utf-8'));cal={r['date']:r for r in s['calendar']}
    cutoff=min(int(s['metadata']['last_sync_ms']),s['captured_ms']);out=[];prev=None
    for raw in s['daily']:
        r=dict(raw);o,h,l,c,v=[Decimal(r[k]) for k in ['open','high','low','close','volume']]
        assert all(x.is_finite() for x in [o,h,l,c,v]) and min(o,h,l,c)>0 and v>=0 and l<=min(o,c)<=max(o,c)<=h
        stamp=int(datetime.fromisoformat(r['date']).replace(tzinfo=TZ).timestamp()*1000)
        assert stamp==r['timestamp'] and stamp<=r['close_time']<stamp+DAY
        if prev:assert stamp-prev['timestamp']==DAY
        reason='unclosed' if stamp+DAY-1>=cutoff else 'source_anomaly' if r['close_time']!=stamp+DAY-1 else 'listing_day' if r['date']==s['metadata']['first_available_date'] else ''
        cr=reason or ('invalid_previous_close' if not prev or prev['close_time']!=prev['timestamp']+DAY-1 else '')
        pc=Decimal(prev['close']) if prev else c
        r.update(g=cal[r['date']]['ganzhi_index'],ganzhi=cal[r['date']]['ganzhi_day'],year=int(r['date'][:4]),weekday=datetime.fromisoformat(r['date']).weekday(),
                 oc_sign=int(c>o)-int(c<o),cc_sign=int(c>pc)-int(c<pc),oc_reason=reason,cc_reason=cr,oc_return=float(c/o-1),cc_return=float(c/pc-1))
        out.append(r);prev=raw
    return out,s

def prepared(rows,basis):
    z=[r for r in rows if not r[basis+'_reason']]
    g=np.array([r['g'] for r in z]);sign=np.array([r[basis+'_sign'] for r in z]);n=[];m=[];up=[];ids=[]
    masks=[np.ones(len(z),bool),np.array([r['date']<=P['training_end'] for r in z]),np.array([r['date']>=P['validation_start'] for r in z])]
    for mask in masks:
        idx=np.flatnonzero(mask);ids.append(idx)
        n.append(np.bincount(g[idx],minlength=60));m.append(np.bincount(g[idx],weights=(sign[idx]!=0).astype(int),minlength=60).astype(int));up.append(np.bincount(g[idx],weights=(sign[idx]>0).astype(int),minlength=60).astype(int))
    assert np.array_equal(n[0],n[1]+n[2]) and np.array_equal(up[0],up[1]+up[2])
    return dict(basis=basis,z=z,g=g,sign=sign,n=np.array(n),m=np.array(m),up=np.array(up),ids=ids,p_actual=float((sign>0).sum()/(sign!=0).sum()),labels={r['g']:r['ganzhi'] for r in z})

def pb_pmf(q):
    pm=np.array([1.])
    for x in q:pm=np.convolve(pm,[1-float(x),float(x)])
    assert abs(pm.sum()-1)<1e-10
    return pm

def pb_tail(q,k):return float(pb_pmf(q)[k:].sum())

def critical(n,h):return (np.asarray(n)*h+99)//100

def qrate(n,m,p,h,side='either'):
    c=critical(n,h);qu=binom.sf(c-1,m,p);qd=binom.cdf(m-c,m,p)
    return qu if side=='up' else qd if side=='down' else qu+qd

def max_tail(n,m,p,r):
    c=np.array([(int(v)*r.numerator+r.denominator-1)//r.denominator for v in n])
    q=binom.sf(c-1,m,p)+binom.cdf(m-c,m,p)
    return float(-np.expm1(np.log1p(-np.minimum(q,1)).sum()))

def conditioned_max_tail(n,m,up,r,p):
    """Condition on exact pooled up count: finite polynomial coefficient, no independent-group assumption."""
    allowed=np.array([1.])
    for nn,mm in zip(n,m):
        k=np.arange(mm+1)
        keep=(k*r.denominator<nn*r.numerator)&((mm-k)*r.denominator<nn*r.numerator)
        allowed=np.convolve(allowed,binom.pmf(k,mm,p)*keep)
    observed=int(up.sum());den=binom.pmf(observed,int(m.sum()),p)
    return float(np.clip(1-allowed[observed]/den,0,1))

def normal_event(m,p,event,cc=True):
    event=np.asarray(event,bool)
    if event.all():return 1.
    if not event.any():return 0.
    idx=np.flatnonzero(event);cuts=np.r_[0,np.flatnonzero(np.diff(idx)>1)+1,len(idx)]
    sd=np.sqrt(m*p*(1-p));prob=0.
    for i in range(len(cuts)-1):
        a,b=idx[cuts[i]],idx[cuts[i+1]-1]
        lo=-np.inf if a==0 else (a-(.5 if cc else 0)-m*p)/sd
        hi=np.inf if b==m else (b+(.5 if cc else 0)-m*p)/sd
        prob+=norm.cdf(hi)-norm.cdf(lo)
    return float(np.clip(prob,0,1))

def exact_normal(k,m,p):
    prob=binom.pmf(np.arange(m+1),m,p);event=prob<=prob[k]*(1+1e-7)
    exact=float(prob[event].sum())
    assert abs(exact-binomtest(k,m,p).pvalue)<1e-10
    return exact,normal_event(m,p,event,False),normal_event(m,p,event,True)

def adjust(rows,field='p',prefix=''):
    groups={}
    for r in rows:
        if r.get(field) is not None:groups.setdefault(r['family'],[]).append(r)
    for group in groups.values():
        ps=[r[field] for r in group]
        for r,h,b in zip(group,multipletests(ps,method='holm')[1],multipletests(ps,method='fdr_bh')[1]):
            r[prefix+'holm']=float(h);r[prefix+'bh']=float(b);r[prefix+'family_size']=len(group)
    return rows

def period_name(j):return ['full','train','validation'][j]

def corr(x,y,mask=None):
    if mask is None:mask=np.ones(x.shape,bool)
    if x.ndim==1:x=x[None,:];y=y[None,:];mask=mask[None,:]
    n=mask.sum(1);nn=np.maximum(n,1)
    xx=(x-(x*mask).sum(1)[:,None]/nn[:,None])*mask
    yy=(y-(y*mask).sum(1)[:,None]/nn[:,None])*mask
    den=np.sqrt((xx*xx).sum(1)*(yy*yy).sum(1))
    return np.divide((xx*yy).sum(1),den,out=np.full(len(x),np.nan),where=(n>=3)&(den>1e-14))

def stats(up,a):
    if up.ndim==2:up=up[None,:,:]
    n=a['n'];m=a['m'];down=m[None,:,:]-up;win=np.maximum(up,down)
    out={}
    for side,val in [('up',up[:,0]),('down',down[:,0]),('either',win[:,0])]:
        for h in TH:out[f'full_{side}{h}']=(val*100>=h*n[0]).sum(1)
    rates=up[:,0]/n[0]
    p=a['p_actual'];mu=m[0]*p;var=m[0]*p*(1-p)
    out['full_max']=(win[:,0]/n[0]).max(1)
    out['full_sd']=rates.std(1,ddof=1)
    out['full_pearson']=((up[:,0]-mu)**2/var).sum(1)
    # Fixed-bin histogram discrepancy: calibrated by simulations, never use a sparse-bin chi-square asymptote.
    if '_bin_expected' not in a:
        exp=np.zeros(len(BINS)-1)
        for nn,mm in zip(n[0],m[0]):exp+=np.histogram(np.arange(mm+1)/nn,BINS,weights=binom.pmf(np.arange(mm+1),mm,p))[0]
        a['_bin_expected']=exp
    exp=a['_bin_expected']
    hist=np.stack([((rates>=lo)&(rates<hi)).sum(1) for lo,hi in zip(BINS[:-1],BINS[1:])],axis=1)
    out['full_hist_chi']=((hist-exp)**2/np.maximum(exp,1e-12)).sum(1)
    tu=up[:,1];td=down[:,1];side=np.sign(tu-td);vk=np.where(side>0,up[:,2],np.where(side<0,down[:,2],0))
    for h in TH:
        sel=(win[:,1]*100>=h*n[1])&(side!=0)
        out[f'train_selected{h}']=sel.sum(1)
        out[f'joint{h}']=(sel&(vk*100>=h*n[2])).sum(1)
        out[f'continued_fraction{h}']=np.divide(out[f'joint{h}'],sel.sum(1),out=np.full(len(up),np.nan),where=sel.sum(1)>0)
    tr=up[:,1]/n[1];va=up[:,2]/n[2]
    out['corr_up_pearson']=corr(tr,va)
    out['corr_up_spearman']=corr(rankdata(tr,axis=1),rankdata(va,axis=1))
    out['corr_frozen_pearson']=corr(win[:,1]/n[1],vk/n[2],side!=0)
    sel=(win[:,1]*100>=55*n[1])&(side!=0)
    out['corr_selected55_pearson']=corr(win[:,1]/n[1],vk/n[2],sel)
    # Exact-rational ranking keys by cross multiplication against common LCM of actual train denominators.
    common=int(np.lcm.reduce(n[1]));score=win[:,1]*(common//n[1])
    order=np.argsort(-score,axis=1,kind='stable')
    for k in P['selection_top_k']:
        ix=order[:,:k];sx=np.take_along_axis(side,ix,axis=1)
        success=np.take_along_axis(vk,ix,axis=1).sum(1)
        denom=n[2][ix].sum(1)
        binary=m[2][ix]
        expected=(binary*np.where(sx>0,p,np.where(sx<0,1-p,0))).sum(1)
        out[f'top{k}_rate']=success/denom
        out[f'top{k}_excess']=(success-expected)/denom
        out[f'top{k}_continued55']=((np.take_along_axis(vk,ix,axis=1)*100>=55*n[2][ix])&(sx!=0)).sum(1)
    return out
