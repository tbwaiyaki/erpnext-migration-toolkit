"""
Egg Sales Importer - Import egg tray sales as Sales Invoices.

Simple product sales for farm egg production.
Creates Sales Invoices for each sale.

Version 1.0: Initial implementation

Architecture:
- Uses CustomerRegistry for customer management
- Egg sales → Sales Invoice
- Item: "Egg Tray" product item

Usage:
    from orchestration.customer_registry import CustomerRegistry
    
    registry = CustomerRegistry(client, "Wellness Centre")
    importer = EggSalesImporter(client, "Wellness Centre", customer_registry=registry)
    results = importer.import_batch(egg_sales_df, contacts_df)
"""

import pandas as pd
from typing import Dict, Optional
from frappeclient import FrappeClient
import time


class EggSalesImporter:
    """
    Import egg sales as Sales Invoices.
    
    Uses CustomerRegistry for professional customer management.
    """
    
    VERSION = "1.0"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        customer_registry: 'CustomerRegistry' = None
    ):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
            customer_registry: CustomerRegistry for customer management
        """
        self.client = client
        self.company = company
        
        # Use provided registry or create internal one
        if customer_registry:
            self.customer_registry = customer_registry
        else:
            from orchestration.customer_registry import CustomerRegistry
            self.customer_registry = CustomerRegistry(client, company)
        
        self.results = {
            'successful': 0,
            'skipped': 0,
            'failed': 0,
            'errors': [],
            'duration_seconds': 0.0
        }
        
        # Cache for contacts
        self._contacts_cache = {}
    
    def import_batch(
        self,
        egg_sales_df: pd.DataFrame,
        contacts_df: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Import egg sales as Sales Invoices.
        
        Args:
            egg_sales_df: Egg sales data
            contacts_df: Optional contacts for customer linking
            
        Returns:
            Results dict
        """
        start_time = time.time()
        
        print(f"[EggSalesImporter {self.VERSION}]")
        print(f"Importing {len(egg_sales_df)} egg sales...")
        print("=" * 70)
        
        # Build contacts cache
        if contacts_df is not None:
            self._build_contacts_cache(contacts_df)
        
        # Ensure egg tray item exists
        self._ensure_egg_tray_item()
        
        # Import sales
        for idx, sale in egg_sales_df.iterrows():
            try:
                # Check for duplicate
                if self._is_duplicate(sale['id']):
                    self.results['skipped'] += 1
                    if (idx + 1) % 20 == 0:
                        print(f"  ⊘ Skipped {idx + 1} duplicates...")
                    continue
                
                # Create sales invoice
                invoice = self._create_egg_sale_invoice(sale)
                
                self.results['successful'] += 1
                
                if (idx + 1) % 20 == 0:
                    print(f"  ✓ Imported {idx + 1}...")
                    
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'sale_id': sale['id'],
                    'sale_date': sale['sale_date'],
                    'error': str(e)
                })
        
        self.results['duration_seconds'] = round(time.time() - start_time, 2)
        
        print(f"  ✓ Complete: {self.results['successful']} sales imported")
        print("=" * 70)
        
        return self.results
    
    def _build_contacts_cache(self, contacts_df: pd.DataFrame):
        """Build contact lookup cache."""
        for _, contact in contacts_df.iterrows():
            self._contacts_cache[contact['id']] = contact['name']
    
    def _ensure_egg_tray_item(self):
        """Ensure 'Egg Tray' product item exists."""
        try:
            existing = self.client.get_list(
                "Item",
                filters={"item_code": "EGG-TRAY"},
                limit_page_length=1
            )
            
            if existing:
                return
            
            # Create Egg Tray product item
            item = {
                "doctype": "Item",
                "item_code": "EGG-TRAY",
                "item_name": "Egg Tray (30 eggs)",
                "item_group": "Products",
                "stock_uom": "Nos",
                "is_stock_item": 0,  # Not tracked in inventory
                "is_sales_item": 1,
                "description": "Farm fresh eggs - 30 eggs per tray"
            }
            
            self.client.insert(item)
            print("  ✓ Created product item: Egg Tray")
            
        except Exception:
            pass
    
    def _is_duplicate(self, sale_id: int) -> bool:
        """Check if sale already imported."""
        try:
            existing = self.client.get_list(
                "Sales Invoice",
                filters={"source_egg_sale_id": str(sale_id)},
                limit_page_length=1
            )
            return len(existing) > 0
        except:
            return False
    
    def _create_egg_sale_invoice(self, sale: pd.Series) -> Dict:
        """
        Create Sales Invoice for egg sale.
        
        Args:
            sale: Sale row from DataFrame
            
        Returns:
            Created invoice dict
        """
        # Get customer
        customer_name = self._get_customer_name(sale)
        
        # Build invoice
        invoice = {
            "doctype": "Sales Invoice",
            "customer": customer_name,
            "posting_date": str(sale['sale_date']),
            # Let ERPNext auto-set due_date
            "company": self.company,
            "currency": "KES",
            "source_egg_sale_id": str(sale['id']),
            "items": [
                {
                    "item_code": "EGG-TRAY",
                    "item_name": "Egg Tray (30 eggs)",
                    "description": self._build_description(sale),
                    "qty": int(sale['trays_sold']),
                    "rate": float(sale['price_per_tray']),
                    "amount": float(sale['total_amount'])
                }
            ]
        }
        
        # Create and submit invoice (all sales are completed)
        created = self.client.insert(invoice)
        created['docstatus'] = 1
        self.client.update(created)
        
        return created
    
    def _get_customer_name(self, sale: pd.Series) -> str:
        """Get or create customer for sale."""
        if pd.notna(sale.get('contact_id')):
            contact_id = int(sale['contact_id'])
            if contact_id in self._contacts_cache:
                contact_name = self._contacts_cache[contact_id]
                # Ensure customer exists (categorize as farm customers)
                return self.customer_registry.ensure_customer(
                    customer_name=contact_name,
                    customer_group="Farm Customers",
                    customer_type="Individual"
                )
        
        raise ValueError(f"No customer contact for sale {sale['id']}")
    
    def _build_description(self, sale: pd.Series) -> str:
        """Build item description."""
        lines = []
        lines.append(f"Sale Date: {sale['sale_date']}")
        lines.append(f"Trays: {sale['trays_sold']}")
        lines.append(f"Price per tray: KES {sale['price_per_tray']}")
        
        if pd.notna(sale.get('notes')):
            lines.append(f"Notes: {sale['notes']}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Get import summary."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("EGG SALES IMPORT SUMMARY")
        lines.append("=" * 70)
        
        # Customer registry stats
        registry_summary = self.customer_registry.get_summary()
        if registry_summary != "No new customers created":
            lines.append(registry_summary)
        
        lines.append(f"Total Imported:       {self.results['successful']}")
        lines.append(f"Skipped (duplicates): {self.results['skipped']}")
        
        if self.results['failed'] > 0:
            lines.append(f"Discrepancies:        {self.results['failed']} (see report)")
        else:
            lines.append(f"Discrepancies:        0")
        
        lines.append(f"Duration:             {self.results['duration_seconds']} seconds")
        
        if self.results['errors']:
            lines.append(f"\nℹ️  {len(self.results['errors'])} discrepancies found")
            lines.append(f"   Discrepancy report will be generated automatically.")
        
        lines.append("=" * 70)
        return "\n".join(lines)
