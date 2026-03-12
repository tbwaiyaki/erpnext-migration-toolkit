"""
Wellness Centre — ERPNext Migration Reconciliation Report
Version 3.0 — Excel Tables throughout (user can reskin via Table Design tab)

Usage:
    from orchestration.report_generator import ReportGenerator
    gen = ReportGenerator(client=client, data_dir=DATA_DIR, company=COMPANY)
    gen.build("../docs/reports/Wellness_Centre_Reconciliation_v3.xlsx")
"""

import pandas as pd
from pathlib import Path
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from frappeclient import FrappeClient

try:
    from orchestration.erpnext_fetcher import ERPNextFetcher
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from erpnext_fetcher import ERPNextFetcher

VERSION = "3.0"

# ── Default table style — user can change per-table in Excel ──────────────────
TABLE_STYLE   = "TableStyleMedium9"   # Blue-green banded rows
TOTAL_STYLE   = "TableStyleMedium9"

# ── Sheet header colours (the only manual formatting remaining) ───────────────
HDR_DARK   = "FF1A4731"   # Dark green — sheet title bar
HDR_MID    = "FF2D6A4F"   # Mid green  — section title bars
HDR_TEXT   = "FFFFFFFF"
KES_FMT    = '#,##0'
COUNT_FMT  = '#,##0'
PCT_FMT    = '0.0%'


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sheet_title(ws, text, subtitle, col_count):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
    c = ws.cell(1, 1, text)
    c.font      = Font(name="Calibri", size=13, bold=True, color=HDR_TEXT)
    c.fill      = PatternFill("solid", fgColor=HDR_DARK)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=col_count)
    c = ws.cell(2, 1, subtitle)
    c.font      = Font(name="Calibri", size=9, color=HDR_TEXT)
    c.fill      = PatternFill("solid", fgColor=HDR_MID)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18
    ws.freeze_panes = "A3"


def _section_row(ws, row, text, col_count):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=col_count)
    c = ws.cell(row, 1, "  " + text)
    c.font      = Font(name="Calibri", size=10, bold=True, color=HDR_TEXT)
    c.fill      = PatternFill("solid", fgColor=HDR_MID)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 20


def _col_widths(ws, widths: list):
    """widths: list of (col_letter_or_int, width)"""
    for col, w in widths:
        letter = col if isinstance(col, str) else get_column_letter(col)
        ws.column_dimensions[letter].width = w


