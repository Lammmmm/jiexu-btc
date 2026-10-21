"""Chinese descending rankings and executed OOS report, separate from production."""
from pathlib import Path
import json,math
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import markdown
import study as s
R=s.ROOT;O=s.OUT
def read(n):return json.loads((O/(n+'.json')).read_text('utf-8'))
def pct(v,d=2):return '—' if v is None or not np.isfinite(v) else f'{100*v:.{d}f}%'
def signed(v,d=3):return '—' if v is None or not np.isfinite(v) else f'{100*v:+.{d}f}%'
def num(v,d=4):return '—' if v is None or not np.isfinite(v) else f'{v:.{d}f}'
def table(head,rows):return '\n\n| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n\n'
B={'oc':'收盘比开盘','cc':'收盘比昨收'};SIDE={-1:'偏空',0:'未达55%',1:'偏多'}
rank=read('ganzhi_rankings');summ=read('summary');state=read('group_state_adjusted');top=read('exante_top10_test');pair=read('paired_60')
for (basis,scope),frame in pd.DataFrame(rank).groupby(['basis','scope']):
    frame.sort_values('rank_mean').to_csv(O/f'ranking_{scope}_{basis}_by_mean.csv',index=False,encoding='utf-8-sig')
def rows(scope,basis='oc',limit=None):
    a=sorted([r for r in rank if r['scope']==scope and r['basis']==basis],key=lambda r:r['rank_median'])
    return a if limit is None else a[:limit]
def rank_table(rr):
    return table(['名次','流日','样本','典型日内振幅','平均日内振幅','2023起典型振幅','≥10% 次数率','截至最新方向状态'],[
        [r['rank_median'],r['ganzhi'],r['n'],pct(r['median_range']),pct(r['mean_range']),pct(r['recent_median']),pct(r['range10_rate']),SIDE[r['current_side']]] for r in rr])

font=Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
d=s.e.read_source();valid=d['valid_oc'];global_med=float(np.median(d['y'][valid,2]));global_mean=float(d['y'][valid,2].mean())
fig,axes=plt.subplots(1,2,figsize=(13,6.5),layout='constrained')
for ax,scope,title in [(axes[0],'history_all','全部日线：历史描述排行'),(axes[1],'rolling55','当时方向胜率 ≥55%：入选日期排行')]:
    rr=rows(scope,limit=15);values=np.array([r['median_range'] for r in rr])*100
    ax.barh(np.arange(len(rr)),values,color='#3e829c');ax.set_yticks(np.arange(len(rr)),[r['ganzhi']+f" n={r['n']}" for r in rr]);ax.invert_yaxis()
    ax.set_xlabel('日内高低振幅中位数（%）');ax.set_title(title);ax.bar_label(ax.containers[0],labels=[f'{x:.2f}%' for x in values],padding=3,fontsize=8)
    if scope=='history_all':ax.axvline(global_med*100,color='#b57a44',ls='--',label=f'同期 BTC {global_med*100:.2f}%');ax.legend(fontsize=8)
    ax.set_xlim(0,max(values)*1.18)
fig.suptitle('2017 起：实际振幅高低排行（事后排序，不是未来预测名单）')
fig.savefig(O/'range_rankings.png',dpi=160);plt.close(fig)
history=rows('history_all');old=np.array([r['old_median'] for r in history]);recent=np.array([r['recent_median'] for r in history])
corr=float(spearmanr(old,recent).statistic);oldtop={r['g'] for r in sorted(history,key=lambda r:-r['old_median'])[:10]};newtop={r['g'] for r in sorted(history,key=lambda r:-r['recent_median'])[:10]};overlap=len(oldtop&newtop)
fig,ax=plt.subplots(figsize=(9,5),layout='constrained');ax.scatter(old*100,recent*100,color='#4a8e9b',alpha=.8)
for r in history[:10]:ax.annotate(r['ganzhi'],(r['old_median']*100,r['recent_median']*100),xytext=(3,3),textcoords='offset points',fontsize=8)
ax.set_xlabel('2017—2022 日内振幅中位数（%）');ax.set_ylabel('2023—2026 日内振幅中位数（%）')
ax.set_title(f'跨时期名次：Spearman {corr:.3f}；两期前10名重合 {overlap}/10')
fig.savefig(O/'period_stability.png',dpi=160);plt.close(fig)

