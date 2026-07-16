# CityPulse 技术架构

## 设计原则

1. **预测模型与生成模型分工**：时序异常检测与排序模型负责“会不会火”；大模型只负责证据整理、经营动作生成与交互解释。
2. **时间可审计**：每条事实记录 `source_url`、`published_at`、`observed_at` 与 `available_at`；回测只允许使用截点前已可获得的信息。
3. **先提示不确定性，再建议动作**：同时输出潜力分、置信区间、风险压力与证据完整度；低置信度城市进入观察池。
4. **企业数据可插拔**：报名期使用官方与开放数据完成方法闭环，企业阶段接入去哪儿脱敏搜索、订单、价格与库存特征。

## 数据链路

`Source Adapters -> Raw Evidence Store -> Entity Resolution -> City-Date Feature Store -> Baseline & Change-Point Detection -> Learning-to-Rank -> Calibration -> Evidence Graph -> Qunar Action Agent -> Dashboard`

- Source Adapters：文旅统计、POI、天气、交通、事件及企业授权数据。
- Entity Resolution：使用行政区划代码统一城市实体，处理同名地名、区县升级与别名。
- Feature Store：按 `city_id × date` 形成可追溯特征快照。
- Baseline：季节基线、同比/环比、移动中位数与稳健 Z-score。
- Ranker：LightGBM/XGBoost 或 LambdaMART，优化未来 7/14/30 天城市排序。
- Calibration：Platt/Isotonic 校准，输出概率与置信区间。
- Evidence Graph：连接“城市-事件-内容主题-客源地-供给风险”。
- Action Agent：生成客群、交通/酒店/景点组合、上线时间、投放主题与备供建议；事实型字段必须来自工具和证据图。

## 最小可行实现

MVP 覆盖 30-50 座城市、3 个历史正例与一组对照城市；每天生成快照。后端使用 FastAPI，数据使用 PostgreSQL/SQLite；先以透明加权基线和变点检测跑通，再替换学习排序模型。
