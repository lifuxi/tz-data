-- ============================================================
-- IV Benchmark & Smile Snapshot Tables
-- ============================================================

-- Daily IV benchmark derivatives (ATM IV, HV, skew, term structure, percentile)
CREATE TABLE IF NOT EXISTS iv_benchmark (
    trade_date       TEXT NOT NULL,    -- YYYY-MM-DD
    variety          TEXT NOT NULL,    -- MO / IO / HO
    atm_iv           REAL,
    atm_strike       REAL,
    spot_price       REAL,
    hv_20            REAL,
    hv_60            REAL,
    iv_hv_spread     REAL,
    skew_25delta     REAL,
    term_structure   TEXT,             -- JSON: {"1M": 18.5, "2M": 19.2, ...}
    iv_percentile_1y REAL,
    iv_regime        TEXT,             -- very_low / low / normal / high / very_high
    pcr_volume       REAL,
    pcr_oi           REAL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, variety)
);

CREATE INDEX IF NOT EXISTS idx_iv_benchmark_date ON iv_benchmark(trade_date);
CREATE INDEX IF NOT EXISTS idx_iv_benchmark_variety ON iv_benchmark(variety);

-- IV smile curve snapshots per expiry
CREATE TABLE IF NOT EXISTS iv_smile_snapshot (
    trade_date   TEXT NOT NULL,       -- YYYY-MM-DD
    variety      TEXT NOT NULL,       -- MO / IO / HO
    expiry_date  TEXT NOT NULL,       -- YYYY-MM-DD
    smile_data   TEXT,                -- JSON: {"strikes": [...], "call_iv": [...], "put_iv": [...]}
    atm_iv       REAL,
    skew_ratio   REAL,                -- OTM Put IV / OTM Call IV
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, variety, expiry_date)
);

CREATE INDEX IF NOT EXISTS idx_iv_smile_date ON iv_smile_snapshot(trade_date);
CREATE INDEX IF NOT EXISTS idx_iv_smile_variety ON iv_smile_snapshot(variety);
