"""Chinese report, complete sixty-group appendices and scientific figures."""
from core import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import markdown
import html,re

plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10,'figure.dpi':140,'axes.spines.top':False,'axes.spines.right':False})
COL=['#334E68','#4682B4','#C99536']
NAMES={'iid50':'独立 p=50%','iid_actual':'独立 p=实际上涨率','fixed_total':'固定分期涨跌总数','year_weekday':'年×星期内置换','weekly_rotation':'每年独立整周循环'}

def read(name):return json.loads((OUT/(name+'.json')).read_text('utf-8'))
def find(rows,**kw):return next(r for r in rows if all(r.get(k)==v for k,v in kw.items()))
def pc(x,d=2):return f'{100*x:.{d}f}%'
def pv(x):return f'{x:.6f}' if x>=.0001 else f'{x:.3g}'
def tab(h,rows):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n\n'
def figure(name):plt.savefig(OUT/name,bbox_inches='tight');plt.close()

def plots():
    bins=read('theoretical_distribution_bins');counts=read('threshold_counts_exact');joints=read('cross_period_exact');mc=read('monte_carlo_tests');split=read('split60')
    fig,axes=plt.subplots(2,2,figsize=(13,8))
    for ib,basis in enumerate(P['bases']):
        for col,mode in enumerate(['up','dominant']):
            ax=axes[ib,col];x=np.arange(len(BINS)-1)
            for off,null in [(-.26,'iid50'),(0,'iid_actual')]:
                rr=[r for r in bins if r['basis']==basis and r['period']=='full' and r['mode']==mode and r['null']==null]
                ax.bar(x+off,[r['expected'] for r in rr],width=.25,label=NAMES[null],color=COL[0 if off<0 else 1])
            ax.bar(x+.26,[r['observed'] for r in rr],width=.25,label='实际60个干支',color=COL[2])
            ax.set_xticks(x,[f'{100*a:g}–{min(100,100*b):g}' for a,b in zip(BINS[:-1],BINS[1:])],rotation=35,ha='right')
            ax.set_xlabel('胜率区间（%，左含右不含，末档含100%）');ax.set_ylabel('干支数量')
            ax.set_title(('开收盘' if basis=='oc' else '昨收')+'：'+('原始上涨胜率' if mode=='up' else '两方向取较高胜率'))
            ax.legend(fontsize=8)
    fig.tight_layout();figure('rate_distribution.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.3))
    for j,(title,data,field,actualkey) in enumerate([('全历史优势方向高胜率数量',counts,'expected','observed'),('前后期同方向双高胜率数量',joints,'expected_both','observed_both')]):
        ax=axes[j];x=np.arange(4)
        for off,null in [(-.25,'iid50'),(0,'iid_actual')]:
            rr=[find(data,basis='oc',null=null,threshold=h,**({'period':'full','side':'either'} if j==0 else {'family':'exact_primary68'})) for h in TH]
            ax.bar(x+off,[r[field] for r in rr],width=.24,color=COL[0 if off<0 else 1],label=NAMES[null])
        ax.bar(x+.25,[r[actualkey] for r in rr],width=.24,color=COL[2],label='实际数量')
        ax.set_xticks(x,[f'≥{h}%' for h in TH]);ax.set_ylabel('干支数量');ax.set_title(title+'（开收盘）');ax.legend(fontsize=8)
    fig.tight_layout();figure('threshold_counts.png')
    with np.load(OUT/'mc_oc_iid_actual_key_distributions.npz') as z:sd=z['full_sd']*100;joint=z['joint60']
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    observed=find(mc,basis='oc',null='iid_actual',statistic='full_sd')['observed']*100
    axes[0].hist(sd,bins=55,color=COL[1],alpha=.8,density=True);axes[0].axvline(observed,color='#B42318',label=f'实际 {observed:.3f} 个百分点')
    axes[0].set_xlabel('60个上涨胜率的样本标准差（百分点）');axes[0].set_title('随机标准差分布');axes[0].legend()
    counts0=np.bincount(joint.astype(int));x=np.arange(len(counts0));axes[1].bar(x,counts0/len(joint),color=COL[1],label='20万次模拟')
    er=find(joints,basis='oc',null='iid_actual',threshold=60,family='exact_primary68');pm=np.array(er['pmf']);axes[1].plot(np.arange(12),pm[:12],'.-',color=COL[2],label='精确 Poisson-binomial')
    axes[1].axvline(er['observed_both'],color='#B42318',label='实际3个');axes[1].set_xlim(-.5,11.5);axes[1].set_xlabel('同方向两期均≥60%的干支数');axes[1].set_title('双60%随机分布');axes[1].legend(fontsize=8)
    fig.tight_layout();figure('null_distributions.png')
    r=[r for r in read('individual_binomial_normal') if r['basis']=='oc' and r['period']=='full' and r['null']=='iid_actual'];r.sort(key=lambda x:x['p'])
    fig,ax=plt.subplots(figsize=(10,4));ax.plot([x['p'] for x in r],[100*abs(x['error_uncorrected']) for x in r],'o-',label='不做连续性校正',markersize=3,color=COL[2]);ax.plot([x['p'] for x in r],[100*x['absolute_error_cc'] for x in r],'o-',label='半整数连续性校正',markersize=3,color=COL[1]);ax.set_xlabel('精确双侧二项p值');ax.set_ylabel('正态近似绝对误差（概率百分点）');ax.legend();ax.set_title('同一离散拒绝区域的近似误差，开收盘全历史');fig.tight_layout();figure('normal_error.png')
    fig,axes=plt.subplots(1,2,figsize=(11,4.3));rr=[r for r in split if r['basis']=='oc']
    axes[0].scatter([r['train_up']/r['train_n']*100 for r in rr],[r['validation_up']/r['validation_n']*100 for r in rr],color=COL[1],alpha=.65)
    axes[0].set_xlabel('前期上涨胜率（%）');axes[0].set_ylabel('后期上涨胜率（%）');axes[0].set_title('所有60个干支，不翻转方向')
    frozen=[r for r in rr if r['validation_frozen_rate'] is not None]
    axes[1].scatter([r['train_rate']*100 for r in frozen],[r['validation_frozen_rate']*100 for r in frozen],color=COL[1],alpha=.65)
    for r in rr:
        if r['ganzhi'] in ['甲子','庚午','甲申','丙申','癸亥']:
            axes[1].annotate(r['ganzhi'],(r['train_rate']*100,r['validation_frozen_rate']*100),fontsize=9,xytext=(3,3),textcoords='offset points')
    axes[1].axhline(50,color='#8094A5',linestyle='--');axes[1].set_xlabel('前期所选优势方向胜率（%）');axes[1].set_ylabel('后期同一方向胜率（%）');axes[1].set_title('方向在前期选择，后期冻结')
    fig.tight_layout();figure('train_validation.png')

def main():
    plots();tot=read('period_totals');th=read('threshold_counts_exact');jo=read('cross_period_exact');mx=read('maximum_exact');mc=read('monte_carlo_tests');rk=read('rankings60');sp=read('split60');nr=read('normal_approximation_error');v=read('verification');ev=read('evaluation_summary')
    full=find(tot,basis='oc',period='full');gmax=find(mx,basis='oc',period='full',null='iid_actual');std=find(mc,basis='oc',null='iid_actual',statistic='full_sd')
    d='# 六十甲子胜率：二项分布、正态近似与随机显著性研究\n\n'
    d+='数据冻结于 **2026-10-24**，最新完整日线 **2026-10-23**。开收盘与昨收分别计算。此次是数学与统计审计，没有调交易参数，没有修改正式系统。\n\n'
    d+='## 1. 三个核心问题的回答\n\n'
    d+='**A：当前高胜率和跨期持续性在无干支预测力的模型下并不罕见。** 开收盘全历史有11个优势方向胜率≥60%的干支，至少出现这么多个的精确概率，在50%基准下为 **24.2299%**，在实际上涨比例基准下为 **44.1297%**。同方向前后两期都≥60%的干支有3个，至少出现3个的概率分别为 **61.4584%**、**75.7687%**。这些是零假设成立时事件的发生频率，**不是“这些规律为假的后验概率”**。\n\n'
    d+='**B：没有发现经过校正后显著的异常分布。** 原始上涨胜率、事后挑较高方向的折叠胜率、标准差、最高值、预先固定分箱的分布差异，都未超出相应随机模型的合理范围。全历史上涨胜率标准差为 **6.376 个百分点**，实际概率IID模拟的95%范围为 **5.479—7.871 个百分点**。\n\n'
    d+='**C：现有证据不足以支持可预测的未来优势。** 观察到个别干支在两期持续较高胜率是事实，但数量与强度可以由小样本、60组选优和市场上涨偏向解释。它不证明干支绝对无效，也不能推出下一次必然回归；要证明未来预测力仍需预先冻结名单、规则与检验家族，用尚未查看的新数据验证。此次没有检验交易收益，不能据此声称有实际交易价值。\n\n'
    d+='## 2. 真实数据、样本数与两种方向口径\n\n'
    d+=tab(['口径','时期','有效n','上涨','下跌','平盘','全部有效日上涨率','每干支n范围'],[[('开收盘' if r['basis']=='oc' else '昨收'),{'full':'全部','train':'2017—2022','validation':'2023—2026-10-23'}[r['period']],r['n'],r['up'],r['down'],r['flat'],pc(r['up_rate_all']),f"{r['n_min']}—{r['n_max']}"] for r in tot])
    d+='真实有效数据从2017-08-18起。排除上市首日、未收盘日、原始收盘时间异常的2018-02-08、2020-02-19、2020-12-21；昨收口径还排除紧随异常日的无效昨收样本。没有删除极端涨跌。原始3356根缓存、逐日排除原因和干支均保存在快照和CSV。\n\n'
    d+='**不把平盘当成下跌。** 表示胜率时分母n仍包括平盘；二项模型固定平盘日期，试验数m=n−平盘，K为上涨次数、m−K为下跌次数。历史实际基准p取1755/(1755+1595)=**52.3881%**；与显示的1755/3351=52.3724%略有不同。昨收基准同理为52.3753%。全部口径和时期分别处理，不混合。\n\n'
    overall=binomtest(full['up'],full['up']+full['down'],.5).pvalue
    d+=f'理想独立模型下，BTC整体二元上涨率相对50%的双侧p值为 **{pv(overall)}**。这反映BTC整体上涨偏向，不能归因于干支。实际p由同一数据估计，固定p的二项结果是**代入参考计算**，不是已消除未知参数影响的复合零假设精确检验；另外用固定总数超几何与条件随机化控制这个问题。\n\n'
    d+='## 3. 精确数学计算及正态近似\n\n'
    d+='固定p时，K~Binomial(m,p)，P(K=k)=C(m,k)p^k(1−p)^(m−k)。单方向“达到当前次数或更高”用精确尾和。个体主检验采用双侧概率排序：把概率质量不大于观察点质量的所有可能k相加，允许上涨与下跌两侧异常。不是在事后选好方向后只做单侧检验。\n\n'
    d+='正态近似使用均值mp、标准差√[mp(1−p)]，分别计算不校正与±0.5连续性校正。两者近似的是**同一个精确离散拒绝区域**；p≠50%时不直接用“2×较小单侧尾概率”代替概率排序双侧p值。近似只用于比较，所有正式结论使用精确计算或明确的条件随机检验。\n\n'
    d+=tab(['口径/时期，实际p基准','无校正平均绝对误差','连续性校正平均绝对误差','连续性校正最大误差'],[[('开收盘' if r['basis']=='oc' else '昨收')+'/'+r['period'],f"{r['mean_absolute_error_uncorrected']*100:.4f}个百分点",f"{r['mean_absolute_error_cc']*100:.4f}个百分点",f"{r['max_absolute_error_cc']*100:.4f}个百分点"] for r in nr if r['null']=='iid_actual'])
    d+='![正态近似误差](results/normal_error.png)\n\n'
    d+='每个干支上涨胜率K/n的理论均值mp/n、标准差√[mp(1−p)]/n。60组样本标准差S的理论平方期望为各组方差平均值，加组均值差异项Σ(μᵢ−μ̄)²/59。报告区分√E[S²]与E[S]，后者通过模拟得到，二者不完全相等。\n\n'
    d+='“两边挑较高”的胜率W=max(K,m−K)/n是**折叠的离散分布**，不能当成均值50%的普通二项比例。它在纯随机下也自然高于50%。其均值、方差用全部k的精确二项权重计算，分布与离散程度另行核验，详见折叠分布结果。\n\n'
    d+='## 4. 实际60组分布与理论分布\n\n'
    d+='![二项理论和实际胜率分布](results/rate_distribution.png)\n\n'
    d+='每个阈值h先换算为整数cᵢ=ceil(h×nᵢ)，精确保留不同n。固定上涨方向概率qᵢ⁺=P(K≥cᵢ)，下跌方向概率qᵢ⁻=P(K≤mᵢ−cᵢ)。当h>50%时两事件不重叠，事后允许任选方向的概率qᵢ=qᵢ⁺+qᵢ⁻。\n\n'
    d+='预期数量是Σqᵢ。观察数量T的**完整精确分布**来自多项式∏[(1−qᵢ)+qᵢz]的系数，即Poisson-binomial；尾概率P(T≥实测数量)通过系数求和，不用“60×平均概率”代替。\n\n'
    for basis in P['bases']:
        d+=f"### {'开收盘' if basis=='oc' else '昨收'}：优势方向达到门槛的数量\n\n"
        d+=tab(['门槛','实际','随机预期 p=50%','至少实际数量的p','随机预期 实际p','至少实际数量的p','60组至少有1组达门槛（实际p）'],[[f'≥{h}%',find(th,basis=basis,period='full',null='iid_actual',side='either',threshold=h)['observed'],f"{find(th,basis=basis,period='full',null='iid50',side='either',threshold=h)['expected']:.3f}",pv(find(th,basis=basis,period='full',null='iid50',side='either',threshold=h)['p']),f"{find(th,basis=basis,period='full',null='iid_actual',side='either',threshold=h)['expected']:.3f}",pv(find(th,basis=basis,period='full',null='iid_actual',side='either',threshold=h)['p']),pc(find(th,basis=basis,period='full',null='iid_actual',side='either',threshold=h)['prob_any'],4)] for h in TH])
    d+='原始上涨方向和下跌方向的数量、完整计数分布与各时期结果也全部导出，不能把仅上涨概率与两方向任选概率混用。表中原始p值在主要68项家族内校正后均不显著。\n\n'
    d+='![门槛数量与跨期数量](results/threshold_counts.png)\n\n'
    d+='## 5. 最高胜率：从60个中挑第一名\n\n'
    d+='观察最高率r时，对每组按ceil(r×nᵢ)计算“任一方向≥r”的概率qᵢ，P(60组最大值≥r)=1−∏(1−qᵢ)。这已经纳入60组选优，不能只报告排名第一那一个的单组二项尾概率。\n\n'
    d+=tab(['口径/时期','实际最高率','50%基准：至少这么高','实际p基准：至少这么高'],[[('开收盘' if basis=='oc' else '昨收')+'/'+period,pc(find(mx,basis=basis,period=period,null='iid_actual')['maximum_rate']),pc(find(mx,basis=basis,period=period,null='iid50')['p'],4),pc(find(mx,basis=basis,period=period,null='iid_actual')['p'],4)] for basis in P['bases'] for period in ['full','train','validation']])
    d+='开收盘全历史第一名丙申36/56=64.29%，在实际p的60组随机试验中，最大值至少达到该水平的概率为 **96.7008%**。条件在实际总上涨数的精确多项式计算给出 **97.0204%**。前期癸亥25/32=78.125%看起来突出，但在60组最大值比较中的实际p概率为 **12.2041%**，仍不是小于5%的全局异常。\n\n'
    d+='## 6. 前后时期同方向持续：按实际样本计算\n\n'
    d+='前期为2017实际开始至2022-12-31，后期为2023-01-01至2026-10-23。先在前期确定方向，后期不能换方向。阈值55%、60%、65%、70%全部事先固定。不是两个时期各自重选更好方向。\n\n'
    d+='对每个干支，联合概率 = P(前期上涨达标)×P(后期上涨达标) + P(前期下跌达标)×P(后期下跌达标)。两期在理想IID模型中独立，60组联合事件再用Poisson-binomial求总数量尾概率。\n\n'
    d+=tab(['口径','两期门槛','前期入选','两期同向达标','50%预期','50%精确p','实际p预期','实际p精确p'],[[('开收盘' if basis=='oc' else '昨收'),f'≥{h}%',find(jo,basis=basis,null='iid_actual',threshold=h,family='exact_primary68')['train_selected'],find(jo,basis=basis,null='iid_actual',threshold=h,family='exact_primary68')['observed_both'],f"{find(jo,basis=basis,null='iid50',threshold=h,family='exact_primary68')['expected_both']:.3f}",pv(find(jo,basis=basis,null='iid50',threshold=h,family='exact_primary68')['p']),f"{find(jo,basis=basis,null='iid_actual',threshold=h,family='exact_primary68')['expected_both']:.3f}",pv(find(jo,basis=basis,null='iid_actual',threshold=h,family='exact_primary68')['p'])] for basis in P['bases'] for h in TH])
    d+='同方向双60%的三组仍为 **庚午、甲申、丙申**。它们值得如实记录，但“发现3个”相对于随机预期3.14—3.90个，没有显示数量上的超额。\n\n'
    d+='### 32次与23次：仅作为数学示例\n\n'
    d+=tab(['门槛','32次所需成功','23次所需成功','32次单向概率','23次单向概率','两期同方向任一边概率','60组预期双高数'],[[f"≥{r['threshold']}%",r['required_train'],r['required_validation'],pc(r['train_up_probability'],4),pc(r['validation_up_probability'],4),pc(r['same_direction_both_probability'],4),f"{r['expected_same_direction_both_among60']:.3f}"] for r in read('illustrative_32_23') if r['basis']=='oc' and r['null']=='iid50'])
    d+='这张示例不能替代真实分母：32次≥60%需20次成功，33次也需20次，但尾概率不同。真实前期31—33次、后期23—24次，因此实际双60%预期3.141个，与统一32/23示例的2.615个不同。低样本量下，整数门槛造成明显的离散跳跃。\n\n'
    d+='### 固定实际前期名单的另一种问题\n\n'
    d+='如果条件在“已经挑出这25个名字及其方向”，只问它们后期继续达标的概率，必须使用各自冻结方向的后期概率重新卷积。开收盘前期≥55%的25组中12组继续达标，实际p下条件预期 **9.035组**，尾概率 **0.148160**。这和完整重筛流程的p=0.471838回答不同问题，均未显著；报告保留两者，未只挑较小的一个。\n\n'
    d+='## 7. 最高的若干组，后期理论上该有多少胜率\n\n'
    d+='预先固定top5、top10、top20，按前期精确分数排序、同分用干支序号打破，不使用后期排序。理想无效模型下，未来胜率不继承前期60%或70%：冻结做多方向的成功率是p，做空是1−p。组合后期成功次数的分布由两种二项分布卷积精确求得，固定名单结果如下。\n\n'
    d+=tab(['口径','前期排名前k','后期成功/总数','实际后期率','无效模型期望率','后期至少这么好p'],[[('开收盘' if r['basis']=='oc' else '昨收'),r['k'],f"{r['validation_success']}/{r['validation_n']}",pc(r['validation_rate']),pc(r['expected_rate']),pv(r['p'])] for r in read('topk_frozen_exact') if r['null']=='iid_actual'])
    d+='模拟另外每次重新选top-k，完整检验筛选流程。所有次要家族校正后均未形成持续优势证据。回落可由选优偏差与随机波动解释，但不意味着市场必须在下一段“补跌”或“补涨”。\n\n'
    d+='## 8. 全分布与时间相关性\n\n'
    d+=tab(['随机基准（开收盘）','上涨率标准差上尾p','固定分箱差异p','双55%至少12组p','双60%至少3组p','前后上涨率Pearson正相关p'],[[NAMES[method],pv(find(mc,basis='oc',null=method,statistic='full_sd')['p']),pv(find(mc,basis='oc',null=method,statistic='full_hist_chi')['p']),pv(find(mc,basis='oc',null=method,statistic='joint55')['p']),pv(find(mc,basis='oc',null=method,statistic='joint60')['p']),pv(find(mc,basis='oc',null=method,statistic='corr_up_pearson')['p'])] for method in P['ideal_nulls']+P['structured_nulls']])
    d+='原始上涨率的前后Pearson相关为0.1442，Spearman为0.1774。正相关尾概率在不同基准下分别约0.135—0.138和0.086—0.088，没有形成显著持续性。前期优势方向胜率与后期冻结方向胜率也计算在内，不能用后期重新翻转方向制造正相关。\n\n'
    d+='![随机标准差与双60%数量](results/null_distributions.png)\n\n![前后期关联](results/train_validation.png)\n\n'
    d+='固定分箱差异统计量使用事先定义的胜率区间，将观察频数与每组二项概率累加后的预期频数比较；因为稀疏分箱和不相同n，不套用简单渐近卡方自由度，而由对应模拟校准。原始上涨率与折叠优势率都计算。\n\n'
    fold=read('dominant_distribution_tests');fs=find(fold,basis='oc',null='iid_actual',statistic='dominant_sd')
    d+=f"折叠优势率的实际标准差为 **{100*fs['observed']:.3f}个百分点**，实际p的IID模拟均值为{100*fs['null_mean']:.3f}个百分点，双侧p={pv(fs['p'])}；折叠分布补充家族校正后亦无显著异常。原始标准差与最高值还做了对称双尾检查，未通过校正。后补诊断的时间与性质在 `diagnostics_supplement.json` 单独披露，不当作新的独立证据。\n\n"
    d+='### 结构条件随机化保留和破坏什么\n\n'
    d+='1. **固定分期总数：** 分别在两个不重叠时期置换非平盘涨跌，精确保留时期总上涨数，破坏年内和局部序列结构。\n2. **年×星期：** 只在相同年份、星期内置换完整收益标记束，保留这些层内的实际涨跌比例，打散连续行情。\n3. **每年独立整周循环：** 对完整有效的周序列逐年使用不同的整周偏移；不完整周、含无效或平盘日期的周保留。控制年份和星期，并保留大多数连续行情。\n\n'
    au=find(read('randomization_structure_audit'),basis='oc',method='weekly_rotation')
    d+=f"整周错位在审计样本中保留 **{pc(au['retained_calendar_neighbor_links'])}** 的相邻日链接；原始绝对收益lag1相关{au['abs_return_lag1_original']:.4f}，错位后均值{au['abs_return_lag1_null']:.4f}。涨跌lag1相关由{au['sign_lag1_original']:.4f}变为{au['sign_lag1_null']:.4f}。这是保留波动聚集的条件参考，仍非完全正确的市场生成模型。\n\n"
    d+='不能全历史统一移动60甲子相位后把它当随机检验：那通常只是重命名60个组，不改变分布或高胜率数量。此处逐年偏移不同、固定边界周，审计未发现单一全局相位重命名；样本数、平盘日期与分期总数保持，构造逻辑与抽样映射均核查。不同随机基准共享数据，不能把多个不显著p值相乘。\n\n'
    d+='## 9. 蒙特卡洛规模、误差和整数复核\n\n'
    d+='两个理想基准×两口径×每组200,000次，加三个结构基准×两口径×每组49,999次，共 **1,099,994 次**。每次重新筛选前期方向、阈值和top-k。种子为202610246055，加口径偏移100000和模型序号偏移10000；批次512。完整种子、源哈希与模拟代码哈希随结果保存。\n\n'
    d+='蒙特卡洛p=(超过次数+1)/(有效模拟次数+1)，附95% Wilson模拟误差区间。在尾概率50%附近，20万次的95%半宽约0.219个百分点，49,999次约0.438个百分点。最低可报告模拟p分别约0.000005、0.000020，不写p=0。精确概率不受这些模拟精度限制。\n\n'
    d+=tab(['事件，开收盘','精确实际p基准','模拟频率估计','模拟尾概率95%区间'],[[key,pv(find(read('exact_vs_monte_carlo'),basis='oc',null='iid_actual',statistic=key)['exact_p']),pv(find(mc,basis='oc',null='iid_actual',statistic=key)['p']),f"[{find(mc,basis='oc',null='iid_actual',statistic=key)['mc_tail_ci_low']:.6f}, {find(mc,basis='oc',null='iid_actual',statistic=key)['mc_tail_ci_high']:.6f}]"] for key in ['full_either55','full_either60','full_max','joint55','joint60']])
    d+='68项精确/模拟对照全部通过预先固定的6倍蒙特卡洛标准误数值核验，66/68项精确值落在各自点态95%模拟区间内；不能要求68个95%区间必然全部覆盖。**68项主要聚合概率再用Python任意精度整数与50位十进制复算，最大与常规数值结果差异5.22×10⁻¹⁵；720个个体二项p值也用整数权重核对。** 所谓精确指有限样本分布与求和定义，不是假装普通浮点具有无限位精度。完整整数分子/分母可还原。\n\n'
    d+='## 10. 多重检验与个体案例\n\n'
    d+='主要校正为Holm家族错误率控制，BH仅作探索性FDR对照。家族事先明确：主要精确聚合68项；全历史个体240项；两分期个体480项；条件超几何个体360项；主要模拟200项。次要精确138项、次要模拟210项和分布补充各20项分开披露，绝不将不同家族当独立复现。\n\n'
    d+='以上主要家族均没有校正后p<0.05的结果。个体原始小p只能说明“如果事先只指定这一组会怎样”；不能省略我们同时看了60组、多个门槛、两种方向口径和分期这一事实。完整个体双侧p、正常近似误差、置信区间、Holm/BH均在CSV中。\n\n'
    cases=['甲子','庚午','甲申','丙申','甲戌','乙亥','癸亥']
    d+=tab(['开收盘干支','前期冻结方向','前期成功/总数','前期率','后期同方向成功/总数','后期率','后期二项95%区间'],[[r['ganzhi'],'上涨' if r['direction']>0 else '下跌',f"{r['train_success']}/{r['train_n']}",pc(r['train_rate']),f"{r['validation_success']}/{r['validation_n']}",pc(r['validation_frozen_rate']),f"[{pc(binomtest(r['validation_success'],r['validation_n']).proportion_ci().low)}, {pc(binomtest(r['validation_success'],r['validation_n']).proportion_ci().high)}]"] for g in cases for r in [find(sp,basis='oc',ganzhi=g)]])
    d+='这些区间是单组、独立二项假设下的点态区间，不是60组同时或时间相关稳健区间，不能拿“区间内某一较高概率”当成功证明。甲子等持续表现与癸亥的后期失效都保留，不从60组中只讲赢家。全60组真实排名与逐期成功次数见 [完整明细](GANZHI_TABLES.md)。\n\n'
    d+='## 11. 证据边界与后续使用\n\n'
    d+='这项审计回答“若无干支效应，这些统计量有多常见”。它没有计算贝叶斯P(无效|数据)，没有证明随机模型就是真实市场，也没有证明所有可能的干支作用不存在。年度环境、星期和连续结构控制后依旧没有看到超额证据，当前更符合市场偏向、有限样本与筛选效应的解释。\n\n'
    d+='所有历史日期此前已经在本项目被多轮查看；此次是独立复算的回顾性统计审计，不能重新包装成从未查看的新样本外验证。训练期筛选冻结可防止验证方向泄漏，却不能抹掉此前研究选择问题。统计关联、未来预测能力、扣费后实际交易价值是三个层次，不能互相替代。\n\n'
    d+='若继续验证，应在未来新数据到来前冻结少量候选、方向、截止日期、成功定义和多重检验范围，按原计划记录失败与成功。当前没有足够依据把观察到的60%左右历史胜率直接当成未来同样的真实概率，也没有依据为了回归而反向下注。\n\n'
    d+='## 12. 可复核文件与核验\n\n'
    d+=f"实际完成 **{v['unit_tests']} 个数学/数据测试、{v['production_oracle_checks']:,} 项正式口径与历法核对、{v['independent_numeric_checks']:,} 项独立数值核验、{v['seeded_MC_statistic_values_replayed']:,} 个已保存模拟统计量的种子重放**。正式统计、API、日历和交易代码均未改变。\n\n"
    d+='[复现说明](README.md)列出完整命令。主要CSV含60组原始次数、二项/正态概率、门槛期望和完整计数PMF、跨期联合、top-k、条件检验、多重比较、模拟频数及结构审计。关键连续统计量分布保存在NPZ；源数据与协议单独做SHA256，最终bundle_manifest覆盖交付文件。\n\n'
    d+='可直接复核：[60组排名CSV](results/rankings60.csv)、[逐干支理论概率与标准差](results/theoretical_probabilities.csv)、[各胜率区间预期/实际数量](results/theoretical_distribution_bins.csv)、[跨期全部60组](results/split60.csv)、[全部模拟检验](results/monte_carlo_tests.csv)、[精确与模拟对照](results/exact_vs_monte_carlo.csv)、[任意精度整数审计](results/integer_exact_primary_audit.csv)。\n\n'
    d+='方法参考：[NIST二项分布定义及方差](https://www.itl.nist.gov/div898/handbook/eda/section3/eda366i.htm)、[SciPy精确二项检验](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)、[SciPy超几何分布](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.hypergeom.html)、[statsmodels多重比较](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)。\n'
    (ROOT/'REPORT.md').write_text(d,encoding='utf-8')
    appendix='# 全部六十甲子真实胜率与跨期明细\n\n排名按全历史优势方向胜率精确分数排序，同分按干支序号；这只是历史描述，不是预测能力排名。开收盘与昨收分开。完整数据截止2026-10-23。\n\n'
    for basis in P['bases']:
        appendix+=f"## {'开收盘' if basis=='oc' else '昨收'}全历史60组\n\n"
        appendix+=tab(['排名','干支','n','上涨','下跌','平盘','上涨率','下跌率','较高方向','较高胜率','实际p双侧检验','Holm240'],[[r['rank'],r['ganzhi'],r['n'],r['up'],r['down'],r['flat'],pc(r['up_rate']),pc(r['down_rate']),{'up':'上涨','down':'下跌','tie':'相同'}[r['dominant_direction']],pc(r['dominant_rate']),pv(r['p_iid_actual_two_sided']),pv(r['holm_full240'])] for r in rk if r['basis']==basis])
        appendix+=f"## {'开收盘' if basis=='oc' else '昨收'}前后期60组\n\n"
        appendix+=tab(['干支','冻结方向','前期成功/n','前期率','后期同向成功/n','后期率','双55%','双60%','双65%','双70%'],[[r['ganzhi'],'上涨' if r['direction']>0 else '下跌' if r['direction']<0 else '无',f"{r['train_success']}/{r['train_n']}",pc(r['train_rate']),f"{r['validation_success']}/{r['validation_n']}",pc(r['validation_frozen_rate']) if r['validation_frozen_rate'] is not None else '无方向']+['是' if r[f'both{h}'] else '否' for h in TH] for r in sp if r['basis']==basis])
    (ROOT/'GANZHI_TABLES.md').write_text(appendix.rstrip()+'\n',encoding='utf-8')
    css='body{font-family:"Microsoft YaHei",sans-serif;max-width:1080px;margin:36px auto;padding:0 24px;color:#243447;line-height:1.85;background:#fbfcfe}h1,h2,h3{line-height:1.4;color:#17324d}h2{margin-top:42px;border-bottom:1px solid #d9e2ec;padding-bottom:9px}a{color:#175a93}img{display:block;max-width:100%;height:auto;background:white}table{border-collapse:collapse;min-width:680px;width:100%;font-size:14px}th{background:#243c5a;color:white;text-align:left}td,th{padding:9px 11px;border-bottom:1px solid #d9e2ec}tbody tr:nth-child(even){background:#eef3f8}.table-wrap{overflow:auto;max-width:100%;margin:18px 0}code{white-space:pre-wrap;overflow-wrap:anywhere}pre{overflow:auto;background:#eef3f8;padding:12px}p,li{overflow-wrap:anywhere}@media(max-width:600px){body{margin:18px auto;padding:0 16px}h1{font-size:25px}table{font-size:13px}}'
    for name in ['REPORT','GANZHI_TABLES','README']:
        text=(ROOT/(name+'.md')).read_text('utf-8');body=markdown.markdown(text,extensions=['tables','fenced_code'])
        body=body.replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')
        for local in ['REPORT','GANZHI_TABLES','README']:body=body.replace(f'href="{local}.md"',f'href="{local}.html"')
        (ROOT/(name+'.html')).write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+html.escape(name)+'</title><style>'+css+'</style></head><body>'+body+'</body></html>',encoding='utf-8')
    dump(OUT/'report_summary.json',dict(conclusion='No multiplicity-adjusted evidence for Ganzhi-specific predictability',main=ev,folded_significant=sum(r['holm']<.05 for r in read('dominant_distribution_tests')),full_ranking_rows=len(rk),split_rows=len(sp)))
    print('REPORT_WRITTEN',len(d),'APPENDIX_ROWS',len(rk)+len(sp),flush=True)

if __name__=='__main__':main()
