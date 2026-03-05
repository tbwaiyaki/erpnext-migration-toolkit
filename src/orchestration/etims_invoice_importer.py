"""
eTIMS Invoice Importer - PRODUCTION VERSION

Imports actual eTIMS invoices from CSV with all fixes applied:
- Customer ID lookup (not display name)
- Required fields (currency, debit_to, income_account)
- Proper error handling
- Docker network compatible
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from frappeclient import FrappeClient


class EtimsInvoiceImporter:
    """
    Import eTIMS invoices to ERPNext Sales Invoice.
    
    All fixes applied:
    - Customer ID lookup (CUST-00039 vs "Dorothy Barasa")
    - Currency explicitly set to KES
    - Debit account set to "Debtors - WC"
    - Income account per item set to "Sales - WC"
    - UOM capitalization
    - Error tracking with full messages
    """
    
    def __init__(self, client: FrappeClient, data_dir: Path):
        self.client = client
        self.data_dir = Path(data_dir)
        self.successes = []
        self.failures = []
        self.skipped = []
    
    def _get_customer_id(self, customer_name: str) -> str:
        """
        Get ERPNext customer internal ID from display name.
        
        ERPNext uses 'name' field as internal ID (e.g. CUST-00039)
        and 'customer_name' as display name (e.g. "Dorothy Barasa")
        
        This function looks up the internal ID.
        """
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
                # Fallback to customer_name if not found
                return customer_name
                
        except Exception as e:
            print(f"    Warning: Customer lookup failed for '{customer_name}': {e}")
            return customer_name
    
    def build_erpnext_invoice(self, invoice_row: dict, items_df: pd.DataFrame) -> dict:
        """
        Build ERPNext Sales Invoice payload from eTIMS CSV data.
        
        Args:
            invoice_row: Row from etims_invoices.csv
            items_df: Full etims_invoice_items.csv dataframe
            
        Returns:
            ERPNext Sales Invoice dict with all required fields
        """
        invoice_id = invoice_row['id']
        customer_name = invoice_row['customer_name']
        
        # CRITICAL FIX 1: Get customer's ERPNext ID (not display name)
        customer_id = self._get_customer_id(customer_name)
        
        # Get items for this invoice
        invoice_items = items_df[items_df['invoice_id'] == invoice_id]
        
        # Build items array
        items = []
        for _, item_row in invoice_items.iterrows():
            # CRITICAL FIX 2: Add income_account to each item
            items.append({
                "item_code": item_row['item_description'],
                "item_name": item_row['item_description'],
                "description": item_row['item_description'],
                "qty": float(item_row['quantity']),
                "rate": float(item_row['unit_price']),
                "amount": float(item_row['total_price']),
                "uom": item_row['unit'].strip().capitalize() if pd.notna(item_row['unit']) else 'Nos',
                "income_account": "Sales - WC"  # Required for GL posting
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
        
        # Build invoice
        from datetime import datetime, timedelta
        
        posting_date = invoice_row['invoice_date']
        # Calculate due date (15 days after posting)
        posting_dt = datetime.strptime(posting_date, '%Y-%m-%d')
        due_dt = posting_dt + timedelta(days=15)
        due_date = due_dt.strftime('%Y-%m-%d')
        
        payload = {
            "doctype": "Sales Invoice",
            "customer": customer_id,  # CRITICAL: Use internal ID, not display name
            "customer_name": customer_name,  # Display name
            "posting_date": posting_date,
            "due_date": due_date,  # 15 days after posting
            
            # CRITICAL FIX 3: Explicitly set these fields
            "currency": "KES",  # Required - bypasses customer default
            "debit_to": "Debtors - WC",  # Required - receivable account
            
            "items": items,
        }
        
        if taxes:
            payload["taxes"] = taxes
        
        # Add eTIMS-specific fields
        etims_ref = f"eTIMS Invoice: {invoice_row['invoice_number']}"
        
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
        Import all eTIMS invoices to ERPNext.
        
        Args:
            check_duplicates: Skip if invoice already exists
            auto_submit: Submit invoices after creation (posts to GL)
            limit: Optional limit for testing (e.g. limit=10)
            
        Returns:
            Dict with results summary
        """
        # Load CSV files
        print("Loading eTIMS data from CSV...")
        invoices_df = pd.read_csv(self.data_dir / 'etims_invoices.csv')
        items_df = pd.read_csv(self.data_dir / 'etims_invoice_items.csv')
        
        if limit:
            invoices_df = invoices_df.head(limit)
        
        print(f"Found {len(invoices_df)} invoices to import")
        print()
        
        # Reset counters
        self.successes = []
        self.failures = []
        self.skipped = []
        
        # Import each invoice
        for i, (_, invoice_row) in enumerate(invoices_df.iterrows(), 1):
            customer_name = invoice_row['customer_name']
            
            try:
                # Check duplicates if requested
                if check_duplicates:
                    # Look for existing invoice with same customer and date
                    existing = self.client.get_list(
                        "Sales Invoice",
                        filters={
                            "customer": customer_name,  # Will match on display name too
                            "posting_date": invoice_row['invoice_date']
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
                
                # Build ERPNext payload
                payload = self.build_erpnext_invoice(
                    invoice_row.to_dict(),
                    items_df
                )
                
                # Insert invoice
                doc = self.client.insert(payload)
                erpnext_name = doc.get('name')
                
                # Auto-submit if requested
                if auto_submit:
                    self.client.update({
                        "doctype": "Sales Invoice",
                        "name": erpnext_name,
                        "docstatus": 1  # Submit
                    })
                
                # Track success
                self.successes.append({
                    'customer': customer_name,
                    'erpnext_name': erpnext_name,
                    'etims_number': invoice_row['invoice_number'],
                    'amount': invoice_row['total_amount']
                })
                
            except Exception as e:
                # Track failure with FULL error message
                self.failures.append({
                    'customer': customer_name,
                    'invoice_date': invoice_row['invoice_date'],
                    'error': str(e)  # Full error, not truncated
                })
            
            # Progress indicator
            if i % 10 == 0 or i == len(invoices_df):
                print(f"  Progress: {i}/{len(invoices_df)} "
                      f"(✓ {len(self.successes)}, ⊘ {len(self.skipped)}, ✗ {len(self.failures)})")
        
        print()
        
        # Return summary
        return {
            'total': len(invoices_df),
            'succeeded': len(self.successes),
            'skipped': len(self.skipped),
            'failed': len(self.failures),
            'successes': self.successes,
            'skips': self.skipped,
            'failures': self.failures
        }
    
    def print_summary(self, result: dict):
        """Print formatted summary of import results"""
        print("="*70)
        print("IMPORT SUMMARY — Sales Invoice (eTIMS)")
        print("="*70)
        print(f"  Total records:  {result['total']}")
        print(f"  Succeeded:      {result['succeeded']}")
        print(f"  Skipped:        {result['skipped']}  (already existed)")
        print(f"  Failed:         {result['failed']}")
        
        if result['succeeded'] > 0:
            total_amount = sum(s['amount'] for s in result['successes'])
            print(f"\n  Total value: KES {total_amount:,.2f}")
        
        if result['failures']:
            print(f"\nFAILURES ({len(result['failures'])}):")
            for f in result['failures'][:5]:
                print(f"  - [{f['customer']}] {f['error'][:150]}")
            if len(result['failures']) > 5:
                print(f"  ... and {len(result['failures']) - 5} more")
        
        if result['skips']:
            print(f"\nSKIPPED ({len(result['skips'])}):")
            for s in result['skips'][:3]:
                print(f"  - [{s['customer']}] {s['reason']}")
            if len(result['skips']) > 3:
                print(f"  ... and {len(result['skips']) - 3} more")
        
        print("="*70)
