"""
Master Data Creator - Auto-creates all required master data.

Creates from CSV source files:
- UOMs (from invoice items)
- Customers (from contacts)
- Suppliers (from contacts)
- Service Items (from invoice line items)

Usage:
    creator = MasterDataCreator(client, company="Wellness Centre")
    results = creator.create_all(
        contacts_df=contacts_df,
        invoice_items_df=items_df
    )
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from frappeclient import FrappeClient


class MasterDataCreator:
    """
    Auto-creates master data from CSV source files.
    
    Handles:
    - UOMs extraction and creation
    - Customers from contacts
    - Suppliers from contacts
    - Service items from invoice items
    """
    
    def __init__(self, client: FrappeClient, company: str):
        """
        Initialize creator.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
        """
        self.client = client
        self.company = company
        self.results = {
            'uoms': {'created': [], 'existed': [], 'errors': []},
            'customers': {'created': [], 'existed': [], 'errors': []},
            'suppliers': {'created': [], 'existed': [], 'errors': []},
            'items': {'created': [], 'existed': [], 'errors': []}
        }
    
    def _record_exists(self, doctype: str, name: str) -> bool:
        """Check if a record exists."""
        try:
            results = self.client.get_list(
                doctype,
                filters={"name": name},
                limit_page_length=1
            )
            return len(results) > 0
        except:
            return False
    
    def create_uoms_from_items(self, invoice_items_df: pd.DataFrame):
        """
        Extract and create UOMs from invoice items.
        
        Args:
            invoice_items_df: DataFrame with 'unit' column
        """
        # Extract unique UOMs
        unique_uoms = invoice_items_df['unit'].dropna().unique()
        
        # Standardize (capitalize first letter)
        unique_uoms = [uom.strip().capitalize() for uom in unique_uoms if uom.strip()]
        unique_uoms = list(set(unique_uoms))  # Remove duplicates
        
        for uom_name in unique_uoms:
            try:
                if self._record_exists("UOM", uom_name):
                    self.results['uoms']['existed'].append(uom_name)
                    continue
                
                # Create UOM
                payload = {
                    "doctype": "UOM",
                    "uom_name": uom_name,
                    "enabled": 1
                }
                
                self.client.insert(payload)
                self.results['uoms']['created'].append(uom_name)
                
            except Exception as e:
                self.results['uoms']['errors'].append({
                    'uom': uom_name,
                    'error': str(e)[:150]
                })
    
    def create_customers_from_contacts(
        self,
        contacts_df: pd.DataFrame,
        invoices_df: pd.DataFrame
    ):
        """
        Create customers from contacts who appear in invoices.
        
        Args:
            contacts_df: Contacts master data
            invoices_df: Invoices with customer_name column
        """
        # Get unique customer names from invoices
        unique_customers = invoices_df['customer_name'].dropna().unique()
        
        for customer_name in unique_customers:
            try:
                # Check if already exists
                existing = self.client.get_list(
                    "Customer",
                    filters={"customer_name": customer_name},
                    limit_page_length=1
                )
                
                if existing:
                    self.results['customers']['existed'].append(customer_name)
                    continue
                
                # Get contact details if available
                contact_match = contacts_df[contacts_df['name'] == customer_name]
                
                phone = None
                email = None
                if len(contact_match) > 0:
                    contact_row = contact_match.iloc[0]
                    phone = contact_row.get('phone')
                    email = contact_row.get('email')
                
                # Create customer
                payload = {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "customer_type": "Individual",
                    "customer_group": "Individual",
                    "territory": "Kenya",
                    "default_currency": "KES"
                }
                
                if phone and pd.notna(phone):
                    payload["mobile_no"] = str(int(phone))
                if email and pd.notna(email):
                    payload["email_id"] = email
                
                self.client.insert(payload)
                self.results['customers']['created'].append(customer_name)
                
            except Exception as e:
                self.results['customers']['errors'].append({
                    'customer': customer_name,
                    'error': str(e)[:150]
                })
    
    def create_suppliers_from_contacts(
        self,
        contacts_df: pd.DataFrame,
        contact_types_df: pd.DataFrame
    ):
        """
        Create suppliers from contacts with supplier types.
        
        Args:
            contacts_df: Contacts with contact_type_id
            contact_types_df: Contact types lookup
        """
        # Find supplier type ID
        supplier_types = contact_types_df[
            contact_types_df['name'].str.contains('Supplier', case=False, na=False)
        ]
        
        if len(supplier_types) == 0:
            # No explicit supplier type - skip
            return
        
        supplier_type_ids = supplier_types['id'].tolist()
        
        # Filter contacts
        suppliers = contacts_df[contacts_df['contact_type_id'].isin(supplier_type_ids)]
        
        for _, supplier_row in suppliers.iterrows():
            supplier_name = supplier_row['name']
            
            try:
                # Check if already exists
                existing = self.client.get_list(
                    "Supplier",
                    filters={"supplier_name": supplier_name},
                    limit_page_length=1
                )
                
                if existing:
                    self.results['suppliers']['existed'].append(supplier_name)
                    continue
                
                # Create supplier
                payload = {
                    "doctype": "Supplier",
                    "supplier_name": supplier_name,
                    "supplier_group": "All Supplier Groups",
                    "default_currency": "KES"
                }
                
                if pd.notna(supplier_row.get('phone')):
                    payload["mobile_no"] = str(int(supplier_row['phone']))
                if pd.notna(supplier_row.get('email')):
                    payload["email_id"] = supplier_row['email']
                
                self.client.insert(payload)
                self.results['suppliers']['created'].append(supplier_name)
                
            except Exception as e:
                self.results['suppliers']['errors'].append({
                    'supplier': supplier_name,
                    'error': str(e)[:150]
                })
    
    def create_service_items_from_invoices(
        self,
        invoice_items_df: pd.DataFrame
    ):
        """
        Create service items from invoice line items.
        
        Args:
            invoice_items_df: Invoice items with item_description
        """
        # Get unique item descriptions
        unique_items = invoice_items_df['item_description'].dropna().unique()
        
        for item_name in unique_items:
            try:
                # Check if already exists
                existing = self.client.get_list(
                    "Item",
                    filters={"item_name": item_name},
                    limit_page_length=1
                )
                
                if existing:
                    self.results['items']['existed'].append(item_name)
                    continue
                
                # Get UOM from first occurrence
                item_rows = invoice_items_df[invoice_items_df['item_description'] == item_name]
                uom = item_rows.iloc[0]['unit'].strip().capitalize() if pd.notna(item_rows.iloc[0]['unit']) else 'Nos'
                
                # Create service item
                payload = {
                    "doctype": "Item",
                    "item_code": item_name,
                    "item_name": item_name,
                    "item_group": "Services",
                    "stock_uom": uom,
                    "is_stock_item": 0,  # Service item, not stock
                    "include_item_in_manufacturing": 0,
                    "is_sales_item": 1,
                    "is_purchase_item": 0
                }
                
                self.client.insert(payload)
                self.results['items']['created'].append(item_name)
                
            except Exception as e:
                self.results['items']['errors'].append({
                    'item': item_name,
                    'error': str(e)[:150]
                })
    
    def create_all(
        self,
        contacts_df: pd.DataFrame,
        contact_types_df: pd.DataFrame,
        invoices_df: pd.DataFrame,
        invoice_items_df: pd.DataFrame
    ) -> Dict:
        """
        Create all master data in correct order.
        
        Args:
            contacts_df: Contacts master data
            contact_types_df: Contact types lookup
            invoices_df: Invoices with customer names
            invoice_items_df: Invoice line items
            
        Returns:
            Results dictionary with creation statistics
        """
        print("CREATING MASTER DATA")
        print("=" * 70)
        
        # Step 1: UOMs (required for items)
        print("Creating UOMs...")
        self.create_uoms_from_items(invoice_items_df)
        print(f"  Created: {len(self.results['uoms']['created'])}, "
              f"Existed: {len(self.results['uoms']['existed'])}, "
              f"Errors: {len(self.results['uoms']['errors'])}")
        
        # Step 2: Customers
        print("Creating Customers...")
        self.create_customers_from_contacts(contacts_df, invoices_df)
        print(f"  Created: {len(self.results['customers']['created'])}, "
              f"Existed: {len(self.results['customers']['existed'])}, "
              f"Errors: {len(self.results['customers']['errors'])}")
        
        # Step 3: Suppliers
        print("Creating Suppliers...")
        self.create_suppliers_from_contacts(contacts_df, contact_types_df)
        print(f"  Created: {len(self.results['suppliers']['created'])}, "
              f"Existed: {len(self.results['suppliers']['existed'])}, "
              f"Errors: {len(self.results['suppliers']['errors'])}")
        
        # Step 4: Service Items
        print("Creating Service Items...")
        self.create_service_items_from_invoices(invoice_items_df)
        print(f"  Created: {len(self.results['items']['created'])}, "
              f"Existed: {len(self.results['items']['existed'])}, "
              f"Errors: {len(self.results['items']['errors'])}")
        
        print("=" * 70)
        
        return self.results
    
    def print_summary(self):
        """Print formatted summary of creation results."""
        print("\n" + "=" * 70)
        print("MASTER DATA CREATION SUMMARY")
        print("=" * 70)
        
        for category, stats in self.results.items():
            print(f"\n{category.upper()}:")
            print(f"  Created: {len(stats['created'])}")
            print(f"  Existed: {len(stats['existed'])}")
            print(f"  Errors:  {len(stats['errors'])}")
            
            if stats['errors']:
                print(f"  First 3 errors:")
                for err in stats['errors'][:3]:
                    key = list(err.keys())[0]  # uom/customer/supplier/item
                    print(f"    {err[key]}: {err['error']}")
        
        print("=" * 70)
