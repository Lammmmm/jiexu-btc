
from engine import *
import pandas as pd, numpy as np, html
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import markdown
R=ROOT/"results"
def read(name):return json.loads((R/name).read_text(encoding="utf-8"))
def pct(v,d=2):return "—" if v is None or not np.isfinite(v) else f"{v*100:.{d}f}%"
def signed(v,d=3):return "—" if v is None else f"{v*100:+.{d}f}%"
def val(v,d=5):return "—" if v is None else f"{v:.{d}f}"
def table(head,rows):
    return "\n\n| "+" | ".join(head)+" |\n| "+" | ".join(["---"]*len(head))+" |\n"+"\n".join("| "+" | ".join(map(str,row))+" |" for row in rows)+"\n\n"
LABEL={"abs_oc":"开收绝对涨跌幅","abs_cc":"昨收绝对涨跌幅","range":"日内高低振幅",
       "oc2":"开收 ≥2%","oc3":"开收 ≥3%","oc5":"开收 ≥5%","cc2":"昨收 ≥2%","cc3":"昨收 ≥3%","cc5":"昨收 ≥5%",
       "range5":"日内振幅 ≥5%","range10":"日内振幅 ≥10%"}
M=read("comparison_main.json");EXT=read("comparison_extended.json");S={(r["target"],r["model"]):r for r in M}
D=read("ganzhi_descriptive.json");O=read("omnibus.json");PAIR=read("paired_60.json")
Y=read("yearly.json");REG=read("regimes.json");ROB=read("robustness.json")
aud=read("audit.json");manifest=json.loads((ROOT/"manifest.json").read_text(encoding="utf-8"))
verification=read("independent_verification.json")
# Delivery CSVs with UTF8 BOM.
for src,dest in [("comparison_main.json","model_comparison.csv"),("comparison_extended.json","model_comparison_extended.csv"),
 ("yearly.json","yearly_models.csv"),("regimes.json","regime_models.csv"),("paired_60.json","paired_main.csv"),
 ("robustness.json","robustness_comparison.csv"),("online_alerts.json","online_alerts.csv"),
 ("calibration.json","calibration.csv"),("omnibus.json","permutation_tests.csv")]:
    pd.DataFrame(read(src)).to_csv(R/dest,index=False,encoding="utf-8-sig")
