# ERPNext Migration Toolkit - Session Continuation Prompt

**Last Updated:** March 7, 2026 (Post-Phase 1, Pre-Phase 2 Reset)  
**Current Status:** Resetting to pristine for clean Phase 2 architecture  
**Project Status:** Active Development - Architectural Refactoring

---

## Quick Start

**I will upload the latest toolkit ZIP at session start** since GitHub cannot be directly accessed from Claude's environment.

**Immediate context needed:**
1. Latest toolkit ZIP (uploaded at start)
2. Confirmation that pristine snapshot restored (20260304_083504)
3. Ready to build AccountRegistry and proper account structure

---

## Project Overview

### Core Mission
Building **ERPNext Migration Toolkit (EMT)** - a reusable, production-ready framework for migrating business data into ERPNext v15. Currently focused on Kenyan wellness centre migration (6 business domains: events, B&B, poultry, inventory, staff, compliance).

### Active Site
- **URL:** well.rosslyn.cloud
- **ERPNext Version:** v15
- **Internal Docker URL:** http://erpnext-frontend:8080
- **Critical:** Must use `Host: well.rosslyn.cloud` header for internal URLs
- **Currency:** KES (Kenyan Shillings)

### Repository
- **GitHub:** https://github.com/tbwaiyaki/erpnext-migration-toolkit
- **Local Path (JupyterLab):** ~/work/ERP/emt/
- **Main Notebook:** notebooks/wellness_centre_migration.ipynb

---

## Current State - RESET IN PROGRESS

### Completed Work (Pre-Reset)

**✅ Phase 1 (Completed but will be redone after reset):**
- 220 Sales Invoices (KES 2,589,840)
- 219 Payment Entries (all receivables cleared)
- Custom field: `original_invoice_number` created
- Kenyan accounts created: M-Pesa - WC, Bank - KCB - WC
- 100% success rate
- Time: ~15 minutes

**✅ Phase 2 Preparation (Completed):**
- AccountMapper built and tested
- 17 expense accounts created
- 709 expenses ready for import (KES 4,363,477)
- Discovered hard-coding issues

### Why We're Resetting

**Problem discovered:**
- Account naming inconsistency between sessions
- PaymentEntryImporter has hard-coded `PAYMENT_ACCOUNT_MAP`
- ExpenseImporter has hard-coded `PAYMENT_ACCOUNT_MAP`
- Different account names expected vs actual (e.g., "Mobile Money - WC" vs "M-Pesa - WC")
- Violates reusability principle (toolkit must work with ANY data)

**Decision:**
- Reset to pristine snapshot (20260304_083504)
- Build proper AccountRegistry for dynamic account discovery
- Establish account creation standards FIRST
- Re-run Phase 1 & 2 cleanly with proper architecture
- Accept 15 minutes of re-work for clean foundation

---

## Architecture Changes for Next Session

### New Component: AccountRegistry

**Purpose:** Centralized, dynamic account discovery (no hard-coding)

**Location:** `src/orchestration/account_registry.py`

**Responsibilities:**
1. Query ERPNext to discover existing accounts
2. Provide account lookup for payment methods
3. Cache results for performance
4. Smart matching (e.g., "M-Pesa" finds "M-Pesa - WC" OR "Mobile Money - WC")
5. Support ANY naming convention (Kenya, Tanzania, Uganda, etc.)

**All importers use AccountRegistry:**
- ✅ SalesInvoiceImporter (no change needed - uses customer accounts automatically)
- ✅ PaymentEntryImporter (remove hard-coded PAYMENT_ACCOUNT_MAP, use registry)
- ✅ ExpenseImporter (remove hard-coded PAYMENT_ACCOUNT_MAP, use registry)
- ✅ Future importers (consistent pattern)

**See:** AccountRegistry_Design.md for full specification

### Updated Importer Pattern

```python
# Create registry once
registry = AccountRegistry(client, "Wellness Centre")

# All importers use it
payment_imp = PaymentEntryImporter(client, company, registry)
expense_imp = ExpenseImporter(client, company, registry)
```

---

## Data Overview

### Source Files (18 CSV)
- **transactions.csv** - 947 rows (income, expenses, capital, savings)
- **etims_invoices.csv** - 220 rows (sales invoices)
- **etims_invoice_items.csv** - 220 rows (line items)
- **contacts.csv** - 45 rows (customers, suppliers, staff)
- **transaction_categories.csv** - 31 rows (expense/income categories)
- **inventory_items.csv** - 77 rows
- **inventory_movements.csv** - 193 rows
- **room_bookings.csv** - 54 rows
- **events.csv** - 25 rows
- **compliance_documents.csv** - 9 rows
- Others: egg_sales, egg_production, animals, properties, etc.

