# 干支胜率的二项分布、正态近似与随机显著性

本目录独立保存 2026-10-24 冻结的真实行情、统计协议、精确计算、随机模拟、核验及中文报告。不修改生产系统。

- [完整中文报告](REPORT.md)
- [全部60干支排名与分期原始次数](GANZHI_TABLES.md)
- [全部精确门槛计数检验](results/threshold_counts_exact.csv)
- [同方向跨期双高胜率](results/cross_period_exact.csv)
- [单干支二项分布及正态误差](results/individual_binomial_normal.csv)
- [全部随机检验与校正](results/monte_carlo_tests.csv)
- [任意精度整数复算记录](results/integer_exact_primary_audit.csv)

## 数据与定义

来源为仓库 `data/market.db` 与 `data/calendar.db` 的只读事务快照，完整源数据保存在 `snapshot.json`，SHA256 与 Git 基准在 `manifest.json`。最新完整日线 2026-10-23。按 UTC+8，开收盘与昨收两种口径分别计算。主分割为实际有效 2017 起至 2022-12-31，以及 2023-01-01 起至最新完整日线。

每组以有效日线数 n 为显示分母。平盘日期固定，二项试验数 m=n−平盘数，up~Binomial(m,p)，down=m−up。避免把平盘算成下跌。阈值为 `100*success >= threshold*n`。本研究的55%门槛是大于等于，不改变另一个固定止盈止损策略中严格大于55%的规则。

两种理想基准：p=0.5，以及全样本非平盘上涨次数/非平盘次数。后者是拟合后的固定参考参数，不能将其概率称为未知参数复合零假设的严格精确p值。超几何条件检验与固定总数/年星期随机化另外处理这个问题。

## 复现

从仓库根目录运行，Python 3.11+。已有科研环境可直接使用。重新创建环境时：

```powershell
python -m venv research/binomial_randomness_2026-10-24/.venv
research/binomial_randomness_2026-10-24/.venv/Scripts/python.exe -m pip install -r research/binomial_randomness_2026-10-24/requirements-research.txt
```

以下 `python` 替换为相应环境的完整路径：

```powershell
python research/binomial_randomness_2026-10-24/exact.py
python research/binomial_randomness_2026-10-24/simulate.py
python research/binomial_randomness_2026-10-24/evaluate.py
python research/binomial_randomness_2026-10-24/integer_audit.py
python research/binomial_randomness_2026-10-24/folded_diagnostics.py
python research/binomial_randomness_2026-10-24/verify.py
python research/binomial_randomness_2026-10-24/make_report.py
```

正式口径核验还需要仓库根目录正式依赖 `requirements.txt`（或直接用项目现有虚拟环境验证）。`exact.py` 仅在本目录没有快照时创建快照；再次运行使用冻结快照。`simulate.py` 会校验源数据、协议、core.py、模拟代码的哈希，只有完全一致才复用缓存，避免旧结果被误用。

需要新数据时请新建日期目录并重建协议，不覆盖这次冻结文件。不要把包含新数据的快照拿去预测旧验证期。当前研究为回顾性数学审计，未执行交易回测。

## 输出与随机复核

每个理想模型、每种价格口径各200,000次；三种结构条件模型每种每口径49,999次，共1,099,994次独立零假设试验。随机种子与批次固定在协议和模拟代码。折叠分布补充分析重放同一批试验，不增加独立模拟次数。

主要假设下68项聚合概率用 Python 任意精度整数再算一次，结果以50位十进制保存；完整分子/分母以十六进制保存在 `results/integer_exact_fractions.json.gz`，可用 Fraction 直接还原。720个个体二项双侧p值也用整数权重重新计算核对。

计数精确分布采用 Poisson-binomial 动态规划，不用“60×平均概率”代替尾概率。不相同的样本数、阈值所需整数次数均保留。随机检验每次重新筛选训练名单和方向，不能只模拟事后选定的赢家。

关键连续统计量原始模拟分布在 `mc_*_key_distributions.npz`，离散计数完整频数在 `monte_carlo_count_histograms.csv`。所有p值使用 `(exceed+1)/(valid_draws+1)`，同时报告二项蒙特卡洛误差的Wilson区间。没有把有限次模拟中未出现事件写成零概率。

## 字段与检验家族

- `period`: full=全部有效数据，train=2017—2022，validation=2023—2026-10-23。
- `basis`: oc=收盘相对开盘，cc=收盘相对连续上一日有效收盘。
- `side`: up=事先固定上涨方向，down=事先固定下跌方向，either=事后允许选择两边中的较高者。
- `joint`: 先用训练期选择优势方向，验证期冻结同一方向。两个时期分别挑自己较高方向不算持续。
- `p`: 指定零假设下当前统计量及更极端结果的概率，不是“规律是假的概率”。
- `holm`: 同一明确列出的检验家族内控制家族错误率。`bh` 仅为FDR补充。
- 主要精确聚合68项；个体全历史240项；个体两分期480项；条件个体360项；主要模拟200项；次要精确138项；次要模拟210项；对称分布与折叠分布补充各20项。不同家族以及重叠模型不构成相互独立的证据。

分期、数据口径、门槛与top5/10/20均已固定。年内整周循环错位采取每年不同偏移，不能使用一个全历史统一偏移来简单重命名60个干支。结构审计明确记录保留的相邻链接、涨跌相关性和绝对收益相关性。

主协议在 `protocol.json`，后来补充的对称/折叠分布诊断在 `diagnostics_supplement.json`，明确其回顾性与同一模拟重用性质。所有结论仍需与未来未看过的数据区分。
