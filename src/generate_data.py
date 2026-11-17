"""Generate a synthetic Amazon-style sales dataset (Superstore-like schema).

The data is simulated so every result can be reproduced and checked. It mirrors
the structure of the public Kaggle Amazon/Superstore sales data: order lines
with customer, product hierarchy, discount, sales and profit, plus a returns
file. A handful of data quality problems are planted on purpose so the
cleaning step has real work to do.

Output: data/raw/amazon_sales_raw.csv and data/raw/returns.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
TARGET_ROWS = 9_994
N_CUSTOMERS = 793
START, END = pd.Timestamp("2014-01-01"), pd.Timestamp("2017-12-30")
ROOT = Path(__file__).resolve().parents[1]

REGION_STATES = {
    "West": ["California", "Washington", "Oregon", "Arizona", "Colorado", "Utah", "Nevada",
             "New Mexico", "Idaho", "Montana", "Wyoming"],
    "East": ["New York", "Pennsylvania", "Ohio", "Massachusetts", "New Jersey", "Delaware",
             "Connecticut", "Maryland", "Rhode Island", "New Hampshire", "Vermont", "Maine",
             "District of Columbia", "West Virginia"],
    "Central": ["Texas", "Illinois", "Michigan", "Indiana", "Wisconsin", "Minnesota", "Missouri",
                "Oklahoma", "Iowa", "Nebraska", "Kansas", "South Dakota", "North Dakota"],
    "South": ["Florida", "Virginia", "North Carolina", "Georgia", "Tennessee", "Kentucky",
              "Alabama", "Mississippi", "Louisiana", "Arkansas", "South Carolina"],
}
BIG_STATES = {"California": 20, "New York": 12, "Texas": 10, "Pennsylvania": 6, "Washington": 5,
              "Illinois": 5, "Ohio": 4, "Florida": 4, "Michigan": 2.5, "North Carolina": 2.5,
              "Virginia": 2.2, "Arizona": 2.0, "Georgia": 1.8, "Tennessee": 1.6, "Colorado": 1.5,
              "Indiana": 1.4, "Kentucky": 1.3, "Massachusetts": 1.3, "New Jersey": 1.2,
              "Oregon": 1.2, "Wisconsin": 1.1, "Delaware": 1.0, "Maryland": 1.0, "Minnesota": 1.0}
CITY = {"California": ["Los Angeles", "San Francisco", "San Diego", "Sacramento"],
        "New York": ["New York City", "Buffalo", "Rochester"], "Texas": ["Houston", "Dallas", "San Antonio", "Austin"],
        "Pennsylvania": ["Philadelphia", "Pittsburgh"], "Washington": ["Seattle", "Spokane"],
        "Illinois": ["Chicago", "Springfield"], "Ohio": ["Columbus", "Cleveland"], "Florida": ["Jacksonville", "Miami", "Tampa"]}

SUBCATS = {  # sub-category: (category, unit price range, base margin, discount propensity, weight)
    "Binders": ("Office Supplies", (3, 60), 0.30, 0.55, 15), "Paper": ("Office Supplies", (5, 40), 0.42, 0.05, 14),
    "Furnishings": ("Furniture", (8, 120), 0.17, 0.25, 9), "Phones": ("Technology", (40, 600), 0.16, 0.20, 9),
    "Storage": ("Office Supplies", (15, 250), 0.11, 0.08, 8), "Art": ("Office Supplies", (3, 40), 0.25, 0.08, 8),
    "Accessories": ("Technology", (12, 200), 0.24, 0.12, 8), "Chairs": ("Furniture", (60, 500), 0.08, 0.30, 6),
    "Appliances": ("Office Supplies", (20, 400), 0.17, 0.25, 5), "Labels": ("Office Supplies", (2, 20), 0.43, 0.03, 4),
    "Tables": ("Furniture", (120, 800), 0.02, 0.55, 3), "Envelopes": ("Office Supplies", (4, 40), 0.42, 0.05, 3),
    "Bookcases": ("Furniture", (80, 700), 0.02, 0.45, 2.3), "Fasteners": ("Office Supplies", (2, 15), 0.30, 0.05, 2.2),
    "Supplies": ("Office Supplies", (5, 120), 0.04, 0.10, 2), "Machines": ("Technology", (90, 2500), 0.08, 0.45, 1.2),
    "Copiers": ("Technology", (300, 3500), 0.37, 0.10, 0.7),
}
BRANDS = ["Avery", "Acme", "Fellowes", "Hon", "Logitech", "Samsung", "Apple", "Cisco", "Staples", "Xerox",
          "Eldon", "Bretford", "Global", "Canon", "Hewlett-Packard", "Wilson Jones", "Tenex", "Novimex"]
FIRST = ["Aaron", "Adam", "Alan", "Alice", "Amy", "Andrew", "Anna", "Ben", "Brian", "Carol", "Chris", "Claire",
         "Dan", "David", "Diana", "Emily", "Eric", "Frank", "Grace", "Greg", "Hannah", "Helen", "Ian", "Jack",
         "James", "Jane", "Jason", "Jill", "John", "Julia", "Karen", "Kevin", "Laura", "Liam", "Linda", "Maria",
         "Mark", "Matt", "Megan", "Nina", "Noah", "Olivia", "Paul", "Peter", "Rachel", "Ryan", "Sam", "Sara",
         "Sean", "Sophia", "Steve", "Tom", "Tracy", "Victor", "Wendy", "Zoe"]
LAST = ["Adams", "Baker", "Brooks", "Carter", "Clark", "Collins", "Cook", "Davis", "Evans", "Fisher", "Foster",
        "Garcia", "Gray", "Hall", "Harris", "Hill", "Hughes", "Jackson", "Kelly", "King", "Lee", "Lewis", "Martin",
        "Miller", "Moore", "Morgan", "Nelson", "Parker", "Patel", "Price", "Reed", "Roberts", "Ross", "Scott",
        "Shaw", "Smith", "Stewart", "Taylor", "Turner", "Walker", "Ward", "White", "Wood", "Young"]
SEASON = np.array([0.55, 0.50, 0.95, 0.85, 0.90, 0.90, 0.85, 0.85, 1.45, 1.10, 1.55, 1.60])


def make_customers(rng):
    states = [s for v in REGION_STATES.values() for s in v]
    region_of = {s: r for r, v in REGION_STATES.items() for s in v}
    w = np.array([BIG_STATES.get(s, 0.35) for s in states]); w /= w.sum()
    rows, used = [], set()
    for i in range(N_CUSTOMERS):
        while True:
            f, l = rng.choice(FIRST), rng.choice(LAST)
            if (f, l) not in used:
                used.add((f, l)); break
        st = states[i] if i < len(states) else rng.choice(states, p=w)
        city = rng.choice(CITY.get(st, [f"{st} City"]))
        rows.append({
            "Customer ID": f"{f[0]}{l[0]}-{10000 + 15 * i}", "Customer Name": f"{f} {l}",
            "Segment": rng.choice(["Consumer", "Corporate", "Home Office"], p=[0.52, 0.30, 0.18]),
            "City": city, "State": st, "Region": region_of[st],
            "Postal Code": str(int(rng.integers(10000, 99999))),
            # latent behaviour: how often they buy, how big, when they start and stop
            "_rate": float(rng.lognormal(np.log(2.6), 0.55)),
            "_value": float(rng.lognormal(0, 0.45)),
            "_start": START + pd.Timedelta(days=int(rng.beta(1.0, 1.5) * 1400)),
            "_churn": (START + pd.Timedelta(days=int(rng.uniform(450, 1460)))) if rng.random() < 0.28 else END,
        })
    return pd.DataFrame(rows)


def make_products(rng):
    names = list(SUBCATS)
    w = np.array([SUBCATS[s][4] for s in names]); w /= w.sum()
    rows = []
    for i in range(1_850):
        sc = rng.choice(names, p=w)
        cat = SUBCATS[sc][0]
        lo, hi = SUBCATS[sc][1]
        rows.append({"Product ID": f"{cat[:3].upper()}-{sc[:2].upper()}-{10000000 + 1013 * i}",
                     "Category": cat, "Sub-Category": sc,
                     "Product Name": f"{rng.choice(BRANDS)} {sc[:-1] if sc.endswith('s') else sc} {chr(65 + i % 26)}{100 + i % 900}",
                     "_price": float(np.exp(rng.uniform(np.log(lo), np.log(hi)))),
                     "_pop": float(rng.lognormal(0, 0.9))})
    return pd.DataFrame(rows)


def make_orders(rng, cust, prod):
    by_sub = {s: g for s, g in prod.groupby("Sub-Category")}
    sub_names = list(SUBCATS)
    base_w = np.array([SUBCATS[s][4] for s in sub_names], dtype=float)
    seg_tilt = {"Corporate": {"Copiers": 2.0, "Machines": 1.8, "Tables": 1.4, "Chairs": 1.3},
                "Home Office": {"Phones": 1.4, "Storage": 1.3}, "Consumer": {"Art": 1.3, "Furnishings": 1.2}}
    region_disc = {"West": 0.75, "East": 0.85, "Central": 1.35, "South": 1.05}
    lines, order_no = [], 100000
    years = (END - START).days / 365.0
    for _, c in cust.iterrows():
        # each customer favours a few sub-categories (their "needs")
        pref = base_w * np.array([seg_tilt.get(c.Segment, {}).get(s, 1.0) for s in sub_names])
        pref = pref * rng.gamma(0.7, 1.0, len(sub_names)); pref /= pref.sum()
        t, stop, first = c._start, max(min(c._churn, END), c._start), True
        while True:
            if not first:
                gap = rng.exponential(365.0 / (c._rate * (1 + 0.22 * (t.year - 2014))))
                t = t + pd.Timedelta(days=int(gap) + 1)
                if t > stop:
                    break
                if rng.random() > SEASON[t.month - 1] / SEASON.max():
                    continue
            first = False
            order_no += 1
            oid = f"{['CA', 'US'][order_no % 2]}-{t.year}-{order_no}"
            ship_mode = rng.choice(["Standard Class", "Second Class", "First Class", "Same Day"], p=[0.6, 0.19, 0.16, 0.05])
            ship_days = {"Standard Class": 5, "Second Class": 3, "First Class": 2, "Same Day": 0}[ship_mode]
            for _ in range(int(min(rng.geometric(0.48), 8))):
                sc = rng.choice(sub_names, p=pref)
                pr = by_sub[sc].sample(1, weights="_pop", random_state=int(rng.integers(1e9))).iloc[0]
                qty = int(min(rng.geometric(0.27), 14))
                disc = 0.0
                if rng.random() < SUBCATS[sc][3] * region_disc[c.Region]:
                    disc = float(rng.choice([0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 0.8], p=[.12, .08, .42, .1, .1, .06, .07, .05]))
                price = pr._price * c._value ** 0.35
                sales = round(price * qty * (1 - disc), 4)
                margin = float(np.clip(SUBCATS[sc][2] - 1.55 * max(disc - 0.05, 0) + rng.normal(0, 0.06), -0.95, 0.6))
                lines.append({"Order ID": oid, "Order Date": t, "Ship Date": t + pd.Timedelta(days=ship_days + int(rng.integers(0, 2))),
                              "Ship Mode": ship_mode, "Customer ID": c["Customer ID"], "Customer Name": c["Customer Name"],
                              "Segment": c.Segment, "Country": "United States", "City": c.City, "State": c.State,
                              "Postal Code": c["Postal Code"], "Region": c.Region, "Product ID": pr["Product ID"],
                              "Category": pr.Category, "Sub-Category": sc, "Product Name": pr["Product Name"],
                              "Sales": sales, "Quantity": qty, "Discount": disc, "Profit": round(sales * margin, 4)})
    df = pd.DataFrame(lines).sort_values(["Order Date", "Order ID"]).reset_index(drop=True)
    return df


def fit_to_target(rng, df):
    """Trim or pad whole order lines so the clean dataset has exactly TARGET_ROWS rows."""
    while len(df) > TARGET_ROWS:
        multi = df[df.duplicated("Order ID", keep=False)].index
        drop = rng.choice(multi, size=min(len(df) - TARGET_ROWS, len(multi) // 2), replace=False)
        df = df.drop(drop)
    assert len(df) == TARGET_ROWS, f"generated too few rows: {len(df)}"
    return df.sort_values(["Order Date", "Order ID"]).reset_index(drop=True)


def plant_problems(rng, df):
    """Plant data quality problems that the cleaning step must find and fix."""
    df = df.copy()
    df["Postal Code"] = df["Postal Code"].astype(object)
    idx = rng.choice(df.index, 45, replace=False)
    df.loc[idx[:15], "Postal Code"] = np.nan                                     # missing postal codes
    df.loc[idx[15:23], "Customer Name"] = np.nan                                 # missing customer names
    swap = idx[23:35]
    df.loc[swap, ["Order Date", "Ship Date"]] = df.loc[swap, ["Ship Date", "Order Date"]].values  # dates swapped
    df.loc[idx[35:41], "Sales"] *= -1                                            # sign errors
    df.loc[idx[41:45], "Profit"] *= 100                                          # unit errors
    dups = df.sample(30, random_state=SEED)                                      # exact duplicate rows
    df = pd.concat([df, dups]).sort_values(["Order Date", "Order ID"]).reset_index(drop=True)
    df.insert(0, "Row ID", range(1, len(df) + 1))
    for c in ("Order Date", "Ship Date"):
        df[c] = pd.to_datetime(df[c]).dt.strftime("%m/%d/%Y")
    return df


def main():
    rng = np.random.default_rng(SEED)
    cust, prod = make_customers(rng), make_products(rng)
    clean = fit_to_target(rng, make_orders(rng, cust, prod))
    orders = clean.groupby("Order ID").agg(cat=("Category", "first")).reset_index()
    p_ret = orders["cat"].map({"Furniture": 0.085, "Office Supplies": 0.075, "Technology": 0.09})
    returns = orders.loc[rng.random(len(orders)) < p_ret, ["Order ID"]].assign(Returned="Yes")
    raw = plant_problems(rng, clean)
    out = ROOT / "data" / "raw"; out.mkdir(parents=True, exist_ok=True)
    raw.to_csv(out / "amazon_sales_raw.csv", index=False)
    returns.to_csv(out / "returns.csv", index=False)
    print(f"raw rows {len(raw)}, clean target {TARGET_ROWS}, orders {clean['Order ID'].nunique()}, "
          f"customers {clean['Customer ID'].nunique()}, states {clean['State'].nunique()}, returns {len(returns)}")


if __name__ == "__main__":
    main()
