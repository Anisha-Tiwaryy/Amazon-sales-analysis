"""Turn the sales data into a territory and account outreach playbook.

1. Territory scorecard and state whitespace (SQL).
2. Account qualification: score every account Hot / Warm / Win-back / Nurture
   from recency, frequency and spend, then back-test it: score on data up to
   30 Jun 2017 and check who actually bought in Jul-Dec 2017.
3. Needs identification: each account's top sub-categories, plus two
   recommended sub-categories that similar accounts buy and this one does not.
   Back-tested the same way against a random-pick baseline.
4. A multi-channel outreach cadence per tier (call, email, LinkedIn, Zoom demo),
   with each territory's calling window converted to IST and matched to a shift.
"""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "amazon_sales.db"
OUT = ROOT / "results" / "sales_playbook"
BACKTEST_CUTOFF, HOLDOUT_END = "2017-06-30", "2017-12-30"
LIVE_CUTOFF, PLAN_START = "2017-12-30", pd.Timestamp("2018-01-02")

# Calling window 10:00-17:00 local, converted to IST (US standard time, no DST)
TERRITORY_TZ = {"East": ("ET", -5.0), "South": ("ET", -5.0), "Central": ("CT", -6.0), "West": ("PT", -8.0)}
SHIFTS = {"US East Coast (4:00 PM-2:00 AM IST)": (16.0, 26.0),
          "US West Coast (6:00 PM-4:00 AM IST)": (18.0, 28.0)}

CADENCE = {  # tier: [(day, channel, purpose)]
    "Hot": [(1, "Call", "Discovery call: confirm current needs and buying timeline"),
            (1, "Email", "Recap call, share needs-based product suggestions"),
            (3, "LinkedIn", "Connect with a short personalised note"),
            (5, "Call", "Follow-up call: answer questions, qualify budget"),
            (7, "Zoom demo", "Book a 20-minute product demo on Zoom")],
    "Warm": [(1, "Email", "Personalised email built on their top categories"),
             (3, "Call", "Call to identify needs and pain points"),
             (6, "LinkedIn", "Connect and share a relevant case study"),
             (10, "Email", "Invite to a Zoom demo")],
    "Win-back": [(1, "Email", "Check-in: ask what changed since their last order"),
                 (4, "Call", "Call to understand why they paused"),
                 (8, "LinkedIn", "Connect with a relevant update"),
                 (14, "Email", "Tailored offer on categories they used to buy")],
    "Nurture": [(1, "Email", "Introductory value email"),
                (14, "Email", "Share a customer story from their segment"),
                (30, "LinkedIn", "Light-touch connection request")],
}


def q(con, name, cutoff):
    sql = (ROOT / "sql" / "sales_playbook.sql").read_text()
    block = sql.split(f"-- {name}:")[1].split("\n-- P")[0]
    block = block.split("\n", 1)[1]
    return pd.read_sql_query(block, con, params={"cutoff": cutoff})


def tier(row):
    r, fm = row.r_score, row.f_score + row.m_score
    if r >= 4 and fm >= 7:
        return "Hot"
    if r >= 3 and fm >= 5:
        return "Warm"
    if r <= 2 and row.m_score >= 4:
        return "Win-back"
    return "Nurture"


def qualify(con, cutoff):
    acc = q(con, "P3", cutoff)
    acc["tier"] = acc.apply(tier, axis=1)
    acc["score"] = (0.45 * acc.r_score + 0.30 * acc.f_score + 0.25 * acc.m_score).round(2)
    return acc


def subcat_matrix(con, start, end):
    df = pd.read_sql_query(
        "SELECT o.customer_id, p.sub_category, SUM(o.sales) AS sales FROM orders o JOIN products p USING (product_id) "
        "WHERE o.order_date > :s AND o.order_date <= :e GROUP BY 1, 2", con, params={"s": start, "e": end})
    return df.pivot_table(index="customer_id", columns="sub_category", values="sales", fill_value=0)


