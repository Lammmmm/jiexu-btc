
from engine import *
from evaluate import *
from threadpoolctl import threadpool_limits
import pandas as pd
import gc,time
def cached_target(data,features,variant,target):
    dest=ROOT/"results";dest.mkdir(exist_ok=True)
    prefix=f"forecast_{variant}_{target}"
    stamp={"snapshot":json.loads((ROOT/"manifest.json").read_text())["source_sha256"],
        "protocol":hashlib.sha256((ROOT/"protocol.json").read_bytes()).hexdigest(),
        "engine":hashlib.sha256((ROOT/"engine.py").read_bytes()).hexdigest(),"variant":variant,"target":target}
    cache=dest/(prefix+".csv.gz");metadata=dest/(prefix+"_stamp.json")
    if cache.exists() and metadata.exists() and json.loads(metadata.read_text())==stamp:
        print("Verified cache",variant,target,flush=True);return pd.read_csv(cache)
    rows,fits=run_forecasts(data,features,variant,[target])
    frame=pd.DataFrame(rows);frame.to_csv(cache,index=False,compression="gzip")
    write_json(prefix+"_fits.json",fits)
    metadata.write_text(json.dumps(stamp,indent=2),encoding="utf-8")
    return frame

def audit_data(data):
    rows={}
    for name,mask in [("oc",data["valid_oc"]),("cc",data["valid_cc"]),("common",data["valid"])]:
        ids=np.flatnonzero(mask)
        rows[name]={"n":len(ids),"first":data["dates"][ids[0]],"last":data["dates"][ids[-1]],
            "n_2023":int(np.sum(mask&(data["dates"]>="2023-01-01")))}
    write_json("audit.json",{"source_sha256":json.loads((ROOT/"manifest.json").read_text())["source_sha256"],
        "raw_n":len(data["dates"]),"counts":rows,"exclusions":data["exclusions"],
        "actual_macro_release_flags":data["macro_retro"][data["valid"]].sum(0).tolist(),
        "provably_preknown_macro_schedule_flags":data["macro_known"][data["valid"]].sum(0).tolist(),
        "macro_vintage":"No valid historical pre-announcement version before most OOS dates; primaryF/G weekday-only. RetroF/G conditional only."})

def main():
    with threadpool_limits(limits=1):
        data=read_source();audit_data(data);features=build_features(data)
        np.savez_compressed(ROOT/"results/causal_features.npz",**features)
        raw=pd.concat([cached_target(data,features,"raw",t) for t in TARGETS],ignore_index=True)
        dates=data["dates"][data["valid"]&(data["dates"]>=P["extended_test_start"])]
        assert len(raw)==len(dates)*len(MODELS)*len(TARGETS)
        assert (raw.last_train_close<raw.decision).all()
        raw.to_csv(ROOT/"results/predictions.csv.gz",index=False,compression="gzip")
        for start,name in [("2023-01-01","main"),("2021-01-01","extended")]:
            write_json("comparison_"+name+".json",summarize(raw,start))
        raw["year"]=raw.date.str[:4]
        write_json("yearly.json",summarize(raw,"2021-01-01",("target","model","year")))
        # Regime classification is defined only using prior closed prices, no later bull/bear boundaries.
        regime={}
        for i in np.flatnonzero(data["valid"]&(data["dates"]>=P["extended_test_start"])):
            hist=eligible(data,i,data["valid"]);close=data["close"][hist]
            r90=close[-1]/close[-91]-1;ma=close[-200:].mean()
            regime[data["dates"][i]]="bull" if close[-1]>ma and r90>.10 else "bear" if close[-1]<ma and r90<-.10 else "range"
        raw["regime"]=raw.date.map(regime)
        write_json("regimes.json",summarize(raw,P["primary_test_start"],("target","model","regime")))
        for block,reps in [(60,20000),(14,10000),(180,10000)]:
            print("Main paired bootstrap",block,flush=True)
            write_json(f"paired_{block}.json",paired(raw,block,reps))
        write_json("paired_extended.json",paired(raw,60,10000,start=P["extended_test_start"]))
        write_json("paired_macro_conditional.json",paired(raw,60,20000,pairs=[["F_retro","G_retro"]]))
        write_json("calibration.json",calibration_tables(raw))
        write_json("online_alerts.json",online_alerts(raw))
        write_json("elevated_ganzhi_predictions.json",elevated_group(raw))
        # Main immutable forecast export was already saved before scoring.
        print("PRIMARY_DONE",flush=True)
        variants=[]
        for variant in ["cap99","omit_2020","omit_2021","omit_2022"]:
            targetlist=CONT if variant=="cap99" else TARGETS
            frame=pd.concat([cached_target(data,features,variant,t) for t in targetlist],ignore_index=True)
            if variant=="cap99":
                frame=pd.concat([frame,raw[raw.target.isin(BIN)]],ignore_index=True)
            frame.to_csv(ROOT/f"results/predictions_{variant}.csv.gz",index=False,compression="gzip")
            for row in summarize(frame):variants.append(dict(variant=variant,**row))
            write_json("robustness_"+variant+"_paired.json",paired(frame,60,10000,pairs=[["C","E"],["F","G"]]))
            write_json("robustness.json",variants)
            print("VARIANT_DONE",variant,flush=True)
            del frame;gc.collect()
        print("ALL_FORECASTS_DONE",flush=True)
if __name__=="__main__":main()
