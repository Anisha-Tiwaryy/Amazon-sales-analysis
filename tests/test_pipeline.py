import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import generate_data, clean, run_analysis, playbook, tracker  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def built():
    generate_data.main(); clean.main(); playbook.main(); tracker.build()


@pytest.fixture
def con():
    c = sqlite3.connect(ROOT / "data" / "amazon_sales.db"); yield c; c.close()


def test_cleaning_finds_every_planted_problem():
    raw = pd.read_csv(ROOT / "data" / "raw" / "amazon_sales_raw.csv", dtype={"Postal Code": str})
    df, log, _ = clean.clean(raw)
    found = dict(log)
    assert len(df) == 9994
    assert found["Exact duplicate rows removed"] == 30
    assert found["Ship date before order date (swapped back)"] == 12
    assert found["Negative sales values (sign corrected)"] == 6
    assert found["Profit larger than sales (x100 unit error corrected)"] == 4
    assert (df["Ship Date"] >= df["Order Date"]).all()
    assert (df["Sales"] > 0).all() and (df["Profit"].abs() <= df["Sales"]).all()


def test_database_shape(con):
    n = dict(con.execute("SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'customers', COUNT(*) FROM customers "
                         "UNION ALL SELECT 'states', COUNT(DISTINCT state) FROM customers").fetchall())
    assert n == {"orders": 9994, "customers": 793, "states": 49}
    orphans = con.execute("SELECT COUNT(*) FROM orders o LEFT JOIN products p USING (product_id) "
                          "WHERE p.product_id IS NULL").fetchone()[0]
    assert orphans == 0


def test_all_ten_questions_run(tmp_path):
    res = run_analysis.run_file(ROOT / "sql" / "analysis.sql", tmp_path, "Q")
    assert sorted(res, key=lambda k: int(k[1:])) == [f"Q{i}" for i in range(1, 11)]
    assert all(len(df) > 0 for _, df in res.values())
    assert len(res["Q1"][1]) == 5 and len(res["Q3"][1]) == 5 and len(res["Q10"][1]) == 2
    assert (res["Q4"][1]["change"] < 0).all()
    assert abs(res["Q9"][1]["contribution_pct"].sum() - 100) < 0.1


def test_scoring_never_sees_the_future(con):
    acc = playbook.qualify(con, playbook.BACKTEST_CUTOFF)
    assert (acc.recency_days >= 0).all()
    one = acc.iloc[0]
    expect = pd.read_sql_query(
        "SELECT SUM(sales) s FROM orders WHERE customer_id = ? AND order_date <= ? AND order_date > date(?, '-730 days')",
        con, params=(one.customer_id, playbook.BACKTEST_CUTOFF, playbook.BACKTEST_CUTOFF)).s[0] or 0
    assert one.sales_24m == pytest.approx(expect, abs=0.01)
    late = pd.read_sql_query("SELECT customer_id FROM orders GROUP BY customer_id HAVING MIN(order_date) > ?",
                             con, params=(playbook.BACKTEST_CUTOFF,))
    assert not set(late.customer_id) & set(acc.customer_id)


def test_tiers_rank_real_buying_in_the_right_order():
    bt = pd.read_csv(ROOT / "results" / "sales_playbook" / "qualification_backtest.csv").set_index("tier")
    base = pd.read_csv(ROOT / "results" / "sales_playbook" / "qualification_summary.csv").baseline_bought_pct[0]
    assert bt.loc["Hot", "bought_next_6m_pct"] > bt.loc["Warm", "bought_next_6m_pct"] > bt.loc["Nurture", "bought_next_6m_pct"]
    assert bt.loc["Hot", "bought_next_6m_pct"] > base


def test_recommendations_are_new_categories(con):
    acc = playbook.qualify(con, playbook.LIVE_CUTOFF)
    bought = playbook.subcat_matrix(con, "2000-01-01", playbook.LIVE_CUTOFF)
    _, recs, has = playbook.recommend(acc, bought)
    for cid in list(recs)[:200]:
        assert not set(recs[cid]) & set(has.columns[has.loc[cid].values])


def test_cadence_plan():
    plan = pd.read_csv(ROOT / "results" / "sales_playbook" / "account_plan.csv")
    t = pd.read_csv(ROOT / "results" / "sales_playbook" / "outreach_cadence.csv", parse_dates=["due_date"])
    assert "Nurture" not in set(t.tier)
    per = t.groupby("customer_id").size()
    tiers = plan.set_index("customer_id").tier
    assert all(per[c] == len(playbook.CADENCE[tiers[c]]) for c in per.index)
    assert (t.due_date >= playbook.PLAN_START).all()
    assert plan.priority.is_unique and plan.iloc[0].tier == "Hot"


def test_ist_call_windows():
    assert playbook.ist_window("East")[0] == "10:00-17:00 ET = 20:30-03:30 IST"
    assert playbook.ist_window("West")[0] == "10:00-17:00 PT = 23:30-06:30 IST"
    assert playbook.ist_window("East")[2]["US East Coast (4:00 PM-2:00 AM IST)"] == 5.5


def test_tracker_has_live_formulas():
    wb = load_workbook(ROOT / "results" / "outreach_tracker.xlsx")
    acc = wb["Accounts"]
    assert acc.max_row == 794
    assert str(acc["T2"].value).startswith("=IFERROR(VLOOKUP(")
    assert str(wb["Summary"]["B4"].value).startswith("=COUNTIFS(")
    assert len(acc.data_validations.dataValidation) == 1
