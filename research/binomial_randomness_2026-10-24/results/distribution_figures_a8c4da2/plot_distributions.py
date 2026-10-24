"""Three report figures from immutable a8c4da2 research results; no new backtest."""
from pathlib import Path
from fractions import Fraction
from math import sqrt
import subprocess,json,hashlib,csv,html
import numpy as np
from scipy.stats import binom,binomtest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT=Path(__file__).resolve().parent
REPO=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT).decode().strip())
BASE='a8c4da2e4d0045e3ac05f92a5ecdcf29f0e2fc28'
SOURCE='research/binomial_randomness_2026-10-24/results'
SOURCE_FILES={}
BASIS=['oc','cc'];MODES=['up','dominant'];NULLS=['iid50','iid_actual'];TH=[55,60,65,70]
EDGES=np.array([0,.35,.40,.45,.50,.55,.60,.65,.70,.75,1.000001])
PLOT_EDGES=EDGES.copy();PLOT_EDGES[-1]=1.
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,
                     'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
BLUE='#386A91';ORANGE='#C38123';INK='#20384F';GREY='#E8EDF2';UP='#13805B';DOWN='#B84B50'


def read(name):
    rel=f'{SOURCE}/{name}.json'
    raw=subprocess.check_output(['git','show',f'{BASE}:{rel}'],cwd=REPO)
    SOURCE_FILES[rel]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    return json.loads(raw)


def find(rows,**kw):
    matches=[r for r in rows if all(r.get(k)==v for k,v in kw.items())]
    assert len(matches)==1,(kw,len(matches))
    return matches[0]


