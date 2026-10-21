
"""Independent scalar feature/baseline reconstruction and sklearn prediction cross-check."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import json,hashlib,math
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge,LogisticRegression
ROOT=Path(__file__).resolve().parent
S=json.loads((ROOT/"snapshot.json").read_text(encoding="utf-8"))
P=json.loads((ROOT/"protocol.json").read_text(encoding="utf-8"))
targets=P["continuous_targets"]+list(P["binary_targets"]);CONT=P["continuous_targets"]
rows=S["daily"];cal={r["date"]:r for r in S["calendar"]};cutoff=int(S["metadata"]["last_sync_ms"]);DAY=86400000
dates=np.array([r["date"] for r in rows]);ts=np.array([r["timestamp"] for r in rows]);ct=np.array([r["close_time"] for r in rows])
g=np.array([cal[r["date"]]["ganzhi_index"] for r in rows])
valid=np.array([i>0 and r["date"]!=S["metadata"]["first_available_date"] and r["timestamp"]+DAY-1<cutoff
    and r["close_time"]==r["timestamp"]+DAY-1 and rows[i-1]["close_time"]==rows[i-1]["timestamp"]+DAY-1 for i,r in enumerate(rows)])
y=np.zeros((len(rows),len(targets)))
for i,r in enumerate(rows):
    o,h,l,c=[Decimal(r[k]) for k in ["open","high","low","close"]]
    magnitudes={"abs_oc":abs(c/o-1),"abs_cc":abs(c/Decimal(rows[i-1]["close"])-1) if i else Decimal(0),"range":(h-l)/o}
    for k,t in enumerate(targets):
        y[i,k]=float(magnitudes[t]) if t in CONT else int(magnitudes[P["binary_targets"][t][0]]>=Decimal(P["binary_targets"][t][1]))
z=pd.read_csv(ROOT/"results/predictions.csv.gz");features=np.load(ROOT/"results/causal_features.npz")
date_to_i={d:i for i,d in enumerate(dates)}
samples=sorted(set(z.date.iloc[np.linspace(0,len(z)-1,48,dtype=int)].tolist()+["2023-01-01","2026-10-20"]))
feature_checks=0;simple_checks=0
for d in samples:
    i=date_to_i[d];past=np.flatnonzero(valid&(ct<ts[i]))
    for k,t in enumerate(targets):
        binary=t not in CONT;uk=targets.index(t if not binary else P["binary_targets"][t][0])
        vals=[y[past[-1],uk]]
        for w in [7,14,30,90]:
            idx=past[ts[past]>=ts[i]-w*DAY];vals.append(float(y[idx,uk].mean()))
        for col,w in [(2,7),(2,30),(0,7),(0,30)]:
            idx=past[ts[past]>=ts[i]-w*DAY];vals.append(float(y[idx,col].mean()))
        expected=list(np.log(np.maximum(vals,1e-6)))
        if binary:
            for w in [7,30,90]:
                idx=past[ts[past]>=ts[i]-w*DAY];rate=(y[idx,k].sum()+1)/(len(idx)+2)
                expected.append(math.log(rate/(1-rate)))
        np.testing.assert_allclose(features[t][i],expected,rtol=1e-12,atol=1e-12);feature_checks+=len(expected)
        same=past[g[past]==g[i]]
        global_mean=(y[past,k].sum()+1)/(len(past)+2) if binary else y[past,k].mean()
        expected_d=(y[same,k].sum()+20*global_mean)/(len(same)+20)
        win=past[ts[past]>=ts[i]-30*DAY]
        expected_b=(y[win,k].sum()+1)/(len(win)+2) if binary else y[win,k].mean()
        selected=z[(z.date==d)&(z.target==t)].set_index("model")
        for model,expected_p in [("A",global_mean),("B30",expected_b),("D",expected_d)]:
            assert math.isclose(float(selected.loc[model,"pred"]),expected_p,abs_tol=1e-12)
            assert int(selected.loc[model,"group_n"])==len(same)
            assert int(selected.loc[model,"group_n_2023"])==int(np.sum(dates[same]>="2023-01-01"))
            simple_checks+=3

regression_checks=0
for t in ["abs_oc","range","oc3","range10"]:
    k=targets.index(t);binary=t not in CONT
    fitlog=json.loads((ROOT/f"results/forecast_raw_{t}_fits.json").read_text())
    for month in ["2023-01","2024-07","2026-10"]:
        for kind in ["C","F"]:
            info=next(r for r in fitlog if r["month"]==month and r["model"]==kind)
            i=date_to_i[month+"-01"];x=features[t]
            if kind=="F":
                weekday=np.array([datetime.fromisoformat(d).weekday() for d in dates])
                x=np.column_stack([x,np.eye(7)[weekday][:,1:]])
            train=np.flatnonzero(valid&(ct<ts[i])&(ts>=ts[i]-1095*DAY)&np.isfinite(x).all(1))
            assert info["train_end"]==dates[train[-1]] and info["train_n"]==len(train)
            mean=x[train].mean(0);scale=x[train].std(0);scale[scale<1e-8]=1
            xx=(x[train]-mean)/scale;yy=y[train,k];alpha=info["alpha"]
            if binary:
                ref=LogisticRegression(C=1/alpha,solver="lbfgs",tol=1e-10,max_iter=2000).fit(xx,yy)
            else:
                ly=np.log(yy+1e-6);ref=Ridge(alpha=alpha).fit(xx,ly);smear=np.exp(ly-ref.predict(xx)).mean()
            for day in ["01","14"]:
                d=month+"-"+day
                if d not in set(z.date):continue
                j=date_to_i[d];tx=(x[j:j+1]-mean)/scale
                pp=float(ref.predict_proba(tx)[0,1]) if binary else float(np.exp(ref.predict(tx)[0])*smear-1e-6)
                actual=float(z[(z.date==d)&(z.target==t)&(z.model==kind)].pred.iloc[0])
                assert math.isclose(actual,pp,abs_tol=2e-6),(t,d,kind,actual,pp)
                regression_checks+=1
assert (z.last_train_close<z.decision).all()
expected_dates=list(dates[valid&(dates>="2021-01-01")])
for (t,m),a in z.groupby(["target","model"]):
    assert a.date.tolist()==expected_dates
    np.testing.assert_allclose(a.actual.to_numpy(),y[[date_to_i[d] for d in expected_dates],targets.index(t)],atol=1e-14)
    assert a.g.nunique()==60
    if t not in CONT:assert a.pred.between(1e-5,1-1e-5).all()
    else:assert (a.pred>=0).all()
result={"status":"PASS","feature_scalar_fields":feature_checks,"baseline_and_count_fields":simple_checks,"sklearn_monthly_predictions":regression_checks,
    "total_prediction_rows":len(z),"extended_days":len(expected_dates),"main_days":sum(d>="2023-01-01" for d in expected_dates),
    "models":z.model.nunique(),"targets":z.target.nunique(),"all_training_closes_before_prediction":True,
    "all_targets_models_identical_test_dates":True,"all_60_groups":True}
(ROOT/"results/independent_verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