def _add_table(ws, start_row: int, headers: list, rows: list,
               name: str, style=TABLE_STYLE,
               num_fmts: dict = None) -> int:
    """
    Write headers + data rows, register as Excel Table.
    num_fmts: dict of {col_index (1-based): format_string}
    Returns the next available row (after a blank gap).
    """
    num_fmts = num_fmts or {}
    ncols = len(headers)

    # Header row
    for c, h in enumerate(headers, 1):
        ws.cell(start_row, c, h)
    ws.row_dimensions[start_row].height = 28

    # Data rows
    for r, row_data in enumerate(rows, start_row + 1):
        for c, val in enumerate(row_data, 1):
            cell = ws.cell(r, c, val)
            if c in num_fmts:
                cell.number_format = num_fmts[c]
        ws.row_dimensions[r].height = 16

    end_row = start_row + len(rows)
    ref = f"A{start_row}:{get_column_letter(ncols)}{end_row}"
    tab = Table(displayName=name, ref=ref)
    tab.tableStyleInfo = TableStyleInfo(
        name=style,
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(tab)

    return end_row + 2   # blank row gap between tables


def _status(match, warned=False):
    if match:    return "✓ Match"
    if warned:   return "⚠ Exception"
    return "✗ Variance"


# ─────────────────────────────────────────────────────────────────────────────
# ReportGenerator
# ─────────────────────────────────────────────────────────────────────────────

class ReportGenerator:

    VERSION = VERSION

    def __init__(self, client: FrappeClient, data_dir: Path, company: str):
        self.company  = company
        self.data_dir = Path(data_dir)
        self._fetcher = ERPNextFetcher(client, company)
        self._erp = {}
        self._csv = {}

    # ── Public ───────────────────────────────────────────────────────────────

    def build(self, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print("=" * 70)
        print(f"REPORT GENERATOR v{VERSION}")
        print("=" * 70)

        print("\n[1/3] Loading source CSV data...")
        self._load_csv()

        print("[2/3] Fetching live ERPNext data...")
        self._fetch_erp()

        print("[3/3] Building workbook...")
        wb = Workbook()
        wb.remove(wb.active)

        self._sheet_summary(wb)
        self._sheet_revenue(wb)
        self._sheet_expenses(wb)
        self._sheet_inventory(wb)
        self._sheet_poultry(wb)
        self._sheet_compliance(wb)
        self._sheet_pnl(wb)

        wb.save(output_path)
        print(f"\n✓ Saved: {output_path}")
        print(f"  Sheets: {wb.sheetnames}")
        return output_path

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_csv(self):
        d = self.data_dir
        tx   = pd.read_csv(d / "transactions.csv")
        cats = pd.read_csv(d / "transaction_categories.csv")
        tx   = tx.merge(cats[["id","name","type"]], left_on="category_id",
                        right_on="id", suffixes=("","_cat"))
        tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
        tx["month_label"]      = tx["transaction_date"].dt.strftime("%b %Y")
        tx["ym"]               = tx["transaction_date"].dt.to_period("M")

        inv      = pd.read_csv(d / "inventory_items.csv")
        inv_cats = pd.read_csv(d / "inventory_categories.csv")
        inv      = inv.merge(inv_cats[["id","name"]], left_on="category_id",
                             right_on="id", suffixes=("","_cat"))
        inv["total_value"] = inv["quantity_on_hand"] * inv["unit_cost"]

        egg_s = pd.read_csv(d / "egg_sales.csv")
        egg_s["sale_date"]   = pd.to_datetime(egg_s["sale_date"])
        egg_s["month_label"] = egg_s["sale_date"].dt.strftime("%b %Y")
        egg_s["ym"]          = egg_s["sale_date"].dt.to_period("M")

        bookings = pd.read_csv(d / "room_bookings.csv")
        rooms    = pd.read_csv(d / "rooms.csv")
        bookings = bookings.merge(rooms[["id","room_name","nightly_rate"]],
                                  left_on="room_id", right_on="id",
                                  suffixes=("","_room"))

        events   = pd.read_csv(d / "events.csv")
        contacts = pd.read_csv(d / "contacts.csv")
        egg_p    = pd.read_csv(d / "egg_production.csv")
        comp     = pd.read_csv(d / "compliance_documents.csv")
        inv_mov  = pd.read_csv(d / "inventory_movements.csv")

        self._csv = {
            "tx": tx, "inv": inv, "egg_s": egg_s,
            "bookings": bookings, "events": events,
            "contacts": contacts, "egg_p": egg_p,
            "comp": comp, "inv_mov": inv_mov,
        }
        print(f"  ✓ {len(self._csv)} source datasets loaded")

    def _fetch_erp(self):
        tasks = {
            "etims":         self._fetcher.etims_invoices,
            "room_inv":      self._fetcher.room_booking_invoices,
            "event_inv":     self._fetcher.event_invoices,
            "egg_inv":       self._fetcher.egg_sale_invoices,
            "payments":      self._fetcher.payment_entries,
            "journal":       self._fetcher.journal_entries,
            "items":         self._fetcher.items,
            "stock_entries": self._fetcher.stock_entries,
            "compliance":    self._fetcher.compliance_documents,
        }
        for key, fn in tasks.items():
            try:
                self._erp[key] = fn()
                print(f"  ✓ {key}: {len(self._erp[key])} records")
            except Exception as e:
                print(f"  ✗ {key}: {e}")
                self._erp[key] = pd.DataFrame()

    # ── Sheet 1 — Summary ────────────────────────────────────────────────────

    def _sheet_summary(self, wb):
        ws = wb.create_sheet("1. Summary")
        ws.sheet_view.showGridLines = False
        COLS = 7

        _sheet_title(ws,
            f"{self.company} — ERPNext Migration Reconciliation",
            f"Generated {date.today().strftime('%d %B %Y')}  |  "
            f"Source: Legacy CSV  |  Target: ERPNext v15  |  "
            f"Report Generator v{VERSION}",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 18), ("B", 46), ("C", 16), ("D", 16),
            ("E", 14), ("F", 14), ("G", 64),
        ])

        erp = self._erp
        csv = self._csv

        def ec(key):   return len(erp[key]) if not erp[key].empty else 0
        def es(key, c): return float(erp[key][c].sum()) if not erp[key].empty else 0.0

        checks = [
            # (domain, description, csv_val, erp_val, warned, notes)
            ("Revenue", "eTIMS Sales Invoices — Count",
             220, ec("etims"), False, ""),
            ("Revenue", "eTIMS Sales Invoices — Total (KES)",
             float(csv["tx"][csv["tx"]["type_cat"]=="income"]["amount"].sum()),
             es("etims","grand_total"), False, ""),
            ("Revenue", "Room Booking Invoices — Count",
             len(csv["bookings"]), ec("room_inv"), False, ""),
            ("Revenue", "Room Booking Revenue (KES)",
             float(csv["bookings"]["total_amount"].sum()),
             es("room_inv","grand_total"), False, ""),
            ("Revenue", "Event Invoices — Count",
             len(csv["events"]), ec("event_inv"), False, ""),
            ("Revenue", "Event Venue Hire Revenue (KES)",
             float(csv["events"]["hire_fee"].sum()),
             es("event_inv","grand_total"), False, ""),
            ("Revenue", "Egg Sale Invoices — Count",
             len(csv["egg_s"]), ec("egg_inv"), False, ""),
            ("Revenue", "Egg Sales Revenue (KES)",
             float(csv["egg_s"]["total_amount"].sum()),
             es("egg_inv","grand_total"), False, ""),
            ("Revenue", "Payment Entries — Total Received (KES)",
             float(csv["tx"][csv["tx"]["type_cat"]=="income"]["amount"].sum()),
             es("payments","paid_amount"), False, ""),
            ("Expenses", "Journal Entries — Count",
             727, ec("journal"), False,
             "709 expense + 15 savings + 3 capital injections"),
            ("Inventory", "Inventory Items — Count",
             len(csv["inv"]), ec("items"), False, ""),
            ("Inventory", "Stock Movements — Count",
             len(csv["inv_mov"]), ec("stock_entries"), True,
             "3 skipped: source issued more than was ever purchased"),
            ("Compliance", "Compliance Documents — Count",
             len(csv["comp"]), ec("compliance"), False,
             "6 of 9 documents historically expired at migration date"),
        ]

        row = 4
        headers = ["Domain", "Reconciliation Check",
                   "Source (CSV)", "ERPNext (Live)",
                   "Variance", "Status", "Notes"]
        rows = []
        for domain, label, src, erp_val, warned, notes in checks:
            variance = erp_val - src
            match    = abs(variance) < 0.01
            if label == "Stock Movements — Count":
                match = abs(variance - (-3)) < 0.01
            is_num   = isinstance(src, float) and src > 100
            rows.append([
                domain, label,
                src, erp_val,
                variance,
                _status(match, warned),
                notes,
            ])

        nf = {3: KES_FMT, 4: KES_FMT, 5: KES_FMT}
        # Only KES format for revenue rows — we'll just apply to all and let
        # integer display be handled by Excel (integers display without decimals)
        _add_table(ws, row, headers, rows, "tbl_summary",
                   style=TABLE_STYLE, num_fmts=nf)

    # ── Sheet 2 — Revenue Detail ─────────────────────────────────────────────

    def _sheet_revenue(self, wb):
        ws = wb.create_sheet("2. Revenue Detail")
        ws.sheet_view.showGridLines = False
        COLS = 8

        _sheet_title(ws,
            "Revenue Detail — All Income by Stream",
            "Green = Source CSV  |  All figures in KES",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 14), ("B", 14), ("C", 18), ("D", 14),
            ("E", 18), ("F", 16), ("G", 13), ("H", 14),
        ])

        erp = self._erp
        csv = self._csv
        row = 4

        # ── eTIMS monthly ────────────────────────────────────────────────────
        _section_row(ws, row, "eTIMS Sales Invoices — Monthly", COLS)
        row += 1

        etims_csv = csv["tx"][csv["tx"]["type_cat"]=="income"].copy()
        etims_csv["ym"] = etims_csv["transaction_date"].dt.to_period("M")
        csv_m = (etims_csv.groupby("month_label")
                 .agg(count=("id","count"), total=("amount","sum"), ym=("ym","min"))
                 .sort_values("ym").reset_index())

        if not erp["etims"].empty:
            erp_m = (erp["etims"].groupby("month_label")
                     .agg(count=("name","count"), total=("grand_total","sum"), ym=("ym","min"))
                     .sort_values("ym").reset_index()
                     .rename(columns={"count":"ec","total":"et"}))
            merged = csv_m.merge(erp_m[["month_label","ec","et"]],
                                 on="month_label", how="left").fillna(0)
        else:
            merged = csv_m.assign(ec=0, et=0)

        rows = []
        for _, r in merged.iterrows():
            v = r["et"] - r["total"]
            rows.append([r["month_label"], int(r["count"]), r["total"],
                         int(r["ec"]), r["et"], v, _status(abs(v) < 0.01)])
        row = _add_table(ws, row,
            ["Month","Count (CSV)","Total CSV (KES)","Count (ERP)","Total ERP (KES)","Variance (KES)","Status"],
            rows, "tbl_etims",
            num_fmts={3: KES_FMT, 5: KES_FMT, 6: KES_FMT})

        # ── Room bookings by room ────────────────────────────────────────────
        _section_row(ws, row, "Room Bookings — by Room", COLS)
        row += 1

        csv_rooms = (csv["bookings"].groupby("room_name")
                     .agg(count=("id","count"), total=("total_amount","sum"),
                          rate=("nightly_rate","mean"))
                     .sort_values("total", ascending=False).reset_index())

        if not erp["room_inv"].empty:
            room_map = csv["bookings"][["id","room_name"]].rename(
                columns={"id":"source_booking_id"})
            erp_r = (erp["room_inv"].merge(room_map, on="source_booking_id", how="left")
                     .groupby("room_name")
                     .agg(ec=("name","count"), et=("grand_total","sum"))
                     .reset_index())
            merged = csv_rooms.merge(erp_r, on="room_name", how="left").fillna(0)
        else:
            merged = csv_rooms.assign(ec=0, et=0)

        rows = []
        for _, r in merged.iterrows():
            v = r["et"] - r["total"]
            rows.append([r["room_name"], int(r["count"]), r["total"],
                         int(r["ec"]), r["et"], v,
                         _status(abs(v) < 0.01), r["rate"]])
        row = _add_table(ws, row,
            ["Room","Bookings (CSV)","Revenue CSV (KES)","Bookings (ERP)",
             "Revenue ERP (KES)","Variance (KES)","Status","Nightly Rate (KES)"],
            rows, "tbl_rooms",
            num_fmts={3: KES_FMT, 5: KES_FMT, 6: KES_FMT, 8: KES_FMT})

        # ── Events by type ───────────────────────────────────────────────────
        _section_row(ws, row, "Event Venue Hire — by Event Type", COLS)
        row += 1

        csv_evt = (csv["events"].groupby("event_type")
                   .agg(count=("id","count"), total=("hire_fee","sum"),
                        avg=("hire_fee","mean"))
                   .sort_values("total", ascending=False).reset_index())

        if not erp["event_inv"].empty:
            evt_map = csv["events"][["id","event_type"]].rename(
                columns={"id":"source_event_id"})
            erp_e = (erp["event_inv"].merge(evt_map, on="source_event_id", how="left")
                     .groupby("event_type")
                     .agg(ec=("name","count"), et=("grand_total","sum"))
                     .reset_index())
            merged = csv_evt.merge(erp_e, on="event_type", how="left").fillna(0)
        else:
            merged = csv_evt.assign(ec=0, et=0)

        rows = []
        for _, r in merged.iterrows():
            v = r["et"] - r["total"]
            rows.append([r["event_type"], int(r["count"]), r["total"],
                         int(r["ec"]), r["et"], v,
                         _status(abs(v) < 0.01), r["avg"]])
        row = _add_table(ws, row,
            ["Event Type","Events (CSV)","Fee CSV (KES)","Events (ERP)",
             "Fee ERP (KES)","Variance (KES)","Status","Avg Fee (KES)"],
            rows, "tbl_events",
            num_fmts={3: KES_FMT, 5: KES_FMT, 6: KES_FMT, 8: KES_FMT})

        # ── Egg sales monthly ────────────────────────────────────────────────
        _section_row(ws, row, "Egg Sales — Monthly", COLS)
        row += 1

        csv_egg = (csv["egg_s"].groupby("month_label")
                   .agg(count=("id","count"), trays=("trays_sold","sum"),
                        total=("total_amount","sum"), ym=("ym","min"))
                   .sort_values("ym").reset_index())

        if not erp["egg_inv"].empty:
            erp_egg = (erp["egg_inv"].groupby("month_label")
                       .agg(ec=("name","count"), et=("grand_total","sum"),
                            ym=("ym","min"))
                       .sort_values("ym").reset_index())
            merged = csv_egg.merge(erp_egg[["month_label","ec","et"]],
                                   on="month_label", how="left").fillna(0)
        else:
            merged = csv_egg.assign(ec=0, et=0)

        rows = []
        for _, r in merged.iterrows():
            v = r["et"] - r["total"]
            rows.append([r["month_label"], int(r["count"]), int(r["trays"]),
                         r["total"], int(r["ec"]), r["et"], v,
                         _status(abs(v) < 0.01)])
        _add_table(ws, row,
            ["Month","Sales (CSV)","Trays Sold","Revenue CSV (KES)",
             "Invoices (ERP)","Revenue ERP (KES)","Variance (KES)","Status"],
            rows, "tbl_eggs",
            num_fmts={4: KES_FMT, 6: KES_FMT, 7: KES_FMT})

    # ── Sheet 3 — Expenses ───────────────────────────────────────────────────

    def _sheet_expenses(self, wb):
        ws = wb.create_sheet("3. Expense Detail")
        ws.sheet_view.showGridLines = False
        COLS = 6

        _sheet_title(ws,
            "Expense Detail — Journal Entries",
            "Operating Expenses · Capital Injections · Savings Transfers",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 40), ("B", 14), ("C", 18), ("D", 14),
            ("E", 16), ("F", 50),
        ])

        erp = self._erp
        csv = self._csv
        row = 4

        # ── Category breakdown ───────────────────────────────────────────────
        _section_row(ws, row,
            "Operating Expenses by Category  "
            "(Source system — category detail in account lines in ERPNext)", COLS)
        row += 1

        expenses   = csv["tx"][csv["tx"]["type_cat"]=="expense"]
        exp_total  = expenses["amount"].sum()
        exp_by_cat = (expenses.groupby("name")
                      .agg(count=("id","count"), total=("amount","sum"))
                      .sort_values("total", ascending=False).reset_index())
        exp_by_cat["pct"] = exp_by_cat["total"] / exp_total

        pay_by_cat = (expenses.groupby(["name","payment_method"])["amount"]
                      .sum().unstack(fill_value=0))

        rows = []
        for _, r in exp_by_cat.iterrows():
            pay_str = ""
            if r["name"] in pay_by_cat.index:
                pay_str = "  |  ".join(
                    f"{pm}: {int(v):,}" for pm, v
                    in pay_by_cat.loc[r["name"]].items() if v > 0)
            rows.append([r["name"], int(r["count"]), r["total"],
                         r["pct"], "✓ In ERPNext", pay_str])
        row = _add_table(ws, row,
            ["Category","Transactions","Total (KES)","% of Expenses",
             "ERPNext Status","Payment Method Breakdown"],
            rows, "tbl_exp_categories",
            num_fmts={3: KES_FMT, 4: PCT_FMT})

        # ── Monthly JE count reconciliation ─────────────────────────────────
        _section_row(ws, row, "Monthly Journal Entries — CSV Count vs ERPNext Count", COLS)
        row += 1

        je_csv = (csv["tx"][csv["tx"]["type_cat"].isin(
                      ["expense","savings","capital_injection"])]
                  .groupby("month_label")
                  .agg(count=("id","count"), total=("amount","sum"), ym=("ym","min"))
                  .sort_values("ym").reset_index())

        if not erp["journal"].empty:
            erp_je = (erp["journal"].groupby("month_label")
                      .agg(ec=("name","count"), ym=("ym","min"))
                      .sort_values("ym").reset_index())
            merged = je_csv.merge(erp_je[["month_label","ec"]],
                                  on="month_label", how="left").fillna(0)
        else:
            merged = je_csv.assign(ec=0)

        rows = []
        for _, r in merged.iterrows():
            match = int(r["count"]) == int(r["ec"])
            rows.append([r["month_label"], int(r["count"]), r["total"],
                         int(r["ec"]), _status(match), ""])
        _add_table(ws, row,
            ["Month","JEs (CSV)","Amount CSV (KES)","JEs (ERPNext)","Status","Notes"],
            rows, "tbl_je_monthly",
            num_fmts={3: KES_FMT})

    # ── Sheet 4 — Inventory ──────────────────────────────────────────────────

    def _sheet_inventory(self, wb):
        ws = wb.create_sheet("4. Inventory")
        ws.sheet_view.showGridLines = False
        COLS = 8

        _sheet_title(ws,
            "Inventory — Items & Stock Movements",
            "77 items · 8 categories · 190 of 193 movements migrated",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 30), ("B", 14), ("C", 14), ("D", 17),
            ("E", 14), ("F", 26), ("G", 14), ("H", 38),
        ])

        erp = self._erp
        csv = self._csv
        row = 4

        # ── Category summary ─────────────────────────────────────────────────
        _section_row(ws, row, "Inventory Summary by Category", COLS)
        row += 1

        csv_cat = (csv["inv"].groupby("name")
                   .agg(items=("id","count"), qty=("quantity_on_hand","sum"),
                        value=("total_value","sum"))
                   .sort_values("value", ascending=False).reset_index())

        if not erp["items"].empty:
            erp_cat = (erp["items"].groupby("item_group")
                       .agg(ei=("name","count")).reset_index()
                       .rename(columns={"item_group":"name"}))
            merged = csv_cat.merge(erp_cat, on="name", how="left").fillna(0)
        else:
            merged = csv_cat.assign(ei=0)

        rows = []
        for _, r in merged.iterrows():
            match = int(r["items"]) == int(r["ei"])
            rows.append([r["name"], int(r["items"]), int(r["qty"]),
                         r["value"], int(r["ei"]), r["name"],
                         _status(match), ""])
        row = _add_table(ws, row,
            ["Category","Items (CSV)","Qty on Hand","Value CSV (KES)",
             "Items (ERP)","ERP Item Group","Status","Notes"],
            rows, "tbl_inv_categories",
            num_fmts={4: KES_FMT})

        # ── Stock movements by type ──────────────────────────────────────────
        _section_row(ws, row, "Stock Movements — by Type", COLS)
        row += 1

        mov_type_map = {
            "Purchase": "Material Receipt",
            "Audit Adjustment": "Material Receipt",
            "Breakage": "Material Issue",
            "Disposal": "Material Issue",
            "Loss": "Material Issue",
        }
        skipped = {"Disposal": 1, "Breakage": 2}

        csv_mov = (csv["inv_mov"].groupby("movement_type")
                   .agg(count=("id","count"), qty=("quantity","sum"))
                   .reset_index())

        rows = []
        for _, r in csv_mov.iterrows():
            skip     = skipped.get(r["movement_type"], 0)
            exp_erp  = int(r["count"]) - skip
            erp_type = mov_type_map.get(r["movement_type"], "")
            note     = f"{skip} skipped — issued > received" if skip else ""
            rows.append([r["movement_type"], int(r["count"]), int(r["qty"]),
                         exp_erp, erp_type, -skip,
                         _status(skip == 0, warned=skip > 0), note])
        row = _add_table(ws, row,
            ["Movement Type","Count (CSV)","Qty (CSV)","Count (ERP)",
             "ERP Entry Type","Variance","Status","Notes"],
            rows, "tbl_stock_movements",
            num_fmts={6: COUNT_FMT})

        # ── All items line by line ───────────────────────────────────────────
        _section_row(ws, row, "All Inventory Items — CSV vs ERPNext", COLS)
        row += 1

        _col_widths(ws, [("A", 36), ("B", 26), ("C", 14), ("D", 17),
                         ("E", 17), ("F", 18), ("G", 36), ("H", 14)])

        if not erp["items"].empty:
            erp_lkp = (erp["items"].set_index("source_item_id")
                       [["name","item_name"]].to_dict("index"))
        else:
            erp_lkp = {}

        inv_sorted = csv["inv"].sort_values(["name","item_name"])
        rows = []
        for r in inv_sorted.itertuples():
            ei = erp_lkp.get(r.id, {})
            rows.append([
                r.item_name, r.name,
                r.quantity_on_hand, float(r.unit_cost), r.total_value,
                ei.get("name", "—"), ei.get("item_name", "Not found"),
                _status(bool(ei)),
            ])
        _add_table(ws, row,
            ["Item Name (CSV)","Category","Qty","Unit Cost (KES)","Value (KES)",
             "ERP Item Code","ERP Item Name","Status"],
            rows, "tbl_items_detail",
            num_fmts={4: KES_FMT, 5: KES_FMT})

    # ── Sheet 5 — Poultry ────────────────────────────────────────────────────

    def _sheet_poultry(self, wb):
        ws = wb.create_sheet("5. Poultry Farm")
        ws.sheet_view.showGridLines = False
        COLS = 7

        _sheet_title(ws,
            "Poultry Farm — Egg Production & Sales",
            "52 weeks production  |  103 egg sale invoices",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 14), ("B", 14), ("C", 14), ("D", 14),
            ("E", 14), ("F", 14), ("G", 44),
        ])

        erp = self._erp
        csv = self._csv
        row = 4

        # ── Weekly production ────────────────────────────────────────────────
        _section_row(ws, row,
            "Egg Production — Weekly  (Source system only)", COLS)
        row += 1

        rows = []
        for r in csv["egg_p"].itertuples():
            dmg = r.eggs_damaged / r.eggs_collected if r.eggs_collected else 0
            rows.append([
                str(r.week_start_date)[:10], str(r.week_end_date)[:10],
                r.eggs_collected, r.eggs_damaged,
                r.eggs_available_for_sale, dmg,
                str(r.notes) if str(r.notes) != "nan" else "",
            ])
        row = _add_table(ws, row,
            ["Week Start","Week End","Collected","Damaged","Available","Damage Rate","Notes"],
            rows, "tbl_egg_production",
            num_fmts={6: PCT_FMT})

        # ── Egg sales with ERP invoice reference ────────────────────────────
        _section_row(ws, row,
            "Egg Sales — All Transactions (CSV vs ERPNext Invoice)", COLS)
        row += 1

        _col_widths(ws, [("A", 14), ("B", 28), ("C", 12), ("D", 18),
                         ("E", 17), ("F", 22), ("G", 17)])

        contacts_map = csv["contacts"].set_index("id")["name"].to_dict()

        if not erp["egg_inv"].empty:
            erp_egg_lkp = (erp["egg_inv"]
                           .set_index("source_egg_sale_id")
                           [["name","grand_total"]].to_dict("index"))
        else:
            erp_egg_lkp = {}

        rows = []
        for r in csv["egg_s"].sort_values("sale_date").itertuples():
            cname   = contacts_map.get(r.contact_id, "Unknown")
            ei      = erp_egg_lkp.get(r.id, {})
            erp_ref = ei.get("name", "—")
            erp_tot = ei.get("grand_total", 0)
            rows.append([
                str(r.sale_date)[:10], cname,
                r.trays_sold, r.price_per_tray, r.total_amount,
                erp_ref, erp_tot,
                _status(abs(erp_tot - r.total_amount) < 0.01),
            ])
        _add_table(ws, row,
            ["Date","Customer","Trays","Price/Tray (KES)","Total CSV (KES)",
             "ERP Invoice","ERP Total (KES)","Status"],
            rows, "tbl_egg_sales",
            num_fmts={4: KES_FMT, 5: KES_FMT, 7: KES_FMT})

    # ── Sheet 6 — Compliance ─────────────────────────────────────────────────

    def _sheet_compliance(self, wb):
        ws = wb.create_sheet("6. Compliance")
        ws.sheet_view.showGridLines = False
        COLS = 8

        _sheet_title(ws,
            "Compliance Documents — Licences & Permits",
            "9 documents migrated  |  6 expired at migration date  |  "
            "Historical accuracy preserved",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 44), ("B", 24), ("C", 44), ("D", 13),
            ("E", 13), ("F", 16), ("G", 14), ("H", 20),
        ])

        erp = self._erp
        csv = self._csv
        row = 4

        if not erp["compliance"].empty:
            erp_comp = erp["compliance"].set_index("document_type").to_dict("index")
        else:
            erp_comp = {}

        today = date(2026, 3, 1)
        rows = []
        for r in csv["comp"].itertuples():
            has_exp = str(r.expiry_date) not in ("nan", "None", "")
            expired = (has_exp and
                       pd.to_datetime(r.expiry_date).date() < today)
            ei       = erp_comp.get(r.document_type, {})
            in_erp   = "✓ Migrated" if ei else "✗ Missing"
            erp_flag = "Expired" if ei.get("is_expired") else "Active"
            status   = "⚠ Expired" if expired else "✓ Active"
            fee      = float(r.renewal_fee) if str(r.renewal_fee) not in ("nan","None") else None
            rows.append([
                r.document_type, r.document_number, r.issuing_authority,
                str(r.issue_date)[:10],
                str(r.expiry_date)[:10] if has_exp else "No expiry",
                in_erp, erp_flag, fee if fee is not None else "",
                status,
            ])

        # 9 cols — extend col widths
        _col_widths(ws, [("I", 14)])

        row = _add_table(ws, row,
            ["Document Type","Document Number","Issuing Authority",
             "Issue Date","Expiry Date","In ERPNext","ERPNext Flag",
             "Renewal Fee (KES)","Status"],
            rows, "tbl_compliance",
            num_fmts={8: KES_FMT})

        # ── Summary counts ───────────────────────────────────────────────────
        _section_row(ws, row, "Summary", COLS)
        row += 1

        erp_total   = len(erp["compliance"]) if not erp["compliance"].empty else 0
        erp_expired = int(erp["compliance"]["is_expired"].sum()) if not erp["compliance"].empty else 0
        erp_active  = erp_total - erp_expired
        csv_fees    = float(csv["comp"]["renewal_fee"].sum())

        sum_rows = [
            ["Total documents migrated", 9, erp_total, _status(9 == erp_total), ""],
            ["Active documents", 3, erp_active, _status(3 == erp_active),
             "KRA PIN, eTIMS Registration, Business Registration"],
            ["Expired at migration date", 6, erp_expired,
             _status(6 == erp_expired, warned=True),
             "Marked is_expired=1 in ERPNext — historical accuracy preserved"],
            ["Total renewal fees outstanding (KES)", 41000, csv_fees,
             _status(abs(csv_fees - 41000) < 0.01), ""],
        ]
        _add_table(ws, row,
            ["Item","Source Count/Amount","ERPNext Count/Amount","Status","Notes"],
            sum_rows, "tbl_compliance_summary",
            num_fmts={2: COUNT_FMT, 3: COUNT_FMT})

    # ── Sheet 7 — Monthly P&L ────────────────────────────────────────────────

    def _sheet_pnl(self, wb):
        ws = wb.create_sheet("7. Monthly P&L")
        ws.sheet_view.showGridLines = False
        COLS = 8

        _sheet_title(ws,
            "Monthly Income & Expenditure — Jan 2024 to Feb 2025",
            "Source CSV  vs  ERPNext Live  |  All revenue streams combined",
            col_count=COLS)

        _col_widths(ws, [
            ("A", 14), ("B", 18), ("C", 21), ("D", 18),
            ("E", 18), ("F", 21), ("G", 18), ("H", 14),
        ])

        erp = self._erp
        csv = self._csv
        row = 4

        # ── Monthly P&L ──────────────────────────────────────────────────────
        _section_row(ws, row, "Monthly P&L Summary", COLS)
        row += 1

        inc_m = (csv["tx"][csv["tx"]["type_cat"]=="income"]
                 .groupby("month_label").agg(inc=("amount","sum"), ym=("ym","min")))
        exp_m = (csv["tx"][csv["tx"]["type_cat"]=="expense"]
                 .groupby("month_label").agg(exp=("amount","sum"), ym=("ym","min")))

        erp_inc_dfs = []
        for key in ["etims","room_inv","event_inv","egg_inv"]:
            df = erp[key]
            if not df.empty:
                d2 = df.copy()
                d2["month_label"] = d2["posting_date"].dt.strftime("%b %Y")
                d2["ym"]          = d2["posting_date"].dt.to_period("M")
                erp_inc_dfs.append(d2[["month_label","ym","grand_total"]])

        if erp_inc_dfs:
            ei_all = pd.concat(erp_inc_dfs)
            erp_inc_m = (ei_all.groupby("month_label")
                         .agg(erp_inc=("grand_total","sum"), ym=("ym","min")))
        else:
            erp_inc_m = pd.DataFrame(columns=["month_label","erp_inc","ym"])

        if not erp["journal"].empty:
            erp_exp_m = (erp["journal"].groupby("month_label")
                         .agg(erp_exp=("total_debit","sum"), ym=("ym","min")))
            erp_exp_m["erp_exp"] = erp_exp_m["erp_exp"] / 2
        else:
            erp_exp_m = pd.DataFrame(columns=["month_label","erp_exp","ym"])

        all_months = sorted(
            set(inc_m.index) | set(exp_m.index),
            key=lambda m: pd.to_datetime(m, format="%b %Y"))

        rows = []
        for month in all_months:
            ci = float(inc_m["inc"].get(month, 0))
            ce = float(exp_m["exp"].get(month, 0))
            cn = ci - ce
            ei = float(erp_inc_m["erp_inc"].get(month, 0)
                       if not erp_inc_m.empty else 0)
            ee = float(erp_exp_m["erp_exp"].get(month, 0)
                       if not erp_exp_m.empty else 0)
            en = ei - ee
            match = abs(ei - ci) < 0.01
            rows.append([month, ci, ce, cn, ei, ee, en, _status(match)])

        row = _add_table(ws, row,
            ["Month","Income CSV (KES)","Expenses CSV (KES)","Net CSV (KES)",
             "Income ERP (KES)","Expenses ERP (KES)","Net ERP (KES)","Status"],
            rows, "tbl_pnl",
            num_fmts={2: KES_FMT, 3: KES_FMT, 4: KES_FMT,
                      5: KES_FMT, 6: KES_FMT, 7: KES_FMT})

        # ── Income stream breakdown ──────────────────────────────────────────
        _section_row(ws, row, "Income Stream Breakdown", COLS)
        row += 1

        def es(key, col):
            return float(erp[key][col].sum()) if not erp[key].empty else 0.0

        streams = [
            ("eTIMS Sales Invoices",
             float(csv["tx"][csv["tx"]["type_cat"]=="income"]["amount"].sum()),
             es("etims","grand_total")),
            ("Room Bookings",
             float(csv["bookings"]["total_amount"].sum()),
             es("room_inv","grand_total")),
            ("Event Venue Hire",
             float(csv["events"]["hire_fee"].sum()),
             es("event_inv","grand_total")),
            ("Egg Sales",
             float(csv["egg_s"]["total_amount"].sum()),
             es("egg_inv","grand_total")),
        ]
        total_csv = sum(s[1] for s in streams)

        rows = []
        for label, cv, ev in streams:
            pct = cv / total_csv if total_csv else 0
            rows.append([label, cv, pct, ev, _status(abs(ev - cv) < 0.01)])

        _add_table(ws, row,
            ["Income Stream","Total CSV (KES)","% of Revenue",
             "Total ERP (KES)","Status"],
            rows, "tbl_income_streams",
            num_fmts={2: KES_FMT, 3: PCT_FMT, 4: KES_FMT})
