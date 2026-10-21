# 节序 · BTC 看盘 V1

本地运行的 BTCUSDT / Binance Spot 看盘系统。以 **UTC+8 自然日日线** 为唯一行情源，关联固定中国历法数据库，再聚合自定义七日线、十二节月线、立春年线。没有交易下单、指标、信号或预测功能。

## 立即运行

本项目已在当前机器安装依赖、生成历法和下载历史行情。

- 双击桌面“节序 BTC 看盘”或 `start.cmd`：自动后台启动并打开浏览器；已运行时直接打开页面。
- PowerShell 执行 `.\start.ps1` 是保留的前台日志模式，需要手动打开下方地址。
- 浏览器打开 **http://127.0.0.1:8000**。
- 需要日期核验面板：`.\start.ps1 -DebugMode`。
- 只查看缓存、不联网更新：`.\start.ps1 -NoSync`。
- 默认每 60 秒更新一次，界面每 5 秒检查本地同步状态。页面“同步行情”可手动触发。
- 前台日志模式中按 Ctrl+C 停止。桌面模式服务在后台运行，关闭浏览器不会停止服务；再次双击会复用。服务仅监听 127.0.0.1。

首次复制到其他机器（Python 3.11+）：

```powershell
.\setup.ps1
.\start.ps1 -DebugMode
```

图表库和历法数据库已包含在项目中，正常运行不需要 Node.js、不访问 CDN、不访问 GitHub。仅重新安装图表依赖或运行浏览器测试需要 Node.js 20+。PowerShell 如果限制脚本执行，可使用 `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`，只影响该次进程。

## 周线锚点：尚未决定

**没有默认锚点，也不默认采用星期一。** 未配置时，点击周线会提示先设置。

1. 页面输入锚点日期并点击“应用”，浏览器将该选择保存在本机 localStorage；或
2. 启动前设置环境变量：

```powershell
# 仅为配置语法示例；不是本系统预设的正式锚点。
$env:CUSTOM_WEEK_ANCHOR = '你最终确定的 YYYY-MM-DD'
.\start.ps1
```

页面设置优先于环境变量。“清除”删除浏览器覆盖值，回到环境变量；环境变量也未配置时回到“尚未设定”。验收使用的 2026-01-01 已清除。

## 1. 目录

```text
backend/
  app.py                    FastAPI、本地静态文件、后台增量同步
  config.py                 环境变量配置
  models.py                 通用 Decimal Candle
  timeutils.py              Asia/Shanghai 时间与 UTC 毫秒转换
  market/
    binance_client.py       官方 API、分页、限流/重试
    repository.py          SQLite 原始日线缓存
    updater.py             增量刷新、缺日检测与补齐
    validation.py          重复/缺日/OHLC/时区验证
  economic/
    bls.py                  BLS官方档案与ICS日历，icalendar解析
    service.py              本地公布日期缓存和后台更新
  calendar/
    repository.py          固定 Calendar DB 只读查询
    service.py             历法查询、日线日期关联
  period/engine.py          日/锚点周/节气月/立春年解析器
  aggregation/aggregator.py 唯一通用 OHLCV 聚合器
  chart_service.py          历法关联与图表数据输出
frontend/
  index.html                本地页面
  app.js                    数据加载与交互
  charts/market-chart.js    Lightweight Charts 适配器
  controls/details.js      原始精度详情
  markers/daily-markers.js  干支/节气标签抽稀
  vendor/                   本地图表库、Apache License、NOTICE
data/
  market.db                 唯一行情源：原始日线
  us-economic-events.json   2017年起CPI/非农官方公布日期快照
  calendar.db               1900-01-01 至 2100-12-31 固定历法
  calendar_source/          历法原始源码包、MIT License、生成清单与校验值
scripts/
  sync_economic_calendar.py BLS公布日期缓存更新
  sync_market.py            命令行历史/增量下载
  generate_calendar.py      一次性离线生成历法
  verify_live_market.py     真实行情独立复核
  vendor-charts.mjs         从锁定 npm 依赖准备本地图表
tests/                      离线核心/API 测试、真实浏览器验收
artifacts/
  market-verification.json  真实 OHLCV 和小时线复核结果
  browser-verification.json 浏览器验收结果
  test-results.xml          自动测试报告
  browser/                  日/月/年及手机截图
requirements-lock.txt       Python 完整依赖锁
package-lock.json           前端及浏览器测试依赖锁
setup.ps1 / start.ps1 / start.cmd
```