def recommend(acc, bought):
    """Two sub-categories most bought by same-segment peers that this account has not bought."""
    seg = acc.set_index("customer_id")["segment"]
    has = (bought > 0).reindex(acc.customer_id, fill_value=False)
    peer_rate = has.groupby(seg.reindex(has.index)).mean()
    needs, recs = {}, {}
    for cid in has.index:
        row = bought.loc[cid] if cid in bought.index else pd.Series(dtype=float)
        needs[cid] = ", ".join(row[row > 0].sort_values(ascending=False).index[:3])
        rate = peer_rate.loc[seg[cid]].copy()
        rate = rate[~has.loc[cid]]
        recs[cid] = list(rate.sort_values(ascending=False).index[:2])
    return needs, recs, has


def backtest(con):
    acc = qualify(con, BACKTEST_CUTOFF)
    fut = pd.read_sql_query(
        "SELECT customer_id, COUNT(DISTINCT order_id) AS future_orders, SUM(sales) AS future_sales FROM orders "
        "WHERE order_date > :c AND order_date <= :e GROUP BY customer_id", con,
        params={"c": BACKTEST_CUTOFF, "e": HOLDOUT_END})
    acc = acc.merge(fut, on="customer_id", how="left").fillna({"future_orders": 0, "future_sales": 0})
    acc["bought"] = acc.future_orders > 0
    base = acc.bought.mean()
    order = ["Hot", "Warm", "Win-back", "Nurture"]
    bt = acc.groupby("tier").agg(accounts=("customer_id", "count"), bought_next_6m_pct=("bought", "mean"),
                                 avg_revenue_next_6m=("future_sales", "mean"),
                                 share_of_next_6m_revenue=("future_sales", "sum")).reindex(order)
    bt["bought_next_6m_pct"] = (100 * bt.bought_next_6m_pct).round(1)
    bt["lift_vs_all_accounts"] = (bt.bought_next_6m_pct / (100 * base)).round(2)
    bt["share_of_next_6m_revenue"] = (100 * bt.share_of_next_6m_revenue / acc.future_sales.sum()).round(1)
    bt["avg_revenue_next_6m"] = bt.avg_revenue_next_6m.round(0)
    # top 20% of accounts by score vs everyone
    top = acc.nlargest(int(0.2 * len(acc)), "score")
    summary = {"accounts_scored": len(acc), "baseline_bought_pct": round(100 * base, 1),
               "top20_bought_pct": round(100 * top.bought.mean(), 1),
               "top20_share_of_revenue_pct": round(100 * top.future_sales.sum() / acc.future_sales.sum(), 1)}

    # needs-based recommendation back-test
    past = subcat_matrix(con, "2000-01-01", BACKTEST_CUTOFF)
    future = subcat_matrix(con, BACKTEST_CUTOFF, HOLDOUT_END)
    _, recs, has = recommend(acc, past)
    rng = np.random.default_rng(7)
    hit = rand_hit = n = 0
    for cid in future.index.intersection(has.index):
        new = set(future.columns[(future.loc[cid] > 0).values]) - set(has.columns[has.loc[cid].values])
        unbought = list(has.columns[~has.loc[cid].values])
        if len(unbought) < 2:
            continue
        n += 1
        hit += bool(new & set(recs[cid]))
        rand_hit += bool(new & set(rng.choice(unbought, 2, replace=False)))
    rec_bt = pd.DataFrame([{"accounts_who_ordered_again": n,
                            "recommended_pick_hit_pct": round(100 * hit / n, 1),
                            "random_pick_hit_pct": round(100 * rand_hit / n, 1),
                            "lift": round(hit / max(rand_hit, 1), 2)}])
    return bt.reset_index(), summary, rec_bt


