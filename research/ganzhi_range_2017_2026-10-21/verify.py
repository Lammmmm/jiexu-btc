"""Independent scalar data, filtering, ranking, and OOS score verification."""
import json,hashlib
from pathlib import Path
from decimal import Decimal
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parent;O=R/'results';B=R.parent/'ganzhi_volatility_2026-10-21'
src=json.loads((B/'snapshot.json').read_text('utf-8'));cut=int(src['metadata']['last_sync_ms'])
cal={r['date']:r for r in src['calendar']};sel=pd.read_csv(O/'selection_daily.csv').set_index(['basis','date'])
counts={b:[[0,0,0] for g in range(60)] for b in ['oc','cc']};global_n=0;common=[0]*60
closed={};ranges={};signs={};gate_checks=0
for i,r in enumerate(src['daily']):
    date=r['date'];g=cal[date]['ganzhi_index'];o,h,l,c=[Decimal(r[k]) for k in ['open','high','low','close']]
    prev=Decimal(src['daily'][i-1]['close']) if i else c
    ocok=i>0 and r['timestamp']+86400000-1<cut and r['close_time']==r['timestamp']+86400000-1
    ccok=bool(ocok and src['daily'][i-1]['close_time']==src['daily'][i-1]['timestamp']+86400000-1)
    roc=c/o-1;rcc=c/prev-1;ran=(h-l)/o
    for b in ['oc','cc']:
        if (b,date) in sel.index:
            x=sel.loc[(b,date)];n,up,dn=counts[b][g]
            side=1 if n and 100*up>=55*n else -1 if n and 100*dn>=55*n else 0
            assert (n,up,dn,side)==(x.history_n,x.up,x.down,x.side)
            assert x.simple_ready==bool(global_n>=30 and common[g]>=1);gate_checks+=1
    y={'abs_oc':float(abs(roc)),'abs_cc':float(abs(rcc)),'range':float(ran)}
    for b,ret in [('oc',roc),('cc',rcc)]:
        for threshold in [2,3,5]:y[b+str(threshold)]=int(abs(ret)>=Decimal(threshold)/100)
    y['range5']=int(ran>=Decimal('.05'));y['range10']=int(ran>=Decimal('.10'))
    if ocok:ranges[date]=(g,float(ran))
    if ccok:closed[date]=y;global_n+=1;common[g]+=1
    for b,ret,okay in [('oc',roc,ocok),('cc',rcc,ccok)]:
        if okay:
            x=counts[b][g];x[0]+=1;x[1]+=int(ret>0);x[2]+=int(ret<0)

rank=json.loads((O/'ganzhi_rankings.json').read_text('utf-8'));rank_checks=0
for x in rank:
    scope=x['scope'];b=x['basis'];g=x['g']
    if scope.startswith('rolling'):
        z=sel.loc[b];z=z[z.selected&z.simple_ready&(z.g==g)]
        if scope.endswith('min10'):z=z[z.history_n>=10]
        if scope.endswith('min20'):z=z[z.history_n>=20]
        dates=z.index.tolist()
    else:dates=[d for d,(gg,v) in ranges.items() if gg==g]
    vals=[ranges[d][1] for d in dates]
    assert len(vals)==x['n'] and abs(np.mean(vals)-x['mean_range'])<1e-14 and abs(np.median(vals)-x['median_range'])<1e-14
    if scope=='current55_descriptive':
        n,u,dn=counts[b][g];assert max(u,dn)*100>=55*n
    rank_checks+=1
prediction_rows=0;score_checks=0
full=pd.read_csv(O/'predictions.csv.gz',low_memory=False)
for name in ['simple_predictions','predictions']:
    p=full if name=='predictions' else pd.read_csv(O/(name+'.csv.gz'))
    assert np.all(p.last_train_close<p.decision)
    for t,pp in p.groupby('target'):
        truth=np.array([closed[d][t] for d in pp.date]);np.testing.assert_allclose(pp.actual.to_numpy(),truth,atol=1e-14)
    prediction_rows+=len(p)
    scores=json.loads((O/('model_comparison.json' if name=='predictions' else 'simple_model_comparison.json')).read_text('utf-8'))
    for row in scores:
        x=p[(p.target==row['target'])&(p.model==row['model'])]
        if row['scope']!='all':
            dates=set(sel.loc[row['scope']].query('selected').index);x=x[x.date.isin(dates)]
        y=x.actual.to_numpy();f=x.pred.to_numpy();assert len(x)==row['n']
        if row['target'] in ['abs_oc','abs_cc','range']:
            assert abs(row['mae']-np.mean(abs(y-f)))<1e-14 and abs(row['rmse']-np.sqrt(np.mean((y-f)**2)))<1e-14
        else:assert abs(row['brier']-np.mean((y-f)**2))<1e-14
        score_checks+=1
top=json.loads((O/'exante_top10_daily.json').read_text('utf-8'))
f=full[(full.target=='range')&(full.model=='F')].sort_values('date')
dates=pd.to_datetime(f.date).to_numpy();gg=f.g.to_numpy();ratio=f.actual.to_numpy()/f.pred.to_numpy();date_strings=f.date.to_numpy();top_checks=0
for row in top:
    stop=np.datetime64(row['date']);use=(dates<stop)&(dates>=stop-np.timedelta64(365,'D'))
    n=np.bincount(gg[use],minlength=60);sums=np.bincount(gg[use],weights=ratio[use],minlength=60)
    assert n.min()>=5
    risks=(sums+20*ratio[use].mean())/(n+20)
    chosen=sorted(range(60),key=lambda g:(-risks[g],g))[:10]
    assert chosen==row['chosen_g'] and row['top10']==(row['g'] in chosen)
    assert row['last_history_date']<row['date'];top_checks+=1
xml=ET.parse(O/'unit-tests.xml').getroot();suites=xml.findall('testsuite')
assert sum(int(x.attrib.get('tests',0)) for x in suites)==12
assert all(int(x.attrib.get('failures',0))==0 and int(x.attrib.get('errors',0))==0 for x in suites)
out=dict(status='PASS',unit_tests=12,scalar_gate_checks=gate_checks,ranking_rows_checked=rank_checks,
    true_target_prediction_rows=prediction_rows,score_rows_checked=score_checks,all_exante_top10_lists_checked=top_checks,
    source_sha256=hashlib.sha256((B/'snapshot.json').read_bytes()).hexdigest(),production_changes=False)
(O/'verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
