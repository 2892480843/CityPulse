# 阶段 5 生产加固验收清单

对照 `docs/superpowers/specs/2026-08-15-citypulse-production-platform-design.md` 第 5.6 节的最终验收清单逐项记录交付状态与证据位置。

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 三类角色只能访问权限矩阵允许的页面与 API，跨角色请求由服务端拒绝并审计 | ✅ | `tests/unit/identity/test_users_api.py`、`tests/unit/prediction/test_prediction_api.py`、`tests/unit/backtest/test_backtest_api.py` |
| 2 | CSV/XLSX 导入具备隔离校验、错误报告、幂等提交和不可变版本 | ✅ | `tests/unit/ingestion/`；`available_at` 数据合同在 `src/citypulse/ingestion/contract.py` |
| 3 | 所有证据具备来源与 published_at / observed_at / available_at，回测严格按截点读取 | ✅ | `src/citypulse/backtest/service.py` 的 `collect_city_observations(available_at_cutoff=...)`；`tests/unit/backtest/` |
| 4 | 趋势分、风险压力、证据完整度和行动优先级分别存储、展示和解释 | ✅ | `prediction_results` 表四列独立；前端榜单与城市详情分区展示；`tests/unit/prediction/test_scoring.py` |
| 5 | 未达到校准门槛时，系统任何位置都不显示"爆发概率" | ✅ | 代码与页面均无 probability 字样；城市详情明确标注"趋势分（非概率）" |
| 6 | 预测失败不会覆盖最近一次成功版本，页面明确展示数据时间和运行版本 | ✅ | 失败运行落 `jobs` 并保留旧结果；榜单页展示运行时间与窗口 |
| 7 | DeepSeek 输出经过结构与证据校验；失败时规则降级；所有草案必须人工审批 | ✅ | `src/citypulse/actions/deepseek.py`（解析失败返回 None 即降级）；审批状态机 `actions/service.py`；仅 operator 可批准 |
| 8 | 演示数据与生产数据在存储、筛选、指标、页面和导出中均可区分 | ✅ | 数据集均带 source_name/legal_basis 与 SHA-256；演示面板文件名独立于生产目录 |
| 9 | 关键操作具有请求 ID、结构化日志和不可由业务接口删除的审计记录 | ✅ | `audit_logs` 无删除 API；`RequestContextMiddleware` 注入 X-Request-ID |
| 10 | Docker Compose 在 macOS 本地和 Linux 环境均可启动，健康检查、迁移、备份与恢复路径经过验证 | ✅ | macOS 本地栈运行中；Linux 冒烟 `scripts/smoke-compose.sh`（CI 中执行）；备份 `scripts/backup.sh`、恢复演练 `scripts/restore-drill.sh`（结果记录于 `backups/restore-drill.log`） |
| 11 | 单元、数据质量、集成、契约、前端、端到端、安全和部署测试通过 | ✅ | pytest 77、vitest 21、ruff、tsc、vite build、compose smoke（含端到端数据链路） |

## 后续迭代补齐项（0004_hardening 迁移交付）

- **保留期定时器** ✅：`citypulse.system.retention` Celery 任务（beat 每日调度）清理超过 365 天的审计行与超过 90 天的已提交原始上传文件，清理量记录在任务结果中；数据集元数据与观测数据保留。
- **动作方案版本表** ✅：`action_plan_versions` 在生成、编辑、提交、审批各事件写入版本快照（`GET /api/v1/action-plans/{id}/versions` 可查），历史版本不可覆盖。
- **概率校准工具** ✅：`calibration` 模块从回测快照计算 Brier / ECE / 可靠性分箱（`POST /api/v1/calibration-reports`），样本 <100 判定 `insufficient_samples`；概率展示门禁按规格 3.6 继续关闭，所有响应附带 gate_note。
- **HSTS**：反向代理配置中已留注释位，TLS 终止后在对应 server 块启用（本地 HTTP 部署不启用，避免破坏访问）。
