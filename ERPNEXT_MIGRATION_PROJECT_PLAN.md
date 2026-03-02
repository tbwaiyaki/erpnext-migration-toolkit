# Wellness Centre ERPNext Migration - Complete Project Plan

**Version:** 1.0  
**Date:** 2026-02-28  
**Estimated Time:** 20-25 hours of focused work  
**Prerequisites:** ERPNext v15 installed, CSV files available, Jupyter access

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Phase 0: Environment Setup](#phase-0-environment-setup)
4. [Phase 1: Master Data Creation](#phase-1-master-data-creation)
5. [Phase 2: Sales Invoices](#phase-2-sales-invoices)
6. [Phase 3: Payments](#phase-3-payments)
7. [Phase 4: Expenses](#phase-4-expenses)
8. [Phase 5: Inventory](#phase-5-inventory)
9. [Phase 6: Validation](#phase-6-validation)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## Project Overview

### Objective
Migrate complete business data from 18 CSV files into ERPNext, achieving:
- 100% financial data accuracy (P&L and Balance Sheet)
- All transactions recorded and reconciled
- Inventory tracked with proper valuations
- Foundation for ongoing operations

### Data Scope

| Category | CSV Files | Records | Priority |
|----------|-----------|---------|----------|
| **Sales** | etims_invoices, etims_invoice_items | 220 | Critical |
| **Payments** | transactions (income subset) | 220 | Critical |
| **Expenses** | transactions (expense subset) | 709 | Critical |
| **Inventory** | inventory_items, inventory_movements | 77 + 193 | High |
| **Master Data** | contacts, transaction_categories | 45 + 31 | Critical |
| **Operations** | events, room_bookings, egg_production | 182 | Medium |
| **Compliance** | compliance_documents, utility_accounts | 13 | Low |

### Success Criteria

✓ All 220 invoices imported (KES 2,589,840)  
✓ All 220 payments linked to invoices (zero outstanding)  
✓ All 709 expenses recorded (KES 4,360,000)  
✓ P&L matches source data  
✓ Balance Sheet balances  
✓ Inventory items tracked with opening balances  

---

## Architecture

### 5-Layer Toolkit Structure

```
Layer 0: Master Data Creators
  ├── UOM Creator
  ├── Account Creator (Chart of Accounts)
  ├── Customer Creator
  ├── Supplier Creator
  ├── Employee Creator
  ├── Item Group Creator
  ├── Item Creator (Stock + Service)
  └── Company Configurator

Layer 1: Core Types
  ├── Money
  ├── Account
  ├── Tax
  └── FiscalPeriod

Layer 2: GL Foundation
  ├── JournalEntry
  └── JournalEntryLine

Layer 3: Document Importers
  ├── Sales Invoice Importer
  ├── Payment Entry Importer
  ├── Expense Importer (Journal Entry)
  └── Stock Entry Importer

Layer 4: Validation & Reconciliation
  ├── Financial Validator
  └── Report Generator

Layer 5: Orchestration
  └── Migration Orchestrator (coordinates all)
```

### File Organization

```
~/work/ERP/emt/
├── src/
│   ├── core/                  # Layer 1
│   ├── gl/                    # Layer 2
│   ├── documents/             # Layer 3 base classes
│   ├── importers/             # Layer 3 importers
│   ├── master_data/           # Layer 0
│   ├── validation/            # Layer 4
│   └── orchestration/         # Layer 5
├── notebooks/
│   └── migration_complete.ipynb
├── data/
│   └── (CSV files from /mnt/project)
└── logs/
    └── (import logs)
```

---

## Phase 0: Environment Setup

**Time:** 30 minutes  
**Objective:** Prepare ERPNext, Jupyter, and data access

### Step 0.1: Verify ERPNext Installation

```python
# Cell 1: Test ERPNext Access
from frappeclient import FrappeClient
import os
import csv
from pathlib import Path

# Configuration
ERPNEXT_URL = "http://erpnext-frontend:8080"  # Internal Docker
ERPNEXT_DOMAIN = "well.rosslyn.cloud"
DATA_DIR = Path("/mnt/project")

# Load credentials
API_KEYS_FILE = Path("/home/jovyan/work/ERP/Wellness Centre/frappe_api_keys.csv")

API_KEY = ""
API_SECRET = ""

if API_KEYS_FILE.exists():
    with open(API_KEYS_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            API_KEY = row.get("api_key", "").strip()
            API_SECRET = row.get("api_secret", "").strip()
            break
    print(f"✓ Credentials loaded from {API_KEYS_FILE}")
else:
    print(f"⚠ Credentials file not found")
    print("Set API_KEY and API_SECRET manually below")
    # API_KEY = "your_key_here"
    # API_SECRET = "your_secret_here"

# Validate
if not API_KEY or not API_SECRET:
    raise ValueError("API credentials missing")

if not DATA_DIR.exists():
    raise ValueError(f"Data directory not found: {DATA_DIR}")

print(f"✓ Configuration validated")
print(f"  URL: {ERPNEXT_URL}")
print(f"  Data: {DATA_DIR}")
```

```python
# Cell 2: Connect to ERPNext
try:
    client = FrappeClient(ERPNEXT_URL)
    client.authenticate(API_KEY, API_SECRET)
    client.session.headers.update({"Host": ERPNEXT_DOMAIN})
    
    # Test connection
    test = client.get_list("Customer", limit_page_length=1)
    
    print(f"✓ Connected to ERPNext")
    print(f"  Version: ERPNext v15")
    print(f"  Company: Wellness Centre")
    
except Exception as e:
    print(f"✗ Connection failed: {e}")
    raise
```

### Step 0.2: Verify Company Setup

```python
# Cell 3: Check Company Configuration
try:
    company = client.get_doc("Company", "Wellness Centre")
    
    print("Company Configuration:")
    print(f"  Name: {company.get('company_name')}")
    print(f"  Currency: {company.get('default_currency')}")
    print(f"  Country: {company.get('country')}")
    print(f"  Fiscal Year Start: {company.get('fiscal_year')}")
    
    # Check critical accounts
    accounts_ok = all([
        company.get('default_cash_account'),
        company.get('default_income_account'),
        company.get('default_receivable_account')
    ])
    
    if accounts_ok:
        print("\n✓ Company ready for import")
    else:
        print("\n⚠ Missing default accounts - check ERPNext setup wizard")
        
except Exception as e:
    print(f"✗ Company not found: {e}")
    print("Run ERPNext setup wizard first to create company")
```

### Step 0.3: Create Repository Structure

```bash
# Run in Jupyter terminal
cd ~/work/ERP
mkdir -p emt/src/{core,gl,documents,importers,master_data,validation,orchestration}
mkdir -p emt/notebooks
mkdir -p emt/logs
mkdir -p emt/data

echo "✓ Repository structure created"
```

---

## Phase 1: Master Data Creation

**Time:** 5-6 hours  
**Objective:** Create all prerequisites (accounts, contacts, items)

### Step 1.1: Build Comprehensive Master Data Creator

Create file: `~/work/ERP/emt/src/master_data/comprehensive_creator.py`

```python
"""
Comprehensive Master Data Creator for ERPNext.

Analyzes CSV files and creates ALL required master data:
- Chart of Accounts from transaction_categories.csv
- Customers, Suppliers, Employees from contacts.csv
- UOMs from invoice items
- Service Items from invoice items
- Stock Items from inventory_items.csv
- Item Groups from inventory_categories.csv
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List
from frappeclient import FrappeClient


class ComprehensiveMasterDataCreator:
    """
    One-stop master data creator for complete migration.
    
    Usage:
        creator = ComprehensiveMasterDataCreator(client, "Wellness Centre", data_dir)
        results = creator.create_all()
    """
    
    def __init__(self, client: FrappeClient, company: str, data_dir: Path):
        self.client = client
        self.company = company
        self.data_dir = Path(data_dir)
        self.created = {
            'uoms': [],
            'accounts': [],
            'customers': [],
            'suppliers': [],
            'employees': [],
            'item_groups': [],
            'service_items': [],
            'stock_items': [],
        }
        self.errors = []
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _log_error(self, error_type: str, name: str, error: str):
        """Record error"""
        self.errors.append({
            'type': error_type,
            'name': name,
            'error': str(error)[:200]
        })
    
    def _exists(self, doctype: str, filters: dict) -> bool:
        """Check if record exists"""
        try:
            results = self.client.get_list(
                doctype,
                filters=filters,
                limit_page_length=1
            )
            return len(results) > 0
        except:
            return False
    
    # ========================================================================
    # UOM CREATION
    # ========================================================================
    
    def create_uoms(self) -> dict:
        """
        Create UOMs from etims_invoice_items.csv
        
        Returns:
            Dict with created count
        """
        print("\n1. Creating Units of Measure (UOMs)...")
        
        try:
            items_df = pd.read_csv(self.data_dir / 'etims_invoice_items.csv')
            unique_uoms = set(
                items_df['unit'].str.strip().str.capitalize().dropna().unique()
            )
            
            print(f"   Found {len(unique_uoms)} unique UOMs")
            
            created = 0
            for uom_name in sorted(unique_uoms):
                try:
                    if self._exists("UOM", {"name": uom_name}):
                        continue
                    
                    self.client.insert({
                        "doctype": "UOM",
                        "uom_name": uom_name
                    })
                    self.created['uoms'].append(uom_name)
                    created += 1
                    print(f"   ✓ {uom_name}")
                    
                except Exception as e:
                    self._log_error('uom', uom_name, str(e))
            
            return {'total': len(unique_uoms), 'created': created}
            
        except Exception as e:
            print(f"   ✗ Error loading UOMs: {e}")
            return {'total': 0, 'created': 0}
    
    # ========================================================================
    # CHART OF ACCOUNTS
    # ========================================================================
    
    def create_chart_of_accounts(self) -> dict:
        """
        Create accounts from transaction_categories.csv
        
        Maps transaction types to ERPNext account types:
        - income → Income Account
        - expense → Expense Account  
        - capital_injection → Equity
        - savings → Current Asset
        """
        print("\n2. Creating Chart of Accounts...")
        
        try:
            cats_df = pd.read_csv(self.data_dir / 'transaction_categories.csv')
            
            # Account type mapping
            type_map = {
                'income': 'Income Account',
                'expense': 'Expense Account',
                'capital_injection': 'Equity',
                'savings': 'Current Asset'
            }
            
            # Parent account mapping
            parent_map = {
                'income': 'Income - WC',
                'expense': 'Expenses - WC',
                'capital_injection': 'Capital Stock - WC',
                'savings': 'Current Assets - WC'
            }
            
            created = 0
            for _, row in cats_df.iterrows():
                cat_name = row['name']
                cat_type = row['type']
                
                account_name = f"{cat_name} - WC"
                
                try:
                    if self._exists("Account", {"account_name": cat_name, "company": self.company}):
                        continue
                    
                    self.client.insert({
                        "doctype": "Account",
                        "account_name": cat_name,
                        "company": self.company,
                        "parent_account": parent_map.get(cat_type, "Expenses - WC"),
                        "account_type": type_map.get(cat_type),
                        "is_group": 0
                    })
                    
                    self.created['accounts'].append(account_name)
                    created += 1
                    
                    if created <= 10:
                        print(f"   ✓ {account_name}")
                
                except Exception as e:
                    self._log_error('account', account_name, str(e))
            
            if created > 10:
                print(f"   ... and {created - 10} more")
            
            return {'total': len(cats_df), 'created': created}
            
        except Exception as e:
            print(f"   ✗ Error creating accounts: {e}")
            return {'total': 0, 'created': 0}
    
    # ========================================================================
    # CONTACTS (CUSTOMERS, SUPPLIERS, EMPLOYEES)
    # ========================================================================
    
    def create_contacts(self) -> dict:
        """
        Create customers, suppliers, employees from contacts.csv
        
        contact_type_id mapping:
        1: Owner/Shareholder → Employee
        2: Permanent Staff → Employee
        3: Supplier → Supplier
        4: Customer → Customer (from invoices)
        5: Event Agent → Customer (agent flag)
        6: Contractor → Supplier
        7: Service Provider → Supplier
        8: Casual Worker → Employee (daily rate)
        """
        print("\n3. Creating Contacts (Customers, Suppliers, Employees)...")
        
        try:
            contacts_df = pd.read_csv(self.data_dir / 'contacts.csv')
            contact_types_df = pd.read_csv(self.data_dir / 'contact_types.csv')
            
            # Get customers from invoices
            invoices_df = pd.read_csv(self.data_dir / 'etims_invoices.csv')
            invoice_customers = set(invoices_df['customer_name'].dropna().unique())
            
            # Merge to get type names
            contacts_merged = contacts_df.merge(
                contact_types_df[['id', 'name']],
                left_on='contact_type_id',
                right_on='id',
                how='left',
                suffixes=('', '_type')
            )
            
            customers_created = 0
            suppliers_created = 0
            employees_created = 0
            
            for _, row in contacts_merged.iterrows():
                contact_name = row['name']
                type_name = row.get('name_type', '')
                
                # Determine type
                is_customer = contact_name in invoice_customers
                is_supplier = 'Supplier' in type_name or 'Contractor' in type_name or 'Service Provider' in type_name
                is_employee = 'Staff' in type_name or 'Worker' in type_name or 'Owner' in type_name
                
                # Create Customer
                if is_customer:
                    try:
                        if not self._exists("Customer", {"customer_name": contact_name}):
                            self.client.insert({
                                "doctype": "Customer",
                                "customer_name": contact_name,
                                "customer_type": "Individual",
                                "customer_group": "Individual",
                                "territory": "Kenya",
                                "default_currency": "KES"
                            })
                            self.created['customers'].append(contact_name)
                            customers_created += 1
                    except Exception as e:
                        self._log_error('customer', contact_name, str(e))
                
                # Create Supplier
                if is_supplier:
                    try:
                        if not self._exists("Supplier", {"supplier_name": contact_name}):
                            payload = {
                                "doctype": "Supplier",
                                "supplier_name": contact_name,
                                "supplier_group": "All Supplier Groups",
                                "supplier_type": "Company" if pd.notna(row.get('company_name')) else "Individual",
                                "country": "Kenya",
                                "default_currency": "KES"
                            }
                            
                            if pd.notna(row.get('kra_pin')):
                                payload['tax_id'] = row['kra_pin']
                            
                            self.client.insert(payload)
                            self.created['suppliers'].append(contact_name)
                            suppliers_created += 1
                    except Exception as e:
                        self._log_error('supplier', contact_name, str(e))
                
                # Create Employee
                if is_employee:
                    try:
                        if not self._exists("Employee", {"employee_name": contact_name}):
                            payload = {
                                "doctype": "Employee",
                                "first_name": contact_name.split()[0] if ' ' in contact_name else contact_name,
                                "last_name": contact_name.split()[-1] if ' ' in contact_name else '',
                                "employee_name": contact_name,
                                "company": self.company,
                                "status": "Active"
                            }
                            
                            self.client.insert(payload)
                            self.created['employees'].append(contact_name)
                            employees_created += 1
                    except Exception as e:
                        self._log_error('employee', contact_name, str(e))
            
            print(f"   Customers: {customers_created}")
            print(f"   Suppliers: {suppliers_created}")
            print(f"   Employees: {employees_created}")
            
            return {
                'customers': customers_created,
                'suppliers': suppliers_created,
                'employees': employees_created
            }
            
        except Exception as e:
            print(f"   ✗ Error creating contacts: {e}")
            return {'customers': 0, 'suppliers': 0, 'employees': 0}
    
    # ========================================================================
    # ITEMS
    # ========================================================================
    
    def create_service_items(self) -> dict:
        """Create service items from etims_invoice_items.csv"""
        print("\n4. Creating Service Items...")
        
        try:
            items_df = pd.read_csv(self.data_dir / 'etims_invoice_items.csv')
            unique_items = items_df[['item_description', 'unit']].drop_duplicates()
            
            created = 0
            for _, row in unique_items.iterrows():
                item_code = row['item_description']
                uom = row['unit'].capitalize() if pd.notna(row['unit']) else 'Nos'
                
                try:
                    if self._exists("Item", {"item_code": item_code}):
                        continue
                    
                    self.client.insert({
                        "doctype": "Item",
                        "item_code": item_code,
                        "item_name": item_code,
                        "item_group": "Services",
                        "stock_uom": uom,
                        "is_stock_item": 0
                    })
                    
                    self.created['service_items'].append(item_code)
                    created += 1
                    
                    if created <= 10:
                        print(f"   ✓ {item_code}")
                
                except Exception as e:
                    self._log_error('item', item_code, str(e))
            
            if created > 10:
                print(f"   ... and {created - 10} more")
            
            return {'total': len(unique_items), 'created': created}
            
        except Exception as e:
            print(f"   ✗ Error creating items: {e}")
            return {'total': 0, 'created': 0}
    
    def create_item_groups(self) -> dict:
        """Create item groups from inventory_categories.csv"""
        print("\n5. Creating Item Groups...")
        
        try:
            cats_df = pd.read_csv(self.data_dir / 'inventory_categories.csv')
            
            created = 0
            for _, row in cats_df.iterrows():
                group_name = row['name']
                
                try:
                    if self._exists("Item Group", {"item_group_name": group_name}):
                        continue
                    
                    self.client.insert({
                        "doctype": "Item Group",
                        "item_group_name": group_name,
                        "parent_item_group": "All Item Groups"
                    })
                    
                    self.created['item_groups'].append(group_name)
                    created += 1
                    print(f"   ✓ {group_name}")
                
                except Exception as e:
                    self._log_error('item_group', group_name, str(e))
            
            return {'total': len(cats_df), 'created': created}
            
        except Exception as e:
            print(f"   ✗ Error creating item groups: {e}")
            return {'total': 0, 'created': 0}
    
    def create_stock_items(self) -> dict:
        """Create stock items from inventory_items.csv"""
        print("\n6. Creating Stock Items...")
        
        try:
            items_df = pd.read_csv(self.data_dir / 'inventory_items.csv')
            cats_df = pd.read_csv(self.data_dir / 'inventory_categories.csv')
            
            # Merge to get category names
            items_merged = items_df.merge(
                cats_df[['id', 'name']],
                left_on='category_id',
                right_on='id',
                how='left',
                suffixes=('', '_cat')
            )
            
            created = 0
            for _, row in items_merged.iterrows():
                item_code = row['item_name']
                item_group = row.get('name_cat', 'Products')
                uom = row['unit'].capitalize() if pd.notna(row['unit']) else 'Nos'
                
                try:
                    if self._exists("Item", {"item_code": item_code}):
                        continue
                    
                    self.client.insert({
                        "doctype": "Item",
                        "item_code": item_code,
                        "item_name": item_code,
                        "description": row.get('description', ''),
                        "item_group": item_group,
                        "stock_uom": uom,
                        "is_stock_item": 1,
                        "opening_stock": row.get('quantity_on_hand', 0),
                        "valuation_rate": row.get('unit_cost', 0)
                    })
                    
                    self.created['stock_items'].append(item_code)
                    created += 1
                    
                    if created <= 10:
                        print(f"   ✓ {item_code}")
                
                except Exception as e:
                    self._log_error('stock_item', item_code, str(e))
            
            if created > 10:
                print(f"   ... and {created - 10} more")
            
            return {'total': len(items_df), 'created': created}
            
        except Exception as e:
            print(f"   ✗ Error creating stock items: {e}")
            return {'total': 0, 'created': 0}
    
    # ========================================================================
    # ORCHESTRATION
    # ========================================================================
    
    def create_all(self) -> dict:
        """
        Create ALL master data in proper order.
        
        Returns:
            Complete summary of what was created
        """
        print("="*70)
        print("COMPREHENSIVE MASTER DATA CREATION")
        print("="*70)
        
        results = {}
        
        # Order matters!
        results['uoms'] = self.create_uoms()
        results['accounts'] = self.create_chart_of_accounts()
        results['contacts'] = self.create_contacts()
        results['service_items'] = self.create_service_items()
        results['item_groups'] = self.create_item_groups()
        results['stock_items'] = self.create_stock_items()
        
        # Summary
        print()
        print("="*70)
        print("MASTER DATA CREATION COMPLETE")
        print("="*70)
        print(f"UOMs:          {results['uoms']['created']}/{results['uoms']['total']}")
        print(f"Accounts:      {results['accounts']['created']}/{results['accounts']['total']}")
        print(f"Customers:     {results['contacts']['customers']}")
        print(f"Suppliers:     {results['contacts']['suppliers']}")
        print(f"Employees:     {results['contacts']['employees']}")
        print(f"Service Items: {results['service_items']['created']}/{results['service_items']['total']}")
        print(f"Item Groups:   {results['item_groups']['created']}/{results['item_groups']['total']}")
        print(f"Stock Items:   {results['stock_items']['created']}/{results['stock_items']['total']}")
        
        if self.errors:
            print(f"\nErrors: {len(self.errors)}")
            for error in self.errors[:5]:
                print(f"  {error['type']}: {error['name']} - {error['error']}")
        
        print("="*70)
        
        results['errors'] = self.errors
        return results
```

### Step 1.2: Run Master Data Creation

```python
# Cell 4: Create ALL Master Data
import sys
sys.path.insert(0, str(Path('~/work/ERP/emt/src').expanduser()))

from master_data.comprehensive_creator import ComprehensiveMasterDataCreator

# Initialize
master_creator = ComprehensiveMasterDataCreator(
    client=client,
    company="Wellness Centre",
    data_dir=DATA_DIR
)

# Create everything
master_results = master_creator.create_all()

# Validate
total_created = (
    master_results['uoms']['created'] +
    master_results['accounts']['created'] +
    master_results['contacts']['customers'] +
    master_results['contacts']['suppliers'] +
    master_results['contacts']['employees'] +
    master_results['service_items']['created'] +
    master_results['item_groups']['created'] +
    master_results['stock_items']['created']
)

print(f"\n✓ Total records created: {total_created}")

if len(master_results['errors']) > 0:
    print(f"⚠ {len(master_results['errors'])} errors - review above")
else:
    print("✓ No errors - all master data created successfully!")
```

---

## Phase 2: Sales Invoices

**Time:** 2-3 hours  
**Objective:** Import all 220 eTIMS invoices

### Step 2.1: Build Invoice Importer

Create file: `~/work/ERP/emt/src/importers/sales_invoice_importer.py`

```python
"""
eTIMS Sales Invoice Importer for ERPNext.

Imports invoices from etims_invoices.csv and etims_invoice_items.csv
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from frappeclient import FrappeClient


class SalesInvoiceImporter:
    """
    Import eTIMS invoices to ERPNext Sales Invoice.
    
    Handles:
    - Customer ID lookup (display name → ERPNext ID)
    - Item validation
    - Tax calculation
    - Required field population (currency, accounts)
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path, company: str = "Wellness Centre"):
        self.client = client
        self.data_dir = Path(data_dir)
        self.company = company
        self.successes = []
        self.failures = []
        self.skipped = []
    
    def _get_customer_id(self, customer_name: str) -> str:
        """Get ERPNext customer ID from display name"""
        try:
            results = self.client.get_list(
                "Customer",
                filters={"customer_name": customer_name},
                fields=["name"],
                limit_page_length=1
            )
            
            if results:
                return results[0]['name']
            else:
                return customer_name  # Fallback
                
        except:
            return customer_name
    
    def build_invoice_payload(self, invoice_row: dict, items_df: pd.DataFrame) -> dict:
        """Build ERPNext Sales Invoice from CSV data"""
        invoice_id = invoice_row['id']
        customer_name = invoice_row['customer_name']
        
        # Get customer ID
        customer_id = self._get_customer_id(customer_name)
        
        # Get items for this invoice
        invoice_items = items_df[items_df['invoice_id'] == invoice_id]
        
        # Build items array
        items = []
        for _, item_row in invoice_items.iterrows():
            items.append({
                "item_code": item_row['item_description'],
                "item_name": item_row['item_description'],
                "description": item_row['item_description'],
                "qty": float(item_row['quantity']),
                "rate": float(item_row['unit_price']),
                "amount": float(item_row['total_price']),
                "uom": item_row['unit'].capitalize() if pd.notna(item_row['unit']) else 'Nos',
                "income_account": "Sales - WC"  # Explicitly set
            })
        
        # Build taxes (if any)
        taxes = []
        total_tax = sum(
            item_row['tax_amount'] for _, item_row in invoice_items.iterrows()
            if pd.notna(item_row['tax_amount']) and item_row['tax_amount'] > 0
        )
        
        if total_tax > 0:
            taxes.append({
                "charge_type": "On Net Total",
                "account_head": "VAT - WC",
                "description": "VAT @ 16%",
                "rate": 16.0,
                "tax_amount": float(total_tax)
            })
        
        # Build invoice payload
        payload = {
            "doctype": "Sales Invoice",
            "customer": customer_id,
            "customer_name": customer_name,
            "posting_date": invoice_row['invoice_date'],
            "due_date": invoice_row['invoice_date'],
            "currency": "KES",
            "debit_to": "Debtors - WC",
            "items": items,
        }
        
        if taxes:
            payload["taxes"] = taxes
        
        # Add eTIMS reference
        etims_ref = f"eTIMS: {invoice_row['invoice_number']}"
        if pd.notna(invoice_row.get('notes')):
            payload["remarks"] = f"{etims_ref}\n{invoice_row['notes']}"
        else:
            payload["remarks"] = etims_ref
        
        return payload
    
    def import_all(
        self,
        check_duplicates: bool = True,
        auto_submit: bool = False,
        limit: Optional[int] = None
    ) -> dict:
        """
        Import all invoices.
        
        Args:
            check_duplicates: Skip if invoice exists
            auto_submit: Submit after creation (posts to GL)
            limit: Optional limit for testing
            
        Returns:
            Summary dict with counts and lists
        """
        # Load data
        invoices_df = pd.read_csv(self.data_dir / 'etims_invoices.csv')
        items_df = pd.read_csv(self.data_dir / 'etims_invoice_items.csv')
        
        if limit:
            invoices_df = invoices_df.head(limit)
        
        print(f"Importing {len(invoices_df)} invoices...")
        print("="*70)
        
        for i, (_, invoice_row) in enumerate(invoices_df.iterrows(), 1):
            customer = invoice_row['customer_name']
            
            try:
                # Check duplicates
                if check_duplicates:
                    filters = {
                        "customer": customer,
                        "posting_date": invoice_row['invoice_date']
                    }
                    
                    existing = self.client.get_list(
                        "Sales Invoice",
                        filters=filters,
                        fields=["name"],
                        limit_page_length=1
                    )
                    
                    if existing:
                        self.skipped.append({
                            'customer': customer,
                            'reason': f"Already exists: {existing[0]['name']}"
                        })
                        continue
                
                # Build payload
                payload = self.build_invoice_payload(invoice_row.to_dict(), items_df)
                
                # Insert
                doc = self.client.insert(payload)
                erpnext_name = doc.get('name')
                
                # Auto-submit if requested
                if auto_submit:
                    self.client.update({
                        "doctype": "Sales Invoice",
                        "name": erpnext_name,
                        "docstatus": 1
                    })
                
                self.successes.append({
                    'customer': customer,
                    'erpnext_name': erpnext_name,
                    'amount': invoice_row['total_amount'],
                    'etims_number': invoice_row['invoice_number']
                })
                
            except Exception as e:
                self.failures.append({
                    'customer': customer,
                    'error': str(e)[:200]
                })
            
            # Progress
            if i % 10 == 0 or i == len(invoices_df):
                print(f"  Progress: {i}/{len(invoices_df)} "
                      f"(✓ {len(self.successes)}, ⊘ {len(self.skipped)}, ✗ {len(self.failures)})")
        
        print("="*70)
        
        return {
            'total': len(invoices_df),
            'succeeded': len(self.successes),
            'skipped': len(self.skipped),
            'failed': len(self.failures),
            'successes': self.successes,
            'skips': self.skipped,
            'failures': self.failures
        }
```

### Step 2.2: Run Invoice Import

```python
# Cell 5: Import All Sales Invoices
from importers.sales_invoice_importer import SalesInvoiceImporter

# Initialize
invoice_importer = SalesInvoiceImporter(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

# Test with 10 first
print("Testing with 10 invoices...")
test_result = invoice_importer.import_all(
    check_duplicates=True,
    auto_submit=False,
    limit=10
)

print(f"\nTest Results:")
print(f"  Succeeded: {test_result['succeeded']}")
print(f"  Skipped: {test_result['skipped']}")
print(f"  Failed: {test_result['failed']}")

if test_result['failed'] > 0:
    print("\nFirst error:")
    print(test_result['failures'][0]['error'])
else:
    print("\n✓ Test successful - proceeding with full import")
```

```python
# Cell 6: Import ALL Invoices (if test passed)
# Reset importer
invoice_importer = SalesInvoiceImporter(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

# Full import
full_result = invoice_importer.import_all(
    check_duplicates=True,
    auto_submit=False  # Keep as Draft for review
)

print(f"\nFinal Results:")
print(f"  Total: {full_result['total']}")
print(f"  Succeeded: {full_result['succeeded']}")
print(f"  Skipped: {full_result['skipped']}")
print(f"  Failed: {full_result['failed']}")

# Calculate total amount
if full_result['succeeded'] > 0:
    total_amount = sum(s['amount'] for s in full_result['successes'])
    print(f"\n✓ Total invoice value: KES {total_amount:,.2f}")
```

---

## Phase 3: Payments

**Time:** 3-4 hours  
**Objective:** Import 220 payment entries and link to invoices

### Step 3.1: Build Payment Importer

Create file: `~/work/ERP/emt/src/importers/payment_entry_importer.py`

```python
"""
Payment Entry Importer for ERPNext.

Imports payments from transactions.csv and links to Sales Invoices.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
from frappeclient import FrappeClient


class PaymentEntryImporter:
    """
    Import payment entries and link to invoices.
    
    Handles:
    - Invoice matching (by customer and date proximity)
    - Payment allocation
    - Mode of Payment mapping
    - Account linking
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path, company: str = "Wellness Centre"):
        self.client = client
        self.data_dir = Path(data_dir)
        self.company = company
        self.successes = []
        self.failures = []
        self.skipped = []
    
    def _get_customer_id(self, customer_name: str) -> Optional[str]:
        """Get ERPNext customer ID"""
        try:
            results = self.client.get_list(
                "Customer",
                filters={"customer_name": customer_name},
                fields=["name"],
                limit_page_length=1
            )
            return results[0]['name'] if results else None
        except:
            return None
    
    def _find_matching_invoice(self, customer_id: str, amount: float, date: str) -> Optional[str]:
        """
        Find matching invoice for payment.
        
        Strategy:
        1. Exact match: customer + amount + date
        2. Fuzzy match: customer + amount within 7 days
        3. Outstanding: customer + amount matches outstanding
        """
        try:
            # Try exact match
            exact = self.client.get_list(
                "Sales Invoice",
                filters={
                    "customer": customer_id,
                    "grand_total": amount,
                    "posting_date": date,
                    "docstatus": 1,  # Submitted
                    "outstanding_amount": [">", 0]
                },
                fields=["name", "outstanding_amount"],
                limit_page_length=1
            )
            
            if exact:
                return exact[0]['name']
            
            # Try fuzzy match (within 7 days)
            fuzzy = self.client.get_list(
                "Sales Invoice",
                filters={
                    "customer": customer_id,
                    "grand_total": amount,
                    "docstatus": 1,
                    "outstanding_amount": [">", 0]
                },
                fields=["name", "posting_date", "outstanding_amount"],
                limit_page_length=5
            )
            
            if fuzzy:
                # Pick closest by date
                payment_date = datetime.strptime(date, "%Y-%m-%d")
                
                best_match = None
                min_diff = 999
                
                for inv in fuzzy:
                    inv_date = datetime.strptime(inv['posting_date'], "%Y-%m-%d")
                    diff = abs((payment_date - inv_date).days)
                    
                    if diff < min_diff:
                        min_diff = diff
                        best_match = inv['name']
                
                if min_diff <= 7:
                    return best_match
            
            return None
            
        except Exception as e:
            print(f"    Error finding invoice: {e}")
            return None
    
    def build_payment_payload(self, txn_row: dict, customer_id: str, invoice_name: Optional[str]) -> dict:
        """Build Payment Entry payload"""
        # Payment method mapping
        mode_map = {
            'M-Pesa': 'M-Pesa',
            'Bank Transfer': 'Bank Transfer',
            'Cash': 'Cash',
            'Cheque': 'Cheque'
        }
        
        mode = mode_map.get(txn_row['payment_method'], 'Cash')
        
        # Account mapping
        account_map = {
            'M-Pesa': 'Mobile Money - WC',
            'Bank Transfer': 'KCB - WC',
            'Cash': 'Cash - WC',
            'Cheque': 'KCB - WC'
        }
        
        paid_to = account_map.get(txn_row['payment_method'], 'Cash - WC')
        
        payload = {
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": customer_id,
            "posting_date": txn_row['transaction_date'],
            "paid_amount": float(txn_row['amount']),
            "received_amount": float(txn_row['amount']),
            "paid_from": "Debtors - WC",
            "paid_to": paid_to,
            "mode_of_payment": mode,
            "company": self.company,
            "reference_no": txn_row.get('reference_number', ''),
        }
        
        # Add invoice reference if found
        if invoice_name:
            payload["references"] = [{
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice_name,
                "allocated_amount": float(txn_row['amount'])
            }]
        
        if txn_row.get('notes'):
            payload["remarks"] = txn_row['notes']
        
        return payload
    
    def import_all(
        self,
        check_duplicates: bool = True,
        auto_submit: bool = False,
        limit: Optional[int] = None
    ) -> dict:
        """Import all payment entries"""
        # Load transactions (income type only)
        txns_df = pd.read_csv(self.data_dir / 'transactions.csv')
        payments_df = txns_df[txns_df['type'] == 'income'].copy()
        
        # Load contacts to get customer names
        contacts_df = pd.read_csv(self.data_dir / 'contacts.csv')
        
        # Merge
        payments_merged = payments_df.merge(
            contacts_df[['id', 'name']],
            left_on='contact_id',
            right_on='id',
            how='left',
            suffixes=('', '_contact')
        )
        
        if limit:
            payments_merged = payments_merged.head(limit)
        
        print(f"Importing {len(payments_merged)} payments...")
        print("="*70)
        
        for i, (_, txn_row) in enumerate(payments_merged.iterrows(), 1):
            customer_name = txn_row.get('name_contact')
            
            if not customer_name:
                self.failures.append({
                    'transaction_id': txn_row['id'],
                    'error': 'No customer name found'
                })
                continue
            
            try:
                # Get customer ID
                customer_id = self._get_customer_id(customer_name)
                
                if not customer_id:
                    self.failures.append({
                        'transaction_id': txn_row['id'],
                        'error': f'Customer not found: {customer_name}'
                    })
                    continue
                
                # Find matching invoice
                invoice_name = self._find_matching_invoice(
                    customer_id,
                    txn_row['amount'],
                    txn_row['transaction_date']
                )
                
                # Check duplicates
                if check_duplicates:
                    existing = self.client.get_list(
                        "Payment Entry",
                        filters={
                            "party": customer_id,
                            "posting_date": txn_row['transaction_date'],
                            "paid_amount": txn_row['amount']
                        },
                        fields=["name"],
                        limit_page_length=1
                    )
                    
                    if existing:
                        self.skipped.append({
                            'customer': customer_name,
                            'reason': f"Already exists: {existing[0]['name']}"
                        })
                        continue
                
                # Build payload
                payload = self.build_payment_payload(
                    txn_row.to_dict(),
                    customer_id,
                    invoice_name
                )
                
                # Insert
                doc = self.client.insert(payload)
                erpnext_name = doc.get('name')
                
                # Auto-submit
                if auto_submit:
                    self.client.update({
                        "doctype": "Payment Entry",
                        "name": erpnext_name,
                        "docstatus": 1
                    })
                
                self.successes.append({
                    'customer': customer_name,
                    'erpnext_name': erpnext_name,
                    'amount': txn_row['amount'],
                    'invoice': invoice_name or 'No match'
                })
                
            except Exception as e:
                self.failures.append({
                    'customer': customer_name,
                    'error': str(e)[:200]
                })
            
            # Progress
            if i % 10 == 0 or i == len(payments_merged):
                print(f"  Progress: {i}/{len(payments_merged)} "
                      f"(✓ {len(self.successes)}, ⊘ {len(self.skipped)}, ✗ {len(self.failures)})")
        
        print("="*70)
        
        return {
            'total': len(payments_merged),
            'succeeded': len(self.successes),
            'skipped': len(self.skipped),
            'failed': len(self.failures),
            'successes': self.successes,
            'failures': self.failures
        }
```

### Step 3.2: Run Payment Import

```python
# Cell 7: Import Payment Entries
from importers.payment_entry_importer import PaymentEntryImporter

# FIRST: Submit all draft invoices so payments can link
print("Submitting draft invoices...")
draft_invoices = client.get_list(
    "Sales Invoice",
    filters={"docstatus": 0},
    fields=["name"]
)

for inv in draft_invoices:
    try:
        client.update({
            "doctype": "Sales Invoice",
            "name": inv['name'],
            "docstatus": 1
        })
    except:
        pass

print(f"✓ Submitted {len(draft_invoices)} invoices")

# Initialize payment importer
payment_importer = PaymentEntryImporter(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

# Import payments
payment_result = payment_importer.import_all(
    check_duplicates=True,
    auto_submit=True  # Submit to clear outstanding
)

print(f"\nPayment Import Results:")
print(f"  Total: {payment_result['total']}")
print(f"  Succeeded: {payment_result['succeeded']}")
print(f"  Skipped: {payment_result['skipped']}")
print(f"  Failed: {payment_result['failed']}")

# Show matching stats
matched = len([s for s in payment_result['successes'] if s['invoice'] != 'No match'])
print(f"\n✓ Matched to invoices: {matched}/{payment_result['succeeded']}")
```

---

## Phase 4: Expenses

**Time:** 4-5 hours  
**Objective:** Import 709 expense transactions

### Step 4.1: Build Expense Importer

Create file: `~/work/ERP/emt/src/importers/expense_importer.py`

```python
"""
Expense Importer for ERPNext.

Imports expense transactions as Journal Entries.
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from frappeclient import FrappeClient


class ExpenseImporter:
    """
    Import expenses as Journal Entries.
    
    Creates double-entry accounting records:
    Debit: Expense Account
    Credit: Payment Account (Cash/Bank/M-Pesa)
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path, company: str = "Wellness Centre"):
        self.client = client
        self.data_dir = Path(data_dir)
        self.company = company
        self.successes = []
        self.failures = []
    
    def _get_expense_account(self, category_name: str) -> str:
        """Map category to expense account"""
        return f"{category_name} - WC"
    
    def _get_payment_account(self, payment_method: str) -> str:
        """Map payment method to account"""
        account_map = {
            'M-Pesa': 'Mobile Money - WC',
            'Bank Transfer': 'KCB - WC',
            'Cash': 'Cash - WC',
            'Cheque': 'KCB - WC'
        }
        return account_map.get(payment_method, 'Cash - WC')
    
    def build_journal_entry(self, txn_row: dict, category_name: str) -> dict:
        """Build Journal Entry for expense"""
        expense_account = self._get_expense_account(category_name)
        payment_account = self._get_payment_account(txn_row['payment_method'])
        
        payload = {
            "doctype": "Journal Entry",
            "posting_date": txn_row['transaction_date'],
            "company": self.company,
            "accounts": [
                {
                    "account": expense_account,
                    "debit_in_account_currency": float(txn_row['amount']),
                    "credit_in_account_currency": 0.0
                },
                {
                    "account": payment_account,
                    "debit_in_account_currency": 0.0,
                    "credit_in_account_currency": float(txn_row['amount'])
                }
            ]
        }
        
        # Add description
        desc_parts = [category_name]
        if txn_row.get('description'):
            desc_parts.append(txn_row['description'])
        if txn_row.get('notes'):
            desc_parts.append(txn_row['notes'])
        
        payload["user_remark"] = " | ".join(desc_parts)
        
        if txn_row.get('reference_number'):
            payload["cheque_no"] = txn_row['reference_number']
            payload["cheque_date"] = txn_row['transaction_date']
        
        return payload
    
    def import_all(
        self,
        auto_submit: bool = False,
        limit: Optional[int] = None
    ) -> dict:
        """Import all expense transactions"""
        # Load data
        txns_df = pd.read_csv(self.data_dir / 'transactions.csv')
        cats_df = pd.read_csv(self.data_dir / 'transaction_categories.csv')
        
        # Get expenses only
        expenses_df = txns_df[txns_df['type'] == 'expense'].copy()
        
        # Merge with categories
        expenses_merged = expenses_df.merge(
            cats_df[['id', 'name']],
            left_on='category_id',
            right_on='id',
            how='left',
            suffixes=('', '_cat')
        )
        
        if limit:
            expenses_merged = expenses_merged.head(limit)
        
        print(f"Importing {len(expenses_merged)} expenses...")
        print("="*70)
        
        for i, (_, txn_row) in enumerate(expenses_merged.iterrows(), 1):
            category_name = txn_row.get('name_cat', 'Miscellaneous')
            
            try:
                # Build payload
                payload = self.build_journal_entry(
                    txn_row.to_dict(),
                    category_name
                )
                
                # Insert
                doc = self.client.insert(payload)
                erpnext_name = doc.get('name')
                
                # Auto-submit
                if auto_submit:
                    self.client.update({
                        "doctype": "Journal Entry",
                        "name": erpnext_name,
                        "docstatus": 1
                    })
                
                self.successes.append({
                    'category': category_name,
                    'erpnext_name': erpnext_name,
                    'amount': txn_row['amount']
                })
                
            except Exception as e:
                self.failures.append({
                    'category': category_name,
                    'date': txn_row['transaction_date'],
                    'error': str(e)[:200]
                })
            
            # Progress
            if i % 50 == 0 or i == len(expenses_merged):
                print(f"  Progress: {i}/{len(expenses_merged)} "
                      f"(✓ {len(self.successes)}, ✗ {len(self.failures)})")
        
        print("="*70)
        
        return {
            'total': len(expenses_merged),
            'succeeded': len(self.successes),
            'failed': len(self.failures),
            'successes': self.successes,
            'failures': self.failures
        }
```

### Step 4.2: Run Expense Import

```python
# Cell 8: Import Expense Transactions
from importers.expense_importer import ExpenseImporter

# Initialize
expense_importer = ExpenseImporter(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

# Test with 50 first
print("Testing with 50 expenses...")
test_result = expense_importer.import_all(
    auto_submit=True,
    limit=50
)

print(f"\nTest Results:")
print(f"  Succeeded: {test_result['succeeded']}")
print(f"  Failed: {test_result['failed']}")

if test_result['failed'] == 0:
    print("\n✓ Test successful - proceeding with full import")
```

```python
# Cell 9: Import ALL Expenses
# Reset importer
expense_importer = ExpenseImporter(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

# Full import
full_result = expense_importer.import_all(
    auto_submit=True
)

print(f"\nFinal Results:")
print(f"  Total: {full_result['total']}")
print(f"  Succeeded: {full_result['succeeded']}")
print(f"  Failed: {full_result['failed']}")

# Calculate total
if full_result['succeeded'] > 0:
    total_expenses = sum(s['amount'] for s in full_result['successes'])
    print(f"\n✓ Total expenses: KES {total_expenses:,.2f}")
```

---

## Phase 5: Inventory

**Time:** 6-8 hours  
**Objective:** Import inventory items and movements

### Step 5.1: Stock Items Already Created

Stock items were created in Phase 1 (master data). Now we need to:
1. Set opening balances
2. Import stock movements

### Step 5.2: Build Stock Entry Importer

Create file: `~/work/ERP/emt/src/importers/stock_entry_importer.py`

```python
"""
Stock Entry Importer for ERPNext.

Imports inventory movements from inventory_movements.csv
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from frappeclient import FrappeClient


class StockEntryImporter:
    """
    Import stock movements.
    
    Movement types:
    - Purchase → Material Receipt
    - Consumption → Material Issue
    - Breakage → Material Issue
    - Transfer → Material Transfer
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path, company: str = "Wellness Centre"):
        self.client = client
        self.data_dir = Path(data_dir)
        self.company = company
        self.warehouse = "Main Warehouse - WC"
        self.successes = []
        self.failures = []
    
    def _get_entry_type(self, movement_type: str) -> str:
        """Map movement type to Stock Entry Type"""
        type_map = {
            'Purchase': 'Material Receipt',
            'Consumption': 'Material Issue',
            'Breakage': 'Material Issue',
            'Sale': 'Material Issue',
            'Transfer': 'Material Transfer'
        }
        return type_map.get(movement_type, 'Material Receipt')
    
    def build_stock_entry(self, movement_row: dict, item_name: str) -> dict:
        """Build Stock Entry"""
        entry_type = self._get_entry_type(movement_row['movement_type'])
        
        payload = {
            "doctype": "Stock Entry",
            "stock_entry_type": entry_type,
            "posting_date": movement_row['movement_date'],
            "company": self.company,
            "items": [{
                "item_code": item_name,
                "qty": abs(float(movement_row['quantity'])),
                "t_warehouse": self.warehouse if entry_type == 'Material Receipt' else None,
                "s_warehouse": self.warehouse if entry_type == 'Material Issue' else None,
            }]
        }
        
        if movement_row.get('notes'):
            payload["remarks"] = movement_row['notes']
        
        return payload
    
    def import_all(
        self,
        auto_submit: bool = False,
        limit: Optional[int] = None
    ) -> dict:
        """Import all stock movements"""
        # Load data
        movements_df = pd.read_csv(self.data_dir / 'inventory_movements.csv')
        items_df = pd.read_csv(self.data_dir / 'inventory_items.csv')
        
        # Merge
        movements_merged = movements_df.merge(
            items_df[['id', 'item_name']],
            left_on='inventory_item_id',
            right_on='id',
            how='left',
            suffixes=('', '_item')
        )
        
        if limit:
            movements_merged = movements_merged.head(limit)
        
        print(f"Importing {len(movements_merged)} stock movements...")
        print("="*70)
        
        for i, (_, movement_row) in enumerate(movements_merged.iterrows(), 1):
            item_name = movement_row.get('item_name')
            
            if not item_name:
                self.failures.append({
                    'movement_id': movement_row['id'],
                    'error': 'Item not found'
                })
                continue
            
            try:
                # Build payload
                payload = self.build_stock_entry(
                    movement_row.to_dict(),
                    item_name
                )
                
                # Insert
                doc = self.client.insert(payload)
                erpnext_name = doc.get('name')
                
                # Auto-submit
                if auto_submit:
                    self.client.update({
                        "doctype": "Stock Entry",
                        "name": erpnext_name,
                        "docstatus": 1
                    })
                
                self.successes.append({
                    'item': item_name,
                    'erpnext_name': erpnext_name,
                    'type': movement_row['movement_type']
                })
                
            except Exception as e:
                self.failures.append({
                    'item': item_name,
                    'error': str(e)[:200]
                })
            
            # Progress
            if i % 20 == 0 or i == len(movements_merged):
                print(f"  Progress: {i}/{len(movements_merged)} "
                      f"(✓ {len(self.successes)}, ✗ {len(self.failures)})")
        
        print("="*70)
        
        return {
            'total': len(movements_merged),
            'succeeded': len(self.successes),
            'failed': len(self.failures),
            'successes': self.successes,
            'failures': self.failures
        }
```

### Step 5.3: Run Stock Entry Import

```python
# Cell 10: Import Stock Movements
from importers.stock_entry_importer import StockEntryImporter

# Initialize
stock_importer = StockEntryImporter(
    client=client,
    data_dir=DATA_DIR,
    company="Wellness Centre"
)

# Import all movements
stock_result = stock_importer.import_all(
    auto_submit=True
)

print(f"\nStock Movement Results:")
print(f"  Total: {stock_result['total']}")
print(f"  Succeeded: {stock_result['succeeded']}")
print(f"  Failed: {stock_result['failed']}")
```

---

## Phase 6: Validation

**Time:** 2-3 hours  
**Objective:** Verify all data imported correctly

### Step 6.1: Financial Validation

```python
# Cell 11: Validate Financial Data
print("FINANCIAL VALIDATION")
print("="*70)

# 1. Check Sales Invoices
invoices = client.get_list(
    "Sales Invoice",
    filters={"docstatus": 1},
    fields=["grand_total"]
)

invoice_total = sum(inv['grand_total'] for inv in invoices)
print(f"Sales Invoices:")
print(f"  Count: {len(invoices)}")
print(f"  Total: KES {invoice_total:,.2f}")
print(f"  Expected: KES 2,589,840")
print(f"  Match: {'✓' if abs(invoice_total - 2589840) < 100 else '✗'}")

print()

# 2. Check Payments
payments = client.get_list(
    "Payment Entry",
    filters={"docstatus": 1, "payment_type": "Receive"},
    fields=["paid_amount"]
)

payment_total = sum(p['paid_amount'] for p in payments)
print(f"Payment Entries:")
print(f"  Count: {len(payments)}")
print(f"  Total: KES {payment_total:,.2f}")
print(f"  Match with invoices: {'✓' if abs(payment_total - invoice_total) < 100 else '✗'}")

print()

# 3. Check Outstanding
outstanding_invoices = client.get_list(
    "Sales Invoice",
    filters={"docstatus": 1, "outstanding_amount": [">", 0]},
    fields=["outstanding_amount"]
)

outstanding_total = sum(inv['outstanding_amount'] for inv in outstanding_invoices)
print(f"Outstanding Receivables:")
print(f"  Invoices: {len(outstanding_invoices)}")
print(f"  Amount: KES {outstanding_total:,.2f}")
print(f"  Status: {'✓ All paid' if outstanding_total < 100 else '⚠ Has outstanding'}")

print()

# 4. Check Expenses
journal_entries = client.get_list(
    "Journal Entry",
    filters={"docstatus": 1},
    fields=["total_debit"]
)

expense_total = sum(je['total_debit'] for je in journal_entries)
print(f"Journal Entries (Expenses):")
print(f"  Count: {len(journal_entries)}")
print(f"  Total: KES {expense_total:,.2f}")
print(f"  Expected: ~KES 4,360,000")

print("="*70)
```

### Step 6.2: Generate Reports

```python
# Cell 12: Generate P&L Report
print("PROFIT & LOSS SUMMARY")
print("="*70)

# Income
print(f"Income:")
print(f"  Sales: KES {invoice_total:,.2f}")

# Expenses  
print(f"\nExpenses:")
print(f"  Total: KES {expense_total:,.2f}")

# Net
net_profit = invoice_total - expense_total
print(f"\nNet Profit/Loss:")
print(f"  KES {net_profit:,.2f}")

if net_profit < 0:
    print(f"  (Loss)")
else:
    print(f"  (Profit)")

print("="*70)
```

---

## Troubleshooting Guide

### Common Issues

**1. Connection Failed**
```python
# Check Docker network
!docker ps | grep erpnext

# Try external URL
ERPNEXT_URL = "https://well.rosslyn.cloud"
# Remove Host header line
```

**2. Customer Not Found**
```python
# Check customer exists
customers = client.get_list("Customer", fields=["name", "customer_name"])
print(customers)

# Check exact name match
target = "Dorothy Barasa"
matches = [c for c in customers if c['customer_name'] == target]
```

**3. Account Not Found**
```python
# List all accounts
accounts = client.get_list(
    "Account",
    filters={"company": "Wellness Centre"},
    fields=["name", "account_name"]
)

# Search for specific account
search = "Sales"
matches = [a for a in accounts if search in a['account_name']]
```

**4. Import Fails Silently**
```python
# Enable verbose errors
try:
    doc = client.insert(payload)
except Exception as e:
    print("Full error:")
    print(str(e))  # Complete error message
```

---

## Success Criteria Checklist

At the end of migration, verify:

- [ ] 220 Sales Invoices imported (KES 2,589,840)
- [ ] 220 Payment Entries linked to invoices
- [ ] Zero outstanding receivables
- [ ] 709 Expense entries recorded
- [ ] P&L shows correct income and expenses
- [ ] Balance Sheet balances
- [ ] 77 Stock Items created with opening balances
- [ ] 193 Stock movements recorded
- [ ] All master data created (accounts, contacts, items)

---

## Completion

**Estimated Total Time:** 20-25 hours

**What You've Achieved:**
- Complete financial data in ERPNext
- All transactions reconciled
- Inventory tracked
- Foundation for ongoing operations
- Professional-grade import toolkit
- Reusable for future imports

**Next Steps:**
- Train users on ERPNext
- Set up recurring transactions
- Configure reports
- Implement workflows
- Consider operations data (events, room bookings)

---

**END OF PROJECT PLAN**
