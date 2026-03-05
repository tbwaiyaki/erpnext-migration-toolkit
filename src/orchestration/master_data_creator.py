"""
Master Data Creator for ERPNext.

Creates required master records before transaction import.
"""

from typing import Optional
from frappeclient import FrappeClient


class MasterDataCreator:
    """
    Create master data in ERPNext (Customers, Items, etc.).
    
    Must be run before importing transactions.
    
    Examples:
        >>> client = FrappeClient(url, api_key=key, api_secret=secret)
        >>> creator = MasterDataCreator(client, "Wellness Centre")
        >>> 
        >>> # Create all prerequisites
        >>> results = creator.create_all_masters()
    """
    
    def __init__(self, client: FrappeClient, company: str):
        """
        Initialize master data creator.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name in ERPNext
        """
        self.client = client
        self.company = company
        self.created = {
            'customers': [],
            'items': [],
            'accounts': [],
        }
        self.errors = []
    
    def create_customer(
        self,
        customer_name: str,
        customer_type: str = "Individual",
        customer_group: str = "Individual",
        territory: str = "Kenya"
    ) -> Optional[dict]:
        """
        Create customer in ERPNext.
        
        Args:
            customer_name: Customer name
            customer_type: Individual or Company
            customer_group: Customer classification
            territory: Geographic territory
            
        Returns:
            Created customer doc or None if failed
        """
        try:
            # Check if exists first
            existing = self.client.get_list(
                "Customer",
                filters={"customer_name": customer_name},
                limit_page_length=1
            )
            
            if existing:
                print(f"  ✓ Customer exists: {customer_name}")
                return existing[0]
            
            # Create new
            customer = self.client.insert({
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": customer_type,
                "customer_group": customer_group,
                "territory": territory,
            })
            
            self.created['customers'].append(customer_name)
            print(f"  ✓ Created customer: {customer_name}")
            return customer
            
        except Exception as e:
            self.errors.append({
                'type': 'customer',
                'name': customer_name,
                'error': str(e)
            })
            print(f"  ✗ Failed to create customer {customer_name}: {e}")
            return None
    
    def create_item(
        self,
        item_code: str,
        item_name: Optional[str] = None,
        item_group: str = "Services",
        stock_uom: str = "Nos",
        is_stock_item: int = 0
    ) -> Optional[dict]:
        """
        Create item in ERPNext.
        
        Args:
            item_code: Unique item code
            item_name: Display name (defaults to item_code)
            item_group: Item classification
            stock_uom: Unit of measure
            is_stock_item: 1 for inventory items, 0 for services
            
        Returns:
            Created item doc or None if failed
        """
        try:
            # Check if exists
            existing = self.client.get_list(
                "Item",
                filters={"item_code": item_code},
                limit_page_length=1
            )
            
            if existing:
                print(f"  ✓ Item exists: {item_code}")
                return existing[0]
            
            # Create new
            item = self.client.insert({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_name or item_code,
                "item_group": item_group,
                "stock_uom": stock_uom,
                "is_stock_item": is_stock_item,
            })
            
            self.created['items'].append(item_code)
            print(f"  ✓ Created item: {item_code}")
            return item
            
        except Exception as e:
            self.errors.append({
                'type': 'item',
                'name': item_code,
                'error': str(e)
            })
            print(f"  ✗ Failed to create item {item_code}: {e}")
            return None
    
    def create_customers_from_invoices(self, invoices: list) -> dict:
        """
        Extract unique customers from invoices and create them.
        
        Args:
            invoices: List of SalesInvoice objects
            
        Returns:
            Dict with created count and errors
        """
        print("\nCreating customers from invoices...")
        
        # Get unique customer names
        unique_customers = set(inv.customer for inv in invoices)
        
        print(f"Found {len(unique_customers)} unique customers")
        
        for customer_name in sorted(unique_customers):
            self.create_customer(customer_name)
        
        return {
            'total': len(unique_customers),
            'created': len(self.created['customers']),
            'errors': len([e for e in self.errors if e['type'] == 'customer'])
        }
    
    def create_wellness_items(self) -> dict:
        """
        Create standard wellness centre items.
        
        Returns:
            Dict with created count and errors
        """
        print("\nCreating wellness centre items...")
        
        items = [
            ("Event Venue Hire", "Event Venue Hire"),
            ("Room Accommodation", "Room Accommodation"),
            ("Farm Eggs", "Farm Eggs (Fresh)"),
            ("Wellness Services", "Wellness Services"),
        ]
        
        for item_code, item_name in items:
            self.create_item(item_code, item_name)
        
        return {
            'total': len(items),
            'created': len(self.created['items']),
            'errors': len([e for e in self.errors if e['type'] == 'item'])
        }
    
    def verify_accounts(self) -> dict:
        """
        Verify required accounts exist.
        
        Returns:
            Dict with account verification results
        """
        print("\nVerifying chart of accounts...")
        
        required_accounts = [
            "Debtors - WC",
            "VAT - WC",
            "Mobile Money - WC",
            "Cash - WC",
            "KCB - WC",
        ]
        
        found = []
        missing = []
        
        for account_name in required_accounts:
            try:
                accounts = self.client.get_list(
                    "Account",
                    filters={
                        "account_name": account_name.replace(" - WC", ""),
                        "company": self.company
                    },
                    limit_page_length=1
                )
                
                if accounts:
                    found.append(account_name)
                    print(f"  ✓ Account exists: {account_name}")
                else:
                    missing.append(account_name)
                    print(f"  ✗ Account missing: {account_name}")
                    
            except Exception as e:
                missing.append(account_name)
                print(f"  ✗ Error checking {account_name}: {e}")
        
        return {
            'required': len(required_accounts),
            'found': len(found),
            'missing': missing
        }
    
    def create_all_masters(self, invoices: list) -> dict:
        """
        Create all required master data.
        
        Args:
            invoices: List of SalesInvoice objects to extract customers from
            
        Returns:
            Complete summary of creation results
        """
        print("="*70)
        print("CREATING MASTER DATA")
        print("="*70)
        
        # Create customers
        customer_results = self.create_customers_from_invoices(invoices)
        
        # Create items
        item_results = self.create_wellness_items()
        
        # Verify accounts
        account_results = self.verify_accounts()
        
        print()
        print("="*70)
        print("MASTER DATA CREATION COMPLETE")
        print("="*70)
        print()
        print(f"Customers: {customer_results['created']}/{customer_results['total']}")
        print(f"Items:     {item_results['created']}/{item_results['total']}")
        print(f"Accounts:  {account_results['found']}/{account_results['required']}")
        print()
        
        if self.errors:
            print(f"Errors: {len(self.errors)}")
            for error in self.errors[:5]:
                print(f"  {error['type']}: {error['name']} - {error['error']}")
        else:
            print("✓ No errors")
        
        print("="*70)
        
        return {
            'customers': customer_results,
            'items': item_results,
            'accounts': account_results,
            'errors': self.errors
        }
