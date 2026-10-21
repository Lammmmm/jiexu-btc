"""Research-only evaluation of a causal >=55% Ganzhi direction gate.

The locked parent forecasts are reused, not fitted again on known test outcomes.
All inference preserves the original calendar and resamples the gate with losses.
"""
import os
for _name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[_name]='1'
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
import sys, json, hashlib
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'ganzhi_volatility_2026-10-21'
sys.path.insert(0,str(BASE))
import engine as parent
from evaluate import metrics,tie_top
from association import cluster_interval,orthogonal
from risk_diagnostics import weighted_ranking
P=json.loads((ROOT/'protocol.json').read_text('utf-8'))
OUT=ROOT/'results'
TARGETS=parent.TARGETS; CONT=parent.CONT; BIN=parent.BIN; MODELS=parent.MODELS

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x

def save(name,x,csv=True):
    x=clean(x);OUT.mkdir(exist_ok=True)
    (OUT/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if csv and isinstance(x,list):
        flat=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in x]
        pd.DataFrame(flat).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    return x

def verify_inputs():
    m=json.loads((ROOT/'manifest.json').read_text('utf-8'))
    assert hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest()==m['protocol_sha256']
    for f,h in m['inputs'].items():assert hashlib.sha256((BASE/f).read_bytes()).hexdigest()==h,f
    return m

def direction_arrays(d):
    rows=d['source']['daily'];oc=[];cc=[]
    for i,r in enumerate(rows):
        c=Decimal(r['close']);o=Decimal(r['open'])
        prev=Decimal(rows[i-1]['close']) if i else c
        oc.append(int(c>o)-int(c<o));cc.append(int(c>prev)-int(c<prev))
    return {'oc':np.array(oc),'cc':np.array(cc)}

def export_candles(d):
    rows=[]
    for i,r in enumerate(d['source']['daily']):
        if not d['valid_oc'][i]:continue
        o,h,l,c=[Decimal(r[k]) for k in ['open','high','low','close']]
        prev=Decimal(d['source']['daily'][i-1]['close'])
        rows.append(dict(date=r['date'],timezone='Asia/Shanghai UTC+8',g=int(d['g'][i]),ganzhi=d['labels'][i],
            open=r['open'],high=r['high'],low=r['low'],close=r['close'],volume=r['volume'],
            timestamp=r['timestamp'],close_time=r['close_time'],
            oc_return=str(c/o-1),cc_return=str(c/prev-1) if d['valid_cc'][i] else None,
            intraday_range=str((h-l)/o),valid_oc=True,valid_cc=bool(d['valid_cc'][i])))
    pd.DataFrame(rows).to_csv(OUT/'daily_ganzhi_candles_2017.csv',index=False,encoding='utf-8-sig')

def choice(n,up,down):
    # Integer comparison: exactly 55%, no rounded display probabilities.
    if n and 100*up>=55*n:return 1
    if n and 100*down>=55*n:return -1
    return 0

def selections(d,signs=None):
    signs=direction_arrays(d) if signs is None else signs
    records=[]
    for basis in ['oc','cc']:
        valid=d['valid_'+basis];sg=signs[basis]
        for i,date in enumerate(d['dates']):
            if date<P['extended_start'] or not d['valid'][i]:continue
            hist=np.flatnonzero(valid&(d['ct']<d['ts'][i]))
            same=hist[d['g'][hist]==d['g'][i]]
            n=len(same);up=int(np.sum(sg[same]>0));down=int(np.sum(sg[same]<0));pick=choice(n,up,down)
            global_up=int(np.sum(sg[hist]>0));global_down=int(np.sum(sg[hist]<0))
            overall_pick=1 if global_up>=global_down else -1
            records.append(dict(date=date,basis=basis,g=int(d['g'][i]),ganzhi=d['labels'][i],
                history_n=n,history_up=up,history_down=down,history_flat=n-up-down,
                up_rate=up/n,down_rate=down/n,selected=bool(pick),side=pick,
                preferred_rate=max(up,down)/n,decision=int(d['ts'][i]),
                last_history_close=int(d['ct'][hist[-1]]),last_group_date=d['dates'][same[-1]],
                actual_side=int(sg[i]),correct=bool(pick and sg[i]==pick),
                btc_majority_side=overall_pick,btc_majority_correct=bool(sg[i]==overall_pick)))
    return pd.DataFrame(records)