### Migration Scope

**Phase 1: Sales & Payments (439 transactions)**
- 220 Sales Invoices (KES 2,589,840)
- 219 Payment Entries (clear receivables)
- Custom field: `original_invoice_number` required

**Phase 2: Expenses, Capital & Savings (727 transactions)**
- 709 Expenses (KES 4,363,477) - via Journal Entries
- 3 Capital Injections (KES 4,000,000) - via Journal Entries
- 15 Savings (KES 229,000) - via Journal Entries

**Phase 3: Inventory (270 records)**
- 77 items, 193 movements

**Phase 4: Operations**
- 54 room bookings, 25 events

**Phase 5: Compliance**
- 9 documents (6 potentially expired - URGENT)

**Phase 6: Farm Operations**
- Egg production, poultry tracking

---

## Critical Technical Learnings

### ERPNext API Patterns

**✅ Working Patterns:**
```python
# Submit document (submit() method is BROKEN)
doc = client.insert(invoice_doc)
doc['docstatus'] = 1
client.update(doc)

# Cancel document
doc['docstatus'] = 2
client.update(doc)
```

**❌ Broken Methods:**
- `client.submit()` - Returns HTML error page
- `client.cancel()` - Same issue
- `client.put()` - Does not exist on FrappeClient

### Custom Fields (CRITICAL)

**Must create BEFORE import:**
```
Doctype: Sales Invoice
Fieldname: original_invoice_number
Label: Original Invoice Number
Fieldtype: Data
insert_after: naming_series
read_only: 1
allow_on_submit: 1
in_list_view: 1
in_standard_filter: 1
```

**Why critical:**
- Enables duplicate prevention via unique business identifier
- Lost during ERPNext restore - must be recreated
- Check existence before every import session

### Account Structure for Kenya (Example)

**Payment Accounts:**
- M-Pesa - WC (mobile money, account_type: Bank)
- Bank - KCB - WC (traditional bank, account_type: Bank)
- Cash - WC (physical cash, account_type: Cash)

**Note:** Naming convention should be flexible via AccountRegistry
- Different countries may use: "Mobile Money", "MTN Money", "Airtel Money", etc.
- AccountRegistry discovers by searching, not hard-coding names

### Mandatory Payment Entry Fields

**Discovered through testing:**
```python
{
    "doctype": "Payment Entry",
    "payment_type": "Receive",
    "party_type": "Customer",
    "party": "Customer Name",
    "posting_date": "2024-01-01",
    "company": "Company Name",
    "mode_of_payment": "M-Pesa",
    
    # CRITICAL - must be leaf accounts, not groups
    "paid_to": "M-Pesa - WC",
    "paid_to_account_currency": "KES",
    
    "paid_amount": 1000.0,
    "received_amount": 1000.0,
    
    # CRITICAL - even for single currency
    "source_exchange_rate": 1.0,
    "target_exchange_rate": 1.0,
    
    "references": [...]
}
```

**Common errors:**
- Using group accounts (e.g., "Bank Accounts - WC") - must use leaf accounts
- Missing exchange rates - mandatory even for single currency
- Missing account currency field

### Journal Entry for Expenses

**Structure:**
```python
{
    "doctype": "Journal Entry",
    "posting_date": "2024-01-01",
    "company": "Company Name",
    "accounts": [
        {
            # Debit expense account (expense increases)
            "account": "Salary - WC",
            "debit_in_account_currency": 50000.0,
            "credit_in_account_currency": 0
        },
        {
            # Credit payment account (cash/bank decreases)
            "account": "M-Pesa - WC",
            "debit_in_account_currency": 0,
            "credit_in_account_currency": 50000.0
        }
    ]
}
```

**Notes:**
- Double-entry accounting (debits = credits)
- Use proper posting dates (historical imports need `set_posting_time: 1` for invoices)
- Payment account discovered via AccountRegistry (not hard-coded)

---

## Concurrent Import Research (COMPLETE)

**Finding:** Sequential import is CORRECT approach for ERPNext API

**Why concurrent failed:**
- Each invoice submit = 700-1000 database calls
- Concurrent submits → database deadlocks
- ERPNext API designed for transactional ops, not bulk
- Multiple users work fine (different data), but bulk threads fail (same data)

