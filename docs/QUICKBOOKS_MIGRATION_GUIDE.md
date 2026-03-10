# QuickBooks to ERPNext Migration - Export Strategy

**Purpose:** How to prepare for QuickBooks data exports and adapt our toolkit

---

## QuickBooks Export Challenges

### The Core Problem

QuickBooks exports are formatted for human reading, not database migration. Merged cells, headers, subtotals – none of this works for data import. Reports are designed for printing, not data migration.

**Issues with QuickBooks exports:**
- ❌ Merged cells in Excel
- ❌ Report headers and subtotals
- ❌ Aggregated data (loses item-level detail)
- ❌ Inconsistent column formats
- ❌ Different export structures (Desktop vs. Online)

---

## QuickBooks Data Export Methods

### Reality: Manual CSV Export Only

**ERPNext's QuickBooks Migrator is NOT available** - all QuickBooks migrations must use manual CSV export from QuickBooks reports.

This applies to both:
- QuickBooks Online
- QuickBooks Desktop

### Export Strategy (Both QB Online and Desktop)

**Master Data:**
```
Customers:
- Reports → List → Customer Contact List → Export to Excel
- OR: Sales → Customers → Export to Excel

Items:
- Reports → List → Item Listing
- Add columns: Cost, Sales Price, On Hand Quantity
- Export to Excel

Vendors (Suppliers):
- Reports → List → Vendor Contact List → Export to Excel

Chart of Accounts:
- Reports → Accounting → Trial Balance
- Export for opening balance date
```

**Transactions:**
```
Sales Invoices:
- Reports → Sales → Transaction List by Customer
- Filter by date range
- Export to Excel

Purchase Invoices:
- Reports → Purchases → Transaction List by Vendor
- Filter by date range
- Export to Excel

Payments:
- Reports → Banking → Deposit Detail
- Export to Excel
```

---

## Data Cleaning Required

### Common QuickBooks Export Issues

**1. Report Formatting**
```
BAD (from QuickBooks report):
Row 1: Company Name
Row 2: Report Title
Row 3: Date Range
Row 4: [blank]
Row 5: Customer, Amount, Date  # Actual headers
Row 6: John Doe, $100.00, 1/1/2024

GOOD (cleaned for import):
Row 1: Customer, Amount, Date
Row 2: John Doe, 100.00, 2024-01-01
```

**2. Currency Formatting**
- Remove $ symbols
- Remove commas from numbers
- Convert brackets (100) to negative values: -100

**3. Date Formats**
- QuickBooks: "1/15/2024" or "Jan 15, 2024"
- ERPNext needs: "2024-01-15" (YYYY-MM-DD)

**4. Account Structure**
```
QuickBooks allows:
- Multiple accounts with same name
- Transactions on group accounts

ERPNext requires:
- Unique account names
- Transactions only on ledger accounts (not groups)
```

---

## Field Mapping: QuickBooks → ERPNext

### Chart of Accounts

| QuickBooks | ERPNext | Notes |
|------------|---------|-------|
| Account Name | Account Name | ERPNext adds "- QB - CompanyAbbr" |
| Account Type | Account Type | Maps to: Asset, Liability, Equity, Income, Expense |
| Parent Account | Parent Account | Hierarchy preserved |
| Balance | Opening Balance | Via Journal Entry |

### Customers

| QuickBooks | ERPNext | Notes |
|------------|---------|-------|
| Customer Name | Customer Name | ERPNext adds "- CompanyAbbr" |
| Company Name | Customer Name | If business customer |
| Contact Person | Contact (child table) | Separate import |
| Terms | Payment Terms | Map to ERPNext payment terms |
| (not in QB) | Customer Group | Default to "Commercial" or "Individual" |
| (not in QB) | Territory | Default to "All Territories" |

### Items

| QuickBooks | ERPNext | Notes |
|------------|---------|-------|
| Item Name | Item Name | ERPNext adds "- CompanyAbbr" |
| Description | Description | Direct map |
| Sales Price | Standard Selling Rate | Via Item Price |
| Cost | Valuation Rate | Via Stock Reconciliation |
| Quantity on Hand | Opening Stock | Via Stock Reconciliation |
| UOM | Stock UOM | QB data often unreliable, default to "Unit" or "Nos" |
| Type (Inventory/Service) | Item Group | Map to custom groups |