def fixed_and_current(d,signs):
    records=[]
    for cutoff,name in [('2023-01-01','frozen_2022'),('2026-10-21','current_descriptive_only')]:
        i=int(np.flatnonzero(d['dates']==cutoff)[0])
        for basis in ['oc','cc']:
            hist=np.flatnonzero(d['valid_'+basis]&(d['ct']<d['ts'][i]))
            for g in range(60):
                same=hist[d['g'][hist]==g];s=signs[basis][same];n=len(same)
                up=int(np.sum(s>0));down=int(np.sum(s<0));pick=choice(n,up,down)
                lo,hi=__import__('statsmodels.stats.proportion',fromlist=['proportion_confint']).proportion_confint(max(up,down),n,method='wilson')
                records.append(dict(pool=name,cutoff=cutoff,basis=basis,g=g,ganzhi=d['labels'][same[0]],
                    n=n,up=up,down=down,flat=n-up-down,up_rate=up/n,down_rate=down/n,
                    preferred_rate=max(up,down)/n,side=pick,selected=bool(pick),
                    preferred_wilson_low=float(lo),preferred_wilson_high=float(hi),
                    caveat='Pointwise IID interval, post-selection/multiple-testing not adjusted; not proof of an edge'))
    return records

def masked_bootstrap(values,mask,block,reps,seed):
    """Resample contiguous original calendar blocks, including zero-weight days."""
    values=np.asarray(values,float)
    if values.ndim==1:values=values[:,None]
    mask=np.asarray(mask,float);n=len(mask)
    assert len(values)==n and np.isfinite(values).all()
    payload=np.column_stack([values*mask[:,None],mask])
    cs=np.vstack([np.zeros(payload.shape[1]),np.cumsum(np.concatenate([payload,payload]),axis=0)])
    starts=np.arange(n);pool=cs[starts+block]-cs[starts]
    q,r=divmod(n,block);tail=cs[starts+r]-cs[starts] if r else None
    rng=np.random.default_rng(seed+block);draws=[]
    for begin in range(0,reps,128):
        k=min(128,reps-begin);total=pool[rng.integers(0,n,size=(k,q))].sum(1)
        if r:total+=tail[rng.integers(0,n,size=k)]
        with np.errstate(divide='ignore',invalid='ignore'):
            draws.append(total[:,:-1]/total[:,-1,None])
    return np.concatenate(draws)

def adjust(rows):
    if rows:
        hp=multipletests([r.get('p',1.) for r in rows],method='holm')[1]
        for r,p in zip(rows,hp):r['p_holm']=float(p)
    return rows

def selection_mask(sel,basis,dates,side=0):
    rows=sel[sel.basis==basis].set_index('date').loc[dates]
    out=rows.selected.to_numpy(bool)
    if side:out&=rows.side.to_numpy()==side
    return out

def frames_for(pred,target,start=P['test_start']):
    z=pred[(pred.target==target)&(pred.date>=start)]
    frames={m:g.sort_values('date').reset_index(drop=True) for m,g in z.groupby('model')}
    dates=frames['A'].date.to_numpy()
    for m,x in frames.items():
        assert np.array_equal(x.date.to_numpy(),dates),m
        np.testing.assert_array_equal(x.actual.to_numpy(),frames['A'].actual.to_numpy())
    return frames,dates

