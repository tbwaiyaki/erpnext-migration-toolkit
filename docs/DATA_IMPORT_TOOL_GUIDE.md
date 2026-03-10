# ERPNext Data Import Tool - Large Dataset Strategy

**Purpose:** How to use ERPNext's Data Import Tool for bulk imports (alternative to API-based importers)

---

## When to Use Data Import Tool vs. API

### Use Data Import Tool When:
- ✅ Importing master data (Customers, Items, Suppliers)
- ✅ Simple transactions without complex dependencies
- ✅ Dataset size: 1,000 - 5,000 records
- ✅ One-time migration (not reusable script needed)
- ✅ Non-technical users need to run imports

### Use API-Based Importers (Our Current Approach) When:
- ✅ Complex transactions with dependencies (Sales Invoice → Payment Entry)
- ✅ Need duplicate detection logic
- ✅ Require data validation beyond ERPNext's built-in checks
- ✅ Building reusable toolkit for multiple migrations
- ✅ Need programmatic control over import process

---

## ERPNext Data Import Tool Capabilities

### What It Does Well

**According to research:**
The Data Import tool allows importing records using CSV or Excel files. It's commonly used for initial system setup, data migration, or bulk updates. Supports Insert New Records and Update Existing Records operations.

**Handles these DocTypes reliably:**
- Customer, Supplier, Item
- Accounts (Chart of Accounts)
- Sales Invoice, Purchase Invoice
- Journal Entries

### What It Struggles With

**According to rtCamp (ERPNext experts):**
ERPNext's Data Import Tool handles master data like Customers, Suppliers, Items reliably. But it struggles with linked transactions - Payment Entries tied to invoices, Bank Reconciliation records, anything with dependencies across doctypes often break or import incorrectly.

---

## Size Limitations

### Web UI Limits