def dump(name,obj):
    (ROOT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def table(name,rows):
    with (ROOT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    dump(name,rows)


def discrete(n,m,p,mode):
    """The exact binomial law, or the SAME max(up,down) transform as the observations."""
    k=np.arange(m+1);pm=binom.pmf(k,m,p)
    counts=k if mode=='up' else np.maximum(k,m-k)
    unique=np.unique(counts);weights=np.array([pm[counts==v].sum() for v in unique])
    return unique/n,weights


def discrete_interval(values,pm,alpha=.05):
    cdf=np.cumsum(pm);cdf[-1]=1.
    return float(values[np.searchsorted(cdf,alpha/2)]),float(values[np.searchsorted(cdf,1-alpha/2)])


def moments(groups,p,mode):
    mus=[];variances=[];expected=np.zeros(len(EDGES)-1)
    for r in groups:
        values,pm=discrete(r['n'],r['binary_n'],p,mode)
        mean=float(np.dot(values,pm));mus.append(mean)
        variances.append(float(np.dot((values-mean)**2,pm)))
        expected+=np.histogram(values,bins=EDGES,weights=pm)[0]
    mus=np.array(mus);variances=np.array(variances);mean=float(mus.mean())
    mixture_variance=float(variances.mean()+np.mean((mus-mean)**2))
    sample_variance_expectation=float(variances.mean()+np.sum((mus-mean)**2)/(len(groups)-1))
    return mean,sqrt(mixture_variance),sqrt(sample_variance_expectation),expected


def value(r,mode):return r['up_rate'] if mode=='up' else r['dominant_rate']
def success(r,mode):return r['up'] if mode=='up' else max(r['up'],r['down'])
def cname(basis,mode):return ('开收盘' if basis=='oc' else '昨收')+' · '+('固定上涨胜率' if mode=='up' else '两方向取高胜率')
def pc(x,d=3):return f'{100*x:.{d}f}%'
def pv(x):return f'{x:.6f}'
def mdtable(head,rows):return '| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)+'\n\n'


def check_figure_text(fig):
    fig.canvas.draw();renderer=fig.canvas.get_renderer();w,h=fig.canvas.get_width_height()
    for text in fig.texts:
        box=text.get_window_extent(renderer)
        assert box.x0>=-1 and box.y0>=-1 and box.x1<=w+1 and box.y1<=h+1,('clipped figure text',text.get_text(),box.bounds,(w,h))


def plots(groups,totals,all_moments,bin_rows,tests,intervals):
    for ino,null in enumerate(NULLS,1):
        fig,axes=plt.subplots(2,2,figsize=(16,10),sharex=True,sharey=True)
        fig.subplots_adjust(left=.065,right=.975,top=.86,bottom=.14,wspace=.13,hspace=.28)
        heading='理论基准 p = 50%' if null=='iid50' else '理论基准 p = 全样本实际二元上涨率'
        fig.suptitle(f'60甲子真实胜率分布与精确二项理论对比\n{heading}',fontsize=22,fontweight='bold',color=INK,y=.965)
        for ib,basis in enumerate(BASIS):
            for im,mode in enumerate(MODES):
                ax=axes[ib,im];rr=groups[basis];vals=np.array([value(r,mode) for r in rr])*100
                counts,_,_=ax.hist(vals,bins=PLOT_EDGES*100,density=False,color=BLUE,alpha=.30,edgecolor=BLUE,linewidth=1.1,label='真实60组：直方图')
                pred=find(all_moments,basis=basis,mode=mode,null=null)
                br=[r for r in bin_rows if r['basis']==basis and r['mode']==mode and r['null']==null]
                centers=(PLOT_EDGES[:-1]+PLOT_EDGES[1:])*50
                ax.plot(centers,[r['expected_count'] for r in br],color=ORANGE,marker='o',markersize=5,linewidth=2.3,label='精确二项期望频数：逐箱连接')
                if null=='iid_actual':
                    old=[r for r in bin_rows if r['basis']==basis and r['mode']==mode and r['null']=='iid50']
                    ax.plot(centers,[r['expected_count'] for r in old],color='#8B96A1',linestyle='--',linewidth=1.35,label='p=50%期望频数（对照）')
                test=find(tests,basis=basis,mode=mode,null=null)
                ax.set_title(cname(basis,mode)+f"  |  p={pred['p_binary_reference']:.6%}",loc='left',fontsize=13,fontweight='bold',pad=12)
                ax.text(.025,.95,f"均值 {pred['actual_mean']*100:.2f}%  /  样本SD {pred['actual_sample_sd']*100:.2f}个百分点\n"
                        f"分箱差异 p={test['histogram_p']:.4f}  /  离散程度上尾 p={test['dispersion_upper_p']:.4f}",
                        transform=ax.transAxes,va='top',fontsize=9.8,color=INK)
                ax.set_xlim(0,100);ax.set_ylim(0,37);ax.set_xticks(np.arange(0,101,10));ax.set_yticks(np.arange(0,36,5))
                ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True);ax.set_xlabel('历史胜率（%）');ax.set_ylabel('干支数量（频数，非密度）')
                ax.legend(loc='upper right',bbox_to_anchor=(1,.77),fontsize=9,framealpha=.95)
                assert np.array_equal(counts,np.array([r['observed_count'] for r in br]))
        fig.text(.065,.079,'统一沿用原研究分箱：0–35、35–40、…、70–75、75–100%；同一面板的直方图与理论期望使用完全相同的分箱、范围和频数单位。',fontsize=10,color=INK)
        fig.text(.065,.052,'理论逐一采用各干支真实 n（54–56）和 m=n−平盘数；右列在理论端同样取 max(上涨次数, 下跌次数)，没有把择优胜率当成普通二项比例。',fontsize=10,color=INK)
        fig.text(.065,.026,'BTCUSDT现货 · UTC+8 · 2017-08-18—2026-10-23 · 来源：a8c4da2已完成研究；p值复用同分箱/统计量的既有模拟检验，校正见摘要。',fontsize=10,color='#5B6D7E')
        name=f'{ino:02d}_distribution_'+('p50' if null=='iid50' else 'p_actual')+'.png'
        check_figure_text(fig);fig.savefig(ROOT/name,dpi=300);plt.close(fig)
    fig,axes=plt.subplots(4,1,figsize=(22,17))
    fig.subplots_adjust(left=.045,right=.985,top=.875,bottom=.075,hspace=.52)
    fig.suptitle('60甲子真实胜率排名与精确随机参考区间',fontsize=25,fontweight='bold',color=INK,y=.975)
    fig.text(.045,.939,'区间基准：各口径全样本实际二元上涨率；蓝色为单组点态95%，灰色为Bonferroni同时至少95%参考带。均为固定p零假设下的精确离散分位数。',fontsize=12,color=INK)
    legend=[Patch(facecolor=GREY,label='60组同时至少95%参考带（Bonferroni）'),Patch(facecolor=BLUE,alpha=.22,label='单组点态95%参考区间'),Line2D([],[],marker='o',color='none',markerfacecolor=UP,label='上涨方向真实胜率'),Line2D([],[],marker='o',color='none',markerfacecolor=DOWN,label='下跌方向择优胜率'),Line2D([],[],marker='o',color='none',markerfacecolor='#6C7883',label='两方向持平')]
    rank_titles=[]
    for ax,(basis,mode) in zip(axes,[(b,m) for b in BASIS for m in MODES]):
        rr=sorted([r for r in intervals if r['basis']==basis and r['mode']==mode],key=lambda r:r['rank']);x=np.arange(60)
        lo=np.array([r['pointwise95_low'] for r in rr])*100;hi=np.array([r['pointwise95_high'] for r in rr])*100
        slo=np.array([r['simultaneous95_low'] for r in rr])*100;shi=np.array([r['simultaneous95_high'] for r in rr])*100
        ax.fill_between(x,slo,shi,color=GREY,step='mid',zorder=0)
        ax.fill_between(x,lo,hi,color=BLUE,alpha=.20,step='mid',zorder=1)
        ax.vlines(x,lo,hi,color=BLUE,linewidth=.75,alpha=.65,zorder=2)
        for h,style in zip(TH,[':',':','--','--']):
            ax.axhline(h,color='#8C765D',linestyle=style,linewidth=.8,alpha=.8,zorder=1)
            ax.text(59.4,h+.5,f'{h}%',fontsize=8,color='#765D42',ha='right',va='bottom')
        vals=np.array([r['observed_rate'] for r in rr])*100
        ax.plot(x,vals,color='#4D6273',linewidth=.8,alpha=.65,zorder=3)
        colors=[UP if mode=='up' else {'up':UP,'down':DOWN,'tie':'#6C7883'}[r['selected_direction']] for r in rr]
        ax.scatter(x,vals,c=colors,s=19,edgecolor='white',linewidth=.45,zorder=4)
        ax.set_xlim(-.7,59.7);ax.set_ylim(25,85);ax.set_yticks([30,40,50,55,60,65,70,80]);ax.set_xticks(x,[r['ganzhi'] for r in rr],fontsize=8.2)
        ax.set_ylabel('历史胜率（%）',fontsize=11);ax.grid(axis='y',alpha=.12);ax.set_axisbelow(True)
        point_out=sum(r['outside_pointwise95'] for r in rr);sim_out=sum(r['outside_simultaneous95'] for r in rr)
        rank_titles.append(ax.set_title(cname(basis,mode)+f'（各自从高到低排序；点态越界 {point_out}/60，同时带越界 {sim_out}/60）',loc='left',fontsize=13,fontweight='bold',pad=12))
    legend_object=fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.53,.924),ncol=5,frameon=False,fontsize=10.5)
    fig.text(.045,.033,'参考区间不是未知真实胜率的置信区间，也不是排序统计量的区间。点态越界不等于经60组比较后显著；排序仅用于展示，所有组、相同n和择优操作均被保留。',fontsize=11,color=INK)
    fig.text(.045,.013,'UTC+8 · 2017-08-18—2026-10-23 · 六十甲子名称、次数与历法均来自 a8c4da2；完整排名、分位数、区间实际覆盖率和校正结果见CSV与统计摘要。',fontsize=11,color='#5B6D7E')
    check_figure_text(fig)
    for title in rank_titles:assert not legend_object.get_window_extent().overlaps(title.get_window_extent()),'Legend overlaps panel title'
    fig.savefig(ROOT/'03_rankings_exact_reference_intervals.png',dpi=300);plt.close(fig)