def ist_window(territory):
    """Return the IST call window, the best-covering shift, and hours of overlap with each shift."""
    tz, off = TERRITORY_TZ[territory]
    start = (10 - off + 5.5) % 24
    if start < 12:
        start += 24
    fmt = lambda h: f"{int(h % 24):02d}:{int(round((h % 1) * 60)):02d}"
    overlaps = {n: round(max(0, min(b, start + 7) - max(a, start)), 1) for n, (a, b) in SHIFTS.items()}
    best = max(overlaps, key=overlaps.get)
    return f"10:00-17:00 {tz} = {fmt(start)}-{fmt(start + 7)} IST", best, overlaps


def account_plan(con):
    acc = qualify(con, LIVE_CUTOFF)
    bought = subcat_matrix(con, "2000-01-01", LIVE_CUTOFF)
    needs, recs, _ = recommend(acc, bought)
    acc["current_needs"] = acc.customer_id.map(needs)
    acc["recommended_next"] = acc.customer_id.map(lambda c: ", ".join(recs[c]))
    win = {t: ist_window(t) for t in TERRITORY_TZ}
    acc["call_window"] = acc.territory.map(lambda t: win[t][0])
    acc["covering_shift"] = acc.territory.map(lambda t: win[t][1])
    acc["first_touch"] = acc.tier.map(lambda t: CADENCE[t][0][1])
    order = {"Hot": 0, "Warm": 1, "Win-back": 2, "Nurture": 3}
    acc = acc.sort_values(["tier", "score", "sales_24m"], key=lambda s: s.map(order) if s.name == "tier" else s,
                          ascending=[True, False, False]).reset_index(drop=True)
    acc.insert(0, "priority", range(1, len(acc) + 1))
    touches = []
    for _, a in acc[acc.tier != "Nurture"].iterrows():
        for step, (day, ch, purpose) in enumerate(CADENCE[a.tier], 1):
            touches.append({"customer_id": a.customer_id, "customer_name": a.customer_name, "territory": a.territory,
                            "tier": a.tier, "step": step, "channel": ch,
                            "due_date": (PLAN_START + pd.Timedelta(days=day - 1)).date(),
                            "purpose": purpose, "talking_points": f"Buys: {a.current_needs}. Suggest: {a.recommended_next}"})
    windows = pd.DataFrame([{"territory": t, "call_window": w[0], "best_shift": w[1],
                             "hours_in_east_coast_shift": w[2]["US East Coast (4:00 PM-2:00 AM IST)"],
                             "hours_in_west_coast_shift": w[2]["US West Coast (6:00 PM-4:00 AM IST)"]}
                            for t, w in win.items()])
    return acc, pd.DataFrame(touches), windows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    q(con, "P1", LIVE_CUTOFF).to_csv(OUT / "territory_scorecard.csv", index=False)
    q(con, "P2", LIVE_CUTOFF).to_csv(OUT / "state_whitespace.csv", index=False)
    bt, summary, rec_bt = backtest(con)
    bt.to_csv(OUT / "qualification_backtest.csv", index=False)
    pd.DataFrame([summary]).to_csv(OUT / "qualification_summary.csv", index=False)
    rec_bt.to_csv(OUT / "recommendation_backtest.csv", index=False)
    plan, touches, windows = account_plan(con)
    plan.to_csv(OUT / "account_plan.csv", index=False)
    touches.to_csv(OUT / "outreach_cadence.csv", index=False)
    windows.to_csv(OUT / "territory_call_windows.csv", index=False)
    con.close()
    pd.set_option("display.width", 200)
    for f in ["territory_scorecard", "qualification_backtest", "qualification_summary", "recommendation_backtest",
              "territory_call_windows"]:
        print(f"\n{f}\n", pd.read_csv(OUT / f"{f}.csv").to_string(index=False))
    print("\nplan tiers:", plan.tier.value_counts().to_dict(), "touches:", len(touches))


if __name__ == "__main__":
    main()