There is no hard limit on the number of records that can be imported. But you must try and upload only a few thousand records at a time. Importing a large number of records (let's say 50,000) might slow down the system considerably.

**Practical limits:**
- **< 1,000 records:** Use web UI safely
- **1,000 - 5,000 records:** Use web UI, expect slowness
- **> 5,000 records:** Use bench command-line tool

### Command-Line for Large Datasets

When importing very large datasets (e.g., more than 5,000 documents), it's recommended to use the command-line utility `bench data-import` instead of the web interface. This approach avoids web request timeouts and ensures a more reliable import process.

**Command:**
```bash
bench --site well.rosslyn.cloud data-import ~/path/to/file.csv
```

**Options:**
```bash
bench import-csv --help
Options:
  --only-insert              Do not overwrite existing records
  --submit-after-import      Submit document after importing it
  --ignore-encoding-errors   Ignore encoding errors
```

---

## Best Practices for Large Imports

### From Industry Experts

**1. Batch Processing**
Split large datasets into smaller batches. Delete all previous Data Import Logs at the beginning of each cycle. Import via bench command, which is reliable and handles large datasets far better than the GUI.

**2. Dependency Order**
Not all data is the same. Some data types (DocTypes in ERPNext) rely on other data types to be already present for effective linking. Ensure prerequisites are imported before dependent data types.

**Import sequence:**
```
1. Master Data First:
   - Item Groups, UOMs
   - Customer Groups, Territories
   - Suppliers, Customers
   - Items

2. Accounts:
   - Chart of Accounts (parent accounts first)

3. Transactions:
   - Sales Invoices
   - Payment Entries (linked to invoices)
   - Stock Entries
```

### From Our Experience

**3. Disable Notifications During Import**
If you are bulk importing Leads then a lot of emails will be sent, which may not be desired. You can disable this option to avoid sending emails.

**4. Progress Visibility**
When importing large datasets, visibility is critical. Progress visibility turns data import from a stressful guessing game into a controlled operation.

---

## Data Import Tool Workflow

### Step 1: Download Template

1. Go to **Data Import → New Import**
2. Select DocType (e.g., "Customer")
3. Select Import Type:
   - **Insert New Records** - Add new data
   - **Update Existing Records** - Modify existing data
4. Click **Download Template**

### Step 2: Prepare CSV File

**Requirements:**
- UTF-8 encoding (critical for non-English characters)
- Column headers must match ERPNext field names exactly
- Dates in YYYY-MM-DD format
- Leave ID column blank for new records

**Example: Customer CSV**
```csv
Customer Name,Customer Group,Territory,Customer Type
John Doe,Commercial,Kenya,Company
Jane Smith,Individual,Nairobi,Individual
```

### Step 3: Upload and Import

1. Upload CSV file
2. Map columns (if headers don't match exactly)
3. Review preview
4. Click **Start Import**
5. Monitor progress bar

### Step 4: Verify Import

```bash
# Check imported records
SELECT COUNT(*) FROM `tabCustomer` WHERE creation > '2026-03-10';
```

---

## Comparison: Data Import Tool vs. Our API Approach

| Feature | Data Import Tool | Our API Importers |
|---------|------------------|-------------------|
| **Ease of Use** | ✅ GUI-based, user-friendly | ⚠️ Requires Python/programming |
| **Reusability** | ❌ One-time use | ✅ Reusable scripts |
| **Large Datasets (10k+)** | ⚠️ bench command needed | ✅ Handles well |
| **Complex Dependencies** | ❌ Struggles | ✅ Full control |
| **Duplicate Detection** | ⚠️ Basic (name only) | ✅ Custom logic (source_*_id) |
| **Data Validation** | ⚠️ ERPNext built-in only | ✅ Custom validation |
| **Error Reporting** | ⚠️ Generic errors | ✅ Discrepancy reports |
| **Child Tables** | ✅ Supports | ✅ Full control |
| **Submit After Import** | ✅ Option available | ✅ Programmatic |

---

## When to Combine Both Approaches

### Hybrid Strategy

**Use Data Import Tool for:**
- Initial master data (Customers, Items) - fast and simple
- One-time account imports (Chart of Accounts)

**Use API Importers for:**
- Transactions with dependencies (our current approach)
- Data requiring validation logic
- Building reusable toolkit

### Example Workflow

```python
# Phase 0: Use Data Import Tool (manual)
# - Import Chart of Accounts via web UI
# - Import Customer Groups via web UI

# Phase 1-6: Use API Importers (automated)
# - All transactions (invoices, payments, etc.)
# - Complex master data (items with stock)
# - Anything requiring duplicate detection
```

---

## For Our Toolkit

### Current Approach is Correct

**Why we use API instead of Data Import Tool:**

1. ✅ **Reusability** - Toolkit works for any business, not just Wellness Centre
2. ✅ **Duplicate Detection** - Custom fields (source_*_id) prevent re-imports
3. ✅ **Professional Patterns** - Registries, dependency injection, OOP
4. ✅ **Data Validation** - User confirmation workflows (UOM mappings)
5. ✅ **Error Reporting** - Discrepancy reports, not generic errors
6. ✅ **Complex Dependencies** - Payment entries linked to invoices

### When to Mention Data Import Tool

**In toolkit documentation:**
- "For simple master data imports, ERPNext's Data Import Tool is sufficient"
- "For complex migrations, use this toolkit's API-based importers"
- "Combine both: Data Import for initial setup, API for transactions"

---

## Conclusion

**Data Import Tool: Great for simple, one-time imports**  
**API Importers (our approach): Essential for complex, reusable migrations**

**Our toolkit's API-based approach is the right choice for:**
- Professional migration toolkit
- Reusable across businesses
- Complex multi-domain operations (Wellness Centre's 6 business streams)
- Historical data with dependencies

**Data Import Tool would be suitable for:**
- Quick master data updates
- Non-technical user imports
- Simple, one-time migrations
