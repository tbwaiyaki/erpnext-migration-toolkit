"""
Customer Registry - Centralized customer management for migration.

Provides a single point of control for customer creation and lookup across
all importers. Follows the same architectural pattern as AccountRegistry.

Version 1.0: Initial implementation

Architecture:
- Single responsibility: Customer existence and creation
- Used by all importers that need customers
- Configurable customer groups for categorization
- Audit trail of created customers

Usage:
    # Initialize registry
    registry = CustomerRegistry(client, company="Wellness Centre")
    
    # Ensure customer exists (auto-create if needed)
    customer_name = registry.ensure_customer(
        customer_name="Rose Adhiambo",
        customer_group="B&B Guests",
        customer_type="Individual"
    )
    
    # Use in invoice
    invoice = {
        "customer": customer_name,
        ...
    }
"""

from frappeclient import FrappeClient
from typing import Optional, Dict, Set


class CustomerRegistry:
    """
    Centralized customer management for migration.
    
    Handles customer existence checking, creation, and categorization.
    All importers should use this instead of creating customers directly.
    """
    
    VERSION = "1.0"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        default_territory: str = "Kenya"
    ):
        """
        Initialize customer registry.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
            default_territory: Default territory for new customers
        """
        self.client = client
        self.company = company
        self.default_territory = default_territory
        
        # Track created entities
        self.customers_created = 0
        self.customer_groups_created = 0
        
        # Cache to avoid duplicate API calls
        self._existing_customers: Set[str] = set()
        self._existing_groups: Set[str] = set()
        self._cache_loaded = False
    
    def ensure_customer(
        self,
        customer_name: str,
        customer_group: str = "Individual",
        customer_type: str = "Individual"
    ) -> str:
        """
        Ensure customer exists, create if needed.
        
        Args:
            customer_name: Customer name
            customer_group: Customer group for categorization
            customer_type: Individual or Company
            
        Returns:
            Customer name (same as input)
        """
        # Load cache on first use
        if not self._cache_loaded:
            self._load_cache()
        
        # Check cache first
        if customer_name in self._existing_customers:
            return customer_name
        
        # Ensure customer group exists
        self._ensure_customer_group(customer_group)
        
        # Create customer
        try:
            customer = {
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": customer_type,
                "customer_group": customer_group,
                "territory": self.default_territory
            }
            
            self.client.insert(customer)
            self.customers_created += 1
            self._existing_customers.add(customer_name)
            
        except Exception as e:
            # If already exists, add to cache and continue
            if "already exists" in str(e).lower():
                self._existing_customers.add(customer_name)
            else:
                raise
        
        return customer_name
    
    def _ensure_customer_group(self, group_name: str):
        """
        Ensure customer group exists, create if needed.
        
        Args:
            group_name: Customer group name
        """
        # Check cache
        if group_name in self._existing_groups:
            return
        
        # Standard ERPNext groups that always exist
        standard_groups = {"Individual", "Commercial", "Government", "Non Profit"}
        if group_name in standard_groups:
            self._existing_groups.add(group_name)
            return
        
        # Create custom group
        try:
            group = {
                "doctype": "Customer Group",
                "customer_group_name": group_name,
                "parent_customer_group": "Individual",  # Default parent
                "is_group": 0
            }
            
            self.client.insert(group)
            self.customer_groups_created += 1
            self._existing_groups.add(group_name)
            
        except Exception as e:
            # If already exists, add to cache
            if "already exists" in str(e).lower():
                self._existing_groups.add(group_name)
            else:
                raise
    
    def _load_cache(self):
        """Load existing customers and groups into cache."""
        try:
            # Load existing customers
            customers = self.client.get_list(
                "Customer",
                fields=["customer_name"],
                limit_page_length=500
            )
            self._existing_customers = {c['customer_name'] for c in customers}
            
            # Load existing customer groups
            groups = self.client.get_list(
                "Customer Group",
                fields=["customer_group_name"],
                limit_page_length=100
            )
            self._existing_groups = {g['customer_group_name'] for g in groups}
            
            self._cache_loaded = True
            
        except Exception as e:
            # If cache loading fails, continue without cache
            # (will check ERPNext directly each time)
            self._cache_loaded = True
    
    def get_summary(self) -> str:
        """Get summary of customer registry activity."""
        lines = []
        
        if self.customer_groups_created > 0:
            lines.append(f"Customer Groups Created: {self.customer_groups_created}")
        
        if self.customers_created > 0:
            lines.append(f"Customers Created:       {self.customers_created}")
        
        return "\n".join(lines) if lines else "No new customers created"
    
    def reset_stats(self):
        """Reset creation counters (useful between import phases)."""
        self.customers_created = 0
        self.customer_groups_created = 0
