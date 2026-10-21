from core import *

def main():
    df,src=read_data();df.to_csv(OUT/'source_daily.csv',index=False,encoding='utf-8-sig')
    accumulated={k:[] for k in ['groups','summary','correlations','yearly','regimes','training_bins','rolling','rolling_windows']}
    annual=[];data_audit=[];survival=[]
    for basis in ['oc','cc']:
        a=prepare(df,basis);obs=observed(a)
        for k,v in obs.items():accumulated[k].extend(v)
        z=a['df']
        data_audit.append(dict(basis=basis,n=len(z),first=z.date.iloc[0],last=z.date.iloc[-1],up=int((z.sign>0).sum()),down=int((z.sign<0).sum()),flat=int((z.sign==0).sum())))
        for yr,x in z.groupby('year'):
            annual.append(dict(basis=basis,year=int(yr),up=int((x.sign>0).sum()),down=int((x.sign<0).sum()),flat=int((x.sign==0).sum()),n=len(x),up_rate=float((x.sign>0).mean()),down_rate=float((x.sign<0).mean())))
        chosen=[r for r in obs['groups'] if r['split']=='S1' and r['selected55']]
        for row in chosen:
            test=z[(z.date>='2023-01-01')&(z.g==row['g'])].reset_index(drop=True)
            for step in [1,5,10,15,20,24,30]:
                okay=len(test)>=step;k=int((test.sign.iloc[:step]==row['direction']).sum()) if okay else None
                survival.append(dict(basis=basis,g=row['g'],ganzhi=row['ganzhi'],direction=row['direction'],step=step,
                    complete=okay,success=k,n=step if okay else None,available=len(test),rate=k/step if okay else None))
    names={'groups':'ganzhi_splits','summary':'persistence_counts','correlations':'correlations_observed','yearly':'ganzhi_validation_yearly',
        'regimes':'ganzhi_validation_regimes','training_bins':'training_strength_bins','rolling':'rolling_summary','rolling_windows':'rolling_windows'}
    for key,rows in accumulated.items():save(names[key],rows)
    save('annual_market_baselines',annual);save('data_audit',data_audit);save('frozen_pool_prefixes',survival)
    labels=[]
    for r in accumulated['groups']:
        if r['kind']!='main' or not r['selected55']:continue
        if r['marked_reversal']:label='marked_reversal_40_or_less'
        elif r['reversal']:label='reversal_below50'
        elif r['continues65']:label='persistent65'
        elif r['continues60']:label='persistent60'
        elif r['continues55']:label='persistent55'
        else:label='lost55_edge_but_not_reversed'
        labels.append(dict(r,classification=label))
    save('persistent_and_reversed',labels)
    print('OBSERVED_DONE',json.dumps([r for r in accumulated['summary'] if r['split']=='S1' and r['train_threshold']==55]),flush=True)

if __name__=='__main__':main()
