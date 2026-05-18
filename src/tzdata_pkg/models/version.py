"""Schema version for tzdata_pkg trading database.

tz2.0 should check this version at startup to ensure compatibility
with the shared SQLite schema.

Increment the PATCH version for non-breaking changes (new columns, new tables).
Increment the MINOR version for backward-compatible additions (new indexes).
Increment the MAJOR version for breaking changes (renamed/dropped columns).
"""

SCHEMA_VERSION = "1.0.0"
