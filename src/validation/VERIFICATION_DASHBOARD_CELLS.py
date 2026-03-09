# MIGRATION VERIFICATION DASHBOARD - NOTEBOOK CELLS
# Copy these cells into your wellness_centre_migration.ipynb notebook

# ============================================================================
# CELL 1: Initialize Dashboard
# ============================================================================
from validation.migration_dashboard import MigrationDashboard

dashboard = MigrationDashboard(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

print("✓ Migration Dashboard initialized")

# ============================================================================
# CELL 2: Quick Summary (Fast Check)
# ============================================================================
# Run this for a quick sanity check - shows counts and totals
summary = dashboard.quick_summary()

# ============================================================================
# CELL 3: Detailed Reconciliation (Full Verification)
# ============================================================================
# This does line-by-line comparison with CSV source data
# Checks for duplicates, missing records, amount mismatches
report = dashboard.full_reconciliation()
dashboard.print_reconciliation_report(report)

# ============================================================================
# CELL 4: Accounting Integrity Check
# ============================================================================
# Validates that all journal entries balance (debits = credits)
integrity = dashboard.validate_accounting_integrity()

# ============================================================================
# CELL 5: Outstanding Receivables Check
# ============================================================================
# Verifies all invoices have been paid
receivables = dashboard.check_outstanding_receivables()

# ============================================================================
# CELL 6: Export Verification Report
# ============================================================================
# Save verification report to file for documentation
import json
from datetime import datetime

verification_report = {
    'timestamp': datetime.now().isoformat(),
    'summary': summary,
    'detailed_reconciliation': report,
    'accounting_integrity': integrity,
    'outstanding_receivables': receivables
}

# Save as JSON
report_file = OUTPUTS_DIR / f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(report_file, 'w') as f:
    json.dump(verification_report, f, indent=2, default=str)

print(f"✓ Verification report saved: {report_file}")

# ============================================================================
# CELL 7: Quick Duplicate Check (Standalone)
# ============================================================================
# Quick check for duplicate journal entries by date+amount
print("DUPLICATE JOURNAL ENTRIES CHECK")
print("=" * 70)

all_je = client.get_list(
    "Journal Entry",
    filters={"docstatus": 1},
    fields=["name", "posting_date", "total_debit", "source_transaction_id"],
    limit_page_length=1000
)

# Check by source_transaction_id (new entries)
source_ids = [je.get('source_transaction_id') for je in all_je if je.get('source_transaction_id')]
from collections import Counter
source_id_dupes = {k: v for k, v in Counter(source_ids).items() if v > 1}

# Check by date+amount (old entries without source_transaction_id)
date_amount_pairs = [(je['posting_date'], je.get('total_debit', 0)) for je in all_je]
date_amount_dupes = {k: v for k, v in Counter(date_amount_pairs).items() if v > 1}

print(f"Total Journal Entries: {len(all_je)}")
print(f"With source_transaction_id: {len(source_ids)}")
print(f"Duplicates by source_transaction_id: {len(source_id_dupes)}")
print(f"Duplicates by date+amount: {len(date_amount_dupes)}")

if date_amount_dupes:
    total_date_amount_dupes = sum(count - 1 for count in date_amount_dupes.values())
    print(f"Total duplicate entries (date+amount): {total_date_amount_dupes}")
    print("\nFirst 10 date+amount duplicates:")
    for (date, amount), count in list(date_amount_dupes.items())[:10]:
        print(f"  {date}, KES {amount:,.0f}: {count} entries")

print("=" * 70)

# ============================================================================
# RECOMMENDED WORKFLOW
# ============================================================================
"""
RECOMMENDED VERIFICATION WORKFLOW:

1. After each phase import:
   - Run CELL 2: Quick Summary
   - Verify counts match expectations

2. After Phase 2 complete (all financial transactions):
   - Run CELL 3: Detailed Reconciliation
   - Run CELL 4: Accounting Integrity
   - Run CELL 5: Outstanding Receivables
   - Fix any issues found

3. Before creating final snapshot:
   - Run CELL 7: Duplicate Check
   - If duplicates found -> restore snapshot and re-import cleanly
   - Run CELL 6: Export Verification Report for documentation

4. After migration complete:
   - Keep verification report as proof of data integrity
   - Use Quick Summary (CELL 2) for ongoing validation
"""
