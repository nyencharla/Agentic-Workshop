import csv
import sqlite3

import pytest

from load_seed import SEED_DIR, load


def _dump(db_path):
    with sqlite3.connect(db_path) as conn:
        return {
            table: conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("tickets", "customers")
        }


def test_loads_every_seed_row_with_matching_columns(tmp_path):
    db = tmp_path / "app.db"

    assert load(db) == {"tickets": 24, "customers": 20}

    with sqlite3.connect(db) as conn:
        for table, filename in (("tickets", "tickets.csv"), ("customers", "customers.csv")):
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            with open(SEED_DIR / filename, newline="") as f:
                assert columns == next(csv.reader(f))


def test_open_tickets_is_an_integer_and_matches_the_mcp_lookup(tmp_path):
    db = tmp_path / "app.db"
    load(db)

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT customer_id FROM tickets WHERE ticket_id = 'T-1042'").fetchone() == ("C-77",)
        assert conn.execute("SELECT plan, open_tickets FROM customers WHERE customer_id = 'C-77'").fetchone() == ("Enterprise", 2)


def test_second_run_leaves_identical_contents(tmp_path):
    db = tmp_path / "app.db"
    load(db)
    first = _dump(db)

    assert load(db) == {"tickets": 24, "customers": 20}
    assert _dump(db) == first


def test_failed_rerun_leaves_previous_contents_intact(tmp_path):
    db = tmp_path / "app.db"
    load(db)
    before = _dump(db)
    broken_seed = tmp_path / "seed"
    broken_seed.mkdir()
    (broken_seed / "tickets.csv").write_text((SEED_DIR / "tickets.csv").read_text())
    (broken_seed / "customers.csv").write_text("customer_id,name,plan,open_tickets\nC-1,Dup,Starter,0\nC-1,Dup,Starter,0\n")

    with pytest.raises(sqlite3.IntegrityError):
        load(db, broken_seed)

    assert _dump(db) == before
