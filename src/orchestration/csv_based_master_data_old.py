"""
Master Data Creator - Updated to use actual CSV data.

Creates items, customers, and accounts based on what's actually in the CSV files.
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from frappeclient import FrappeClient


class CSVBasedMasterDataCreator:
    """
    Create master data from actual CSV files.
    
    Analyzes the CSV files to determine what Items, Customers, and Accounts
    actually need to exist in ERPNext.
    """
    
    def __init__(self, client: FrappeClient, company: str, data_dir: Path):
        """
        Initialize creator.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name in ERPNext
            data_dir: Path to CSV files
        """
        self.client = client
        self.company = company
        self.data_dir = Path(data_dir)
        self.created = {
            'customers': [],
            'items': [],
        }
        self.errors = []
    
    def get_unique_items_from_csv(self) -> list[dict]:
        """
        Extract unique items from etims_invoice_items.csv.
        
        Returns:
            List of dicts with item_code, item_name, uom
        """
        csv_path = self.data_dir / 'etims_invoice_items.csv'
        
        if not csv_path.exists():
            print(f"✗ File not found: {csv_path}")
            return []
        
        df = pd.read_csv(csv_path)
        
        # Get unique combinations
        unique_items = df[['item_description', 'unit']].drop_duplicates()
        
        items = []
        for _, row in unique_items.iterrows():
            item_desc = row['item_description']
            unit = row['unit'].capitalize() if pd.notna(row['unit']) else 'Nos'
            
            items.append({
                'item_code': item_desc,  # Use description as code
                'item_name': item_desc,
                'uom': unit
            })
        
        return items
    
    def get_unique_customers_from_csv(self) -> list[str]:
        """
        Extract unique customers from etims_invoices.csv.
        
        Returns:
            List of customer names
        """
        csv_path = self.data_dir / 'etims_invoices.csv'
        
        if not csv_path.exists():
            print(f"✗ File not found: {csv_path}")
            return []
        
        df = pd.read_csv(csv_path)
        
        # Get unique customer names (excluding null/Walk-in)
        customers = df['customer_name'].dropna().unique()
        customers = [c for c in customers if c not in ['Walk-in Customer', '']]
        
        return sorted(customers)
    
    def create_item(self, item_code: str, item_name: str, uom: str = "Nos") -> bool:
        """
        Create item in ERPNext.
        
        Returns:
            True if created or already exists
        """
        try:
            # Check if exists
            existing = self.client.get_list(
                "Item",
                filters={"item_code": item_code},
                limit_page_length=1
            )
            
            if existing:
                return True
            
            # Create
            self.client.insert({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_name,
                "item_group": "Services",
                "stock_uom": uom,
                "is_stock_item": 0,
            })
            
            self.created['items'].append(item_code)
            return True
            
        except Exception as e:
            self.errors.append({
                'type': 'item',
                'name': item_code,
                'error': str(e)
            })
            return False
    
    def create_customer(self, customer_name: str) -> bool:
        """Create customer in ERPNext"""
        try:
            # Check if exists
            existing = self.client.get_list(
                "Customer",
                filters={"customer_name": customer_name},
                limit_page_length=1
            )
            
            if existing:
                return True
            
            # Create
            self.client.insert({
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": "Kenya",
            })
            
            self.created['customers'].append(customer_name)
            return True
            
        except Exception as e:
            self.errors.append({
                'type': 'customer',
                'name': customer_name,
                'error': str(e)
            })
            return False
    
    def create_all_from_csv(self) -> dict:
        """
        Create all master data from CSV files.
        
        Returns:
            Summary of what was created
        """
        print("="*70)
        print("CREATING MASTER DATA FROM CSV FILES")
        print("="*70)
        
        # Get items from CSV
        print("\n1. Analyzing items from etims_invoice_items.csv...")
        items_to_create = self.get_unique_items_from_csv()
        print(f"   Found {len(items_to_create)} unique items")
        
        # Create items
        print("\n2. Creating items in ERPNext...")
        items_created = 0
        for item in items_to_create:
            if self.create_item(item['item_code'], item['item_name'], item['uom']):
                items_created += 1
                print(f"   ✓ {item['item_code']}")
        
        # Get customers from CSV
        print("\n3. Analyzing customers from etims_invoices.csv...")
        customers_to_create = self.get_unique_customers_from_csv()
        print(f"   Found {len(customers_to_create)} unique customers")
        
        # Create customers
        print("\n4. Creating customers in ERPNext...")
        customers_created = 0
        for customer in customers_to_create:
            if self.create_customer(customer):
                customers_created += 1
                if customers_created <= 10:  # Show first 10
                    print(f"   ✓ {customer}")
        
        if customers_created > 10:
            print(f"   ... and {customers_created - 10} more")
        
        print()
        print("="*70)
        print("MASTER DATA CREATION COMPLETE")
        print("="*70)
        print(f"Items:     {items_created}/{len(items_to_create)}")
        print(f"Customers: {customers_created}/{len(customers_to_create)}")
        
        if self.errors:
            print(f"\nErrors: {len(self.errors)}")
            for error in self.errors[:5]:
                print(f"  {error['type']}: {error['name']} - {error['error'][:100]}")
        
        print("="*70)
        
        return {
            'items': {
                'total': len(items_to_create),
                'created': items_created
            },
            'customers': {
                'total': len(customers_to_create),
                'created': customers_created
            },
            'errors': self.errors
        }
