"""Backfill account_summary from bills data.

Aggregates bills by (account_id, year, month) into one account_summary row per period.
  - total_pnl = SUM(realized_pl + mtm_pl) for the month
  - balance_b_f = first bill's balance_bf
  - balance_c_f = last bill's balance_cf
  - accumulated_pnl = running total across months
"""
import sqlite3
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "tzdata_trading.db"

logger = logging.getLogger(__name__)


def backfill_account_summary(dry_run: bool = False):
    """Backfill account_summary from bills table."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Check if already populated
    count = conn.execute("SELECT COUNT(*) FROM account_summary").fetchone()[0]
    if count > 0:
        print(f"account_summary already has {count} rows, skipping backfill")
        conn.close()
        return

    # Aggregate bills by (account_id, year, month)
    rows = conn.execute("""
        SELECT
            account_id,
            CAST(SUBSTR(bill_date_start, 1, 4) AS INTEGER) AS year,
            CAST(SUBSTR(bill_date_start, 6, 2) AS INTEGER) AS month,
            MIN(bill_date_start) AS start_date,
            MAX(bill_date_end) AS end_date,
            COUNT(*) AS bill_count,
            -- First bill's balance_bf (month opening)
            (SELECT b2.balance_bf FROM bills b2
             WHERE CAST(SUBSTR(b2.bill_date_start, 1, 4) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 1, 4) AS INTEGER)
               AND CAST(SUBSTR(b2.bill_date_start, 6, 2) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 6, 2) AS INTEGER)
               AND b2.account_id = bills.account_id
             ORDER BY b2.bill_date_start LIMIT 1) AS balance_bf,
            -- Last bill's balance_cf (month closing)
            (SELECT b2.balance_cf FROM bills b2
             WHERE CAST(SUBSTR(b2.bill_date_start, 1, 4) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 1, 4) AS INTEGER)
               AND CAST(SUBSTR(b2.bill_date_start, 6, 2) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 6, 2) AS INTEGER)
               AND b2.account_id = bills.account_id
             ORDER BY b2.bill_date_start DESC LIMIT 1) AS balance_cf,
            SUM(COALESCE(deposit_withdrawal, 0)) AS deposit_withdrawal,
            SUM(COALESCE(realized_pl, 0) + COALESCE(mtm_pl, 0)) AS total_pnl,
            SUM(COALESCE(exercise_pl, 0)) AS exercise_pnl,
            SUM(COALESCE(commission, 0)) AS commission,
            SUM(COALESCE(premium_received, 0)) AS premium_received,
            SUM(COALESCE(premium_paid, 0)) AS premium_paid,
            -- Last bill's snapshot values
            (SELECT b2.client_equity FROM bills b2
             WHERE CAST(SUBSTR(b2.bill_date_start, 1, 4) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 1, 4) AS INTEGER)
               AND CAST(SUBSTR(b2.bill_date_start, 6, 2) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 6, 2) AS INTEGER)
               AND b2.account_id = bills.account_id
             ORDER BY b2.bill_date_start DESC LIMIT 1) AS client_equity,
            (SELECT b2.fund_available FROM bills b2
             WHERE CAST(SUBSTR(b2.bill_date_start, 1, 4) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 1, 4) AS INTEGER)
               AND CAST(SUBSTR(b2.bill_date_start, 6, 2) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 6, 2) AS INTEGER)
               AND b2.account_id = bills.account_id
             ORDER BY b2.bill_date_start DESC LIMIT 1) AS fund_available,
            (SELECT b2.margin_occupied FROM bills b2
             WHERE CAST(SUBSTR(b2.bill_date_start, 1, 4) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 1, 4) AS INTEGER)
               AND CAST(SUBSTR(b2.bill_date_start, 6, 2) AS INTEGER) = CAST(SUBSTR(bills.bill_date_start, 6, 2) AS INTEGER)
               AND b2.account_id = bills.account_id
             ORDER BY b2.bill_date_start DESC LIMIT 1) AS margin_occupied
        FROM bills
        GROUP BY account_id,
                 CAST(SUBSTR(bill_date_start, 1, 4) AS INTEGER),
                 CAST(SUBSTR(bill_date_start, 6, 2) AS INTEGER)
        ORDER BY start_date
    """).fetchall()

    if not rows:
        print("No bills data to backfill")
        conn.close()
        return

    print(f"Aggregated into {len(rows)} monthly periods from bills...")

    running_pnl = 0.0
    inserts = []

    for r in rows:
        total_pnl = r["total_pnl"] or 0
        running_pnl += total_pnl
        inserts.append({
            "account_id": r["account_id"],
            "year": r["year"],
            "month": r["month"],
            "start_date": r["start_date"],
            "end_date": r["end_date"],
            "balance_b_f": r["balance_bf"] or 0,
            "balance_c_f": r["balance_cf"] or 0,
            "deposit_withdrawal": r["deposit_withdrawal"] or 0,
            "total_pnl": total_pnl,
            "accumulated_pnl": running_pnl,
            "exercise_pnl": r["exercise_pnl"] or 0,
            "commission": r["commission"] or 0,
            "client_equity": r["client_equity"] or 0,
            "margin_occupied": r["margin_occupied"] or 0,
            "fund_available": r["fund_available"] or 0,
            "premium_received": r["premium_received"] or 0,
            "premium_paid": r["premium_paid"] or 0,
            "bill_count": r["bill_count"],
        })

        if dry_run:
            print(f"  {r['year']}-{r['month']:02d}: bills={r['bill_count']}, "
                  f"pnl={total_pnl:.2f}, accum={running_pnl:.2f}, "
                  f"bal={r['balance_bf']:.2f}->{r['balance_cf']:.2f}")

    if dry_run:
        print(f"\nDry run: would insert {len(inserts)} rows")
        conn.close()
        return

    # Insert
    for r in inserts:
        conn.execute("""
            INSERT INTO account_summary
                (account_id, year, month, start_date, end_date,
                 balance_b_f, balance_c_f, deposit_withdrawal,
                 total_pnl, accumulated_pnl, exercise_pnl,
                 commission, client_equity, margin_occupied,
                 fund_available, premium_received, premium_paid)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["account_id"], r["year"], r["month"],
            r["start_date"], r["end_date"],
            r["balance_b_f"], r["balance_c_f"], r["deposit_withdrawal"],
            r["total_pnl"], r["accumulated_pnl"], r["exercise_pnl"],
            r["commission"], r["client_equity"], r["margin_occupied"],
            r["fund_available"], r["premium_received"], r["premium_paid"],
        ))

    conn.commit()

    # Verify
    count = conn.execute("SELECT COUNT(*) FROM account_summary").fetchone()[0]
    print(f"Backfilled {count} rows into account_summary")

    row = conn.execute("""
        SELECT MIN(start_date) as first, MAX(end_date) as last,
               SUM(total_pnl) as sum_pnl, MAX(accumulated_pnl) as final_accum
        FROM account_summary
    """).fetchone()
    print(f"  Period: {row['first']} to {row['last']}")
    print(f"  Total PnL: {row['sum_pnl']:.2f}")
    print(f"  Final accumulated PnL: {row['final_accum']:.2f}")

    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill account_summary from bills")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be inserted")
    args = parser.parse_args()
    backfill_account_summary(dry_run=args.dry_run)
