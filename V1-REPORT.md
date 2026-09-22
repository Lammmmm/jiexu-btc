# V1 交付与验收报告

验收日期：2026-09-17。项目位于 `D:\work\pythonProject\玄学k线`。

**系统已实际启动、下载 Binance 行情并通过真实浏览器验收。** 本次保留的本地服务地址是 http://127.0.0.1:8000，Debug 已开启；服务仅监听本机。以后双击 `start.cmd` 即可启动，或 `.\start.ps1 -DebugMode`。

## 1. 项目目录结构

```text
backend/
  market/       BinanceClient / MarketRepository / MarketDataService / Validation
  calendar/     CalendarRepository / CalendarService
  period/       Daily / CustomWeek / SolarMonth / SolarYear
  aggregation/  CandleAggregator
  app.py / chart_service.py / config.py / models.py / timeutils.py
frontend/
  charts/ / controls/ / markers/ / vendor/
data/
  market.db / calendar.db / calendar_source/
scripts/ / tests/ / artifacts/
README.md / requirements-lock.txt / package-lock.json
setup.ps1 / start.ps1 / start.cmd
```

## 2. 技术栈

Python 3.11.4、FastAPI 0.115.12、Uvicorn 0.34.2、httpx 0.28.1、SQLite、Decimal；原生 JavaScript 模块与 **Lightweight Charts 5.2.1**。没有 Pine Script 或 TradingView Widget。图表脚本随项目本地提供。

## 3. Binance 数据获取方式

Binance Spot 官方公共行情端点：`https://data-api.binance.vision/api/v3/klines`，仅 BTCUSDT，每页最多 1000 根，无需密钥。首次缓存 **3,319 根**，日期为 **2017-08-17～2026-09-17**。第二次同步实测仅重取 **2 根**，没有重复下载全部历史。

SQLite 主键去重，缺日合并为区间补取，昨日和当日反复刷新。错误明确呈现，既有缓存保留。

## 4. UTC+8 Daily K 的实现

请求显式使用 `interval=1d&timeZone=8`；startTime/endTime 使用 UTC 毫秒。后端逐根检查 Asia/Shanghai 零点开盘，绝不把 UTC 日线改标签冒充 UTC+8。

独立取得 **2025-09-07 的 24 根小时线**重算 OHLCV，与日线完全一致。

## 5–6. GitHub 历法项目、版本与 License

采用 [6tail/lunar-python](https://github.com/6tail/lunar-python)，**精确锁定发行版本 1.4.8，MIT License**。许可证、源码 tar.gz、源码包校验和、生成规则及数据库 SHA-256 均保存在 `data/calendar_source/`。

数据库已离线生成 **1900-01-01～2100-12-31，共 73,414 行**。正式后端只读 SQLite，不调用历法库，也不实时访问 GitHub。节气时间与干支均来自源库，不手写天文算法。

源库给出 2026-09-07 为 **甲申日**，不是需求中示意的甲午日。已据实实现并测试。

## 7. Calendar Database 结构

- `calendar_days`：公历日期、干支、天干、地支、甲子索引、节气名称/索引/日期/精确时间、节气月名称/ID/序号、传统年 ID。
- `calendar_periods`：月份和年份的真实起止日期与名称。
- `calendar_metadata`：源项目、版本、License、生成范围、时区和切换口径。

例如 `2026-09-07`：甲申、白露、`2026-bailu`、传统年 2026；源库精确节气时刻 `22:41:16+08:00`，V1 则从 **当天零点**切月。

## 8. 周/月/年聚合规则

- **周**：锚点起连续七天，floor 除法向前反推负序号。正式锚点仍未配置。
- **月**：立春、惊蛰、清明等十二节到下一节前一天；不按公历月份。
- **年**：立春到下一立春前一天，小寒仍属于上一传统年。
- **OHLCV**：首开、最高、最低、尾收、成交量 Decimal 求和，共用一个聚合器。
- 所有派生 K 线按需从原始日线重新生成，未作为独立源数据保存。
- 详情区分周期理论边界、已观察日期、未收盘、数据缺失和交易所时间异常。

## 9. 自动测试与实际运行结果

**70 项 Python 自动测试通过，0 失败**；耗时约 4 秒。有 1 条 AnyIO/Starlette 测试工具弃用警告，不影响功能。

涵盖：
- 立春、白露前/当天/后一天切换，小寒传统年归属；
- 25 个固定随机日期的干支与原始库核对；
- 全部 **4,824 个节气**日期和精确时刻与原始库核对；
- 日历两端完整、闰日、越界；
- 月/年/周 OHLCV 精确聚合与负序号周；
- 重复、乱序、缺日、非法 OHLC、NaN、错误时区；
- 分页、增量、缺口修复、幂等、昨日未收盘数据终值刷新；
- 限流冷却、网络/5xx 重试、API 异常与 Debug 开关。

**11 项真实 Edge 浏览器验收通过**：
日线展示、未设锚点提示、设置锚点后的周线、节气月切换及点击详情、立春年切换及点击详情、干支/节气开关和标记数据、Debug 查询、测试锚点清除及刷新验证、手动同步、手机布局、无 JavaScript 异常。

已查看日线、年线和手机截图。快速连续点击触发图表双击时的详情固定行为已修复。

### 真实市场数据独立复核

| 周期 | 日期范围 | 日线数 | Open | High | Low | Close | Volume（BTC） |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025 白露月 | 2025-09-07～2025-10-07 | 31 | 110384.16000000 | 126199.63000000 | 108620.07000000 | 121846.01000000 | 418850.79717600 |
| 2025 立春年 | 2025-02-03～2026-02-03 | 366 | 99346.87000000 | 126199.63000000 | 74508.00000000 | 78132.33000000 | 7390928.68472400 |

从 SQLite 原始日线用独立代码逐项重算，与系统聚合**完全一致**。这不是人工肉眼逐笔验算，完整输入边界、预期值和实际值保存在 `artifacts/market-verification.json`。

## 10. 已知问题

1. Binance 历史源数据有 **2018-02-08、2020-02-19、2020-12-21** 三个提前 closeTime 异常日。**原始 OHLCV/时间戳完整保留**，日志与 UI 明示，聚合周期传播异常；尚未用细粒度历史行情重建这些日。
2. 周线正式锚点待你指定；未使用默认星期或擅自固定测试日期。
3. V1 每 60 秒轮询，当前日/周/月/年均可能未收盘，非逐笔实时系统。
4. 最早上市区间可能不完整，已按覆盖范围标记；历法不支持 1900～2100 外查询。
5. 历法输出与采用的开源库一致，但未另做独立天文机构校核；历史精确节气时刻采用源库固定北京时间，不套历史夏令时。BTC 行情无此历史 DST 问题。
6. 本机内置 Codex 浏览器和图片工具有 Windows ACL 启动故障；实际验收改用本机 Edge 完成，并保存截图。项目本身正常运行。
7. 本系统当前只支持 BTCUSDT / Binance Spot，无下单、策略、信号、技术指标或预测。

## 11. 后续扩展接口

`PeriodResolver.resolve(Candle) -> Period` 支持增加新周期，继续共用 CandleAggregator。CalendarService 负责日线与历法字段关联，新增属性放 metadata。行情 API 客户端、SQLite 仓库、周期计算和前端图表分别独立。

进一步的启动、配置、API、重建与测试命令见 **README.md**。
