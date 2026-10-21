
"""Additional risk-ranking intervals and genuinely held-out pre2023 high-Ganzhi bands."""
from engine import *
from evaluate import *
from association import oos_group_tables
from statsmodels.stats.multitest import multipletests
from threadpoolctl import threadpool_limits
import pandas as pd

def bootstrap_weights(n,reps=2000,block=60):
    rng=np.random.default_rng(P["seed"]+790);q,r=divmod(n,block)
    weights=np.zeros((reps,n),dtype=np.int16)
    for i in range(reps):
        starts=rng.integers(0,n,size=q+(r>0))
        ids=[(s+np.arange(block))%n for s in starts[:q]]
        if r:ids.append((starts[-1]+np.arange(r))%n)
        weights[i]=np.bincount(np.concatenate(ids),minlength=n)
    assert np.all(weights.sum(1)==n)
    return weights

def weighted_ranking(y,p,w):
    # Exact weighted ROC/AP ties; validated against sklearn sample_weight independently.
    order=np.argsort(-p,kind="stable");ps=p[order];ys=y[order]
    starts=np.r_[0,np.flatnonzero(np.diff(ps)!=0)+1]
    pos=np.add.reduceat(w[:,order]*ys,starts,axis=1)
    neg=np.add.reduceat(w[:,order]*(1-ys),starts,axis=1)
    cp=np.cumsum(pos,axis=1);cn=np.cumsum(neg,axis=1)
    np_total=pos.sum(1);nn_total=neg.sum(1)
    with np.errstate(invalid="ignore",divide="ignore"):
        roc=np.sum(pos*(nn_total[:,None]-cn+.5*neg),axis=1)/(np_total*nn_total)
        precision=cp/np.maximum(cp+cn,1)
        ap=np.sum(precision*pos,axis=1)/np_total
    return roc,ap
def ranking_intervals(pred):
    z=pred[pred.date>=P["primary_test_start"]];n=len(z[(z.target=="oc3")&(z.model=="C")])
    w=bootstrap_weights(n);records=[]
    for t in BIN:
        frames={m:g.sort_values("date").reset_index(drop=True) for m,g in z[z.target==t].groupby("model")}
        for ref,cand in [("C","E"),("F","G")]:
            a,b=frames[ref],frames[cand];y=a.actual.to_numpy()
            r1,p1=weighted_ranking(y,a.pred.to_numpy(),w);r2,p2=weighted_ranking(y,b.pred.to_numpy(),w)
            for name,vals,point in [("roc_auc",r2-r1,metrics(b,t)["roc_auc"]-metrics(a,t)["roc_auc"]),
                                    ("pr_auc_ap",p2-p1,metrics(b,t)["pr_auc_ap"]-metrics(a,t)["pr_auc_ap"])]:
                lo,hi=np.nanquantile(vals,[.025,.975])
                records.append(dict(target=t,reference=ref,candidate=cand,metric=name,delta=point,
                    ci_low=float(lo),ci_high=float(hi),reps=len(w),valid_replicates=int(np.sum(np.isfinite(vals))),
                    p=float((1+np.sum(abs(vals-point)>=abs(point)))/(1+np.sum(np.isfinite(vals)))),
                    caveat="Exploratory paired block interval;32 AUC/AP hypotheses corrected separately."))
    hp=multipletests([r["p"] for r in records],method="holm")[1]
    for i,r in enumerate(records):r["p_holm"]=float(hp[i])
    write_json("ranking_intervals.json",records)
def heldout_top10(data,pred):
    z=pred[pred.date>=P["primary_test_start"]];n=len(z[(z.target=="abs_oc")&(z.model=="F")])
    w=bootstrap_weights(n,reps=10000);out=[];yearrows=[]
    for k,t in enumerate(TARGETS):
        train=np.flatnonzero(data["valid"]&(data["dates"]<"2023-01-01"))
        means=np.array([data["y"][train[data["g"][train]==g],k].mean() for g in range(60)])
        ranking=np.argsort(-means,kind="stable");top=ranking[:10]
        f=z[(z.target==t)&(z.model=="F")].sort_values("date")
        high=np.isin(f.g.to_numpy(),top);low=~high
        y=f.actual.to_numpy();resid=y-f.pred.to_numpy()
        for name,values in [("actual",y),("excess_over_F",resid)]:
            wh=w*high;wl=w*low
            draws=(wh@values)/wh.sum(1)-(wl@values)/wl.sum(1)
            delta=float(values[high].mean()-values[low].mean())
            lo,hi=np.quantile(draws,[.025,.975])
            pv=(1+np.sum(abs(draws-delta)>=abs(delta)))/(len(w)+1)
            out.append(dict(target=t,metric=name,train_end="2022-12-31",selection="top10 of60 by pre2023 empirical mean",
                selected=[data["labels"][np.flatnonzero(data["g"]==g)[0]] for g in top],n_high=int(high.sum()),n_low=int(low.sum()),
                high_mean=float(values[high].mean()),low_mean=float(values[low].mean()),delta=delta,ci_low=float(lo),ci_high=float(hi),p=float(pv)))
        for year in sorted(f.date.str[:4].unique()):
            use=(f.date.str[:4]==year).to_numpy()
            yearrows.append(dict(target=t,year=year,n_high=int((use&high).sum()),
                high_mean=float(y[use&high].mean()),rest_mean=float(y[use&low].mean()),
                high_residual=float(resid[use&high].mean()),rest_residual=float(resid[use&low].mean())))
    hp=multipletests([r["p"] for r in out],method="holm")[1]
    for i,r in enumerate(out):r["p_holm"]=float(hp[i])
    write_json("heldout_pre2023_top10.json",out);write_json("heldout_pre2023_top10_yearly.json",yearrows)

def historical_sensitivity(data):
    rows=[]
    for k,t in enumerate(TARGETS):
        allidx=np.flatnonzero(data["valid"])
        allmean=np.array([data["y"][allidx[data["g"][allidx]==g],k].mean() for g in range(60)])
        for omitted in [2017,2020,2021,2022]:
            idx=allidx[np.array([not d.startswith(str(omitted)) for d in data["dates"][allidx]])]
            m=[]
            for g in range(60):
                ii=idx[data["g"][idx]==g];v=data["y"][ii,k];m.append(float(v.mean()))
                rows.append(dict(target=t,omitted_year=omitted,g=g,ganzhi=data["labels"][np.flatnonzero(data["g"]==g)[0]],
                    n=len(ii),mean=float(v.mean()),all_history_mean=float(allmean[g])))
    pd.DataFrame(rows).to_csv(ROOT/"results/descriptive_year_sensitivity.csv",index=False,encoding="utf-8-sig")
    tail=[]
    z=pd.read_csv(ROOT/"results/predictions.csv.gz");z=z[z.date>=P["primary_test_start"]]
    for t in CONT:
        yy=z[(z.target==t)&(z.model=="A")].sort_values("date")
        # Fixed diagnostic actual upper1%, not a forward-tradable filter.
        threshold=float(yy.actual.quantile(.99))
        for model,x in z[z.target==t].groupby("model"):
            x=x[x.actual<threshold];m=metrics(x,t)
            tail.append(dict(target=t,model=model,actual_99pct=threshold,**m))
    write_json("tail_test_diagnostic.json",tail)

def main():
    with threadpool_limits(limits=1):
        data=read_source();pred=pd.read_csv(ROOT/"results/predictions.csv.gz")
        oos_group_tables(pred);ranking_intervals(pred);heldout_top10(data,pred);historical_sensitivity(data)
        print("RISK_DIAGNOSTICS_DONE",flush=True)
if __name__=="__main__":main()