**Documented:** docs/research/CONCURRENT_IMPORT_EXPERIMENT.md

**For >10K records:** Investigate ERPNext's Data Import Tool (future work)

**For current scale:** Sequential v3.0 importers are optimal

---

## Snapshot/Restore System

### Current State
- **Pristine baseline:** 20260304_083504 (0.9 MB) - Post-setup wizard
- **Phase 1 snapshot:** 20260307_144732 (1.1 MB) - Has wrong account structure, DO NOT USE

### Snapshot Commands (Host Server)

```bash
# List snapshots
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud list

# Create snapshot
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud snapshot

# Restore snapshot
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud restore SNAPSHOT_ID
```

### After Restore Checklist
1. Update fiscal years (2024-2025)
2. Generate new API keys
3. **⚠️ CREATE CUSTOM FIELD** (`original_invoice_number` on Sales Invoice)
4. Update config/erpnext_connection.yaml with new API keys
5. **Create all accounts FIRST** (using AccountRegistry design)
6. Run Cell: PrerequisitesChecker
7. Run Cell: MasterDataCreator
8. Begin migration phases

---

## Next Session Workflow

### Step 1: Restore Pristine Snapshot

```bash
# On host server
/opt/consultancy-platform/scripts/erpnext/erpnext-site-snapshot well.rosslyn.cloud restore 20260304_083504
```

### Step 2: Initial ERPNext Setup

1. Login to well.rosslyn.cloud
2. Complete setup wizard if needed
3. Update fiscal years: 2024-01-01 to 2024-12-31, 2025-01-01 to 2025-12-31, 2026-01-01 to 2026-12-31
4. Generate API keys for main user
5. **Create custom field:** `original_invoice_number` on Sales Invoice
6. Update `config/erpnext_connection.yaml`

### Step 3: Build AccountRegistry

**Create:** `src/orchestration/account_registry.py`
- Dynamic account discovery
- Smart matching for payment methods
- Caching for performance
- No hard-coded account names

**See:** AccountRegistry_Design.md for implementation

### Step 4: Update Existing Importers

**PaymentEntryImporter v3.2:**
- Remove `PAYMENT_ACCOUNT_MAP` constant
- Add `registry` parameter to `__init__`
- Use `registry.get_payment_account(payment_method)` instead

**ExpenseImporter v1.1:**
- Remove `PAYMENT_ACCOUNT_MAP` constant
- Add `registry` parameter to `__init__`
- Use `registry.get_payment_account(payment_method)` instead

### Step 5: Create Kenyan Accounts

**Using AccountRegistry pattern:**
```python
registry = AccountRegistry(client, "Wellness Centre")

# Create payment accounts
registry.ensure_payment_account("M-Pesa", account_type="Bank", parent="Bank Accounts - WC")
registry.ensure_payment_account("Bank Transfer", account_name="Bank - KCB", account_type="Bank")
registry.ensure_payment_account("Cash", account_type="Cash")
```

### Step 6: Run Migration

**Phase 1: Invoices & Payments (~15 minutes)**
- Use existing SalesInvoiceImporter v3.0 (no changes needed)
- Use updated PaymentEntryImporter v3.2 (with AccountRegistry)
- Expected: 220 invoices, 219 payments, 100% success

**Phase 2: Expenses, Capital & Savings (~20 minutes)**
- Use updated ExpenseImporter v1.1 (with AccountRegistry)
- Use AccountMapper for expense category mapping
- Expected: 727 transactions, KES 8.6M total

**Create snapshot after each phase**

---

## Performance Expectations

### Sequential Import Performance

**Sales Invoices (v3.0):**
- 220 records in ~150 seconds
- Rate: ~1.5 invoices/second
- This is OPTIMAL for external API

**Payment Entries (v3.1):**
- 219 records in ~820 seconds
- Rate: ~0.27 payments/second
- Slower due to complex GL posting (expected)

**Expenses (Journal Entries):**
- Expected: ~0.5-1.0 entries/second
- 709 expenses: ~15-20 minutes

### Scaling Guidelines

| Record Count | Approach | Expected Time |
|--------------|----------|---------------|
| <1,000 | Sequential | 10-30 minutes |
| 1,000-5,000 | Sequential | 1-3 hours |
| 5,000-10,000 | Sequential | 3-5 hours |
| >10,000 | Data Import Tool | TBD (investigate) |

---

## Known Issues to Avoid

### Common Pitfalls

