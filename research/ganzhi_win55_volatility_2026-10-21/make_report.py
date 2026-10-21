"""Create Chinese research report from executed outputs; no estimated results."""
import json,html,math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import markdown
import study as s
R=s.ROOT;O=s.OUT
def read(n):return json.loads((O/(n+'.json')).read_text('utf-8'))
def pct(v,d=2):return '—' if v is None or not np.isfinite(v) else f'{100*v:.{d}f}%'
def num(v,d=6):return '—' if v is None or not np.isfinite(v) else f'{v:.{d}f}'
def signed(v,d=3):return '—' if v is None else f'{100*v:+.{d}f}%'
def table(head,rows):
    return '\n\n| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+'\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in rows)+'\n\n'
BASIS={'oc':'收盘比开盘','cc':'收盘比昨收'};SIDE={0:'合并',1:'做多',-1:'做空'}
L={'abs_oc':'开收绝对涨跌幅','abs_cc':'昨收绝对涨跌幅','range':'日内高低振幅',
 'oc2':'开收 ≥2%','oc3':'开收 ≥3%','oc5':'开收 ≥5%','cc2':'昨收 ≥2%','cc3':'昨收 ≥3%','cc5':'昨收 ≥5%',
 'range5':'日内振幅 ≥5%','range10':'日内振幅 ≥10%'}
M=read('model_comparison');PAIR=read('paired_60');POOL=read('ganzhi_direction_pools')
DIR=read('direction_validation');COUNTS=read('ganzhi_selected_counts')
G=read('ganzhi_selected_oos');YEAR=read('yearly_models')
scores={(r['basis'],r['target'],r['model']):r for r in M}
def core(rows):return [r for r in rows if (r['reference'],r['candidate']) in [('C','E'),('F','G')]]
def primary(r):return r['metric'] in ['se','brier']
def gain_table(rows,targets=None):
    return table(['筛选口径','目标','比较','样本','损失改善','95% 区间','Holm p'],[
        [BASIS[r['basis']],L[r['target']],r['candidate']+' 对 '+r['reference'],r['n'],signed(r['relative_improvement']),
         f"[{signed(r['relative_ci_low'])}, {signed(r['relative_ci_high'])}]",num(r['p_holm'],4)]
        for r in core(rows) if primary(r) and (targets is None or r['target'] in targets)])

font=Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():
    font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
for ax,basis in zip(axes,['oc','cc']):
    rows=[r for r in DIR if r['basis']==basis]
    xx=np.arange(len(rows));rates=np.array([r['actual_win_rate'] for r in rows]);lo=np.array([r['ci_low'] for r in rows]);hi=np.array([r['ci_high'] for r in rows])
    ax.bar(xx,rates*100,color=['#547896','#29a48a','#c46868']);ax.errorbar(xx,rates*100,yerr=np.vstack([rates-lo,hi-rates])*100,fmt='none',color='#334155',capsize=4)
    ax.axhline(55,ls='--',color='#d89c41',label='训练筛选门槛 55%');ax.set_ylim(35,66)
    ax.set_xticks(xx,[SIDE[r['side']]+f"\nn={r['n']}" for r in rows]);ax.set_title(BASIS[basis]);ax.set_ylabel('样本外方向命中率（%）')
    ax.legend(loc='upper right',fontsize=8)
