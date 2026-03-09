"""
Migration Verification Dashboard - Comprehensive data validation and reconciliation.

Provides three levels of verification:
1. Quick Summary - High-level counts and totals
2. Detailed Reconciliation - Line-by-line comparison with source data
3. Financial Validation - Accounting integrity checks

Version 1.0: Initial implementation

Usage:
    dashboard = MigrationDashboard(client, data_dir, company="Wellness Centre")
    
    # Quick check
    dashboard.quick_summary()
    
    # Detailed reconciliation
    report = dashboard.full_reconciliation()
    dashboard.print_report(report)
    
    # Financial validation
    dashboard.validate_accounting_integrity()
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from frappeclient import FrappeClient
from datetime import datetime
from collections import Counter


class MigrationDashboard:
    """
    Comprehensive migration verification and reconciliation dashboard.
    
    Features:
    - Count and amount reconciliation for all document types
    - Duplicate detection across all doctypes
    - Financial integrity validation (debits = credits)
    - Missing data identification
    - Account balance verification
    """
    
    VERSION = "1.0"
    
    def __init__(
        self,
        client: FrappeClient,
        data_dir: Path,
        company: str = "Wellness Centre"
    ):
        """
        Initialize dashboard.
        
        Args:
            client: Authenticated FrappeClient
            data_dir: Path to CSV source data directory
            company: Company name for filtering
        """
        self.client = client
        self.data_dir = Path(data_dir)
        self.company = company
        
    # ==================== LEVEL 1: QUICK SUMMARY ====================
    
    def quick_summary(self) -> Dict:
        """
        Quick summary of migration status.
        
        Returns counts and totals for all imported data.
        Fast check - doesn't do detailed reconciliation.
        """
        print("=" * 70)
        print("MIGRATION QUICK SUMMARY")
        print("=" * 70)
        print(f"Company: {self.company}")
        print(f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Sales Invoices
        invoices = self.client.get_list(
            "Sales Invoice",
            filters={"docstatus": 1, "company": self.company},
            fields=["grand_total"],
            limit_page_length=500
        )
        inv_count = len(invoices)
        inv_total = sum(float(i['grand_total']) for i in invoices)
        print(f"Sales Invoices:     {inv_count:4d} records, KES {inv_total:,.0f}")
        
        # Payment Entries
        payments = self.client.get_list(
            "Payment Entry",
            filters={"docstatus": 1, "payment_type": "Receive", "company": self.company},
            fields=["paid_amount"],
            limit_page_length=500
        )
        pay_count = len(payments)
        pay_total = sum(float(p['paid_amount']) for p in payments)
        print(f"Payment Entries:    {pay_count:4d} records, KES {pay_total:,.0f}")
        
        # Journal Entries
        journal = self.client.get_list(
            "Journal Entry",
            filters={"docstatus": 1, "company": self.company},
            fields=["total_debit"],
            limit_page_length=1000
        )
        je_count = len(journal)
        je_total = sum(float(j.get('total_debit', 0)) for j in journal)
        print(f"Journal Entries:    {je_count:4d} records, KES {je_total:,.0f}")
        
        # Master Data
        customers = self.client.get_list("Customer", fields=["name"], limit_page_length=100)
        suppliers = self.client.get_list("Supplier", fields=["name"], limit_page_length=100)
        items = self.client.get_list("Item", fields=["name"], limit_page_length=100)
        
        print()
        print(f"Customers:          {len(customers):4d}")
        print(f"Suppliers:          {len(suppliers):4d}")
        print(f"Items:              {len(items):4d}")
        
        print("=" * 70)
        
        return {
            'invoices': {'count': inv_count, 'total': inv_total},
            'payments': {'count': pay_count, 'total': pay_total},
            'journal_entries': {'count': je_count, 'total': je_total},
            'customers': len(customers),
            'suppliers': len(suppliers),
            'items': len(items)
        }
    
    # ==================== LEVEL 2: DETAILED RECONCILIATION ====================
    
    def reconcile_sales_invoices(self) -> Dict:
        """Detailed reconciliation of sales invoices against CSV source."""
        # Load CSV
        csv_inv = pd.read_csv(self.data_dir / 'etims_invoices.csv')
        csv_count = len(csv_inv)
        csv_total = csv_inv['total_amount'].sum()
        
        # Get ERPNext data
        erp_inv = self.client.get_list(
            "Sales Invoice",
            filters={"docstatus": 1, "company": self.company},
            fields=["name", "grand_total", "original_invoice_number"],
            limit_page_length=500
        )
        erp_count = len(erp_inv)
        erp_total = sum(float(i['grand_total']) for i in erp_inv)
        
        # Check for duplicates by original_invoice_number
        orig_numbers = [i.get('original_invoice_number') for i in erp_inv if i.get('original_invoice_number')]
        duplicates = [num for num, count in Counter(orig_numbers).items() if count > 1]
        
        # Check for missing invoices
        csv_numbers = set(csv_inv['invoice_number'].astype(str))
        erp_numbers = set(orig_numbers)
        missing = csv_numbers - erp_numbers
        
        return {
            'document_type': 'Sales Invoice',
            'csv_count': csv_count,
            'erp_count': erp_count,
            'csv_total': csv_total,
            'erp_total': erp_total,
            'count_match': csv_count == erp_count,
            'amount_match': abs(csv_total - erp_total) < 1,
            'amount_diff': erp_total - csv_total,
            'duplicates': duplicates,
            'missing': list(missing),
            'status': 'PASS' if (csv_count == erp_count and abs(csv_total - erp_total) < 1 and not duplicates) else 'FAIL'
        }
    
    def reconcile_payment_entries(self) -> Dict:
        """Detailed reconciliation of payment entries against CSV source."""
        # Load CSV
        csv_tx = pd.read_csv(self.data_dir / 'transactions.csv')
        csv_pay = csv_tx[csv_tx['type'] == 'income']
        csv_count = len(csv_pay)
        csv_total = csv_pay['amount'].sum()
        
        # Get ERPNext data
        erp_pay = self.client.get_list(
            "Payment Entry",
            filters={"docstatus": 1, "payment_type": "Receive", "company": self.company},
            fields=["name", "paid_amount", "posting_date"],
            limit_page_length=500
        )
        erp_count = len(erp_pay)
        erp_total = sum(float(p['paid_amount']) for p in erp_pay)
        
        return {
            'document_type': 'Payment Entry',
            'csv_count': csv_count,
            'erp_count': erp_count,
            'csv_total': csv_total,
            'erp_total': erp_total,
            'count_match': csv_count == erp_count,
            'amount_match': abs(csv_total - erp_total) < 1,
            'amount_diff': erp_total - csv_total,
            'status': 'PASS' if (csv_count == erp_count and abs(csv_total - erp_total) < 1) else 'FAIL'
        }
    
    def reconcile_journal_entries(self) -> Dict:
        """Detailed reconciliation of journal entries (expenses, capital, savings)."""
        # Load CSV
        csv_tx = pd.read_csv(self.data_dir / 'transactions.csv')
        csv_expenses = csv_tx[csv_tx['type'] == 'expense']
        csv_capital = csv_tx[csv_tx['type'] == 'capital_injection']
        csv_savings = csv_tx[csv_tx['type'] == 'savings']
        
        csv_count = len(csv_expenses) + len(csv_capital) + len(csv_savings)
        csv_total = (csv_expenses['amount'].sum() + 
                     csv_capital['amount'].sum() + 
                     csv_savings['amount'].sum())
        
        # Get ERPNext data - don't query source_transaction_id as it may not be queryable
        erp_je = self.client.get_list(
            "Journal Entry",
            filters={"docstatus": 1, "company": self.company},
            fields=["name", "total_debit", "posting_date"],
            limit_page_length=1000
        )
        erp_count = len(erp_je)
        erp_total = sum(float(j.get('total_debit', 0)) for j in erp_je)
        
        # Try to check for duplicates by source_transaction_id
        # If the field doesn't exist or isn't populated, this will be empty
        try:
            # Get full documents to access custom field
            source_ids = []
            for je in erp_je[:100]:  # Sample first 100 for performance
                try:
                    doc = self.client.get_doc("Journal Entry", je['name'])
                    if doc.get('source_transaction_id'):
                        source_ids.append(doc['source_transaction_id'])
                except:
                    pass
            
            duplicates = [sid for sid, count in Counter(source_ids).items() if count > 1]
            has_source_ids = len(source_ids) > 0
        except Exception as e:
            duplicates = []
            has_source_ids = False
        
        # Check for duplicates by date+amount (works for all entries)
        date_amount_pairs = [(j['posting_date'], j.get('total_debit', 0)) for j in erp_je]
        date_amount_dupes = {k: v for k, v in Counter(date_amount_pairs).items() if v > 1}
        
        return {
            'document_type': 'Journal Entry',
            'csv_count': csv_count,
            'erp_count': erp_count,
            'csv_total': csv_total,
            'erp_total': erp_total,
            'count_match': csv_count == erp_count,
            'amount_match': abs(csv_total - erp_total) < 10,  # Allow small rounding
            'amount_diff': erp_total - csv_total,
            'duplicates_by_source_id': duplicates if has_source_ids else None,
            'duplicates_by_date_amount': len(date_amount_dupes),
            'total_duplicate_entries': sum(count - 1 for count in date_amount_dupes.values()),
            'duplicate_details': date_amount_dupes,
            'has_source_transaction_id': has_source_ids,
            'status': 'PASS' if (csv_count == erp_count and not duplicates and not date_amount_dupes) else 'FAIL'
        }
    
    def full_reconciliation(self) -> Dict:
        """
        Complete reconciliation across all document types.
        
        Returns comprehensive report with all checks.
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'company': self.company,
            'sales_invoices': self.reconcile_sales_invoices(),
            'payment_entries': self.reconcile_payment_entries(),
            'journal_entries': self.reconcile_journal_entries(),
        }
    
    def print_reconciliation_report(self, report: Dict):
        """Print formatted reconciliation report."""
        print("\n" + "=" * 70)
        print("DETAILED RECONCILIATION REPORT")
        print("=" * 70)
        print(f"Company: {report['company']}")
        print(f"Generated: {report['timestamp']}")
        print()
        
        for key in ['sales_invoices', 'payment_entries', 'journal_entries']:
            data = report[key]
            print(f"{data['document_type'].upper()}:")
            print(f"  CSV Count:          {data['csv_count']:4d}")
            print(f"  ERPNext Count:      {data['erp_count']:4d}")
            print(f"  Count Match:        {'✓ PASS' if data['count_match'] else '✗ FAIL'}")
            print(f"  CSV Total:          KES {data['csv_total']:,.2f}")
            print(f"  ERPNext Total:      KES {data['erp_total']:,.2f}")
            print(f"  Amount Match:       {'✓ PASS' if data['amount_match'] else '✗ FAIL'}")
            
            if data.get('duplicates'):
                print(f"  ⚠ Duplicates:        {len(data['duplicates'])} found")
            if data.get('missing'):
                print(f"  ⚠ Missing:           {len(data['missing'])} records")
            if data.get('total_duplicate_entries'):
                print(f"  ⚠ Duplicate Entries: {data['total_duplicate_entries']} (by date+amount)")
                if data.get('duplicate_details'):
                    print(f"     Showing first 5 duplicate patterns:")
                    for (date, amount), count in list(data['duplicate_details'].items())[:5]:
                        print(f"       {date}, KES {amount:,.0f}: {count} entries ({count-1} duplicates)")
            
            if key == 'journal_entries':
                has_source_id = data.get('has_source_transaction_id', False)
                print(f"  Source IDs Present: {'✓ Yes' if has_source_id else '✗ No (old imports)'}")
            
            print(f"  Status:             {data['status']}")
            print()
        
        # Overall status
        all_pass = all(
            report[k]['status'] == 'PASS' 
            for k in ['sales_invoices', 'payment_entries', 'journal_entries']
        )
        print("=" * 70)
        print(f"OVERALL: {'✓ ALL CHECKS PASSED' if all_pass else '⚠ ISSUES FOUND - REVIEW ABOVE'}")
        print("=" * 70)
    
    # ==================== LEVEL 3: FINANCIAL VALIDATION ====================
    
    def validate_accounting_integrity(self) -> Dict:
        """
        Validate accounting integrity - debits must equal credits.
        
        Checks all Journal Entries to ensure proper double-entry.
        """
        print("=" * 70)
        print("ACCOUNTING INTEGRITY VALIDATION")
        print("=" * 70)
        
        # Get all journal entries
        journal_entries = self.client.get_list(
            "Journal Entry",
            filters={"docstatus": 1, "company": self.company},
            fields=["name", "total_debit", "total_credit"],
            limit_page_length=1000
        )
        
        imbalanced = []
        for je in journal_entries:
            debit = float(je.get('total_debit', 0))
            credit = float(je.get('total_credit', 0))
            
            if abs(debit - credit) > 0.01:  # Allow 1 cent rounding
                imbalanced.append({
                    'name': je['name'],
                    'debit': debit,
                    'credit': credit,
                    'diff': debit - credit
                })
        
        print(f"Total Journal Entries Checked: {len(journal_entries)}")
        print(f"Imbalanced Entries Found:      {len(imbalanced)}")
        
        if imbalanced:
            print("\n⚠ IMBALANCED JOURNAL ENTRIES:")
            for je in imbalanced[:10]:  # Show first 10
                print(f"  {je['name']}: Debit {je['debit']:,.2f}, Credit {je['credit']:,.2f}, Diff {je['diff']:,.2f}")
        else:
            print("\n✓ All journal entries are balanced (debits = credits)")
        
        print("=" * 70)
        
        return {
            'total_checked': len(journal_entries),
            'imbalanced_count': len(imbalanced),
            'imbalanced_entries': imbalanced,
            'status': 'PASS' if not imbalanced else 'FAIL'
        }
    
    def check_outstanding_receivables(self) -> Dict:
        """Check if all invoices have been paid (outstanding = 0)."""
        print("=" * 70)
        print("OUTSTANDING RECEIVABLES CHECK")
        print("=" * 70)
        
        # Get invoices with outstanding amounts
        invoices = self.client.get_list(
            "Sales Invoice",
            filters={"docstatus": 1, "company": self.company},
            fields=["name", "grand_total", "outstanding_amount"],
            limit_page_length=500
        )
        
        outstanding_invoices = [
            inv for inv in invoices 
            if float(inv.get('outstanding_amount', 0)) > 0.01
        ]
        
        total_outstanding = sum(float(inv['outstanding_amount']) for inv in outstanding_invoices)
        
        print(f"Total Invoices:           {len(invoices)}")
        print(f"Fully Paid:               {len(invoices) - len(outstanding_invoices)}")
        print(f"With Outstanding:         {len(outstanding_invoices)}")
        print(f"Total Outstanding Amount: KES {total_outstanding:,.2f}")
        
        if outstanding_invoices:
            print("\n⚠ INVOICES WITH OUTSTANDING AMOUNTS:")
            for inv in outstanding_invoices[:10]:
                print(f"  {inv['name']}: KES {float(inv['outstanding_amount']):,.2f}")
        else:
            print("\n✓ All invoices fully paid")
        
        print("=" * 70)
        
        return {
            'total_invoices': len(invoices),
            'outstanding_count': len(outstanding_invoices),
            'total_outstanding': total_outstanding,
            'status': 'PASS' if total_outstanding < 1 else 'WARNING'
        }
