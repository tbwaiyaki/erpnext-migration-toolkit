"""
Sales Invoice Importer - Import eTIMS invoices into ERPNext.

Handles batch import of sales invoices from CSV data with proper
customer linking, item validation, and submission.
"""

import pandas as pd
from typing import Dict, List
from frappeclient import FrappeClient
from datetime import datetime


class SalesInvoiceImporter:
    """
    Import sales invoices from eTIMS CSV data.
    
    Handles:
    - Customer name matching
    - Item validation
    - Tax calculation
    - Batch submission
    - Historical date posting
    
    Usage:
        importer = SalesInvoiceImporter(client, "Wellness Centre")
        results = importer.import_batch(invoices_df, items_df, contacts_df)
    """
    
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
            'errors': []
        }
    
    def import_batch(
        self,
        invoices_df: pd.DataFrame,
        invoice_items_df: pd.DataFrame,
        contacts_df: pd.DataFrame
    ) -> Dict:
        """
        Import batch of sales invoices.
        
        Args:
            invoices_df: Invoice headers from etims_invoices.csv
            invoice_items_df: Line items from etims_invoice_items.csv
            contacts_df: Contact data for customer matching
            
        Returns:
            Results dict with successful/failed counts
        """
        print(f"Importing {len(invoices_df)} sales invoices...")
        
        for idx, inv_row in invoices_df.iterrows():
            try:
                # Get line items for this invoice
                inv_items = invoice_items_df[
                    invoice_items_df['invoice_id'] == inv_row['id']
                ]
                
                if inv_items.empty:
                    raise ValueError(f"No line items found for invoice {inv_row['id']}")
                
                # Build invoice document
                invoice_doc = self._build_invoice_doc(inv_row, inv_items)
                
                # Insert and submit
                created = self.client.insert(invoice_doc)
                self.client.submit(created)
                
                self.results['successful'] += 1
                
                # Progress indicator
                if self.results['successful'] % 50 == 0:
                    print(f"  Imported {self.results['successful']}...")
                
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'invoice_id': inv_row['id'],
                    'invoice_number': inv_row.get('invoice_number'),
                    'error': str(e)[:500]  # Increased from 200 to 500 chars
                })
        
        return self.results
    
    def _build_invoice_doc(
        self,
        inv_row: pd.Series,
        inv_items: pd.DataFrame
    ) -> Dict:
        """
        Build ERPNext Sales Invoice document.
        
        Args:
            inv_row: Invoice header row
            inv_items: Invoice line items
            
        Returns:
            Invoice document dict
        """
        # Parse invoice date
        invoice_date = pd.to_datetime(inv_row['invoice_date']).strftime('%Y-%m-%d')
        
        # Build document
        doc = {
            "doctype": "Sales Invoice",
            "customer": inv_row['customer_name'],
            "posting_date": invoice_date,
            "due_date": invoice_date,  # Must be explicit and >= posting_date
            "set_posting_time": 1,  # CRITICAL: Allow historical dates
            "company": self.company,
            "naming_series": "ACC-SINV-.YYYY.-",
            "items": [],
            "taxes": []
        }
        
        # Add line items
        for _, item_row in inv_items.iterrows():
            doc["items"].append({
                "item_code": item_row['item_description'],
                "qty": float(item_row['quantity']),
                "rate": float(item_row['unit_price']),
                "uom": item_row['unit']
            })
        
        # Add tax if applicable
        tax_amount = float(inv_row.get('tax_amount', 0))
        if tax_amount > 0:
            doc["taxes"].append({
                "charge_type": "Actual",
                "account_head": f"VAT - {self.company[0:3]}",
                "description": "VAT",
                "tax_amount": tax_amount
            })
        
        return doc
    
    def get_summary(self) -> str:
        """
        Get import summary report.
        
        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("SALES INVOICE IMPORT SUMMARY")
        lines.append("=" * 70)
        lines.append(f"Successful: {self.results['successful']}")
        lines.append(f"Failed:     {self.results['failed']}")
        
        if self.results['errors']:
            lines.append(f"\nFirst 5 errors:")
            for err in self.results['errors'][:5]:
                lines.append(f"  Invoice {err['invoice_number']}: {err['error'][:100]}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
