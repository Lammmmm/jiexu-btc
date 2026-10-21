# 高胜率持续性研究：复现、字段与文件索引

[完整报告](REPORT.md) · [全部60干支明细](GANZHI_DETAILS.md)

## 独立性和数据

本目录从snapshot.json的原始OHLC、收盘时间和干支标签独立计算，不导入以往研究结果或代码。快照是仓库真实UTC+8数据的冻结副本，截止2026-10-20收盘。source_daily.csv保留全部源日期和剔除原因；未收盘/异常行不进训练验证。manifest.json记录源、协议和Git基线。初始协议与任何计算前的两项方法澄清均保留。

## 环境与执行

Python3.12，依赖见requirements-research-lock.txt。可建立本目录独立.venv，也可使用现有科学研究环境。仓库根目录：

```powershell
$rp = '.\research\ganzhi_volatility_2026-10-21\.venv\Scripts\python.exe'
& $rp research/ganzhi_persistence_2026-10-21/run_observed.py
& $rp research/ganzhi_persistence_2026-10-21/simulate.py
& $rp research/ganzhi_persistence_2026-10-21/bootstrap.py
& $rp research/ganzhi_persistence_2026-10-21/evaluate.py
& $rp -m pytest research/ganzhi_persistence_2026-10-21/test_research.py -q --junitxml=research/ganzhi_persistence_2026-10-21/results/unit-tests.xml
& .\.venv\Scripts\python.exe research/ganzhi_persistence_2026-10-21/verify_production.py
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
