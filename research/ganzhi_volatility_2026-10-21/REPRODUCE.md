# 波动强度研究：复现、字段和输出索引

[完整报告](REPORT.html) · [六十干支附表](GANZHI_APPENDIX.html)

## 范围与冻结数据

所有新增文件位于 research/ganzhi_volatility_2026-10-21，研究代码不导入生产计算或此前EV模型。snapshot.json包含真实OHLC原始字符串、收盘时间、干支标签、行情同步时刻、仓库两份宏观日历快照。manifest.json记录源哈希与正式代码基线；protocol.json为主规格，protocol.initial.json保留首次计算前的时间边界澄清前版本。完整最终文件清单见bundle_manifest.json。

主样本外2023-01-01—2026-10-20；扩展2021-01-01—2026-10-20。2018-07起的较早回溯只用于产生诚实的历史基础预测残差。所有预测只用目标日开始之前收盘的信息，不进行交易收益模拟。

主规格之外的历史锁定前10组、固定2023整体基准与短窗口先验公平性比较为探索性补充。不能将这些试验中的个别有利结果当额外确认性证据。所有分母、原始结果与不利结果均保留。

## 建立独立研究环境

使用Python3.12，在仓库根目录运行：
```powershell
python -m venv research/ganzhi_volatility_2026-10-21/.venv
& .\research\ganzhi_volatility_2026-10-21\.venv\Scripts\python.exe -m pip install -r research/ganzhi_volatility_2026-10-21/requirements-research-lock.txt
```

研究依赖只安装在该目录的虚拟环境，正式项目环境没有改动。Windows若普通沙箱阻碍pip或研究进程，应以受授权的本地执行方式运行；不需要更改系统环境变量或生产requirements。

## 执行

主研究缓存逐目标预测，并校验快照、协议、引擎代码SHA；若任何不一致则重算，不能悄悄使用旧缓存。首次完整运行后，带真实预测数据的两项排序测试才能执行；其余12项测试不依赖主输出。
```powershell
$researchPython = '.\research\ganzhi_volatility_2026-10-21\.venv\Scripts\python.exe'
& $researchPython research/ganzhi_volatility_2026-10-21/run_study.py
& $researchPython research/ganzhi_volatility_2026-10-21/association.py
& $researchPython research/ganzhi_volatility_2026-10-21/risk_diagnostics.py
& $researchPython research/ganzhi_volatility_2026-10-21/cutoff_sensitivity.py
& $researchPython research/ganzhi_volatility_2026-10-21/verify.py
& .\.venv\Scripts\python.exe research/ganzhi_volatility_2026-10-21/verify_production_rules.py
& $researchPython -m pytest research/ganzhi_volatility_2026-10-21/test_research.py -q
& $researchPython research/ganzhi_volatility_2026-10-21/make_report.py
```

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
