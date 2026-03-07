# Reset to Pristine - Complete Checklist

**Purpose:** Clean reset for proper AccountRegistry architecture  
**Estimated Time:** 2-3 hours (including migration re-run)  
**Date:** March 7, 2026

---

## Prerequisites

**Have ready:**
- [ ] Host server SSH access
- [ ] JupyterLab access
- [ ] ERPNext web UI access (well.rosslyn.cloud)
- [ ] Git credentials for pushing current state
- [ ] Latest toolkit code (will be in git)

---

## Phase 1: Save Current State (5 minutes)

### Step 1.1: Git Commit Current Work

```bash
# In JupyterLab terminal
cd ~/work/ERP/emt

# Check what's changed
git status

# Add all changes
git add -A

# Commit with detailed message
git commit -m "Pre-reset checkpoint: Phase 1 complete, AccountRegistry needed

Phase 1 Completed (will be redone):
- 220 Sales Invoices imported (KES 2.6M)
- 219 Payment Entries imported
- Custom field 'original_invoice_number' working
- Account structure: M-Pesa - WC, Bank - KCB - WC, Cash - WC

Phase 2 Preparation (complete):
- AccountMapper built and tested
- 17 expense accounts created
- ExpenseImporter tested (hard-coded accounts discovered)

Issues Found:
- PaymentEntryImporter has hard-coded PAYMENT_ACCOUNT_MAP
- ExpenseImporter has hard-coded PAYMENT_ACCOUNT_MAP
- Account names differ between sessions
- Violates reusability (won't work for Tanzania, Uganda, etc.)

Solution:
- Build AccountRegistry for dynamic account discovery
- Update all importers to use registry
- Reset to pristine snapshot for clean rebuild
- Re-run Phase 1 & 2 with proper architecture

Files in this commit:
- PaymentEntryImporter v3.1 (has hard-coding)
- ExpenseImporter v1.0 (has hard-coding)
- AccountMapper (working correctly)
- Test notebooks and results

Next steps after reset:
1. Implement AccountRegistry
2. Update importers to use registry
3. Create accounts via registry
4. Re-run Phase 1 (15 min)
5. Run Phase 2 (20 min)
6. Continue to Phase 3+

Reference documents:
- SESSION_CONTINUATION_PROMPT_v2.md
- AccountRegistry_Design.md"

# Push to remote
git push origin main

# Tag this state
git tag -a v1.1.1-pre-accountregistry-reset -m "Pre-reset checkpoint

Phase 1 complete but needs architectural refactoring.
Hard-coded account names prevent reusability.
Resetting to pristine to build AccountRegistry properly."

git push origin v1.1.1-pre-accountregistry-reset
```

**✓ Current work saved to git**

---

## Phase 2: Prepare Documentation (Already Complete)

**Documents created:**
- [x] SESSION_CONTINUATION_PROMPT_v2.md (comprehensive)
- [x] AccountRegistry_Design.md (full architecture)
- [x] This reset checklist

**These are in `/mnt/user-data/outputs/` - copy to toolkit repo:**

```bash
cd ~/work/ERP/emt

# Create docs directory if needed
mkdir -p docs/architecture

# Copy documents
cp /path/to/SESSION_CONTINUATION_PROMPT_v2.md SESSION_CONTINUATION_PROMPT.md
cp /path/to/AccountRegistry_Design.md docs/architecture/
cp /path/to/RESET_CHECKLIST.md docs/

# Commit documentation
git add SESSION_CONTINUATION_PROMPT.md docs/
git commit -m "Add: Session continuation prompt v2 + AccountRegistry design

- Updated continuation prompt with Phase 1 & 2 learnings
- Full AccountRegistry architecture specification
- Reset checklist for clean rebuild
- Documents reason for reset (eliminate hard-coding)"

git push origin main
```

**✓ Documentation committed to git**

---

## Phase 3: Restore Pristine Snapshot (2 minutes)

### Step 3.1: List Available Snapshots

```bash
# On host server (SSH)
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud list
```

**Expected output:**
```
Snapshots for well.rosslyn.cloud:
  20260307_144732           1.1 MB  (Phase 1 - wrong accounts, DON'T USE)
  20260304_083504           0.9 MB  (Pristine - USE THIS)
```