positive_groups=[r for r in state if r['passes_association']]
positive_top=[r for r in top if r['metric']=='relative_excess_over_F' and r['p_holm']<.05 and r['delta']>0]
core=[r for r in pair if (r['reference'],r['candidate']) in [('C','E'),('F','G')]]
positive_models=[r for r in core if r['p_holm']<.05 and r['delta']>0]
verdict='B' if positive_groups or positive_top or positive_models else 'C'
verdict_text='有局部探索性线索，仍不能把事后高振幅名单当成已验证的交易信号' if verdict=='B' else '有历史高低差异，但未发现足够证据证明高振幅流日能提前、稳定识别'

doc=['# jiexu-btc｜2017 起流日日内振幅排行与滚动回测\n',
 '[全部排行与附表](RANKINGS.md) · [复现方法](REPRODUCE.md) · [全历史60干支排序 CSV](results/ranking_history_all_oc.csv) · [滚动55%筛选排序 CSV](results/ranking_rolling55_oc.csv) · [按平均振幅排序 CSV](results/ranking_rolling55_oc_by_mean.csv)\n',
 f'**结论 {verdict}：{verdict_text}。** 排行中的“高振幅”首先是实际历史分布的描述；是否能提前识别，另用滚动预测和控制波动环境后的检验回答，不能由名次本身推断。\n',
 '## 1. 本次“从2017开始”的含义\n',
 '使用同一份真实 Binance BTCUSDT 现货 UTC+8 日线，最新已收盘日为 **2026-10-20**。振幅本轮也使用 **2017 起全部有效历史**，用于回答扩展研究问题；没有更改正式系统“2017 起方向、2023 起强度”的配置。首根有效整日为 2017-08-18，共 3,348 根开收盘口径有效日线；昨收/共同有效集为 3,345 根。\n',
 '主排序指标是 **日内振幅 = (最高−最低)÷开盘**。采用中位数降序作为“典型振幅”主排行，减少少数暴涨暴跌的影响；另给完整平均数降序名次，便于查看极端事件贡献。开收盘绝对收益、昨收绝对收益单独导出，绝不把它们当成日内高低振幅。\n',
 '方向筛选沿用上次规则：每个历史日开始之前，以 2017 起已收盘同干支记录计算上涨/下跌频率，任一方向 ≥55% 才入选；平盘在分母，原始 Decimal 方向、整数比较 55%，不根据本轮结果调整门槛。名单随历史推进变化。\n',
 '2017 年最初出现的同干支没有先前历史，不能虚构预测。简单模型至少有 30 根整体历史和 1 根同干支历史，首次可回测为 **2017-10-17**。复杂模型需先积累 90 根历史来生成特征，再有至少 180 个可训练特征样本，首次同模型比较为 **'+summ[0]['complex_start']+'**。2017 初期只参与描述和后来训练，不能宣称全17模型已在上市第一天就做过预测。\n',
 table(['方向筛选口径','简单模型起点','简单比较日数','入选日数','最少同干支训练 n','17模型起点','共同日期','入选日期'],[
 [B[r['basis']],r['simple_start'],r['simple_all_n'],r['simple_selected_n'],r['early_train_min'],r['complex_start'],r['complex_all_n'],r['complex_selected_n']] for r in summ]),
 '## 2. 全部六十流日：历史典型振幅最高的前20名\n',
 f'同期普通 BTC 的日内振幅中位数为 **{pct(global_med)}**，平均值为 **{pct(global_mean)}**。本表包含每个流日的全部有效日期，不做方向筛选，因此是最直接的全历史对照；两个方向筛选口径下的这张表相同。\n',rank_table(rows('history_all',limit=20)),
 '## 3. 按上次方式：当时方向胜率 ≥55% 的日期，振幅从高到低\n',
 '这是本次要求的滚动筛选排行。**只汇总该流日在当时满足 ≥55% 的日期**，不是先用今天的胜率筛名单，再回看 2017 年。某流日可能在早期达标，后来不达标，因此历史排行靠前并不意味着现在仍入选。表中“2023起典型振幅”为该池内 2023 起的入选日期，空白表示没有这种样本。\n',
 '### 收盘比开盘方向筛选：前20名\n',rank_table(rows('rolling55','oc',20)),
 '### 收盘比昨收方向筛选：前20名\n',rank_table(rows('rolling55','cc',20)),
 '![按实际日内振幅降序](results/range_rankings.png)\n',
 '早期每个干支只有 1—数根训练记录，观察到一次上涨就可能形成 100% 的历史上涨率；这会大量入选，却不代表胜率可靠。为避免把这种现象遗漏，另提供预先固定的训练 n≥10 和 n≥20 两种敏感性排行，保留原始 n≥1 主结果，没有挑选最有利版本。完整 60 干支及样本起止、四分位、最大值、开收/昨收幅度均在附表和 CSV。\n',
 '## 4. 现在仍然达到55%的流日，历史振幅排行\n',
 '这是截至最新收盘的当前描述池，只用于查看现在的名单，不参与历史预测。这里的样本包含该干支所有有效历史，而不是仅含过去曾经达标的日期。\n',rank_table(rows('current55_descriptive','oc',20)),
 '## 5. 按平均振幅排序：检查极端日是否改变名次\n',
 table(['平均数名次','流日','n','平均振幅','中位振幅','最大单日振幅','去掉最大值后均值','最大值占总振幅'],[
 [r['rank_mean'],r['ganzhi'],r['n'],pct(r['mean_range']),pct(r['median_range']),pct(r['max_range']),pct(r['remove_largest_mean']),pct(r['largest_share'])]
 for r in sorted(rows('history_all'),key=lambda r:r['rank_mean'])[:15]]),
 '平均数排行反映“包含尾部的大幅波动贡献”，中位数反映“普通一次出现时的典型水平”，两者回答不同问题。去掉最大值仅是敏感性诊断，主结果没有删除任何真实极端行情；另外逐行提供分别删除2017、2020、2021、2022后的中位数，不能把这些事后删样本结果当可执行筛选。\n',
 '## 6. 跨时期能否维持高振幅名次\n',
 f'将所有流日分成 2017—2022 与2023—2026两期，日内振幅中位数的 Spearman 名次相关为 **{corr:.3f}**；两期前10名重合 **{overlap}/10**。两期的 BTC 波动环境不同，绝对振幅整体下降，所以不能把早期5%直接当作今天的预期。该分期对比是描述性稳定性诊断，不是重新选择表现最好的训练窗口。\n',
 '![不同时期的振幅水平](results/period_stability.png)\n',
 '## 7. 控制普通BTC波动环境后，哪些流日还突出\n',
 '在17模型可比较的日期，使用事前发布的 F 模型预测（多尺度近期状态＋星期）作为基准，计算实际日内振幅÷F预测−1，再按日历年减去当年入选池的平均相对残差。这样避免某个干支只是碰巧更多落在高波动年份。年度分组均值用于事后关联检验，不能当成预测输入。\n',
 f'对两个筛选器的共 **{len(state)} 项**逐干支关联比较一起 Holm 校正。年度聚类 t 区间是近似，尤其某干支出现年份少时功效有限。正向关联通过校正的项目数为 **{len(positive_groups)}**；即使有关联，也必须继续通过下面的真正事前分组检验。\n',
 table(['口径','流日','样本','实际平均振幅','F事前平均预测','年份调整后超额比例','95%区间','Holm p'],[
 [B[r['basis']],r['ganzhi'],r['n'],pct(r['actual_mean_range']),pct(r['F_mean_prediction']),signed(r['year_adjusted_excess']),
  '['+signed(r['ci_low'])+', '+signed(r['ci_high'])+']',num(r['p_holm'])]
 for r in sorted(state,key=lambda r:-r['year_adjusted_excess'])[:20]]),
 '这里的“超额比例”是相对 F 所预测振幅的比例差，不是 BTC 收益率百分点，也不表示能赚到同等利润。\n',
 '## 8. 真正事前选“高波动流日”，之后是否更高\n',
 '每日只用此前365个自然日已经产生的诚实 F 预测及真实结果，估计60干支各自的“实际/F预测”比例，按20个样本向整体收缩；60组均至少有5个过去预测后才发布名单。事前取前10组，固定规则不搜索前5/前15等版本，再看当天是否落在这个名单。之后才用当日真实振幅评分，绝不使用本报告的事后排行作为历史预测名单。\n',
 table(['方向口径','指标','检验起点','前10组实际日数','其他组实际日数','前10组均值','其他组均值','差值','95%区间','Holm p'],[
 [B[r['basis']],r['metric'],r['first'],r['n_high'],r['n_rest'],pct(r['high_mean']),pct(r['rest_mean']),signed(r['delta']),
  '['+signed(r['ci_low'])+', '+signed(r['ci_high'])+']',num(r['p_holm'])] for r in top]),
 '原始振幅更高可能是市场状态更高；相对 F 的超额比例才是是否超越近期波动基准的关键。置信区间在原始自然日日历上做60日区块配对重抽样，同时重抽两个池的指示与结果；源无效日仍保留零权重，未将相隔数月的同干支日期压缩成连续日。4个比较一起校正。\n',
 '## 9. 与上次相同的17模型比较：起点前移后的结果\n',
 '全部11个目标分别回测，模型、时间窗口、月度拟合及训练内部顺序验证沿用上次协议；本轮重新生成早期预测，不把2021起缓存冒充2017起结果。E在C上增加干支，G在F上增加干支，是最重要的独立增量比较。F_retro/G_retro使用最终宏观公布日，只能作为条件性分析；仓库缺少历史事前公告版本。\n',
 table(['口径','目标','比较','n','MSE/Brier相对改善','95%区间','Holm p'],[
 [B[r['basis']],r['target'],r['candidate']+' 对 '+r['reference'],r['n'],signed(r['relative_improvement']),
  '['+signed(r['relative_ci_low'])+', '+signed(r['relative_ci_high'])+']',num(r['p_holm'])]
 for r in core if r['metric'] in ['se','brier'] and r['target'] in ['range','abs_oc','abs_cc','range5','range10']]),
 '连续目标表中改善是 MSE；RMSE 改善另外记录于CSV，不能把两个百分比混用。主176项比较一起 Holm 校正；14/180日区块敏感性、全部MAE/RMSE/Brier/Log Loss/AUC/AP及逐年表现保留。简单模型2017起结果与17模型共同起点结果分开，不跨不同日期直接排优劣。\n',
 table(['区块','全部显著有利项','E−C/G−F显著有利项'],[
 [block,sum(r['p_holm']<.05 and r['delta']>0 for r in read('paired_'+str(block))),
 sum(r['p_holm']<.05 and r['delta']>0 and (r['reference'],r['candidate']) in [('C','E'),('F','G')] for r in read('paired_'+str(block)))] for block in [14,60,180]]),
 '## 10. 应怎样使用这份排序\n',
 f'本次可明确指出历史上哪些流日振幅较大，并提供全部降序清单；但“特别突出”若指可提前重复预测，需要控制状态、样本量、多重比较和事前排序。当前判断为 **{verdict}：{verdict_text}**。本轮正向逐干支关联有 {len(positive_groups)} 项，事前分组的状态调整后显著正差异有 {len(positive_top)} 项，主同等模型显著正改善有 {len(positive_models)} 项，三者不得互相替代。\n',
 '继续在已看过的历史上追加排序属于探索研究，没有新的未使用确认期。范围扩到2017也会增加早期巨大振幅和低样本筛选的影响。某流日的高低价差不等于可实现方向收益，不能据此声称有交易盈利；没有模拟不存在的入场出场成交。本次只新增研究文件，正式日历、API和统计逻辑未修改。\n',
 '## 11. 实际验证与交付\n',
 table(['核验项目','实际结果'],[[k,str(v)] for k,v in read('verification').items()]),
 '数据和源代码输入哈希见 manifest.json；逐日筛选、完整逐日预测、各目标模型指标、全60干支排序和敏感性结果均可复现。方法参考：[滚动时间序列交叉验证](https://otexts.com/fpp3/tscv.html)。所有数值来自本次实际执行。\n']

