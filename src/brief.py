"""Write a one-page sales brief for the team from the latest results."""
from pathlib import Path
import calendar
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BQ, SP = ROOT / "results" / "business_questions", ROOT / "results" / "sales_playbook"


def read(folder, prefix):
    return pd.read_csv(next(folder.glob(f"{prefix}*.csv")))


def build():
    sc = pd.read_csv(SP / "territory_scorecard.csv")
    sc["growth_pct"] = (100 * (sc.revenue_last_12m / sc.revenue_prior_12m - 1)).round(1)
    bt = pd.read_csv(SP / "qualification_backtest.csv").set_index("tier")
    sm = pd.read_csv(SP / "qualification_summary.csv").iloc[0]
    rec = pd.read_csv(SP / "recommendation_backtest.csv").iloc[0]
    ws = pd.read_csv(SP / "state_whitespace.csv").head(3)
    win = pd.read_csv(SP / "territory_call_windows.csv")
    plan = pd.read_csv(SP / "account_plan.csv")
    q8 = read(BQ, "q8").set_index("discount_band")
    q5 = read(BQ, "q5")
    q7 = read(BQ, "q7")
    losers = q5[q5.total_profit < 0].sub_category.tolist()
    fastest = sc.loc[sc.growth_pct.idxmax()]; slowest = sc.loc[sc.growth_pct.idxmin()]
    hot = plan[plan.tier == "Hot"].head(5)
    hw = bt.loc[["Hot", "Warm"]]
    lines = [
        "# Weekly sales brief", "",
        "_Generated from the latest data by `src/brief.py`. All data in this project is simulated._", "",
        "## 1. Territories",
        f"- **Fastest growing:** {fastest.territory} ({fastest.growth_pct:+.1f}% revenue, last 12 months vs prior 12).",
        f"- **Slowest:** {slowest.territory} ({slowest.growth_pct:+.1f}%).",
        f"- **Under-penetrated states** (revenue per account vs their territory average): "
        + ", ".join(f"{r.state} ({r.index_vs_territory:.0f}%)" for r in ws.itertuples()) + ".",
        "", "## 2. Who to call first",
        f"- Hot and Warm accounts are {int(hw.accounts.sum())} of {int(bt.accounts.sum())} accounts but brought "
        f"{hw.share_of_next_6m_revenue.sum():.1f}% of the next six months' revenue in the back-test.",
        f"- {bt.loc['Hot', 'bought_next_6m_pct']}% of Hot accounts ordered again within six months, against "
        f"{sm.baseline_bought_pct}% of all accounts.",
        f"- Top five Hot accounts this week: " + "; ".join(f"{r.customer_name} ({r.territory}, buys {r.current_needs.split(',')[0]})"
                                                         for r in hot.itertuples()) + ".",
        "", "## 3. What to pitch",
        f"- Suggesting the two categories that similar accounts buy and this account does not hit "
        f"{rec.recommended_pick_hit_pct}% of the time, against {rec.random_pick_hit_pct}% for a random pick ({rec.lift}x).",
        f"- **Avoid leading with deep discounts:** lines with 21-40% off ran a {q8.loc['21-40%', 'weighted_margin_pct']}% margin, "
        f"and 41%+ ran {q8.loc['41%+', 'weighted_margin_pct']}%." + (f" {', '.join(losers)} lose money overall." if losers else ""),
        f"- **Timing:** the busiest months are {', '.join(calendar.month_name[m] for m in q7.month.head(3))}, so start outreach a month before.",
        "", "## 4. Calling windows (10 AM-5 PM local)",
    ] + [f"- {r.territory}: {r.call_window}; best shift: {r.best_shift}." for r in win.itertuples()] + [
        "", "## 5. Feedback for the team",
        f"- {int((plan.tier == 'Win-back').sum())} high-spend accounts have gone quiet. They need a different first message "
        "(ask what changed) rather than the standard pitch.",
        "- West accounts can only be called for part of their day from either US shift, so lean more on email and LinkedIn there.",
    ]
    out = ROOT / "reports"; out.mkdir(exist_ok=True)
    (out / "sales_brief.md").write_text("\n".join(lines) + "\n")
    return out / "sales_brief.md"


if __name__ == "__main__":
    print(build().read_text())