### Step 3.2: Restore Pristine Snapshot

```bash
# On host server
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud restore 20260304_083504
```

**Expected output:**
```
Restoring snapshot: 20260304_083504
  Stopping site...
  Restoring database...
  Restoring files...
  Starting site...
✓ Snapshot restored successfully
```

**⚠️ WARNING:** This will DELETE all current data:
- 220 invoices (will be re-imported in ~5 minutes)
- 219 payments (will be re-imported in ~10 minutes)
- All accounts created today
- API keys (will need to regenerate)

**✓ Snapshot restored to pristine state**

---

## Phase 4: Post-Restore ERPNext Setup (10 minutes)

### Step 4.1: Login and Verify

1. Open browser: https://well.rosslyn.cloud
2. Login with admin credentials
3. Verify clean state (no transactions)

### Step 4.2: Update Fiscal Years

**Go to:** Setup → Accounting → Fiscal Year

**Create/Update fiscal years:**
- 2024: 2024-01-01 to 2024-12-31
- 2025: 2025-01-01 to 2025-12-31  
- 2026: 2026-01-01 to 2026-12-31

**✓ Fiscal years configured**

### Step 4.3: Generate New API Keys

1. Go to: User menu → My Settings → API Access
2. Click: Generate Keys
3. Copy API Key and API Secret

**Save to password manager!**

**✓ API keys generated**

### Step 4.4: Update Connection Config

**Edit:** `~/work/ERP/emt/config/erpnext_connection.yaml`

```yaml
url: "http://erpnext-frontend:8080"
site: "well.rosslyn.cloud"
api_key: "NEW_API_KEY_HERE"
api_secret: "NEW_API_SECRET_HERE"
host_header: "well.rosslyn.cloud"
```

**✓ Connection config updated**

### Step 4.5: Create Custom Field

**CRITICAL - Must do before importing invoices!**

**Go to:** Customize → Customize Form → Sales Invoice

**Add Custom Field:**
```
Fieldname: original_invoice_number
Label: Original Invoice Number
Fieldtype: Data
Insert After: naming_series
Read Only: ✓ (checked)
Allow on Submit: ✓ (checked)
In List View: ✓ (checked)
In Standard Filter: ✓ (checked)
```

**Click:** Update

**✓ Custom field created**

### Step 4.6: Test Connection from JupyterLab

```python
# In JupyterLab notebook
import yaml
from frappeclient import FrappeClient

# Load config
with open('config/erpnext_connection.yaml') as f:
    config = yaml.safe_load(f)

# Create client
client = FrappeClient(config['url'])
client.authenticate(config['api_key'], config['api_secret'])

# Add Host header
client.session.headers.update({"Host": config['host_header']})

# Test
company = client.get_doc("Company", "Wellness Centre")
print(f"✓ Connected to: {company['company_name']}")
print(f"  Default Currency: {company['default_currency']}")
```

**Expected output:**
```
✓ Connected to: Wellness Centre
  Default Currency: KES
```

**✓ Connection verified**

---

## Phase 5: Implement AccountRegistry (30 minutes)

### Step 5.1: Create AccountRegistry File

**Create:** `~/work/ERP/emt/src/orchestration/account_registry.py`

**Copy implementation from:** `AccountRegistry_Design.md`

**Full code is in the design document - copy the complete class.**

**✓ AccountRegistry implemented**

### Step 5.2: Add Unit Tests (Optional but Recommended)

**Create:** `~/work/ERP/emt/tests/test_account_registry.py`

**Basic test structure:**
```python
import pytest
from unittest.mock import Mock
from orchestration.account_registry import AccountRegistry

def test_discover_payment_account():
    # Test basic discovery
    pass

def test_fuzzy_matching():
    # Test smart matching
    pass

def test_ensure_account_creation():
    # Test account creation
    pass
```

**✓ Tests added (or skipped for now)**

### Step 5.3: Git Commit