def main():
    observed=read('ganzhi_observed');totals=read('period_totals');original_bins=read('theoretical_distribution_bins')
    threshold_source=read('threshold_counts_exact');mc=read('monte_carlo_tests');fold=read('dominant_distribution_tests');sym=read('symmetric_distribution_tests')
    original_moments=read('dominant_distribution_moments');individual=read('individual_binomial_normal');conditional=read('individual_conditional')
    source_groups={b:sorted([r for r in observed if r['basis']==b and r['period']=='full'],key=lambda r:r['g']) for b in BASIS}
    for b,rr in source_groups.items():
        assert len(rr)==60 and len({r['ganzhi'] for r in rr})==60
        assert sum(r['up'] for r in rr)==find(totals,basis=b,period='full')['up']
        assert all(r['up']+r['down']+r['flat']==r['n'] and r['up']+r['down']==r['binary_n'] for r in rr)
    moment_rows=[];bin_rows=[];threshold_rows=[];test_rows=[];interval_rows=[];mean_rows=[]
    for basis in BASIS:
        rr=source_groups[basis];total=find(totals,basis=basis,period='full');p_actual=total['up']/(total['up']+total['down'])
        mean_rows.append(dict(basis=basis,pooled_up=total['up'],pooled_binary_n=total['up']+total['down'],pooled_p=p_actual,
                              exact_two_sided_p_vs50=binomtest(total['up'],total['up']+total['down'],.5).pvalue,
                              interpretation='BTC pooled market upward bias, not a test of extra Ganzhi value; IID calibration'))
        for mode in MODES:
            vals=np.array([value(r,mode) for r in rr]);ranked=sorted(rr,key=lambda r:(-Fraction(success(r,mode),r['n']),r['g']))
            for null,p in [('iid50',.5),('iid_actual',p_actual)]:
                mean,mixsd,rms,expected=moments(rr,p,mode);actualhist=np.histogram(vals,bins=EDGES)[0]
                old=find(mc,basis=basis,null=null,statistic='full_sd') if mode=='up' else find(fold,basis=basis,null=null,statistic='dominant_sd')
                moment_rows.append(dict(basis=basis,mode=mode,null=null,p_binary_reference=p,actual_mean=float(vals.mean()),actual_sample_sd=float(vals.std(ddof=1)),
                                        theoretical_mean=mean,theoretical_mixture_sd=mixsd,theoretical_rms_sample_sd=rms,MC_expected_sample_sd=old['null_mean'],
                                        MC_sample_sd_q025=old['null_q025'],MC_sample_sd_q975=old['null_q975']))
                for i,(lo,hi) in enumerate(zip(PLOT_EDGES[:-1],PLOT_EDGES[1:])):
                    oldbin=find(original_bins,basis=basis,period='full',null=null,mode=mode,lower=float(EDGES[i]),upper=float(EDGES[i+1]))
                    assert int(actualhist[i])==oldbin['observed'] and abs(expected[i]-oldbin['expected'])<1e-10
                    bin_rows.append(dict(basis=basis,mode=mode,null=null,bin_lower_pct=lo*100,bin_upper_pct=hi*100,observed_count=int(actualhist[i]),expected_count=float(expected[i])))
                histtest=find(mc,basis=basis,null=null,statistic='full_hist_chi') if mode=='up' else find(fold,basis=basis,null=null,statistic='dominant_hist_chi')
                dispersion=old['p'] if mode=='up' else old['p_upper'];twoside=find(sym,basis=basis,null=null,statistic='full_sd') if mode=='up' else old
                test_rows.append(dict(basis=basis,mode=mode,null=null,histogram_p=histtest['p'],histogram_holm=histtest['holm'],histogram_family_size=histtest['family_size'],
                                      dispersion_upper_p=dispersion,dispersion_two_sided_p=twoside['p'],dispersion_holm=twoside['holm'],
                                      note='Reused original predeclared binning and null MC tests; no new Monte Carlo'))
                for h in TH:
                    oldth=find(threshold_source,basis=basis,period='full',null=null,side='up' if mode=='up' else 'either',threshold=h)
                    expected_count=0
                    for r in rr:
                        values,pm=discrete(r['n'],r['binary_n'],p,mode)
                        # Integer-count criterion, before display rounding.
                        k=np.arange(r['binary_n']+1);successes=k if mode=='up' else np.maximum(k,r['binary_n']-k)
                        expected_count+=float(binom.pmf(k,r['binary_n'],p)[successes*100>=h*r['n']].sum())
                    assert abs(expected_count-oldth['expected'])<1e-10
                    threshold_rows.append(dict(basis=basis,mode=mode,null=null,threshold_pct=h,observed_count=oldth['observed'],expected_count=expected_count,
                                               exact_upper_tail_p=oldth['p'],holm_primary68=oldth['holm']))
            for rank,r in enumerate(ranked,1):
                values,pm=discrete(r['n'],r['binary_n'],p_actual,mode);lo,hi=discrete_interval(values,pm);slo,shi=discrete_interval(values,pm,.05/60)
                exact=find(individual,basis=basis,period='full',null='iid_actual',g=r['g'])
                interval_rows.append(dict(basis=basis,mode=mode,rank=rank,g=r['g'],ganzhi=r['ganzhi'],n=r['n'],binary_n=r['binary_n'],flat=r['flat'],up=r['up'],down=r['down'],
                                          success=success(r,mode),selected_direction='up' if mode=='up' else r['dominant_direction'],observed_rate=value(r,mode),p_binary_reference=p_actual,
                                          pointwise95_low=lo,pointwise95_high=hi,pointwise_actual_coverage=float(pm[(values>=lo)&(values<=hi)].sum()),
                                          simultaneous95_low=slo,simultaneous95_high=shi,simultaneous_marginal_coverage=float(pm[(values>=slo)&(values<=shi)].sum()),
                                          outside_pointwise95=bool(value(r,mode)<lo-1e-12 or value(r,mode)>hi+1e-12),outside_simultaneous95=bool(value(r,mode)<slo-1e-12 or value(r,mode)>shi+1e-12),
                                          original_two_sided_binomial_p=exact['p'],original_holm240=exact['holm']))
    assert all(r['pointwise_actual_coverage']>=.95-1e-12 and r['simultaneous_marginal_coverage']>=1-.05/60-1e-12 for r in interval_rows)
    table('moments_summary',moment_rows);table('histogram_frequency_data',bin_rows);table('thresholds_summary',threshold_rows);table('significance_summary',test_rows)
    table('group_intervals_and_ranks',interval_rows);table('pooled_market_mean_tests',mean_rows)
    plots(source_groups,totals,moment_rows,bin_rows,test_rows,interval_rows)
    make_summary(moment_rows,threshold_rows,test_rows,interval_rows,mean_rows)
    dump('source_manifest',dict(base_commit=BASE,source_files=SOURCE_FILES,source_period='2017-08-18 to 2026-10-23',produces='3 PNGs, no production or original study modifications',
                                normal_approximation_used=False,new_MC_runs=0,reference_interval_rule='Exact fixed-p quantiles; pointwise alpha=.05; simultaneous Bonferroni alpha=.05/60; not true-parameter CIs or order-statistic envelopes'))
    print(json.dumps({'status':'PASS','panels_per_png':4,'group_interval_rows':len(interval_rows),'source_commit':BASE,'source_files':len(SOURCE_FILES)}))


