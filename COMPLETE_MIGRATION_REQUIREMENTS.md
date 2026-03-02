# Complete Migration Requirements - Wellness Centre to ERPNext

## Data Inventory (18 CSV Files)

### FINANCIAL DATA (Priority 1 - Critical)
1. **etims_invoices.csv** (220 records)
   - Customer invoices with KRA eTIMS integration
   - ERPNext: Sales Invoice
   - Status: Master data ready, importer needs fixes

2. **etims_invoice_items.csv** (220 line items)
   - Invoice line items
   - ERPNext: Sales Invoice Items (child table)
   - Status: Linked to parent

3. **transactions.csv** (947 records)
   - Types: income(220), expense(709), capital_injection(17), savings(1)
   - ERPNext Multiple: Payment Entry, Journal Entry, Purchase Invoice
   - Status: Not started

### MASTER DATA (Priority 1 - Required for transactions)
4. **contacts.csv** (45 records)
   - Types: Owner, Employee, Supplier, Customer, Agent, Contractor, Service Provider, Casual
   - Fields: name, phone, email, company_name, daily_rate, monthly_salary, kra_pin
   - ERPNext: Customer, Supplier, Employee (need to split by type)
   - Status: 12 customers created, 33 others missing

5. **contact_types.csv** (8 types)
   - Maps to ERPNext: Customer Type, Supplier Type
   - Status: Not created

6. **transaction_categories.csv** (31 categories)
   - Types: income(4), expense(24), capital_injection(2), savings(1)
   - ERPNext: Account (Chart of Accounts)
   - Status: Not created as accounts

### INVENTORY (Priority 2 - Business Operations)
7. **inventory_items.csv** (77 items)
   - Kitchen, Furniture, Linens/Bedding, Cleaning, Event/Catering, Garden, Farm, Bathroom
   - ERPNext: Item (stock items)
   - Status: Not started

8. **inventory_categories.csv** (8 categories)
   - ERPNext: Item Group
   - Status: Not created

9. **inventory_movements.csv** (193 records)
   - Types: Purchase(60), Consumption(83), Breakage(44), Sale(2), Transfer(4)
   - ERPNext: Stock Entry
   - Status: Not started

### PROPERTY & OPERATIONS (Priority 2)
10. **properties.csv** (6 records)
    - Main House, Guest Cottage, Staff Quarters, Chicken Coop, Gardens, Storage Shed
    - ERPNext: Custom DocType or Asset
    - Status: Not created

11. **rooms.csv** (5 rooms)
    - ERPNext: Custom DocType "Room" or use Item with type "Room"
    - Status: Not created

12. **room_bookings.csv** (54 bookings)
    - ERPNext: Custom DocType "Room Booking" or Sales Invoice
    - Status: Not started

13. **events.csv** (25 events)
    - ERPNext: Custom DocType "Event" or Project
    - Status: Not started

### FARM OPERATIONS (Priority 3)
14. **animals.csv** (3 records)
    - Dog, Indigenous Chicken (laying hens)
    - ERPNext: Asset or Custom DocType
    - Status: Not created

15. **egg_production.csv** (52 weeks)
    - Weekly production tracking
    - ERPNext: Custom DocType or Manufacturing
    - Status: Not created

16. **egg_sales.csv** (103 sales)
    - Already covered in etims_invoices
    - Status: Will be imported via invoices

### COMPLIANCE & UTILITIES (Priority 3)
17. **compliance_documents.csv** (9 documents)
    - KRA PIN, Business License, Fire Safety, Health Permit, etc.
    - ERPNext: Custom DocType or Document Attachment
    - Status: Not created

18. **utility_accounts.csv** (4 accounts)
    - Electricity, Water, Internet, Security
    - ERPNext: Custom DocType or Supplier with contracts
    - Status: Not created

---

## ERPNext Prerequisites Analysis

