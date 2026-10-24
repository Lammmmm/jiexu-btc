"""Arbitrary-integer finite sample audit of all 68 primary aggregate probabilities."""
from core import *
from math import comb
from decimal import localcontext
import gzip

def weights(m,a,b):
    return [comb(m,k)*a**k*(b-a)**(m-k) for k in range(m+1)],b**m

def integer_count_tail(events,observed):
    coefficients=[1];den=1
    for numerator,denominator in events:
        new=[0]*(len(coefficients)+1)
        for j,v in enumerate(coefficients):new[j]+=v*(denominator-numerator);new[j+1]+=v*numerator
        coefficients=new;den*=denominator
    assert sum(coefficients)==den
    return sum(coefficients[observed:]),den

def decimal_ratio(num,den):
    with localcontext() as ctx:
        ctx.prec=50
        return str(Decimal(num)/Decimal(den))

def main():
    rows,_=data();ex=json.loads((OUT/'aggregate_exact_tests.json').read_text('utf-8'));records=[];raw=[];individual=[]
    for basis in P['bases']:
        x=prepared(rows,basis);n=x['n'];m=x['m'];up=x['up'];down=m-up
        for null in P['ideal_nulls']:
            fp=Fraction(1,2) if null=='iid50' else Fraction(int(up[0].sum()),int(m[0].sum()));aa,bb=fp.numerator,fp.denominator
            cache={int(mm):weights(int(mm),aa,bb) for mm in set(m.ravel())}
            for r in ex:
                if r['family']!='exact_primary68' or r['basis']!=basis or r['null']!=null:continue
                events=[]
                for g in range(60):
                    if 'observed_both' in r:
                        w1,d1=cache[int(m[1,g])];w2,d2=cache[int(m[2,g])]
                        c1=int(critical(n[1,g],r['threshold']));c2=int(critical(n[2,g],r['threshold']))
                        num=sum(w1[c1:])*sum(w2[c2:])+sum(w1[:int(m[1,g])-c1+1])*sum(w2[:int(m[2,g])-c2+1]);den=d1*d2
                    else:
                        w,den=cache[int(m[0,g])];mm=int(m[0,g])
                        if 'maximum_rate' in r:
                            rat=Fraction(r['exact_fraction']);crit=(int(n[0,g])*rat.numerator+rat.denominator-1)//rat.denominator
                            num=sum(v for k,v in enumerate(w) if k>=crit or mm-k>=crit)
                        else:
                            crit=int(critical(n[0,g],r['threshold']));side=r['side']
                            num=sum(v for k,v in enumerate(w) if (side in ['up','either'] and k>=crit) or (side in ['down','either'] and mm-k>=crit))
                    events.append((num,den))
                observed=r.get('observed_both',r.get('observed',1))
                num,den=integer_count_tail(events,observed)
                exact=decimal_ratio(num,den);err=abs(float(exact)-r['p']);assert err<1e-10
                record=dict(basis=basis,null=null,side=r.get('side'),threshold=r.get('threshold'),kind='joint' if 'observed_both' in r else 'maximum' if 'maximum_rate' in r else 'full_count',
                            observed=observed,probability_50_decimal_digits=exact,reported_float_p=r['p'],absolute_float_error=err,numerator_bits=num.bit_length(),denominator_bits=den.bit_length())
                records.append(record);raw.append(dict(**record,numerator_hex=hex(num),denominator_hex=hex(den)))
            for j in range(3):
                for g in range(60):
                    k=int(up[j,g]);w,den=cache[int(m[j,g])];num=sum(v for v in w if v<=w[k]);value=float(decimal_ratio(num,den))
                    expected=next(r for r in json.loads((OUT/'individual_binomial_normal.json').read_text('utf-8')) if r['basis']==basis and r['period']==period_name(j) and r['null']==null and r['g']==g)
                    assert abs(value-expected['p'])<1e-10
                    individual.append(dict(basis=basis,period=period_name(j),g=g,null=null,integer_p=value,scipy_p=expected['p'],absolute_error=abs(value-expected['p'])))
    save('integer_exact_primary_audit',records);save('integer_individual_audit',individual)
    (OUT/'integer_exact_fractions.json.gz').write_bytes(gzip.compress(json.dumps(raw,separators=(',',':')).encode(),mtime=0))
    print(json.dumps(dict(primary_aggregate_integer_checks=len(records),individual_integer_checks=len(individual),max_absolute_error=max(r['absolute_float_error'] for r in records))),flush=True)

if __name__=='__main__':main()
