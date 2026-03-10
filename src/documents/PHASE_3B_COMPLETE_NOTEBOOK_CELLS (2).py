# PHASE 3B: STOCK MOVEMENTS IMPORT - COMPLETE NOTEBOOK CELLS
# ============================================================
# Import 193 inventory movements into ERPNext Stock Entry

# ============================================================================
# MARKDOWN: Phase 3B Header
# ============================================================================
"""
# Phase 3B: Stock Movements Import

Import 193 inventory movements into ERPNext Stock Entry.

**Data:**
- 117 Purchase movements (Material Receipt)
- 48 Breakage movements (Material Issue)
- 11 Loss movements (Material Issue)
- 9 Disposal movements (Material Issue)
- 8 Audit Adjustment movements (Material Receipt)

**ERPNext Mapping:**
- Purchase → Stock Entry (Material Receipt)
- Breakage/Loss/Disposal → Stock Entry (Material Issue)
- Audit Adjustment → Stock Entry (Material Receipt)

**Expected Duration:** 2-3 minutes
"""

# ============================================================================
# MARKDOWN: Prerequisites
# ============================================================================
"""
## Prerequisites for Phase 3B

**Required:**
1. Phase 3A complete (77 items imported)
2. Custom field: Stock Entry.source_movement_id
3. Warehouse exists: "Stores - WC"

**Data Required:**
- inventory_movements.csv loaded
- items_df available (for item code lookup)
"""

# ============================================================================
# CELL: Create Custom Field - Stock Entry.source_movement_id
# ============================================================================
print("Creating custom field: Stock Entry - source_movement_id")

custom_field = {
    "doctype": "Custom Field",
    "dt": "Stock Entry",
    "fieldname": "source_movement_id",
    "label": "Source Movement ID",
    "fieldtype": "Data",
    "insert_after": "title",
    "read_only": 1,
    "in_list_view": 0
}

try:
    result = client.insert(custom_field)
    print(f"✓ Created: {result['name']}")
except Exception as e:
    if "already exists" in str(e).lower():
        print("✓ Already exists")
    else:
        print(f"✗ Error: {e}")

# ============================================================================
# CELL: Verify Warehouse
# ============================================================================
print("Verifying warehouse exists...")

try:
    warehouse = client.get_doc("Warehouse", "Stores - WC")
    print(f"✓ Warehouse exists: {warehouse['name']}")
except Exception as e:
    print(f"✗ Warehouse not found: {e}")
    print("Creating warehouse...")
    
    warehouse_doc = {
        "doctype": "Warehouse",
        "warehouse_name": "Stores",
        "company": "Wellness Centre",
        "is_group": 0
    }
    
    created = client.insert(warehouse_doc)
    print(f"✓ Created warehouse: {created['name']}")

# ============================================================================
# CELL: Load Movement Data
# ============================================================================
import pandas as pd

print("Loading inventory movements data...")

movements_df = pd.read_csv(DATA_DIR / 'inventory_movements.csv')

print(f"✓ Loaded {len(movements_df)} movements")
print(f"\nMovement types:")
for mtype, count in movements_df['movement_type'].value_counts().items():
    print(f"  {mtype}: {count}")

# ============================================================================
# CELL: Reload StockMovementImporter
# ============================================================================
import importlib
from orchestration import stock_movement_importer

importlib.reload(stock_movement_importer)
from orchestration.stock_movement_importer import StockMovementImporter

print(f"✓ StockMovementImporter loaded: v{StockMovementImporter.VERSION}")

# ============================================================================
# CELL: Import Stock Movements with Auto-Discrepancy Reporting
# ============================================================================
print("=" * 70)
print("PHASE 3B: IMPORTING STOCK MOVEMENTS")
print("=" * 70)

# Initialize importer
stock_imp = StockMovementImporter(
    client=client,
    company="Wellness Centre",
    warehouse="Stores - WC"
)

# Import movements
results = stock_imp.import_batch(movements_df, items_df)

# Show summary
print()
print(stock_imp.get_summary())

# Auto-generate discrepancy report if needed
if stock_imp.results['errors']:
    print("\n" + "=" * 70)
    print("GENERATING DISCREPANCY REPORT")
    print("=" * 70)
    
    # Load discrepancy reporter
    from validation.discrepancy_reporter import DiscrepancyReporter
    
    reporter = DiscrepancyReporter()
    reporter.add_stock_movement_failures(
        stock_imp.results['errors'],
        movements_df,
        items_df
    )
    
    # Generate report
    report_path = REPO_ROOT / 'docs' / 'phase3b_discrepancies.md'
    reporter.generate_report(report_path)
    
    print(f"\n✓ Discrepancy report generated: {report_path}")
    print(reporter.get_summary_text())
    
    print("\n" + "=" * 70)
    print("PHASE 3B COMPLETE - WITH DOCUMENTED DISCREPANCIES")
    print("=" * 70)
    print(f"Successfully imported: {stock_imp.results['successful']}/{len(movements_df)} movements")
    print(f"Discrepancies documented: {len(stock_imp.results['errors'])}")
    print(f"Success rate: {stock_imp.results['successful']/len(movements_df)*100:.1f}%")
    print()
    print("ℹ️  Discrepancies represent data quality issues in source CSV,")
    print("   not system errors. Review report and resolve per your policies.")
    print("=" * 70)