def loss_columns(pred,start):
    cols=[];meta=[];cal=None
    for t in TARGETS:
        fr,dates=frames_for(pred,t,start)
        if cal is None:cal=dates
        assert np.array_equal(dates,cal)
        y=fr['A'].actual.to_numpy()
        for ref,cand in P['pairs']:
            a=fr[ref].pred.to_numpy();b=fr[cand].pred.to_numpy()
            for metric in ['se','ae'] if t in CONT else ['brier','logloss']:
                def l(p):
                    if metric=='ae':return abs(y-p)
                    if metric=='logloss':
                        p=np.clip(p,1e-5,1-1e-5);return -(y*np.log(p)+(1-y)*np.log1p(-p))
                    return (y-p)**2
                cols.extend([l(a),l(b)])
                meta.append(dict(target=t,reference=ref,candidate=cand,metric=metric))
    return np.column_stack(cols),meta,cal

def paired(pred,sel,start,block,reps,side=0):
    values,meta,dates=loss_columns(pred,start);rows=[]
    for bi,basis in enumerate(['oc','cc']):
        mask=selection_mask(sel,basis,dates,side)
        if not mask.any():continue
        boot=masked_bootstrap(values,mask,block,reps,P['seed']+bi)
        observed=values[mask].mean(0)
        for j,m in enumerate(meta):
            ref,cand=observed[j*2:j*2+2];delta=ref-cand
            diff=boot[:,j*2]-boot[:,j*2+1];diff=diff[np.isfinite(diff)]
            lo,hi=np.quantile(diff,[.025,.975]);p=(1+np.sum(abs(diff-delta)>=abs(delta)))/(len(diff)+1)
            skill=1-boot[:,j*2+1]/boot[:,j*2]
            slo,shi=np.nanquantile(skill,[.025,.975])
            rmse=1-np.sqrt(cand/ref) if m['metric']=='se' else None
            rows.append(dict(**m,basis=basis,side=side,n=int(mask.sum()),calendar_n=len(mask),block=block,reps=reps,
                ref_mean=ref,candidate_mean=cand,delta=delta,ci_low=lo,ci_high=hi,p=p,
                relative_improvement=1-cand/ref,relative_ci_low=slo,relative_ci_high=shi,rmse_improvement=rmse))
    return adjust(rows)

def comparison(pred,sel,start=P['test_start'],subgroup=None):
    result=[]
    for basis in ['oc','cc']:
        ss=sel[(sel.basis==basis)&sel.selected&(sel.date>=start)]
        if subgroup=='side':groups=[(str(k),g) for k,g in ss.groupby('side')]
        elif subgroup=='year':groups=[(k,g) for k,g in ss.groupby(ss.date.str[:4])]
        elif subgroup=='regime':groups=[(k,g) for k,g in ss.groupby('regime')]
        else:groups=[('all',ss)]
        for group,s in groups:
            for (t,m),x in pred[(pred.date>=start)&pred.date.isin(s.date)].groupby(['target','model']):
                result.append(dict(basis=basis,subgroup=group,target=t,model=m,**metrics(x,t)))
    return result

def calendar_regimes(d):
    out={}
    for i,date in enumerate(d['dates']):
        hist=np.flatnonzero(d['valid']&(d['ct']<d['ts'][i]));cl=d['close'][hist]
        if len(cl)<200:out[date]='unknown';continue
        drift=cl[-1]/cl[-31]-1
        out[date]='bull' if cl[-1]>=cl[-200:].mean() and drift>=.20 else 'bear' if cl[-1]<cl[-200:].mean() and drift<=-.20 else 'sideways'
    return out

