"""Load the seed tickets and customers into app.db (Epic 1, story 2).

Usage: uv run python load_seed.py
"""

import csv
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = REPO_ROOT / "app.db"
SEED_DIR = REPO_ROOT / "seed"

_TABLES = {
    "tickets": (
        "tickets.csv",
        "CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, customer_id TEXT, created_at TEXT, text TEXT)",
    ),
    "customers": (
        "customers.csv",
        "CREATE TABLE customers (customer_id TEXT PRIMARY KEY, name TEXT, plan TEXT, open_tickets INTEGER)",
    ),
}


def load(db_path: Path = DB_PATH, seed_dir: Path = SEED_DIR) -> dict[str, int]:
    """Rebuild both tables from the seed CSVs in one transaction; return row counts."""
    seeds = {}
    for table, (filename, _) in _TABLES.items():
        with open(seed_dir / filename, newline="") as f:
            reader = csv.DictReader(f)
            seeds[table] = (reader.fieldnames, [tuple(row[c] for c in reader.fieldnames) for row in reader])

    # Explicit BEGIN: sqlite3's implicit transactions don't cover DROP/CREATE,
    # so a failed rerun could otherwise leave a table dropped.
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        conn.execute("BEGIN")
        for table, (_, create_sql) in _TABLES.items():
            columns, rows = seeds[table]
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(create_sql)
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {table: len(rows) for table, (_, rows) in seeds.items()}


if __name__ == "__main__":
    counts = load()
    print(f"Loaded {counts['tickets']} tickets and {counts['customers']} customers into {DB_PATH.name}")