## 2. 技术栈

- Python 3.11+、FastAPI 0.115.12、Uvicorn 0.34.2、httpx 0.28.1、icalendar 6.3.2。
- Python sqlite3；OHLCV 在数据库中保存十进制字符串，聚合使用 Decimal。
- 原生 JavaScript 模块 + **TradingView Lightweight Charts 5.2.1**；不是 Pine Script，也不是官网 Widget。
- lunar-python **1.4.8** 只用于离线数据生成及测试；生产 `backend/` 没有对该库的导入。
- pytest；Playwright 1.58.2 + 本机 Edge 用于端到端验收。
- `requirements.txt` 为生产直接依赖，`requirements-dev.txt` 加上生成和测试工具；`requirements-lock.txt` 锁定此次验证的完整环境。

## 3. Binance 数据获取

官方只读行情端点 `https://data-api.binance.vision/api/v3/klines`，无需 API Key：

```text
symbol=BTCUSDT
interval=1d
timeZone=8
limit=1000
startTime=<UTC 毫秒时间戳>
endTime=<UTC 毫秒时间戳>
```

首次从上市前日期开始查询，以 API 真正返回的第一根 K 确定历史起点；分页后保存 SQLite。后续只刷新缓存尾部及缺失区间，并重取上一天，避免昨天未收盘快照永久留在缓存中。缺口按连续区间合并请求，主键 UPSERT 防止重复；响应内部重复、乱序和非法 OHLC 会明确报错。

连接失败/5xx 最多重试三次；429/418 显示错误，并按 Retry-After 进入冷却。离线仍可查看既有缓存，UI 明示同步错误或陈旧状态。若缺日无法补齐，聚合返回 HTTP 409，绝不填造 K 线。