```bash
cd ~/work/ERP/emt

git add src/orchestration/account_registry.py
git commit -m "Add: AccountRegistry v1.0 - Dynamic account discovery

- Eliminates hard-coded account names
- Smart fuzzy matching for payment methods
- Works with ANY country/naming convention
- Caching for performance
- Support for account creation
- Single source of truth for account lookups

Key methods:
- get_payment_account(payment_method) - Auto-discover
- ensure_payment_account() - Create if missing
- get_expense_account() - Expense account lookup

Next: Update PaymentEntryImporter and ExpenseImporter to use registry"

git push origin main
```

**✓ AccountRegistry committed**

---

## Phase 6: Update Importers to Use Registry (20 minutes)

### Step 6.1: Update PaymentEntryImporter

**Edit:** `~/work/ERP/emt/src/orchestration/payment_entry_importer.py`

**Changes:**

1. **Update imports:**
```python
from orchestration.account_registry import AccountRegistry
```

2. **Remove PAYMENT_ACCOUNT_MAP constant** (delete entire dict)

3. **Update __init__:**
```python
def __init__(self, client: FrappeClient, company: str, registry: AccountRegistry):
    self.client = client
    self.company = company
    self.registry = registry  # Add registry
    self.results = {...}
```

4. **Update _build_payment_doc:**
```python
def _build_payment_doc(self, pay_row, invoice):
    payment_method = pay_row.get('payment_method', 'Cash')
    
    # Use registry instead of hard-coded map
    paid_to_account = self.registry.get_payment_account(payment_method)
    
    doc = {
        "doctype": "Payment Entry",
        "paid_to": paid_to_account,  # Dynamic!
        # ... rest unchanged
    }
```

5. **Update VERSION:**
```python
VERSION = "3.2-with-accountregistry"
```

**✓ PaymentEntryImporter updated**

### Step 6.2: Update ExpenseImporter

**Edit:** `~/work/ERP/emt/src/orchestration/expense_importer.py`

**Same changes:**
1. Remove PAYMENT_ACCOUNT_MAP
2. Add registry parameter to __init__
3. Use registry.get_payment_account() in build_journal_entry()
4. Update VERSION to "1.1-with-accountregistry"

**✓ ExpenseImporter updated**

### Step 6.3: Git Commit

```bash
git add src/orchestration/payment_entry_importer.py src/orchestration/expense_importer.py

git commit -m "Update: Importers to use AccountRegistry (remove hard-coding)

PaymentEntryImporter v3.2:
- Removed PAYMENT_ACCOUNT_MAP constant
- Added registry parameter
- Uses registry.get_payment_account() for dynamic discovery
- No more hard-coded account names

ExpenseImporter v1.1:
- Removed PAYMENT_ACCOUNT_MAP constant
- Added registry parameter
- Uses registry.get_payment_account() for dynamic discovery

Benefits:
- Works with ANY account naming convention
- Portable across countries (Kenya, Tanzania, Uganda, etc.)
- Single source of truth for account logic
- Easy to test and maintain

Breaking change: All importers now require AccountRegistry instance"

git push origin main
```

**✓ Importers updated and committed**

---

## Phase 7: Create Accounts via Registry (5 minutes)

### Step 7.1: Initialize Registry and Create Accounts

**In JupyterLab notebook:**

```python
from orchestration.account_registry import AccountRegistry

# Create registry
registry = AccountRegistry(client, "Wellness Centre")

# Create payment accounts (idempotent - safe to run multiple times)
print("Creating payment accounts...")

# M-Pesa
mpesa = registry.ensure_payment_account(
    payment_method="M-Pesa",
    account_name="M-Pesa",
    account_type="Bank",
    parent_account="Bank Accounts - WC"
)
print(f"✓ M-Pesa account: {mpesa}")

# Bank Transfer (KCB)
bank = registry.ensure_payment_account(
    payment_method="Bank Transfer",
    account_name="Bank - KCB",
    account_type="Bank",
    parent_account="Bank Accounts - WC"
)
print(f"✓ Bank account: {bank}")

# Cash
cash = registry.ensure_payment_account(
    payment_method="Cash",
    account_type="Cash"
)
print(f"✓ Cash account: {cash}")

print("\n✓ All payment accounts created")

# Verify they can be discovered
print("\nVerifying discovery:")
print(f"  M-Pesa → {registry.get_payment_account('M-Pesa')}")
print(f"  Bank Transfer → {registry.get_payment_account('Bank Transfer')}")
print(f"  Cash → {registry.get_payment_account('Cash')}")
```

