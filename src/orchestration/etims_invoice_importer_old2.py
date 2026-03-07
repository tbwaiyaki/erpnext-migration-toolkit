"""
eTIMS Invoice Importer for ERPNext.

Imports actual eTIMS invoices directly from CSV files.
"""

import pandas as pd
from pathlib import Path
from datetime import date
from typing import Optional

from frappeclient import FrappeClient
from orchestration.erpnext_submitter import ERPNextSubmitter, ImportResult


class EtimsInvoiceImporter:
    """
    Import eTIMS invoices from CSV to ERPNext.
    
    Reads etims_invoices.csv and etims_invoice_items.csv and creates
    Sales Invoices in ERPNext with the exact data from eTIMS system.
    
    Examples:
        >>> importer = EtimsInvoiceImporter(client, Path('/mnt/project'))
        >>> result = importer.import_all()
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            data_dir: Path to CSV files
        """
        self.client = client
        self.data_dir = Path(data_dir)
        self.submitter = ERPNextSubmitter(client)
    
    def load_invoices(self) -> pd.DataFrame:
        """Load eTIMS invoices CSV"""
        csv_path = self.data_dir / 'etims_invoices.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"eTIMS invoices not found: {csv_path}")
        
        return pd.read_csv(csv_path)
    
    def load_invoice_items(self) -> pd.DataFrame:
        """Load eTIMS invoice items CSV"""
        csv_path = self.data_dir / 'etims_invoice_items.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"eTIMS invoice items not found: {csv_path}")
        
        return pd.read_csv(csv_path)
    
    def build_erpnext_invoice(self, invoice_row: dict, items_df: pd.DataFrame) -> dict:
        """
        Build ERPNext Sales Invoice payload from eTIMS data.
        
        Args:
            invoice_row: Row from etims_invoices.csv
            items_df: Full etims_invoice_items.csv dataframe
            
        Returns:
            ERPNext Sales Invoice dict
        """
        invoice_id = invoice_row['id']
        customer_name = invoice_row['customer_name']
        
        # Get customer's ERPNext ID (name field)
        # ERPNext uses 'name' as internal ID, 'customer_name' as display name
        try:
            customer_list = self.client.get_list(
                "Customer",
                filters={"customer_name": customer_name},
                fields=["name"],
                limit_page_length=1
            )
            
            if customer_list:
                customer_id = customer_list[0]['name']
            else:
                # Fall back to customer_name if not found
                customer_id = customer_name
        except:
            customer_id = customer_name
        
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
                "uom": item_row['unit'].capitalize() if pd.notna(item_row['unit']) else 'Nos'
            })
        
        # Build taxes (if any)
        taxes = []
        total_tax = sum(item_row['tax_amount'] for _, item_row in invoice_items.iterrows() 
                       if pd.notna(item_row['tax_amount']) and item_row['tax_amount'] > 0)
        
        if total_tax > 0:
            # Assume 16% VAT (from tax_rate column)
            taxes.append({
                "charge_type": "On Net Total",
                "account_head": "VAT - WC",
                "description": "VAT @ 16%",
                "rate": 16.0,
                "tax_amount": float(total_tax)
            })
        
        # Build invoice
        payload = {
            "doctype": "Sales Invoice",
            "customer": customer_id,  # Use ERPNext internal ID
            "customer_name": customer_name,  # Display name
            "posting_date": invoice_row['invoice_date'],
            "due_date": invoice_row['invoice_date'],  # Same day for eTIMS
            "items": items,
        }
        
        if taxes:
            payload["taxes"] = taxes
        
        # Add eTIMS-specific fields
        if pd.notna(invoice_row.get('notes')):
            payload["remarks"] = invoice_row['notes']
        
        # Store eTIMS invoice number in remarks
        etims_ref = f"eTIMS Invoice: {invoice_row['invoice_number']}"
        if payload.get("remarks"):
            payload["remarks"] = f"{etims_ref}\n{payload['remarks']}"
        else:
            payload["remarks"] = etims_ref
        
        return payload
    
    def import_all(
        self,
        check_duplicates: bool = True,
        auto_submit: bool = False,
        limit: Optional[int] = None
    ) -> ImportResult:
        """
        Import all eTIMS invoices to ERPNext.
        
        Args:
            check_duplicates: Skip existing invoices
            auto_submit: Submit invoices after creation
            limit: Optional limit for testing
            
        Returns:
            ImportResult with statistics
        """
        print("Loading eTIMS data from CSV...")
        invoices_df = self.load_invoices()
        items_df = self.load_invoice_items()
        
        if limit:
            invoices_df = invoices_df.head(limit)
        
        print(f"Found {len(invoices_df)} invoices to import")
        print()
        
        result = ImportResult("Sales Invoice (eTIMS)")
        result.total = len(invoices_df)
        
        for i, (_, invoice_row) in enumerate(invoices_df.iterrows(), 1):
            try:
                # Build ERPNext payload
                payload = self.build_erpnext_invoice(invoice_row, items_df)
                
                # Check duplicates if requested
                if check_duplicates:
                    filters = {
                        "customer": payload['customer'],
                        "posting_date": payload['posting_date']
                    }
                    
                    existing = self.client.get_list(
                        "Sales Invoice",
                        filters=filters,
                        fields=["name"],
                        limit_page_length=1
                    )
                    
                    if existing:
                        result.skipped += 1
                        result.skips.append({
                            'record_id': payload['customer'],
                            'reason': f"Already exists: {existing[0]['name']}"
                        })
                        continue
                
                # Insert invoice
                doc = self.client.insert(payload)
                erpnext_name = doc.get('name')
                
                # Auto-submit if requested
                if auto_submit:
                    self.client.update({
                        "doctype": "Sales Invoice",
                        "name": erpnext_name,
                        "docstatus": 1
                    })
                
                result.succeeded += 1
                result.successes.append({
                    'record_id': payload['customer'],
                    'erpnext_name': erpnext_name,
                    'etims_number': invoice_row['invoice_number']
                })
                
            except Exception as e:
                result.failed += 1
                result.failures.append({
                    'record_id': invoice_row.get('customer_name', 'Unknown'),
                    'error': str(e)[:200]
                })
            
            # Progress
            if i % 10 == 0 or i == len(invoices_df):
                print(f"  Progress: {i}/{len(invoices_df)} "
                      f"(✓ {result.succeeded}, ⊘ {result.skipped}, ✗ {result.failed})")
        
        result.finish()
        return result
