"""Render individual-first Chinese report directly from executed evidence."""
from core import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import markdown
def read(n):return json.loads((OUT/(n+'.json')).read_text('utf-8'))
def pct(x,d=2):return '—' if x is None or not np.isfinite(x) else f'{100*x:.{d}f}%'
def signed(x,d=2):return '—' if x is None or not np.isfinite(x) else f'{100*x:+.{d}f}个百分点'
def num(x,d=4):return '—' if x is None or not np.isfinite(x) else f'{x:.{d}f}'
def ratio(r,stage):return f"—/{r[stage+'_n']}" if r.get(stage+'_success') is None else f"{r[stage+'_success']}/{r[stage+'_n']}"
def table(head,rows):return '\n\n| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n\n'
BS={'oc':'开收盘','cc':'昨收'};SIDE={1:'上涨',-1:'下跌',0:'训练平票，无预测'}
MN={'year_weekday':'年×星期分层','year_weekday_regime':'年×星期×牛熊分层','week_block28':'年内28日区块','weekly_rotation':'按年整周循环错位'}
G=read('ganzhi_splits');MAIN=read('main60_details');COUNTS=read('persistence_counts');NULL=read('null_persistence_tests');IND=read('individual_randomization')
COR=read('correlation_tests');ROLL=read('rolling_summary');RN=read('rolling_null_tests');YEAR=read('ganzhi_validation_yearly');REG=read('ganzhi_validation_regimes')
FIXED=read('fixed_training_pool_validation_tests')
AUD=read('null_structure_audit');CASES=P['case_studies'];df,_=read_data()
consistency=[]
for r in G:
    if r['kind']!='main':continue
    yy=[v for v in YEAR if v['split']==r['split'] and v['basis']==r['basis'] and v['g']==r['g']]
    consistency.append(dict(split=r['split'],basis=r['basis'],g=r['g'],ganzhi=r['ganzhi'],direction=r['direction'],selected55=r['selected55'],
        years=len(yy),years_ge55=sum(v['success']*100>=55*v['n'] for v in yy),years_ge60=sum(v['success']*100>=60*v['n'] for v in yy),years_above_btc_baseline=sum(v['rate']>v['baseline'] for v in yy),
        minimum_year_rate=min((v['rate'] for v in yy),default=None),maximum_year_rate=max((v['rate'] for v in yy),default=None)))
save('year_consistency',consistency)

