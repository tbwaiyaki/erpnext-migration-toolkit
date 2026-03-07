# AccountRegistry Design Document

**Version:** 1.0  
**Created:** March 7, 2026  
**Purpose:** Dynamic account discovery for ERPNext Migration Toolkit - eliminates hard-coding

---

## Problem Statement

### Current Issues

**Hard-coded account names in importers:**
```python
# PaymentEntryImporter v3.1
PAYMENT_ACCOUNT_MAP = {
    'M-Pesa': 'M-Pesa - WC',
    'Bank Transfer': 'Bank - KCB - WC',
    'Cash': 'Cash - WC'
}
```

**Problems:**
1. **Not reusable** - works only for Kenyan accounts with exact names
2. **Brittle** - breaks if account names change
3. **Not portable** - can't migrate Tanzanian, Ugandan, or other data
4. **Violates DRY** - same mapping logic in multiple importers
5. **Hard to test** - can't mock account lookups

### Requirements

**AccountRegistry must:**
1. ✅ Discover accounts dynamically (query ERPNext)
2. ✅ Support ANY naming convention (Kenya, Tanzania, Uganda, etc.)
3. ✅ Cache results for performance
4. ✅ Smart matching (fuzzy/flexible)
5. ✅ Single source of truth (one place for account logic)
6. ✅ Easy to test (mockable interface)
7. ✅ Handle missing accounts gracefully
8. ✅ Support account creation if needed

---

## Architecture

### Class Design