### Already Exist (from diagnostics):
✓ Mode of Payment (7): Cash, M-Pesa, Bank Transfer, etc.
✓ Debtors Account: "Debtors - WC"
✓ Company defaults: Sales, Cash accounts set

### Missing Master Data:

#### 1. Chart of Accounts Expansion
**Need to create accounts for 31 transaction categories:**

Income Accounts (4):
- Event Venue Hire
- Room Accommodation  
- Farm Eggs
- Wellness Services

Expense Accounts (24):
- Inventory Purchases
- Permanent Staff Salaries
- Property Renovations
- Animal Feed (Chicken)
- Garden & Landscaping Maintenance
- Casual Labour (multiple types)
- Event Supplies & Setup
- Estate Service Charge
- Supplies & Provisions
- Agent Commissions
- Consultant Fees
- Utilities (Electricity, Water, Borehole)
- Furniture & Fittings
- Dog Care
- Veterinary Care
- Business Registration & Permits
- Miscellaneous

Other Accounts (3):
- Owner Capital Injection (Equity)
- Savings Account (Asset)
- Capital Purchases (Asset)

**ERPNext Action:**
- Create Account records with proper account_type
- Link to company "Wellness Centre"
- Set parent accounts (Income, Direct Expenses, etc.)

#### 2. Contacts Split by Type

From contacts.csv (45 total):
- Customers (12) → Already created ✓
- Suppliers (est. 15) → Need to create
- Employees (est. 10) → Need to create
- Agents (est. 3) → Create as Customer with agent flag
- Contractors (est. 5) → Create as Supplier

**ERPNext Action:**
- Create Supplier records with KRA PIN
- Create Employee records with salary info
- Update existing Customers with missing fields (currency, payment terms)

#### 3. Item Master Expansion

Currently have (10):
- Service items for invoicing ✓

Need to add (77):
- Physical inventory items (Kitchen, Furniture, Linens, etc.)
- Item Group structure (8 categories)

**ERPNext Action:**
- Create Item Groups from inventory_categories.csv
- Create Stock Items from inventory_items.csv
- Set opening stock with valuations

#### 4. Company Configuration

**Missing settings:**
- Fiscal Year: Should be 2024-01-01 to 2024-12-31
- Cost Centers: May need for expense tracking
- Warehouses: At least one for inventory

#### 5. Customer Defaults

**All 12 customers need:**
- default_currency: "KES"
- payment_terms: "Immediate" or create Payment Terms Template
- territory: "Kenya"
- customer_group: "Individual" or "Corporate"

---

## Complete Toolkit Gaps

### Layer 0: Master Data Creator (Needs Expansion)

**Current:**
✓ UOM Creator
✓ Item Creator (services only)
✓ Customer Creator

**Missing:**
1. **Account Creator** - Create Chart of Accounts from transaction_categories.csv
2. **Supplier Creator** - Extract suppliers from contacts.csv
3. **Employee Creator** - Extract employees from contacts.csv
4. **Item Group Creator** - Create from inventory_categories.csv
5. **Stock Item Creator** - Create inventory items
6. **Customer Updater** - Set currency, payment terms defaults
7. **Company Setup** - Fiscal year, warehouses, cost centers

### Layer 3: Document Importers (Needs Expansion)

**Current:**
✓ Sales Invoice Importer (eTIMS)

**Missing:**
1. **Payment Entry Importer** - Import 220 payment transactions
2. **Purchase Invoice Importer** - Import supplier bills from expense transactions
3. **Journal Entry Importer** - Import capital injections, savings, adjustments
4. **Stock Entry Importer** - Import inventory movements
5. **Opening Balance Importer** - Set initial inventory values

### Layer 4: Domain Model Importers (Optional)

**Missing:**
1. **Room Booking Importer** - Custom DocType or link to invoices
2. **Event Importer** - Custom DocType or link to projects
3. **Egg Production Importer** - Manufacturing/production entries

---

## Recommended Implementation Order

