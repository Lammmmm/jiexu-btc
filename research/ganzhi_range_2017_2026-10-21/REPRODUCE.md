# 2017 起振幅研究：复现说明

[报告](REPORT.md) · [全部降序排行](RANKINGS.md)

本目录是独立研究，依赖父目录的 ganzhi_volatility_2026-10-21 与 ganzhi_win55_volatility_2026-10-21。真实冻结行情和干支标签、原模型引擎、先前无泄漏评估辅助函数都按 manifest.json 的SHA256校验。方向史和本轮幅度均从2017实际可用起，2026-10-20为最新收盘日。

## 运行

仓库根目录，Python3.12，科学依赖沿用父研究 requirements-research-lock.txt：

```powershell
$rp = '.\research\ganzhi_volatility_2026-10-21\.venv\Scripts\python.exe'
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
