"""
Validation Reporter - Compare source CSV data against ERPNext after migration.

Performs three-level reconciliation:
  1. Financial: Revenue, expenses, payments
  2. Inventory: Items, stock movements
  3. Operational: Customers, compliance documents

Produces a structured result dict that can be rendered as Markdown,
printed to console, or saved as a file.

Designed to be reusable across any ERPNext migration project.

Usage:
    reporter = ValidationReporter(
        client=client,
        data_dir=DATA_DIR,
        company="Wellness Centre"
    )
    report = reporter.run()
    reporter.save_markdown(report, output_path)

Version: 1.1 - Fixed custom field filter names (no custom_ prefix)
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from frappeclient import FrappeClient


class ValidationReporter:
    """
    Validate migration completeness by comparing source CSV vs ERPNext.

    Key design note on custom fields:
        Frappe stores custom fields in the DB as `custom_fieldname` but the
        API filter key is just `fieldname` (no prefix). Using the `custom_`
        prefix in get_list filters or fields raises DataError in Frappe v15.
    """

    VERSION = "1.1"

    def __init__(self, client: FrappeClient, data_dir: Path, company: str):
        self.client = client
        self.data_dir = Path(data_dir)
        self.company = company
        self._cache = {}

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def run(self) -> dict:
        print("=" * 70)
        print("VALIDATION REPORTER v" + self.VERSION)
        print("=" * 70)

        print("\n[1/3] Financial reconciliation...")
        financial = self._validate_financial()

        print("[2/3] Inventory reconciliation...")
        inventory = self._validate_inventory()

        print("[3/3] Operational reconciliation...")
        operational = self._validate_operational()

        all_results = financial + inventory + operational
        total   = len(all_results)
        passed  = sum(1 for r in all_results if r["match"])
        failed  = total - passed

        report = {
            "meta": {
                "company":   self.company,
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "version":   self.VERSION,
            },
            "financial":   financial,
            "inventory":   inventory,
            "operational": operational,
            "summary": {
                "total":        total,
                "passed":       passed,
                "failed":       failed,
                "success_rate": round(100 * passed / total, 1) if total else 0,
            },
        }

        print(f"\n{'=' * 70}")
        print(f"COMPLETE: {passed}/{total} checks passed "
              f"({report['summary']['success_rate']}%)")
        print("=" * 70)
        return report

    def save_markdown(self, report: dict, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._render_markdown(report), encoding="utf-8")
        print(f"✓ Report saved: {output_path}")
        return output_path

    # ─────────────────────────────────────────────────────────────────────
    # Financial Validations
    # ─────────────────────────────────────────────────────────────────────

    def _validate_financial(self) -> list:
        results = []

        # Sales Invoices (eTIMS) — custom field: original_invoice_number
        src = self._csv_sum("etims_invoices.csv", "total_amount")
        erp = self._erp_sum(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "original_invoice_number": ["is", "set"]},
            field="grand_total"
        )
        results.append(self._result("Sales Invoice revenue (eTIMS)", src, erp))

        # Sales Invoice count
        src = self._csv_count("etims_invoices.csv")
        erp = self._erp_count(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "original_invoice_number": ["is", "set"]}
        )
        results.append(self._result("Sales invoice count", src, erp, is_count=True))

        # Room booking revenue — custom field: source_booking_id
        src = self._csv_sum("room_bookings.csv", "total_amount")
        erp = self._erp_sum(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_booking_id": ["is", "set"]},
            field="grand_total"
        )
        results.append(self._result("Room booking revenue", src, erp))

        # Event revenue — custom field: source_event_id
        src = self._csv_sum("events.csv", "hire_fee")
        erp = self._erp_sum(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_event_id": ["is", "set"]},
            field="grand_total"
        )
        results.append(self._result("Event venue hire revenue", src, erp))

        # Egg sales revenue — custom field: source_egg_sale_id
        src = self._csv_sum("egg_sales.csv", "total_amount")
        erp = self._erp_sum(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_egg_sale_id": ["is", "set"]},
            field="grand_total"
        )
        results.append(self._result("Egg sales revenue", src, erp))

        # Payment entries
        src = self._csv_sum_filtered("transactions.csv", "amount", "type", "income")
        erp = self._erp_sum(
            "Payment Entry",
            filters={"company": self.company, "docstatus": 1,
                     "payment_type": "Receive"},
            field="paid_amount"
        )
        results.append(self._result("Payment entries total", src, erp))

        # Expense journal entries — count JEs vs source expense rows
        # Comparing sums is meaningless: JE total_debit double-counts (both legs).
        # Count is the correct reconciliation metric here.
        # All JE-generating transaction types: expense, capital_injection, savings
        src = len(self._load_csv("transactions.csv").query(
            "type in ('expense', 'capital_injection', 'savings')"
        ))
        erp = self._erp_count(
            "Journal Entry",
            filters={"company": self.company, "docstatus": 1,
                     "source_transaction_id": ["is", "set"]}
        )
        results.append(self._result(
            "Journal entries (expense + savings + capital)",
            src, erp, is_count=True,
            note="All 3 transaction types import as JEs sharing source_transaction_id: 709 expense + 15 savings + 3 capital injections = 727"
        ))

        return results

    # ─────────────────────────────────────────────────────────────────────
    # Inventory Validations
    # ─────────────────────────────────────────────────────────────────────

    def _validate_inventory(self) -> list:
        results = []

        # Item count — custom field: source_item_id
        src = self._csv_count("inventory_items.csv")
        erp = self._erp_count(
            "Item",
            filters={"source_item_id": ["is", "set"]}
        )
        results.append(self._result("Inventory items", src, erp, is_count=True))

        # Stock movements — custom field: source_movement_id
        src = self._csv_count("inventory_movements.csv")
        erp = self._erp_count(
            "Stock Entry",
            filters={"docstatus": 1, "source_movement_id": ["is", "set"]}
        )
        results.append(self._result(
            "Stock movements", src, erp, is_count=True,
            note="3 movements skipped: source data issued more stock than purchased (documented)",
            expected_variance=-3
        ))

        return results

    # ─────────────────────────────────────────────────────────────────────
    # Operational Validations
    # ─────────────────────────────────────────────────────────────────────

    def _validate_operational(self) -> list:
        results = []

        # Room bookings count
        src = self._csv_count("room_bookings.csv")
        erp = self._erp_count(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_booking_id": ["is", "set"]}
        )
        results.append(self._result("Room bookings", src, erp, is_count=True))

        # Events count
        src = self._csv_count("events.csv")
        erp = self._erp_count(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_event_id": ["is", "set"]}
        )
        results.append(self._result("Event invoices", src, erp, is_count=True))

        # Egg sales count
        src = self._csv_count("egg_sales.csv")
        erp = self._erp_count(
            "Sales Invoice",
            filters={"company": self.company, "docstatus": 1,
                     "source_egg_sale_id": ["is", "set"]}
        )
        results.append(self._result("Egg sale invoices", src, erp, is_count=True))

        # Compliance documents
        src = self._csv_count("compliance_documents.csv")
        erp = self._erp_count("License", filters={})
        results.append(self._result(
            "Compliance documents", src, erp, is_count=True
        ))

        return results

    # ─────────────────────────────────────────────────────────────────────
    # ERPNext Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _erp_sum(self, doctype: str, filters: dict, field: str) -> float:
        try:
            records = self.client.get_list(
                doctype,
                filters=filters,
                fields=["name", field],
                limit_page_length=10000
            )
            return float(sum(r.get(field, 0) or 0 for r in records))
        except Exception as e:
            print(f"  ⚠ ERPNext query failed ({doctype}.{field}): {e}")
            return -1.0

    def _erp_count(self, doctype: str, filters: dict) -> int:
        try:
            records = self.client.get_list(
                doctype,
                filters=filters,
                fields=["name"],
                limit_page_length=10000
            )
            return len(records)
        except Exception as e:
            print(f"  ⚠ ERPNext query failed (count {doctype}): {e}")
            return -1

    # ─────────────────────────────────────────────────────────────────────
    # CSV Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _load_csv(self, filename: str) -> pd.DataFrame:
        if filename not in self._cache:
            self._cache[filename] = pd.read_csv(self.data_dir / filename)
        return self._cache[filename]

    def _csv_sum(self, filename: str, column: str) -> float:
        return float(self._load_csv(filename)[column].sum())

    def _csv_sum_filtered(self, filename, column, filter_col, filter_val) -> float:
        df = self._load_csv(filename)
        return float(df[df[filter_col] == filter_val][column].sum())

    def _csv_count(self, filename: str) -> int:
        return len(self._load_csv(filename))

    # ─────────────────────────────────────────────────────────────────────
    # Result Builder
    # ─────────────────────────────────────────────────────────────────────

    def _result(self, label, source, erpnext, is_count=False, note="", expected_variance=0) -> dict:
        if erpnext in (-1, -1.0):
            variance, match = None, False
            status = "❌"
        else:
            variance = erpnext - source
            match    = abs(variance - expected_variance) < 0.01
            status   = "✅" if match else "❌"

        def fmt(v):
            if v is None: return "ERROR"
            return int(v) if is_count else round(float(v), 2)

        return {
            "label":    label,
            "source":   fmt(source),
            "erpnext":  fmt(erpnext),
            "variance": fmt(variance) if variance is not None else "N/A",
            "match":    match,
            "status":   status,
            "note":     note,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Markdown Renderer
    # ─────────────────────────────────────────────────────────────────────

    def _render_markdown(self, report: dict) -> str:
        meta    = report["meta"]
        summary = report["summary"]
        lines   = []

        lines += [
            "# ERPNext Migration Validation Report", "",
            f"**Company:** {meta['company']}  ",
            f"**Generated:** {meta['generated']}  ",
            f"**Reporter Version:** {meta['version']}  ",
            "", "---", "",
        ]

        overall = ("✅ ALL CHECKS PASSED"
                   if summary["failed"] == 0
                   else f"⚠️  {summary['failed']} CHECK(S) FAILED")
        lines += [
            "## Summary", "",
            "| | |", "|---|---|",
            f"| **Overall status** | {overall} |",
            f"| **Checks passed** | {summary['passed']} / {summary['total']} |",
            f"| **Success rate** | {summary['success_rate']}% |",
            "", "---", "",
        ]

        sections = [
            ("Financial Reconciliation",   report["financial"]),
            ("Inventory Reconciliation",   report["inventory"]),
            ("Operational Reconciliation", report["operational"]),
        ]

        for title, results in sections:
            lines += [f"## {title}", "",
                      "| Status | Check | Source (CSV) | ERPNext | Variance |",
                      "|--------|-------|-------------|---------|----------|"]
            for r in results:
                note_md = f"<br>_{r['note']}_" if r["note"] else ""
                lines.append(
                    f"| {r['status']} | {r['label']}{note_md} "
                    f"| {r['source']:,} | {r['erpnext']:,} | {r['variance']} |"
                    if isinstance(r['source'], (int, float))
                    else f"| {r['status']} | {r['label']}{note_md} "
                         f"| {r['source']} | {r['erpnext']} | {r['variance']} |"
                )
            lines.append("")

        lines += [
            "---", "",
            "## Notes", "",
            "- **Source (CSV):** Ground truth — values read directly from source CSV files",
            "- **ERPNext:** Live values queried via API at report generation time",
            "- **Variance:** ERPNext minus Source. Zero = perfect reconciliation.",
            "- Stock discrepancies: 3 movements skipped (source issued more than purchased). Documented.",
            "",
            f"_Generated by ERPNext Migration Toolkit ValidationReporter v{meta['version']}_",
        ]

        return "\n".join(lines)