def make_summary(moments_rows,threshold_rows,tests,intervals,means):
    d='# 60甲子真实胜率与精确二项理论对比图\n\n'
    d+='严格读取 Git 提交 **a8c4da2e4d0045e3ac05f92a5ecdcf29f0e2fc28** 中已完成研究的JSON，不读取后续实时行情，不重新训练或回测，也不修改正式功能。源数据有效区间为 **2017-08-18—2026-10-23，UTC+8**。每张图四个面板，分别对应两种价格口径与两种成功定义。\n\n'
    d+='## 成功定义与图的读法\n\n'
    d+='左列/第1和第3排名面板：**固定上涨胜率**，成功是收盘高于开盘（oc）或高于连续前一日有效收盘（cc）。右列/第2和第4排名面板：沿用原研究排名的**两方向取高胜率**，成功次数为max(上涨次数,下跌次数)，保留该组择优方向。后者是择优后的折叠分布，在纯随机下平均胜率也高于50%，不能直接与普通Binomial比例比较。\n\n'
    d+='所有显示分母n包括平盘，m=n−平盘；在随机模型中固定平盘日期，K~Binomial(m,p)，下跌=m−K。各组n为54—56，逐组计算精确PMF，再在原研究预先固定的相同分箱累加期望频数。未使用正态近似、核密度、平滑或密度归一化。连线只是各分箱期望频数的连接，不代表连续概率密度。\n\n'
    d+='图1使用p=50%；图2使用全样本二元实际上涨率：oc为1755/3350=52.388060%，cc为1753/3347=52.375261%。这不是60个择优胜率的平均值。将约55.57%的择优均值再当作p进行相同择优，会重复引入筛选偏差。图2另保留50%理论虚线方便比较。\n\n'
    d+='![图1：p=50%](01_distribution_p50.png)\n\n![图2：实际上涨率](02_distribution_p_actual.png)\n\n'
    d+='## 均值与标准差\n\n'
    d+='实际均值为60组胜率的非加权平均，实际标准差使用样本定义ddof=1，和原研究一致。理论主对照为 **√E[S²]**，同时给出原模拟的 **E[S]**，避免把二者混为一谈。完整CSV还给出理论混合分布的总体标准差。标准差数值单位均为百分点。\n\n'
    d+=mdtable(['口径/定义','基准p','实际均值','实际样本SD','理论均值','理论√E[S²]','原模拟E[S]'],[[cname(r['basis'],r['mode']),'50%' if r['null']=='iid50' else '实际率',pc(r['actual_mean']),f"{r['actual_sample_sd']*100:.4f}",pc(r['theoretical_mean']),f"{r['theoretical_rms_sample_sd']*100:.4f}",f"{r['MC_expected_sample_sd']*100:.4f}"] for r in moments_rows])
    d+='对每组随机胜率Xᵢ，理论混合方差 = 平均Var(Xᵢ)+平均(μᵢ−μ̄)²；E[S²] = 平均Var(Xᵢ)+Σ(μᵢ−μ̄)²/59。K/n与max(K,m−K)/n都按其精确离散分布求矩，未用平均n替代真实n。\n\n'
    d+='## 高胜率数量与精确尾概率\n\n'
    for basis in BASIS:
        for mode in MODES:
            d+='### '+cname(basis,mode)+'\n\n'
            d+=mdtable(['门槛','实际数量','p50理论数量','p50精确尾p','p50 Holm68','实际率理论数量','实际率精确尾p','实际率 Holm68'],[[f'≥{h}%',find(threshold_rows,basis=basis,mode=mode,null='iid50',threshold_pct=h)['observed_count'],f"{find(threshold_rows,basis=basis,mode=mode,null='iid50',threshold_pct=h)['expected_count']:.4f}",pv(find(threshold_rows,basis=basis,mode=mode,null='iid50',threshold_pct=h)['exact_upper_tail_p']),pv(find(threshold_rows,basis=basis,mode=mode,null='iid50',threshold_pct=h)['holm_primary68']),f"{find(threshold_rows,basis=basis,mode=mode,null='iid_actual',threshold_pct=h)['expected_count']:.4f}",pv(find(threshold_rows,basis=basis,mode=mode,null='iid_actual',threshold_pct=h)['exact_upper_tail_p']),pv(find(threshold_rows,basis=basis,mode=mode,null='iid_actual',threshold_pct=h)['holm_primary68'])] for h in TH])
    d+='尾概率是随机模型下至少出现当前数量的概率，复用原研究逐组精确概率卷积得到的Poisson-binomial计数分布；不是用Binomial(60,平均q)近似。原始整数阈值100×成功次数≥h×n保持不变。所有主要门槛检验均未通过原预先规定的68项Holm校正。\n\n'
    d+='## 分布与离散程度的显著性\n\n'
    d+=mdtable(['口径/定义','基准','分箱整体差异p','分箱检验Holm','标准差增大上尾p','标准差双尾p','离散检验Holm'],[[cname(r['basis'],r['mode']),r['null'],pv(r['histogram_p']),pv(r['histogram_holm']),pv(r['dispersion_upper_p']),pv(r['dispersion_two_sided_p']),pv(r['dispersion_holm'])] for r in tests])
    d+='分箱差异和标准差p值直接复用a8c4da2中的同分箱、同统计量和相同模拟，不新开模拟选择更好看的p值。每个理想模型每口径200,000次；原始上涨率分箱检验属于原主要200项家族，择优分布属于原补充20项家族；离散程度双尾诊断亦沿用各自原家族。完整模拟次数、种子与Wilson误差区间保留在上级研究。不同检验不是独立证据，不把p值相乘。\n\n'
    oc=find(tests,basis='oc',mode='up',null='iid_actual');dom=find(tests,basis='oc',mode='dominant',null='iid_actual')
    d+=f"开收盘原始上涨率：相对实际p理论，整体分箱差异p={oc['histogram_p']:.6f}，标准差增大上尾p={oc['dispersion_upper_p']:.6f}；择优胜率对应p分别为{dom['histogram_p']:.6f}、{dom['dispersion_upper_p']:.6f}。没有发现更宽的尾部或更大的整体离散程度。\n\n"
    d+='### 均值偏移与干支效应必须分开\n\n'
    d+=mdtable(['合并样本口径','上涨/非平盘总数','实际二元上涨率','相对50%的精确双侧p'],[[r['basis'],f"{r['pooled_up']}/{r['pooled_binary_n']}",pc(r['pooled_p']),pv(r['exact_two_sided_p_vs50'])] for r in means])
    d+='这里存在一个需要保留的区别：**BTC合并样本的上涨比例相对50%有均值偏移**，在理想IID二项检验下具有原始显著性；它是整个市场的上涨偏向，并非特定干支的额外作用。p=实际上涨率基准正是对这一偏向的控制。上表合并样本检验检验加权市场上涨率，不冒充60组非加权平均值的精确检验；它与分箱整体检验针对不同备择，因此p值可以不同。\n\n'
    d+='择优胜率均值约55.57%，不能被解释为相对50%有5.57个百分点的预测优势，因为随机二项模型经过相同择优操作后，预期均值已经约55.3%—55.6%。另外，实际p从同一数据估计，属于固定参数代入参考，不能把它当成未知参数复合零假设的精确检验；原研究另有条件超几何、固定涨跌总数、年星期和整周错位检验控制此问题，均无校正后优势证据。\n\n'
    d+='## 排名图与95%随机参考区间\n\n'
    d+='![图3：排名与随机参考](03_rankings_exact_reference_intervals.png)\n\n'
    d+='每个面板按自己的真实胜率精确分数降序排列，同分按原干支序号。每个干支仍使用自己的n、m。蓝带为固定实际p零假设下的精确2.5%与97.5%分位数；灰带把单组α设为0.05/60，给出Bonferroni同时至少95%参考。离散分位数使实际覆盖率通常高于标称值，CSV保留真实覆盖率。\n\n'
    d+=mdtable(['口径/定义','点态95%区间外数量','同时95%参考带外数量'],[[cname(b,m),sum(r['outside_pointwise95'] for r in intervals if r['basis']==b and r['mode']==m),sum(r['outside_simultaneous95'] for r in intervals if r['basis']==b and r['mode']==m)] for b in BASIS for m in MODES])
    d+='这些是**随机胜率的参考区间**，不是未知真实成功率参数的置信区间；排序后也不能把单组点态带当作第1名、第2名等排序统计量的区间。点态越界允许偶然发生，不能忽略60组选优。图中另画55%、60%、65%、70%线，它们是阅读参考，不是事后调参筛选线。原研究个体二项检验Holm240值也保留在完整CSV中。\n\n'
    d+='## 客观结论与交付\n\n'
    d+='**现有60甲子胜率分布没有显示经多重比较校正后显著超出精确随机二项参考的尾部或离散异常。** 50%基准下能看到市场总体上涨均值偏移；控制实际市场基准后，没有证据将其归因于干支。择优胜率高于50%的大部分表象是取高操作自身造成的，不能直接解释成预测优势。\n\n'
    d+='这不证明所有可能的干支效应绝对不存在；也不提供P(规律为真|数据)的后验概率。这批历史数据已被多次查看，图表不是新的样本外预测验证，更不能据统计描述推出未来有效或扣费后可交易。未来预测能力需要预先冻结规则并用未查看数据验证。\n\n'
    d+='目录含三张300 DPI高清PNG、唯一绘图脚本、60组名称/次数/分位数CSV、理论频数、矩与阈值摘要、复用检验结果、源文件哈希和测试记录。运行：从仓库根目录用原科研环境执行 `python research/binomial_randomness_2026-10-24/results/distribution_figures_a8c4da2/plot_distributions.py`；依赖沿用上级 `requirements-research.txt`，中文字体Microsoft YaHei。所有输入通过 `git show a8c4da2:路径` 读取，不受工作区或实时数据库改变影响。\n'
    (ROOT/'SUMMARY.md').write_text(d.rstrip()+'\n',encoding='utf-8')
    import markdown
    body=markdown.markdown(d,extensions=['tables','fenced_code']);body=body.replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')
    css='body{font-family:"Microsoft YaHei",sans-serif;color:#20384f;max-width:1120px;margin:36px auto;padding:0 24px;line-height:1.85}h1,h2,h3{line-height:1.45}h2{margin-top:38px;border-bottom:1px solid #d9e2ec}img{max-width:100%;height:auto}table{border-collapse:collapse;min-width:850px;width:100%;font-size:13px}.table-wrap{overflow:auto;max-width:100%}th{background:#20384f;color:white}th,td{padding:8px;border-bottom:1px solid #dae2e9}tbody tr:nth-child(even){background:#f0f4f8}code{overflow-wrap:anywhere}p{overflow-wrap:anywhere}@media(max-width:600px){body{padding:0 15px;margin:20px auto}h1{font-size:25px}}'
    (ROOT/'SUMMARY.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>60甲子分布对比图</title><style>'+css+'</style></head><body>'+body+'</body></html>',encoding='utf-8')


if __name__=='__main__':main()