font=Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name()
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
for basis in ['oc','cc']:
    obs=next(r for r in NULL if r['basis']==basis and r['split']=='S1' and r['train_threshold']==55 and r['test_threshold']==55)
    fig,axes=plt.subplots(1,2,figsize=(13,4.7),layout='constrained')
    for j,method in enumerate(METHODS):
        with np.load(OUT/f'null_{basis}_{method}.npz') as z:
            n=z['candidates'][:,0,0];k=z['continued'][:,0,0,0]
        for ax,values in [(axes[0],k),(axes[1],k[n==obs['selected']])]:
            lo=int(values.min());hi=int(values.max());hist=np.bincount(values.astype(int),minlength=hi+1)/len(values)
            ax.step(np.arange(hi+1),hist,where='mid',label=MN[method],color=['#2f75a0','#429382','#b37a42','#8a6ea7'][j])
    for ax in axes:
        ax.axvline(obs['continued'],color='#c44e52',ls='--',label=f"真实持续 {obs['continued']} 个")
        ax.set_xlabel('验证期同方向仍 ≥55% 的干支数');ax.set_ylabel('随机频率');ax.legend(fontsize=8)
    axes[0].set_title('完整流程：候选数也随随机训练改变');axes[1].set_title(f"条件对照：随机训练恰好选出 {obs['selected']} 个")
    fig.suptitle(BS[basis]+f"：实际 {obs['continued']}/{obs['selected']} 与随机分布")
    fig.savefig(OUT/f'null_counts_{basis}.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(figsize=(10,6),layout='constrained')
x=[r for r in MAIN if r['basis']=='oc' and r['direction']]
ax.scatter([r['train_rate']*100 for r in x],[r['test_rate']*100 for r in x],c=['#2c967f' if r['persistent55'] else '#c76e60' if r['reversal'] else '#91a4b5' for r in x],alpha=.85)
for r in x:
    if r['ganzhi'] in CASES:ax.annotate(r['ganzhi']+'·'+SIDE[r['direction']],(r['train_rate']*100,r['test_rate']*100),xytext=(4,4),textcoords='offset points',fontsize=9)
ax.axvline(55,color='#8597aa',ls='--');ax.axhline(55,color='#8597aa',ls='--');ax.axhline(50,color='#ccd3db',lw=1)
ax.set_xlabel('训练期锁定方向胜率（%）');ax.set_ylabel('验证期同一方向胜率（%）');ax.set_title('每个点是同一干支；验证期没有重新挑方向')
fig.savefig(OUT/'individual_persistence.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5.4),layout='constrained');matrix=np.full((len(CASES),4),np.nan);text={}
for i,label in enumerate(CASES):
    for j,year in enumerate(range(2023,2027)):
        row=next((r for r in YEAR if r['split']=='S1' and r['basis']=='oc' and r['ganzhi']==label and r['year']==year),None)
        if row:matrix[i,j]=row['rate'];text[i,j]=f"{row['success']}/{row['n']}"
im=ax.imshow(matrix,cmap='RdYlGn',vmin=0,vmax=1,aspect='auto')
ax.set_yticks(range(len(CASES)),[label+'·'+SIDE[next(r for r in MAIN if r['basis']=='oc' and r['ganzhi']==label)['direction']] for label in CASES]);ax.set_xticks(range(4),['2023','2024','2025','2026至今'])
for (i,j),t in text.items():ax.text(j,i,t,ha='center',va='center',color='#1f2937',fontweight='bold')
ax.set_title('训练期冻结方向：验证期逐年成功次数/样本数');fig.colorbar(im,ax=ax,label='同方向胜率')
fig.savefig(OUT/'case_yearly.png',dpi=160);plt.close(fig)

def individual_table(rows):
    return table(['干支','冻结方向','训练成功/总数','训练胜率','验证成功/总数','验证胜率','变化','仍≥55%','匹配市场差','个体校正p'],[
      [r['ganzhi'],SIDE[r['direction']],ratio(r,'train'),pct(r['train_rate']),ratio(r,'test'),pct(r['test_rate']),signed(r['rate_change']),'是' if r['continues55'] else '否',signed(r['matched_excess']),num(r.get('best_global_holm_p'))] for r in rows])

doc=['# jiexu-btc｜六十甲子高胜率持续性与跨周期验证\n',
 '[全部60干支与分割明细](GANZHI_DETAILS.md) · [复现说明](REPRODUCE.md) · [主分割120行CSV](results/main60_details.csv) · [随机检验CSV](results/null_persistence_tests.csv)\n',
 '## 1. 先回答本次真正关心的三个问题\n',
 '**哪些个体持续？** 独立从原始OHLC重算，确认开收盘口径25个训练≥55%候选中，12个在2023以后同方向仍≥55%；昨收口径为11/25。庚午、甲申、丙申确实在两期都≥60%。这些个体结果完整保留，没有用约52%的汇总命中率替代。\n',
 '**超出随机多少？** 四种完整流程随机检验下，实际持续数量处于正常随机范围。即使限定随机训练也恰好选出25个，12/25及11/25仍未显著超过随机预期。主216项门槛/口径/分割/方法检验、多分割个体检验及关联检验均未形成整体稳健证据。\n',
 '**能否提前认出未来赢家？** 固定名单、方向、滚动过去30次→未来10/20次均没有通过校正的可重复优势。但有应当披露的局部线索：癸亥在2017—2020筛选后，2021—2022下跌11/12，在一种控制牛熊的条件零假设下有较强局部证据；2023以后却降至10/24。因此它支持“早期阶段值得研究”，不支持“已经找到稳定跨期赢家”。\n',
 '本报告是方向持续性研究，不讨论EV、波动预测或虚构交易收益。只新增研究文件，正式日历、统计、API及交易逻辑没有修改。\n',
 '## 2. 数据与固定研究设计\n',
 '使用仓库真实Binance BTCUSDT现货UTC+8日线，最新已收盘为 **2026-10-20**。上市首根不完整日、三处源收盘时间异常、未收盘数据排除；昨收口径另外排除前收无效的日期。原始Decimal价格比较决定方向，平盘保留分母。时间和干支标签按正式系统核对，且所有已完成源K线已与当前本地行情库只读核对一致。\n',
 table(['口径','有效样本','第一日','最后日','上涨','下跌','平盘'],[[BS[r['basis']],r['n'],r['first'],r['last'],r['up'],r['down'],r['flat']] for r in read('data_audit')]),
 table(['分割','训练','冻结验证','用途'],[[r['id'],r['train_start']+'—'+r['train_end'],r['test_start']+'—'+r['test_end'],'主要预定分割'] for r in P['splits']]),
 '每个分割内部训练、验证完全不重叠；但S1的2023验证也是S3的训练，S2的2021—2022验证也是S1训练的一部分。因此不能把三次结果相乘或称为三个独立重复试验。额外的逐年3年训练→1年验证也明确属于相关的探索性检查。\n',
 '方向仅由训练期多数决定，平票不预测；三个训练门槛为55%、60%、65%，三个验证门槛也固定为55%、60%、65%，使用整数次数比较，不用四舍五入百分比筛选。验证期绝不重新选择优势方向。所有60干支都导出，包含没入选者。\n',
 '## 3. 三档高胜率：到底延续了多少\n']
doc.append(table(['口径','训练门槛','入选','验证仍≥55%','验证仍≥60%','验证仍≥65%'],[
 [BS[b],f'{t}%',next(r['selected'] for r in COUNTS if r['split']=='S1' and r['basis']==b and r['train_threshold']==t),
  *[next(r['continued'] for r in COUNTS if r['split']=='S1' and r['basis']==b and r['train_threshold']==t and r['test_threshold']==v) for v in TH]]
 for b in ['oc','cc'] for t in TH]))
doc+=['“前期≥55%的25个中，后期7个≥60%”和“两个时期都≥60%的3个”是不同统计，不能混淆。小样本还使门槛离散化：验证只有23次时，≥55%需要13/23，≥60%需要14/23，≥65%需要15/23。\n',
 '### 两期都至少60%的全部个体\n',individual_table([r for r in MAIN if r['basis']=='oc' and r['selected60'] and r['continues60']]),
 '这三例在昨收口径的训练/验证次数相同；两种口径来自同一批相近价格路径，不是独立复制证据。\n',
 '### 开收盘口径：训练≥55%的25个逐一验证\n',individual_table([r for r in MAIN if r['basis']=='oc' and r['selected55']]),
 '### 昨收口径：训练≥55%的25个逐一验证\n',individual_table([r for r in MAIN if r['basis']=='cc' and r['selected55']]),
 '“仍≥55%”只是算术达标，不等于已证明真实概率高于BTC。表中个体校正p使用全部3分割×2口径×60干支×4方法的1,440项随机化检验，展示最小值也没有通过；完整各方法p和较窄家族诊断全部保留。\n',
 '## 4. 随机零假设如何建立，为什么不只是换名字\n',
 '随机检验针对“干支标签没有稳定的独立方向关联”。BTC整体并非固定50%上涨，因此没有把每根日K当成公平硬币。每个模拟完整重排、重算训练多数方向、重新按门槛选名单，然后在不重选方向的验证期计数。每方法/口径19,999次，共159,992个完整模拟路径；同一条路径同时评价所有分割和门槛。\n',
 table(['方法','精确保留','主要破坏/限制'],[
 ['年×星期分层','每年每星期的上涨/下跌/平盘总数','破坏连续顺序；依赖分层内可交换假设'],
 ['年×星期×牛熊分层','上述总数及事前牛熊状态内方向比例','仍破坏序列；条件协变量固定，不重建自洽价格路径'],
 ['年内28日整块重排','每年及星期总数、块内连续方向/幅度序列','跨块连接破坏；移动28的倍数还保留干支序号mod4，因此是较受限敏感性'],
 ['按年整周循环错位','每年及星期总数，绝大多数连续序列','每年独立错位，年内循环接缝及无效周间断打破少量连接']]),
 '无效日、年初年末不完整周/块保持原位，不跨年份偷换样本；完整周/块只在同年移动，星期位置不变。映射同时可用于方向、收益和幅度整束，聚集性审计直接计算原始收益绝对值的lag1相关。方向检验本身不使用幅度作为预测指标。\n',
 '特别避免错误零假设：对所有日期只给干支统一加一个常数，只会把60个名字轮换，持续达标的总数完全不变。该错误方法已用测试演示，未用于统计。60日整块移动也会保留相位而失效。整周移动的7与60互质，并且每年独立，审计中512个抽样映射均没有出现单一全局干支相位替换。28与60最大公约数4的限制明确保留，不能把28日方法当成唯一“完全随机”零假设。\n',
 table(['口径','方法','保留原始相邻日连接','方向lag1：原始→模拟','绝对收益lag1：原始→模拟','全局只改名字映射'],[
 [BS[r['basis']],MN[r['method']],pct(r['original_neighbor_links_preserved_mean']),num(r['sign_lag1_original'],3)+' → '+num(r['sign_lag1_null_mean'],3),
  num(r['absolute_return_lag1_original'],3)+' → '+num(r['absolute_return_lag1_null_mean'],3),str(r['constant_global_phase_maps'])+'/'+str(r['sampled_mappings'])] for r in AUD]),
 '这些是不同假设下的条件参考分布，尤其时间块并非对真实非平稳金融过程的精确生成模型。分层方法严格固定相应比例，区块/错位方法尽量保留依赖；四者一致的结果比任选一种更可信，但它们不是独立实验。\n',
 '## 5. 12/25与11/25究竟异常吗\n',
 '必须区分两个问题：完整流程中随机候选数量也变化；另一个是已经知道候选恰好25个之后，持续数量是否异常。两种都报告，避免把“随机平均持续11个”误读为“在固定25个中随机应有11个”。\n',
 table(['口径','方法','真实持续/入选','随机候选均值','随机持续均值','随机持续95%范围','经验p','p的MC95%区间','主家族Holm p'],[
 [BS[r['basis']],MN[r['method']],f"{r['continued']}/{r['selected']}",num(r['null_selected_mean'],2),num(r['null_mean'],2),f"[{r['null_low']:.0f}, {r['null_high']:.0f}]",num(r['p']),
  '['+num(r['p_mc_low'])+', '+num(r['p_mc_high'])+']',num(r['p_holm'])]
 for r in NULL if r['split']=='S1' and r['train_threshold']==55 and r['test_threshold']==55]),
 '### 补充：实际25个名字和方向也完全固定，只随机验证期\n',
 '这项次级条件对照从既有个体零分布推导，在查看主要结果后为澄清条件含义追加，完整覆盖同样门槛/分割/口径/方法216项并校正。它没有替代每次都重新筛选的主检验，也不是一份新增独立确认。\n',
 table(['口径','方法','实际持续/固定候选','随机持续均值','95%范围','经验p','次级Holm p'],[
 [BS[r['basis']],MN[r['method']],f"{r['continued']}/{r['selected']}",num(r['null_mean'],2),f"[{r['null_low']:.0f}, {r['null_high']:.0f}]",num(r['p']),num(r['p_holm'])]
 for r in FIXED if r['split']=='S1' and r['train_threshold']==55 and r['test_threshold']==55]),
 table(['口径','方法','随机中恰好选25的次数','条件随机持续均值','条件95%范围','条件经验p','条件p的MC95%区间'],[
 [BS[r['basis']],MN[r['method']],r['exact_n_conditional_draws'],num(r['exact_n_conditional_mean'],2),f"[{r['exact_n_conditional_low']:.0f}, {r['exact_n_conditional_high']:.0f}]",num(r['exact_n_conditional_p']),
  '['+num(r['exact_n_conditional_mc_low'])+', '+num(r['exact_n_conditional_mc_high'])+']']
 for r in NULL if r['split']=='S1' and r['train_threshold']==55 and r['test_threshold']==55]),
 '**结论：12/25和11/25均可由正常随机波动解释，没有显著超出零假设。** 条件样本只有约几百次，因此另外给出Monte Carlo区间；它只描述模拟p值的数值误差，不是经济规律的真实概率区间。主结果同时比较持续比例和恰好同候选数的次级统计，校正后也没有显著结果。\n',
 '![开收盘随机持续分布](results/null_counts_oc.png)\n','![昨收随机持续分布](results/null_counts_cc.png)\n',
 '主计数家族：3训练门槛×3验证门槛×3时间分割×2口径×4零假设=216项，联合Holm；年度滚动另432项。持续比例/同候选数是次级家族，不能事后用最有利的一项替换主指标。经验p按(尾部次数+1)/(模拟数+1)，不会出现“p=0”。所有原始、校正值及直方分布均已导出。\n',
 '## 6. 逐个代表性干支：基准、区间与证据强弱\n',
 '验证期市场上涨比例本身约53%，所以看涨60%与看跌60%的超额大小不同。除了同方向整体BTC基准，还按每个干支验证日的年份×星期匹配、排除该干支后计算市场基准。以下使用更长的180日历日区块区间，尽量保留相邻几次流日（相隔60天）的依赖；60日区块主区间和Wilson区间另外保留。区间是逐点而非60组同时区间。\n',
 table(['干支','冻结方向','前期成功/总数','后期成功/总数','后期胜率','同方向整体BTC','年×星期匹配基准','超额及180日95%区间','分层原始p','全部个体Holm p'],[
 [r['ganzhi'],SIDE[r['direction']],ratio(r,'train'),ratio(r,'test'),pct(r['test_rate']),pct(r['btc_same_direction_rate']),pct(r['matched_leave_group_rate']),
  signed(r['matched_excess'])+' ['+signed(r['block180_matched_excess_low'])+', '+signed(r['block180_matched_excess_high'])+']',num(r['year_weekday_p']),num(r['best_global_holm_p'])]
 for label in CASES for r in MAIN if r['basis']=='oc' and r['ganzhi']==label]),
 '甲子下跌19/32→15/24是准确的个体持续现象，后期比匹配基准约高16.84个百分点，但只有24次，180日区块区间仍触及零，普通分层随机化p约0.076，未达未校正的5%门槛，更不能越过60组搜索问题。庚午、甲申、丙申都在60%以上，但其区间宽，尚不足证明超过普通BTC上涨倾向。\n',
 '![逐干支训练与验证胜率](results/individual_persistence.png)\n',
 '### 不应忽略的局部线索：癸亥在2021—2022\n']
gh=next(r for r in G if r['split']=='S2' and r['basis']=='oc' and r['ganzhi']=='癸亥')
exact=[r for r in IND if r['split']=='S2' and r['basis']=='oc' and r['ganzhi']=='癸亥' and r['method'].startswith('year_weekday')]
doc.append(f"癸亥在S2训练期下跌 **{ratio(gh,'train')}（{pct(gh['train_rate'])}）**，冻结方向后2021—2022下跌 **{ratio(gh,'test')}（{pct(gh['test_rate'])}）**。这不是可以忽略的普通52%汇总现象。两种独立分层零假设还可作解析校验：同干支每个年×星期最多只有一个验证日期，因此成功次数服从不同概率Bernoulli之和，卷积可算出同一零假设的精确尾部概率，避免罕见事件的模拟误差。\n")
doc.append(table(['分层零假设','模拟p','同一零假设解析p','只限该口径/该分割60组校正','该方法全部分割/口径360组校正','两种解析零假设720项校正'],[
 [MN[r['method']],num(r['p'],6),num(r['p_exact'],6),num(r['p_exact_holm_split_basis60'],6),num(r['p_exact_holm_method360'],6),num(r['p_exact_holm_all720'],6)] for r in exact]))
doc+=['在控制牛熊的这一分层假设下，若研究范围事先仅限S2、开收盘口径、60干支，解析Holm p约0.033，属于有一定强度的局部线索；普通年×星期假设下，60组校正约0.18。扩大到本次实际考察的多个分割/口径/方法后，证据不再通过校正。两种解析概率只是同一分层随机化的数值核验，不是两份新的独立证据。\n',
 '更关键的是，癸亥2023以后只有10/24下跌。早期相邻两段的强表现不能保证第三段继续。统计结果无法证明它为何改变：可能是小样本选择后的回归、市场阶段性关系或偶然排列；没有因果证据将失效归因于某个宏观事件，也不能据此断言将来必然均值回归或反向。其早期线索值得透明披露，但没有形成跨2023的稳定优势。\n',
 '## 7. 逐年与牛熊环境：是否仅由一两个年份贡献\n',
 '主验证期每组通常每年只有5—6次，年度比例以大步长跳动，不能把4/6与3/6的差别当精确概率变化。下表每格直接展示成功/总数。2026为截至10月20日的部分年度。\n',
 table(['干支','冻结方向','2023','2024','2025','2026至今','年度≥55%次数','年度≥60%次数','超过年度BTC基准次数'],[
 [label,SIDE[next(r for r in MAIN if r['basis']=='oc' and r['ganzhi']==label)['direction']],
  *[next((f"{r['success']}/{r['n']}" for r in YEAR if r['split']=='S1' and r['basis']=='oc' and r['ganzhi']==label and r['year']==yr),'—') for yr in range(2023,2027)],
  next(r['years_ge55'] for r in consistency if r['split']=='S1' and r['basis']=='oc' and r['ganzhi']==label),
  next(r['years_ge60'] for r in consistency if r['split']=='S1' and r['basis']=='oc' and r['ganzhi']==label),
  next(r['years_above_btc_baseline'] for r in consistency if r['split']=='S1' and r['basis']=='oc' and r['ganzhi']==label)] for label in CASES]),
 '![代表干支逐年次数](results/case_yearly.png)\n',
 '丙申的逐年形状值得单独保留：2023—2025各4/6、2026至今3/5，四个验证年度都≥60%，比甲申、庚午更均匀。它不只是某一个年度贡献全部优势。但每年仅5—6次，总计15/23；在本次预定的个体验证随机检验中仍未超过多重比较门槛。不能因其他组失效就忽视它，也不能事后专挑“连续四年达标”这一形状另算一个未校正的成功概率。\n',
 '牛熊标签只用当日开始前的有效收盘：前收相对过去200个收盘均线、过去90个有效收盘涨跌超过±10%，否则震荡；历史不足200个为unknown。状态是控制因素，不是事后根据完整周期挑选。\n',
 table(['干支','冻结方向','环境','成功/总数','胜率','同环境其他BTC基准'],[
 [r['ganzhi'],SIDE[r['direction']],r['regime'],f"{r['success']}/{r['n']}",pct(r['rate']),pct(r['baseline'])]
 for label in CASES for r in REG if r['split']=='S1' and r['basis']=='oc' and r['ganzhi']==label]),
 '完整25候选及全部60组逐年/环境表都在CSV中。分层控制牛熊的零假设没有使主12/25现象显著；环境内更小的个体样本不足以证明某流日在牛熊都稳定有效。\n',
 '## 8. 前期越高，后期是否越强\n',
 '同时报告原始上涨率相关、冻结训练多数方向后的相关，以及训练≥55/60/65的候选内相关。它们不同：验证期不能重新改成更成功的方向。稀少候选的相关系数尤其不稳。正相关的显著性同样在每次随机模拟中重新选训练方向与候选，4方法合计240项校正。\n',
 table(['口径','队列','Pearson','Spearman','四方法正关联p范围','最小Holm p'],[
 [BS[b],cohort,next(r['value'] for r in COR if r['basis']==b and r['split']=='S1' and r['cohort']==cohort and r['statistic']=='pearson' and r['method']==METHODS[0]),
  next(r['value'] for r in COR if r['basis']==b and r['split']=='S1' and r['cohort']==cohort and r['statistic']=='spearman' and r['method']==METHODS[0]),
  num(min(r['p'] for r in COR if r['basis']==b and r['split']=='S1' and r['cohort']==cohort))+'—'+num(max(r['p'] for r in COR if r['basis']==b and r['split']=='S1' and r['cohort']==cohort)),
  num(min(r['p_holm'] for r in COR if r['basis']==b and r['split']=='S1' and r['cohort']==cohort))] for b in ['oc','cc'] for cohort in CORR_COHORTS]),
 table(['口径','前期胜率区间','干支数','前期平均胜率','后期个体平均胜率','后期成功/总数'],[
 [BS[r['basis']],r['train_bin'],r['groups'],pct(r['train_rate_mean']),pct(r['test_rate_mean']),f"{r['test_success']}/{r['test_n']}"] for r in read('training_strength_bins') if r['split']=='S1']),
 '没有证据表明前期更高的方向胜率能稳定排序出未来更高者。主≥55候选的Pearson反而为负，但这不证明存在可交易的“反向规律”；不能看见负号就事后把原先冻结方向翻过来。\n',
 '## 9. 多种分割与年度滚动稳健性\n',
 table(['分割','口径','训练门槛','入选','后期≥55%','后期≥60%','后期≥65%'],[
 [split['id'],BS[b],f'{t}%',next(r['selected'] for r in COUNTS if r['split']==split['id'] and r['basis']==b and r['train_threshold']==t),
  *[next(r['continued'] for r in COUNTS if r['split']==split['id'] and r['basis']==b and r['train_threshold']==t and r['test_threshold']==v) for v in TH]]
 for split in P['splits'][1:] for b in ['oc','cc'] for t in TH]),
 '另在每年1月1日用此前完整3年冻结名单，预测下一公历年；年际训练重叠，最后一年未完整。下表仅列训练55%主门槛，其他门槛已包含在探索性432项校正家族。\n',
 table(['验证年度','口径','候选','仍≥55%','仍≥60%','仍≥65%'],[
 [year,BS[b],next(r['selected'] for r in COUNTS if r['split']==f'Y{year}' and r['basis']==b and r['train_threshold']==55),
  *[next(r['continued'] for r in COUNTS if r['split']==f'Y{year}' and r['basis']==b and r['train_threshold']==55 and r['test_threshold']==v) for v in TH]] for year in range(2021,2027) for b in ['oc','cc']]),
 '各年度验证通常只有约6次/干支，因此55%、60%、65%有时对应完全相同的成功次数门槛。没有通过年度滚动家族校正的持续数量异常，不能将几个相关年份中的好看比例拼成独立确认。\n',
 '## 10. 过去30次≥60%，未来10/20/30次怎么样\n',
 '每个流日仅用过去30个有效出现记录，达到至少18/30才选定同一方向；接下来10、20、30次冻结预测。主版本每次出现都可启动一个窗口，因此大量重叠；另用事先固定的每H次启动一次的网格，展示未来窗口不重叠的对照。网格推进不依赖上一窗口是否入选，避免挑选最好起点。\n']
win=read('rolling_windows');overlap=[]
for row in ROLL:
    used=[r for r in win if r['basis']==row['basis'] and r['horizon']==row['horizon'] and r['policy']==row['policy']]
    actual=set()
    for w in used:
        valid=df[(df[w['basis']+'_valid'])&(df.g==w['g'])&(df.date>=w['test_first'])&(df.date<=w['test_last'])]
        actual.update(valid.date.tolist())
    overlap.append(dict(basis=row['basis'],horizon=row['horizon'],policy=row['policy'],windows=len(used),unique_test_dates=len(actual),unique_groups=len(set(w['g'] for w in used))))
save('rolling_overlap_audit',overlap)
doc.append(table(['口径','未来次数','窗口规则','入选窗口','重复计数成功/总数','去重实际日期','命中率','相对匹配基准差','校正p最小—最大'],[
 [BS[r['basis']],r['horizon'],r['policy'],r['selected_windows'],f"{r['success']}/{r['n']}",next(x['unique_test_dates'] for x in overlap if x['basis']==r['basis'] and x['horizon']==r['horizon'] and x['policy']==r['policy']),
  pct(r['hit_rate']),signed(r['excess_rate']),num(min(x['p_holm'] for x in RN if x['basis']==r['basis'] and x['horizon']==r['horizon'] and x['policy']==r['policy']))+'—'+num(max(x['p_holm'] for x in RN if x['basis']==r['basis'] and x['horizon']==r['horizon'] and x['policy']==r['policy']))]
 for r in ROLL if r['horizon'] in [10,20]]))
doc+=['完整流程随机化也重新执行“过去30次筛选”，控制年度/星期或状态基准后，32项未来超额命中检验没有显著优势。重复窗口中的3,320等计数不是3,320根独立日K，也不是几百个独立交易试验；模拟保持同样重叠，不能用普通二项标准误制造小p值。\n',
 '**未来30次：没有完整可用窗口。** 每个干支目前最多56次出现，过去30＋未来30至少需要60次。因此本研究没有用少于30次的未完成窗口冒充验证。一个干支大约60个自然日出现一次，未来10/20/30次约跨600/1200/1800天，样本增长很慢。\n',
 '## 11. 具体哪些持续，哪些反转\n']
for basis in ['oc','cc']:
    keep=[r for r in MAIN if r['basis']==basis and r['persistent55']];rev=[r for r in MAIN if r['basis']==basis and r['reversal']]
    doc.append(BS[basis]+'持续≥55%：'+ '、'.join(r['ganzhi']+'（'+SIDE[r['direction']]+' '+ratio(r,'test')+'）' for r in keep)+'。\n')
    doc.append(BS[basis]+'跌至同方向不足50%：'+'、'.join(r['ganzhi']+'（'+ratio(r,'test')+'）' for r in rev)+'。\n')
doc+=['其中“明显反转”预先定义为后期同方向≤40%，并不自动等于统计上证实有反向优势。完整名单、成功次数、变化幅度、逐年及冻结池未来出现次数曲线均在CSV。没有按验证表现重新选择方向或修改训练名单。\n',
 table(['口径','验证前几次出现','具备完整记录的干支','同方向成功/总数','汇总命中','个体仍≥55%数量'],[
 [BS[r['basis']],r['step'],r['groups'],f"{r['success']}/{r['n']}",pct(r['pooled_rate']),r['groups_still55']] for r in read('frozen_pool_prefix_curve')]),
 '这些曲线只是事先固定的期限描述，没有从1、5、10、15、20、24次中挑出最高者作为结论；30次缺失保持缺失。个体可在几个阶段持续，也可能在更晚阶段失效，不能把一次漂亮的验证视为永久参数。\n',
 '## 12. 证据分级与后续建议\n',
 '**得到数据支持的事实：** 指定12/25、11/25及三个双60%个体均被独立复算确认；甲子存在真实记录的同方向持续，癸亥存在早期强、后期失效的阶段变化。\n',
 '**局部值得保留的线索：** 癸亥2021—2022在特定事前状态分层零假设、限定单一分割单一口径60组时有一定显著性。但更广研究家族和2023以后均不支持稳定延续。不能因为总体没有优势就删掉这个例子，也不能因这个例子好看就忽略失败的第三期。\n',
 '**尚无充分证据的主张：** 存在可预先识别、跨时期稳定高于BTC基准的干支集合；训练胜率越高后期必然更好；或者可以把当期高胜率名单直接变成自动交易规则。主检验、完整个体家族、相关性及滚动未来窗口均未提供足够支持。\n',
 '最终建议是保留为个体研究与未来验证清单，暂不改变正式预测/交易功能。若要确认，必须在未使用的新数据上事先冻结方向、门槛、名单、验证期限、基准和检验家族；当前已观察历史的追加分割不能冒充新确认样本。没有证据断言所有规律永久不存在，亦没有证据承诺这些个体将继续保持约60%。\n',
 '## 13. 已执行核验、数值误差与方法来源\n',
 table(['项目','实际结果'],[[k,str(v)] for k,v in read('verification').items()]),
 '研究从原始价格重新解析，不导入此前EV或波动分析代码。所有训练/验证方向计数与当前正式系统只读交叉核对；完整模拟原始数组、分布直方、p值、校正家族和16项实际测试均保留。部分运行日志包含中断后重启记录，以evaluation-final.log及核验文件为准，不将中断当作完成。\n',
 '随机化的精确性依赖各自的可交换性/近似平稳假设；年份和状态分层无法完美描述金融结构变动。bootstrap区间是逐点近似，60日与180日结果均保留。过多窗口、极少验证样本和研究者已看过历史会限制结论，不应把不显著当成“真实效果严格为零”。\n',
 '参考：[SciPy随机化检验及加一p值](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html)、[Phipson与Smyth原论文](https://gksmyth.github.io/pubs/PermPValuesPreprint.pdf)、[Holm多重检验](https://www.statsmodels.org/v0.14.4/generated/statsmodels.stats.multitest.multipletests.html)。外部来源只支持统计方法，所有行情结果来自仓库实际执行。\n']

append=['# 六十甲子：全部训练、验证与持续性明细\n','[返回报告](REPORT.md) · [全部1080行CSV](results/ganzhi_splits.csv)\n',
 '每个表均含全部60个干支；方向只在训练期决定。年度滚动没有单独的个体显著性检验，校正p留空而非假定通过。表中“仍≥55%”是冻结方向的验证算术达标；是否训练入选请看训练胜率/CSV的selected55。\n']
for split in all_splits():
    for basis in ['oc','cc']:
        append.extend(['## '+split['id']+'｜'+BS[basis]+'\n',split['train_start']+'—'+split['train_end']+'训练，'+split['test_start']+'—'+split['test_end']+'验证。\n',individual_table([r for r in G if r['split']==split['id'] and r['basis']==basis])])

repro='''# 高胜率持续性研究：复现、字段与文件索引

[完整报告](REPORT.md) · [全部60干支明细](GANZHI_DETAILS.md)

## 独立性和数据

本目录从snapshot.json的原始OHLC、收盘时间和干支标签独立计算，不导入以往研究结果或代码。快照是仓库真实UTC+8数据的冻结副本，截止2026-10-20收盘。source_daily.csv保留全部源日期和剔除原因；未收盘/异常行不进训练验证。manifest.json记录源、协议和Git基线。初始协议与任何计算前的两项方法澄清均保留。

## 环境与执行

Python3.12，依赖见requirements-research-lock.txt。可建立本目录独立.venv，也可使用现有科学研究环境。仓库根目录：

```powershell
$rp = '.\\research\\ganzhi_volatility_2026-10-21\\.venv\\Scripts\\python.exe'
& $rp research/ganzhi_persistence_2026-10-21/run_observed.py
& $rp research/ganzhi_persistence_2026-10-21/simulate.py
& $rp research/ganzhi_persistence_2026-10-21/bootstrap.py
& $rp research/ganzhi_persistence_2026-10-21/evaluate.py
& $rp -m pytest research/ganzhi_persistence_2026-10-21/test_research.py -q --junitxml=research/ganzhi_persistence_2026-10-21/results/unit-tests.xml
& .\\.venv\\Scripts\\python.exe research/ganzhi_persistence_2026-10-21/verify_production.py
& $rp research/ganzhi_persistence_2026-10-21/verify.py
& $rp research/ganzhi_persistence_2026-10-21/make_report.py
```

run_observed先执行；simulate和bootstrap可独立运行但须全部完成后evaluate。主模拟批量固定256，随机种子固定，每次完整重选训练方向及名单。缓存按源/协议/core/simulate文件哈希校验；改动会触发重算。evaluate一次性解压每个模拟文件；不得在循环中反复读取NPZ成员。正式规则核验需现有项目环境和calendar.db，仅以SQLite mode=ro读数据库。截图QA另需Node/Playwright/Edge，不影响数值研究。

## 主要结果

| 文件 | 内容 |
| --- | --- |
| source_daily.csv / data_audit.json | 独立解析的方向、时区、有效性、剔除及数据范围 |
| ganzhi_splits.csv | 1080行：全部60×2口径×9分割，原始上涨/下跌/平盘、冻结方向、训练验证k/n、基准及主分割区间/p |
| main60_details.csv | 主分割120行完整明细 |
| main_selected55.csv / main_persistent55.csv / main_both60.csv / main_reversed.csv | 候选、持续、双60%、反转名单 |
| persistence_counts.csv | 162个真实门槛计数，含主54项及年度108项 |
| null_persistence_tests.csv | 4方法共648行；主216项与年度432项分家族校正，含固定候选数条件对照 |
| null_count_histograms.csv | 全部计数零分布直方图，可独立绘图 |
| null_main55_draws.csv.gz | 159992条主55%完整模拟的候选及持续55/60/65数量 |
| fixed_training_pool_validation_tests.csv | 次级条件对照：训练选中的具体名字及方向固定，随机验证期；完整216项另校正，追加范围记录于conditional_supplement.json |
| null_*_*.npz | 全部分割、门槛、个体、关联和滚动窗口的逐次模拟数组 |
| null_structure_audit.csv | 年份/星期约束、相邻日连接及方向/绝对收益lag1相关审计 |
| individual_randomization.csv | 1440行固定真实训练方向后的验证随机检验，原始/多家族Holm、解析p值核对 |
| group_block_intervals.csv | 主360组×60/180日区块的率/匹配基准差逐点区间，重算每次benchmark |
| correlation_tests.csv / training_strength_bins.csv | 240项原始上涨/冻结方向/候选内相关检验及前期胜率分档 |
| ganzhi_validation_yearly.csv / ganzhi_validation_regimes.csv | 主分割全部干支的逐年、事前市场状态 |
| year_consistency.csv | 各干支验证年度≥55%/超过该年市场基准的次数及最差最好年份，描述性不作为独立重复证据 |
| annual_market_baselines.csv | 各年BTC涨跌比例，未假设50% |
| rolling_windows.csv / rolling_summary.csv | 过去30次≥60%→完整未来10/20/30次，重叠及固定不重叠窗口 |
| rolling_null_tests.csv / rolling_overlap_audit.csv | 重跑筛选的未来超额检验32项及真实日期去重；未来30次缺失 |
| frozen_pool_prefixes.csv / frozen_pool_prefix_curve.csv | 主固定池按1/5/10/15/20/24/30出现次数的持续曲线 |
| unit-tests.xml / production_verification.json / verification.json | 实际测试、正式规则只读核对及独立数值核验 |

CSV为UTF8 BOM，概率小数0.01表示1%。direction=+1上涨，-1下跌，0训练平票无预测。selected55是训练筛选，continues55仅是验证同方向达标；persistent55要求前后都达标。成功次数永远相对于训练冻结方向，不能用验证多数方向替代。

## 模拟数组轴与p值

NPZ文件每basis/method一个，draw轴19999。splits顺序S1/S2/S3/Y2021...Y2026；门槛轴55/60/65。candidates=(draw,9,3)，continued=(draw,9,3,3)。individual=(draw,3,60)只随机验证结果、保持实际训练方向固定。correlations=(draw,3,10)，依次raw_up_all/frozen_majority_all/selected55/selected60/selected65，每组Pearson/Spearman。rolling=(draw,6,5)，期限/政策按10overlap、10nonoverlap、20overlap、20nonoverlap、30overlap、30nonoverlap；末轴为入选窗口数、成功数、未来≥60窗口数、超过匹配市场的成功数、总可用窗口数。

主计数216项一起Holm，年度滚动432项另校正；比例/恰好同候选数的检验为次级216/432家族。个体主家族1440，另给单方法360、主分割480、单方法主分割120和限定单分割口径方法60的诊断，不能只挑最小者当主结论。解析p是两种分层零假设的同一概率精确求值，共720项，同时保留单方法360/限定60校正。关联240项，未来窗口超额32项。缺失30次验证不纳入32项，也不伪造0命中。

Monte Carlo区间描述随机模拟数值误差；零分布95%范围是随机现象的参考范围；组别区块/Wilson区间估计胜率或超额的不确定性，三者不可混用。Bootstrap条件在训练方向不变，不是对整个训练筛选器再拟合；完整筛选不确定性由全流程随机化检验承担。匹配基准在每个区块抽样中重算，极少空的其他组分层用原样本leave-group概率，计数见输出。区间非同时区间，最终显著性用多重检验。

整周/区块移动不重建自洽金融价格过程；状态分层条件在原始事前状态协变量。28日移动保留干支序号mod4，是受限敏感性。统一相位改名和60日块移动不能用作本题零假设。测试明确验证了这个陷阱，以及未来扰动不改变训练方向、完整重筛计数、解析概率、模拟批次复现和未来30次数据不足。
'''

def render(name,text):
    text=text.rstrip()+'\n';(ROOT/(name+'.md')).write_text(text,encoding='utf-8')
    body=markdown.markdown(text,extensions=['tables','fenced_code']).replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')
    for n in ['REPORT','GANZHI_DETAILS','REPRODUCE']:body=body.replace('href="'+n+'.md"','href="'+n+'.html"')
    css='''*{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#233246;font:15px/1.85 "Microsoft YaHei",sans-serif}main{max-width:1380px;margin:24px auto;padding:34px 42px;background:#fff;border:1px solid #d8e1eb;border-radius:10px}h1{font-size:27px;color:#173f65}h2{margin-top:38px;padding-top:20px;border-top:1px solid #e2e8f0;color:#234d70}h3{font-size:18px}p,li{overflow-wrap:anywhere}a{color:#226cb0}.table-wrap{overflow-x:auto;margin:20px 0;border:1px solid #dce4ed}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th,td{padding:8px 11px;text-align:left;border-bottom:1px solid #e6edf4}th{background:#edf3f8}tr:nth-child(even){background:#f8fafc}img{display:block;max-width:100%;height:auto;margin:25px auto}pre{overflow-x:auto;padding:16px;background:#edf2f7}code{font:13px Consolas,monospace}@media(max-width:700px){main{margin:0;padding:17px 14px;border:0}h1{font-size:23px}body{font-size:14px}}'''
    (ROOT/(name+'.html')).write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+name+'</title><style>'+css+'</style></head><body><main>'+body+'</main></body></html>',encoding='utf-8')
render('REPORT','\n'.join(doc));render('GANZHI_DETAILS','\n'.join(append));render('REPRODUCE',repro)
summary=dict(main_count_significant=sum(r['kind']=='main' and r['p_holm']<.05 for r in NULL),
    annual_count_significant=sum(r['kind']!='main' and r['p_holm']<.05 for r in NULL),
    global_individual_significant=sum(r['p_holm_all1440']<.05 for r in IND),
    correlation_significant=sum(r['p_holm']<.05 for r in COR),rolling_significant=sum(r['p_holm'] is not None and r['p_holm']<.05 for r in RN),
    local_guihai_exact_regime_p=next(r['p_exact'] for r in exact if r['method']=='year_weekday_regime'),
    local_guihai_exact_holm60=next(r['p_exact_holm_split_basis60'] for r in exact if r['method']=='year_weekday_regime'))
save('report_summary',summary);print('PERSISTENCE_REPORT_DONE',json.dumps(summary))
