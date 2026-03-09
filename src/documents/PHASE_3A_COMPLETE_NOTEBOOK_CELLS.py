# PHASE 3A: ITEM MASTER IMPORT - COMPLETE NOTEBOOK CELLS
# =======================================================
# User-review workflow for inventory items with UOM preparation

# ============================================================================
# MARKDOWN: Phase 3A Header
# ============================================================================
"""
# Phase 3A: Item Master Import

Import 77 inventory items into ERPNext Item Master with user-reviewed UOM mappings.

**Workflow:**
1. Discover unique UOMs from source data
2. User reviews and maps UOMs (manual step)
3. Create user-confirmed UOMs
4. Import items with validated mappings

**Why this workflow:**
- Prevents auto-creation of junk data from typos
- Gives user control over UOM standardization
- Allows consolidation of variants (pack/package → Pack)
- Reusable for any migration with any UOMs

**Expected Duration:** 5-10 minutes (including user review)
"""

# ============================================================================
# MARKDOWN: Step 1 - Discover Source UOMs
# ============================================================================
"""
## Step 1: Discover Source UOMs

Analyze all UOMs in source items data and check what exists in ERPNext.
"""

# ============================================================================
# CELL: Load UOM Preparation Module
# ============================================================================
import importlib
from setup import uom_preparation

importlib.reload(uom_preparation)
from setup.uom_preparation import UOMPreparation

print(f"✓ UOMPreparation loaded: v{UOMPreparation.VERSION}")

# ============================================================================
# CELL: Discover and Analyze UOMs
# ============================================================================
from pathlib import Path

print("=" * 70)
print("STEP 1: DISCOVERING SOURCE UOMs")
print("=" * 70)

# Initialize UOM preparation
uom_prep = UOMPreparation(client)

# Discover unique UOMs from items data
analysis = uom_prep.discover_source_uoms(items_df)

# Display review table
uom_prep.display_review_table(analysis)

print("\n✓ UOM analysis complete")
print(f"  Total unique UOMs: {len(analysis)}")
print(f"  Already exist in ERPNext: {analysis['exists_in_erpnext'].sum()}")
print(f"  Need user decision: {(~analysis['exists_in_erpnext']).sum()}")

# ============================================================================
# MARKDOWN: Step 2 - Generate Mapping Template
# ============================================================================
"""
## Step 2: Generate UOM Mapping Template

Create a YAML configuration file for user to review and edit.
"""

# ============================================================================
# CELL: Generate Mapping Template
# ============================================================================
print("=" * 70)
print("STEP 2: GENERATING MAPPING TEMPLATE")
print("=" * 70)

# Create config directory if needed
config_dir = REPO_ROOT / 'config'
config_dir.mkdir(exist_ok=True)

# Generate template
template_path = config_dir / 'uom_mappings.yaml'
uom_prep.generate_mapping_template(analysis, template_path)

print(f"\n✓ Template generated: {template_path}")
print()
print("=" * 70)
print("ACTION REQUIRED - MANUAL STEP")
print("=" * 70)
print("1. Open the file in a text editor:")
print(f"   {template_path}")
print()
print("2. Review each UOM and decide:")
print("   - Keep in 'uom_mappings' to map to existing ERPNext UOM")
print("   - Keep in 'create_new_uoms' to create new UOM")
print("   - Move between sections as needed")
print()
print("3. Save the file when done")
print()
print("4. Continue to next cell")
print("=" * 70)

# ============================================================================
# MARKDOWN: Step 3 - Review and Edit
# ============================================================================
"""
## Step 3: User Review and Edit (MANUAL STEP)

**⚠️ STOP HERE AND EDIT THE CONFIG FILE**

Open `config/uom_mappings.yaml` and review each UOM decision.

**Example decisions:**

```yaml
uom_mappings:
  piece:
    maps_to: Nos              # Map "piece" to standard ERPNext "Nos"
    items_affected: 45

create_new_uoms:
  - uom_name: Pack            # Create new "Pack" UOM
    used_by_items: 8
  - uom_name: Bundle          # Create new "Bundle" UOM
    used_by_items: 3
```

**Common mappings:**
- piece/pieces/pcs → Nos
- set/sets → Set
- pack/package/pkg → Pack (or map to Nos if packaging doesn't matter)
- kg/kilogram → Kg
- litre/liter → Litre

**When done editing, run the next cell.**
"""

# ============================================================================
# MARKDOWN: Step 4 - Apply Decisions
# ============================================================================
"""
## Step 4: Apply User Decisions

Load the edited configuration and create user-confirmed UOMs.
"""

# ============================================================================
# CELL: Load User Mappings
# ============================================================================
print("=" * 70)
print("STEP 4: LOADING USER MAPPINGS")
print("=" * 70)

# Load user-edited mappings
mappings = uom_prep.load_mappings(template_path)