**Expected output:**
```
Creating payment accounts...
✓ M-Pesa account: M-Pesa - WC
✓ Bank account: Bank - KCB - WC
✓ Cash account: Cash - WC

✓ All payment accounts created

Verifying discovery:
  M-Pesa → M-Pesa - WC
  Bank Transfer → Bank - KCB - WC
  Cash → Cash - WC
```

**✓ Payment accounts created and verified**

---

## Phase 8: Run Prerequisites and Master Data (5 minutes)

**Run existing cells from notebook:**

```python
# Cell: Run Prerequisites Checker
from orchestration.prerequisites_checker import PrerequisitesChecker

checker = PrerequisitesChecker(client, "Wellness Centre")
results = checker.check_all()
checker.print_results()

# Expected: All checks pass
```

```python
# Cell: Create Master Data
from orchestration.master_data_creator import MasterDataCreator

creator = MasterDataCreator(client, "Wellness Centre")
results = creator.create_all()
print(creator.get_summary())

# Expected: 13 Customers, 9 Suppliers, 10 Items, 4 UOMs created
```

**✓ Prerequisites checked and master data created**

---

## Phase 9: Re-run Phase 1 (15 minutes)

### Step 9.1: Import Sales Invoices

```python
# Cell: Phase 1A - Sales Invoices
from orchestration.sales_invoice_importer import SalesInvoiceImporter

importer = SalesInvoiceImporter(client, "Wellness Centre")

results = importer.import_batch(
    invoices_df=invoices_df,
    invoice_items_df=items_df,
    contacts_df=contacts_df
)

print(importer.get_summary())

# Expected: 220 successful, 0 failed
```

**✓ 220 invoices imported**

### Step 9.2: Import Payment Entries

```python
# Cell: Phase 1B - Payment Entries
from orchestration.payment_entry_importer import PaymentEntryImporter

# Pass registry to importer (NEW!)
importer = PaymentEntryImporter(
    client=client,
    company="Wellness Centre",
    registry=registry  # Using AccountRegistry
)

results = importer.import_batch(
    transactions_df=transactions_df,
    invoices_df=invoices_df
)

print(importer.get_summary())

# Expected: 219 successful, 1 skipped (already paid), 0 failed
```

**✓ 219 payments imported**

### Step 9.3: Verify Phase 1

```python
# Verify all invoices imported
invoices = client.get_list(
    "Sales Invoice",
    filters={"docstatus": 1},
    fields=["name", "grand_total", "outstanding_amount"],
    limit_page_length=999
)

print(f"Total invoices: {len(invoices)}")
total_amount = sum(inv['grand_total'] for inv in invoices)
total_outstanding = sum(inv['outstanding_amount'] for inv in invoices)

print(f"Total Amount: KES {total_amount:,.2f}")
print(f"Outstanding: KES {total_outstanding:,.2f}")

# Expected: 220 invoices, KES 2,589,840, Outstanding KES 0
```

**✓ Phase 1 verified complete**

---

## Phase 10: Create Phase 1 Snapshot (1 minute)

```bash
# On host server
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud snapshot

# Note the snapshot ID (e.g., 20260307_153045)
```

**Document this snapshot:**
- **Label:** Phase 1 Complete (Clean AccountRegistry Architecture)
- **Contains:** 220 invoices + 219 payments
- **Accounts:** M-Pesa - WC, Bank - KCB - WC, Cash - WC
- **Architecture:** AccountRegistry v1.0 in place
- **Use:** Baseline for Phase 2+

**✓ Phase 1 snapshot created**

---

## Phase 11: Run Phase 2 (30 minutes)

**Now ready for clean Phase 2 with proper architecture!**

### Step 11.1: Map Expense Categories

```python
from orchestration.account_mapper import AccountMapper

config_file = REPO_ROOT / 'config' / 'account_mappings.yaml'
mapper = AccountMapper(config_file=config_file, company="Wellness Centre")

expense_mappings = mapper.map_categories(categories_df, transaction_type='expense')
print(f"Mapped {len(expense_mappings)} expense categories")
```