def direction_results(sel):
    out=[]
    for basis in ['oc','cc']:
        ss=sel[(sel.basis==basis)&(sel.date>=P['test_start'])].sort_values('date')
        for side in [0,1,-1]:
            mask=ss.selected.to_numpy()&((ss.side.to_numpy()==side) if side else True)
            if not mask.any():continue
            win=ss.correct.to_numpy(float);base=ss.btc_majority_correct.to_numpy(float)
            boot=masked_bootstrap(np.column_stack([win,base,win-base]),mask,60,20000,P['seed']+81)
            lo,hi=np.quantile(boot[:,0],[.025,.975]);b0,b1=np.quantile(boot[:,2],[.025,.975])
            delta=float((win-base)[mask].mean())
            pv=(1+np.sum(abs(boot[:,2]-delta)>=abs(delta)))/(len(boot)+1)
            out.append(dict(basis=basis,side=side,n=int(mask.sum()),wins=int(win[mask].sum()),
                actual_win_rate=float(win[mask].mean()),forecast_rate=float(ss.preferred_rate.to_numpy()[mask].mean()),
                ci_low=lo,ci_high=hi,btc_majority_win_rate=float(base[mask].mean()),
                excess_hit_rate=delta,excess_low=b0,excess_high=b1,p=pv))
    adjust(out);save('direction_validation',out)
    yr=[]
    for (basis,year),ss in sel[(sel.date>=P['test_start'])&sel.selected].groupby(['basis',sel.loc[(sel.date>=P['test_start'])&sel.selected,'date'].str[:4]]):
        for side in [0,1,-1]:
            s=ss if side==0 else ss[ss.side==side]
            if len(s):yr.append(dict(basis=basis,year=year,side=side,n=len(s),wins=int(s.correct.sum()),
                actual_win_rate=float(s.correct.mean()),forecast_rate=float(s.preferred_rate.mean()),btc_majority_win_rate=float(s.btc_majority_correct.mean())))
    save('direction_yearly',yr)

def subset_diagnostics(pred,sel):
    rows=[];elev=[];cal=[];online=[]
    for basis in ['oc','cc']:
        selected=set(sel[(sel.basis==basis)&sel.selected].date)
        for t in TARGETS:
            fr,dates=frames_for(pred,t);mask=np.isin(dates,list(selected));y=fr['A'].actual.to_numpy()
            for name,mm in [('selected',mask),('not_selected',~mask),('all',np.ones(len(mask),bool))]:
                rows.append(dict(basis=basis,target=t,group=name,n=int(mm.sum()),mean=float(y[mm].mean()),
                    median=float(np.median(y[mm])),events=int(y[mm].sum()) if t in BIN else None))
            for ref,cand in [('C','E'),('F','G'),('F_retro','G_retro')]:
                a=fr[ref].pred.to_numpy();b=fr[cand].pred.to_numpy()
                high=mask&((b-a>=.05) if t in BIN else (b>=a*1.2))
                elev.append(dict(basis=basis,target=t,reference=ref,candidate=cand,n=int(high.sum()),
                    actual_mean=float(y[high].mean()) if high.any() else None,
                    baseline_mean=float(a[high].mean()) if high.any() else None,
                    group_forecast_mean=float(b[high].mean()) if high.any() else None))
        for (t,m),x in pred.groupby(['target','model']):
            x=x.sort_values('date');s=x[x.date.isin(selected)].copy();main=s[s.date>=P['test_start']]
            if t in BIN:
                pp=main.pred.to_numpy();yy=main.actual.to_numpy();bins=np.minimum((pp*10).astype(int),9)
                for b in range(10):
                    use=bins==b
                    if use.any():cal.append(dict(basis=basis,target=t,model=m,bin=b,n=int(use.sum()),events=int(yy[use].sum()),predicted=float(pp[use].mean()),observed=float(yy[use].mean())))
            dates=pd.to_datetime(s.date);series=pd.Series(s.pred.to_numpy(),index=dates)
            for q in [.1,.2]:
                cut=series.rolling('365D',closed='left',min_periods=60).quantile(1-q).to_numpy()
                use=(s.date>=P['test_start']).to_numpy()&np.isfinite(cut);alarm=use&(s.pred.to_numpy()>cut);yy=s.actual.to_numpy()
                online.append(dict(basis=basis,target=t,model=m,nominal=q,eligible_n=int(use.sum()),alert_n=int(alarm.sum()),
                    actual_alert_fraction=float(alarm.sum()/use.sum()) if use.any() else None,
                    actual_mean_alert=float(yy[alarm].mean()) if alarm.any() else None,
                    actual_mean_eligible=float(yy[use].mean()) if use.any() else None))
    save('selected_vs_ordinary',rows);save('elevated_predictions',elev);save('calibration',cal);save('online_alerts',online)

