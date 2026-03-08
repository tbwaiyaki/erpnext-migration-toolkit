"""
Payment Entry Importer - Import invoice payments into ERPNext.

Handles batch import of payment entries linked to sales invoices,
with dynamic account discovery via AccountRegistry.

Version 3.2: AccountRegistry integration (eliminates hard-coding)
- Uses AccountRegistry for dynamic payment account discovery
- Works with ANY country's account naming convention
- All mandatory fields included (exchange rates, paid_to, currencies)
- Timing metrics added
"""

import pandas as pd
from typing import Dict
from frappeclient import FrappeClient
import time


class PaymentEntryImporter:
    """
    Import payment entries for sales invoices.
    
    Links payments to invoices based on etims_invoice_id,
    uses AccountRegistry for dynamic account discovery.
    
    Usage:
        registry = AccountRegistry(client, "Wellness Centre")
        importer = PaymentEntryImporter(client, "Wellness Centre", registry)
        results = importer.import_batch(transactions_df, invoices_df)
    """
    
    VERSION = "3.2-accountregistry"  # Version marker
    
    def __init__(self, client: FrappeClient, company: str, registry):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
            registry: AccountRegistry instance for dynamic account lookup
        """
        self.client = client
        self.company = company
        self.registry = registry
        self.results = {
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'duration_seconds': 0.0,
            'rate_per_second': 0.0
        }
        
        # Cache invoices
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
            Results dict with successful/failed counts and timing
        """
        # Filter for payment transactions
        payments = transactions_df[
            transactions_df['etims_invoice_id'].notna()
        ].copy()
        
        print(f"[PaymentEntryImporter {self.VERSION}]")
        print(f"Importing {len(payments)} payment entries...")
        
        # Start timing
        start_time = time.time()
        
        # Build invoice lookup
        self._build_invoice_cache(invoices_df)
        
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
                payment_doc = self._build_payment_doc(pay_row, invoice)
                
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
                    'error': str(e)[:500]  # Increased from 200 for better debugging
                })
        
        # Calculate timing metrics
        duration = time.time() - start_time
        self.results['duration_seconds'] = round(duration, 2)
        
        # Calculate rate (successful imports per second)
        if duration > 0 and self.results['successful'] > 0:
            self.results['rate_per_second'] = round(self.results['successful'] / duration, 2)
        
        return self.results
    
    def _build_invoice_cache(self, invoices_df: pd.DataFrame):
        """Build lookup dict: invoice_id -> invoice_number mapping."""
        for _, inv in invoices_df.iterrows():
            self._invoices_cache[inv['id']] = inv['invoice_number']
    
    def _build_payment_doc(self, pay_row: pd.Series, invoice: Dict) -> Dict:
        """
        Build ERPNext Payment Entry document with all mandatory fields.
        
        Args:
            pay_row: Payment transaction row
            invoice: ERPNext invoice dict (from get_list)
            
        Returns:
            Payment Entry document dict
        """
        # Parse payment date
        payment_date = pd.to_datetime(pay_row['transaction_date']).strftime('%Y-%m-%d')
        
        # Get payment method
        payment_method = pay_row.get('payment_method', 'Cash')
        
        # Get account dynamically via AccountRegistry
        try:
            paid_to_account = self.registry.get_payment_account(payment_method)
        except ValueError as e:
            # Fallback to Cash if payment method not found
            print(f"⚠ Payment method '{payment_method}' not found, using Cash: {e}")
            paid_to_account = self.registry.get_payment_account('Cash')
        
        # Get customer from invoice
        invoice_full = self.client.get_doc("Sales Invoice", invoice['name'])
        
        # Build payment document with ALL mandatory fields
        doc = {
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": invoice_full['customer'],
            "posting_date": payment_date,
            "company": self.company,
            "mode_of_payment": payment_method,
            
            # CRITICAL: Account fields (mandatory)
            "paid_to": paid_to_account,
            "paid_to_account_currency": "KES",
            
            # Amounts
            "paid_amount": float(pay_row['amount']),
            "received_amount": float(pay_row['amount']),
            
            # CRITICAL: Exchange rates (mandatory even for single currency)
            "source_exchange_rate": 1.0,
            "target_exchange_rate": 1.0,
            
            # Invoice reference
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
        
        # Add performance metrics
        lines.append(f"\nPerformance:")
        duration = self.results['duration_seconds']
        minutes = duration / 60
        lines.append(f"  Duration: {duration} seconds ({minutes:.2f} minutes)")
        lines.append(f"  Rate: {self.results['rate_per_second']} payments/second")
        
        if self.results['errors']:
            lines.append(f"\nFirst 5 errors:")
            for err in self.results['errors'][:5]:
                lines.append(f"  Transaction {err['transaction_id']}: {err['error'][:100]}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
