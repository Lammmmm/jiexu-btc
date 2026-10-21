
from engine import *
from scipy import stats
from scipy.linalg import qr
from statsmodels.stats.multitest import multipletests
from threadpoolctl import threadpool_limits
import pandas as pd

def cluster_interval(values,years):
    values=np.asarray(values);mu=float(values.mean());ys=np.unique(years)
    if len(ys)<2:return mu,None,None,1.,len(ys)
    masses=np.array([np.mean(years==yr) for yr in ys])
    scores=np.array([np.sum(values[years==yr]-mu)/len(values) for yr in ys])
    se=np.sqrt(len(ys)/(len(ys)-1)*np.sum(scores**2))
    keff=1/np.sum(masses**2);df=max(1.,keff-1)
    critical=stats.t.ppf(.975,df)
    pv=float(2*stats.t.sf(abs(mu)/se,df)) if se>1e-15 else (1. if abs(mu)<1e-15 else 0.)
    return mu,float(mu-critical*se),float(mu+critical*se),pv,float(keff)

def descriptive(data):
    rows=[];wide=[]
    dates=data["dates"]
    for g in range(60):
        label=data["labels"][np.flatnonzero(data["g"]==g)[0]]
        wrow={"g":g,"ganzhi":label}
        for window,start in [("all","2017-01-01"),("2023","2023-01-01")]:
            for k,t in enumerate(TARGETS):
                valid=(data["valid_cc"] if t=="abs_cc" or t.startswith("cc") else data["valid_oc"])&(dates>=start)
                idx=np.flatnonzero(valid);same=idx[data["g"][idx]==g]
                y=data["y"][:,k];years=np.array([d[:4] for d in dates])
                yearmeans={yr:float(y[idx[years[idx]==yr]].mean()) for yr in np.unique(years[idx])}
                resid=np.array([y[j]-yearmeans[years[j]] for j in same])
                delta,lo,hi,p,keff=cluster_interval(resid,years[same])
                mean=float(y[same].mean());med=float(np.median(y[same]));base=float(y[idx].mean())
                rows.append(dict(window=window,target=t,g=g,ganzhi=label,n=len(same),n_since2023=int(np.sum(dates[same]>="2023-01-01")),
                    mean=mean,median=med,q25=float(np.quantile(y[same],.25)),q75=float(np.quantile(y[same],.75)),
                    baseline_mean=base,baseline_median=float(np.median(y[idx])),raw_difference=mean-base,
                    year_matched_difference=delta,ci_low=lo,ci_high=hi,p=p,effective_years=keff,
                    first=dates[same[0]],last=dates[same[-1]],
                    single_remove_max_mean_change=float(np.max(abs((y[same].sum()-y[same])/(len(same)-1)-mean)))))
                wrow[f"{window}_{t}_n"]=len(same);wrow[f"{window}_{t}_mean"]=mean
                if t in CONT:wrow[f"{window}_{t}_median"]=med
        wide.append(wrow)
    pv=[r["p"] for r in rows];hp=multipletests(pv,method="holm")[1];bh=multipletests(pv,method="fdr_bh")[1]
    for i,r in enumerate(rows):r["p_holm"]=float(hp[i]);r["p_bh"]=float(bh[i])
    df=pd.DataFrame(rows)
    df["historical_rank"]=df.groupby(["window","target"])["mean"].rank(method="min",ascending=False).astype(int)
    df.to_csv(ROOT/"results/ganzhi_descriptive.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(wide).to_csv(ROOT/"results/sixty_ganzhi_statistics.csv",index=False,encoding="utf-8-sig")
    write_json("ganzhi_descriptive.json",df.to_dict("records"))
    return df

def orthogonal(x):
    q,r,p=qr(x,mode="economic",pivoting=True)
    rank=int(np.sum(abs(np.diag(r))>1e-9))
    return q[:,:rank]

def omnibus(data,features,window,t,method,reps):
    k=TARGETS.index(t);valid=data["valid"]&np.isfinite(features[t]).all(1)
    if window=="2023":valid&=data["dates"]>="2023-01-01"
    ids=np.flatnonzero(valid);n=len(ids);y=data["y"][ids,k]
    years=np.array([d[:4] for d in data["dates"][ids]])
    state=features[t][ids];state=(state-state.mean(0))/np.maximum(state.std(0),1e-8)
    year_dummy=np.column_stack([(years==yr).astype(float) for yr in sorted(set(years))[1:]])
    week_dummy=np.eye(7)[data["weekday"][ids]][:,1:]
    controls=np.column_stack([np.ones(n),state,year_dummy,week_dummy,data["macro_retro"][ids]])
    # Final actual-release flags are legitimate retrospective controls here, NOT ex-ante features.
    qc=orthogonal(controls)
    group=np.eye(60)[data["g"][ids]]
    z=group-qc@(qc.T@group);qg=orthogonal(z)
    residual=y-qc@(qc.T@y)
    denom=float(residual@residual);obs=float(np.sum((qg.T@residual)**2)/denom)
    rawgroupmeans=[float(y[data["g"][ids]==g].mean()) for g in range(60)]
    rng=np.random.default_rng(P["seed"]+k*101+(0 if window=="all" else 10000)+{"rotation":0,"block14":14,"block28":28}[method])
    matrices=np.vstack([qc.T,qg.T]);yearids=[np.flatnonzero(years==yr) for yr in sorted(set(years))]
    exceed=0;draws=[]
    for begin in range(0,reps,128):
        count=min(128,reps-begin);permuted=np.empty((n,count))
        for positions in yearids:
            vals=residual[positions];ny=len(vals)
            if method=="rotation":
                offsets=rng.integers(0,ny,size=count)
                indices=(np.arange(ny)[:,None]+offsets[None,:])%ny
                permuted[positions]=vals[indices]
            else:
                block=14 if method=="block14" else 28
                chunks=[np.arange(j,min(j+block,ny)) for j in range(0,ny,block)]
                for col in range(count):
                    permuted[positions,col]=vals[np.concatenate([chunks[j] for j in rng.permutation(len(chunks))])]
        projection=matrices@permuted
        remaining=np.maximum(1e-20,denom-np.sum(projection[:qc.shape[1]]**2,axis=0))
        score=np.sum(projection[qc.shape[1]:]**2,axis=0)/remaining
        exceed+=int(np.sum(score>=obs));draws.extend(score.tolist())
    return dict(window=window,target=t,n=n,first=data["dates"][ids[0]],last=data["dates"][ids[-1]],
        method=method,permutations=reps,partial_r2=obs,p=(exceed+1)/(reps+1),
        null95=float(np.quantile(draws,.95)),null99=float(np.quantile(draws,.99)),
        raw_min_group_mean=min(rawgroupmeans),raw_max_group_mean=max(rawgroupmeans),
        control_rank=qc.shape[1],group_rank=qg.shape[1],
        caveat="Retrospective association only; independent year rotations/block reordering approximate dependence-preserving null, not exact randomization.")
def run_omnibus(data,features):
    result=[]
    for method,reps in [("rotation",9999),("block14",1999),("block28",1999)]:
        family=[]
        for window in ["all","2023"]:
            for t in TARGETS:
                family.append(omnibus(data,features,window,t,method,reps))
                print("Omnibus",method,window,t,flush=True)
        adjusted=multipletests([x["p"] for x in family],method="holm")[1]
        for i,x in enumerate(family):x["p_holm"]=float(adjusted[i])
        result.extend(family);write_json("omnibus.json",result)
    return result

def oos_group_tables(pred):
    records=[];z=pred[pred.date>=P["primary_test_start"]]
    for t in TARGETS:
        frames={m:g.sort_values("date").reset_index(drop=True) for m,g in z[z.target==t].groupby("model")}
        for ref,cand in [("C","E"),("F","G")]:
            a,b=frames[ref],frames[cand];diff=(a.actual-a.pred)**2-(b.actual-b.pred)**2
            for g in range(60):
                mask=a.g==g;yr=a.loc[mask,"date"].str[:4].to_numpy()
                vals=diff[mask].to_numpy()
                delta,lo,hi,p,keff=cluster_interval(vals,yr)
                yearly={str(year):float(np.mean(vals[yr==year])) for year in np.unique(yr)}
                same=a[mask]
                records.append(dict(target=t,reference=ref,candidate=cand,g=g,ganzhi=same.ganzhi.iloc[0],
                    n=int(mask.sum()),actual_mean=float(same.actual.mean()),mean_base_prediction=float(same.pred.mean()),
                    mean_ganzhi_prediction=float(b.loc[mask,"pred"].mean()),loss_improvement=delta,ci_low=lo,ci_high=hi,p=p,
                    positive_years=sum(v>0 for v in yearly.values()),yearly_improvements=yearly,effective_years=keff,
                    events=int(same.actual.sum()) if t in BIN else None))
    hp=multipletests([r["p"] for r in records],method="holm")[1]
    bh=multipletests([r["p"] for r in records],method="fdr_bh")[1]
    for i,r in enumerate(records):
        r["p_holm"]=float(hp[i]);r["p_bh"]=float(bh[i])
        r["passes_validation"]=bool(r["p_holm"]<.05 and r["loss_improvement"]>0 and r["positive_years"]>=3
            and r["n"]>=15 and (r["target"] in CONT or r["events"]>=5))
    write_json("ganzhi_oos.json",records)
    flat=[dict(r,yearly_improvements=json.dumps(r["yearly_improvements"],ensure_ascii=False)) for r in records]
    pd.DataFrame(flat).to_csv(ROOT/"results/ganzhi_oos.csv",index=False,encoding="utf-8-sig")
    return records
def main():
    with threadpool_limits(limits=1):
        data=read_source();features=build_features(data)
        descriptive(data);run_omnibus(data,features)
        p=ROOT/"results/predictions.csv.gz"
        if p.exists():oos_group_tables(pd.read_csv(p))
        print("ASSOCIATION_DONE",flush=True)
if __name__=="__main__":main()
