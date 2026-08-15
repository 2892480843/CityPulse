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

## 生产平台工程

> 新工程与上方静态演示原型分开。阶段 1 交付工程基础；阶段 2 交付身份与数据；阶段 3-4 交付预测闭环与动作/回测（见下）。

### 阶段 3-4：预测闭环 · 动作与回测

- **评分分层**：趋势分（版本化权重的透明基线，排序分而非概率）、风险压力、证据完整度、行动优先级四项独立存储与展示；硬约束包括"风险 ≥80 直接 blocked"、"证据 <50% 最高 watch"、"数据超过 14 天不得 high"。
- **预测运行**：分析师选择 7/14/30 天窗口创建运行，输出城市榜单（排名、趋势分、风险、证据、优先级）与城市详情（因子构成、时间序列）；运行结果不可变并绑定评分版本与数据指纹。
- **经营动作**：从预测结果一键生成结构化草案（默认规则模板，配置 `CITYPULSE_DEEPSEEK_API_KEY` 后自动升级 DeepSeek 并保留降级）；草稿可编辑 → 提交审批 → 仅运营角色可批准/驳回，全程审计。
- **历史回测**：按 `available_at <= cutoff` 在 T0-30/14/7 截点重建排名，输出 Hit@5（候选 <6 时标注描述性）、平均提前量、每 100 城市日误报、证据覆盖；对照组越阈计入误报。
- **任务中心**：预测、回测、动作生成任务的状态、摘要与错误统一可查。
- **演示面板**：`data/signals_demo_panel.csv`（13 城 × 45 天 × 9 指标，5031 行）——上传提交后创建运行即可看到延吉 76.7（行动）/ 淄博 66.0（验证）的分层榜单，回测演示提前量 7 天、误报 0。

### 阶段 2：身份与数据

- **身份**：Argon2id 密码、服务端会话（HttpOnly Cookie + CSRF 令牌）、闲置 30 分钟 / 绝对 12 小时超时、登录失败限流（15 分钟窗口 5 次锁定）、三角色 RBAC（管理员 / 分析师 / 运营）。
- **用户管理**：管理员创建用户、分配角色、禁用即时撤销全部会话；不能禁用自己；密码策略至少 10 位并含字母数字。
- **审计**：登录成功/失败、登出、用户变更、数据集上传/校验/提交全部写入追加式 `audit_logs`。
- **数据中心**：CSV/XLSX 上传进入隔离区（扩展名 + MIME + 文件签名校验、20 MiB 与 20 万行上限、公式注入阻断、UTF-8 强制）；校验执行数据合同（必填列、`available_at` 必须存在且不早于 `published_at`、城市码必须在目录中、指标白名单、主键去重）；全部阻断错误修复后提交为不可变数据版本，重复内容按 SHA-256 幂等去重。
- **城市目录**：行政区划代码为主键的城市主数据 + 别名检索。
- **Web 工作台**：登录页、总览、数据中心（上传 / 校验报告 / 提交 / 城市目录）、系统管理（用户与角色）、系统状态；路由守卫按角色过滤，预测 / 动作 / 回测 / 任务中心为后续阶段占位。

### Docker Compose 启动

```bash
test -f .env || cp .env.example .env
docker compose --env-file .env run --rm migrate
docker compose --env-file .env run --rm api \
  python -m citypulse.identity.bootstrap --username admin --roles admin   # 交互输入密码
docker compose --env-file .env up --build -d
curl http://127.0.0.1:8080/health/ready
```

打开 `http://127.0.0.1:8080` 并用 bootstrap 创建的账号登录。数据库迁移必须显式执行，API 启动时不会自动修改 Schema（数据库结构）。bootstrap 支持从环境变量读密码：`--password-env CITYPULSE_BOOTSTRAP_PASSWORD`。

### 本地进程开发

```bash
python3.13 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install -e 'apps/api[dev]'
npm --prefix apps/web install
test -f .env || cp .env.example .env
docker compose --env-file .env -f compose.yaml -f compose.dev.yaml up -d postgres redis
apps/api/.venv/bin/alembic -c apps/api/alembic.ini upgrade head
CITYPULSE_DATABASE_URL='postgresql+psycopg://citypulse:local-development-database-password@127.0.0.1:5432/citypulse' \
  apps/api/.venv/bin/python -m citypulse.identity.bootstrap --username admin --roles admin
CITYPULSE_DATABASE_URL='postgresql+psycopg://citypulse:local-development-database-password@127.0.0.1:5432/citypulse' \
CITYPULSE_REDIS_URL='redis://127.0.0.1:6379/0' \
apps/api/.venv/bin/uvicorn citypulse.main:app --app-dir apps/api/src --reload
npm --prefix apps/web run dev
```

数据合同样例见 `data/signal_observation_sample.csv`：登录后在数据中心上传 → 校验 → 提交即可走通完整闭环。

### 验收

```bash
apps/api/.venv/bin/ruff check apps/api/src apps/api/tests apps/api/migrations
apps/api/.venv/bin/pytest apps/api/tests -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
./scripts/smoke-compose.sh
```
