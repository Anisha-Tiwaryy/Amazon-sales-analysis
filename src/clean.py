"""Clean the raw export, log every fix, and load a normalised SQLite database."""
from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
DB = ROOT / "data" / "amazon_sales.db"


def clean(raw: pd.DataFrame):
    log, df = [], raw.copy()
    n0 = len(df)

    dup = df.drop(columns="Row ID").duplicated()
    df = df[~dup].copy()
    log.append(("Exact duplicate rows removed", int(dup.sum())))

    for c in ("Order Date", "Ship Date"):
        df[c] = pd.to_datetime(df[c], format="%m/%d/%Y")
    bad = df["Ship Date"] < df["Order Date"]
    df.loc[bad, ["Order Date", "Ship Date"]] = df.loc[bad, ["Ship Date", "Order Date"]].values
    log.append(("Ship date before order date (swapped back)", int(bad.sum())))

    neg = df["Sales"] < 0
    df.loc[neg, "Sales"] = df.loc[neg, "Sales"].abs()
    log.append(("Negative sales values (sign corrected)", int(neg.sum())))

    unit = df["Profit"].abs() > df["Sales"]
    df.loc[unit, "Profit"] = df.loc[unit, "Profit"] / 100
    log.append(("Profit larger than sales (x100 unit error corrected)", int(unit.sum())))

    for col in ("Customer Name", "Postal Code"):
        miss = df[col].isna()
        fill = df.dropna(subset=[col]).groupby("Customer ID")[col].first()
        df.loc[miss, col] = df.loc[miss, "Customer ID"].map(fill)
        log.append((f"Missing {col} (filled from the same customer's other orders)", int(miss.sum())))

    assert df["Discount"].between(0, 1).all() and (df["Quantity"] > 0).all()
    assert df[["Customer Name", "Postal Code"]].notna().all().all()
    assert not df.drop(columns="Row ID").duplicated().any()
    df["Postal Code"] = df["Postal Code"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["Row ID"] = range(1, len(df) + 1)
    return df.reset_index(drop=True), log, n0


def to_tables(df, returns):
    customers = df[["Customer ID", "Customer Name", "Segment", "City", "State", "Postal Code", "Region"]] \
        .drop_duplicates("Customer ID").sort_values("Customer ID")
    products = df[["Product ID", "Category", "Sub-Category", "Product Name"]].drop_duplicates("Product ID") \
        .sort_values("Product ID")
    orders = df[["Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode", "Customer ID", "Product ID",
                 "Sales", "Quantity", "Discount", "Profit"]].copy()
    for c in ("Order Date", "Ship Date"):
        orders[c] = orders[c].dt.strftime("%Y-%m-%d")
    ren = lambda d: d.rename(columns=lambda c: c.lower().replace(" ", "_").replace("-", "_"))
    return {"customers": ren(customers), "products": ren(products), "orders": ren(orders), "returns": ren(returns)}


def main():
    raw = pd.read_csv(RAW / "amazon_sales_raw.csv", dtype={"Postal Code": str})
    returns = pd.read_csv(RAW / "returns.csv")
    df, log, n0 = clean(raw)
    CLEAN.mkdir(parents=True, exist_ok=True)
    tables = to_tables(df, returns)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript((ROOT / "sql" / "schema.sql").read_text())
    for name, t in tables.items():
        t.to_csv(CLEAN / f"{name}.csv", index=False)
        t.to_sql(name, con, if_exists="append", index=False)
    con.commit(); con.close()
    lines = ["DATA QUALITY REPORT", "=" * 19, f"Raw rows: {n0}", ""]
    lines += [f"- {k}: {v}" for k, v in log]
    lines += ["", f"Clean rows: {len(df)}", f"Orders: {df['Order ID'].nunique()}",
              f"Customers: {df['Customer ID'].nunique()}", f"Products: {df['Product ID'].nunique()}",
              f"States: {df['State'].nunique()}", f"Date range: {df['Order Date'].min().date()} to {df['Order Date'].max().date()}",
              f"Returned orders: {len(returns)}"]
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "data_quality_report.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