print(f"✓ Loaded mappings from: {template_path}")
print()
print(f"UOM Mappings (source → ERPNext):")
for source, config in mappings.get('uom_mappings', {}).items():
    print(f"  {source:15s} → {config['maps_to']:15s} ({config['items_affected']} items)")

print()
print(f"New UOMs to Create:")
for uom_config in mappings.get('create_new_uoms', []):
    print(f"  {uom_config['uom_name']:15s} (used by {uom_config['used_by_items']} items)")

print()
print("=" * 70)
print("⚠️ CONFIRM BEFORE PROCEEDING")
print("=" * 70)
print("Review the mappings above. If correct, run next cell.")
print("If you need to make changes, edit the YAML file and re-run this cell.")
print("=" * 70)

# ============================================================================
# CELL: Create User-Confirmed UOMs
# ============================================================================
print("=" * 70)
print("CREATING USER-CONFIRMED UOMs")
print("=" * 70)

# Create new UOMs (only user-confirmed ones)
results = uom_prep.create_missing_uoms(mappings)

print()
if results['created'] > 0:
    print(f"✓ Created {results['created']} new UOMs")
if results['skipped'] > 0:
    print(f"  Skipped {results['skipped']} (already existed)")
if results['errors']:
    print(f"✗ Failed {len(results['errors'])} UOMs:")
    for err in results['errors']:
        print(f"    {err['uom']}: {err['error']}")

# Generate mapping dict for ItemImporter
uom_dict = uom_prep.get_uom_mapping_dict(mappings)

print()
print(f"✓ UOM mapping dictionary ready")
print(f"  {len(uom_dict)} mappings loaded for ItemImporter")
print("=" * 70)

# ============================================================================
# MARKDOWN: Step 5 - Import Items
# ============================================================================
"""
## Step 5: Import Items with Validated UOMs

Now import items using the user-reviewed and confirmed UOM mappings.
"""

# ============================================================================
# CELL: Reload ItemImporter
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

# Initialize importer with user-confirmed UOM mappings
item_imp = ItemImporter(
    client=client,
    company="Wellness Centre",
    default_warehouse="Stores - WC",
    uom_mappings=uom_dict  # Pass user-reviewed mappings
)

# Import items
results = item_imp.import_batch(items_df, categories_df)

# Show summary
print()
print(item_imp.get_summary())

notify('complete')

# ============================================================================
# MARKDOWN: Verify Results
# ============================================================================
"""
## Verify Phase 3A Results

Check that all items imported successfully with correct UOMs.
"""

# ============================================================================
# CELL: Verify Items
# ============================================================================
print("=" * 70)
print("PHASE 3A VERIFICATION")
print("=" * 70)

# Check items imported
items = client.get_list(
    "Item",
    filters={"source_item_id": ["is", "set"]},
    fields=["name", "item_name", "stock_uom", "item_group"],
    limit_page_length=100
)

print(f"\nItems imported: {len(items)} (expected 77)")

# Check UOMs used
uoms_used = {}
for item in items:
    uom = item['stock_uom']
    uoms_used[uom] = uoms_used.get(uom, 0) + 1

print(f"\nUOMs in use:")
for uom, count in sorted(uoms_used.items(), key=lambda x: -x[1]):
    print(f"  {uom}: {count} items")

# Check item groups
item_groups = client.get_list(
    "Item Group",
    filters={"parent_item_group": "All Item Groups"},
    fields=["name"],
    limit_page_length=20
)

print(f"\nItem Groups created: {len(item_groups)} (expected 8)")
for group in item_groups:
    print(f"  - {group['name']}")

# Sample items by category
print(f"\nSample items by category:")
for cat_id, cat_name in [(1, 'Kitchen'), (2, 'Dining Cutlery'), (5, 'Linens & Fabrics')]:
    cat_items = [i for i in items if i['item_group'] == cat_name]
    if cat_items:
        sample = cat_items[0]
        print(f"  {cat_name}: {sample['item_name']} ({sample['stock_uom']})")

print("=" * 70)

# ============================================================================
# MARKDOWN: Phase 3A Complete
# ============================================================================
"""
## Phase 3A Complete ✅

**Achievements:**
- All source UOMs reviewed and mapped by user
- User-confirmed UOMs created in ERPNext
- 77 items imported with validated UOM mappings
- 8 item groups created
- Zero auto-created junk data

**Key Files Created:**
- `config/uom_mappings.yaml` - User-reviewed UOM decisions

**Next Steps:**
1. Review verification results above
2. If all correct, proceed to Phase 3B (Stock Movements)
3. If issues found, restore snapshot and adjust mappings

**Phase 3B will use the items created here to import 193 stock movements.**
"""

# ============================================================================
# END OF PHASE 3A CELLS
# ============================================================================