def group_results(pred,sel):
    out=[];wide=[]
    for basis in ['oc','cc']:
        ss=sel[(sel.basis==basis)&(sel.date>=P['test_start'])]
        for g in range(60):
            allg=ss[ss.g==g];sg=allg[allg.selected]
            wide.append(dict(basis=basis,g=g,ganzhi=allg.ganzhi.iloc[0],eligible_n=len(allg),selected_n=len(sg),
                long_n=int((sg.side==1).sum()),short_n=int((sg.side==-1).sum()),
                min_training_n=int(allg.history_n.min()),max_training_n=int(allg.history_n.max()),
                actual_win_rate=float(sg.correct.mean()) if len(sg) else None,
                avg_forecast_rate=float(sg.preferred_rate.mean()) if len(sg) else None))
        for t in TARGETS:
            fr,dates=frames_for(pred,t);s=ss.set_index('date').loc[dates]
            for ref,cand in [('C','E'),('F','G')]:
                a=fr[ref];b=fr[cand];diff=(a.actual-a.pred)**2-(b.actual-b.pred)**2
                for g in range(60):
                    mask=s.selected.to_numpy()&(s.g.to_numpy()==g)
                    if not mask.any():continue
                    vals=diff[mask].to_numpy();yrs=a.loc[mask,'date'].str[:4].to_numpy()
                    mu,lo,hi,p,keff=cluster_interval(vals,yrs)
                    by={yr:float(vals[yrs==yr].mean()) for yr in np.unique(yrs)}
                    yy=a.actual.to_numpy()[mask]
                    out.append(dict(basis=basis,target=t,reference=ref,candidate=cand,g=g,ganzhi=s.loc[mask,'ganzhi'].iloc[0],
                        n=int(mask.sum()),events=int(yy.sum()) if t in BIN else None,actual_mean=float(yy.mean()),
                        loss_improvement=mu,ci_low=lo,ci_high=hi,p=p,effective_years=keff,
                        positive_years=sum(v>0 for v in by.values()),yearly_improvements=by))
    adjust(out)
    for r in out:r['passes_validation']=bool(r['p_holm']<.05 and r['loss_improvement']>0 and r['n']>=15 and r['positive_years']>=3 and (r['events'] is None or r['events']>=5))
    save('ganzhi_selected_counts',wide);save('ganzhi_selected_oos',out)

def ranking_intervals(pred,sel):
    records=[]
    for bi,basis in enumerate(['oc','cc']):
        for t in BIN:
            fr,dates=frames_for(pred,t);mask=selection_mask(sel,basis,dates)
            n=len(mask);rng=np.random.default_rng(P['seed']+bi);q,r=divmod(n,60)
            weights=np.zeros((2000,n),np.int16)
            for j in range(len(weights)):
                starts=rng.integers(0,n,size=q+(r>0));ids=[(st+np.arange(60))%n for st in starts[:q]]
                if r:ids.append((starts[-1]+np.arange(r))%n)
                weights[j]=np.bincount(np.concatenate(ids),minlength=n)
            w=weights[:,mask];y=fr['A'].actual.to_numpy()[mask]
            for ref,cand in [('C','E'),('F','G')]:
                aa=fr[ref][mask];bb=fr[cand][mask]
                ar,ap=weighted_ranking(y,aa.pred.to_numpy(),w);br,bp=weighted_ranking(y,bb.pred.to_numpy(),w)
                ma=metrics(aa,t);mb=metrics(bb,t)
                for label,draws in [('roc_auc',br-ar),('pr_auc_ap',bp-ap)]:
                    point=mb[label]-ma[label];draws=draws[np.isfinite(draws)];lo,hi=np.quantile(draws,[.025,.975])
                    records.append(dict(basis=basis,target=t,reference=ref,candidate=cand,metric=label,n=int(mask.sum()),
                        delta=point,ci_low=lo,ci_high=hi,p=float((1+np.sum(abs(draws-point)>=abs(point)))/(1+len(draws))),reps=len(draws)))
    save('ranking_intervals',adjust(records))