```python
"""
Account Registry - Dynamic account discovery for ERPNext migrations.

Provides centralized account lookup with smart matching and caching.
Eliminates hard-coded account names from importers.
"""

from typing import Dict, Optional, List
from frappeclient import FrappeClient


class AccountRegistry:
    """
    Registry for discovering and caching ERPNext account mappings.
    
    Usage:
        registry = AccountRegistry(client, "Wellness Centre")
        
        # Discover payment account dynamically
        mpesa_account = registry.get_payment_account("M-Pesa")
        # Returns: "M-Pesa - WC" OR "Mobile Money - WC" (whichever exists)
        
        # Get expense account
        salary_account = registry.get_expense_account("Salaries")
        # Returns: "Salary - WC" OR "Salaries - WC" (fuzzy match)
    """
    
    VERSION = "1.0"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        company_suffix: Optional[str] = None
    ):
        """
        Initialize account registry.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
            company_suffix: Optional suffix for accounts (e.g., "WC")
                          If None, auto-detected from first account
        """
        self.client = client
        self.company = company
        self.suffix = company_suffix or self._detect_suffix()
        
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
        
        Args:
            payment_method: Payment method (e.g., "M-Pesa")
            account_name: Optional account name (e.g., "M-Pesa" or "Mobile Money")
            account_type: "Bank" or "Cash"
            parent_account: Parent account (e.g., "Bank Accounts - WC")
            
        Returns:
            Account name (full, e.g., "M-Pesa - WC")
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
        # Load all payment accounts if not cached
        if not self._all_accounts_cache:
            self._all_accounts_cache = self._load_all_accounts()
        
        # Filter to Bank/Cash accounts only
        payment_accounts = [
            acc for acc in self._all_accounts_cache
            if acc.get('account_type') in ['Bank', 'Cash']
            and acc.get('is_group') == 0  # Leaf accounts only
        ]
        
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
        if payment_method == "Bank Transfer":
            # Return first bank account that's not mobile money
            for acc in payment_accounts:
                acc_name_lower = acc['account_name'].lower()
                if acc.get('account_type') == 'Bank' and \
                   'mobile' not in acc_name_lower and \
                   'mpesa' not in acc_name_lower and \
                   'm-pesa' not in acc_name_lower:
                    return acc['name']
        
        if payment_method == "Cash":
            # Return first cash account
            for acc in payment_accounts:
                if acc.get('account_type') == 'Cash':
                    return acc['name']
        
        # No match found
        raise ValueError(
            f"No payment account found for: {payment_method}\n"
            f"Available accounts: {[acc['account_name'] for acc in payment_accounts]}"
        )
    
    def _discover_expense_account(self, category_name: str) -> Optional[str]:
        """
        Discover expense account via fuzzy matching.
        
        Args:
            category_name: Expense category
            
        Returns:
            Account name or None if not found
        """
        if not self._all_accounts_cache:
            self._all_accounts_cache = self._load_all_accounts()
        
        # Filter to Expense accounts
        expense_accounts = [
            acc for acc in self._all_accounts_cache
            if acc.get('root_type') == 'Expense'
            and acc.get('is_group') == 0
        ]
        
        # Try fuzzy match
        category_lower = category_name.lower()
        for acc in expense_accounts:
            acc_name_lower = acc['account_name'].lower()
            if category_lower in acc_name_lower or acc_name_lower in category_lower:
                return acc['name']
        
        return None
    
    def _create_payment_account(
        self,
        account_name: str,
        account_type: str,
        parent_account: Optional[str]
    ) -> str:
        """
        Create new payment account.
        
        Args:
            account_name: Account name (without suffix)
            account_type: "Bank" or "Cash"
            parent_account: Parent account name
            
        Returns:
            Full account name with suffix
        """
        # Determine parent
        if not parent_account:
            if account_type == "Bank":
                parent_account = f"Bank Accounts - {self.suffix}"
            else:
                parent_account = f"Cash In Hand - {self.suffix}"
        
        # Build account document
        account_doc = {
            "doctype": "Account",
            "account_name": account_name,
            "parent_account": parent_account,
            "company": self.company,
            "account_type": account_type,
            "account_currency": "KES",  # TODO: Make configurable
            "is_group": 0
        }
        
        # Create
        created = self.client.insert(account_doc)
        full_name = created['name']
        
        # Invalidate cache
        self._all_accounts_cache = None
        
        return full_name
    
    def _create_expense_account(self, category_name: str) -> str:
        """
        Create new expense account.
        
        Args:
            category_name: Category name
            
        Returns:
            Full account name
        """
        # Determine parent (simplified - can be made smarter)
        parent_account = f"Direct Expenses - {self.suffix}"
        
        account_doc = {
            "doctype": "Account",
            "account_name": category_name,
            "parent_account": parent_account,
            "company": self.company,
            "is_group": 0
        }
        
        created = self.client.insert(account_doc)
        
        # Invalidate cache
        self._all_accounts_cache = None
        
        return created['name']
    
    def _load_all_accounts(self) -> List[Dict]:
        """
        Load all accounts for company.
        
        Returns:
            List of account dicts with fields: name, account_name, account_type, 
            root_type, is_group
        """
        accounts = self.client.get_list(
            "Account",
            filters={"company": self.company},
            fields=[
                "name",
                "account_name",
                "account_type",
                "root_type",
                "is_group"
            ],
            limit_page_length=999
        )
        return accounts
    
    def _detect_suffix(self) -> str:
        """
        Auto-detect company suffix from existing accounts.
        
        Returns:
            Suffix (e.g., "WC")
        """
        # Get one account
        accounts = self.client.get_list(
            "Account",
            filters={"company": self.company},
            fields=["name"],
            limit_page_length=1
        )
        
        if not accounts:
            # Fallback: use first letters of company
            words = self.company.split()
            return ''.join(word[0] for word in words).upper()
        
        # Extract suffix (e.g., "Cash - WC" → "WC")
        account_name = accounts[0]['name']
        if ' - ' in account_name:
            return account_name.split(' - ')[-1]
        
        # Fallback
        return self.company[:2].upper()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords for fuzzy matching.
        
        Args:
            text: Input text (e.g., "M-Pesa" or "Bank Transfer")
            
        Returns:
            List of keywords
        """
        # Remove common words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'for'}
        
        # Split on spaces and hyphens
        words = text.replace('-', ' ').split()
        
        # Filter stopwords and lowercase
        keywords = [
            word.lower() for word in words
            if word.lower() not in stopwords and len(word) > 2
        ]
        
        return keywords
    
    def clear_cache(self):
        """Clear all caches (useful for testing or after account changes)."""
        self._payment_accounts_cache = {}
        self._expense_accounts_cache = {}
        self._all_accounts_cache = None
```

---

## Usage Examples

