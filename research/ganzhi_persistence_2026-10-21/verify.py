"""Independent scalar cross-checks of full-flow null p-values and cached evidence."""
from pathlib import Path
from decimal import Decimal
import json,hashlib
import xml.etree.ElementTree as ET
import numpy as np
R=Path(__file__).resolve().parent;O=R/'results';p=json.loads((R/'protocol.json').read_text('utf-8'));m=json.loads((R/'manifest.json').read_text('utf-8'))
assert hashlib.sha256((R/'snapshot.json').read_bytes()).hexdigest()==m['source_sha256']
assert hashlib.sha256((R/'protocol.json').read_bytes()).hexdigest()==m['protocol_sha256']
groups=json.loads((O/'ganzhi_splits.json').read_text('utf-8'));observed=json.loads((O/'persistence_counts.json').read_text('utf-8'))
for row in observed:
    subset=[g for g in groups if g['basis']==row['basis'] and g['split']==row['split'] and g['direction'] and max(g['train_up'],g['train_down'])*100>=row['train_threshold']*g['train_n']]
    assert len(subset)==row['selected']
    assert sum(g['test_success']*100>=row['test_threshold']*g['test_n'] for g in subset)==row['continued']
tests=json.loads((O/'null_persistence_tests.json').read_text('utf-8'));individual=json.loads((O/'individual_randomization.json').read_text('utf-8'))
fixed=json.loads((O/'fixed_training_pool_validation_tests.json').read_text('utf-8'))
methods=list(p['null_methods']);splits=[s['id'] for s in p['splits']]+[f'Y{y}' for y in range(2021,2027)];th=p['thresholds']
checks=0;exact_checks=0
for basis in ['oc','cc']:
    for method in methods:
        with np.load(O/f'null_{basis}_{method}.npz') as archive:
            continued=archive['continued'];candidates=archive['candidates'];ivals=archive['individual']
        assert continued.shape==(19999,9,3,3) and candidates.shape==(19999,9,3)
        stamp=json.loads((O/f'null_{basis}_{method}.stamp.json').read_text('utf-8'))
        assert stamp['source']==m['source_sha256'] and stamp['protocol']==m['protocol_sha256']
        assert stamp['core']==hashlib.sha256((R/'core.py').read_bytes()).hexdigest()
        assert stamp['simulator']==hashlib.sha256((R/'simulate.py').read_bytes()).hexdigest()
        for row in tests:
            if row['basis']!=basis or row['method']!=method:continue
            si=splits.index(row['split']);ti=th.index(row['train_threshold']);vi=th.index(row['test_threshold']);draws=continued[:,si,ti,vi]
            pv=(1+int((draws>=row['continued']).sum()))/20000
            assert abs(pv-row['p'])<1e-15;assert row['p_holm']>=row['p'];checks+=1
        for row in individual:
            if row['basis']!=basis or row['method']!=method:continue
            k=row['test_success'];draws=ivals[:,splits.index(row['split']),row['g']]
            pv=(1+int((draws>=k).sum()))/20000 if k is not None else 1.
            assert abs(pv-row['p'])<1e-15;checks+=1
            if row['p_exact'] is not None:
                q=row['p_exact'];tol=max(7*np.sqrt(q*(1-q)/19999),6/20000)
                assert abs(q-pv)<=tol,(row,tol);exact_checks+=1
        for row in fixed:
            if row['basis']!=basis or row['method']!=method:continue
            selected=[g for g in groups if g['basis']==basis and g['split']==row['split'] and g['direction'] and 100*g['train_success']>=row['train_threshold']*g['train_n']]
            gg=np.array([g['g'] for g in selected],int);nn=np.array([g['test_n'] for g in selected])
            outcomes=np.sum(ivals[:,splits.index(row['split']),gg]*100>=row['test_threshold']*nn[None,:],axis=1)
            assert abs(row['p']-(1+int((outcomes>=row['continued']).sum()))/20000)<1e-15;checks+=1
root=ET.parse(O/'unit-tests.xml').getroot();suites=root.findall('testsuite')
assert sum(int(x.attrib['tests']) for x in suites)==16
assert all(int(x.attrib.get('failures',0))==0 and int(x.attrib.get('errors',0))==0 for x in suites)
prod=json.loads((O/'production_verification.json').read_text('utf-8'));assert prod['status']=='PASS'
out=dict(status='PASS',research_tests=16,observed_threshold_count_cells=len(observed),null_and_individual_p_values_recomputed=checks,
    analytical_vs_montecarlo_checks=exact_checks,simulations_per_method_basis=19999,total_null_draws=19999*8,
    production_rule_checks=prod['production_rule_checks'],current_cache_completed_candles_matched=prod['current_cache_completed_candles_matched'],
    production_changes=False)
(O/'verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