### Step 11.2: Create Expense Accounts

```python
results = mapper.create_missing_accounts(client, expense_mappings)
print(f"Created: {len(results['created'])} accounts")
```

### Step 11.3: Import Expenses

```python
from orchestration.expense_importer import ExpenseImporter

# Pass registry (NEW!)
expense_imp = ExpenseImporter(
    client=client,
    company="Wellness Centre",
    registry=registry  # Using AccountRegistry
)

results = expense_imp.import_expenses(
    transactions_df=tx,
    account_mappings=expense_mappings,
    auto_submit=True
)

expense_imp.print_summary()

# Expected: 709 successful, 0 failed, KES 4,363,477
```

**✓ Phase 2 complete with clean architecture**

---

## Phase 12: Final Verification and Snapshot (5 minutes)

### Step 12.1: Verify All Data

```python
# Check totals
print("FINAL VERIFICATION:")
print("="*70)

# Invoices
invoices = client.get_list("Sales Invoice", filters={"docstatus": 1}, limit_page_length=999)
print(f"Sales Invoices: {len(invoices)}")

# Payments
payments = client.get_list("Payment Entry", filters={"docstatus": 1}, limit_page_length=999)
print(f"Payment Entries: {len(payments)}")

# Journal Entries (expenses)
je = client.get_list("Journal Entry", filters={"docstatus": 1}, limit_page_length=999)
print(f"Journal Entries: {len(je)}")

print("="*70)
print("✓ Migration complete with AccountRegistry architecture")
```

### Step 12.2: Create Final Snapshot

```bash
# On host server
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud snapshot
```

**Document:**
- **Label:** Phase 1 & 2 Complete (AccountRegistry Architecture)
- **Contains:** 220 invoices + 219 payments + 709 expenses
- **Total:** 1,148 transactions, KES 11M+
- **Architecture:** Clean, reusable, no hard-coding

**✓ Final snapshot created**

---

## Summary Checklist

**Preparation:**
- [x] Current work committed to git
- [x] Documentation created and committed
- [x] Snapshot list reviewed

**Reset:**
- [ ] Pristine snapshot restored (20260304_083504)
- [ ] Fiscal years updated
- [ ] API keys generated
- [ ] Connection config updated
- [ ] Custom field created
- [ ] Connection tested

**Architecture:**
- [ ] AccountRegistry implemented
- [ ] PaymentEntryImporter updated (v3.2)
- [ ] ExpenseImporter updated (v1.1)
- [ ] All changes committed

**Accounts:**
- [ ] Registry initialized
- [ ] Payment accounts created via registry
- [ ] Discovery verified

**Migration:**
- [ ] Prerequisites checked
- [ ] Master data created
- [ ] Phase 1A: 220 invoices imported
- [ ] Phase 1B: 219 payments imported
- [ ] Phase 1 snapshot created
- [ ] Phase 2: 709 expenses imported
- [ ] Final verification complete
- [ ] Final snapshot created

---

## Troubleshooting

**If accounts not found:**
```python
# Clear registry cache and retry
registry.clear_cache()
account = registry.get_payment_account("M-Pesa")
```

**If API connection fails:**
```python
# Verify Host header
print(client.session.headers)
# Should show: {'Host': 'well.rosslyn.cloud'}
```

**If custom field missing:**
- Recreate it via UI (Customize Form → Sales Invoice)
- MUST exist before importing invoices

**If import fails:**
- Check error messages carefully
- Verify accounts exist
- Test with limit=10 first
- Check git for working version

---

## Success Criteria

**Reset is successful when:**
1. ✅ All code committed to git
2. ✅ Pristine snapshot restored
3. ✅ AccountRegistry working
4. ✅ All importers use registry (no hard-coding)
5. ✅ Phase 1 & 2 re-imported successfully
6. ✅ Zero hard-coded account names in codebase
7. ✅ Architecture is portable (works for any country)
8. ✅ Clean snapshots created

**Time investment:** 2-3 hours  
**Long-term benefit:** Clean, maintainable, reusable toolkit

---

**Ready to execute! Follow checklist step-by-step.** ✅