### Sales Invoices

| QuickBooks | ERPNext | Notes |
|------------|---------|-------|
| Invoice Number | Name | ERPNext can auto-number or preserve |
| Customer | Customer | Must exist first |
| Invoice Date | Posting Date | Convert to YYYY-MM-DD |
| Due Date | Due Date | OR let ERPNext calculate from payment terms |
| Line Items | Items (child table) | Item, Qty, Rate |
| Tax | Taxes and Charges (child table) | Map to ERPNext tax templates |
| Total | Grand Total | Should match after mapping |

---

## Adapting Our Toolkit for QuickBooks

### Differences vs. Generic CSV Export

**Our Current Source (Generic CSV):**
```
transactions.csv:
- id, transaction_date, type, category_id, amount

etims_invoices.csv:
- id, invoice_number, invoice_date, customer_name, total_amount

inventory_items.csv:
- id, item_name, unit, quantity_on_hand
```

**QuickBooks Export Structure:**
```
sales_invoices_export.csv:
- Type, Num, Date, Customer, Memo, Item, Qty, Rate, Amount, Balance

customer_list.csv:
- Name, Company Name, Main Phone, Main Email, Terms, Balance Total

item_list.csv:
- Name, Description, Type, Unit of Measure, Sales Price, Cost, Qty On Hand
```

### Required Toolkit Enhancements

**1. QuickBooks-Specific CSV Parser**

```python
class QuickBooksCSVParser:
    """
    Parse QuickBooks exports to standardized format.
    
    Handles:
    - Report header removal
    - Currency formatting ($100.00 → 100.00)
    - Date conversion (1/15/2024 → 2024-01-15)
    - Negative values (100) → -100
    - Multi-line transactions (grouped invoices)
    """
    
    def clean_currency(self, value):
        """Remove $, commas, convert brackets to negative."""
        
    def convert_date(self, value):
        """Convert M/D/YYYY to YYYY-MM-DD."""
        
    def parse_invoice_export(self, filepath):
        """
        Parse QuickBooks Sales by Customer Detail report.
        Returns standardized invoice DataFrame.
        """
```

**2. QuickBooks Account Mapper**

```python
class QuickBooksAccountMapper:
    """
    Map QuickBooks chart of accounts to ERPNext.
    
    Handles:
    - Duplicate account names (add suffixes)
    - Group accounts with child ledgers
    - Account type mapping (QB → ERPNext)
    - Parent-child hierarchy
    """
    
    def handle_duplicates(self, accounts_df):
        """Add suffixes to duplicate account names."""
        
    def create_ledger_for_groups(self, account):
        """
        QB allows transactions on group accounts.
        ERPNext doesn't - create child ledger.
        """
```

**3. QuickBooks Item Importer**

```python
class QuickBooksItemImporter:
    """
    Import QuickBooks items with special handling.
    
    Differences from generic import:
    - UOM often unreliable (default to 'Unit')
    - Type field → Item Group mapping
    - Inventory vs. Non-Inventory items
    - Opening stock via Stock Reconciliation
    """
```

---

## Migration Sequence for QuickBooks

### Phase 0: Pre-Migration Preparation

**A. Clean QuickBooks Data**
1. Remove duplicate customers/vendors
2. Fix inactive items
3. Verify chart of accounts structure
4. Reconcile all accounts

**B. Export All Data**
```
Master Data:
✓ Chart of Accounts (Trial Balance export)
✓ Customers (Customer Contact List)
✓ Vendors (Vendor Contact List)
✓ Items (Item Listing with Cost, Price, Qty)

Transactions:
✓ Sales Invoices (Transaction List by Customer)
✓ Purchase Invoices (Transaction List by Vendor)
✓ Payments Received (Deposit Detail)
✓ Payments Made (Check Detail)
✓ Journal Entries (if any)
```

**C. Data Cleaning**
```python
# Remove report headers
# Convert currencies
# Standardize dates
# Handle negative values
```

### Phase 1: Master Data Import

