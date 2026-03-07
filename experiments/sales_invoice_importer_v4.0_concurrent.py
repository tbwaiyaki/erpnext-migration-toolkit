"""
Sales Invoice Importer v4.0 - Concurrent import with threading.

Handles batch import of sales invoices using concurrent workers
for dramatically improved performance.
"""

import pandas as pd
from typing import Dict, List
from frappeclient import FrappeClient
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time


class SalesInvoiceImporter:
    """
    Import sales invoices with concurrent processing.
    
    Features:
    - Multi-threaded concurrent imports (5x speedup)
    - Thread-safe duplicate prevention
    - Each thread has own FrappeClient instance
    - Progress tracking with thread safety
    
    Usage:
        importer = SalesInvoiceImporter(
            client, 
            "Wellness Centre", 
            max_workers=5,
            api_key=API_KEY,
            api_secret=API_SECRET
        )
        results = importer.import_batch(invoices_df, items_df)
    """
    
    VERSION = "4.0-concurrent"  # Version marker
    
    def __init__(
        self, 
        client: FrappeClient, 
        company: str, 
        max_workers: int = 5,
        api_key: str = None,
        api_secret: str = None,
        host_header: str = None
    ):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient (for main operations)
            company: Company name
            max_workers: Number of concurrent threads (default 5)
            api_key: API key for thread-local clients (required for concurrency)
            api_secret: API secret for thread-local clients (required for concurrency)
            host_header: Host header value for internal Docker URLs (e.g., 'well.rosslyn.cloud')
        """
        self.company = company
        self.max_workers = max_workers
        
        # Store credentials for thread-safe client creation
        if api_key and api_secret:
            self.client_config = {
                'url': client.url,
                'api_key': api_key,
                'api_secret': api_secret,
                'host_header': host_header  # Store Host header
            }
        else:
            # No credentials provided - fall back to sequential with main client
            print(f"  Warning: No API credentials provided for threading")
            print(f"  Falling back to sequential processing...")
            self.max_workers = 1
            self.client_config = None
        
        # Thread-safe results tracking
        self.results = {
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'start_time': None,
            'end_time': None,
            'duration_seconds': 0
        }
        self.results_lock = threading.Lock()
        
        # Main client for batch operations
        self.main_client = client
    
    def import_batch(
        self,
        invoices_df: pd.DataFrame,
        invoice_items_df: pd.DataFrame
    ) -> Dict:
        """
        Import batch of sales invoices concurrently.
        
        Args:
            invoices_df: Invoice headers from etims_invoices.csv
            invoice_items_df: Line items from etims_invoice_items.csv
            
        Returns:
            Results dict with successful/failed counts
        """
        print(f"[SalesInvoiceImporter {self.VERSION}]")
        print(f"Importing {len(invoices_df)} sales invoices with {self.max_workers} workers...")
        
        # Start timer
        self.results['start_time'] = time.time()
        
        # Batch duplicate check (load all existing at once)
        print("  Loading existing invoices for duplicate check...")
        existing_numbers = self._load_existing_invoices()
        print(f"  Found {len(existing_numbers)} existing invoices")
        
        # Prepare invoice data with items
        invoice_data_list = []
        for idx, inv_row in invoices_df.iterrows():
            # Skip duplicates
            if inv_row['invoice_number'] in existing_numbers:
                with self.results_lock:
                    self.results['skipped'] += 1
                continue
            
            # Get items for this invoice
            inv_items = invoice_items_df[
                invoice_items_df['invoice_id'] == inv_row['id']
            ]
            
            if inv_items.empty:
                with self.results_lock:
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'invoice_id': inv_row['id'],
                        'invoice_number': inv_row.get('invoice_number'),
                        'error': 'No line items found'
                    })
                continue
            
            invoice_data_list.append({
                'header': inv_row,
                'items': inv_items
            })
        
        print(f"  Processing {len(invoice_data_list)} new invoices...")
        
        # Import concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all invoices
            futures = {
                executor.submit(self._import_single_invoice, invoice_data): idx
                for idx, invoice_data in enumerate(invoice_data_list)
            }
            
            # Process results as they complete
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    future.result()  # Raises exception if import failed
                except Exception as e:
                    # Error already logged in _import_single_invoice
                    pass
                
                # Progress indicator (every 50)
                if completed % 50 == 0:
                    with self.results_lock:
                        print(f"  Completed {completed}/{len(invoice_data_list)}... "
                              f"(✓ {self.results['successful']} | ✗ {self.results['failed']})")
        
        # End timer and calculate duration
        self.results['end_time'] = time.time()
        self.results['duration_seconds'] = self.results['end_time'] - self.results['start_time']
        
        return self.results
    
    def _load_existing_invoices(self) -> set:
        """
        Load all existing invoice numbers for batch duplicate check.
        
        Returns:
            Set of existing original_invoice_numbers
        """
        try:
            existing = self.main_client.get_list(
                "Sales Invoice",
                filters={},
                fields=["original_invoice_number"],
                limit_page_length=999
            )
            
            return {
                inv['original_invoice_number'] 
                for inv in existing 
                if inv.get('original_invoice_number')
            }
        except Exception as e:
            print(f"  Warning: Could not load existing invoices: {str(e)[:100]}")
            return set()
    
    def _import_single_invoice(self, invoice_data: Dict) -> str:
        """
        Import a single invoice (thread-safe).
        
        Args:
            invoice_data: Dict with 'header' and 'items'
            
        Returns:
            Created invoice name
        """
        inv_row = invoice_data['header']
        inv_items = invoice_data['items']
        
        try:
            # Create thread-local client if credentials available
            if self.client_config:
                thread_client = FrappeClient(self.client_config['url'])
                thread_client.authenticate(
                    self.client_config['api_key'],
                    self.client_config['api_secret']
                )
                
                # Add Host header if configured (for Docker internal URLs)
                if self.client_config.get('host_header'):
                    thread_client.session.headers.update({
                        "Host": self.client_config['host_header']
                    })
            else:
                # Use main client (sequential mode)
                thread_client = self.main_client
            
            # Build invoice document
            invoice_doc = self._build_invoice_doc(inv_row, inv_items)
            
            # Insert
            created = thread_client.insert(invoice_doc)
            
            # Submit by updating docstatus
            created['docstatus'] = 1
            thread_client.update(created)
            
            # Update results (thread-safe)
            with self.results_lock:
                self.results['successful'] += 1
            
            return created['name']
            
        except Exception as e:
            # Log error (thread-safe)
            with self.results_lock:
                self.results['failed'] += 1
                error_msg = str(e)
                # Clean HTML errors
                if error_msg.startswith('<!DOCTYPE html>') or '<html' in error_msg[:100]:
                    error_msg = "Server returned HTML error - likely validation failure"
                
                self.results['errors'].append({
                    'invoice_id': inv_row['id'],
                    'invoice_number': inv_row.get('invoice_number'),
                    'error': error_msg[:500]
                })
            raise
    
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
            "due_date": invoice_date,
            "set_posting_time": 1,
            "company": self.company,
            "original_invoice_number": inv_row['invoice_number'],  # For duplicate prevention
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
        lines.append(f"Skipped:    {self.results['skipped']} (already exist)")
        lines.append(f"Failed:     {self.results['failed']}")
        
        # Add timing information
        if self.results['duration_seconds'] > 0:
            duration = self.results['duration_seconds']
            lines.append(f"\nPerformance:")
            lines.append(f"  Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
            
            total_processed = self.results['successful'] + self.results['failed']
            if total_processed > 0:
                rate = total_processed / duration
                lines.append(f"  Rate: {rate:.1f} invoices/second")
                lines.append(f"  Workers: {self.max_workers}")
        
        if self.results['errors']:
            lines.append(f"\nFirst 5 errors:")
            for err in self.results['errors'][:5]:
                lines.append(f"  Invoice {err['invoice_number']}: {err['error'][:100]}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