参考：[Binance 官方 Klines 参数](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data)、[官方公开行情端点](https://developers.binance.com/en/docs/products/spot/rest-api)。

## 4. UTC+8 日线实现

使用 Binance 原生 `timeZone=8`，不是默认 UTC 日线改显示标签。请求时间戳仍为 UTC 毫秒；每条响应校验 openTime 必须对应 Asia/Shanghai 当天 00:00。

例如 2026-09-07 00:00 +08:00 对应 2026-09-06 16:00Z。原始正常日线 closeTime 为下一零点前 1 毫秒。图表横轴传入服务端提供的公历日期（BusinessDay），不在浏览器重新分组或推算历法。

实际将 **2025-09-07 的 24 根 Binance 小时线**独立汇总，与 UTC+8 日线 OHLCV 全部一致，详见验收 JSON。

## 5–6. 历法来源、版本与许可证

- 项目：[6tail/lunar-python](https://github.com/6tail/lunar-python)。
- 精确发行版本：**1.4.8**。生成器检查安装版本，版本不符直接拒绝。
- License：[MIT](https://github.com/6tail/lunar-python/blob/master/LICENSE)，完整文本保存在 `data/calendar_source/LICENSE.lunar-python`。
- 原始发行源码包：`data/calendar_source/lunar_python-1.4.8.tar.gz`。
- 生成范围：1900-01-01～2100-12-31，**73,414 行**；额外读取前后年份的节气作为边界，使首尾年不截断。
- `manifest.json` 保存版本、范围、规则和数据库 SHA-256；`source-archive.json` 保存源码包与 PyPI 发布校验值。
- 重新生成：`.\.venv\Scripts\python.exe -m scripts.generate_calendar`。过程完全离线；先写临时数据库，完整性检查成功后替换正式库。建议停服后再生成。
- 节气精确时刻遵循源库的北京时间（固定 +08:00），不额外套用历史夏令时。V1 实际只使用日期；BTC 行情始于 2017 年，不涉及中国历史夏令时。
- 干支使用源库 `getDayInGanZhi()` 对自然日的输出，不使用 23 点换日口径。需求示例 2026-09-07 的真实输出是 **甲申**。

## 7. Calendar Database 结构

`calendar_days`：
`date`、`ganzhi_day`、`heavenly_stem`、`earthly_branch`、`ganzhi_index`（0 起）、`solar_term`、`solar_term_index`（源库冬至起，0 起）、`solar_term_date`、`solar_term_exact_time`、`solar_month`、`solar_month_id`、`month_index`（立春起 1～12）、`solar_year_id`。

`calendar_periods` 保存历法周期 ID、种类、名称、真实起止日期；`calendar_metadata` 保存生成规则及来源。历法周期表是离线历法索引，**不保存周/月/年行情**。

例如 2026-09-07：干支甲申、节气白露、`solar_month_id=2026-bailu`、`solar_year_id=2026`、精确节气时间 `2026-09-07T22:41:16+08:00`；V1 从当天 00:00 切月。

## 8. 聚合规则

- 日：UTC+8 自然日。
- 周：`index = floor((date - anchor).days / 7)`，起点为 `anchor + index*7 天`，终点为第七天；负 index 支持锚点前历史。
- 月：仅十二“节”切月；雨水、春分、秋分等“气”只作标记，不切月。白露月结束于寒露前一天。
- 年：立春起，到下一立春前一天；1 月 1 日不切换。2026 小寒月 ID 为 `2025-xiaohan`，其传统年为 2025。
- 唯一聚合器按 period resolver 分组：首日 Open / 最高 High / 最低 Low / 尾日 Close / Decimal Volume 求和。
- `Candle.metadata` 区分完整周期起止、实际包含的日期、日数、是否收盘、是否完整、源数据异常。首个不完整历史周期及正在形成的周期都不冒充完整周期。
- API 中 OHLCV 为十进制字符串；只在绘图时转换为 JS Number，详情保留原始精度。
- 聚合结果的 openTime/closeTime 是周期理论边界；日线 metadata 的 `sourceCloseTime` 保留 Binance 原始值，SQLite 也完整保留原始 close_time。

## 9. 测试与实际验收

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/test-results.xml
.\.venv\Scripts\python.exe -m scripts.verify_live_market
# 服务以 DebugMode 运行后执行；需要 npm ci 安装开发依赖和本机 Edge
npm run test:ui
```

此次结果记录在 `V1-REPORT.md`。核心测试包含 25 个固定随机日期的干支对照、201 年全部 4,824 个节气的源库对照、立春/白露/小寒边界、十进制精确 OHLCV、锚点前后周线、完整历法范围、缺日修复、缓存幂等、昨天终值刷新、限流冷却、API 错误和 Debug 开关。

浏览器测试会在隔离的浏览器上下文中临时使用 2026-01-01 锚点并清除，不改变正式配置。截图保存在本地。市场复核脚本需联网，离线单元测试不需联网。

## 10. 已知问题与明确边界

1. Binance 原始日线 **2018-02-08、2020-02-19、2020-12-21** 的 closeTime 提前。保留源行情，记录 warning，UI 显示并向周/月/年传播异常；没有用猜测价格补齐。尚未用完整分钟/小时历史重建这些异常日，因此不能宣称这些日完整无异常。
2. 周线正式锚点待你决定；没有擅自设定。
3. V1 是 60 秒轮询，不是逐笔/秒级流；当前日线及其上级周期均会变动。
4. 首个上市日可能只有部分日内交易；它所在的首个周/月/年若缺少前置自然日会标为不完整。
5. 历法可靠性继承 lunar-python 1.4.8；已对库原始输出交叉验证，未另做独立天文机构校核。1900～2100 范围外明确拒绝查询。
6. 首次使用需网络可达 Binance；不可达时保留缓存并显示失败，无备用交易所或模拟行情。
7. 运行环境的 AnyIO/Starlette 测试工具有一条弃用警告，不影响通过的测试。
8. 本机 Codex 内置浏览器/图片工具因 Windows ACL 配置错误无法使用；已使用本机 Edge 的真实浏览器测试与截图核验，项目服务不受该工具故障影响。

## 11. 后续扩展接口

- 新行情源实现 `server_time()`、`daily(start_ms,end_ms)` 接口；新增交易对时再扩展 SQLite 复合主键，V1 当前严格只有 BTCUSDT。
- 新周期实现 `PeriodResolver.resolve(candle) -> Period` 并注册到 `resolver_for`；共享同一聚合器。
- 新历法字段在离线生成器和 schema 版本中扩展，通过 CalendarService join 进入 metadata。
- 图表仅消费 ChartService 输出；五行、指标等后续模块可单独计算后附加，当前没有预先实现。
- 要改成精确节气时刻，需引入小时/分钟等更细行情并重新定义切分；本版不会把日线任意拆分。

### 配置与 API

环境变量：`CUSTOM_WEEK_ANCHOR`（空）、`DEBUG_MODE=false`、`AUTO_SYNC=true`、`SYNC_SECONDS=60`（最小 30）、`BINANCE_BASE_URL`、`MARKET_DB`、`CALENDAR_DB`。程序直接读取进程环境，`.env.example` 是说明示例，不自动加载。

- `GET /api/config`：规则、历法来源、配置。
- `GET /api/status`：缓存范围、同步状态、错误、陈旧状态。
- `POST /api/sync`：后台增量更新，不阻塞图表。
- `GET /api/candles?period=day|week|month|year&anchor=YYYY-MM-DD`：完整本地历史的相应聚合；anchor 为可选覆盖。
- `GET /api/debug/YYYY-MM-DD?anchor=YYYY-MM-DD`：仅 DEBUG_MODE 开启时提供。
- `GET /docs`：FastAPI 本地交互接口文档。

Lightweight Charts 使用 [Apache 2.0](https://github.com/tradingview/lightweight-charts/blob/v5.2.1/LICENSE)，页面保留 TradingView 链接与版权声明，分发保留完整 LICENSE / NOTICE。


## 周期干支显示更新

右侧详情标题与历法坐标统一使用对应周期的干支：日线取日干支、月线取月干支、年线取立春年干支；自定义周线取理论周期起始日干支，即使最早行情缺少该日，也不改用首根已缓存日线的干支。周线这一值是起始日标识，不另造传统“周干支”。

年/月干支预先由 lunar-python 1.4.8 的 getYearInGanZhiByLiChun / getMonthInGanZhi 生成，使用日期零点切换口径。Calendar schema 已升级为 2，新增 ganzhi_month / ganzhi_year。API metadata 增加 displayGanzhi、ganzhiBasis、ganzhiDate。OHLCV 和周期边界不变；图表上的节气标记开关仍可单独控制。

桌面启动入口为 scripts/launch.py，经由项目内 pythonw.exe 运行；错误日志在 artifacts/launcher-error.log，后台服务日志在 artifacts/desktop-server-8000.log。同一条历史提前收盘警告每个进程只记录一次，原始数据与页面异常提示仍完整保留。

## 日线干支筛选与全部干支排行

日线图表右上方新增“14号”开关；勾选后保留完整日线，并以金色烛芯和“14号”标记突出每个公历月 14 日的日 K。缩至全部历史时文字自动隐藏、保留圆点，放大后恢复文字。切换到其他周期时此开关不可用，返回日线后沿用当前勾选状态。

日线右侧 K 线详情增加“日内振幅”：悬停或点击任意日 K 时，显示（最高 − 最低）÷ 开盘 × 100%，保留两位小数。未收盘日线注明“当前”，随行情同步更新。

在日线图下方输入干支（例如“丁酉”）并点击“筛选统计”，查看匹配日期的 OHLC、涨跌幅、上涨/下跌/平盘次数和历史比例。点击明细日期会定位并固定图表详情，匹配日线会突出显示。

点击旁边的“遍历全部干支”无需填写干支，会按当前日期范围和涨跌口径一次统计六十甲子，同时显示上涨概率降序榜、下跌概率降序榜。点击排行榜里的干支，按该榜的日期范围和口径查看明细。概率相同时先按有效样本数降序，再按六十甲子顺序；无有效样本时显示“—”并排最后。排序用精确次数比值，不用显示后四舍五入的百分数。

- 日期范围含开始日和结束日；留空使用全部本地历史，统计不受图表缩放范围影响。
- 默认口径：收盘相对开盘；可切换为收盘相对前一自然日收盘。昨收即使在筛选范围外也会读取。
- 分母为有效样本总数，上涨、下跌和平盘分别计数；未收盘、没有成功同步快照、源时间异常、上市首日不完整的日线不计入。昨收口径还排除缺少有效昨收的日期。
- 关闭时间以最近成功同步快照为准；不会因为本机时间已跨日就把未刷新的日线计为已收盘。
- 一次遍历共享同一份 SQLite 读快照。发现历史缺日会明确报错，不默默跳过或填造数据。
- 概率是历史样本频率，不代表未来表现。日线和月线提供此面板；切换到周/年线时隐藏。切换统计周期会清除旧周期的查询结果和高亮。

接口：
- `GET /api/statistics/ganzhi/options`：60 个有效干支。
- `GET /api/statistics/ganzhi?ganzhi=丁酉&basis=open`：单干支明细与统计。
- `GET /api/statistics/ganzhi/rankings?basis=open`：两个完整排行榜。
- 后两者支持可选 `start=YYYY-MM-DD`、`end=YYYY-MM-DD`；`basis` 可选 `open` 或 `previous_close`。

浏览器统计验收：`npm run test:statistics`（需先启动本地服务）。

## 月线干支筛选与排行

月线图会在月 K 下方标注对应流月干支；保持“干支”开关可用，缩放较密时自动抽稀，放大后显示每根月 K 的标签。标签取月周期起始日对应的月干支，与右侧详情一致。

切换到“月”后，图表下方显示“干支月 · 筛选统计”。输入“丁酉”或“丁酉月”筛选月干支，或直接点击“遍历全部干支”，查看上涨概率、下跌概率降序双榜。点击干支展开对应月份的 OHLCV 和涨跌幅，点击月周期起止日期定位并固定月 K 详情。

- 使用已有的十二节月线边界和对应月干支，不按公历月份、起始日日干支或单根日 K 分组。
- 日期范围按月 K 理论起始日筛选，包含两端；即使结束筛选日位于月内，也使用整根月 K，不截断月 OHLCV。
- 默认比较月收盘和月开盘；“收盘 vs 上月收盘”读取前一个连续节气月，前月可在筛选范围外。
- 仅统计已收盘、自然日日线覆盖完整、没有源时间异常且不包含上市首日的月份。上月收盘口径还要求前月有效。未收盘或不完整月份保留在明细中并注明不计入。
- 两榜包含全部 60 个干支，无有效月样本显示“—”并排最后。月线样本数独立于日线。
- 单干支和排行榜接口增加可选参数 `period=month`；不传仍默认 `period=day`。例如：`GET /api/statistics/ganzhi?ganzhi=丁酉&period=month`、`GET /api/statistics/ganzhi/rankings?period=month`。
- 月线浏览器验收：`npm run test:month-statistics`；该测试会核对真实月 K 与双榜计数、月干支明细、日期范围、前月收盘、图表定位及手机布局。

## 流日逐年胜率

在日线页筛选干支日后，点击明细中的任意日期，历史统计区会在日线明细表后直接显示该干支日的逐年胜率，并突出当前点击日期所属的公历年。每一行年份为该年 1 月 1 日（含）至次年 1 月 1 日（不含）；显示上涨率、下跌率、平盘次数与有效样本数。上涨率 = 当年有效上涨次数 ÷ 当年有效样本数，平盘计入分母。

逐年结果沿用当前干支、日期范围、收盘/开盘或收盘/昨收口径，以及未收盘、源异常和上市首日的排除规则。日期范围若只覆盖某年的一部分，该年只统计范围内的匹配日线；没有有效样本时概率显示“—”。API 单干支结果增加 `yearly` 数组，每项含 `start` 与次年 1 月 1 日 `endExclusive`；排行榜和月线结果不展示年度明细。

## 流日胜率日历

日线图下方、干支筛选统计上方使用 [FullCalendar](https://github.com/fullcalendar/fullcalendar) 6.1.21 标准版的 `dayGridMonth` 月视图。项目固定 npm 版本并保存其浏览器脚本与中文语言包到 `frontend/vendor/`，桌面运行不依赖 CDN。标准版为 MIT 许可；完整许可见 `frontend/vendor/LICENSE.fullcalendar` 和 `LICENSE.fullcalendar-core`。

日历自带上月、下月、今天导航；每格显示公历日期、日干支、节气（如有）和同干支日历史胜率、典型幅度、大行情率及有效样本数。上涨或下跌率严格超过 50% 时显示占优方向；均未超过时显示双边比例。已完成且有效的日期另显示当日实际涨跌幅，悬停可查看完整概率及有效样本数。默认使用“收盘 vs 开盘”，下方选择“收盘 vs 昨收”时同步更新。日历胜率默认取全部本地已收盘、有效日线，可切换近三年；不随图表缩放或下方日期筛选变化。点击日期会按该日干支打开现有日线统计；月线、周线、年线隐藏日历。日历右上角显示当月判断核对：月末尚未走完时显示“未完成”，月末已过时仅对有明确上涨或下跌方向且有有效实际收盘的日期计算正确率，同时列出正确天数、可判断天数及未计入天数。此统计按当前选择的历史样本窗口回看核对，并非独立的预测回测。胜率是历史频率，不代表该日期的未来表现。

服务端 `GET /api/calendar/days?start=YYYY-MM-DD&end=YYYY-MM-DD&basis=open` 返回可见区间（开始含、结束不含）的固定历法数据和六十甲子日线概率。`npm run test:calendar` 可在本地服务运行时验证日期显示、翻月、筛选联动、口径切换与手机七列布局。


## 流日强度统计

日历在方向概率之外显示典型幅度（逐次绝对涨跌幅的中位数）、大行情率及同干支样本数。方向概率默认保留 2017 年上线以来的有效历史；所有幅度历史统计统一只使用 2023 年 1 月 1 日（含）起的有效 K 线，包括典型幅度、上涨时中位涨幅、下跌时中位跌幅、带符号平均涨跌幅、典型日内振幅、大行情率、大涨率、大跌率及普通 BTC 日线对照。日线和月线筛选统计的平均、中位、最高及最低涨跌幅也使用此下限，月线按周期开始日期取样；方向计数、涨跌概率、逐年方向胜率与历史明细仍保留原方向范围。

门槛可选 2%、3%、5%，默认 3%；大行情包含绝对涨跌幅达到门槛的日期。大行情率、大涨率、大跌率的分子和分母都使用 2023 年起范围内全部有效样本；上涨、下跌幅度中位数分别用该范围内各自方向样本。日内振幅为（最高 − 最低）÷ 开盘 × 100%。日历格分别显示方向样本和幅度样本；详情卡片标明起点和样本数，没有符合范围的幅度样本时显示“—”。蓝色底色深浅以典型幅度相对同范围普通 BTC 日线的比例表示。已收盘且有效日期的实际绝对涨跌幅达到当前 2%、3% 或 5% 门槛（含等于）时，日历格持续显示上涨绿色或下跌红色；悬停和选中保留该底色，选中另显示描边。此颜色按当天实际结果判断，并随收盘/开盘、收盘/昨收口径和门槛同步更新；未收盘、源异常及无实际结果日期不高亮。服务端按 Decimal 原始精度返回 actualLargeMoveDirection，避免舍入导致误判，且不受 2023 年起的历史幅度窗口限制。

“全部历史 / 近三年”以及下方日期筛选保持原有作用，幅度统计额外与 2023 年起的范围取交集。近三年以最后同步时间的 UTC+8 日期减三年为起点（2 月 29 日回退至 2 月 28 日）；切换月份不改变历史窗口。点击流日后，下方已有干支日筛选也沿用这一窗口。每根历史 K 线的实际涨跌幅、图表 OHLCV 和单根振幅保留原始真实值，旧日期仍展示其已收盘实际结果。

仅使用现有有效已收盘样本，继续排除未收盘、源异常、上市首日以及昨收不可用的记录；所有计算先使用 Decimal 原始精度，再格式化输出，门槛分类不使用舍入后的涨跌幅。无有效样本显示“—”，不填零。现有统计用于按当前样本回看；未增加滚动预测回测。

日历接口新增可选参数：`GET /api/calendar/days?start=2026-10-01&end=2026-11-01&threshold=3&window=recent3&basis=open`。响应包含各干支的 `strength` 和同窗口普通日线 `benchmark`。

## 后台刷新

行情同步后，日历、强度详情、筛选统计、逐年胜率和排行榜在新数据返回前保留现有内容，不清空日历或临时隐藏结果，也不取消 K 线筛选高亮。刷新保留阅读位置和图表缩放；相同行情跳过重绘，末根价格变化和新增 K 线使用 Lightweight Charts 的增量更新，历史修正仍完整更新。

短暂刷新失败时保留上次成功的数据并显示更新失败提示，后续状态轮询会重试。只有切换周期或主动改变统计条件时展示对应的加载状态。`npm run test:refresh` 模拟慢响应、失败恢复、无变化行情、新增 K 线与历史修正（需先启动本地服务）。

## 美国 CPI / 非农公布日标注

日线图右上角加入 CPI、非农勾选项，默认关闭。CPI 用蓝色向下箭头和影线、非农用紫色向下箭头和影线，标在每次公布日的 K 线上；取消勾选恢复。与14号、干支、节气和干支筛选高亮并存，不删除其他 K 线，非日线周期禁用这两个开关。缩放后只更新可见标注，缩得很远时保留箭头并隐藏拥挤文字。点击或悬停对应 K 线，侧栏显示北京时间和 BLS 官方发布原文链接。

已调研 GitHub 上的 [AKShare](https://github.com/akfamily/akshare)、[investpy](https://github.com/alvarobartt/investpy) 和 [Trading Economics](https://github.com/tradingeconomics/tradingeconomics-python)。本功能仅需要精确的发布日期，采用 [icalendar 6.3.2](https://github.com/collective/icalendar) 解析 BLS 官方 ICS，并用官方档案确认历史实际发布；无需付费账户或 API Key，没有按固定星期或固定号数推算日期。

- CPI 历史：[BLS CPI档案](https://www.bls.gov/bls/news-release/cpi.htm)。
- 非农历史：[BLS Employment Situation档案](https://www.bls.gov/bls/news-release/empsit.htm)，不是 ADP 就业或失业救济申请。
- 官方日历：[BLS ICS](https://www.bls.gov/schedule/news_release/bls.ics)。
- 取档案链接文件名中的实际公布日，不取数据所属月份。历史发布时刻为美国东部08:30，按 America/New_York 时区处理夏令时，映射到 UTC+8 日线，分别是北京时间20:30 / 21:30。
- 档案确认的实际发布优先于计划日历，延期/取消的旧计划不混入历史标注。当前日及未来计划保留“计划”字样；未来没有行情 K 线时不创建价格或虚拟 K 线。已过去且未获档案确认的计划日期不会继续标注。
- 项目附带2017年开始的官方日期快照 data/us-economic-events.json，离线即可显示。默认后台每6小时更新；失败保留已核实缓存并30分钟后重试，不阻塞行情加载。-NoSync 不联网更新。
- BLS 对机器访问返回403等网络错误时，使用 Jina 公共文本阅读服务获取同一官方页面；校验 URL Source 与 ICS 发布者，原始来源链接始终为 BLS。缓存记录访问渠道，数据接口 /api/economic-events 提供版本、更新时间和状态。
- 手动更新本地缓存：python -m scripts.sync_economic_calendar。重建随项目分发的快照：python -m scripts.sync_economic_calendar --seed。

经济事件浏览器验收：npm run test:economic-events；离线数据与时区验证：python -m pytest tests/test_economic_events.py -q。
