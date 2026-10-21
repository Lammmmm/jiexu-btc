# 六十甲子干支日与 BTC 波动强度研究

本目录是独立研究交付，不修改正式日历、API、干支统计或交易逻辑。

**结论 C：目前无法证明干支日具有独立、稳定的波动预测价值，不建议据此开发预测功能。** 历史排行不能当作未来预测优势；详细结论、反例及限制见报告。

## 阅读入口

- [完整中文研究报告](REPORT.md)
- [六十甲子详细统计与样本外附表](GANZHI_APPENDIX.md)
- [复现步骤、字段定义及文件索引](REPRODUCE.md)
- [六十甲子统计 CSV](results/sixty_ganzhi_statistics.csv)
- [模型样本外对比 CSV](results/model_comparison.csv)
- [各模型逐年表现 CSV](results/yearly_models.csv)
- [稳健性对比 CSV](results/robustness_comparison.csv)
- [完整逐日预测（压缩 CSV）](results/predictions.csv.gz)

下载目录后可用浏览器打开 `REPORT.html` 阅读带图表的本地版本。

## 数据与验证范围

使用仓库真实 Binance BTCUSDT 现货 UTC+8 日线冻结快照及现有干支规则，最新已收盘日为 **2026-10-20**。主样本外区间为 **2023-01-01 至 2026-10-20，共 1,389 日**；扩展区间自 2021 年开始，共 2,119 日。研究比较 17 个模型和 11 个目标，覆盖开收盘绝对涨跌幅、昨收口径、日内振幅和固定大行情门槛。

逐日预测只使用目标日开始之前已收盘的信息。仓库缺少历史宏观日历的逐时版本，因此严格主检验 F/G 不使用无法证实事前可知的 CPI/非农标签；使用最终公布日期的结果单列为条件性分析，不能当作严格可执行预测。

已完成 14 项研究测试、独立预测核验及 840 项正式统计规则对照。原始验证记录见 [unit_tests.json](results/unit_tests.json)、[independent_verification.json](results/independent_verification.json) 和 [production_rules_verification.json](results/production_rules_verification.json)。

## 复现与审计

`snapshot.json`、`protocol.json`、`manifest.json` 和 `bundle_manifest.json` 保留数据、预设规格及文件哈希。研究使用独立 Python 环境，依赖版本见 `requirements-research-lock.txt`。虚拟环境和缓存不上传；运行日志保留成功运行及初次中断的记录，完成状态以 `run-final.log` 及验证文件为准。

本目录的 `.gitattributes` 保留文件原始字节，避免 Git 自动转换换行符使审计哈希失效。`bundle_manifest.json` 是研究结束时的清单，不包含随后新增的本阅读入口及 Git 配置文件。
