# ≥55% 流日研究：复现说明

[完整报告](REPORT.md) · [六十干支附表](GANZHI_APPENDIX.md)

## 研究范围

本目录只新增研究文件。父研究 `../ganzhi_volatility_2026-10-21` 必须完整存在，其中的真实冻结行情、干支标签、代码及逐日预测按 manifest.json 哈希核对。方向筛选从 2017 年实际可用日 K 起，绝不改成 2023 起方向筛选。父研究最新已收盘日为 2026-10-20；当天未收盘日不参与筛选或评分。

`protocol.json` 在读取新筛选结果前固定 55% 规则和推断方案。收益和事件口径不变，模型和超参数不重新优化。父研究的月度滚动、训练内选择和逐日输入详见其 REPRODUCE.md；本轮复用的是它当时已发布的无泄漏预测，重新执行测试日筛选和评分，而非在筛选样本上训练新的模型。

## 运行

在仓库根目录使用 Python 3.12。可以复用父研究环境，或创建新环境并安装父研究的 requirements-research-lock.txt：

```powershell
$rp = '.\research\ganzhi_volatility_2026-10-21\.venv\Scripts\python.exe'
& $rp research/ganzhi_win55_volatility_2026-10-21/study.py
& $rp -m pytest research/ganzhi_win55_volatility_2026-10-21/test_study.py -q --junitxml=research/ganzhi_win55_volatility_2026-10-21/results/unit-tests.xml
& $rp research/ganzhi_win55_volatility_2026-10-21/verify.py
& .\.venv\Scripts\python.exe research/ganzhi_win55_volatility_2026-10-21/verify_production_rules.py
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
