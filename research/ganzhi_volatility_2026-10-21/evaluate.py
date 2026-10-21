
from engine import *
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score,average_precision_score,precision_recall_curve,auc
from statsmodels.stats.proportion import proportion_confint

def safe_float(x):
    return float(x) if np.isfinite(x) else None
def tie_top(scores,fraction,dates):
    n=len(scores);k=max(1,int(np.ceil(n*fraction)))
    # Hash tie order fixed without target outcomes, common across models.
    jitter=np.array([int(hashlib.sha256(str(d).encode()).hexdigest()[:12],16) for d in dates])
    rank=np.lexsort((jitter,-np.asarray(scores)))
    mask=np.zeros(n,bool);mask[rank[:k]]=True
    return mask

def metrics(x,target):
    y=x.actual.to_numpy();p=x.pred.to_numpy();n=len(y)
    base=dict(n=n,actual_mean=float(y.mean()),pred_mean=float(p.mean()))
    if target in CONT:
        base.update(mae=float(abs(y-p).mean()),rmse=float(np.sqrt(np.mean((y-p)**2))),
            mse=float(np.mean((y-p)**2)),spearman=safe_float(spearmanr(y,p).statistic) if np.std(p)>0 else None)
        high=tie_top(y,.10,x.date)
        for q in [.1,.2]:
            alert=tie_top(p,q,x.date)
            base[f"top{int(q*100)}_mean_actual"]=float(y[alert].mean())
            base[f"top{int(q*100)}_lift"]=float(y[alert].mean()/y.mean())
            base[f"top{int(q*100)}_highvol_recall"]=float((high&alert).sum()/high.sum())
    else:
        pp=np.clip(p,1e-5,1-1e-5)
        bs=float(np.mean((y-pp)**2));ll=float(np.mean(-(y*np.log(pp)+(1-y)*np.log1p(-pp))))
        base.update(brier=bs,logloss=ll,events=int(y.sum()),
            roc_auc=float(roc_auc_score(y,pp)) if 0<y.sum()<n else None,
            pr_auc_ap=float(average_precision_score(y,pp)) if y.sum()>0 else None)
        if 0<y.sum()<n:
            precision,recall,_=precision_recall_curve(y,pp)
            base["pr_auc_trapezoid"]=float(auc(recall,precision))
        else:base["pr_auc_trapezoid"]=None
        bins=np.minimum((pp*10).astype(int),9)
        ece=sum(np.mean(bins==b)*abs(y[bins==b].mean()-pp[bins==b].mean()) for b in range(10) if np.any(bins==b))
        base["ece10"]=float(ece)
        for q in [.1,.2]:
            alert=tie_top(pp,q,x.date)
            precision=float(y[alert].mean())
            base[f"top{int(q*100)}_event_rate"]=precision
            base[f"top{int(q*100)}_recall"]=float(y[alert].sum()/y.sum()) if y.sum()>0 else None
            base[f"top{int(q*100)}_lift"]=float(precision/y.mean()) if y.mean()>0 else None
    return base

def summarize(pred,start="2023-01-01",keys=("target","model")):
    out=[]
    for key,x in pred[pred.date>=start].groupby(list(keys),sort=True):
        meta=dict(zip(keys,key if isinstance(key,tuple) else (key,)))
        out.append(dict(**meta,**metrics(x,meta["target"])))
    return out

def add_losses(pred):
    z=pred.copy()
    z["se"]=(z.actual-z.pred)**2
    z["ae"]=abs(z.actual-z.pred)
    pp=np.clip(z.pred,1e-5,1-1e-5)
    z["brier"]=z.se
    z["logloss"]=-(z.actual*np.log(pp)+(1-z.actual)*np.log1p(-pp))
    return z

