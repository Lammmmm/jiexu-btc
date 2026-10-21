
from engine import *
import copy,pytest
import numpy as np
from sklearn.linear_model import Ridge,LogisticRegression
from scipy.special import expit

@pytest.fixture(scope="module")
def setup():
    data=read_source();features=build_features(data);return data,features

def test_full_calendar_and_closed_data(setup):
    d,_=setup
    assert set(d["g"])==set(range(60))
    assert not d["valid"][-1]
    assert np.all(d["ct"][d["valid"]]<int(d["source"]["metadata"]["last_sync_ms"]))

def test_decimal_event_boundary():
    src=json.loads((ROOT/"snapshot.json").read_text(encoding="utf-8"))
    i=100
    for close,expect in [("101.99999999",0),("102.00000000",1),("102.00000001",1)]:
        s=copy.deepcopy(src);s["daily"][i].update(open="100",low="99",high="104",close=close)
        d=read_source(s)
        assert d["y"][i,TARGETS.index("oc2")]==expect

def test_no_target_or_future_in_current_features(setup):
    d,f=setup;i=int(np.flatnonzero(d["dates"]=="2023-01-01")[0])
    changed={k:v.copy() if isinstance(v,np.ndarray) else v for k,v in d.items()}
    changed["y"][i:]=999
    other=build_features(changed)
    for t in TARGETS:np.testing.assert_array_equal(f[t][i],other[t][i])
    ids=eligible(d,i,d["valid"])
    assert ids[-1]==i-1 and d["ct"][ids[-1]]<d["ts"][i]

def test_no_future_in_tuning_or_training(setup):
    d,f=setup;i=int(np.flatnonzero(d["dates"]=="2023-01-01")[0]);k=0;x=f["abs_oc"]
    mask=d["valid"];a=select_base(d,x,k,i,mask)
    changed={k:v.copy() if isinstance(v,np.ndarray) else v for k,v in d.items()}
    changed["y"][i:,0]=999
    b=select_base(changed,x,k,i,mask)
    assert a[1:]==b[1:]
    np.testing.assert_allclose(predict_base(a[0],x[i]),predict_base(b[0],x[i]),rtol=0,atol=0)

def test_ridge_matches_sklearn_on_real_data(setup):
    d,f=setup;x=f["range"];idx=np.flatnonzero(d["valid"]&np.isfinite(x).all(1))[:500]
    xx=x[idx];yy=d["y"][idx,2];fit=fit_base(xx,yy,False,10)
    mean,scale,beta,smear,_=fit
    ref=Ridge(alpha=10).fit((xx-mean)/scale,np.log(yy+EPS))
    np.testing.assert_allclose(beta[1:],ref.coef_,atol=1e-10)
    assert abs(beta[0]-ref.intercept_)<1e-10
    residual=np.log(yy+EPS)-ref.predict((xx-mean)/scale)
    assert abs(smear-np.exp(residual).mean())<1e-10

def test_logistic_matches_sklearn_on_real_data(setup):
    d,f=setup;k=TARGETS.index("oc3");x=f["oc3"]
    idx=np.flatnonzero(d["valid"]&np.isfinite(x).all(1))[:600]
    xx=x[idx];yy=d["y"][idx,k];fit=fit_base(xx,yy,True,10)
    mean,scale,beta,_,_=fit
    ref=LogisticRegression(C=.1,solver="lbfgs",tol=1e-10,max_iter=2000).fit((xx-mean)/scale,yy)
    np.testing.assert_allclose(predict_base(fit,xx),ref.predict_proba((xx-mean)/scale)[:,1],atol=1e-6)

def test_group_offsets_centered_and_off_zero():
    y=np.array([.01,.02,.07,.08]);p=np.full(4,.03);g=np.array([0,0,1,1])
    theta,n=group_effect(y,p,g,False,20)
    assert abs(theta@n)<1e-12
    assert theta[0]<0<theta[1] and theta[2]==0
    off,_=group_effect(y,p,g,False,"off")
    assert np.all(off==0)

def test_group_offset_future_excluded(setup):
    d,_=setup;i=int(np.flatnonzero(d["dates"]=="2023-01-01")[0])
    k=TARGETS.index("oc3");baseline=np.full(len(d["dates"]),.25)
    a=select_group(d,baseline,k,i,d["valid"])
    changed={k:v.copy() if isinstance(v,np.ndarray) else v for k,v in d.items()}
    changed["y"][i:,k]=1
    baseline2=baseline.copy();baseline2[i:]=.99
    b=select_group(changed,baseline2,k,i,d["valid"])
    assert a[2]==b[2]
    np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[1],b[1])

def test_binary_probability_limits():
    theta=np.zeros(60);theta[0]=1e6;theta[1]=-1e6
    pp=apply_effect(np.array([.2,.2]),np.array([0,1]),theta,True)
    assert np.all(pp>=1e-5) and np.all(pp<=1-1e-5)

def test_recent_window_is_past_calendar_days(setup):
    d,_=setup;i=int(np.flatnonzero(d["dates"]=="2024-01-01")[0])
    ids=eligible(d,i,d["valid"],30)
    assert len(ids)==30
    assert d["dates"][ids[-1]]=="2023-12-31" and d["dates"][ids[0]]=="2023-12-02"

def test_no_macro_vintage_is_fabricated(setup):
    d,f=setup
    # Main F has weekday plus causal state; retrospective F adds exactly2 known-in-hindsight flags.
    assert design(d,f,"abs_oc","F").shape[1]==f["abs_oc"].shape[1]+6
    assert design(d,f,"abs_oc","F_retro").shape[1]==f["abs_oc"].shape[1]+8
    assert d["macro_known"][d["valid"]].sum()==0

def test_omitted_year_labels_unavailable(setup):
    d,_=setup;mask=label_mask(d,2022)
    assert not mask[np.char.startswith(d["dates"],"2022")].any()

def test_weighted_auc_ap_matches_sklearn_with_ties_on_real_forecasts():
    import pandas as pd
    from risk_diagnostics import weighted_ranking,bootstrap_weights
    from sklearn.metrics import roc_auc_score,average_precision_score
    frame=pd.read_csv(ROOT/"results/predictions.csv.gz")
    x=frame[(frame.target=="oc3")&(frame.model=="B30")&(frame.date>="2023-01-01")]
    y=x.actual.to_numpy();p=x.pred.to_numpy();w=bootstrap_weights(len(x),reps=5)
    roc,ap=weighted_ranking(y,p,w)
    for i in range(5):
        assert abs(roc[i]-roc_auc_score(y,p,sample_weight=w[i]))<1e-12
        assert abs(ap[i]-average_precision_score(y,p,sample_weight=w[i]))<1e-12

def test_same_fraction_alarm_count_is_exact():
    from evaluate import tie_top
    scores=np.full(100,.2);dates=np.array([str(i) for i in range(100)])
    assert tie_top(scores,.1,dates).sum()==10
    assert tie_top(scores,.2,dates).sum()==20
    np.testing.assert_array_equal(tie_top(scores,.1,dates),tie_top(scores,.1,dates))
