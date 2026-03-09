# PHASE 3: INVENTORY MANAGEMENT - NOTEBOOK CELLS
# =================================================
# Add these cells to your notebook after Phase 2

# ============================================================================
# MARKDOWN: Phase 3 Header
# ============================================================================
"""
# Phase 3: Inventory Management

Import physical inventory items and stock movements into ERPNext.

**Data:**
- 77 inventory items (kitchen equipment, furniture, linens, etc.)
- 8 item categories (Kitchen, Dining, Electrical, Events, Linens, Furniture, Garden, Cleaning)
- 193 stock movements (purchases, breakage, loss, disposal, adjustments)

**ERPNext Mapping:**
- Items → Item Master
- Categories → Item Groups
- Movements → Stock Entry (Material Receipt/Issue)

**Expected Duration:** 2-3 minutes
"""

# ============================================================================
# MARKDOWN: Prerequisites
# ============================================================================
"""
## Prerequisites for Phase 3

**Custom Fields Required:**
1. Item: `source_item_id` (duplicate detection)
2. Stock Entry: `source_movement_id` (duplicate detection)

**Warehouse Required:**
- Default warehouse must exist: "Stores - WC"

**Data Required:**
- inventory_items.csv loaded
- inventory_categories.csv loaded
- inventory_movements.csv loaded
"""

# ============================================================================
# CELL: Create Custom Field - Item.source_item_id
# ============================================================================
print("Creating custom field: Item - source_item_id")

custom_field = {
    "doctype": "Custom Field",
    "dt": "Item",
    "fieldname": "source_item_id",
    "label": "Source Item ID",
    "fieldtype": "Data",
    "insert_after": "item_code",
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
# CELL: Verify Warehouse Exists
# ============================================================================
print("Verifying default warehouse exists...")

try:
    warehouse = client.get_doc("Warehouse", "Stores - WC")
    print(f"✓ Warehouse exists: {warehouse['name']}")
except Exception as e:
    print(f"✗ Warehouse not found, creating...")
    
    warehouse_doc = {
        "doctype": "Warehouse",
        "warehouse_name": "Stores",
        "company": "Wellness Centre",
        "is_group": 0
    }
    
    created = client.insert(warehouse_doc)
    print(f"✓ Created warehouse: {created['name']}")

# ============================================================================
# CELL: Load Inventory Data
# ============================================================================
import pandas as pd

print("Loading inventory data...")

items_df = pd.read_csv(DATA_DIR / 'inventory_items.csv')
categories_df = pd.read_csv(DATA_DIR / 'inventory_categories.csv')
movements_df = pd.read_csv(DATA_DIR / 'inventory_movements.csv')

print(f"✓ Loaded:")
print(f"  Items: {len(items_df)}")
print(f"  Categories: {len(categories_df)}")
print(f"  Movements: {len(movements_df)}")

# ============================================================================
# MARKDOWN: Phase 3A Header
# ============================================================================
"""
## Phase 3A: Import Items

Import 77 inventory items into Item Master with proper configuration.
"""

# ============================================================================
# CELL: Reload Phase 3A Modules
# ============================================================================
import importlib
from orchestration import item_importer

importlib.reload(item_importer)
from orchestration.item_importer import ItemImporter

print(f"✓ ItemImporter loaded: v{ItemImporter.VERSION}")

# ============================================================================
# CELL: Import Items
# ============================================================================
print("=" * 70)
print("PHASE 3A: IMPORTING ITEMS")
print("=" * 70)

# Initialize importer
item_imp = ItemImporter(
    client=client,
    company="Wellness Centre",
    default_warehouse="Stores - WC"
)

# Import items
results = item_imp.import_batch(items_df, categories_df)

# Show summary
print()
print(item_imp.get_summary())

notify('complete')

# ============================================================================
# MARKDOWN: Phase 3B Header
# ============================================================================
"""
## Phase 3B: Import Stock Movements

Import 193 inventory movements (purchases, breakage, loss, disposal, adjustments).
"""

# ============================================================================
# CELL: Reload Phase 3B Modules
# ============================================================================
import importlib
from orchestration import stock_movement_importer

importlib.reload(stock_movement_importer)
from orchestration.stock_movement_importer import StockMovementImporter

print(f"✓ StockMovementImporter loaded: v{StockMovementImporter.VERSION}")

# ============================================================================
# CELL: Import Stock Movements
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

notify('complete')

# ============================================================================
# MARKDOWN: Verification
# ============================================================================
"""
## Phase 3 Verification

Verify all items and stock movements imported correctly.
"""

# ============================================================================
# CELL: Verify Phase 3 Results
# ============================================================================
print("=" * 70)
print("PHASE 3 VERIFICATION")
print("=" * 70)

# Check items
items = client.get_list(
    "Item",
    filters={"source_item_id": ["is", "set"]},
    fields=["name", "item_name", "stock_uom"],
    limit_page_length=100
)

print(f"\nItems imported: {len(items)} (expected 77)")

# Check item groups
item_groups = client.get_list(
    "Item Group",
    filters={"parent_item_group": "All Item Groups"},
    fields=["name"],
    limit_page_length=20
)

print(f"Item Groups created: {len(item_groups)} (expected 8)")

# Check stock entries
stock_entries = client.get_list(
    "Stock Entry",
    filters={"docstatus": 1, "source_movement_id": ["is", "set"]},
    fields=["name", "stock_entry_type", "posting_date"],
    limit_page_length=200
)

print(f"Stock Entries imported: {len(stock_entries)} (expected 193)")

# Group by type
by_type = {}
for entry in stock_entries:
    entry_type = entry['stock_entry_type']
    by_type[entry_type] = by_type.get(entry_type, 0) + 1

print(f"\nStock Entries by type:")
for etype, count in by_type.items():
    print(f"  {etype}: {count}")

# Check stock balance for sample item
sample_item = "ITM-0001"  # Cooking Pot (Large)
try:
    stock_balance = client.get_list(
        "Stock Ledger Entry",
        filters={"item_code": sample_item},
        fields=["posting_date", "voucher_type", "actual_qty", "qty_after_transaction"],
        limit_page_length=10
    )
    
    if stock_balance:
        final_qty = stock_balance[-1]['qty_after_transaction']
        print(f"\nSample item ({sample_item}) final stock: {final_qty}")
except:
    print(f"\nCould not retrieve stock balance for {sample_item}")

print("=" * 70)

# ============================================================================
# MARKDOWN: Phase 3 Complete
# ============================================================================
"""
## Phase 3 Complete ✅

**Achievements:**
- 77 items imported into Item Master
- 8 item groups created
- 193 stock movements processed
- Stock balances calculated

**Next:** Create snapshot and proceed to Phase 4 (Room Bookings)

**Snapshot command:**
```bash
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud snapshot "Phase 3 complete - inventory"
```
"""

# ============================================================================
# END OF PHASE 3 CELLS
# ============================================================================
