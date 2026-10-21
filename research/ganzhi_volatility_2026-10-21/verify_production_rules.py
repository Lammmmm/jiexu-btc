
from pathlib import Path
from decimal import Decimal
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
from backend.models import Candle
from backend.statistics.ganzhi import GanzhiStatisticsService
from backend.calendar.repository import CalendarRepository
s=json.loads((ROOT/"snapshot.json").read_text(encoding="utf-8"))
class FrozenMarket:
    def snapshot(self):
        return [Candle(r["timestamp"],r["close_time"],*(Decimal(r[k]) for k in ["open","high","low","close","volume"]),r["date"]) for r in s["daily"]],s["metadata"]
service=GanzhiStatisticsService(FrozenMarket(),CalendarRepository(ROOT.parents[1]/"data/calendar.db"))
prepared=service._prepare("day")
records=json.loads((ROOT/"results/ganzhi_descriptive.json").read_text(encoding="utf-8"))
checks=0
for basis,prefix,target in [("open","oc","abs_oc"),("previous_close","cc","abs_cc")]:
    for g in service.options():
        allrow=next(r for r in records if r["ganzhi"]==g and r["target"]==target and r["window"]=="all")
        r=service._summarize(g,prepared,start=None,end=None,basis=basis,period="day")
        assert r["sampleCount"]==allrow["n"];checks+=1
        for threshold in [2,3,5]:
            r=service._summarize(g,prepared,start=None,end=None,basis=basis,period="day",threshold=Decimal(threshold))
            actual=r["strength"]["largeMove"]["counts"]["total"]
            expected=next(x for x in records if x["ganzhi"]==g and x["target"]==prefix+str(threshold) and x["window"]=="2023")
            assert actual==round(expected["mean"]*expected["n"])
            assert r["strength"]["sampleCount"]==expected["n"];checks+=2
output={"status":"PASS","checks":checks,"formal_strength_start":"2023-01-01","source":"frozen snapshot only; formal database not written"}
(ROOT/"results/production_rules_verification.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
print(json.dumps(output))