fig.suptitle('2017 起历史胜率 ≥55% 的流日，未来命中率并未维持 ≥55%')
fig.savefig(O/'direction_validation.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(13,6.3),layout='constrained')
for ax,basis in zip(axes,['oc','cc']):
    ts=['abs_'+basis,'range',basis+'2',basis+'3',basis+'5','range5','range10'];xx=np.arange(len(ts))
    for offset,ref,cand,color in [(-.13,'C','E','#287dc1'),(.13,'F','G','#aa6d45')]:
        rr=[next(r for r in PAIR if r['basis']==basis and r['target']==t and r['reference']==ref and primary(r)) for t in ts]
        val=np.array([r['relative_improvement'] for r in rr])*100;lo=np.array([r['relative_ci_low'] for r in rr])*100;hi=np.array([r['relative_ci_high'] for r in rr])*100
        ax.errorbar(val,xx+offset,xerr=np.vstack([val-lo,hi-val]),fmt='o',label=cand+' 对 '+ref,color=color,capsize=3)
    ax.axvline(0,color='#64748b',lw=1);ax.set_yticks(xx,[L[t] for t in ts]);ax.set_title(BASIS[basis]+'筛选');ax.invert_yaxis();ax.legend()
    ax.set_xlabel('MSE / Brier 相对改善（%）；右侧更好')
fig.suptitle('限定 ≥55% 胜率日期后，仍未发现可靠的正向干支增量')
fig.savefig(O/'incremental_effects.png',dpi=160);plt.close(fig)

doc=['# jiexu-btc｜胜率 ≥55% 流日的波动预测复核报告\n',
 '[逐干支附表](GANZHI_APPENDIX.md) · [复现说明](REPRODUCE.md) · [筛选逐日记录 CSV](results/selection_daily.csv) · [2017 起干支日 K CSV](results/daily_ganzhi_candles_2017.csv)\n',
 '## 1. 结论\n',
 '**结论 C：按照做多或做空历史胜率 ≥55% 缩小测试范围后，仍没有证明干支信息提供稳定、独立的波动强度预测优势。** 这不等于证明任何干支规律永远不存在，而是本次数据和锁定模型没有提供可开发的证据。\n',
 '主样本外为 **2023-01-01—2026-10-20**；方向筛选始终使用 **2017 年实际可用起** 的已收盘日 K，不把 2023 作为方向历史起点。每个测试日先以过去同干支记录决定是否入选，随后才评分当日结果。另验证 2021 年起扩展区间、2022 年底固定名单、做多/做空分组和四类稳健性预测。\n',
 '本次执行的是“限定测试日期”的新假设，复用上次锁定且逐日无未来信息的 17 个模型预测，重新计算筛选、全部指标、区间和检验。**没有在已经看到的测试结果上重新拟合或优化模型，也没有把训练样本只缩到入选日期。** 后者会成为另一个不同假设，不能把本报告当成已经验证。\n',
 '## 2. 如何筛选，为什么没有直接用现在的名单回测\n',
 '开收盘口径上涨为 C>O、下跌为 C<O；昨收口径为 C>前一日有效收盘、C<前收。做空胜率指该口径的下跌频率，不是扣除成本后的可实现做空收益。平盘保留在分母。使用原始 Decimal 价格判断方向，并以整数比较 `100×上涨次数 ≥55×n` 或 `100×下跌次数 ≥55×n`，避免四舍五入把 54.98% 当成 55%。\n',
 '每天 UTC+8 00:00 只使用该时刻之前已收盘的有效日线；沿用现有干支历法标注每根日 K。2017-08-17 上市首根不完整日线、源收盘时间异常、未收盘日线排除；昨收口径另排除前一日源收盘异常。有效开收盘方向样本 3,348 根，昨收口径 3,345 根，起于 **2017-08-18**。测试目标沿用原研究共同有效集，保证模型的测试日期相同。\n',
 '“现在筛到哪些干支”是描述清单；它包含后来行情，不能回头用于 2023 年预测。因此报告同时提供：逐日滚动名单、只用 2022 年底之前信息固定的名单，以及截至 2026-10-20 的当前名单。当前名单没有被用于历史预测。\n']
doc.append(table(['方向口径','测试起点','全部日','入选日','保留比例','曾入选干支','做多日','做空日','当时训练 n'],[
 [BASIS[r['basis']],r['start'],r['total_n'],r['selected_n'],pct(r['fraction']),r['selected_groups'],r['long_n'],r['short_n'],f"{r['training_n_min']}—{r['training_n_max']}"] for r in read('selection_summary')]))
doc+=['## 3. 方向胜率本身有没有延续\n',
 '下面是筛选之后才发生的真实结果。置信区间使用原始日历上的 60 日区块重抽样。BTC 对照是在同一天、同一收益口径上按过去整体多数方向判断；本区间该基准始终偏向上涨，不能把做空命中率同另外一批日期的上涨率比较。\n',
 table(['方向口径','筛选侧','n','训练胜率均值','样本外命中','95% 区间','同日 BTC 基准','超额命中'],[
 [BASIS[r['basis']],SIDE[r['side']],r['n'],pct(r['forecast_rate']),f"{r['wins']}/{r['n']} = {pct(r['actual_win_rate'])}",
  f"[{pct(r['ci_low'])}, {pct(r['ci_high'])}]",pct(r['btc_majority_win_rate']),signed(r['excess_hit_rate'],2)] for r in DIR]),
 '训练期入选日期的优势方向胜率平均约 59.5%，但样本外合并命中只有约 52%。尤其训练时偏空的日期，后来做空命中并未超过 50%。这是筛选后在新数据上减弱的实际结果；不能把 ≥55% 的历史门槛直接解释成未来 ≥55%。方向命中对 BTC 基准的差异也没有通过校正检验。\n',
 '![方向命中与区间](results/direction_validation.png)\n',
 table(['口径','年份','筛选侧','n','样本外命中','同日 BTC 基准'],[
 [BASIS[r['basis']],r['year'],SIDE[r['side']],r['n'],pct(r['actual_win_rate']),pct(r['btc_majority_win_rate'])] for r in read('direction_yearly')]),
 '## 4. 波动预测模型与统一比较\n',
 '与原研究完全一致：A 全历史均值；B30 过去 30 日；C7/C14/C90/C365 不同窗口；Cewma 为半衰期 14 日；C 为多尺度近期波动状态回归；D 为同干支向整体收缩 20 个样本；D_raw 为原始同干支；D_2023 为 2023 起同干支。E30 在 B30 上加入干支残差，E 在 C 上加入干支，F 在多尺度状态上控制星期，G 在 F 上加入干支。F_retro/G_retro 另用最终宏观公布日期，只是条件性分析。\n',
 '主要看 **E 对 C、G 对 F**。E 对 B30 同时增加了更强的波动状态模型和干支信息，改善不能直接归因于干支。幅度目标是绝对涨跌幅与高低振幅；事件目标固定 ≥2%、≥3%、≥5%，高低振幅另列 ≥5%、≥10%。原始精度判定，二者不混合。\n']
for basis in ['oc','cc']:
    own='abs_'+basis
    doc.append('### '+BASIS[basis]+'筛选：全部模型主指标\n')
    doc.append(table(['模型','绝对收益 MAE','绝对收益 RMSE','振幅 MAE','振幅 RMSE','≥2% Brier','≥3% Brier','≥5% Brier','≥3% AUC','≥3% AP'],[
        [m,pct(scores[basis,own,m]['mae'],3),pct(scores[basis,own,m]['rmse'],3),pct(scores[basis,'range',m]['mae'],3),pct(scores[basis,'range',m]['rmse'],3),
         num(scores[basis,basis+'2',m]['brier']),num(scores[basis,basis+'3',m]['brier']),num(scores[basis,basis+'5',m]['brier']),
         num(scores[basis,basis+'3',m]['roc_auc'],4),num(scores[basis,basis+'3',m]['pr_auc_ap'],4)] for m in s.MODELS]))
    for t in [own,'range',basis+'2',basis+'3',basis+'5']:
        metric='rmse' if t in s.CONT else 'brier'
        ranking=sorted([(m,scores[basis,t,m][metric]) for m in s.MODELS if not m.endswith('_retro')],key=lambda x:x[1])
        doc.append(f"{L[t]} 按 {metric} 的事后诊断第一名：**{ranking[0][0]}**（{num(ranking[0][1])}）。该排名没有用于重新调参或宣称已选出未来最优模型。\n")
doc+=['## 5. 干支信息的实际增量和统计区间\n',
 '下表连续目标使用 **MSE** 改善，事件目标使用 **Brier** 改善；正数表示候选更好。区间是点态 95%，不是同时区间。主检验将两个筛选口径、11 个目标、两个损失指标、四组比较合计 **176 项** 一起做 Holm 校正。14 日和 180 日区块作为敏感性。\n',gain_table(PAIR),
 '两个最关键的独立增量比较（E−C、G−F）均没有通过主检验校正。个别 ≥5% 事件 Brier 的小改善，其区间仍跨过零。相对 RMSE 改善进一步小于相对 MSE 改善。\n',
 table(['筛选口径','目标','E 对 C：RMSE 改善','G 对 F：RMSE 改善'],[
 [BASIS[b],L[t],signed(next(r for r in PAIR if r['basis']==b and r['target']==t and r['candidate']=='E' and r['metric']=='se')['rmse_improvement'],4),
  signed(next(r for r in PAIR if r['basis']==b and r['target']==t and r['candidate']=='G' and r['metric']=='se')['rmse_improvement'],4)] for b in ['oc','cc'] for t in ['abs_'+b,'range']]),
 '![干支增量及区间](results/incremental_effects.png)\n',
 '### 必须披露的有利结果及其归因\n',
 '主 176 项检验中确有通过校正的有利结果，全部是 E 对简单 B30 的比较，不能省略。但 E 对 C 没有显著增量，因此这些结果不足以证明干支独立有效；还应直接查看 C 相对 B30 的同目标改善。\n']
sig=[r for r in PAIR if r['p_holm']<.05]
doc.append(table(['筛选口径','目标','损失','比较','改善','Holm p','C 对 B30 同损失改善'],[
 [BASIS[r['basis']],L[r['target']],r['metric'],r['candidate']+' 对 '+r['reference'],signed(r['relative_improvement']),num(r['p_holm'],4),
  signed(1-scores[r['basis'],r['target'],'C'][{'se':'mse','ae':'mae'}.get(r['metric'],r['metric'])]/scores[r['basis'],r['target'],'B30'][{'se':'mse','ae':'mae'}.get(r['metric'],r['metric'])])]
 for r in sig]))
doc+=['## 6. 是否更容易提前识别大行情\n',
 '同等预警比例采用入选日期预测值前 10%，属于整段预测排序诊断，不是当时已知阈值。逐日可执行的预警另以过去 365 个自然日已发布、且当时入选的预测分位点确定阈值，至少 60 个先前入选预测；其实际预警比例不能强行等于 10%。完整 10%/20% 指标、ROC-AUC、PR-AUC、Log Loss、固定概率区间校准均已导出。\n',
 table(['筛选口径','事件','总事件/n','模型','前10% 日数','识别事件','前10% 实际率','ROC-AUC','PR-AUC(AP)','Log Loss'],[
 [BASIS[b],L[t],f"{scores[b,t,m]['events']}/{scores[b,t,m]['n']}",m,math.ceil(scores[b,t,m]['n']*.1),
  round(scores[b,t,m]['top10_event_rate']*math.ceil(scores[b,t,m]['n']*.1)),pct(scores[b,t,m]['top10_event_rate']),
  num(scores[b,t,m]['roc_auc'],4),num(scores[b,t,m]['pr_auc_ap'],4),num(scores[b,t,m]['logloss'])]
 for b in ['oc','cc'] for t in [b+'2',b+'3',b+'5','range5','range10'] for m in ['F','G']]),
 '排序指标共 64 项 E−C/G−F 的配对区块检验，没有通过 Holm 校正的增量。少数高阈值事件基数很小，前 10% 多识别一两次并不能支持稳定预警能力。`calibration.csv` 给出每档预测概率与实际发生率，`online_alerts.csv` 给出真实历史阈值预警，不使用几乎永远预测“无大行情”的准确率充当效果。\n',
 '## 7. 入选日期的实际波动是否更高\n',
 table(['筛选口径','目标','入选 n','入选实际均值/发生率','同期全部 BTC','差值(百分点)'],[
 [BASIS[b],L[t],a['n'],pct(a['mean'],3),pct(z['mean'],3),signed(a['mean']-z['mean'],3)]
 for b in ['oc','cc'] for t in ['abs_'+b,'range',b+'2',b+'3',b+'5','range5','range10']
 for a in [next(r for r in read('selected_vs_ordinary') if r['basis']==b and r['target']==t and r['group']=='selected')]
 for z in [next(r for r in read('selected_vs_ordinary') if r['basis']==b and r['target']==t and r['group']=='all')]]),
 '≥3% 发生率在入选日期略高，但绝对收益平均值、≥2% 和 ≥5% 发生率没有一致提高；高低振幅均值也十分接近同期普通 BTC。即使存在某项描述差异，也要由 F/G 的同日预测损失验证是否产生增量，不能据此直接改仓位。\n',
 '## 8. 逐年、牛熊与震荡稳定性\n',
 '牛/熊标签只用此前有效收盘：前一收盘相对过去 200 根均线，且过去 30 根涨跌达到预设的 ±20%；不满足为中间/震荡环境。这主要区分强趋势，不能把未达 20% 的日期都解释为价格横盘。标签不使用当日结果。它只是固定研究分组，不是对市场周期的唯一划分。逐年表显示相对 MSE/Brier 改善，正值更好。\n']
for name in ['yearly_models','regime_models']:
    rows=read(name);lookup={(r['basis'],r['subgroup'],r['target'],r['model']):r for r in rows}
    doc.append('### '+('逐年' if name=='yearly_models' else '市场环境')+'核心比较\n')
    doc.append(table(['筛选口径','分组','目标','n','E 对 C','G 对 F'],[
        [BASIS[b],group,L[t],lookup[b,group,t,'C']['n'],
         signed(1-lookup[b,group,t,'E'][metric]/lookup[b,group,t,'C'][metric]),
         signed(1-lookup[b,group,t,'G'][metric]/lookup[b,group,t,'F'][metric])]
        for b in ['oc','cc'] for group in sorted({r['subgroup'] for r in rows if r['basis']==b}) for t in ['abs_'+b,'range',b+'3',b+'5']
        for metric in ['mse' if t in s.CONT else 'brier']]))
doc+=['## 9. 固定名单、扩展起点、长短分组与极端行情\n',
 '固定名单只在 2022 年底计算一次，此后不增删干支。它避免滚动名单进入退出的影响，但只对应那个时点的固定池，不能替代当前名单。稳健性模型使用上次已严格滚动产生的训练内 99 分位封顶或剔除单个极端年份的预测，并保留原始真实测试涨跌幅评分。本次筛选器仍使用原始 2017 起方向历史，避免每个变体偷偷更换测试日期。\n']
sens=[]
for name in ['paired_60','paired_14','paired_180','paired_extended','frozen_paired','paired_long_short','robustness_paired']:
    x=read(name);z=core(x)
    sens.append([name,len(x),sum(r['p_holm']<.05 and r['delta']>0 for r in x),len(z),sum(r['p_holm']<.05 and r['delta']>0 for r in z),num(min(r['p_holm'] for r in z),4)])
doc.append(table(['检验','全部项','全部有利显著项','E−C/G−F 项','干支有利显著项','干支最小 Holm p'],sens))
doc+=['E 对 B30 的部分改善对区块长度敏感，14 日区块下未通过主家族校正；无论这些敏感性如何，E 对 C、G 对 F 都没有检出显著干支增量。个别做空分组的大振幅结果来自更强的基础模型，而非已经证明干支有效。\n',
 '### 2022 年底固定池的同等模型比较\n',gain_table(read('frozen_paired'),['abs_oc','abs_cc','range','oc3','cc3','oc5','cc5']),
 '## 10. 干支间差异、多重比较与极端样本\n',
 f"主测试中有入选记录的逐干支比较共 {len(G)} 项（两个筛选器 × 可用干支 ×11目标 ×E−C/G−F），一起 Holm 校正。通过预设的正改善、校正 p<0.05、至少 15 个样本、至少 3 年正改善及事件数门槛的行数为 **{sum(r['passes_validation'] for r in G)}**。因此不输出“已经验证的高波动流日赢家榜”。全部 60 个干支仍保留在清单与样本量表中，没有入选记录的干支明确显示 0。\n",
 '控制年份、多尺度既有波动状态、星期和最终宏观日标签后，又对固定入选路径做年内独立旋转残差的探索性关联检验（22 项、每项 4,999 次）。没有通过 Holm 校正的关联。该置换保留局部波动结构，但没有在每次置换中重新学习方向筛选器，因此不是整个自适应筛选算法的精确零假设检验，不用于证明预测有效。真正的判断依据仍是滚动样本外配对损失。\n',
 '筛选后的每个干支常常只有个位数到二十多次测试记录，做空子样本更少。区间宽、稀有事件少、只有四个主检验年份，都限制统计功效。未显著不等于已证明差异严格为零；同样，样本小也不能作为采用该信号的正面证据。\n',
 '## 11. 当前筛选名单与历史排行\n',
 '以下名单截至 2026-10-20 收盘，方向频率用 2017 起全部有效日 K，**只用于现在描述，不用于回看生成历史选股池**。当前名单、固定名单和逐日滚动名单会不同。完整 60 干支方向、全历史/2023 起幅度和样本外结果见附表和 CSV。\n']
for b in ['oc','cc']:
    pool=[r for r in POOL if r['pool']=='current_descriptive_only' and r['basis']==b and r['selected']]
    doc.append('### '+BASIS[b]+f'：当前 {len(pool)} 个入选干支\n')
    doc.append(table(['方向','干支','有效历史 n','该方向次数','历史胜率','主 OOS 入选 n','样本外命中'],[
        [SIDE[r['side']],r['ganzhi'],r['n'],r['up'] if r['side']==1 else r['down'],pct(r['preferred_rate']),
         next(c['selected_n'] for c in COUNTS if c['basis']==b and c['g']==r['g']),
         pct(next(c['actual_win_rate'] for c in COUNTS if c['basis']==b and c['g']==r['g']))]
        for r in sorted(pool,key=lambda r:(-r['side'],-r['preferred_rate'],r['g']))]))
doc+=['## 12. 局限和最终开发建议\n',
 '本次是看过上一轮全干支结果后提出的 ≥55% 新筛选，虽然每笔历史预测和筛选没有未来泄漏，整个研究仍属于同一历史数据上的追加探索，不能称为一份完全未被观察过的新确认样本。没有尝试 56%、57%、不同幅度门槛或事后最优开始年份。若后续要确认任何有利信号，需要先锁定规则，再等待真正未使用的新行情。\n',
 '仓库保存的是 CPI/非农最终实际公布日期，缺少每个历史日事前可知的公告日程版本。因此正式主比较 F/G 只控制波动状态和星期；F_retro/G_retro 仅条件性描述。这项限制未因本次缩小范围而消失。\n',
 '本报告只研究方向命中和波动预警，没有把预测幅度转换成虚构交易收益，也没有假设知道当日高低价可以成交。胜率、收益幅度、成本后收益是不同问题，不能互换。\n',
 '**最终判断：保持 C，不建议因为缩小到历史胜率 ≥55% 就继续开发干支波动预测模型。** 可保留历史统计作为描述展示；无法据此提高仓位、设为自动交易条件，或承诺未来胜率。现有“2017 起方向 +2023 起幅度”仍只是不同统计窗口的展示方案，本次没有证明其具有可交易优势，也没有修改正式功能。\n',
 '## 13. 可复现文件与实际完成的验证\n',
 table(['检查','实际结果'],[[k,str(v)] for k,v in read('independent_verification').items()]),
 '此外已按只读方式核对正式系统历法与方向计数：3,353 个源日期的干支标签、240 个“口径×历史截点×干支”方向池，共 **4,553 项检查通过**，确认方向从 2017 起统计，并非 2023 起。记录见 `production_rules_verification.json`。\n',
 '11 个目标、17 个模型、两种方向筛选均有完整 CSV。交付包含真实源快照哈希、父研究代码/预测文件哈希、预先固定的新筛选协议、逐日入选的历史计数、逐日预测、完整模型指标、逐年/市场环境、长短、校准、预警和稳健性。原始交易所数据没有重抓或篡改，保证与上一轮可比。\n',
 '方法参考：[滚动时间序列交叉验证](https://otexts.com/fpp3/tscv.html)、[Holm 多重比较校正](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)。数值均来自本目录实际执行输出，不来自外部示例。\n']

# Join descriptive parent statistics to the explicitly current direction pools.
old=pd.read_csv(s.BASE/'results/sixty_ganzhi_statistics.csv')
current=pd.DataFrame([r for r in POOL if r['pool']=='current_descriptive_only'])
wide=current.merge(old,on=['g','ganzhi'],validate='many_to_one').merge(pd.DataFrame(COUNTS),on=['basis','g','ganzhi'],validate='one_to_one')
wide.to_csv(O/'sixty_ganzhi_statistics.csv',index=False,encoding='utf-8-sig')
hist=[]
for basis in ['oc','cc']:
    w=wide[(wide.basis==basis)&wide.selected]
    for target in ['abs_'+basis,'range',basis+'2',basis+'3',basis+'5']:
        # Explicitly descriptive current-pool ranking; never used as a historical filter.
        for rank,(_,r) in enumerate(w.sort_values('2023_'+target+'_mean',ascending=False).iterrows(),1):
            hist.append(dict(basis=basis,target=target,rank=rank,g=r.g,ganzhi=r.ganzhi,side=r.side,
                current_direction_rate=r.preferred_rate,amplitude_since2023_mean=r['2023_'+target+'_mean'],
                amplitude_since2023_n=r['2023_'+target+'_n'],caveat='Current-pool retrospective descriptive ranking only'))
s.save('historical_selected_ranking',hist)

append=['# ≥55% 筛选：六十干支逐项附表\n','[返回主报告](REPORT.md)\n',
 '所有原始 60 干支都在下面列出；0 表示主区间该干支从未满足当时的筛选条件。当前胜率不用于过去回测。幅度原始历史统计见 [完整宽表 CSV](results/sixty_ganzhi_statistics.csv)，逐日筛选见 [selection_daily.csv](results/selection_daily.csv)。\n']
for basis in ['oc','cc']:
    append.append('## '+BASIS[basis]+'：全 60 干支方向与样本\n')
    w=wide[wide.basis==basis].sort_values('g')
    append.append(table(['干支','历史 n','上涨率','下跌率','当前入选侧','OOS 入选 n','OOS 命中','2023 起典型绝对幅度','2023 起典型日内振幅'],[
        [r.ganzhi,r.n,pct(r.up_rate),pct(r.down_rate),SIDE[r.side] if r.selected else '不入选',r.selected_n,pct(r.actual_win_rate),
         pct(r['2023_abs_'+basis+'_median']),pct(r['2023_range_median'])] for _,r in w.iterrows()]))
    append.append('## '+BASIS[basis]+'：逐干支样本外同等模型比较\n')
    for target in ['abs_'+basis,'range',basis+'2',basis+'3',basis+'5','range5','range10']:
        append.append('### '+L[target]+'\n')
        append.append(table(['干支','比较','n','实际均值/率','MSE/Brier 改善量','95% 区间','正改善年份','Holm p','通过'],[
            [r['ganzhi'],r['candidate']+' 对 '+r['reference'],r['n'],pct(r['actual_mean']),num(r['loss_improvement'],8),
             f"[{num(r['ci_low'],8)}, {num(r['ci_high'],8)}]",r['positive_years'],num(r['p_holm'],4),'是' if r['passes_validation'] else '否']
            for r in G if r['basis']==basis and r['target']==target]))

repro='''# ≥55% 流日研究：复现说明

[完整报告](REPORT.md) · [六十干支附表](GANZHI_APPENDIX.md)

## 研究范围

本目录只新增研究文件。父研究 `../ganzhi_volatility_2026-10-21` 必须完整存在，其中的真实冻结行情、干支标签、代码及逐日预测按 manifest.json 哈希核对。方向筛选从 2017 年实际可用日 K 起，绝不改成 2023 起方向筛选。父研究最新已收盘日为 2026-10-20；当天未收盘日不参与筛选或评分。

`protocol.json` 在读取新筛选结果前固定 55% 规则和推断方案。收益和事件口径不变，模型和超参数不重新优化。父研究的月度滚动、训练内选择和逐日输入详见其 REPRODUCE.md；本轮复用的是它当时已发布的无泄漏预测，重新执行测试日筛选和评分，而非在筛选样本上训练新的模型。

## 运行

在仓库根目录使用 Python 3.12。可以复用父研究环境，或创建新环境并安装父研究的 requirements-research-lock.txt：

```powershell
$rp = '.\\research\\ganzhi_volatility_2026-10-21\\.venv\\Scripts\\python.exe'
& $rp research/ganzhi_win55_volatility_2026-10-21/study.py
& $rp -m pytest research/ganzhi_win55_volatility_2026-10-21/test_study.py -q --junitxml=research/ganzhi_win55_volatility_2026-10-21/results/unit-tests.xml
& $rp research/ganzhi_win55_volatility_2026-10-21/verify.py
& .\\.venv\\Scripts\\python.exe research/ganzhi_win55_volatility_2026-10-21/verify_production_rules.py
& $rp research/ganzhi_win55_volatility_2026-10-21/make_report.py
```

父研究输出缺失时，应先按照其复现说明完整重跑，不可替换为全样本回看预测。CSV 使用 UTF-8 BOM；概率和幅度用小数，0.01 表示 1%。MAE/RMSE 是幅度，MSE/Brier 是平方量。Log Loss 使用自然对数。正的 relative_improvement 为误差下降，rmse_improvement 只用于连续目标；不能混用二者。

## 主要输出

| 文件 | 内容 |
| --- | --- |
| daily_ganzhi_candles_2017.csv | 2017 起所有 3,348 根有效开收盘口径日 K，原始 OHLCV、干支、时区、昨收有效标记；昨收有效 3,345 根 |
| selection_daily.csv | 4,238 条 basis/date 决策，含当时同干支样本量、上涨/下跌/平盘计数、55% 入选侧、严格历史收盘界限和实际后验方向 |
| ganzhi_direction_pools.csv | 2022 年底固定池和最新描述池，两个口径各 60 干支；当前池绝未用于回测筛选 |
| selected_predictions.csv.gz | 437,954 条入选 basis/date/target/model 预测，由入选键与父研究预测精确合并 |
| model_comparison.csv | 主区间 374 个模型/口径/目标组合；完整误差、概率和前 10%/20% 排序指标 |
| model_comparison_extended.csv | 扩展区间 2021 起 |
| paired_60.csv | 主 176 项配对检验，原日历 60 日区块、20,000 次、Holm |
| paired_14.csv / paired_180.csv | 区块长度敏感性，各 10,000 次 |
| yearly_models.csv / regime_models.csv | 各年及事前可知市场环境 |
| direction_validation.csv / direction_yearly.csv | 方向筛选自身样本外命中、训练胜率、同日 BTC 多数方向基准 |
| long_short_models.csv / paired_long_short.csv | 做多和做空侧单列 |
| frozen_model_comparison.csv / frozen_paired.csv | 2022 年底固定名单 |
| robustness_comparison.csv / robustness_paired.csv | 99 分位封顶及训练剔除 2020/21/22 年，原始测试结果不删 |
| sixty_ganzhi_statistics.csv | 120 行完整 60 干支 ×2方向口径，合并父研究全部历史/2023 起幅度及本次入选统计 |
| ganzhi_selected_oos.csv | 2,134 项有入选记录的逐干支样本外差异、年度聚类区间、Holm及稳定性规则 |
| historical_selected_ranking.csv | 当前入选池的历史描述排行，不是通过验证的赢家排行 |
| calibration.csv / online_alerts.csv | 概率校准及只用历史预测形成阈值的实际报警 |
| elevated_predictions.csv | 干支模型比基准明显提高风险预测时的真实结果 |
| ranking_intervals.csv | 64 项 ROC-AUC / PR-AUC 增量区块检验 |
| conditional_permutation.csv | 固定入选路径、控制年份/状态/星期/宏观后的探索性年内旋转检验，不是精确自适应零假设 |
| audit.json / independent_verification.json / unit-tests.xml | 实际执行与独立核验 |
| production_rules_verification.json | 正式历法与方向统计只读核对，共 4,553 项 |

`side=1` 是历史偏多，`side=-1` 是历史偏空，`side=0` 是无方向或汇总行，依文件上下文区分。`history_n` 始终是预测前可用样本；`actual_side`、`correct` 仅用于事后评分，不能输入筛选。`group_n` 是父模型共同训练集计数，可能与采用各自有效性口径的 `history_n` 差几根，二者用途不同。

## 推断限制

主 bootstrap 沿原日历抽取区块，未入选日保留零权重，同时重抽选择指示与配对损失，使用入选分母的比值；不能压缩入选日期再当连续日。它对已经实现的预测/筛选路径做误差推断，不会每次重训整个预测器和筛选器。逐干支年度聚类只有四年，区间近似且功效有限。

主家族 176 项、长短家族 352 项、稳健性家族 704 项、逐干支家族 2,134 项和排序家族 64 项分别校正。所有追加检验均属探索，不能将各家族最有利的结果拼成确认性结论。宏观最终日期没有历史事前版本，F_retro/G_retro 不能宣称可执行预测。没有模拟交易 PnL。

报告新增图表可本地打开 REPORT.html；Markdown 可直接在 GitHub 阅读。独立测试涵盖未来收益扰动、55% 原始精度、2017 数据起点、固定池、日历区块、所有模型同日和逐日合并。QA 脚本另需 Node/Playwright 与 Edge，只验证报告显示，不参与数值研究。
'''

def render(name,text):
    (R/(name+'.md')).write_text(text,encoding='utf-8')
    body=markdown.markdown(text,extensions=['tables','fenced_code'])
    body=body.replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')
    # In local HTML keep cross-document navigation in the rendered HTML pages.
    for n in ['REPORT','GANZHI_APPENDIX','REPRODUCE']:body=body.replace('href="'+n+'.md"','href="'+n+'.html"')
    css='''*{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#233246;font:15px/1.85 "Microsoft YaHei",sans-serif}main{max-width:1320px;margin:24px auto;padding:34px 42px;background:#fff;border:1px solid #d8e1eb;border-radius:10px}h1{font-size:27px;color:#173f65}h2{margin-top:38px;padding-top:20px;border-top:1px solid #e2e8f0;color:#234d70}h3{font-size:18px}p,li{overflow-wrap:anywhere}a{color:#226cb0}.table-wrap{overflow-x:auto;margin:20px 0;border:1px solid #dce4ed}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th,td{padding:8px 11px;text-align:left;border-bottom:1px solid #e6edf4}th{background:#edf3f8}tr:nth-child(even){background:#f8fafc}img{display:block;max-width:100%;height:auto;margin:25px auto}pre{overflow-x:auto;padding:16px;background:#edf2f7}code{font:13px Consolas,monospace}@media(max-width:700px){main{margin:0;padding:17px 14px;border:0}h1{font-size:23px}body{font-size:14px}}'''
    (R/(name+'.html')).write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+name+'</title><style>'+css+'</style></head><body><main>'+body+'</main></body></html>',encoding='utf-8')
render('REPORT','\n'.join(doc));render('GANZHI_APPENDIX','\n'.join(append));render('REPRODUCE',repro)
print('WIN55_REPORT_DONE',json.dumps({'report_chars':sum(map(len,doc)),'group_rows':len(G),'all_60_rows':len(wide)}))