def paired(pred,block,reps,pairs=None,start="2023-01-01"):
    pairs=pairs or P["main_pairs"]
    z=add_losses(pred[pred.date>=start])
    columns=[];rows=[]
    for t in TARGETS:
        frames={m:g.sort_values("date").reset_index(drop=True) for m,g in z[z.target==t].groupby("model")}
        dates=frames["A"].date.tolist()
        for ref,cand in pairs:
            assert frames[ref].date.tolist()==dates==frames[cand].date.tolist()
            for metric in ["se","ae"] if t in CONT else ["brier","logloss"]:
                a=frames[ref][metric].to_numpy();b=frames[cand][metric].to_numpy()
                columns.append(a-b);rows.append(dict(target=t,reference=ref,candidate=cand,metric=metric,
                    ref_mean=float(a.mean()),candidate_mean=float(b.mean()),relative_improvement=float(1-b.mean()/a.mean())))
    values=np.column_stack(columns);n=len(values);observed=values.mean(0)
    cs=np.vstack([np.zeros(values.shape[1]),np.cumsum(np.concatenate([values,values]),axis=0)])
    starts=np.arange(n);pool=cs[starts+block]-cs[starts];q,r=divmod(n,block)
    tail=cs[starts+r]-cs[starts] if r else None
    rng=np.random.default_rng(P["seed"]+block+len(pairs))
    draws=[]
    for j in range(0,reps,500):
        count=min(500,reps-j)
        sums=pool[rng.integers(0,n,size=(count,q))].sum(1)
        if r:sums+=tail[rng.integers(0,n,size=count)]
        draws.append(sums/n)
    boot=np.concatenate(draws)
    lo,hi=np.quantile(boot,[.025,.975],axis=0)
    pv=(1+np.sum(abs(boot-observed)>=abs(observed),axis=0))/(reps+1)
    from statsmodels.stats.multitest import multipletests
    hp=multipletests(pv,method="holm")[1]
    for i,row in enumerate(rows):
        row.update(delta=float(observed[i]),ci_low=float(lo[i]),ci_high=float(hi[i]),p=float(pv[i]),p_holm=float(hp[i]),
            block=block,reps=reps,n=n)
    return rows

def calibration_tables(pred):
    out=[]
    for (t,m),x in pred[(pred.date>=P["primary_test_start"])&pred.target.isin(BIN)].groupby(["target","model"]):
        pp=np.clip(x.pred.to_numpy(),1e-5,1-1e-5);y=x.actual.to_numpy();bins=np.minimum((pp*10).astype(int),9)
        for b in range(10):
            mask=bins==b
            if not np.any(mask):continue
            n=int(mask.sum());events=int(y[mask].sum())
            low,high=proportion_confint(events,n,method="wilson")
            out.append(dict(target=t,model=m,bin=b,n=n,events=events,predicted=float(pp[mask].mean()),
                observed=float(y[mask].mean()),wilson_low=float(low),wilson_high=float(high),
                caveat="Pointwise IID Wilson diagnostic, not serial/multiple-testing adjusted"))
    return out

def online_alerts(pred):
    out=[]
    for (t,m),x in pred.groupby(["target","model"]):
        x=x.sort_values("date").copy()
        dates=pd.to_datetime(x.date);series=pd.Series(x.pred.to_numpy(),index=dates)
        for q in [.1,.2]:
            cutoff=series.rolling("365D",closed="left",min_periods=60).quantile(1-q).to_numpy()
            use=(x.date>=P["primary_test_start"]).to_numpy()&np.isfinite(cutoff)
            alert=(x.pred.to_numpy()>cutoff)&use
            y=x.actual.to_numpy();total=int(use.sum());n=int(alert.sum())
            out.append(dict(target=t,model=m,nominal_fraction=q,test_n=total,alert_n=n,
                actual_fraction=float(n/total),actual_mean_alert=float(y[alert].mean()) if n else None,
                overall_mean=float(y[use].mean()),event_recall=float(y[alert].sum()/y[use].sum()) if t in BIN and y[use].sum() else None))
    return out

def elevated_group(pred):
    out=[]
    z=pred[pred.date>=P["primary_test_start"]]
    for t in TARGETS:
        rows={m:g.sort_values("date").reset_index(drop=True) for m,g in z[z.target==t].groupby("model")}
        for ref,cand in [("C","E"),("F","G"),("F_retro","G_retro")]:
            a,b=rows[ref],rows[cand]
            threshold=.05 if t in BIN else .20
            mask=(b.pred-a.pred>=threshold) if t in BIN else (b.pred>=a.pred*(1+threshold))
            n=int(mask.sum())
            out.append(dict(target=t,reference=ref,candidate=cand,n=n,
                actual_mean=float(b.loc[mask,"actual"].mean()) if n else None,
                baseline_prediction_mean=float(a.loc[mask,"pred"].mean()) if n else None,
                group_prediction_mean=float(b.loc[mask,"pred"].mean()) if n else None,
                realized_excess_over_baseline=float((b.loc[mask,"actual"]-a.loc[mask,"pred"]).mean()) if n else None))
    return out
