# CityPulse 热城先知

> 面向去哪儿的爆火小城预测与产品生成智能体。

**核心主张：**在热度形成前 7-14 天，识别正在异常升温的小城，解释原因与不确定性，并把预测转成可上线的交通、酒店、景点和内容方案。

## 为什么不是普通 Agent

- 核心预测由**季节基线、变点检测和学习排序模型**承担；大模型不直接“猜城市”。
- 每个结论同时给出**置信度、风险压力、证据来源和时间版本**。
- 使用**历史时间截断回测**，防止事后信息泄漏。
- 输出不止是报告，而是面向去哪儿运营的**客群、产品组合、上线时机、投放主题和备供建议**。


## 界面预览

| 全国热城雷达 | 城市详情与证据 |
|---|---|
| ![全国热城雷达](assets/ui_radar.png) | ![城市详情与证据](assets/ui_detail.png) |

| 去哪儿经营动作 | 历史回测验证 |
|---|---|
| ![去哪儿经营动作](assets/ui_action.png) | ![历史回测验证](assets/ui_backtest.png) |

## 仓库内容

```text
.
├── index.html
├── data/
│   ├── city_score_snapshot.csv
│   ├── daily_signal_sample.csv
│   ├── feature_dictionary.csv
│   └── reference_sources.csv
├── src/scoring.py
├── assets/
│   ├── ui_radar.png
│   ├── ui_detail.png
│   ├── ui_action.png
│   └── ui_backtest.png
└── docs/
    ├── architecture.md
    ├── backtest_protocol.md
    ├── research_notes.md
    ├── enterprise_questions.md
    ├── judging_map.md
    ├── references.md
    └── team_evidence.md
```

## 运行

直接打开 `index.html`，或在目录中执行：

```bash
python -m http.server 8000
```

透明基线：

```bash
python src/scoring.py data/city_score_snapshot.csv --output ranked_output.csv
```

## 真实性声明

仓库内候选城市、数值、排名和回测曲线均为**模拟数据/方法演示**，用于说明数据合同、评分逻辑、界面与验证流程，不构成真实预测，也不宣称已取得模型指标。所有正式结果必须基于合法获取的数据和严格时间截断回测重新生成。