def selected_permutation(d,sel):
    features=np.load(BASE/'results/causal_features.npz');records=[]
    for bi,basis in enumerate(['oc','cc']):
        ss=sel[(sel.basis==basis)&(sel.date>=P['test_start'])].set_index('date')
        for k,t in enumerate(TARGETS):
            ids=np.flatnonzero(d['valid']&(d['dates']>=P['test_start']));dates=d['dates'][ids]
            mask=ss.loc[dates,'selected'].to_numpy();years=np.array([v[:4] for v in dates]);state=features[t][ids]
            controls=np.column_stack([np.ones(len(ids)),state,np.eye(7)[d['weekday'][ids]][:,1:],d['macro_retro'][ids],
                np.column_stack([(years==yr).astype(float) for yr in sorted(set(years))[1:]])])
            q=orthogonal(controls);yy=d['y'][ids,k];res=yy-q@(q.T@yy)
            gs=d['g'][ids][mask];present=np.unique(gs);indicator=np.column_stack([gs==g for g in present]).astype(float)
            n=indicator.sum(0);sample=res[mask]-res[mask].mean()
            obs=float(np.sum((indicator.T@sample)**2/n)/np.sum(sample**2))
            rng=np.random.default_rng(P['seed']+bi*100+k);yearids=[np.flatnonzero(years==yr) for yr in sorted(set(years))]
            exceed=0;draws=[]
            for begin in range(0,4999,128):
                count=min(128,4999-begin);permuted=np.empty((len(ids),count))
                for pos in yearids:
                    off=rng.integers(0,len(pos),size=count);permuted[pos]=res[pos][(np.arange(len(pos))[:,None]+off)%len(pos)]
                v=permuted[mask];v-=v.mean(0)
                scores=np.sum((indicator.T@v)**2/n[:,None],axis=0)/np.sum(v*v,axis=0)
                exceed+=int(np.sum(scores>=obs));draws.extend(scores.tolist())
            records.append(dict(basis=basis,target=t,n=int(mask.sum()),groups=len(present),partial_group_fraction=obs,
                null95=float(np.quantile(draws,.95)),p=(exceed+1)/5000,permutations=4999,
                caveat='Exploratory fixed-selected-path conditional association; not exact adaptive-selection null, not a forecast-validation test'))
            print('PERMUTATION',basis,t,flush=True)
    save('conditional_permutation',adjust(records))

def audit_predictions(pred,d):
    unique=pred[['date','decision','last_train_close']].drop_duplicates()
    assert (unique.last_train_close<unique.decision).all()
    for (t,m),x in pred.groupby(['target','model']):
        assert len(x)==2119
        ids=np.searchsorted(d['dates'],x.date.to_numpy());np.testing.assert_allclose(x.actual,d['y'][ids,TARGETS.index(t)],atol=1e-15)
        assert np.all(x.g.to_numpy()==d['g'][ids])
    return len(unique)

