
from engine import *
from evaluate import *
from threadpoolctl import threadpool_limits
import pandas as pd
def main():
    with threadpool_limits(limits=1):
        d=read_source();records=[];cutoff=[]
        for k,t in enumerate(TARGETS):
            binary=t in BIN;y=d["y"][:,k]
            for i in np.flatnonzero(d["valid"]&(d["dates"]>=P["primary_test_start"])):
                past=eligible(d,int(i),d["valid"]);recent=past[d["dates"][past]>="2023-01-01"]
                use=recent if len(recent)>=30 else past
                p=float((y[use].sum()+1)/(len(use)+2)) if binary else float(y[use].mean())
                cutoff.append(dict(date=d["dates"][i],target=t,model="A_2023",actual=y[i],pred=p))
                if not binary:continue
                global_rate=float((y[past].sum()+.5)/(len(past)+1))
                for w in [7,14,30,90,365]:
                    ids=past[d["ts"][past]>=d["ts"][i]-w*DAY];n=len(ids);count=y[ids].sum()
                    for name,p in [("raw_clipped",np.clip(count/n,1e-5,1-1e-5)),
                                   ("Jeffreys", (count+.5)/(n+1)),
                                   ("EB2",(count+2*global_rate)/(n+2))]:
                        records.append(dict(date=d["dates"][i],target=t,model=f"roll{w}_{name}",actual=y[i],pred=float(p)))
        a=pd.DataFrame(cutoff);b=pd.DataFrame(records)
        a.to_csv(ROOT/"results/cutoff_unconditional_predictions.csv.gz",index=False,compression="gzip")
        write_json("cutoff_unconditional_comparison.json",summarize(a))
        write_json("probability_prior_sensitivity.json",summarize(b))
        print("CUTOFF_AND_PRIOR_DONE",flush=True)
if __name__=="__main__":main()
