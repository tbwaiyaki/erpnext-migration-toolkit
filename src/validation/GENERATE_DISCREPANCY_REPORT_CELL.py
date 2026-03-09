# GENERATE DISCREPANCY REPORT FOR PHASE 3B
# ==========================================
# Run this cell after Phase 3B to document failed movements

# ============================================================================
# CELL: Load Discrepancy Reporter
# ============================================================================
import importlib
from validation import discrepancy_reporter

importlib.reload(discrepancy_reporter)
from validation.discrepancy_reporter import DiscrepancyReporter

print(f"✓ DiscrepancyReporter loaded: v{DiscrepancyReporter.VERSION}")

# ============================================================================
# CELL: Generate Discrepancy Report
# ============================================================================
from pathlib import Path

print("=" * 70)
print("GENERATING DISCREPANCY REPORT")
print("=" * 70)

# Initialize reporter
reporter = DiscrepancyReporter()

# Add stock movement failures (if any)
if stock_imp.results['errors']:
    reporter.add_stock_movement_failures(
        stock_imp.results['errors'],
        movements_df,
        items_df
    )

# Generate report
report_path = REPO_ROOT / 'docs' / 'phase3b_discrepancies.md'
report_text = reporter.generate_report(report_path)

print(f"\n✓ Discrepancy report generated: {report_path}")
print(reporter.get_summary_text())

print("\n" + "=" * 70)
print("PHASE 3B STATUS")
print("=" * 70)
print(f"Successfully imported: {stock_imp.results['successful']}/193 movements")
print(f"Discrepancies documented: {len(stock_imp.results['errors'])}")
print(f"Success rate: {stock_imp.results['successful']/193*100:.1f}%")
print()
print("Next steps:")
print("1. Review discrepancy report (see path above)")
print("2. Decide resolution approach per your business policies")
print("3. Mark Phase 3B as complete (190/193 with documented variances)")
print("4. Proceed to Phase 4")
print("=" * 70)

# ============================================================================
# CELL: Display Discrepancy Report Summary
# ============================================================================
# Show the report in the notebook for quick review
print("\n" + "=" * 70)
print("DISCREPANCY REPORT PREVIEW")
print("=" * 70)
print()

# Show first 50 lines of report
report_lines = report_text.split('\n')
for line in report_lines[:50]:
    print(line)

if len(report_lines) > 50:
    print(f"\n... ({len(report_lines) - 50} more lines)")
    print(f"\nFull report: {report_path}")

print("\n" + "=" * 70)

# ============================================================================
# MARKDOWN: Phase 3B Complete with Discrepancies
# ============================================================================
"""
## Phase 3B Complete (with documented discrepancies)

**Import Results:**
- ✅ Successfully imported: 190/193 stock movements (98.4% success rate)
- ⚠️ Documented discrepancies: 3 movements (insufficient stock)

**Discrepancies:**
- Item 4 (Frying Pan Small): Disposal of 3 units when only 2 purchased
- Item 25 (Water Jugs): Total breakage (14) exceeds purchases (10)

**Root Cause:** Source data quality issues (missing purchases or incorrect quantities)

**Resolution Approach:** Professional accounting practice
1. Discrepancies documented in report (not fabricated to force balance)
2. Users review report and make manual adjustments per business policies
3. Migration proceeds with known variances clearly documented

**Files Created:**
- `docs/phase3b_discrepancies.md` - Full discrepancy report

**This is the correct approach:** Preserve data integrity, document discrepancies, 
allow business users to make informed decisions about resolution.

**Status:** Phase 3B COMPLETE with known variances documented ✅

**Next:** Proceed to Phase 4 (Room Bookings)
"""