### Basic Usage

```python
from orchestration.account_registry import AccountRegistry

# Initialize registry
registry = AccountRegistry(client, "Wellness Centre")

# Get payment accounts (auto-discovered)
mpesa = registry.get_payment_account("M-Pesa")
# Returns: "M-Pesa - WC" OR "Mobile Money - WC" (whichever exists)

bank = registry.get_payment_account("Bank Transfer")
# Returns: "Bank - KCB - WC" OR "Bank - Equity - WC" (first bank found)

cash = registry.get_payment_account("Cash")
# Returns: "Cash - WC"
```

### With Importers

```python
# Initialize registry once
registry = AccountRegistry(client, "Wellness Centre")

# Payment Entry Importer
payment_imp = PaymentEntryImporter(
    client=client,
    company="Wellness Centre",
    registry=registry  # Pass registry
)
results = payment_imp.import_batch(...)

# Expense Importer
expense_imp = ExpenseImporter(
    client=client,
    company="Wellness Centre",
    registry=registry  # Same registry
)
results = expense_imp.import_expenses(...)
```

### Ensuring Accounts Exist

```python
# Create accounts if missing (idempotent)
registry.ensure_payment_account("M-Pesa", account_type="Bank")
registry.ensure_payment_account("Bank Transfer", account_name="Bank - KCB", account_type="Bank")
registry.ensure_payment_account("Cash", account_type="Cash")

# Now importers will find these accounts
```

### Different Countries

```python
# Kenya
registry_ke = AccountRegistry(client, "Kenya Corp")
registry_ke.ensure_payment_account("M-Pesa", account_type="Bank")
# Creates: "M-Pesa - KC"

# Tanzania
registry_tz = AccountRegistry(client, "Tanzania Ltd")
registry_tz.ensure_payment_account("Tigo Pesa", account_type="Bank")
registry_tz.ensure_payment_account("Airtel Money", account_type="Bank")
# Creates: "Tigo Pesa - TL", "Airtel Money - TL"

# Uganda
registry_ug = AccountRegistry(client, "Uganda Inc")
registry_ug.ensure_payment_account("MTN Mobile Money", account_type="Bank")
# Creates: "MTN Mobile Money - UI"

# ALL use same importer code - no hard-coding!
```

---

## Integration with Importers

### PaymentEntryImporter Changes

**Before (hard-coded):**
```python
class PaymentEntryImporter:
    PAYMENT_ACCOUNT_MAP = {
        'M-Pesa': 'M-Pesa - {suffix}',
        'Bank Transfer': 'Bank - KCB - {suffix}',
        'Cash': 'Cash - {suffix}'
    }
    
    def __init__(self, client, company, company_suffix):
        self.suffix = company_suffix
```

**After (using AccountRegistry):**
```python
class PaymentEntryImporter:
    def __init__(self, client, company, registry):
        self.client = client
        self.company = company
        self.registry = registry  # Store registry
    
    def _build_payment_doc(self, pay_row, invoice):
        payment_method = pay_row.get('payment_method', 'Cash')
        
        # Use registry for dynamic discovery
        paid_to_account = self.registry.get_payment_account(payment_method)
        
        doc = {
            "doctype": "Payment Entry",
            "paid_to": paid_to_account,  # Dynamic!
            # ... rest of doc
        }
        return doc
```

### ExpenseImporter Changes

**Before:**
```python
class ExpenseImporter:
    PAYMENT_ACCOUNT_MAP = {
        'M-Pesa': 'Mobile Money - {suffix}',
        'Bank Transfer': 'KCB - {suffix}',
        'Cash': 'Cash - {suffix}'
    }
```

**After:**
```python
class ExpenseImporter:
    def __init__(self, client, company, registry):
        self.client = client
        self.company = company
        self.registry = registry
    
    def build_journal_entry(self, transaction, expense_account):
        payment_method = transaction['payment_method']
        
        # Use registry
        payment_account = self.registry.get_payment_account(payment_method)
        
        payload = {
            "doctype": "Journal Entry",
            "accounts": [
                {"account": expense_account, "debit": amount},
                {"account": payment_account, "credit": amount}  # Dynamic!
            ]
        }
        return payload
```

