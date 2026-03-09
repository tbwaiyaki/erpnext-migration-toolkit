"""
Account Registry - Dynamic account discovery for ERPNext migrations.

Provides centralized account lookup with smart matching and caching.
Eliminates hard-coded account names from importers.

Version: 1.1 - Added AccountCreationPolicy support
Created: March 7, 2026
Updated: March 9, 2026
"""

from typing import Dict, Optional, List
from frappeclient import FrappeClient


class AccountRegistry:
    """
    Registry for discovering and caching ERPNext account mappings.
    
    Enables reusable migrations that work with ANY country's data by
    dynamically discovering accounts instead of hard-coding names.
    
    Usage:
        registry = AccountRegistry(client, "Wellness Centre")
        
        # Discover payment account dynamically
        mpesa_account = registry.get_payment_account("M-Pesa")
        # Returns: "M-Pesa - WC" OR "Mobile Money - WC" (whichever exists)
        
        # Get expense account
        salary_account = registry.get_expense_account("Salaries")
        # Returns: "Salary - WC" OR "Salaries - WC" (fuzzy match)
        
        # Ensure account exists (create if missing)
        registry.ensure_payment_account("M-Pesa", account_type="Bank")
    
    Features:
        - Smart matching (case-insensitive, fuzzy, keyword-based)
        - Caching for performance
        - Works with ANY naming convention (Kenya, Tanzania, Uganda, etc.)
        - Graceful error messages
        - Account creation support
    """
    
    VERSION = "1.1"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        company_suffix: Optional[str] = None,
        policy: Optional['AccountCreationPolicy'] = None
    ):
        """
        Initialize account registry.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
            company_suffix: Optional suffix for accounts (e.g., "WC")
                          If None, auto-detected from first account
            policy: Optional AccountCreationPolicy for controlling account creation
                   If None, defaults to AUTOMATIC mode
        """
        self.client = client
        self.company = company
        self.suffix = company_suffix or self._detect_suffix()
        
        # Import here to avoid circular dependency
        if policy is None:
            from core.account_creation_policy import AccountCreationPolicy
            policy = AccountCreationPolicy(mode=AccountCreationPolicy.AUTOMATIC)
        self.policy = policy
        
        # Caches
        self._payment_accounts_cache = {}
        self._expense_accounts_cache = {}
        self._all_accounts_cache = None
    
    def get_payment_account(self, payment_method: str) -> str:
        """
        Get account for payment method via smart discovery.
        
        Args:
            payment_method: Payment method (e.g., "M-Pesa", "Bank Transfer", "Cash")
            
        Returns:
            Account name (e.g., "M-Pesa - WC")
            
        Raises:
            ValueError: If no matching account found
        
        Example:
            account = registry.get_payment_account("M-Pesa")
            # Returns "M-Pesa - WC" or "Mobile Money - WC" (whichever exists)
        """
        # Check cache
        if payment_method in self._payment_accounts_cache:
            return self._payment_accounts_cache[payment_method]
        
        # Discover account
        account = self._discover_payment_account(payment_method)
        
        # Cache result
        self._payment_accounts_cache[payment_method] = account
        return account
    
    def get_expense_account(
        self,
        category_name: str,
        create_if_missing: bool = False
    ) -> str:
        """
        Get expense account for category.
        
        Args:
            category_name: Expense category (e.g., "Salaries", "Utilities")
            create_if_missing: Create account if not found
            
        Returns:
            Account name
            
        Raises:
            ValueError: If not found and create_if_missing=False
        
        Example:
            account = registry.get_expense_account("Salaries")
            # Returns "Salary - WC" or "Salaries - WC" (fuzzy match)
        """
        # Check cache
        if category_name in self._expense_accounts_cache:
            return self._expense_accounts_cache[category_name]
        
        # Discover or create
        account = self._discover_expense_account(category_name)
        
        if not account and create_if_missing:
            account = self._create_expense_account(category_name)
        
        if not account:
            raise ValueError(f"No expense account found for: {category_name}")
        
        # Cache result
        self._expense_accounts_cache[category_name] = account
        return account
    
    def ensure_payment_account(
        self,
        payment_method: str,
        account_name: Optional[str] = None,
        account_type: str = "Bank",
        parent_account: Optional[str] = None
    ) -> str:
        """
        Ensure payment account exists, create if missing.
        
        Idempotent operation - safe to call multiple times.
        
        Args:
            payment_method: Payment method (e.g., "M-Pesa")
            account_name: Optional account name (e.g., "M-Pesa" or "Mobile Money")
            account_type: "Bank" or "Cash"
            parent_account: Parent account (e.g., "Bank Accounts - WC")
            
        Returns:
            Account name (full, e.g., "M-Pesa - WC")
        
        Example:
            # Create M-Pesa account if missing
            account = registry.ensure_payment_account("M-Pesa", account_type="Bank")
            # Returns existing or creates new "M-Pesa - WC"
        """
        # Try to discover first
        try:
            return self.get_payment_account(payment_method)
        except ValueError:
            pass
        
        # Create account
        if not account_name:
            account_name = payment_method
        
        return self._create_payment_account(
            account_name,
            account_type,
            parent_account
        )
    
    def clear_cache(self):
        """Clear all caches. Useful for testing or after account creation."""
        self._payment_accounts_cache = {}
        self._expense_accounts_cache = {}
        self._all_accounts_cache = None
    
    # ==================== PRIVATE METHODS ====================
    
    def _detect_suffix(self) -> str:
        """
        Auto-detect company suffix from existing accounts.
        
        Returns:
            Suffix (e.g., "WC" from "Cash - WC")
            Falls back to abbreviation of company name
        """
        try:
            # Get any account for this company
            accounts = self.client.get_list(
                "Account",
                filters={"company": self.company},
                fields=["name"],
                limit_page_length=1
            )
            
            if accounts:
                # Extract suffix from account name
                # Format: "Account Name - SUFFIX"
                account_name = accounts[0]['name']
                if ' - ' in account_name:
                    return account_name.split(' - ')[-1]
        except Exception:
            pass
        
        # Fallback: abbreviate company name
        words = self.company.split()
        if len(words) > 1:
            return ''.join(word[0].upper() for word in words)
        return self.company[:3].upper()
    
    def _load_all_accounts(self) -> List[Dict]:
        """
        Load all accounts for company from ERPNext.
        
        Returns:
            List of account dicts with name, account_name, account_type, is_group
        """
        try:
            accounts = self.client.get_list(
                "Account",
                filters={"company": self.company},
                fields=["name", "account_name", "account_type", "is_group", "parent_account"],
                limit_page_length=9999
            )
            return accounts
        except Exception as e:
            raise ValueError(f"Failed to load accounts from ERPNext: {e}")
    
    def _discover_payment_account(self, payment_method: str) -> str:
        """
        Discover payment account via smart matching.
        
        Strategy:
        1. Get all Bank/Cash accounts for company
        2. Try exact match (case-insensitive)
        3. Try fuzzy match (contains search)
        4. Apply domain-specific rules (e.g., "Bank Transfer" → any Bank account)
        
        Args:
            payment_method: Payment method to search for
            
        Returns:
            Account name
            
        Raises:
            ValueError: If no match found
        """
        # Load all accounts if not cached
        if not self._all_accounts_cache:
            self._all_accounts_cache = self._load_all_accounts()
        
        # Filter to Bank/Cash leaf accounts only
        payment_accounts = [
            acc for acc in self._all_accounts_cache
            if acc.get('account_type') in ['Bank', 'Cash']
            and acc.get('is_group') == 0  # Leaf accounts only
        ]
        
        if not payment_accounts:
            raise ValueError(f"No Bank or Cash accounts found for company: {self.company}")
        
        # Strategy 1: Exact match (case-insensitive)
        payment_lower = payment_method.lower()
        for acc in payment_accounts:
            acc_name = acc['account_name'].lower()
            if payment_lower == acc_name or payment_lower in acc_name:
                return acc['name']
        
        # Strategy 2: Keyword matching
        keywords = self._extract_keywords(payment_method)
        for keyword in keywords:
            for acc in payment_accounts:
                if keyword.lower() in acc['account_name'].lower():
                    return acc['name']
        
        # Strategy 3: Domain-specific rules
        
        # Bank Transfer: find first non-mobile bank account
        if payment_method.lower() in ["bank transfer", "bank"]:
            for acc in payment_accounts:
                acc_name_lower = acc['account_name'].lower()
                if acc.get('account_type') == 'Bank' and \
                   'mobile' not in acc_name_lower and \
                   'mpesa' not in acc_name_lower and \
                   'm-pesa' not in acc_name_lower:
                    return acc['name']
        
        # Cash: find first cash account
        if payment_method.lower() == "cash":
            for acc in payment_accounts:
                if acc.get('account_type') == 'Cash':
                    return acc['name']
        
        # M-Pesa variations: find mobile money account
        if payment_method.lower() in ["mpesa", "m-pesa", "mobile money"]:
            for acc in payment_accounts:
                acc_name_lower = acc['account_name'].lower()
                if any(term in acc_name_lower for term in ['mpesa', 'm-pesa', 'mobile']):
                    return acc['name']
        
        # No match found
        available = [acc['account_name'] for acc in payment_accounts]
        raise ValueError(
            f"No payment account found for: {payment_method}\n"
            f"Available Bank/Cash accounts: {available}\n"
            f"Hint: Use ensure_payment_account() to create missing accounts"
        )
    
    def _discover_expense_account(self, category_name: str) -> Optional[str]:
        """
        Discover expense account via fuzzy matching.
        
        Args:
            category_name: Expense category
            
        Returns:
            Account name or None if not found
        """
        # Load all accounts if not cached
        if not self._all_accounts_cache:
            self._all_accounts_cache = self._load_all_accounts()
        
        # Filter to Expense leaf accounts
        expense_accounts = [
            acc for acc in self._all_accounts_cache
            if acc.get('account_type') == 'Expense'
            and acc.get('is_group') == 0
        ]
        
        if not expense_accounts:
            return None
        
        # Exact match (case-insensitive)
        category_lower = category_name.lower()
        for acc in expense_accounts:
            acc_name = acc['account_name'].lower()
            if category_lower == acc_name or category_lower in acc_name:
                return acc['name']
        
        # Keyword matching
        keywords = self._extract_keywords(category_name)
        for keyword in keywords:
            for acc in expense_accounts:
                if keyword.lower() in acc['account_name'].lower():
                    return acc['name']
        
        return None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text for matching.
        
        Args:
            text: Input text
            
        Returns:
            List of keywords
        
        Example:
            "Bank Transfer" → ["Bank", "Transfer"]
        """
        # Remove common words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'of', 'for', 'to', 'from'}
        
        # Split and filter
        words = text.split()
        keywords = [w for w in words if w.lower() not in stopwords and len(w) > 2]
        
        return keywords if keywords else [text]
    
    def _create_payment_account(
        self,
        account_name: str,
        account_type: str,
        parent_account: Optional[str] = None
    ) -> str:
        """
        Create payment account in ERPNext.
        
        Args:
            account_name: Account name (without suffix)
            account_type: "Bank" or "Cash"
            parent_account: Parent account (e.g., "Bank Accounts - WC")
            
        Returns:
            Full account name (with suffix)
        """
        # Determine parent if not provided
        if not parent_account:
            if account_type == "Cash":
                parent_account = f"Cash - {self.suffix}"
            else:  # Bank
                parent_account = f"Bank Accounts - {self.suffix}"
        
        # Full account name with suffix
        full_name = f"{account_name} - {self.suffix}"
        
        # Check if exists
        try:
            existing = self.client.get_doc("Account", full_name)
            if existing:
                # Already exists, cache and return
                self._payment_accounts_cache[account_name] = full_name
                return full_name
        except Exception:
            pass  # Doesn't exist, create it
        
        # Create account
        account_doc = {
            "doctype": "Account",
            "account_name": account_name,
            "company": self.company,
            "account_type": account_type,
            "parent_account": parent_account,
            "is_group": 0
        }
        
        try:
            result = self.client.insert(account_doc)
            created_name = result.get('name')
            
            # Cache result
            self._payment_accounts_cache[account_name] = created_name
            
            # Clear all accounts cache to pick up new account
            self._all_accounts_cache = None
            
            return created_name
        except Exception as e:
            raise ValueError(f"Failed to create payment account '{account_name}': {e}")
    
    def _create_expense_account(
        self,
        category_name: str,
        parent_account: Optional[str] = None
    ) -> str:
        """
        Create expense account in ERPNext.
        
        Args:
            category_name: Category name (without suffix)
            parent_account: Parent account (default: "Indirect Expenses - {suffix}")
            
        Returns:
            Full account name (with suffix)
        """
        # Determine parent if not provided
        if not parent_account:
            parent_account = f"Indirect Expenses - {self.suffix}"
        
        # Full account name with suffix
        full_name = f"{category_name} - {self.suffix}"
        
        # Check if exists
        try:
            existing = self.client.get_doc("Account", full_name)
            if existing:
                self._expense_accounts_cache[category_name] = full_name
                return full_name
        except Exception:
            pass
        
        # Create account
        account_doc = {
            "doctype": "Account",
            "account_name": category_name,
            "company": self.company,
            "account_type": "Expense",
            "parent_account": parent_account,
            "is_group": 0
        }
        
        try:
            result = self.client.insert(account_doc)
            created_name = result.get('name')
            
            # Cache result
            self._expense_accounts_cache[category_name] = created_name
            
            # Clear cache
            self._all_accounts_cache = None
            
            return created_name
        except Exception as e:
            raise ValueError(f"Failed to create expense account '{category_name}': {e}")
    
    def ensure_account(
        self,
        account_name: str,
        account_type: str,
        parent_account: Optional[str] = None,
        is_group: int = 0
    ) -> str:
        """
        Ensure account exists, create if missing (idempotent).
        
        Generic account creation for any account type (Equity, Bank, Asset, etc.)
        
        Args:
            account_name: Account name (without suffix, e.g., "Capital Stock")
            account_type: ERPNext account type (Equity, Bank, Asset, Liability, Income, Expense, Cash)
            parent_account: Parent account (with suffix, e.g., "Equity - WC")
                          If None, uses default parent for account type
            is_group: 1 for group account, 0 for leaf (default: 0)
            
        Returns:
            Full account name (with suffix, e.g., "Capital Stock - WC")
        
        Example:
            # Create equity account
            account = registry.ensure_account("Capital Stock", "Equity", parent_account="Equity - WC")
            # Returns: "Capital Stock - WC"
        """
        # Full account name with suffix
        full_name = f"{account_name} - {self.suffix}"
        
        # Check if exists
        try:
            existing = self.client.get_list(
                "Account",
                filters={"name": full_name, "company": self.company},
                limit_page_length=1
            )
            if existing:
                return full_name
        except Exception:
            pass
        
        # Determine default parent if not provided
        if not parent_account:
            parent_map = {
                "Equity": f"Equity - {self.suffix}",
                "Bank": f"Bank Accounts - {self.suffix}",
                "Cash": f"Cash - {self.suffix}",
                "Asset": f"Assets - {self.suffix}",
                "Liability": f"Liabilities - {self.suffix}",
                "Income": f"Income - {self.suffix}",
                "Expense": f"Indirect Expenses - {self.suffix}"
            }
            parent_account = parent_map.get(account_type, f"{account_type} - {self.suffix}")
        
        # Check policy before creating
        should_create = self.policy.should_create_account(
            account_name=full_name,
            account_type=account_type,
            parent_account=parent_account
        )
        
        if not should_create:
            # User declined in CONFIRM mode
            raise ValueError(
                f"Account creation declined by user: {full_name}\n"
                f"Cannot proceed without this account."
            )
        
        # Create account
        account_doc = {
            "doctype": "Account",
            "account_name": account_name,
            "company": self.company,
            "account_type": account_type,
            "parent_account": parent_account,
            "is_group": is_group
        }
        
        try:
            result = self.client.insert(account_doc)
            created_name = result.get('name')
            
            # Clear cache to pick up new account
            self._all_accounts_cache = None
            
            return created_name
        except Exception as e:
            raise ValueError(f"Failed to create account '{account_name}': {e}")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"AccountRegistry(company='{self.company}', "
            f"suffix='{self.suffix}', "
            f"cached_payments={len(self._payment_accounts_cache)}, "
            f"cached_expenses={len(self._expense_accounts_cache)})"
        )
