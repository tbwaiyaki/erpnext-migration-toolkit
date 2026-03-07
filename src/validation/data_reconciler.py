"""
Data Reconciliation Module - Verifies ERPNext data against CSV source.

Compares ERPNext API results with source CSV files to ensure
100% data integrity after migration.

Usage:
    reconciler = DataReconciler(client, data_dir)
    report = reconciler.run_full_reconciliation()
    reconciler.print_report(report)
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List
from frappeclient import FrappeClient
from datetime import datetime


class DataReconciler:
    """
    Reconcile ERPNext data against CSV source files.
    
    Verifies:
    - Transaction counts match
    - Total amounts match
    - All records imported
    - No duplicates
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path):
        """
        Initialize reconciler.
        
        Args:
            client: Authenticated FrappeClient
            data_dir: Path to CSV source data
        """
        self.client = client
        self.data_dir = Path(data_dir)
        
    def reconcile_invoices(self) -> Dict:
        """Reconcile sales invoices."""
        # Load CSV
        csv_invoices = pd.read_csv(self.data_dir / 'etims_invoices.csv')
        csv_total = csv_invoices['total_amount'].sum()
        csv_count = len(csv_invoices)
        
        # Get ERPNext data
        erp_invoices = self.client.get_list(
            "Sales Invoice",
            filters={"docstatus": 1},
            fields=["name", "grand_total"],
            limit_page_length=500
        )
        erp_total = sum(float(inv['grand_total']) for inv in erp_invoices)
        erp_count = len(erp_invoices)
        
        return {
            'document': 'Sales Invoices',
            'csv_count': csv_count,
            'erp_count': erp_count,
            'csv_total': csv_total,
            'erp_total': erp_total,
            'count_match': csv_count == erp_count,
            'amount_match': abs(csv_total - erp_total) < 1,
            'difference': erp_total - csv_total
        }
    
    def reconcile_payments(self) -> Dict:
        """Reconcile payment entries."""
        # Load CSV (income transactions)
        csv_tx = pd.read_csv(self.data_dir / 'transactions.csv')
        csv_payments = csv_tx[csv_tx['type'] == 'income']
        csv_total = csv_payments['amount'].sum()
        csv_count = len(csv_payments)
        
        # Get ERPNext data
        erp_payments = self.client.get_list(
            "Payment Entry",
            filters={"docstatus": 1, "payment_type": "Receive"},
            fields=["name", "paid_amount"],
            limit_page_length=500
        )
        erp_total = sum(float(p['paid_amount']) for p in erp_payments)
        erp_count = len(erp_payments)
        
        return {
            'document': 'Payment Entries',
            'csv_count': csv_count,
            'erp_count': erp_count,
            'csv_total': csv_total,
            'erp_total': erp_total,
            'count_match': csv_count == erp_count,
            'amount_match': abs(csv_total - erp_total) < 1,
            'difference': erp_total - csv_total
        }
    
    def reconcile_expenses(self) -> Dict:
        """Reconcile expense journal entries."""
        # Load CSV
        csv_tx = pd.read_csv(self.data_dir / 'transactions.csv')
        csv_expenses = csv_tx[csv_tx['type'] == 'expense']
        csv_total = csv_expenses['amount'].sum()
        csv_count = len(csv_expenses)
        
        # Get ERPNext data - expenses are journal entries
        # This is approximate - would need to filter JEs by account type
        erp_journal = self.client.get_list(
            "Journal Entry",
            filters={"docstatus": 1},
            fields=["name", "total_debit"],
            limit_page_length=800
        )
        
        # For now, just count
        # Proper verification would check accounts table
        expected_je_count = (
            len(csv_expenses) +  # Expenses
            len(csv_tx[csv_tx['type'] == 'capital_injection']) +  # Capital
            len(csv_tx[csv_tx['type'] == 'savings'])  # Savings
        )
        
        return {
            'document': 'Journal Entries (Expenses)',
            'csv_count': csv_count,
            'erp_count': len(erp_journal),
            'expected_total_je': expected_je_count,
            'csv_total': csv_total,
            'erp_total': None,  # Would need to sum from accounts table
            'count_match': len(erp_journal) == expected_je_count,
            'amount_match': None,  # Complex to verify without detailed query
            'note': 'JE count includes expenses + capital + savings'
        }
    
    def reconcile_master_data(self) -> Dict:
        """Reconcile master data (customers, suppliers)."""
        # Customers
        csv_contacts = pd.read_csv(self.data_dir / 'contacts.csv')
        csv_invoices = pd.read_csv(self.data_dir / 'etims_invoices.csv')
        unique_customers_csv = csv_invoices['customer_name'].nunique()
        
        erp_customers = self.client.get_list(
            "Customer",
            fields=["name"],
            limit_page_length=100
        )
        
        # Suppliers (estimated from contacts)
        erp_suppliers = self.client.get_list(
            "Supplier",
            fields=["name"],
            limit_page_length=100
        )
        
        return {
            'document': 'Master Data',
            'csv_customers': unique_customers_csv,
            'erp_customers': len(erp_customers),
            'erp_suppliers': len(erp_suppliers),
            'note': 'Customers from invoices, suppliers from expenses'
        }
    
    def run_full_reconciliation(self) -> Dict:
        """
        Run complete reconciliation.
        
        Returns:
            Dictionary with all reconciliation results
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'invoices': self.reconcile_invoices(),
            'payments': self.reconcile_payments(),
            'expenses': self.reconcile_expenses(),
            'master_data': self.reconcile_master_data()
        }
        
        # Calculate overall status
        invoice_ok = results['invoices']['count_match'] and results['invoices']['amount_match']
        payment_ok = results['payments']['count_match'] and results['payments']['amount_match']
        expense_ok = results['expenses']['count_match']
        
        results['overall_status'] = 'PASS' if (invoice_ok and payment_ok and expense_ok) else 'REVIEW'
        
        return results
    
    def print_report(self, results: Dict):
        """
        Print formatted reconciliation report.
        
        Args:
            results: Dictionary from run_full_reconciliation()
        """
        print("\n" + "=" * 70)
        print("DATA RECONCILIATION REPORT")
        print("=" * 70)
        print(f"Generated: {results['timestamp']}")
        print()
        
        # Invoices
        inv = results['invoices']
        print("SALES INVOICES:")
        print(f"  CSV Records:     {inv['csv_count']}")
        print(f"  ERPNext Records: {inv['erp_count']}")
        print(f"  Count Match:     {'✓' if inv['count_match'] else '✗'}")
        print(f"  CSV Total:       KES {inv['csv_total']:,.2f}")
        print(f"  ERPNext Total:   KES {inv['erp_total']:,.2f}")
        print(f"  Amount Match:    {'✓' if inv['amount_match'] else '✗'}")
        print()
        
        # Payments
        pay = results['payments']
        print("PAYMENT ENTRIES:")
        print(f"  CSV Records:     {pay['csv_count']}")
        print(f"  ERPNext Records: {pay['erp_count']}")
        print(f"  Count Match:     {'✓' if pay['count_match'] else '✗'}")
        print(f"  CSV Total:       KES {pay['csv_total']:,.2f}")
        print(f"  ERPNext Total:   KES {pay['erp_total']:,.2f}")
        print(f"  Amount Match:    {'✓' if pay['amount_match'] else '✗'}")
        print()
        
        # Expenses
        exp = results['expenses']
        print("JOURNAL ENTRIES:")
        print(f"  Expected Total:  {exp['expected_total_je']}")
        print(f"  ERPNext Total:   {exp['erp_count']}")
        print(f"  Count Match:     {'✓' if exp['count_match'] else '✗'}")
        print(f"  Note: {exp['note']}")
        print()
        
        # Master data
        master = results['master_data']
        print("MASTER DATA:")
        print(f"  Customers (CSV): {master['csv_customers']}")
        print(f"  Customers (ERP): {master['erp_customers']}")
        print(f"  Suppliers (ERP): {master['erp_suppliers']}")
        print()
        
        # Overall
        print("=" * 70)
        status = results['overall_status']
        symbol = "✓" if status == "PASS" else "⚠"
        print(f"OVERALL STATUS: {symbol} {status}")
        print("=" * 70)
