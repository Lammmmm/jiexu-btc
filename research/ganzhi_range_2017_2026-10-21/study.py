"""Research-only 2017-origin range rankings and rolling forecast validation."""
import os
for _key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[_key]='1'
from pathlib import Path
import sys,json,hashlib,importlib.util
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from statsmodels.stats.multitest import multipletests
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results';BASE=ROOT.parent/'ganzhi_volatility_2026-10-21'
PREV=ROOT.parent/'ganzhi_win55_volatility_2026-10-21'
sys.path.insert(0,str(BASE))
import engine as e
from evaluate import metrics
from association import cluster_interval
spec=importlib.util.spec_from_file_location('locked_win55_helpers',PREV/'study.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
P=json.loads((ROOT/'protocol.json').read_text('utf-8'))
TARGETS=e.TARGETS;MODELS=e.MODELS;SIMPLE=[m for m in MODELS if m not in ['C','E30','E','F','G','F_retro','G_retro']]

def save(name,rows):
    obj=gate.clean(rows)
    (OUT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if isinstance(obj,list):
        pd.DataFrame([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in obj]).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    return obj

def verify_inputs():
    m=json.loads((ROOT/'manifest.json').read_text('utf-8'))
    assert hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest()==m['protocol_sha256']
    for f,h in m['inputs'].items():assert hashlib.sha256((BASE/f).read_bytes()).hexdigest()==h,f
    for f,h in m.get('previous_inputs',{}).items():assert hashlib.sha256((PREV/f).read_bytes()).hexdigest()==h,f

def select_daily(d):
    signs=gate.direction_arrays(d);rows=[]
    for basis in ['oc','cc']:
        for i,date in enumerate(d['dates']):
            if not d['valid'][i]:continue
            ids=e.eligible(d,i,d['valid_'+basis]);same=ids[d['g'][ids]==d['g'][i]]
            common=e.eligible(d,i,d['valid']);same_common=common[d['g'][common]==d['g'][i]]
            n=len(same);up=int(np.sum(signs[basis][same]>0));dn=int(np.sum(signs[basis][same]<0));side=gate.choice(n,up,dn)
            rows.append(dict(date=date,basis=basis,g=int(d['g'][i]),ganzhi=d['labels'][i],history_n=n,
                up=up,down=dn,flat=n-up-dn,preferred_rate=max(up,dn)/n if n else None,side=side,selected=bool(side),
                simple_ready=bool(len(common)>=30 and len(same_common)>=1),common_history_n=len(common),
                common_same_n=len(same_common),decision=int(d['ts'][i]),last_history_close=int(d['ct'][ids[-1]]) if len(ids) else None,
                actual_side=int(signs[basis][i]),correct=bool(side and side==signs[basis][i])))
    return pd.DataFrame(rows)

def simple_forecasts(d):
    rows=[]
    for i,date in enumerate(d['dates']):
        if not d['valid'][i]:continue
        past=e.eligible(d,i,d['valid']);same=past[d['g'][past]==d['g'][i]]
        if len(past)<30 or not len(same):continue
        for k,t in enumerate(TARGETS):
            preds,ng,n23,close=e.simple_predictions(d,k,i,d['valid'])
            for m in SIMPLE:
                rows.append(dict(date=date,target=t,model=m,actual=float(d['y'][i,k]),pred=preds[m],
                    g=int(d['g'][i]),ganzhi=d['labels'][i],group_n=ng,decision=int(d['ts'][i]),last_train_close=close))
    return pd.DataFrame(rows)

def complex_forecasts(d,features):
    # Fixed availability warm-up, independent of future outcomes and dates of good results.
    okay=d['valid']&np.isfinite(features['range']).all(1)
    first=next(i for i in np.flatnonzero(okay) if len(e.eligible(d,int(i),okay))>=180)
    start=str(d['dates'][first]);e.P=dict(e.P,backcast_start=start,extended_test_start=start)
    parts=[]
    for t in TARGETS:
        stamp={'source':hashlib.sha256((BASE/'snapshot.json').read_bytes()).hexdigest(),
            'protocol':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),
            'engine':hashlib.sha256((BASE/'engine.py').read_bytes()).hexdigest(),
            'runner':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'start':start,'target':t}
        dest=OUT/f'forecast_raw_{t}.csv.gz';st=OUT/f'forecast_raw_{t}_stamp.json'
        if dest.exists() and st.exists() and json.loads(st.read_text('utf-8'))==stamp:
            frame=pd.read_csv(dest,low_memory=False);print('VERIFIED_CACHE',t,flush=True)
        else:
            rows,fits=e.run_forecasts(d,features,'raw',[t]);frame=pd.DataFrame(rows)
            frame.to_csv(dest,index=False,compression='gzip');save(f'forecast_raw_{t}_fits',fits)
            st.write_text(json.dumps(stamp,indent=2),encoding='utf-8')
        parts.append(frame)
    return pd.concat(parts,ignore_index=True),start

def metric_tables(pred,sel,start):
    out=[]
    for scope in ['all','oc','cc']:
        dates=set(sel[(sel.basis==scope)&sel.selected].date) if scope!='all' else set(pred.date)
        z=pred[(pred.date>=start)&pred.date.isin(dates)]
        for (t,m),x in z.groupby(['target','model']):out.append(dict(scope=scope,target=t,model=m,**metrics(x,t)))
    return out

def ranking(d,sel):
    records=[]
    for basis in ['oc','cc']:
        current=gate.fixed_and_current(d,gate.direction_arrays(d))
        current={r['g']:r for r in current if r['basis']==basis and r['pool']=='current_descriptive_only'}
        for scope in ['history_all','current55_descriptive','rolling55','rolling55_min10','rolling55_min20']:
            for g in range(60):
                if scope.startswith('rolling'):
                    ss=sel[(sel.basis==basis)&sel.selected&sel.simple_ready&(sel.g==g)]
                    if scope=='rolling55_min10':ss=ss[ss.history_n>=10]
                    if scope=='rolling55_min20':ss=ss[ss.history_n>=20]
                    ids=np.flatnonzero(d['valid']&np.isin(d['dates'],ss.date))
                else:
                    if scope=='current55_descriptive' and not current[g]['selected']:continue
                    ids=np.flatnonzero(d['valid_oc']&(d['g']==g))
                if not len(ids):continue
                vals=d['y'][ids,2];oc=d['y'][ids,0]
                ccids=ids[d['valid_cc'][ids]];cc=d['y'][ccids,1]
                recent=vals[d['dates'][ids]>='2023-01-01'];old=vals[d['dates'][ids]<'2023-01-01']
                yr=np.array([v[:4] for v in d['dates'][ids]])
                yearly={v:float(vals[yr==v].mean()) for v in np.unique(yr)}
                row=dict(basis=basis,scope=scope,g=g,ganzhi=d['labels'][ids[0]],n=len(ids),
                    first=d['dates'][ids[0]],last=d['dates'][ids[-1]],median_range=float(np.median(vals)),mean_range=float(vals.mean()),
                    q25=float(np.quantile(vals,.25)),q75=float(np.quantile(vals,.75)),max_range=float(vals.max()),
                    range5_rate=float(d['y'][ids,TARGETS.index('range5')].mean()),range10_rate=float(d['y'][ids,TARGETS.index('range10')].mean()),
                    abs_oc_median=float(np.median(oc)),abs_oc_mean=float(oc.mean()),
                    abs_cc_n=len(cc),abs_cc_median=float(np.median(cc)) if len(cc) else None,abs_cc_mean=float(cc.mean()) if len(cc) else None,
                    n_recent=len(recent),recent_median=float(np.median(recent)) if len(recent) else None,
                    recent_mean=float(recent.mean()) if len(recent) else None,
                    old_median=float(np.median(old)) if len(old) else None,
                    remove_largest_mean=float((vals.sum()-vals.max())/(len(vals)-1)) if len(vals)>1 else None,
                    largest_share=float(vals.max()/vals.sum()),yearly_means=yearly,
                    current_side=current[g]['side'],current_preferred_rate=current[g]['preferred_rate'],current_n=current[g]['n'])
                for year in [2017,2020,2021,2022]:
                    v=vals[yr!=str(year)];row[f'omit_{year}_median']=float(np.median(v)) if len(v) else None
                records.append(row)
    frame=pd.DataFrame(records)
    for (b,scope),x in frame.groupby(['basis','scope']):
        ordered=x.sort_values(['median_range','mean_range','g'],ascending=[False,False,True]).index
        frame.loc[ordered,'rank_median']=np.arange(1,len(x)+1)
        ordered=x.sort_values(['mean_range','median_range','g'],ascending=[False,False,True]).index
        frame.loc[ordered,'rank_mean']=np.arange(1,len(x)+1)
    frame[['rank_median','rank_mean']]=frame[['rank_median','rank_mean']].astype(int)
    save('ganzhi_rankings',frame.to_dict('records'))
    for (b,scope),x in frame.groupby(['basis','scope']):
        save(f'ranking_{scope}_{b}',x.sort_values('rank_median').to_dict('records'))
    return frame

def group_state_tests(d,sel,pred):
    f=pred[(pred.target=='range')&(pred.model=='F')].sort_values('date').reset_index(drop=True)
    allrows=[]
    for basis in ['oc','cc']:
        ss=sel[sel.basis==basis].set_index('date').loc[f.date]
        use=ss.selected.to_numpy();y=f.actual.to_numpy();p=f.pred.to_numpy();years=f.date.str[:4].to_numpy()
        ratio=y/p-1
        yearmeans={yr:float(ratio[use&(years==yr)].mean()) for yr in np.unique(years)}
        adjusted=np.array([r-yearmeans[yr] for r,yr in zip(ratio,years)])
        for g in range(60):
            mask=use&(f.g.to_numpy()==g)
            if not mask.any():continue
            mu,lo,hi,pv,keff=cluster_interval(adjusted[mask],years[mask])
            raw=ratio[mask];rs={yr:float(raw[years[mask]==yr].mean()) for yr in np.unique(years[mask])}
            allrows.append(dict(basis=basis,g=g,ganzhi=f.loc[mask,'ganzhi'].iloc[0],n=int(mask.sum()),
                actual_mean_range=float(y[mask].mean()),F_mean_prediction=float(p[mask].mean()),
                raw_mean_relative_excess=float(raw.mean()),year_adjusted_excess=mu,ci_low=lo,ci_high=hi,p=pv,
                positive_years=sum(v>0 for v in rs.values()),years=len(rs),yearly_relative_excess=rs,effective_years=keff))
    gate.adjust(allrows)
    for r in allrows:r['passes_association']=bool(r['p_holm']<.05 and r['year_adjusted_excess']>0)
    save('group_state_adjusted',allrows)

def exante_top(d,sel,pred):
    f=pred[(pred.target=='range')&(pred.model=='F')].sort_values('date').reset_index(drop=True)
    dates=f.date.to_numpy();ts=pd.to_datetime(dates).values.astype('datetime64[ms]').astype(np.int64)
    g=f.g.to_numpy();y=f.actual.to_numpy();p=f.pred.to_numpy();ratio=y/p
    top=np.zeros(len(f),bool);ready=np.zeros(len(f),bool);scores=np.full(len(f),np.nan);records=[]
    for i in range(len(f)):
        hist=np.flatnonzero((np.arange(len(f))<i)&(ts>=ts[i]-365*e.DAY))
        counts=np.bincount(g[hist],minlength=60)
        if not np.all(counts>=5):continue
        ready[i]=True;pooled=ratio[hist].mean();sums=np.bincount(g[hist],weights=ratio[hist],minlength=60)
        expected=(sums+20*pooled)/(counts+20)
        order=np.lexsort((np.arange(60),-expected));chosen=order[:10];top[i]=g[i] in chosen;scores[i]=expected[g[i]]
        records.append(dict(date=dates[i],g=int(g[i]),ganzhi=f.ganzhi.iloc[i],score=scores[i],top10=bool(top[i]),
            train_n=int(counts[g[i]]),min_group_n=int(counts.min()),last_history_date=dates[hist[-1]],
            actual_range=y[i],F_pred=p[i],chosen_g=chosen.tolist()))
    save('exante_top10_daily',records)
    result=[];byyear=[]
    for bi,basis in enumerate(['oc','cc']):
        ss=sel[sel.basis==basis].set_index('date').loc[dates];selected=ss.selected.to_numpy()&ready
        high=selected&top;low=selected&~top
        calendar=pd.date_range(str(dates[0]),str(dates[-1]),freq='D').strftime('%Y-%m-%d').to_numpy()
        positions=pd.Index(calendar).get_indexer(dates)
        for label,values in [('actual_range',y),('relative_excess_over_F',ratio-1)]:
            # Original calendar carries zero weights on days outside each warning group.
            padded=np.zeros(len(calendar));padded[positions]=values
            high_calendar=np.zeros(len(calendar),bool);high_calendar[positions]=high
            low_calendar=np.zeros(len(calendar),bool);low_calendar[positions]=low
            bv=gate.masked_bootstrap(padded,high_calendar,60,20000,P['seed']+bi)
            bl=gate.masked_bootstrap(padded,low_calendar,60,20000,P['seed']+bi)
            draws=bv[:,0]-bl[:,0];draws=draws[np.isfinite(draws)]
            delta=float(values[high].mean()-values[low].mean());lo,hi=np.quantile(draws,[.025,.975])
            pv=float((1+np.sum(abs(draws-delta)>=abs(delta)))/(len(draws)+1))
            result.append(dict(basis=basis,metric=label,n_high=int(high.sum()),n_rest=int(low.sum()),
                first=dates[np.flatnonzero(selected)[0]],last=dates[np.flatnonzero(selected)[-1]],
                high_mean=float(values[high].mean()),rest_mean=float(values[low].mean()),delta=delta,ci_low=lo,ci_high=hi,p=pv))
            for yr in sorted(set(v[:4] for v in dates[selected])):
                inyear=np.array([v.startswith(yr) for v in dates]);a=high&inyear;b=low&inyear
                byyear.append(dict(basis=basis,year=yr,metric=label,n_high=int(a.sum()),n_rest=int(b.sum()),
                    high_mean=float(values[a].mean()) if a.any() else None,rest_mean=float(values[b].mean()) if b.any() else None))
    save('exante_top10_test',gate.adjust(result));save('exante_top10_yearly',byyear)

def calendar_pad(pred,sel):
    dates=pd.date_range(str(pred.date.min()),str(pred.date.max()),freq='D').strftime('%Y-%m-%d')
    padded=[]
    for (t,m),x in pred.groupby(['target','model']):
        x=x.set_index('date').reindex(dates);x.index.name='date'
        x['target']=t;x['model']=m;x['actual']=x.actual.fillna(0);x['pred']=x.pred.fillna(0)
        padded.append(x.reset_index())
    gates=[]
    for basis in ['oc','cc']:
        x=sel[sel.basis==basis].set_index('date').reindex(dates);x.index.name='date'
        x['basis']=basis;x['selected']=x.selected.fillna(False).astype(bool);x['side']=x.side.fillna(0)
        gates.append(x.reset_index())
    return pd.concat(padded,ignore_index=True),pd.concat(gates,ignore_index=True)

def main():
    verify_inputs();d=e.read_source();features=dict(np.load(BASE/'results/causal_features.npz'))
    sel=select_daily(d);save('selection_daily',sel.to_dict('records'))
    ranks=ranking(d,sel)
    early=simple_forecasts(d);early.to_csv(OUT/'simple_predictions.csv.gz',index=False,compression='gzip')
    save('simple_model_comparison',metric_tables(early,sel,str(early.date.min())))
    print('SIMPLE_DONE',early.date.min(),len(early),flush=True)
    full,start=complex_forecasts(d,features);full.to_csv(OUT/'predictions.csv.gz',index=False,compression='gzip')
    assert (full.last_train_close<full.decision).all()
    save('model_comparison',metric_tables(full,sel,start))
    # Reuse the exact previous paired-loss procedure, with an explicit earlier test date.
    gate.P=dict(gate.P,seed=P['seed'],test_start=start)
    padded,sel_padded=calendar_pad(full,sel)
    for block,reps in [(60,20000),(14,10000),(180,10000)]:
        save(f'paired_{block}',gate.paired(padded,sel_padded,start,block,reps));print('PAIRED_DONE',block,flush=True)
    yearly=[]
    for year in sorted(full.date.str[:4].unique()):
        z=full[full.date.str.startswith(year)]
        yearly.extend([dict(year=year,**r) for r in metric_tables(z,sel,start)])
    save('yearly_models',yearly);group_state_tests(d,sel,full);exante_top(d,sel,full)
    summary=[]
    for basis in ['oc','cc']:
        ss=sel[(sel.basis==basis)&sel.simple_ready];z=ss[ss.selected]
        ss2=sel[(sel.basis==basis)&(sel.date>=start)];z2=ss2[ss2.selected]
        summary.append(dict(basis=basis,simple_start=str(early.date.min()),simple_all_n=len(ss),simple_selected_n=len(z),
            early_train_min=int(z.history_n.min()),complex_start=start,complex_all_n=len(ss2),complex_selected_n=len(z2),
            training_min=int(z2.history_n.min()),historical_valid_oc=int(d['valid_oc'].sum()),historical_valid_cc=int(d['valid_cc'].sum()),
            source_last=str(d['dates'][d['valid']][-1]),simple_rows=len(early),complex_rows=len(full)))
    save('summary',summary);print('STUDY_DONE',json.dumps(summary),flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
