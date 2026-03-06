"""
Payment Entry Importer - Import invoice payments into ERPNext.

Handles batch import of payment entries linked to sales invoices,
with proper mode of payment mapping and account reconciliation.
"""

import pandas as pd
from typing import Dict, List
from frappeclient import FrappeClient
from datetime import datetime


class PaymentEntryImporter:
    """
    Import payment entries for sales invoices.
    
    Links payments to invoices based on etims_invoice_id,
    maps payment methods, and reconciles accounts.
    
    Usage:
        importer = PaymentEntryImporter(client, "Wellness Centre")
        results = importer.import_batch(transactions_df, invoices_df)
    """
    
    VERSION = "3.0-duplicate-prevention"  # Version marker
    
    # Payment method mapping
    PAYMENT_MODE_MAP = {
        'Cash': 'Cash',
        'M-Pesa': 'M-Pesa',
        'Bank Transfer': 'Bank Transfer',
        'Cheque': 'Bank Transfer'
    }
    
    def __init__(self, client: FrappeClient, company: str):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
        """
        self.client = client
        self.company = company
        self.results = {
            'successful': 0,
            'failed': 0,
            'skipped': 0,  # Added for duplicate detection
            'errors': []
        }
        
        # Cache accounts and invoices
        self._accounts_cache = None
        self._invoices_cache = {}
    
    def import_batch(
        self,
        transactions_df: pd.DataFrame,
        invoices_df: pd.DataFrame
    ) -> Dict:
        """
        Import batch of payment entries.
        
        Args:
            transactions_df: Payment transactions (filtered for income type)
            invoices_df: Invoice data for matching
            
        Returns:
            Results dict with successful/failed counts
        """
        # Filter for payment transactions
        payments = transactions_df[
            transactions_df['etims_invoice_id'].notna()
        ].copy()
        
        print(f"[PaymentEntryImporter {self.VERSION}]")
        print(f"Importing {len(payments)} payment entries...")
        
        # Build invoice lookup
        self._build_invoice_cache(invoices_df)
        
        # Load accounts
        self._load_accounts()
        
        for idx, pay_row in payments.iterrows():
            try:
                # Get invoice details first
                invoice_id = int(pay_row['etims_invoice_id'])
                invoice_number = self._invoices_cache.get(invoice_id)
                
                if not invoice_number:
                    raise ValueError(f"Invoice ID {invoice_id} not found in source data")
                
                # Find invoice in ERPNext
                invoices = self.client.get_list(
                    "Sales Invoice",
                    filters={
                        "docstatus": 1,
                        "original_invoice_number": invoice_number
                    },
                    fields=["name", "outstanding_amount"],
                    limit_page_length=1
                )
                
                if not invoices:
                    raise ValueError(f"ERPNext invoice not found for {invoice_number}")
                
                invoice = invoices[0]
                
                # Check if already paid (outstanding = 0)
                if invoice['outstanding_amount'] == 0:
                    self.results['skipped'] += 1
                    if self.results['skipped'] % 50 == 0:
                        print(f"  Skipped {self.results['skipped']} (already paid)...")
                    continue
                
                # Build payment document
                payment_doc = self._build_payment_doc(pay_row)
                
                # Insert and submit
                created = self.client.insert(payment_doc)
                
                # Submit by updating docstatus (submit() method is broken)
                created['docstatus'] = 1
                self.client.update(created)
                
                self.results['successful'] += 1
                
                # Progress indicator
                if self.results['successful'] % 50 == 0:
                    print(f"  Imported {self.results['successful']}...")
                
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'transaction_id': pay_row['id'],
                    'invoice_id': pay_row.get('etims_invoice_id'),
                    'error': str(e)[:200]
                })
        
        return self.results
    
    def _build_invoice_cache(self, invoices_df: pd.DataFrame):
        """Build lookup dict: invoice_id -> invoice_number mapping."""
        for _, inv in invoices_df.iterrows():
            self._invoices_cache[inv['id']] = inv['invoice_number']
    
    def _load_accounts(self):
        """Load company accounts for payment linking."""
        if self._accounts_cache:
            return
        
        # Get default debtors account
        company_doc = self.client.get_doc("Company", self.company)
        
        self._accounts_cache = {
            'debtors': company_doc.get('default_receivable_account'),
            'cash': company_doc.get('default_cash_account'),
        }
    
    def _build_payment_doc(self, pay_row: pd.Series) -> Dict:
        """
        Build ERPNext Payment Entry document.
        
        Args:
            pay_row: Payment transaction row
            
        Returns:
            Payment Entry document dict
        """
        # Parse payment date
        payment_date = pd.to_datetime(pay_row['transaction_date']).strftime('%Y-%m-%d')
        
        # Get payment mode
        payment_method = pay_row.get('payment_method', 'Cash')
        mode_of_payment = self.PAYMENT_MODE_MAP.get(payment_method, 'Cash')
        
        # Find related invoice in ERPNext
        invoice_id = int(pay_row['etims_invoice_id'])
        invoice_number = self._invoices_cache.get(invoice_id)
        
        if not invoice_number:
            raise ValueError(f"Invoice ID {invoice_id} not found in source data")
        
        # Get invoice from ERPNext using custom field
        invoices = self.client.get_list(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "original_invoice_number": invoice_number
            },
            fields=["name", "grand_total", "outstanding_amount", "customer"],
            limit_page_length=5
        )
        
        if not invoices:
            raise ValueError(f"ERPNext invoice not found for {invoice_number}")
        
        invoice = invoices[0]  # Should only be one match
        
        # Build payment document
        doc = {
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": invoice['customer'],
            "posting_date": payment_date,
            "company": self.company,
            "mode_of_payment": mode_of_payment,
            "paid_amount": float(pay_row['amount']),
            "received_amount": float(pay_row['amount']),
            "references": [
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice['name'],
                    "allocated_amount": float(pay_row['amount'])
                }
            ]
        }
        
        # Add reference number if present
        if pd.notna(pay_row.get('reference_number')):
            doc['reference_no'] = str(pay_row['reference_number'])
            doc['reference_date'] = payment_date
        
        return doc
    
    def get_summary(self) -> str:
        """
        Get import summary report.
        
        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("PAYMENT ENTRY IMPORT SUMMARY")
        lines.append("=" * 70)
        lines.append(f"Successful: {self.results['successful']}")
        lines.append(f"Skipped:    {self.results['skipped']} (already paid)")
        lines.append(f"Failed:     {self.results['failed']}")
        
        if self.results['errors']:
            lines.append(f"\nFirst 5 errors:")
            for err in self.results['errors'][:5]:
                lines.append(f"  Transaction {err['transaction_id']}: {err['error']}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