# Fonts and static shareable plots.
font=Path("C:/Windows/Fonts/msyh.ttc")
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams["font.family"]=font_manager.FontProperties(fname=font).get_name()
plt.rcParams.update({"axes.unicode_minus":False,"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
shown=["A","B30","C","D","D_2023","E","F","G"]
fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout="constrained")
for ax,t in zip(axes,CONT):
    means=[S[t,m]["rmse"]*100 for m in shown]
    bars=ax.bar(shown,means,color=["#94a3b8","#64748b","#287dc1","#ae7d5b","#b9a072","#52a7a0","#24364b","#7755aa"])
    ax.bar_label(bars,labels=[f"{x:.3f}" for x in means],padding=3,fontsize=8)
    ax.tick_params(axis="x",labelrotation=45);ax.set_title(LABEL[t]);ax.set_ylabel("RMSE（收益百分点）")
    ax.set_ylim(0,max(means)*1.18)
fig.suptitle("2023—2026-10-20 样本外误差：近期状态比全历史均值更重要",fontsize=14)
fig.savefig(R/"model_rmse.png",dpi=160);fig.savefig(R/"model_rmse.svg");plt.close(fig)
fig,ax=plt.subplots(figsize=(11,7),layout="constrained")
for j,(ref,cand,col) in enumerate([("C","E","#287dc1"),("F","G","#a85d43")]):
    for i,t in enumerate(TARGETS):
        metric="se" if t in CONT else "brier"
        row=next(r for r in PAIR if r["target"]==t and r["reference"]==ref and r["metric"]==metric)
        mean=100*row["delta"]/row["ref_mean"];lo=100*row["ci_low"]/row["ref_mean"];hi=100*row["ci_high"]/row["ref_mean"]
        ax.errorbar(mean,i+(j-.5)*.15,xerr=[[mean-lo],[hi-mean]],fmt="o",capsize=2,color=col,
                    label=f"{cand} 对 {ref}" if i==0 else None)
ax.axvline(0,color="black",lw=1);ax.set_yticks(np.arange(len(TARGETS)),[LABEL[t] for t in TARGETS])
ax.invert_yaxis();ax.grid(axis="x",alpha=.15);ax.legend()
ax.set_xlabel("样本外损失减少（%）；正值表示加入干支后改善")
ax.set_title("干支的独立增量很小且不稳定\n连续目标用 MSE，事件用 Brier；点态95%区间，主检验全部未通过 Holm 校正")
fig.savefig(R/"incremental_effects.png",dpi=160);fig.savefig(R/"incremental_effects.svg");plt.close(fig)
cal=read("calibration.json")
fig,axes=plt.subplots(1,3,figsize=(13,4),layout="constrained")
for ax,t in zip(axes,["oc3","oc5","range5"]):
    ax.plot([0,1],[0,1],"--",color="#9aa7b5",lw=1)
    for m,col in [("C","#287dc1"),("E","#54a6a0"),("F","#24364b"),("G","#a85d43")]:
        rr=[r for r in cal if r["target"]==t and r["model"]==m and r["n"]>=10]
        ax.plot([r["predicted"] for r in rr],[r["observed"] for r in rr],"o-",label=m,color=col,ms=4)
    ax.set_xlim(0,1);ax.set_ylim(0,1);ax.set_title(LABEL[t]);ax.set_xlabel("平均预测概率");ax.set_ylabel("实际发生率")
axes[0].legend(ncol=2)
fig.suptitle("样本外概率校准：固定十分位概率区间，仅绘制样本≥10的箱",fontsize=13)
fig.savefig(R/"calibration.png",dpi=160);fig.savefig(R/"calibration.svg");plt.close(fig)

parts=["# jiexu-btc｜六十甲子与 BTC 波动强度独立研究报告",
"""**结论分类：C——目前无法证明干支日具有独立的波动预测价值，不建议据此继续开发预测模型。**

研究仅新增独立代码、数据快照、测试和报告。正式日历、API、现有干支统计及生产运行环境没有修改。方向 EV 不属于本轮研究目标，没有将方向胜率与幅度中位数混合计算。

[六十干支完整附表](GANZHI_APPENDIX.html) · [60 行统计 CSV](results/sixty_ganzhi_statistics.csv) · [模型对比 CSV](results/model_comparison.csv) · [复现与文件说明](REPRODUCE.html)
""",
"## 1. 研究结论与实际改善幅度",
"""不同干支的历史平均幅度、事件比例确实有可见差异，但这些差异没有超出本轮保留波动聚集的置换检验可解释的随机范围。控制近期波动与星期后，干支修正没有提供可靠的样本外增量。

C 表示近期波动状态模型，F 表示加入已知星期信息的基准。**宏观历史预告版本不全：严格F/G主版本未使用最终公布日，宏观日期只在明确标记的条件性对照中使用。**\n\n最重要的结果来自加入干支前后的同基准比较：E 对 C、G 对 F，而不是只看 E 是否超过全历史或30日均值。主区间为 2023-01-01 至 2026-10-20，共 **1,389 天**；扩展区间 2021-01-01 至同日，共 **2,119 天**。
"""]
rows=[]
for t in TARGETS:
    metric="rmse" if t in CONT else "brier"
    rows.append([LABEL[t],pct(S[t,"C"][metric],4) if t in CONT else val(S[t,"C"][metric],6),
                 pct(S[t,"E"][metric],4) if t in CONT else val(S[t,"E"][metric],6),
                 f"{100*(1-S[t,'E'][metric]/S[t,'C'][metric]):+.3f}%",
                 pct(S[t,"F"][metric],4) if t in CONT else val(S[t,"F"][metric],6),
                 pct(S[t,"G"][metric],4) if t in CONT else val(S[t,"G"][metric],6),
                 f"{100*(1-S[t,'G'][metric]/S[t,'F'][metric]):+.3f}%"])
parts.append(table(["目标","C","E= C+干支","E 改善","F","G= F+干支","G 改善"],rows))
parts.append("""连续目标表中使用 RMSE，事件目标使用 Brier，均越低越好；改善为相对减少百分比，负值表示变差。**E 对 C 和 G 对 F 的所有主检验，经 88 项 Holm 校正后均未显著。**

开收绝对幅度的 G 相对 F，RMSE 仅降低约 0.043%；日内振幅反而增加约 0.180%。5% 开收大行情的 Brier 小幅改善约 0.450%，但 2%、3% 档变差，且5%改善未获得统计确认。不能把这项小幅有利结果单独宣传为干支有效。

历史排名与真正验证的排名不同：60 个干支中，没有一个通过本研究的样本外分组验证标准。附表仍完整列出历史排名和所有检验，不把排名最高者写成“未来高波动日”。
""")
parts.append("![模型误差](results/model_rmse.png)\n\n![独立增量与区间](results/incremental_effects.png)")
parts.append("## 2. 数据核对与有效性")
parts.append(f"""仓库远端为 Lammmmm/jiexu-btc，本地正式代码基线 {manifest['git_head']}。行情来源为仓库 Binance BTCUSDT 现货日线，按 Asia/Shanghai（UTC+8）自然日；干支标签直接使用本地历法数据库，验证每日按 60 循环。实际可用起点是 **2017-08-18**，没有补造 2017 年 1 月行情。

冻结原始记录 {aud['raw_n']} 根，包含上市首日与尚未完成的 2026-10-21；最新完整日线为 **2026-10-20**。研究全部使用这份固定快照，后续行情自动更新不改变此次结果。快照 SHA-256：{manifest['source_sha256']}。
""")
parts.append(table(["规则","有效全历史","2023年以来","首/末有效日"],[
    [name,r["n"],r["n_2023"],r["first"]+" → "+r["last"]] for name,r in aud["counts"].items()]))
parts.append("""oc 为开收与日内振幅的自身有效规则，cc 为昨收规则，common 是二者交集。排除上市日、未收盘日，以及源收盘时间异常的 2018-02-08、2020-02-19、2020-12-21；昨收口径另排除上述异常日的下一日。

**所有模型和所有目标的训练、测试采用 common 规则**，避免某个模型多用几条异常附近数据。历史描述附表保留各目标自身有效规则，所以开收/振幅全历史样本比 common 多 3 条；这三条都早于主测试区间。每条预测保留当时同干支全历史样本数、2023年以来样本数、干支残差训练样本数及训练收盘上界。

已与正式服务逐干支核对有效样本和 2/3/5% 原始门槛计数，840 项核对通过。研究进程只读正式数据库。
""")
parts.append("## 3. 目标、信息时点和模型定义")
parts.append("""三个连续目标分别为 |C/O−1|、|C/Cprev−1|、(H−L)/O。百分比仅用于显示，程序内部用小数。开收和昨收分别建立模型，不互相替代。

事件目标为开收和昨收各自的绝对涨跌 ≥2%、≥3%、≥5%，以及独立的日内振幅 ≥5%、≥10%。门槛从原始十进制价格计算，使用 Decimal 判断，不使用显示四舍五入后的数值。收盘大行情和日内极端振幅从未混成一类。

这是提前预测当日波动的研究，不是开盘成交交易回测。主预测在目标日 00:00 发出，只能使用此前收盘时间严格早于该时刻的完整日线，通常可以使用 d−1。没有使用当日 O/H/L/C、成交量、当日宏观结果或之后价格作为输入。若真实部署要求收到日线后再计算，可稍延迟发出预警；本研究不声称日界线零延迟成交。最初方案曾考虑前日23:59，首次计算前已书面澄清为日界线信息集，初版协议保留。

基础状态特征包括过去已知幅度的上一日、7/14/30/90 日均值，近期日内振幅7/30日均值、开收绝对幅度7/30日均值；事件模型另使用平滑后的近期事件比例。目标历史窗口内无效日直接排除，不填造价格。星期几为预先已知的日历信息。

C/F 参数每月滚动重估，使用过去1095个公历日的训练标签，每天更新输入状态；每次在历史最后252条可用记录上做3段顺序验证，选择正则强度1/10/100。连续模型拟合 log(幅度+1e−6)，用训练期残差的 smearing 因子还原条件均值；概率模型用正则 logistic 回归。连续预测均值主要用 RMSE/MSE 检验，MAE同时报告，不能仅凭MAE判断均值预测有效。
""")
parts.append(table(["模型","内容"],[
 ["A","所有已知历史的无条件均值/事件基准"],
 ["B30","过去30个公历日平均幅度；概率采用Beta(1,1)平滑"],
 ["C7/C14/C90/C365","固定7/14/90/365日近期基准"],
 ["Cewma","14日半衰期指数近期基准"],
 ["C","多时间尺度近期波动状态模型"],
 ["D_raw","各干支独立全历史统计；概率有Beta(1,1)平滑"],
 ["D","各干支全历史统计，向同窗口整体均值收缩20个伪样本"],
 ["D_2023","2023年以来同干支统计，向2023年以来整体均值收缩20；初期整体不足30条时回退D"],
 ["E30","B30 + 从历史预测残差学习的干支修正"],
 ["E","C + 从历史预测残差学习的干支修正"],
 ["F","近期状态 + 星期；严格主版本的宏观历史预告缺失，未冒用最终公布日"],
 ["G","F + 干支修正"],
 ["F_retro / G_retro","加入最终CPI/非农日期的条件性对照，仅作回顾敏感性"]]))
parts.append("""E/G 的干支效应来自过去真正发出过的基础预测与之后实际幅度之间的偏差，不使用当前模型在训练集上的拟合残差。连续修正做样本收缩并减去整体偏差；概率修正在 logit 空间估计并按历史频数居中，避免把一般校准改善冒称为干支作用。

干支正则强度20/60/180/关闭，在过去的3段顺序验证中选择。允许关闭；同损失时优先关闭。选择、效应拟合与窗口都只使用当时已收盘的标签。早期用于建立诚实残差的回溯预测从2018年7月开始，2017—2020年没有冒充主测试结果。每个目标/模型共享全部测试日，没有按事后表现筛选干支或删日期。
""")
parts.append("## 4. CPI、非农与严格历史版本的限制")
parts.append("""**这是本研究最重要的数据限制。** 仓库经济日历是2026年抓取的最终发布日期和未来日程，不是逐年留存的历史预告快照。最终某日确实公布，不等于该日期在历史预测时就可提前确认；延期、取消和特殊日程会使这种区别真实存在。

核对后，在已完成行情范围内，没有一条“抓取时已是未来日程、且抓取早于该日开始”的可证明提前已知事件记录。因此主 F/G 使用近期波动与星期，不把未证实的宏观预告当成零事件，更不把最终发布日期悄悄塞进严格主预测。**完整的历史宏观日历 F/G 可执行检验，在现有仓库数据下尚无法确认。**

为尽可能控制混淆，另做两种明确不同用途的分析：历史关联检验可以条件化最终已知的 CPI/非农日期，因为它只解释历史关联；F_retro/G_retro 则用这些日期训练和评分，作为“假设这些日期当时都能提前获知”的条件性敏感性。后者不进入17模型中的可部署主模型结论，也不能替代真正的日程版本数据。它同样没有产生可靠干支增量。

如将来继续宏观风险预警，应先积累带有抓取时间、修改时间、原计划日期和实际日期的历史日程版本；当前结果不能宣称已经彻底验证了真实宏观预警能力。
""")
parts.append("## 5. 全部模型：幅度预测与排序")
for t in CONT:
    parts.append("### "+LABEL[t])
    rows=[]
    for m in MODELS:
        r=S[t,m]
        rows.append([m,r["n"],pct(r["mae"],4),pct(r["rmse"],4),
            f"{100*(1-r['rmse']/S[t,'B30']['rmse']):+.2f}%",val(r["spearman"],3),pct(r["top10_mean_actual"]),val(r["top10_lift"],2)])
    parts.append(table(["模型","测试日","MAE","RMSE","RMSE相对B30改善","Spearman","前10%预测日实际均幅","前10%幅度提升倍数"],rows))
parts.append("""高波动排序不只看平均误差，还看预测最高10%日期是否实际更剧烈。该10%是同一测试区间内按预测分数分配的统一评估配额，用于公平比较排序，未用实际结果挑选；它不是可事先知道整个未来区间分数分位点的交易规则。在线阈值的独立结果见后文。
""")
parts.append("## 6. 全部模型：大行情概率预测")
for t in BIN:
    parts.append("### "+LABEL[t]+f"；实际发生 {S[t,'A']['events']} / {S[t,'A']['n']}（{pct(S[t,'A']['actual_mean'])}）")
    parts.append(table(["模型","Brier","Log Loss","ROC-AUC","PR-AUC(AP)","校准ECE","最高10%预警发生率","捕获全部事件比例"],[
        [m,val(S[t,m]["brier"],6),val(S[t,m]["logloss"],5),val(S[t,m]["roc_auc"],3),val(S[t,m]["pr_auc_ap"],3),
         pct(S[t,m]["ece10"]),pct(S[t,m]["top10_event_rate"]),pct(S[t,m]["top10_recall"])] for m in MODELS]))
parts.append("""PR-AUC 主列使用 Average Precision（阶梯式 PR 面积），另外保存梯形积分版本。ECE 是固定10个概率区间的诊断，对样本量和分箱敏感；不能把 ECE 最小等同于最好的概率模型。Brier和Log Loss同时衡量概率质量；未报告“几乎全猜没有大行情”的普通准确率来冒充成功。

极端日内振幅≥10%在主区间只有21次，各干支通常0—2次；5%开收大行情也只有67次。这种频率不足以支持稳定的逐干支概率排名。
""")
parts.append("![概率校准](results/calibration.png)")
# Continue below.

parts.append("## 7. 干支增量的配对检验与置信区间")
parts.append("""主检验为同日、同目标的损失差：3个连续目标各检验MSE/MAE，8个概率目标各检验Brier/Log Loss，共22个端点；4组比较为 E30 对 B30、E 对 B30、E 对 C、G 对 F，共88项一起Holm校正。

采用60日循环区块bootstrap，20,000次；同一次重采样对全部模型共享相同日期，保留一段时间的波动聚集。双侧检验使用中心化的配对损失差，最小Monte Carlo p=1/20,001，未报告伪零p。另用14/180日区块各10,000次检查敏感性。区块假设不能消除BTC长期非平稳，故同时报告逐年、环境和训练剔除检验。
""")
rows=[]
for t in TARGETS:
    metric="se" if t in CONT else "brier"
    for ref,cand in [("B30","E"),("C","E"),("F","G")]:
        r=next(r for r in PAIR if r["target"]==t and r["reference"]==ref and r["candidate"]==cand and r["metric"]==metric)
        rows.append([LABEL[t],cand+" / "+ref,f"{r['relative_improvement']*100:+.3f}%",
            f"[{r['ci_low']/r['ref_mean']*100:+.3f}%, {r['ci_high']/r['ref_mean']*100:+.3f}%]",val(r["p_holm"],4)])
parts.append(table(["目标","比较","损失减少","95%点态区间¹","Holm p"],rows))
parts.append("""¹ 区间是配对平均损失差除以参考模型实测平均损失的归一化表示；连续使用MSE，不是RMSE相对区间。区间未做同时校正，显著性判断以Holm p为准。

E对B30有少数显著改善，但C本身已经比B30更好，加入干支的E通常没有比C更好；把“更好的近期状态模型”带来的进步算给干支，是错误归因。E对C、G对F的全部主端点均未通过校正。14/180日区块与2021起扩展检验也未提供可靠的独立干支改善。

ROC-AUC与PR-AP另有32项探索性配对区块检验和区间，同样没有通过自身Holm校正。它们不替代主损失指标，也不把个别有利的排序数字当作确认性成功。
""")
rankci=read("ranking_intervals.json")
parts.append(table(["目标","比较","ROC-AUC变化","ROC 95%区间","AP变化","AP 95%区间"],[
    [LABEL[t],cand+" / "+ref,
     f"{next(r['delta'] for r in rankci if r['target']==t and r['reference']==ref and r['metric']=='roc_auc'):+.4f}",
     "["+", ".join(f"{next(r[k] for r in rankci if r['target']==t and r['reference']==ref and r['metric']=='roc_auc'):+.4f}" for k in ["ci_low","ci_high"])+"]",
     f"{next(r['delta'] for r in rankci if r['target']==t and r['reference']==ref and r['metric']=='pr_auc_ap'):+.4f}",
     "["+", ".join(f"{next(r[k] for r in rankci if r['target']==t and r['reference']==ref and r['metric']=='pr_auc_ap'):+.4f}" for k in ["ci_low","ci_high"])+"]"]
    for t in BIN for ref,cand in [("C","E"),("F","G")]]))
parts.append("## 8. 相同预警比例能多识别多少大行情")
parts.append("""下表各模型均选取同一批测试日中预测概率最高的10%，共139天；20%配额为278天。相同分数用与结果无关、对所有模型一致的日期哈希打破平局，避免某个模型因平局处理多报警。实际发生率与召回率都来自未来真实结果。
""")
parts.append(table(["事件","预警比例","C发生率","E发生率","F发生率","G发生率","F召回","G召回"],[
    [LABEL[t],f"{q}%",*[pct(S[t,m][f"top{q}_event_rate"]) for m in ["C","E","F","G"]],
     pct(S[t,"F"][f"top{q}_recall"]),pct(S[t,"G"][f"top{q}_recall"])]
    for t in BIN for q in [10,20]]))
parts.append("""例如3%开收大行情，F的最高10%预警日实际发生率30.94%，加入干支后的G为29.50%，反而少识别2个事件。5%开收大行情则由7.91%变为9.35%，只多识别2个事件；该档共67次，不能据此确认稳定改善。日内振幅≥5%的最高10%预警发生率，F/G同为45.32%。

另采用可实际提前执行的分位阈值：每一天只与该模型过去365日已发出预测的80/90分位比较；阈值不依赖未来预测或未来结果。因为市场环境变化，实际报警比例不会恰好10%或20%，因此同时报告真实比例，不能把它和固定配额混称。
""")
online=read("online_alerts.json")
parts.append(table(["事件","模型","历史阈值名义10%","实际报警比例","报警日发生率","总体发生率","事件召回"],[
    [LABEL[t],m,"90分位",pct(next(r["actual_fraction"] for r in online if r["target"]==t and r["model"]==m and r["nominal_fraction"]==.1)),
     pct(next(r["actual_mean_alert"] for r in online if r["target"]==t and r["model"]==m and r["nominal_fraction"]==.1)),
     pct(S[t,m]["actual_mean"]),pct(next(r["event_recall"] for r in online if r["target"]==t and r["model"]==m and r["nominal_fraction"]==.1))]
    for t in ["oc2","oc3","oc5","range5","range10"] for m in ["C","E","F","G"]]))
parts.append("### 干支模型明显抬高风险的日期，未来是否兑现")
parts.append("""另外预先定义相对明显的抬高：事件概率较基础模型增加至少5个百分点；连续幅度预测增加至少20%。以发出的预测本身选择日期，再观察真实结果，未按真实结果筛选。

3%开收事件中，G比F抬高至少5个百分点的44天，G平均预测约34.76%，F约27.46%，真实只发生22.73%，没有兑现额外风险。5%档只有13天，实际15.38%，G预测18.91%，F预测12.59%；只有2次事件，样本过少。日内振幅≥10%主版本根本没有符合5个百分点抬高的日期。完整所有目标见 elevated_ganzhi_predictions.json，零样本项明确为空，不给伪准确率。
""")
parts.append("## 9. 历史差异与保留波动聚集的置换")
parts.append("""不能随机逐日打乱行情，因为那会破坏波动聚集，夸大证据；也不能把整个60日序列平移一个固定相位，因为这主要只是给60个干支重新命名，整体组间差异会保持不变。

主关联检验先控制年份、近期多尺度波动状态、星期以及实际CPI/非农公布日，再检验加入59个独立干支对比能解释多少剩余变化。这里的最终宏观日期只作**回顾控制变量**，没有当作严格预测输入。之后在每个公历年内分别做随机循环旋转残差，保留该年分布和绝大部分局部波动聚集，打破不同年份之间固定干支相位的对应；9999次。另用年内14/28日区块重排各1999次检查稳健性。

两个时期×11目标共22项关联检验一起Holm校正。需要90条已知历史来构造近期状态，因此全历史条件检验从2017年稍晚日期开始，共3255天；历史描述表仍使用实际最早有效数据。置换是条件交换性假设下的近似，无法保证任意非平稳过程下精确有效，因此预测验证才是核心。
""")
parts.append(table(["时期","目标","样本数","干支部分R²","旋转p","Holm p"],[
    [r["window"],LABEL[r["target"]],r["n"],pct(r["partial_r2"]),val(r["p"],4),val(r["p_holm"],4)]
    for r in O if r["method"]=="rotation"]))
parts.append("""所有主关联检验均未显著；14/28日区块敏感性也没有提供通过校正的关联证据。59个自由干支对比本来就会在样本内解释一些噪声；例如近期样本部分R²约3%—4%，不能把这个拟合比例直接叫作预测能力。

历史上每个干支全历史只有54—56条有效日线，2023年以来只有23—24条。近期3%大行情率的历史组别范围可从约4.35%到30.43%，5%率可从0到16.67%，看起来很大，但分母仅约23，少一两次就会改变排名。年度匹配的组别差异区间采用年度聚类t近似，再对60×11×2=1320项做Holm/BH校正，没有可靠显著的干支。

年度簇只有约4个的近期区间非常不精确，年与年之间也可能相关。这些区间是历史均值差的研究性不确定性描述，不是未来单日波动的预测区间，也不证明“干支绝对没有任何效应”。
""")
parts.append("### 历史高波动排行示例（不能当作已验证预警名单）")
parts.append(table(["时期","指标","历史名次","干支","样本","平均幅度","中位数","普通BTC均值"],[
    [window,LABEL[t],r["historical_rank"],r["ganzhi"],r["n"],pct(r["mean"]),pct(r["median"]),pct(r["baseline_mean"])]
    for window in ["all","2023"] for t in ["abs_oc","range"]
    for r in sorted([x for x in D if x["window"]==window and x["target"]==t],key=lambda x:x["historical_rank"])[:5]]))
parts.append("## 10. 历史高波动干支能否在未来重复")
parts.append("""追加一个直观的探索性留出检验：仅用2017—2022年已知行情，为每个目标锁定历史平均值最高的10个干支，然后在2023年之后不再换名单。这样“高风险名单”不会使用2023年之后的真实结果来挑选。

主表为高组和其余50干支的未来差异；另对实际减去F预测后的残差做同样比较，控制近期状态与星期。22项检验一起校正。该分析是在主规格之外补充的研究对照，不把其个别有利结果当新的确认性发现。
""")
held=read("heldout_pre2023_top10.json")
parts.append(table(["目标","高组未来样本","高组实际均值/率","其余实际均值/率","差异","95%差异区间","Holm p"],[
    [LABEL[r["target"]],r["n_high"],pct(r["high_mean"]),pct(r["low_mean"]),signed(r["delta"]),
     f"[{signed(r['ci_low'])}, {signed(r['ci_high'])}]",val(r["p_holm"],4)] for r in held if r["metric"]=="actual"]))
parts.append("""5%开收档有一个值得保留的探索性数字：高组未来发生率6.87%，其余4.41%，差约2.46个百分点；但95%区间约为[−0.94，+6.18]个百分点，校正后p=1。它可以是后续假设，不能作为稳定的高风险名单。年份切片和固定名单保存于 heldout_pre2023_top10_yearly.json / heldout_pre2023_top10.json。

逐干支的E−C和G−F样本外损失差还单独做1320项校正，要求改善为正、至少3个主测试年份同向、样本≥15，事件目标还要求至少5次事件。**通过者为0。** 因而没有“真正通过验证的高波动干支排行”；附表把历史排名与验证状态分列，未强行排出未来赢家。
""")
parts.append("## 11. 跨年份、牛熊周期与稳健性")
parts.append("以下逐年表使用核心模型；全部17模型、全部目标和2021/2022扩展结果见 yearly_models.csv。2026年为截至10月20日的部分年份。")
for t in ["abs_oc","abs_cc","range","oc2","oc3","oc5","range5","range10"]:
    parts.append("### "+LABEL[t])
    metric="rmse" if t in CONT else "brier"
    rows=[]
    for year in ["2023","2024","2025","2026"]:
        rr={m:next(r for r in Y if r["year"]==year and r["target"]==t and r["model"]==m) for m in ["B30","C","E","F","G"]}
        fmt=lambda v:pct(v,4) if t in CONT else val(v,6)
        rows.append([year,rr["C"]["n"]]+[fmt(rr[m][metric]) for m in ["B30","C","E","F","G"]]+
                    [f"{100*(1-rr['E'][metric]/rr['C'][metric]):+.2f}%",f"{100*(1-rr['G'][metric]/rr['F'][metric]):+.2f}%"])
    parts.append(table(["年","样本","B30","C","E","F","G","E改善","G改善"],rows))
parts.append("""5%概率档有数年微小改善，2026又有所反转；3%档多数年份变差或干支效应被验证关闭。日内振幅的干支修正几乎没有跨年增益。2021起扩展区间，E−C/G−F主端点仍全部不显著，没有通过换测试起点得到稳定成功。

牛熊标签仅用预测时已知的最近收盘相对200日均线及90根有效日线收益（高于均线且>10%为牛，低于且<−10%为熊，其余震荡）。全部环境表现见 regime_models.csv；这是固定操作定义，没有用事后峰谷划分牛熊。
""")
parts.append(table(["目标","环境","样本","C","E","F","G","G相对F改善"],[
    [LABEL[t],{"bull":"牛","bear":"熊","range":"震荡"}[reg],
     next(r["n"] for r in REG if r["target"]==t and r["regime"]==reg and r["model"]=="F"),
     *[(pct(next(r["rmse"] for r in REG if r["target"]==t and r["regime"]==reg and r["model"]==m),4)
        if t in CONT else val(next(r["brier"] for r in REG if r["target"]==t and r["regime"]==reg and r["model"]==m),6)) for m in ["C","E","F","G"]],
     f"{100*(1-next(r['rmse' if t in CONT else 'brier'] for r in REG if r['target']==t and r['regime']==reg and r['model']=='G')/next(r['rmse' if t in CONT else 'brier'] for r in REG if r['target']==t and r['regime']==reg and r['model']=='F')):+.2f}%"]
    for t in ["abs_oc","range","oc3","oc5"] for reg in ["bull","bear","range"]]))
parts.append("### 极端年份、极端值与训练稳健性")
parts.append("""保留原始数据为主结果；另外分别从训练标签中排除2020、2021、2022年，重新进行滚动拟合和内部选择。预测输入仍是当时实际可知的近期市场状态，未假装这些年份没有发生。主测试真实目标始终不删。另将连续目标的训练值按当时训练集99分位封顶；事件标签保持原始定义，二元结果不做任意截断。

下表展示加入干支后的损失改善，连续用MSE、事件用Brier。所有稳健性检验中的E−C/G−F仍未形成经校正的正面证据。
""")
parts.append(table(["处理","目标","E对C损失减少","G对F损失减少"],[
    [v,LABEL[t],
     f"{100*(1-next(r['mse' if t in CONT else 'brier'] for r in ROB if r['variant']==v and r['target']==t and r['model']=='E')/next(r['mse' if t in CONT else 'brier'] for r in ROB if r['variant']==v and r['target']==t and r['model']=='C')):+.3f}%",
     f"{100*(1-next(r['mse' if t in CONT else 'brier'] for r in ROB if r['variant']==v and r['target']==t and r['model']=='G')/next(r['mse' if t in CONT else 'brier'] for r in ROB if r['variant']==v and r['target']==t and r['model']=='F')):+.3f}%"]
    for v in ["cap99","omit_2020","omit_2021","omit_2022"] for t in ["abs_oc","abs_cc","range","oc2","oc3","oc5","range5","range10"]]))
parts.append("""封顶版本的事件结果与主版本完全相同，因为事件标签和状态输入都未改，并没有把相同结果虚称为独立的第二份概率证据。另保存历史描述逐年删除的排名敏感性 CSV，及仅用于诊断的删去测试目标最大1%日期后的评分；后者利用了事后结果，不是可以提前执行的过滤器。
""")
parts.append("## 12. 现有2017方向 + 2023强度设计是否合理")
cut={(r["target"]):r for r in read("cutoff_unconditional_comparison.json")}
parts.append("""从历史分布与此次预测看，2017年以来的全历史幅度均值对近期波动水平往往偏高。2023年以来的统计更接近近年的整体水平，作为**明确标注时期的历史描述**有理由保留；但这不支持“某干支的2023统计就是下一次波动预测”。

为区分“近期分布更匹配”和“干支真的有用”，补充同样自2023年以来的普通BTC整体基准A_2023；它与D_2023都只使用当时已知的2023年之后历史，初期整体少于30条时回退全历史。此补充只检验固定起点解释，不改变主模型及主88项检验。
""")
parts.append(table(["目标","全历史A","全历史D","2023整体A_2023","2023干支D_2023","30日B30","近期状态C","状态+星期F"],[
    [LABEL[t],*[(pct(S[t,m]["rmse"],4) if t in CONT else val(S[t,m]["brier"],6)) for m in ["A","D"]],
     pct(cut[t]["rmse"],4) if t in CONT else val(cut[t]["brier"],6),
     *[(pct(S[t,m]["rmse"],4) if t in CONT else val(S[t,m]["brier"],6)) for m in ["D_2023","B30","C","F"]]]
    for t in ["abs_oc","range","oc2","oc3","oc5","range5","range10"]]))
parts.append("""连续幅度的A_2023已经优于D_2023，说明近期口径的主要好处来自市场波动环境更匹配，不能归功于干支。滚动近期模型还更能适应时间变化，所以没有证据认为“2023年1月1日”是长期最优、永远固定的预测切点。

概率短窗口使用Beta(1,1)会对稀有事件有平滑偏差，特别是7日窗口。为避免主结论依赖一个偏弱基准，另补充原始比例截断、Jeffreys平滑和2样本整体先验三种滚动概率基准，见 probability_prior_sensitivity.json。它们作为基准敏感性，不按测试结果替换主B30；核心E对C、G对F也不依赖该平滑选择。

关于2017年以来方向胜率：本研究没有重新检验方向，因此不能用波动结果来证明方向预测有效。分开显示方向与强度的历史统计在计算口径上可以成立，但需要各自明确样本时期、样本数和“历史描述”身份；不能混算一个未经验证的收益或预警分数。是否调整生产展示，应由用户审核后另行决定，本轮没有改动。
""")
parts.append("## 13. 九个问题的明确回答与开发建议")
answers=[
("不同干支之间是否有显著波动差异？","历史点估计有明显高低；控制环境并保留聚集结构后，没有经校正的显著关联证据。不能把样本内排名当成规律。"),
("开收绝对幅度和日内振幅，哪个更适合干支预测？","没有证据支持其中任何一个具有可靠干支增量。G对F开收RMSE约好0.043%，日内振幅约差0.180%，均不显著；普通近期状态对振幅的解释较强，不是干支作用。"),
("是否有干支的大行情率稳定高于普通BTC？","没有识别到通过分组样本外与多重校正的名单。历史高组5%档的未来率有正向点差，但区间跨零且分年不稳。"),
("干支能提升2/3/5%概率预测吗？","2%、3%多数比较略差；5%档有不到0.5%的相对Brier改善，但未经统计确认，不能只挑这一档开发。"),
("相比普通波动模型实际改善多少？","见核心增量表。总体接近零，常为负；E对30日基准的进步主要由C近期状态本身提供，不能归因干支。"),
("能跨年和牛熊维持吗？","没有稳定维持。2021起扩展检验、逐年、环境及训练剔除均未确认增量。"),
("哪些可能是随机现象？","历史最大/最小干支、少量5%事件带来的高比例、单一阈值的微小改善，以及在很多检验中出现的个别点态区间。样本与有效年度不足是主要限制。"),
("是否有风险预警或仓位应用价值？","近期波动状态与星期基准有一定排序能力，可作为另一个研究方向；本轮没有支持给干支额外加风险权重。没有方向信息及可执行衍生品价格，不能把波动预测宣称成盈利策略或已验证仓位规则。"),
("现有2017方向、2023强度设计是否保留？","作为分时期的历史描述可以保留；2023强度较贴近近期分布，但没有干支独立预测证据，也未证明固定2023切点最优。本研究不能替方向预测背书。")]
parts.extend([f"**{i}. {question}**\n\n{answer}" for i,(question,answer) in enumerate(answers,1)])
parts.append("""**最终选择 C。** 在这份仓库数据、此次严格信息集、固定目标和检验范围内，未证明六十甲子具有可重复、可实用的独立波动预测价值，不建议投入正式干支预测模型开发。这个决定不等于证明任何极小效应永远不存在，而是当前证据不足以支持开发成本和使用者的预测信任。

应避免把“未显著”解释成已证明完全无效，也避免把少数有利点估计解释成成功。若未来要推翻当前结论，应先锁定模型、补齐宏观日程历史版本，再积累尚未看过的新行情进行确认，不能继续在同一段历史上调窗口、改阈值直到好看。
""")
parts.append("## 14. 复现、验证和证据范围")
parts.append(f"""独立代码位于本研究目录，没有导入前两轮方向EV研究模型。14项单元测试已实际通过；包括原始门槛精度、未来数据不改变当前特征与拟合、正则回归与scikit-learn对照、宏观版本限制、概率区间、固定报警配额及加权ROC/AP含平局算法。

另从原始行情重新构建 **{verification['feature_scalar_fields']}个特征字段、{verification['baseline_and_count_fields']}个基准预测/样本数字段**，并用scikit-learn独立复核真实月份的 **{verification['sklearn_monthly_predictions']}个C/F预测**。主导出含 {verification['total_prediction_rows']:,} 条记录、17个模型、11个目标；已验证训练收盘严格早于预测、测试日期全部一致、60干支全部覆盖。正式有效性与阈值规则另有840项核对通过。

结果包含所有主窗口、所有阈值和不利结果，没有只展示赢家。历史版本缺失、少数极端事件、少量年度簇、日线粒度和非平稳性仍限制结论。仓库行情是当前保存版本，无法验证逐日历史修订；源数据与报告都已哈希冻结，便于复算。
""")
parts.append("""## 15. 方法来源

行情、历法和事件记录全部来自仓库冻结快照；以下仅用于方法核对。

- [scikit-learn：概率校准](https://scikit-learn.org/stable/modules/calibration.html)：概率评分与校准不能混为同一个指标。
- [scikit-learn：模型评估](https://scikit-learn.org/1.6/modules/model_evaluation.html)：ROC、PR、Brier与Log Loss的含义与使用。
- [Politis：区块重采样原始研究目录](https://mathweb.ucsd.edu/~politis/DPpublication.html)：依赖数据重采样背景。本研究的年内旋转零假设为明确的近似设计，不宣称该文直接保证其有限样本有效性。
- [Cameron / Miller：聚类稳健推断](https://escholarship.org/uc/item/1jq5d0pq)：少簇与不均衡聚类的限制；本研究有效年度自由度也是研究性近似。
- [statsmodels：多重检验](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)：Holm/BH实现。主结论以Holm为准。
""")
CSS="""
*{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#1f2937;font:15px/1.85 "Microsoft YaHei",sans-serif}
main{max-width:1300px;margin:24px auto;background:white;padding:38px 46px;border:1px solid #dbe3ed;border-radius:12px}
h1{font-size:28px;line-height:1.5;color:#173d65;margin:0 0 22px}h2{font-size:22px;margin-top:40px;padding-top:24px;border-top:1px solid #e4e9f1}
h3{font-size:17px;margin-top:28px}strong{color:#173d65}p,li{overflow-wrap:anywhere}a{color:#1766a4}
.table-wrap{max-width:100%;overflow-x:auto;margin:20px 0;border:1px solid #dbe3ed;border-radius:6px}
table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}td,th{padding:8px 11px;border-bottom:1px solid #e5eaf1;text-align:left}
th{background:#edf2f7;color:#274867}tr:nth-child(even){background:#f8fafc}img{display:block;max-width:100%;height:auto;margin:28px auto}
pre{overflow-x:auto;background:#edf2f7;padding:16px;border-radius:6px}code{font-family:Consolas,monospace;font-size:13px}
@media(max-width:700px){body{font-size:14px}main{padding:18px 15px;border:0;margin:0}h1{font-size:23px}h2{font-size:20px}}
@media print{main{margin:0;padding:0;border:0}h2,h3{break-after:avoid}img{break-inside:avoid}table{font-size:8px}}
"""
def save(name,text):
    (ROOT/(name+".md")).write_text(text,encoding="utf-8")
    rendered=markdown.markdown(text,extensions=["tables","fenced_code"])
    rendered=rendered.replace("<table>","<div class='table-wrap'><table>").replace("</table>","</table></div>")
    out="<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+name+"</title><style>"+CSS+"</style></head><body><main>"+rendered+"</main></body></html>"
    (ROOT/(name+".html")).write_text(out,encoding="utf-8")
save("REPORT","\n\n".join(parts))
# Appendix follows below.

appendix=["# 六十干支完整统计与样本外验证附表",
"[返回主报告](REPORT.html) · [60行宽表CSV](results/sixty_ganzhi_statistics.csv) · [全部历史统计及区间CSV](results/ganzhi_descriptive.csv) · [样本外验证CSV](results/ganzhi_oos.csv)",
"""历史排名以该时期完整结果排序，属于回顾描述，不能用于回看预测。样本外表中的预测由当时可知信息滚动产生；按原始干支顺序排列，没有强行排出“已验证赢家”。全部60干支均覆盖。百分数是幅度或事件率，正负差异为百分点。年度聚类区间是研究近似，Holm p对1320项共同校正。"""]
for window in ["all","2023"]:
    for t in CONT:
        appendix.append("## "+("全部历史" if window=="all" else "2023年以来")+" · "+LABEL[t])
        selected=sorted([r for r in D if r["window"]==window and r["target"]==t],key=lambda r:r["historical_rank"])
        rows=[]
        thresholds=["range5","range10"] if t=="range" else [("oc" if t=="abs_oc" else "cc")+str(n) for n in [2,3,5]]
        for r in selected:
            rates=[pct(next(x["mean"] for x in D if x["window"]==window and x["target"]==threshold and x["g"]==r["g"])) for threshold in thresholds]
            rows.append([r["historical_rank"],r["ganzhi"],r["n"],r["n_since2023"],pct(r["mean"]),pct(r["median"]),pct(r["baseline_mean"]),
                signed(r["year_matched_difference"]),f"[{signed(r['ci_low'])}, {signed(r['ci_high'])}]",val(r["p_holm"],4)]+rates)
        appendix.append(table(["历史名次","干支","n","其中2023+","均值","中位数","整体均值","年匹配差","95%差异区间","校正p"]+[LABEL[k] for k in thresholds],rows))
oos=read("ganzhi_oos.json")
appendix.append("## 真正的样本外分组结果")
appendix.append("主区间2023—2026-10-20。连续目标的损失是MSE，事件目标是Brier。损失减少=基础模型−加入干支模型，正值较好；表中科学计数法使用原始小数平方单位，不是收益百分比。没有一个干支达到预设验证标准，因此不生成通过验证的高波动排名。")
for t in TARGETS:
    appendix.append("### "+LABEL[t])
    rows=[]
    for g in range(60):
        a=next(r for r in oos if r["target"]==t and r["g"]==g and r["reference"]=="C")
        b=next(r for r in oos if r["target"]==t and r["g"]==g and r["reference"]=="F")
        rows.append([a["ganzhi"],a["n"],pct(a["actual_mean"]),
            f"{a['loss_improvement']:+.3e}",f"[{a['ci_low']:+.3e}, {a['ci_high']:+.3e}]",val(a["p_holm"],4),
            f"{b['loss_improvement']:+.3e}",f"[{b['ci_low']:+.3e}, {b['ci_high']:+.3e}]",val(b["p_holm"],4),
            "通过" if b["passes_validation"] else "未通过"])
    appendix.append(table(["干支","测试n","实际幅度/率","E−C损失减少","E−C 95%区间","E−C校正p","G−F损失减少","G−F95%区间","G−F校正p","验证"],rows))
appendix.append("完整CSV另有事件数、各年同向改善次数、原始p、BH p及有效年度数。没有提供空洞的预测赢家列表。")
save("GANZHI_APPENDIX","\n\n".join(appendix))
fence=chr(96)*3
repro="""# 波动强度研究：复现、字段和输出索引

[完整报告](REPORT.html) · [六十干支附表](GANZHI_APPENDIX.html)

## 范围与冻结数据

所有新增文件位于 research/ganzhi_volatility_2026-10-21，研究代码不导入生产计算或此前EV模型。snapshot.json包含真实OHLC原始字符串、收盘时间、干支标签、行情同步时刻、仓库两份宏观日历快照。manifest.json记录源哈希与正式代码基线；protocol.json为主规格，protocol.initial.json保留首次计算前的时间边界澄清前版本。完整最终文件清单见bundle_manifest.json。

主样本外2023-01-01—2026-10-20；扩展2021-01-01—2026-10-20。2018-07起的较早回溯只用于产生诚实的历史基础预测残差。所有预测只用目标日开始之前收盘的信息，不进行交易收益模拟。

主规格之外的历史锁定前10组、固定2023整体基准与短窗口先验公平性比较为探索性补充。不能将这些试验中的个别有利结果当额外确认性证据。所有分母、原始结果与不利结果均保留。

## 建立独立研究环境

使用Python3.12，在仓库根目录运行：
"""
repro+=fence+"""powershell
python -m venv research/ganzhi_volatility_2026-10-21/.venv
& .\\research\\ganzhi_volatility_2026-10-21\\.venv\\Scripts\\python.exe -m pip install -r research/ganzhi_volatility_2026-10-21/requirements-research-lock.txt
"""+fence
repro+="""

研究依赖只安装在该目录的虚拟环境，正式项目环境没有改动。Windows若普通沙箱阻碍pip或研究进程，应以受授权的本地执行方式运行；不需要更改系统环境变量或生产requirements。

## 执行

主研究缓存逐目标预测，并校验快照、协议、引擎代码SHA；若任何不一致则重算，不能悄悄使用旧缓存。首次完整运行后，带真实预测数据的两项排序测试才能执行；其余12项测试不依赖主输出。
"""
repro+=fence+"""powershell
$researchPython = '.\\research\\ganzhi_volatility_2026-10-21\\.venv\\Scripts\\python.exe'
& $researchPython research/ganzhi_volatility_2026-10-21/run_study.py
& $researchPython research/ganzhi_volatility_2026-10-21/association.py
& $researchPython research/ganzhi_volatility_2026-10-21/risk_diagnostics.py
& $researchPython research/ganzhi_volatility_2026-10-21/cutoff_sensitivity.py
& $researchPython research/ganzhi_volatility_2026-10-21/verify.py
& .\\.venv\\Scripts\\python.exe research/ganzhi_volatility_2026-10-21/verify_production_rules.py
& $researchPython -m pytest research/ganzhi_volatility_2026-10-21/test_research.py -q
& $researchPython research/ganzhi_volatility_2026-10-21/make_report.py
"""+fence
repro+="""

run_study.py限制数值库为单线程，月度顺序验证与逐日特征在所有模型间保持信息规则一致。association.py和risk_diagnostics.py可在主结果生成后顺序运行，避免Windows同时读写同一导出文件。最终完整运行日志为run-final.log，其他初次中断日志保留审计，不代表最终结果缺失。

## 主交付CSV

| 文件 | 内容 |
| --- | --- |
| results/sixty_ganzhi_statistics.csv | 60行宽表，全部历史/2023以来各目标n、均值、中位数、各门槛发生率 |
| results/ganzhi_descriptive.csv | 1320行历史描述，分时期/目标，普通BTC基准差、年度匹配区间、Holm/BH与历史名次 |
| results/ganzhi_oos.csv | 1320行逐干支 E−C/G−F 样本外误差差、区间、年份稳定性、通过状态 |
| results/model_comparison.csv | 主区间187个模型/目标组合的完整指标 |
| results/model_comparison_extended.csv | 扩展区间同样组合 |
| results/yearly_models.csv | 全部模型逐年表现 |
| results/regime_models.csv | 牛/熊/震荡环境 |
| results/paired_main.csv | 主88项配对损失比较 |
| results/robustness_comparison.csv | 99分位封顶、分别排除2020/2021/2022训练年 |
| results/calibration.csv | 固定概率区间中的样本数、预测概率与实际率 |
| results/online_alerts.csv | 仅用历史预测分位点确定预警阈值的实际报警率与效果 |
| results/permutation_tests.csv | 年内独立旋转、14/28日区块的关联检验 |
| results/descriptive_year_sensitivity.csv | 历史统计分别删除2017/2020/2021/2022年的描述性变化 |

所有CSV为UTF8 BOM，原始幅度/概率用小数：0.01表示1%。均方误差和Brier是原始小数的平方，不是收益百分比。报告的MAE/RMSE乘100显示收益百分点；相对改善百分比按1−候选损失/参考损失计算。

## 逐日预测与超参数

results/predictions.csv.gz包含396253行（17模型×11目标×2119天）。每行保存date、target、model、actual、pred、g、ganzhi、group_n、group_n_2023、group_effect_n、regularization、decision、last_train_close、base_alpha、base_train_end。后两个macro字段是最终实际公布日标记，只供条件性分析与审计，不能误认为主F/G使用了这些事后字段。

group_n与group_n_2023是预测当日可用的标签数；group_effect_n是该月冻结的干支效应拟合数，可能比月末当前可用数少。参数月度冻结，输入逐日更新。forecast_*_fits.json记录每月选出的alpha与干支正则，里面group_项目的train_end表示该次月度决策的历史上界，omit变体实际使用日期可能更早；真实样本数由counts确定。

forecast_*_stamp.json是缓存来源校验；forecast_raw_*.csv.gz是逐目标检查点。predictions_cap99/omit_*.csv.gz为各稳健性版本。cap99的二元事件结果复用原始结果，是因为该变体不改变事件训练和输入，报告没有把它当额外独立证据。

## 其他结果

paired_14/60/180.json为主区块敏感性，paired_extended.json为扩展起点。paired_macro_conditional.json是非严格版本的宏观条件对照。ranking_intervals.json给出ROC/AP配对区间及32项单独Holm校正。

heldout_pre2023_top10.json / *_yearly.json保存仅用2022年底之前统计锁定的10个干支组及之后效果。elevated_ganzhi_predictions.json保存干支相对基础预测增加≥5个百分点/连续幅度增加≥20%的日期分组效果。cutoff_unconditional_comparison.json与probability_prior_sensitivity.json属于探索性基准公平性补充，未据此改写主模型。

所有验证见independent_verification.json、production_rules_verification.json与unit_tests.json。图以PNG/SVG双格式保存。报告QA包含本地页面图片与移动端宽度检查。

## 概率与统计注意事项

主短窗口概率使用Beta(1,1)，可能对极少事件有偏差，因此提供原始比例截断、Jeffreys、2样本整体先验敏感性；强近期模型C/F与干支增量E/G不依赖这项平滑。

F/G的主严格版本没有历史宏观预告输入，因为仓库缺少那种版本数据。F_retro/G_retro仅假设最终实际日期可提前知道，不可直接算作可部署成绩。关联置换中使用最终宏观日期只是在回顾分析里控制混淆。

校准箱Wilson区间仅为IID诊断，不是时间序列稳健/多重校正区间。年度聚类区间是少量年份下的近似均值差区间，不是单日预测区间。置换和bootstrap依赖各自的局部稳定/交换性假设，结果需要和真正样本外稳定性一起判断。

本研究没有方向交易策略，也没有期权、永续合约或可执行融资价格，未生成或宣称模拟利润。
"""
save("REPRODUCE",repro)
print("REPORT, appendix, CSVs and reproduction guide written",flush=True)
