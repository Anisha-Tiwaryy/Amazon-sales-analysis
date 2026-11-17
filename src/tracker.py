"""Build an Excel outreach tracker with live formulas from the account plan."""
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

import playbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "outreach_tracker.xlsx"
HEAD = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F3864")
INPUT = PatternFill("solid", fgColor="FFF2CC")
STATUSES = ["Not started", "In progress", "Demo booked", "Qualified", "Not interested"]


def header(ws, cols, widths):
    ws.append(cols)
    for i, w in enumerate(widths, 1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill, c.alignment = HEAD, FILL, Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def build():
    plan = pd.read_csv(ROOT / "results" / "sales_playbook" / "account_plan.csv")
    wb = Workbook()

    cad = wb.active; cad.title = "Cadence"
    header(cad, ["Key", "Tier", "Step", "Day", "Channel", "Purpose"], [14, 10, 6, 6, 12, 60])
    for t, steps in playbook.CADENCE.items():
        for i, (day, ch, purpose) in enumerate(steps, 1):
            cad.append([f"{t}|{i}", t, i, day, ch, purpose])

    acc = wb.create_sheet("Accounts")
    cols = ["Priority", "Customer ID", "Customer", "Segment", "Territory", "State", "Tier", "Score", "Days Since Order",
            "Orders (24m)", "Sales (24m)", "Buys Most", "Suggest Next", "Call Window", "Best Shift",
            "Steps Done", "Last Touch Date", "Status", "Next Step", "Next Channel", "Next Touch Date"]
    header(acc, cols, [8, 11, 18, 12, 10, 14, 9, 7, 9, 8, 11, 34, 26, 32, 30, 8, 12, 14, 7, 12, 13])
    for r, a in enumerate(plan.itertuples(), 2):
        acc.append([a.priority, a.customer_id, a.customer_name, a.segment, a.territory, a.state, a.tier, a.score,
                    a.recency_days, a.orders_24m, a.sales_24m, a.current_needs, a.recommended_next, a.call_window,
                    a.covering_shift, 0, None, "Not started",
                    f"=P{r}+1",
                    f'=IFERROR(VLOOKUP(G{r}&"|"&S{r},Cadence!$A:$E,5,FALSE),"Cadence complete")',
                    f'=IFERROR(IF(Q{r}="",DATE(2018,1,2)+VLOOKUP(G{r}&"|"&S{r},Cadence!$A:$D,4,FALSE)-1,'
                    f'Q{r}+VLOOKUP(G{r}&"|"&S{r},Cadence!$A:$D,4,FALSE)-IFERROR(VLOOKUP(G{r}&"|"&P{r},Cadence!$A:$D,4,FALSE),1)),"")'])
        for c in ("P", "Q", "R"):
            acc[f"{c}{r}"].fill = INPUT
        acc[f"Q{r}"].number_format = "yyyy-mm-dd"
        acc[f"U{r}"].number_format = "yyyy-mm-dd"
        acc[f"K{r}"].number_format = "#,##0"
    n = len(plan) + 1
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=False)
    acc.add_data_validation(dv); dv.add(f"R2:R{n}")
    acc.auto_filter.ref = f"A1:U{n}"

    sm = wb.create_sheet("Summary", 0)
    sm["A1"] = "Outreach tracker summary (all figures are live formulas)"; sm["A1"].font = Font(bold=True, size=13)
    tiers, terrs = list(playbook.CADENCE), ["West", "East", "Central", "South"]
    sm.append([]); sm.append(["Territory"] + tiers + ["Total", "Sales (24m)", "Demos booked", "Qualified"])
    for c in range(1, 10):
        sm.cell(row=3, column=c).font, sm.cell(row=3, column=c).fill = HEAD, FILL
    for i, t in enumerate(terrs, 4):
        row = [t] + [f'=COUNTIFS(Accounts!$E:$E,$A{i},Accounts!$G:$G,"{tier}")' for tier in tiers]
        row += [f"=SUM(B{i}:E{i})", f"=SUMIFS(Accounts!$K:$K,Accounts!$E:$E,$A{i})",
                f'=COUNTIFS(Accounts!$E:$E,$A{i},Accounts!$R:$R,"Demo booked")',
                f'=COUNTIFS(Accounts!$E:$E,$A{i},Accounts!$R:$R,"Qualified")']
        sm.append(row)
    sm.append(["Total"] + [f"=SUM({get_column_letter(c)}4:{get_column_letter(c)}7)" for c in range(2, 10)])
    sm.append([])
    sm.append(["Status", "Accounts"])
    for c in (1, 2):
        sm.cell(row=10, column=c).font, sm.cell(row=10, column=c).fill = HEAD, FILL
    for s in STATUSES:
        sm.append([s, f'=COUNTIF(Accounts!$R:$R,"{s}")'])
    sm.append([]); sm.append(["Touches due by 2018-01-07", '=COUNTIFS(Accounts!$U:$U,"<="&DATE(2018,1,7),Accounts!$U:$U,">0")'])
    for col, w in zip("ABCDEFGHI", [26, 9, 9, 10, 10, 9, 13, 13, 11]):
        sm.column_dimensions[col].width = w
    for r in range(4, 9):
        sm[f"G{r}"].number_format = "#,##0"
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
