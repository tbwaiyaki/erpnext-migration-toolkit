"""
ERPNext live data fetcher for the ReportGenerator.
All API queries are centralised here. Each method returns a pandas DataFrame
so the report builder can treat ERPNext data identically to CSV data.

Field name rule (Frappe v15):
  Custom fields are stored as `custom_fieldname` in the DB but the API
  filter/fields key is just `fieldname` — no custom_ prefix.

Page size:
  FrappeClient limit_page_length=0 silently defaults to 20.
  Always pass an explicit large value.
"""

import pandas as pd
from frappeclient import FrappeClient

PAGE = 10_000   # safe ceiling for any realistic dataset


class ERPNextFetcher:

    def __init__(self, client: FrappeClient, company: str):
        self.client  = client
        self.company = company

    # ─────────────────────────────────────────────────────────────────────
    # Revenue
    # ─────────────────────────────────────────────────────────────────────

    def etims_invoices(self) -> pd.DataFrame:
        """All submitted eTIMS sales invoices."""
        rows = self.client.get_list(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "original_invoice_number": ["is", "set"]},
            fields=["name", "posting_date", "grand_total",
                    "original_invoice_number", "customer"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"] = pd.to_datetime(df["posting_date"])
        df["month_label"]  = df["posting_date"].dt.strftime("%b %Y")
        df["ym"]           = df["posting_date"].dt.to_period("M")
        return df

    def room_booking_invoices(self) -> pd.DataFrame:
        """All submitted room booking invoices."""
        rows = self.client.get_list(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_booking_id": ["is", "set"]},
            fields=["name", "posting_date", "grand_total",
                    "source_booking_id", "customer"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"]      = pd.to_datetime(df["posting_date"])
        df["month_label"]       = df["posting_date"].dt.strftime("%b %Y")
        df["ym"]                = df["posting_date"].dt.to_period("M")
        df["source_booking_id"] = pd.to_numeric(df["source_booking_id"])
        return df

    def event_invoices(self) -> pd.DataFrame:
        """All submitted event hire invoices."""
        rows = self.client.get_list(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_event_id": ["is", "set"]},
            fields=["name", "posting_date", "grand_total",
                    "source_event_id", "customer"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"]    = pd.to_datetime(df["posting_date"])
        df["month_label"]     = df["posting_date"].dt.strftime("%b %Y")
        df["ym"]              = df["posting_date"].dt.to_period("M")
        df["source_event_id"] = pd.to_numeric(df["source_event_id"])
        return df

    def egg_sale_invoices(self) -> pd.DataFrame:
        """All submitted egg sale invoices."""
        rows = self.client.get_list(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_egg_sale_id": ["is", "set"]},
            fields=["name", "posting_date", "grand_total",
                    "source_egg_sale_id", "customer"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"]       = pd.to_datetime(df["posting_date"])
        df["month_label"]        = df["posting_date"].dt.strftime("%b %Y")
        df["ym"]                 = df["posting_date"].dt.to_period("M")
        df["source_egg_sale_id"] = pd.to_numeric(df["source_egg_sale_id"])
        return df

    def payment_entries(self) -> pd.DataFrame:
        """All submitted payment entries (Receive)."""
        rows = self.client.get_list(
            "Payment Entry",
            filters={"company": self.company, "docstatus": 1,
                     "payment_type": "Receive"},
            fields=["name", "posting_date", "paid_amount", "party"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"] = pd.to_datetime(df["posting_date"])
        df["month_label"]  = df["posting_date"].dt.strftime("%b %Y")
        df["ym"]           = df["posting_date"].dt.to_period("M")
        return df

    # ─────────────────────────────────────────────────────────────────────
    # Expenses / Journal Entries
    # ─────────────────────────────────────────────────────────────────────

    def journal_entries(self) -> pd.DataFrame:
        """
        All submitted JEs with source_transaction_id (expense + savings + capital).
        Note: category breakdown is not available at the JE header level via API.
        total_debit double-counts (both ledger legs) — use count and posting_date only.
        """
        rows = self.client.get_list(
            "Journal Entry",
            filters={"company": self.company, "docstatus": 1,
                     "source_transaction_id": ["is", "set"]},
            fields=["name", "posting_date", "source_transaction_id", "total_debit"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"]         = pd.to_datetime(df["posting_date"])
        df["month_label"]          = df["posting_date"].dt.strftime("%b %Y")
        df["ym"]                   = df["posting_date"].dt.to_period("M")
        df["source_transaction_id"] = pd.to_numeric(df["source_transaction_id"])
        return df

    # ─────────────────────────────────────────────────────────────────────
    # Inventory
    # ─────────────────────────────────────────────────────────────────────

    def items(self) -> pd.DataFrame:
        """All migrated inventory items."""
        rows = self.client.get_list(
            "Item",
            filters={"source_item_id": ["is", "set"]},
            fields=["name", "item_name", "item_group",
                    "stock_uom", "valuation_rate", "source_item_id"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["source_item_id"] = pd.to_numeric(df["source_item_id"])
        df["valuation_rate"] = pd.to_numeric(df["valuation_rate"], errors="coerce").fillna(0)
        return df

    def stock_entries(self) -> pd.DataFrame:
        """All submitted stock entries from migration."""
        rows = self.client.get_list(
            "Stock Entry",
            filters={"docstatus": 1, "source_movement_id": ["is", "set"]},
            fields=["name", "posting_date", "stock_entry_type", "source_movement_id"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["posting_date"]       = pd.to_datetime(df["posting_date"])
        df["source_movement_id"] = pd.to_numeric(df["source_movement_id"])
        return df

    def stock_balances(self, warehouse: str = "Stores - WC") -> pd.DataFrame:
        """
        Current stock balances per item via Stock Ledger Entry.
        Takes the last qty_after_transaction for each item_code.
        """
        rows = self.client.get_list(
            "Stock Ledger Entry",
            filters={"warehouse": warehouse},
            fields=["item_code", "posting_date", "actual_qty", "qty_after_transaction"],
            order_by="posting_date asc, creation asc",
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Keep last entry per item = current balance
        df["posting_date"] = pd.to_datetime(df["posting_date"])
        df = df.sort_values(["item_code", "posting_date", "creation"]
                            if "creation" in df.columns
                            else ["item_code", "posting_date"])
        return df.groupby("item_code").last().reset_index()[
            ["item_code", "qty_after_transaction"]
        ].rename(columns={"qty_after_transaction": "current_qty"})

    # ─────────────────────────────────────────────────────────────────────
    # Compliance
    # ─────────────────────────────────────────────────────────────────────

    def compliance_documents(self) -> pd.DataFrame:
        """All compliance/licence documents."""
        rows = self.client.get_list(
            "License",
            fields=["name", "document_type", "document_number",
                    "expiry_date", "is_expired"],
            limit_page_length=PAGE
        )
        df = pd.DataFrame(rows)
        df["is_expired"] = df["is_expired"].astype(bool)
        return df

    # ─────────────────────────────────────────────────────────────────────
    # Convenience summary methods
    # ─────────────────────────────────────────────────────────────────────

    def revenue_by_month(self) -> pd.DataFrame:
        """
        Combined income by month from all invoice types.
        Used for Sheet 7 (Monthly P&L).
        """
        dfs = []
        for df, label in [
            (self.etims_invoices(),        "eTIMS"),
            (self.room_booking_invoices(), "Rooms"),
            (self.event_invoices(),        "Events"),
            (self.egg_sale_invoices(),     "Eggs"),
        ]:
            if not df.empty:
                df["source_type"] = label
                dfs.append(df[["posting_date", "grand_total", "source_type"]])

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        combined["month_label"] = combined["posting_date"].dt.strftime("%b %Y")
        combined["ym"]          = combined["posting_date"].dt.to_period("M")
        return (combined.groupby(["month_label", "ym"])["grand_total"]
                .sum().reset_index()
                .sort_values("ym")
                .rename(columns={"grand_total": "erp_income"}))