append=['# 全部流日日内振幅降序结果\n','[返回报告](REPORT.md)\n',
 '典型振幅为(H-L)/O的中位数，主表按此降序；CSV另有rank_mean平均振幅降序名次。全历史排行不是样本外预测名单，滚动55%排行只含每个日期当时达标的记录。\n']
for scope,title in [('history_all','全历史描述'),('current55_descriptive','截至最新仍达55%：历史描述'),('rolling55','逐日滚动55%：实际入选日期'),('rolling55_min10','滚动55%且方向训练 n≥10'),('rolling55_min20','滚动55%且方向训练 n≥20')]:
    for b in ['oc','cc']:
        append.extend(['## '+title+'｜'+B[b]+'\n',rank_table(rows(scope,b)),f'[下载本表CSV](results/ranking_{scope}_{b}.csv)\n'])

repro='''# 2017 起振幅研究：复现说明

[报告](REPORT.md) · [全部降序排行](RANKINGS.md)

本目录是独立研究，依赖父目录的 ganzhi_volatility_2026-10-21 与 ganzhi_win55_volatility_2026-10-21。真实冻结行情和干支标签、原模型引擎、先前无泄漏评估辅助函数都按 manifest.json 的SHA256校验。方向史和本轮幅度均从2017实际可用起，2026-10-20为最新收盘日。

## 运行

仓库根目录，Python3.12，科学依赖沿用父研究 requirements-research-lock.txt：

```powershell
$rp = '.\\research\\ganzhi_volatility_2026-10-21\\.venv\\Scripts\\python.exe'
& $rp research/ganzhi_range_2017_2026-10-21/study.py
& $rp -m pytest research/ganzhi_range_2017_2026-10-21/test_study.py -q --junitxml=research/ganzhi_range_2017_2026-10-21/results/unit-tests.xml
& $rp research/ganzhi_range_2017_2026-10-21/verify.py
& $rp research/ganzhi_range_2017_2026-10-21/make_report.py
```

所有模型预测只用目标日开始前已收盘信息。简单模型从2017首次重复流日后开始，复杂模型需180个可用训练特征日，特征本身需90日历史，所以2017不能伪造完整复杂模型结果。17模型逐目标重新运行并按源、协议、引擎、研究runner哈希缓存，任一不符就重算。原模型窗口与内部验证规则未优化。

## 输出

| 文件 | 内容 |
| --- | --- |
| selection_daily.csv | 2017起逐日方向样本计数、入选及暖机标记；初次流日历史n=0不入选 |
| ganzhi_rankings.csv | 全部范围及两个口径的完整排名，含rank_median/rank_mean |
| ranking_history_all_oc.csv | 全60干支全部有效日线，典型振幅降序 |
| ranking_current55_descriptive_oc.csv | 最新达55%名单的历史描述排序，禁止回头当预测名单 |
| ranking_rolling55_oc.csv | 严格当时55%入选日期的排序；cc文件为昨收方向筛选 |
| ranking_rolling55_min10_oc.csv / ranking_rolling55_min20_oc.csv | 固定方向训练量敏感性，cc同理 |
| ranking_*_by_mean.csv | 对应范围按平均振幅降序的独立文件，主文件按中位数降序 |
| simple_predictions.csv.gz / simple_model_comparison.csv | 2017起可用简单模型的逐日预测及评分 |
| predictions.csv.gz / model_comparison.csv | 17模型共同暖机起点后的11目标预测与完整指标 |
| forecast_raw_*_stamp.json / *_fits.json | 逐目标数据/代码哈希、月度训练与正则选择 |
| paired_60.csv / paired_14.csv / paired_180.csv | 176项同日配对损失检验，原日历区块及Holm |
| yearly_models.csv | 各年模型表现，简单与复杂日期不能混排 |
| group_state_adjusted.csv | 120项逐流日状态与年份调整后关联检验，年度聚类区间、Holm |
| exante_top10_daily.csv | 每天只用过去365日诚实F预测形成的收缩前10组，训练至少每组5个 |
| exante_top10_test.csv / exante_top10_yearly.csv | 真正事前高风险组的后验实际及F调整后差异、区间、逐年 |
| verification.json / unit-tests.xml | 本轮实际核验 |

CSV为UTF8 BOM；概率/幅度原始小数，0.01表示1%。median_range和mean_range是日内高低振幅；abs_oc/cc幅度另列，range5/10按原始Decimal分类。F相对超额为实际振幅/F预测−1，是相对比例，不是价格收益百分点。

无效源日期在评分时不使用，在bootstrap时按原自然日日历保留零权重，选择指示和损失同时重抽，不能把相隔很远的流日压缩成相邻日。事前前10组推断给高组和其他组使用相同区块随机序列，保留配对关系。

全历史和当前池排行均是回顾统计。滚动入选日期排行也是根据真实结果事后排序，不能视为已经提前选择出的最优组。只有exante_top10的名单在目标发生前确定。逐干支区间为近似年度聚类，缺失年份及小样本要谨慎。所有研究仍是同一已观察历史上的追加探索；不修改正式功能，不宣称净交易收益。
'''
def render(name,text):
    text=text.rstrip()+'\n';(R/(name+'.md')).write_text(text,encoding='utf-8')
    body=markdown.markdown(text,extensions=['tables','fenced_code']).replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')
    for n in ['REPORT','RANKINGS','REPRODUCE']:body=body.replace('href="'+n+'.md"','href="'+n+'.html"')
    css='''*{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#233246;font:15px/1.85 "Microsoft YaHei",sans-serif}main{max-width:1320px;margin:24px auto;padding:34px 42px;background:#fff;border:1px solid #d8e1eb;border-radius:10px}h1{font-size:27px;color:#173f65}h2{margin-top:38px;padding-top:20px;border-top:1px solid #e2e8f0;color:#234d70}h3{font-size:18px}p,li{overflow-wrap:anywhere}a{color:#226cb0}.table-wrap{overflow-x:auto;margin:20px 0;border:1px solid #dce4ed}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th,td{padding:8px 11px;text-align:left;border-bottom:1px solid #e6edf4}th{background:#edf3f8}tr:nth-child(even){background:#f8fafc}img{display:block;max-width:100%;height:auto;margin:25px auto}pre{overflow-x:auto;padding:16px;background:#edf2f7}code{font:13px Consolas,monospace}@media(max-width:700px){main{margin:0;padding:17px 14px;border:0}h1{font-size:23px}body{font-size:14px}}'''
    (R/(name+'.html')).write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+name+'</title><style>'+css+'</style></head><body><main>'+body+'</main></body></html>',encoding='utf-8')
render('REPORT','\n'.join(doc));render('RANKINGS','\n'.join(append));render('REPRODUCE',repro)
s.save('report_summary',dict(verdict=verdict,positive_group_associations=len(positive_groups),positive_exante_adjusted_tests=len(positive_top),positive_core_model_tests=len(positive_models),global_median_range=global_med,global_mean_range=global_mean,period_rank_correlation=corr,period_top10_overlap=overlap))
print('REPORT_DONE',verdict)