### Phase 1: Complete Financial Foundation (THIS WEEK)
Priority: CRITICAL - Get books balanced

1. **Expand Master Data Creator**
   - Add Account Creator (transaction_categories → Chart of Accounts)
   - Add Supplier Creator (contacts.csv where type = Supplier)
   - Add Employee Creator (contacts.csv where type = Employee)
   - Add Customer Updater (set currency, payment terms)

2. **Fix & Complete Sales Invoice Import**
   - Apply current fixes (currency, debit_to, income_account)
   - Import all 220 invoices

3. **Build Payment Entry Importer**
   - Extract 220 payment transactions from transactions.csv
   - Link to invoices
   - Clear outstanding receivables

4. **Build Expense Transaction Importer**
   - Extract 709 expense transactions
   - Create as Journal Entries or Purchase Invoices
   - Link to expense accounts

5. **Validate Financial Data**
   - P&L should match: Income KES 2.59M, Expenses KES 4.36M
   - Balance Sheet should balance
   - No outstanding invoices (all paid)

### Phase 2: Inventory Management (NEXT WEEK)
Priority: HIGH - Track assets

1. **Create Item Groups** (inventory_categories.csv)
2. **Create Stock Items** (inventory_items.csv)
3. **Import Stock Entries** (inventory_movements.csv)
4. **Set Opening Balances**

### Phase 3: Operations Data (LATER)
Priority: MEDIUM - Nice to have

1. Room bookings
2. Event records
3. Egg production tracking
4. Compliance documents
5. Utility accounts

---

## Required ERPNext Configuration

### Before Any Imports:

```python
# 1. Update Company Settings
company_updates = {
    "default_currency": "KES",
    "country": "Kenya",
    # Ensure fiscal year exists for 2024
}

# 2. Create/Verify Warehouse
warehouse = {
    "warehouse_name": "Main Warehouse - WC",
    "company": "Wellness Centre"
}

# 3. Create Payment Terms Template
payment_terms = {
    "template_name": "Immediate Payment",
    "terms": [{
        "description": "Payment due immediately",
        "invoice_portion": 100,
        "credit_days": 0
    }]
}

# 4. Update ALL customers with defaults
for customer in all_customers:
    customer.update({
        "default_currency": "KES",
        "payment_terms": "Immediate Payment",
        "territory": "Kenya"
    })
```

---

## Estimated Effort

| Phase | Work Items | Est. Hours | Priority |
|-------|-----------|------------|----------|
| **Master Data Expansion** | Account/Supplier/Employee creators | 4-6 | CRITICAL |
| **Invoice Import Fix** | Apply fixes, test, import all | 2-3 | CRITICAL |
| **Payment Import** | Build importer, test, import | 3-4 | CRITICAL |
| **Expense Import** | Build importer, test, import | 4-5 | CRITICAL |
| **Financial Validation** | Reconciliation, reports | 2-3 | CRITICAL |
| **Inventory Setup** | Items, groups, movements | 6-8 | HIGH |
| **Operations Data** | Custom doctypes, imports | 8-12 | MEDIUM |
| **TOTAL (Phase 1)** | Complete financial migration | **15-21 hours** | |
| **TOTAL (Phase 1+2)** | Financial + Inventory | **21-29 hours** | |

---

## Critical Next Steps (RIGHT NOW)

1. **Fix current invoice importer** (30 min)
   - Add currency, debit_to, income_account fields
   - Test with 10 invoices
   - Import all 220

2. **Build comprehensive master data creator** (4 hours)
   - Chart of Accounts from transaction_categories
   - Suppliers from contacts
   - Employees from contacts
   - Update customers with defaults

3. **Build payment importer** (3 hours)
   - Extract payments from transactions.csv
   - Match to invoices
   - Import payment entries

4. **Build expense importer** (4 hours)
   - Extract expenses from transactions.csv
   - Create purchase invoices or journal entries
   - Validate totals

**After these 4 items, you'll have complete financial data in ERPNext.**
