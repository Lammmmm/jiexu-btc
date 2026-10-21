
"""Independent volatility study. No production or prior EV research algorithms imported."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import json,hashlib
import numpy as np
from scipy.special import expit,logit
from scipy.linalg import solve
ROOT=Path(__file__).resolve().parent
P=json.loads((ROOT/"protocol.json").read_text(encoding="utf-8"))
DAY=86400000
CONT=P["continuous_targets"];BIN=list(P["binary_targets"]);TARGETS=CONT+BIN
MODELS=list(P["models"])
EPS=1e-6
def write_json(name,obj):
    out=ROOT/"results";out.mkdir(exist_ok=True)
    (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,
        default=lambda x:x.item() if isinstance(x,np.generic) else str(x)),encoding="utf-8")
def read_source(snapshot=None):
    source=snapshot or json.loads((ROOT/"snapshot.json").read_text(encoding="utf-8"))
    if snapshot is None:
        assert hashlib.sha256((ROOT/"snapshot.json").read_bytes()).hexdigest()==json.loads((ROOT/"manifest.json").read_text())["source_sha256"]
    cal={x["date"]:x for x in source["calendar"]};rows=source["daily"];n=len(rows)
    dates=np.array([x["date"] for x in rows]);ts=np.array([x["timestamp"] for x in rows],dtype=np.int64)
    close_time=np.array([x["close_time"] for x in rows],dtype=np.int64)
    gz=np.array([cal[d]["ganzhi_index"] for d in dates],int);labels=np.array([cal[d]["ganzhi_day"] for d in dates])
    assert set(gz)==set(range(60)) and np.all(np.diff(gz)%60==1)
    cutoff=int(source["metadata"]["last_sync_ms"]);listing=source["metadata"]["first_available_date"]
    y=np.zeros((n,len(TARGETS)));reasons={"oc":[],"cc":[]};valid_oc=np.zeros(n,bool);valid_cc=np.zeros(n,bool)
    signed=np.zeros(n)
    for i,r in enumerate(rows):
        o,h,l,c,v=[Decimal(r[k]) for k in ["open","high","low","close","volume"]]
        expected=int(datetime.fromisoformat(r["date"]).replace(tzinfo=timezone(timedelta(hours=8))).timestamp()*1000)
        assert expected==r["timestamp"] and r["timestamp"]<=r["close_time"]<r["timestamp"]+DAY
        assert all(a.is_finite() for a in [o,h,l,c,v]) and min(o,h,l,c)>0 and v>=0 and l<=min(o,c)<=max(o,c)<=h
        if i:assert ts[i]==ts[i-1]+DAY
        reason="unclosed" if ts[i]+DAY-1>=cutoff else "source_anomaly" if close_time[i]!=ts[i]+DAY-1 else "listing_day" if r["date"]==listing else ""
        cc_reason=reason or ("invalid_previous_close" if not i or close_time[i-1]!=ts[i-1]+DAY-1 else "")
        valid_oc[i]=not reason;valid_cc[i]=not cc_reason
        if reason:reasons["oc"].append({"date":r["date"],"reason":reason})
        if cc_reason:reasons["cc"].append({"date":r["date"],"reason":cc_reason})
        roc=c/o-1;rcc=c/Decimal(rows[i-1]["close"])-1 if i else Decimal(0);ran=(h-l)/o
        values={"abs_oc":abs(roc),"abs_cc":abs(rcc),"range":ran}
        signed[i]=float(roc)
        for j,t in enumerate(TARGETS):
            if t in CONT:y[i,j]=float(values[t])
            else:
                base,threshold=P["binary_targets"][t]
                y[i,j]=float(values[base]>=Decimal(threshold))
    retro=np.zeros((n,2));known_schedule=np.zeros((n,2));dateindex={d:i for i,d in enumerate(dates)}
    for snap in source["economic_snapshots"]:
        cap=int(datetime.fromisoformat(snap["capturedAt"]).timestamp()*1000)
        for ev in snap["events"]:
            if ev["date"] not in dateindex:continue
            j=dateindex[ev["date"]];kind=["cpi","nfp"].index(ev["kind"])
            assert datetime.fromisoformat(ev["releaseAtShanghai"]).date().isoformat()==ev["date"]
            if ev["status"]=="released":retro[j,kind]=1
            # Only archived future schedule records captured before target day are provably pre-known.
            if ev["status"]=="scheduled" and cap<ts[j]:known_schedule[j,kind]=1
    weekday=np.array([datetime.fromisoformat(d).weekday() for d in dates])
    return dict(source=source,dates=dates,ts=ts,ct=close_time,g=gz,labels=labels,y=y,
        valid_oc=valid_oc,valid_cc=valid_cc,valid=valid_oc&valid_cc,exclusions=reasons,
        weekday=weekday,macro_retro=retro,macro_known=known_schedule,signed=signed,
        close=np.array([float(x["close"]) for x in rows]))

def build_features(data):
    n=len(data["dates"]);features={}
    mask=data["valid"];ts=data["ts"];y=data["y"]
    for target in TARGETS:
        k=TARGETS.index(target);under=target if target in CONT else P["binary_targets"][target][0];uk=TARGETS.index(under)
        feats=np.full((n,9+(3 if target in BIN else 0)),np.nan)
        for i in range(n):
            hist=np.flatnonzero(mask&(data["ct"]<ts[i]))
            if len(hist)<90:continue
            values=[y[hist[-1],uk]]
            for w in [7,14,30,90]:
                win=hist[ts[hist]>=ts[i]-w*DAY]
                values.append(np.mean(y[win,uk]) if len(win) else np.mean(y[hist,uk]))
            for col,w in [(2,7),(2,30),(0,7),(0,30)]:
                win=hist[ts[hist]>=ts[i]-w*DAY]
                values.append(np.mean(y[win,col]) if len(win) else np.mean(y[hist,col]))
            v=list(np.log(np.maximum(values,EPS)))
            if target in BIN:
                for w in [7,30,90]:
                    win=hist[ts[hist]>=ts[i]-w*DAY]
                    rate=(y[win,k].sum()+1)/(len(win)+2)
                    v.append(float(logit(rate)))
            feats[i]=v
        features[target]=feats
    return features

def design(data,features,target,kind):
    x=features[target]
    if kind=="C":return x
    weekday=np.eye(7)[data["weekday"]][:,1:]  # reference Monday
    # Main F/G deliberately omit non-vintaged final release-date flags.
    additions=[x,weekday]
    if kind=="F_retro":additions.append(data["macro_retro"])
    return np.column_stack(additions)

def transformed_y(y,binary,cap=None):
    z=y if cap is None or binary else np.minimum(y,cap)
    return z if binary else np.log(z+EPS)

def fit_base(x,y,binary,alpha,cap=None):
    mean=x.mean(0);scale=x.std(0);scale[scale<1e-8]=1.
    z=np.column_stack([np.ones(len(x)),(x-mean)/scale])
    penalty=np.r_[0.,np.full(x.shape[1],alpha)]
    if not binary:
        ly=transformed_y(y,False,cap)
        beta=solve(z.T@z+np.diag(penalty),z.T@ly,assume_a="pos",check_finite=False)
        residual=ly-z@beta;smearing=float(np.exp(np.clip(residual,-20,20)).mean())
    else:
        smearing=1.
        prior=(y.sum()+.5)/(len(y)+1)
        beta=np.zeros(z.shape[1]);beta[0]=logit(prior)
        if 0<y.sum()<len(y):
            for iteration in range(40):
                pp=expit(z@beta);v=np.maximum(pp*(1-pp),1e-8)
                gradient=z.T@(y-pp)-penalty*beta
                hessian=z.T@(v[:,None]*z)+np.diag(penalty)
                step=solve(hessian,gradient,assume_a="pos",check_finite=False)
                step=np.clip(step,-3,3);beta+=step
                if np.max(abs(step))<1e-7:break
    return (mean,scale,beta,smearing,binary)

def predict_base(fit,x):
    mean,scale,beta,smearing,binary=fit
    z=beta[0]+((x-mean)/scale)@beta[1:]
    if binary:return np.clip(expit(z),1e-5,1-1e-5)
    return np.maximum(EPS,np.exp(np.clip(z,-20,2))*smearing-EPS)

def label_mask(data,omit_year=None):
    mask=data["valid"].copy()
    if omit_year:mask&=np.array([not d.startswith(str(omit_year)) for d in data["dates"]])
    return mask

def eligible(data,i,mask,window=None):
    use=mask&(data["ct"]<data["ts"][i])
    if window:use&=data["ts"]>=data["ts"][i]-window*DAY
    return np.flatnonzero(use)

def folds(indices,length=252):
    tail=indices[-length:]
    if len(tail)<126:return []
    return [a for a in np.array_split(tail,3) if len(a)]

def loss(y,p,binary,logloss=False):
    if binary and logloss:
        p=np.clip(p,1e-5,1-1e-5)
        return -(y*np.log(p)+(1-y)*np.log1p(-p))
    return (y-p)**2

def select_base(data,x,k,i,mask,cap99=False):
    binary=TARGETS[k] in BIN
    feature_ok=np.isfinite(x).all(1)
    available=eligible(data,i,mask&feature_ok)
    validation=folds(available)
    scores=[]
    for alpha in P["base_alpha_candidates"]:
        total=0.;n=0
        for val in validation:
            train=eligible(data,int(val[0]),mask&feature_ok,P["base_fit_window_days"])
            if len(train)<180:continue
            yy=data["y"][train,k]
            cap=np.quantile(yy,.99) if cap99 and not binary else None
            fit=fit_base(x[train],yy,binary,alpha,cap)
            pred=predict_base(fit,x[val])
            total+=loss(data["y"][val,k],pred,binary,True).sum();n+=len(val)
        scores.append(total/n if n else np.inf)
    chosen=P["base_alpha_candidates"][int(np.argmin(scores))] if np.isfinite(scores).any() else 10
    train=eligible(data,i,mask&feature_ok,P["base_fit_window_days"])
    yy=data["y"][train,k];cap=np.quantile(yy,.99) if cap99 and not binary else None
    fit=fit_base(x[train],yy,binary,chosen,cap)
    return fit,chosen,int(train[-1]),{"alpha":chosen,"cv_loss":None if not np.isfinite(min(scores)) else min(scores),
        "train_n":len(train),"train_end":data["dates"][train[-1]]}

def group_effect(y,p,g,binary,lam,cap99=False):
    counts=np.bincount(g,minlength=60).astype(float)
    if lam=="off" or not len(y):return np.zeros(60),counts
    if binary:
        offset=logit(np.clip(p,1e-5,1-1e-5));theta=np.zeros(60)
        precision=float(lam)/4
        for _ in range(40):
            prob=expit(offset+theta[g])
            score=np.bincount(g,weights=y-prob,minlength=60)-precision*theta
            curvature=np.bincount(g,weights=prob*(1-prob),minlength=60)+precision
            step=np.clip(score/curvature,-2,2);theta+=step
            if np.max(abs(step))<1e-8:break
    else:
        yy=np.minimum(y,np.quantile(y,.99)) if cap99 else y
        resid=yy-p
        sums=np.bincount(g,weights=resid,minlength=60)
        theta=(sums-counts*resid.mean())/(counts+float(lam))
    present=counts>0
    theta[present]-=np.sum(theta*counts)/counts.sum()
    theta[~present]=0.
    return theta,counts

def apply_effect(p,g,theta,binary):
    if binary:return np.clip(expit(logit(np.clip(p,1e-5,1-1e-5))+theta[g]),1e-5,1-1e-5)
    return np.maximum(EPS,p+theta[g])

def select_group(data,baseline,k,i,mask,cap99=False):
    binary=TARGETS[k] in BIN
    available=eligible(data,i,mask&np.isfinite(baseline))
    available=available[data["ts"][available]>=data["ts"][i]-P["group_effect_window_days"]*DAY]
    validation=folds(available)
    candidates=["off",180,60,20];scores=[]
    for lam in candidates:
        total=0.;n=0
        for val in validation:
            train=eligible(data,int(val[0]),mask&np.isfinite(baseline),P["group_effect_window_days"])
            if len(train)<120:continue
            theta,counts=group_effect(data["y"][train,k],baseline[train],data["g"][train],binary,lam,cap99)
            pp=apply_effect(baseline[val],data["g"][val],theta,binary)
            total+=loss(data["y"][val,k],pp,binary).sum();n+=len(val)
        scores.append(total/n if n else np.inf)
    lam=candidates[int(np.argmin(scores))] if np.isfinite(scores).any() else "off"
    theta,counts=group_effect(data["y"][available,k],baseline[available],data["g"][available],binary,lam,cap99)
    return theta,counts,lam

def simple_predictions(data,k,i,mask,cap99=False):
    binary=TARGETS[k] in BIN
    past=eligible(data,i,mask);y=data["y"][:,k]
    cap=np.quantile(y[past],.99) if cap99 and not binary else None
    values=np.minimum(y,cap) if cap is not None else y
    def avg(idx):
        if not len(idx):idx=past
        return float((values[idx].sum()+1)/(len(idx)+2)) if binary else float(values[idx].mean())
    global_mean=avg(past);gidx=past[data["g"][past]==data["g"][i]]
    raw=avg(gidx)
    d=(values[gidx].sum()+20*global_mean)/(len(gidx)+20)
    result={"A":global_mean,"D":float(d),"D_raw":raw}
    for name,w in [("B30",30),("C7",7),("C14",14),("C90",90),("C365",365)]:
        idx=past[data["ts"][past]>=data["ts"][i]-w*DAY];result[name]=avg(idx)
    w=np.exp2(-(data["ts"][i]-data["ct"][past])/DAY/14)
    result["Cewma"]=float((w@values[past]+1)/(w.sum()+2)) if binary else float(w@values[past]/w.sum())
    recent=past[data["dates"][past]>="2023-01-01"]
    if len(recent)<30:result["D_2023"]=result["D"]
    else:
        base=avg(recent);same=recent[data["g"][recent]==data["g"][i]]
        result["D_2023"]=float((values[same].sum()+20*base)/(len(same)+20))
    if binary:
        result={k:float(np.clip(v,1e-5,1-1e-5)) for k,v in result.items()}
    return result,len(gidx),int(np.sum(data["dates"][gidx]>="2023-01-01")),int(data["ct"][past[-1]])

def run_forecasts(data,features,variant="raw",targets=None):
    targets=targets or TARGETS;cap99=variant=="cap99"
    omit=int(variant.split("_")[1]) if variant.startswith("omit_") else None
    mask=label_mask(data,omit)
    n=len(data["dates"]);all_rows=[];fit_log=[]
    for target in targets:
        k=TARGETS.index(target);binary=target in BIN
        matrices={kind:design(data,features,target,kind) for kind in ["C","F","F_retro"]}
        baselines={kind:np.full(n,np.nan) for kind in ["C","F","F_retro","B30"]}
        fits={};effects={};selected={};trainends={};month=None
        for i in range(n):
            if data["dates"][i]<P["backcast_start"] or not data["valid"][i] or not np.isfinite(features[target][i]).all():continue
            simple,ng,n23,lastclose=simple_predictions(data,k,i,mask,cap99)
            baselines["B30"][i]=simple["B30"]
            currentmonth=data["dates"][i][:7]
            if currentmonth!=month:
                for kind,x in matrices.items():
                    fit,alpha,end,info=select_base(data,x,k,i,mask,cap99)
                    fits[kind]=fit;selected[kind]=alpha;trainends[kind]=end
                    fit_log.append(dict(variant=variant,target=target,month=currentmonth,model=kind,**info))
                # Only earlier baseline forecasts whose actual labels are closed may be learned.
                for kind in ["C","F","F_retro","B30"]:
                    effect,counts,lam=select_group(data,baselines[kind],k,i,mask,cap99)
                    effects[kind]=(effect,counts);selected["group_"+kind]=lam
                    fit_log.append(dict(variant=variant,target=target,month=currentmonth,model="group_"+kind,lambda_value=lam,
                        train_n=int(counts.sum()),train_end=data["dates"][i-1]))
                month=currentmonth
            for kind,x in matrices.items():
                baselines[kind][i]=float(predict_base(fits[kind],x[i]))
            prediction=dict(simple)
            prediction.update({kind:baselines[kind][i] for kind in ["C","F","F_retro"]})
            for model,kind in [("E","C"),("G","F"),("G_retro","F_retro"),("E30","B30")]:
                theta,counts=effects[kind]
                prediction[model]=float(apply_effect(baselines[kind][i],data["g"][i],theta,binary))
            if data["dates"][i]<P["extended_test_start"]:continue
            # Daily counts reflect all currently usable history, even if offset coefficients are frozen monthly.
            for model in MODELS:
                if model in ("E","G","G_retro","E30"):
                    kind={"E":"C","G":"F","G_retro":"F_retro","E30":"B30"}[model]
                    theta,counts=effects[kind];n_effect=int(counts[data["g"][i]])
                    reg=selected["group_"+kind]
                else:n_effect=None;reg=None
                all_rows.append(dict(date=data["dates"][i],target=target,model=model,actual=float(data["y"][i,k]),
                    pred=float(prediction[model]),g=int(data["g"][i]),ganzhi=data["labels"][i],
                    group_n=ng,group_n_2023=n23,group_effect_n=n_effect,regularization=reg,
                    decision=int(data["ts"][i]),last_train_close=lastclose,
                    base_alpha=selected.get(model),base_train_end=data["dates"][trainends[model]] if model in trainends else None,
                    macro_cpi=int(data["macro_retro"][i,0]),macro_nfp=int(data["macro_retro"][i,1])))
        print("Forecast complete",variant,target,flush=True)
    return all_rows,fit_log