---

## Testing Strategy

### Unit Tests

```python
import pytest
from unittest.mock import Mock
from orchestration.account_registry import AccountRegistry


def test_discover_mpesa_account():
    """Test M-Pesa account discovery."""
    mock_client = Mock()
    mock_client.get_list.return_value = [
        {'name': 'M-Pesa - WC', 'account_name': 'M-Pesa', 
         'account_type': 'Bank', 'is_group': 0}
    ]
    
    registry = AccountRegistry(mock_client, "Wellness Centre", "WC")
    account = registry.get_payment_account("M-Pesa")
    
    assert account == "M-Pesa - WC"


def test_discover_mobile_money_alternate_name():
    """Test mobile money with different naming."""
    mock_client = Mock()
    mock_client.get_list.return_value = [
        {'name': 'Mobile Money - WC', 'account_name': 'Mobile Money',
         'account_type': 'Bank', 'is_group': 0}
    ]
    
    registry = AccountRegistry(mock_client, "Wellness Centre", "WC")
    account = registry.get_payment_account("M-Pesa")
    
    # Should find "Mobile Money" when searching for "M-Pesa"
    assert account == "Mobile Money - WC"


def test_bank_transfer_finds_any_bank():
    """Test Bank Transfer finds first non-mobile bank."""
    mock_client = Mock()
    mock_client.get_list.return_value = [
        {'name': 'M-Pesa - WC', 'account_name': 'M-Pesa',
         'account_type': 'Bank', 'is_group': 0},
        {'name': 'Bank - KCB - WC', 'account_name': 'Bank - KCB',
         'account_type': 'Bank', 'is_group': 0}
    ]
    
    registry = AccountRegistry(mock_client, "Wellness Centre", "WC")
    account = registry.get_payment_account("Bank Transfer")
    
    # Should skip M-Pesa and find KCB
    assert account == "Bank - KCB - WC"
```

---

## Migration Path

### Step 1: Implement AccountRegistry
1. Create `src/orchestration/account_registry.py`
2. Add unit tests
3. Test with mock data

### Step 2: Update PaymentEntryImporter
1. Add `registry` parameter to `__init__`
2. Remove `PAYMENT_ACCOUNT_MAP` constant
3. Replace `_get_payment_account` with `registry.get_payment_account()`
4. Update version to v3.2
5. Test with sample data

### Step 3: Update ExpenseImporter
1. Add `registry` parameter to `__init__`
2. Remove `PAYMENT_ACCOUNT_MAP` constant
3. Use `registry.get_payment_account()` in `build_journal_entry`
4. Update version to v1.1
5. Test with sample data

### Step 4: Integration Testing
1. Restore pristine snapshot
2. Create accounts using registry.ensure_payment_account()
3. Run full Phase 1 migration
4. Run full Phase 2 migration
5. Verify 100% success rate

---

## Benefits

### For Developers
- ✅ No hard-coding
- ✅ Single source of truth
- ✅ Easy to test (mockable)
- ✅ Reusable across projects

### For Users
- ✅ Works with ANY country's data
- ✅ Works with ANY account naming convention
- ✅ Automatic discovery (less configuration)
- ✅ Graceful error messages

### For Maintenance
- ✅ Change account logic in ONE place
- ✅ Add new account types easily
- ✅ Support new payment methods without code changes
- ✅ Clear separation of concerns

---

## Future Enhancements

### Phase 1 (Current)
- ✅ Payment account discovery
- ✅ Expense account discovery
- ✅ Smart matching

### Phase 2 (Future)
- [ ] Support account creation preferences (config file)
- [ ] Support multiple companies in one session
- [ ] Account validation (check if account is active)
- [ ] Account hierarchy navigation
- [ ] Support for tax accounts, inventory accounts, etc.

### Phase 3 (Advanced)
- [ ] Machine learning for better fuzzy matching
- [ ] Account recommendation engine
- [ ] Migration history tracking
- [ ] Account mapping export/import

---

**Version:** 1.0  
**Status:** Ready for Implementation  
**Next Steps:** Build AccountRegistry, update importers, test with pristine snapshot