**❌ Don't:**
- Use `client.submit()` or `client.cancel()` (broken)
- Use group accounts in transactions (only leaf accounts work)
- Import without `original_invoice_number` custom field
- Forget `Host` header for internal Docker URLs
- Hard-code account names (violates reusability)
- Match invoices by (date, amount, customer) - not unique
- Use concurrent approaches for API imports

**✅ Do:**
- Use `client.update({docstatus: 1})` for submit
- Verify custom field exists before import
- Set `Host` header for all internal requests
- Use AccountRegistry for dynamic account discovery
- Match via `original_invoice_number` custom field
- Use sequential importers (proven reliable)
- Create snapshot before major operations

---

## Standards & Patterns

### Manual v6.2 Requirements (STRICT)

**Non-negotiable:**
- ✅ No `cd` commands - use absolute paths
- ✅ No hard-coded values - use variables/config/discovery
- ✅ No quick fixes - proper architecture only
- ✅ Pure Docker-managed volumes
- ✅ Explicit volume naming with project prefix
- ✅ Four-network isolation (frontend/backend/database/monitoring)

**Reference:** `/mnt/project/manual-v6_2-skill-complete.md`

### Git Conventions

**Commit format:**
```
Component: Brief summary (50 chars max)

Detailed explanation:
- What changed
- Why it changed
- Breaking changes
- References

Tested: Verification steps
```

**Tags:**
- Milestones: `v1.1-phase1-complete`, `v1.2-accountregistry`
- Phases: `v6.2-chapter7`

---

## Tools to Use

### When to Search Web
- Verify current ERPNext docs/features
- Check if software features changed since training cutoff
- Find current best practices for integrations
- Research compatibility issues
- Confirm technical specifications

### When to Use Computer Tools
- Create actual documentation files (.md, .docx, .py)
- Generate diagrams or visual aids
- Build code examples to test
- Create templates for business use
- Develop configuration checklists

### When to Use Past Chat Search
- Reference previous decisions in this project
- Find earlier implementation discussions
- Retrieve context from past troubleshooting
- Verify what we already covered
- Look up specific technical details from earlier conversations

---

## Communication Preferences

### Working Style
- Homelab enthusiast, conceptual thinker
- Technically capable, new to ERPNext specifics
- Value understanding principles over memorizing steps
- English is second language - prioritize clarity
- Prefer comprehensive context over quick fixes

### Response Format

**For technical discussions:**
1. Concept/Goal
2. Context (why this approach)
3. Implementation (how to do it)
4. Validation (how to verify)
5. Alternatives (other approaches)

**For documentation:**
- Plain language, no jargon
- Concrete examples
- Step-by-step with verification
- Professional tone, clear structure

---

## Critical Reminders

**For Claude:**
- ✅ Search web to verify current ERPNext docs/behavior
- ✅ Create actual files (.md, .py) not just text
- ✅ Reference past chats for project continuity
- ✅ Question assumptions, suggest better approaches
- ✅ Be honest about limitations/uncertainties
- ✅ NO HARD-CODING - use discovery/config patterns

**For Developer:**
- ✅ Git commit before major testing
- ✅ Create snapshots before risky operations
- ✅ Verify custom fields after restores
- ✅ Always check `original_invoice_number` exists
- ✅ AccountRegistry pattern for all account lookups
- ✅ Sequential importers are correct, not inferior

---

## Files to Reference

**Project Skills:**
- `/mnt/project/manual-v6_2-skill-complete.md` - Deployment standards
- `/mnt/project/erpnext-multisite-skill-complete.md` - Site lifecycle patterns

**Source Data:**
- `/mnt/project/*.csv` - 18 CSV files (read-only project copies)

**Design Documents:**
- `docs/AccountRegistry_Design.md` - AccountRegistry architecture
- `docs/research/CONCURRENT_IMPORT_EXPERIMENT.md` - Concurrent research findings
- `experiments/concurrent/` - Reference implementations

---

## Session Startup Checklist

When starting a new session:

1. ✅ Toolkit ZIP uploaded
2. ✅ Pristine snapshot restored (20260304_083504)
3. ✅ Fiscal years updated (2024, 2025, 2026)
4. ✅ API keys generated and config updated
5. ✅ Custom field `original_invoice_number` created
6. ✅ AccountRegistry implemented
7. ✅ Importers updated to use AccountRegistry
8. ✅ Ready to create accounts and begin migration

---

**Ready to build clean, reusable migration toolkit with proper architecture!** 🚀

**Key Focus:** AccountRegistry eliminates ALL hard-coding, making toolkit work with ANY country's data.