**Sequence matters:**
```
1. Chart of Accounts
   - Parent accounts first
   - Then child accounts
   
2. Customer Groups / Territories
   - Create custom groups if needed
   
3. Customers
   - Basic customer records
   - Then contacts (child table)
   
4. Suppliers
   
5. Item Groups / UOMs
   
6. Items
   - Without stock first
   - Stock reconciliation later
```

### Phase 2: Opening Balances

**Two strategies:**

**Strategy A: Opening Balances Only (Recommended)**
```
Import balances as of cutoff date (e.g., Jan 1, 2025):
- Accounts Receivable (outstanding invoices)
- Accounts Payable (outstanding bills)
- Inventory valuation
- GL account balances

Keep QuickBooks as read-only archive for history.
```

**Strategy B: Full History Migration**
```
Import all transactions from start:
- All sales invoices
- All purchase invoices
- All payments (linked to invoices)
- All journal entries

Time-consuming but complete audit trail.
```

### Phase 3: Transactions

**If doing full history:**
```
1. Sales Invoices (draft first, verify, then submit)
2. Payment Entries (linked to invoices)
3. Purchase Invoices
4. Payment Entries (vendor payments)
5. Stock Entries
6. Journal Entries
```

---

## Key Differences: Generic CSV vs. QuickBooks Reports

| Aspect | Generic CSV (Current) | QuickBooks Reports |
|--------|----------------------|-------------------|
| **Export Method** | ✅ Database export, clean CSV | ⚠️ Manual report exports, messy formatting |
| **Data Quality** | ✅ Clean, structured | ⚠️ Report-formatted (headers, subtotals, merged cells) |
| **Chart of Accounts** | Simple list | Hierarchical, duplicates allowed, group transactions |
| **Account Names** | Direct use | May need suffixes for duplicates |
| **UOMs** | Reliable | Unreliable, often default to 'Each' or 'Unit' |
| **Item Types** | Explicit groups | Type field → must map to Item Groups |
| **Invoices** | Simple CSV rows | Multi-line grouped format, aggregated by customer |
| **Payments** | Separate table | May be embedded in invoice reports OR separate |
| **Dates** | ISO format (YYYY-MM-DD) | M/D/YYYY or locale-specific |
| **Currency** | Numbers (100.00) | $100.00, (100.00) brackets for negative |
| **Data Cleaning** | Minimal | **70% of migration effort** |
| **Automation** | ❌ No QB Migrator available | ❌ Fully manual process |

**Key Insight:** QuickBooks migrations require **extensive data cleaning** before our toolkit can process them. The QuickBooksCSVParser component is **essential**, not optional.

---

## Toolkit Enhancement Roadmap

### Phase 8: QuickBooks Adapter (Priority)

**Required Components:**

1. **QuickBooksCSVParser** - Clean QB report exports
2. **QuickBooksAccountMapper** - Handle account quirks  
3. **QuickBooksItemImporter** - Default UOMs, type mapping
4. **QuickBooksInvoiceImporter** - Multi-line format handling

**Configuration:**
```yaml
# config/quickbooks_mapping.yaml
account_suffixes:
  enabled: true
  pattern: "- {company_abbr}"

uom_defaults:
  inventory: "Unit"
  service: "Nos"

item_type_mapping:
  "Inventory Part": "Products"
  "Non-inventory Part": "Services"
  "Service": "Services"

report_cleaning:
  remove_currency_symbols: true
  convert_brackets_to_negative: true
  date_format: "M/D/YYYY"  # Input format from QB
```

---

## Recommendation for Current Project

**For Wellness Centre (Generic CSV):**
✅ Current approach is perfect - clean source data, no QB-specific issues

**For Future QuickBooks Migrations:**
1. ⚠️ **No automated migrator available** - manual CSV export required
2. Use QuickBooks report exports (challenging but necessary)
3. Build QuickBooksCSVParser to clean messy report formats
4. Use toolkit importers with QB adapters for data transformation
5. Expect significant data cleaning effort (70% of migration time)

**Priority:** 
- Phase 7: Multi-company support (African market need)
- Phase 8: QuickBooks adapter (high demand - most businesses migrate from QB)

**QuickBooks migrations are common in African markets** - adding this adapter would significantly increase toolkit adoption.
