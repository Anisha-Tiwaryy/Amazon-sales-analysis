"""Charts for the README, plus the ERD."""
from pathlib import Path
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
CH = ROOT / "charts"
BQ = ROOT / "results" / "business_questions"
SP = ROOT / "results" / "sales_playbook"
NAVY, ORANGE, GREY = "#1F3864", "#E07B39", "#9AA5B1"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    fig.tight_layout(); fig.savefig(CH / name, dpi=130); plt.close(fig)


def read(folder, prefix):
    return pd.read_csv(next(folder.glob(f"{prefix}*.csv")))


def charts():
    CH.mkdir(exist_ok=True)
    con = sqlite3.connect(ROOT / "data" / "amazon_sales.db")
    m = pd.read_sql_query("SELECT substr(order_date,1,7) AS ym, COUNT(DISTINCT order_id) AS orders FROM orders GROUP BY ym", con)
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(pd.to_datetime(m.ym), m.orders, color=NAVY)
    ax.set_title("Orders per month"); ax.set_ylabel("orders"); save(fig, "01_orders_per_month.png")

    sc = pd.read_csv(SP / "territory_scorecard.csv")
    fig, ax = plt.subplots(figsize=(7, 3.4))
    x = range(len(sc)); w = 0.38
    ax.bar([i - w / 2 for i in x], sc.revenue_prior_12m / 1e3, w, color=GREY, label="Prior 12 months")
    ax.bar([i + w / 2 for i in x], sc.revenue_last_12m / 1e3, w, color=NAVY, label="Last 12 months")
    ax.set_xticks(list(x), sc.territory); ax.set_ylabel("revenue ($k)"); ax.legend(frameon=False)
    ax.set_title("Revenue by territory"); save(fig, "02_revenue_by_territory.png")

    q5 = read(BQ, "q5").sort_values("total_profit")
    fig, ax = plt.subplots(figsize=(7, 4.6))
    ax.barh(q5.sub_category, q5.total_profit / 1e3, color=[ORANGE if v < 0 else NAVY for v in q5.total_profit])
    ax.set_xlabel("profit ($k)"); ax.set_title("Profit by sub-category"); save(fig, "03_profit_by_subcategory.png")

    q8 = read(BQ, "q8")
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.bar(q8.discount_band, q8.weighted_margin_pct, color=[NAVY if v >= 0 else ORANGE for v in q8.weighted_margin_pct])
    ax.axhline(0, color="black", lw=0.8); ax.set_ylabel("profit margin %"); ax.set_xlabel("discount")
    ax.set_title("Margin falls below zero once discounts pass 20%"); save(fig, "04_margin_by_discount.png")

    q6 = read(BQ, "q6").sort_values("orders")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(q6.state, q6.orders, color=NAVY); ax.set_xlabel("orders"); ax.set_title("Top 10 states by orders")
    save(fig, "05_top_states.png")

    q7 = read(BQ, "q7").sort_values("month")
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(q7.month, q7.orders, color=[ORANGE if mo in (9, 11, 12) else NAVY for mo in q7.month])
    ax.set_xticks(range(1, 13)); ax.set_xlabel("month"); ax.set_ylabel("orders"); ax.set_title("Orders by month (all years)")
    save(fig, "06_orders_by_month.png")

    bt = pd.read_csv(SP / "qualification_backtest.csv")
    base = pd.read_csv(SP / "qualification_summary.csv").baseline_bought_pct[0]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.bar(bt.tier, bt.bought_next_6m_pct, color=[NAVY, NAVY, ORANGE, GREY])
    ax.axhline(base, color="black", ls="--", lw=1); ax.text(3.45, base + 1.5, f"all accounts {base}%", ha="right")
    ax.set_ylabel("% that ordered in next 6 months"); ax.set_title("Back-test: account tier vs real buying (Jul-Dec 2017)")
    save(fig, "07_tier_backtest.png")

    ret = read(BQ, "q10")
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    ax.bar(ret.category, ret.return_pct, color=NAVY); ax.set_ylabel("return %"); ax.set_title("Top two categories by returns")
    save(fig, "08_returns.png")
    con.close()


def erd():
    tables = {
        "customers": (0.05, 0.55, ["customer_id  PK", "customer_name", "segment", "city", "state", "postal_code", "region"]),
        "orders": (0.38, 0.30, ["row_id  PK", "order_id", "order_date", "ship_date", "ship_mode", "customer_id  FK",
                                "product_id  FK", "sales", "quantity", "discount", "profit"]),
        "products": (0.72, 0.35, ["product_id  PK", "category", "sub_category", "product_name"]),
        "returns": (0.72, 0.75, ["order_id  (joins orders)", "returned"]),
    }
    fig, ax = plt.subplots(figsize=(10, 6.2)); ax.axis("off")
    rowy = {}
    for name, (x, y, cols) in tables.items():
        h = 0.05 * (len(cols) + 1)
        ax.add_patch(FancyBboxPatch((x, y), 0.24, h, boxstyle="round,pad=0.01", fc="white", ec=NAVY, lw=1.5))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.05), 0.24, 0.05, boxstyle="round,pad=0.01", fc=NAVY, ec=NAVY))
        ax.text(x + 0.12, y + h - 0.025, name, color="white", ha="center", va="center", weight="bold")
        for i, c in enumerate(cols):
            yy = y + h - 0.075 - 0.05 * i
            ax.text(x + 0.01, yy, c, va="center", fontsize=9)
            rowy[(name, c.split()[0])] = yy
    line = dict(color=ORANGE, lw=1.6)
    # customers.customer_id -> orders.customer_id
    y1, y2 = rowy[("customers", "customer_id")], rowy[("orders", "customer_id")]
    ax.plot([0.30, 0.335, 0.335, 0.37], [y1, y1, y2, y2], **line); ax.text(0.30, y1 + 0.02, "1", color=ORANGE)
    ax.text(0.345, y2 + 0.015, "many", color=ORANGE, fontsize=8)
    # products.product_id -> orders.product_id
    y1, y2 = rowy[("products", "product_id")], rowy[("orders", "product_id")]
    ax.plot([0.71, 0.67, 0.67, 0.63], [y1, y1, y2, y2], **line); ax.text(0.695, y1 + 0.015, "1", color=ORANGE)
    ax.text(0.635, y2 + 0.015, "many", color=ORANGE, fontsize=8)
    # returns.order_id -> orders.order_id
    y1, y2 = rowy[("returns", "order_id")], rowy[("orders", "order_id")]
    ax.plot([0.71, 0.67, 0.67, 0.63], [y1, y1, y2, y2], **line); ax.text(0.645, y2 + 0.015, "order_id", color=ORANGE, fontsize=8)
    ax.set_xlim(0, 1); ax.set_ylim(0.25, 0.97); ax.set_title("Entity-Relationship Diagram", weight="bold")
    save(fig, "erd.png")


if __name__ == "__main__":
    charts(); erd(); print("charts done")