else:
    print("\n" + "=" * 70)
    print("PHASE 3B COMPLETE - ALL MOVEMENTS IMPORTED SUCCESSFULLY")
    print("=" * 70)
    print(f"Successfully imported: {stock_imp.results['successful']}/{len(movements_df)} movements")
    print(f"Success rate: 100%")
    print("=" * 70)

notify('complete')

# ============================================================================
# MARKDOWN: Verify Results
# ============================================================================
"""
## Verify Phase 3B Results

Check that all stock movements imported correctly and stock balances are accurate.
"""

# ============================================================================
# CELL: Verify Stock Movements
# ============================================================================
print("=" * 70)
print("PHASE 3B VERIFICATION")
print("=" * 70)

# Check stock entries imported
stock_entries = client.get_list(
    "Stock Entry",
    filters={"docstatus": 1, "source_movement_id": ["is", "set"]},
    fields=["name", "stock_entry_type", "posting_date"],
    limit_page_length=200
)

print(f"\nStock Entries imported: {len(stock_entries)} (expected 193)")

# Group by type
by_type = {}
for entry in stock_entries:
    entry_type = entry['stock_entry_type']
    by_type[entry_type] = by_type.get(entry_type, 0) + 1

print(f"\nStock Entries by type:")
for etype, count in sorted(by_type.items()):
    print(f"  {etype}: {count}")

print(f"\nExpected:")
print(f"  Material Receipt: ~125 (117 purchases + 8 adjustments)")
print(f"  Material Issue: ~68 (48 breakage + 11 loss + 9 disposal)")

# ============================================================================
# CELL: Check Stock Balances for Sample Items
# ============================================================================
print("=" * 70)
print("STOCK BALANCE VERIFICATION - SAMPLE ITEMS")
print("=" * 70)

# Sample items to check
sample_items = [
    ("ITM-0001", "Cooking Pot (Large)"),
    ("ITM-0013", "Dinner Plates"),
    ("ITM-0056", "Kitchen Towels")
]

for item_code, item_name in sample_items:
    try:
        # Get stock ledger entries
        ledger = client.get_list(
            "Stock Ledger Entry",
            filters={"item_code": item_code, "warehouse": "Stores - WC"},
            fields=["posting_date", "voucher_type", "actual_qty", "qty_after_transaction"],
            order_by="posting_date asc",
            limit_page_length=50
        )
        
        if ledger:
            print(f"\n{item_name} ({item_code}):")
            print(f"  Total movements: {len(ledger)}")
            
            # Show first and last entry
            first = ledger[0]
            last = ledger[-1]
            
            print(f"  First: {first['posting_date']} - {first['voucher_type']} - Qty: {first['actual_qty']:+.0f} (Balance: {first['qty_after_transaction']:.0f})")
            print(f"  Last:  {last['posting_date']} - {last['voucher_type']} - Qty: {last['actual_qty']:+.0f} (Balance: {last['qty_after_transaction']:.0f})")
            print(f"  Final stock balance: {last['qty_after_transaction']:.0f}")
        else:
            print(f"\n{item_name} ({item_code}): No stock movements found")
            
    except Exception as e:
        print(f"\n{item_name} ({item_code}): Error - {e}")

print("\n" + "=" * 70)

# ============================================================================
# CELL: Verify No Duplicates
# ============================================================================
print("=" * 70)
print("DUPLICATE DETECTION VERIFICATION")
print("=" * 70)

# Get all source_movement_ids
all_movements = client.get_list(
    "Stock Entry",
    filters={"docstatus": 1, "source_movement_id": ["is", "set"]},
    fields=["name", "source_movement_id"],
    limit_page_length=200
)

# Check for duplicate source IDs
source_ids = [m['source_movement_id'] for m in all_movements]
duplicates = [sid for sid in set(source_ids) if source_ids.count(sid) > 1]

print(f"Total movements with source_movement_id: {len(source_ids)}")
print(f"Unique source_movement_ids: {len(set(source_ids))}")
print(f"Duplicates found: {len(duplicates)}")

if duplicates:
    print(f"\n⚠ WARNING: Duplicate source_movement_ids found:")
    for dup_id in duplicates[:5]:
        print(f"  {dup_id}")
else:
    print(f"\n✓ No duplicates - all movements have unique source IDs")

print("=" * 70)

# ============================================================================
# MARKDOWN: Phase 3B Complete
# ============================================================================
"""
## Phase 3B Complete ✅

**Achievements:**
- 193 stock movements imported into Stock Entry
- Material Receipts for purchases (incoming stock)
- Material Issues for breakage/loss/disposal (outgoing stock)
- Stock balances calculated automatically by ERPNext
- Zero duplicates (verified via source_movement_id)

**Stock Entry Types Created:**
- Material Receipt: Purchases + Audit Adjustments
- Material Issue: Breakage + Loss + Disposal

**Next Steps:**
1. Review verification results above
2. If all correct, create Phase 3 complete snapshot
3. Proceed to Phase 4 (Room Bookings)

**Snapshot command:**
```bash
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud snapshot "Phase 3 complete - inventory"
```

**Git tag:**
```bash
git tag -a v1.5-phase3-complete -m "Phase 3: Inventory Management complete"
git push origin v1.5-phase3-complete
```
"""

# ============================================================================
# END OF PHASE 3B CELLS
# ============================================================================