def main():
    verify_inputs();d=parent.read_source();signs=direction_arrays(d);sel=selections(d,signs)
    export_candles(d)
    sel['regime']=sel.date.map(calendar_regimes(d))
    save('selection_daily',sel.to_dict('records'))
    pools=fixed_and_current(d,signs);save('ganzhi_direction_pools',pools)
    pred=pd.read_csv(BASE/'results/predictions.csv.gz',low_memory=False);audit_predictions(pred,d)
    summary=[]
    for basis in ['oc','cc']:
        for start in [P['extended_start'],P['test_start']]:
            z=sel[(sel.basis==basis)&(sel.date>=start)];s=z[z.selected]
            summary.append(dict(basis=basis,start=start,total_n=len(z),selected_n=len(s),fraction=len(s)/len(z),
                selected_groups=int(s.g.nunique()),long_n=int((s.side==1).sum()),short_n=int((s.side==-1).sum()),
                training_n_min=int(s.history_n.min()),training_n_max=int(s.history_n.max())))
    save('selection_summary',summary);print('SELECTION',json.dumps(summary),flush=True)
    save('model_comparison',comparison(pred,sel));save('model_comparison_extended',comparison(pred,sel,P['extended_start']))
    save('yearly_models',comparison(pred,sel,subgroup='year'));save('regime_models',comparison(pred,sel,subgroup='regime'))
    save('long_short_models',comparison(pred,sel,subgroup='side'))
    for block,reps in [(60,20000),(14,10000),(180,10000)]:
        save('paired_'+str(block),paired(pred,sel,P['test_start'],block,reps));print('PAIRED',block,flush=True)
    save('paired_extended',paired(pred,sel,P['extended_start'],60,10000))
    sided=[]
    for side in [1,-1]:sided+=paired(pred,sel,P['test_start'],60,10000,side=side)
    save('paired_long_short',adjust(sided))
    frozen=sel.copy()
    for basis in ['oc','cc']:
        rules={r['g']:r['side'] for r in pools if r['pool']=='frozen_2022' and r['basis']==basis}
        use=frozen.basis==basis;frozen.loc[use,'side']=frozen.loc[use,'g'].map(rules)
        frozen.loc[use,'selected']=frozen.loc[use,'side']!=0
    save('frozen_model_comparison',comparison(pred,frozen));save('frozen_paired',paired(pred,frozen,P['test_start'],60,10000))
    robust=[];rp=[]
    for variant in ['cap99','omit_2020','omit_2021','omit_2022']:
        v=pd.read_csv(BASE/('results/predictions_'+variant+'.csv.gz'),low_memory=False);audit_predictions(v,d)
        robust.extend([dict(variant=variant,**r) for r in comparison(v,sel)])
        rp.extend([dict(variant=variant,**r) for r in paired(v,sel,P['test_start'],60,10000)])
        print('ROBUSTNESS',variant,flush=True)
    save('robustness_comparison',robust);save('robustness_paired',adjust(rp))
    direction_results(sel);subset_diagnostics(pred,sel);group_results(pred,sel)
    ranking_intervals(pred,sel);selected_permutation(d,sel)
    # Full selected predictions are reconstructable by date joining this key to parent predictions.
    keys=sel[sel.selected][['basis','date','side','history_n','up_rate','down_rate']]
    joined=keys.merge(pred,on='date',validate='many_to_many')
    joined.to_csv(OUT/'selected_predictions.csv.gz',index=False,compression='gzip')
    save('audit',dict(status='PASS',source_sha256=hashlib.sha256((BASE/'snapshot.json').read_bytes()).hexdigest(),
        parent_predictions_rows=len(pred),selected_predictions_rows=len(joined),
        all_models_same_selected_dates=True,source_and_cache_hashes_verified=True,
        selection_history_closed_before_decision=bool((sel.last_history_close<sel.decision).all()),
        source_last_closed=d['dates'][np.flatnonzero(d['valid'])[-1]],
        macro_vintage_known_valid_days=int(d['macro_known'][d['valid']].sum()),
        created_utc=datetime.now(timezone.utc).isoformat()),csv=False)
    print('WIN55_STUDY_DONE',flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
