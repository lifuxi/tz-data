# 报告中心 — 数据层需求文档

> 项目：tz-data
> 关联：tz2.0 报告中心（REPORT-REQUIREMENTS.md）
> 日期：2026-05-17
> 状态：待实施

---

## 1. 背景

tz2.0 正在建设统一的"报告中心"，需要将报告的元数据、模板配置、订阅信息和访问审计持久化存储。tz-data 项目作为底层数据源（SQLite），负责提供报告中心的数据库支持。

tz2.0 通过 Python import (`tzdata_pkg`) 和 SQLite 直读访问 tz-data 的数据库，因此新增表在 tz-data 中定义，由 tz2.0 的 ORM 或原生 SQL 读写。

---

## 2. 新增表设计

### 2.1 reports — 报告元数据表

存储每份报告的基本信息，用于列表展示、筛选和管理。

```sql
CREATE TABLE reports (
    report_id       VARCHAR(50)  PRIMARY KEY,
    report_name     VARCHAR(200) NOT NULL,
    report_type     VARCHAR(50)  NOT NULL,  -- daily/weekly/monthly/quarterly/yearly/custom
    report_subtype  VARCHAR(50),             -- pnl/risk/position/behavior/volatility/comprehensive
    status          VARCHAR(20)  NOT NULL,   -- generating/success/failed/cancelled
    generation_time TIMESTAMP,
    data_date       DATE         NOT NULL,
    data_end_date   DATE,                    -- 周报/月报的结束日期
    account_id      VARCHAR(50),
    template_id     VARCHAR(50),
    file_path       VARCHAR(500),            -- 文件存储路径
    file_size       BIGINT,
    file_format     VARCHAR(20),             -- html/pdf/excel/json
    storage_location VARCHAR(50) DEFAULT 'local',  -- local/cloud
    view_count      INT          DEFAULT 0,
    download_count  INT          DEFAULT 0,
    share_count     INT          DEFAULT 0,
    visibility      VARCHAR(20)  DEFAULT 'private',  -- private/shared/public
    created_by      VARCHAR(50)  NOT NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_report_type   (report_type, data_date),
    INDEX idx_account_date  (account_id, data_date),
    INDEX idx_status_created (status, created_at),
    INDEX idx_data_date     (data_date)
);
```

### 2.2 report_contents — 报告内容存储表

存储报告的章节内容，支持大报告分段加载。

```sql
CREATE TABLE report_contents (
    content_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_id       VARCHAR(50) NOT NULL,
    section_name    VARCHAR(100),
    content_type    VARCHAR(20),            -- text/chart/table
    content_data    LONGTEXT,               -- JSON 或 HTML
    content_order   INT DEFAULT 0,

    FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE,
    INDEX idx_report_section (report_id, section_name)
);
```

### 2.3 report_templates — 报告模板表

存储报告模板定义，支持用户自定义模板。

```sql
CREATE TABLE report_templates (
    template_id     VARCHAR(50) PRIMARY KEY,
    template_name   VARCHAR(100) NOT NULL,
    template_type   VARCHAR(50)  NOT NULL,  -- daily/weekly/monthly/custom
    description     TEXT,
    config          JSON NOT NULL,          -- 模板配置 JSON
    version         INT DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      VARCHAR(50) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_template_type (template_type, is_active)
);
```

### 2.4 report_subscriptions — 报告订阅表

用户订阅的报告类型、频率和分发渠道。

```sql
CREATE TABLE report_subscriptions (
    subscription_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(50) NOT NULL,
    template_id     VARCHAR(50) NOT NULL,
    frequency       VARCHAR(20) NOT NULL,   -- daily/weekly/monthly/quarterly
    delivery_time   VARCHAR(20),            -- '08:00'
    delivery_format VARCHAR(20) DEFAULT 'html',
    delivery_channels JSON,                 -- ['email', 'web', 'im']
    conditions      JSON,                   -- 条件过滤（如盈亏阈值）
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_user_template (user_id, template_id, frequency),
    INDEX idx_user_active (user_id, is_active)
);
```

### 2.5 report_access_logs — 报告访问日志表

审计用户对报告的操作。

```sql
CREATE TABLE report_access_logs (
    log_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_id       VARCHAR(50) NOT NULL,
    user_id         VARCHAR(50) NOT NULL,
    action          VARCHAR(20) NOT NULL,   -- view/download/share/delete
    access_time     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address      VARCHAR(50),
    user_agent      TEXT,

    FOREIGN KEY (report_id) REFERENCES reports(report_id) ON DELETE CASCADE,
    INDEX idx_report_access (report_id, access_time),
    INDEX idx_user_access (user_id, access_time)
);
```

---

## 3. 实施步骤

### 3.1 数据库迁移

在 tz-data 项目中创建迁移脚本，执行上述 5 张表的 CREATE TABLE 语句。

建议位置：`src/tzdata_pkg/migrations/add_report_tables.sql`

### 3.2 SQLAlchemy Model

在 tz-data 的 `src/tzdata_pkg/models/` 目录下新增对应的 SQLAlchemy ORM model：

- `models/report.py` — Report model
- `models/report_content.py` — ReportContent model
- `models/report_template.py` — ReportTemplate model
- `models/report_subscription.py` — ReportSubscription model
- `models/report_access_log.py` — ReportAccessLog model

### 3.3 依赖关系

```
tz-data (数据层)
  ├── SQLite 表：reports, report_contents, report_templates,
  │               report_subscriptions, report_access_logs
  └── SQLAlchemy Models

tz2.0 (服务层)
  ├── 通过 tzdata_pkg import 访问 model
  ├── 或 SQLite 直读访问
  └── report_service.py 读写报告元数据
```

---

## 4. 与现有表的关系

| 新增表 | 关联现有表 | 关联字段 |
|--------|-----------|---------|
| reports | bills | data_date → 账单日期 |
| reports | trades | account_id → 交易账户 |
| reports | backtest_runs | report_subtype='backtest' 时关联 |
| report_subscriptions | users | user_id → 用户 |
| report_access_logs | users | user_id → 用户 |

---

## 5. 存储策略

- **报告文件**：存储在 `reports/` 目录（本地），大文件可迁移到对象存储
- **SQLite 数据库**：`tzdata_trading.db`（报告元数据与交易数据同库）
- **保留期限**：系统保留所有报告至少 2 年，超过 2 年的可自动归档
- **归档机制**：定期将旧报告的 content_data 迁移到冷存储，仅保留元数据
