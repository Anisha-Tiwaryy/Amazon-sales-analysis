"""Run every "-- Q<n>: title" block in a .sql file and save each result as CSV."""
from pathlib import Path
import re
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "amazon_sales.db"


def split_queries(sql_text: str, prefix: str = "Q"):
    """Return [(key, title, sql)] for blocks headed '-- <prefix><n>: title'."""
    parts = re.split(rf"^-- ({prefix}\d+): (.*)$", sql_text, flags=re.M)
    return [(parts[i], parts[i + 1].strip(), parts[i + 2].strip()) for i in range(1, len(parts), 3)]


def run_file(sql_path: Path, out_dir: Path, prefix: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    results = {}
    for key, title, sql in split_queries(sql_path.read_text(), prefix):
        df = pd.read_sql_query(sql, con)
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50]
        df.to_csv(out_dir / f"{key.lower()}_{slug}.csv", index=False)
        results[key] = (title, df)
    con.close()
    return results


def main():
    res = run_file(ROOT / "sql" / "analysis.sql", ROOT / "results" / "business_questions", "Q")
    for key, (title, df) in res.items():
        print(f"\n{key}: {title}\n{df.head(10).to_string(index=False)}")


if __name__ == "__main__":
    main()
