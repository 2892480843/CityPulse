# 官方开放数据快照

## admin_divisions_cn.csv（行政区划 · 地级）

- **来源**：`Administrative-divisions-of-China`（github.com/modood/Administrative-divisions-of-China），数据派生自民政部《中华人民共和国行政区划代码》公开发布。
- **快照时间**：2026-08-16 拉取，后续以 `data_sources` 表配置的更新计划重新同步。
- **派生规则**：取省/直辖市下二级（地级市、自治州、盟、直辖市本级）；直辖市合并为单行（如 110100 北京市）；编码统一为 6 位地级码（`XXXX00`）；名称去除行政后缀"市"。共 338 个地级单位。
- **用途**：`data_source` 同步器将本快照幂等导入 `cities` 城市目录；县级市（如 222401 延吉）仍由种子数据单独维护。
