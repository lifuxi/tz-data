# SQLite Models Migration (Viewpoint 3)

## 目标

将 tz2.0 中的共享表定义（bills, trades, positions_summary, account_summary）
统一迁移到 tz-data 工程，消除跨项目 schema drift。

## 现状分析

tz2.0 的旧定义与 tz-data 的 canonical schema 存在以下不匹配：

| 表 | tz2.0 旧列 | tz-data 实际列 | 影响 |
|---|------------|----------------|------|
| trades | `bill_id` (FK) | `account_id`, `exchange`, `product`, `premium`... | tz-data 写入的数据无 bill_id，tz2.0 过滤 bill_id 返回空 |
| account_summary | `client_id` | `account_id` | 列名不一致，数据无法对齐 |
| account_summary | 缺少 `total_pnl`, `accumulated_pnl`, `exercise_pnl`... | 有 | tz2.0 读取不到新增字段 |
| positions_summary | `bill_id` (FK), `client_id`, `avg_buy_price`, `avg_sell_price` | `account_id`, `float_pl` | 列名+缺失双问题 |

## 迁移步骤

### Phase 1: 备份 + 对齐（已完成）

- [x] 备份旧定义到 `migrations/sqlite_models_backup/old_sqlite_models.py`
- [x] 重写 `tz2.0/src/infrastructure/db/sqlite_models.py`，对齐 tz-data schema
- [x] 保留 tz2.0 特有列（`total_records`, `parse_error` on Bill）
- [x] 添加 schema version guard（`check_schema_version()`）

### Phase 2: 验证（进行中）

- [ ] 运行 `migrations/verify_schema_alignment.py` 检查实际 DB schema
- [ ] 确认 tz2.0 启动不报错，旧代码路径仍有兼容代理
- [ ] 验证 /api/v2/ 端点返回的数据与旧 ORM 读取一致

### Phase 3: 逐步下线旧代码

- [ ] 移除 `Trade` 中 `bill_id` 的兼容代理（Phase 2 验证无使用者后）
- [ ] 移除 `PositionSummary` 中 `avg_buy_price`, `avg_sell_price` 等已废弃列
- [ ] 将 tz2.0 中仍定义共享表的地方全部替换为 `from tzdata_pkg.models import ...`

### Phase 4: 统一维护

- [ ] tz2.0 sqlite_models.py 中只保留 tz2.0 独有表：
  - `user_drawings`
  - `capital_transactions_raw`
  - `capital_transactions_classified`
  - `daily_account_snapshots`
- [ ] 所有共享表统一在 `tzdata_pkg/models/trading.py` 维护
- [ ] 添加 CI check：tz-data schema 变更时自动通知 tz2.0

## 文件清单

```
tz-data:
  src/tzdata_pkg/models/__init__.py          # 导出所有共享表
  src/tzdata_pkg/models/trading.py           # 31 张表的 SQLAlchemy Core 定义
  src/tzdata_pkg/models/version.py           # SCHEMA_VERSION = "1.0.0"
  migrations/sqlite_models_backup/           # 旧定义备份（只读参考）
    old_sqlite_models.py                     # 迁移前 tz2.0 的旧定义
    README.md                                # 本文件

tz2.0:
  src/infrastructure/db/sqlite_models.py     # 已对齐 tz-data schema（含废弃标记）
  src/clients/tzdata_api.py                  # HTTP client 替代直接 SQLite 读取
```

## 回退方案

如果新 schema 导致问题，恢复旧定义：
```bash
cp migrations/sqlite_models_backup/old_sqlite_models.py \
   C:\myspace\tz2.0\src\infrastructure\db\sqlite_models.py
```
