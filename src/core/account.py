"""
Account type for Chart of Accounts references.

Represents an account in the Chart of Accounts with type validation
and ERPNext naming convention support.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re


class AccountType(Enum):
    """
    ERPNext account types.
    
    These map directly to ERPNext's account_type field values.
    """
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    INCOME = "Income"
    EXPENSE = "Expense"
    
    # ERPNext also has these subtypes (treated as specialized accounts)
    RECEIVABLE = "Receivable"  # Subset of Asset
    PAYABLE = "Payable"        # Subset of Liability
    BANK = "Bank"              # Subset of Asset
    CASH = "Cash"              # Subset of Asset
    STOCK = "Stock"            # Subset of Asset
    TAX = "Tax"                # Can be Asset or Liability
    CHARGEABLE = "Chargeable"  # Income/Expense with tax implications
    
    def is_debit_positive(self) -> bool:
        """
        Determine if debits increase this account type.
        
        Debit-positive: Assets, Expenses
        Credit-positive: Liabilities, Equity, Income
        
        Returns:
            True if debits increase balance, False if credits increase
        """
        return self in (
            AccountType.ASSET,
            AccountType.EXPENSE,
            AccountType.RECEIVABLE,
            AccountType.BANK,
            AccountType.CASH,
            AccountType.STOCK,
        )
    
    def is_balance_sheet(self) -> bool:
        """Check if this account appears on Balance Sheet (vs P&L)"""
        return self in (
            AccountType.ASSET,
            AccountType.LIABILITY,
            AccountType.EQUITY,
            AccountType.RECEIVABLE,
            AccountType.PAYABLE,
            AccountType.BANK,
            AccountType.CASH,
            AccountType.STOCK,
        )


@dataclass(frozen=True)
class Account:
    """
    Immutable reference to a Chart of Accounts entry.
    
    ERPNext account names follow the pattern: "Account Name - Company Abbr"
    Example: "Cash - WC", "Event Venue Hire - WC"
    
    This class validates the account name format and provides utilities
    for working with ERPNext's account hierarchy.
    
    Examples:
        >>> acc = Account("Cash - WC", AccountType.CASH)
        >>> acc.name
        'Cash - WC'
        >>> acc.base_name
        'Cash'
        >>> acc.company_suffix
        'WC'
        
        >>> acc = Account("Debtors", AccountType.RECEIVABLE, company="WC")
        >>> acc.name  # Auto-formats with suffix
        'Debtors - WC'
    """
    
    name: str
    account_type: AccountType
    account_number: Optional[str] = None
    parent_account: Optional[str] = None
    
    def __init__(
        self,
        name: str,
        account_type: AccountType,
        account_number: Optional[str] = None,
        parent_account: Optional[str] = None,
        company: Optional[str] = None,
    ):
        """
        Initialize Account with validation.
        
        Args:
            name: Account name, with or without company suffix
                  "Cash - WC" or just "Cash" (if company provided)
            account_type: Type from AccountType enum
            account_number: Optional account code (e.g., "1000")
            parent_account: Parent account name (for hierarchy)
            company: Company abbreviation (auto-appends if name lacks suffix)
            
        Raises:
            ValueError: If name format invalid or account_type not enum
        """
        # Validate account type
        if not isinstance(account_type, AccountType):
            raise ValueError(f"account_type must be AccountType enum, got {type(account_type)}")
        
        # Handle name formatting
        if company and " - " not in name:
            # Auto-append company suffix
            formatted_name = f"{name} - {company}"
        else:
            formatted_name = name.strip()
        
        # Validate name format
        if not formatted_name:
            raise ValueError("Account name cannot be empty")
        
        # ERPNext accounts should have company suffix (but allow flexible for parent references)
        if " - " in formatted_name:
            parts = formatted_name.rsplit(" - ", 1)
            if len(parts[1]) < 1:
                raise ValueError(f"Invalid account name format: '{formatted_name}'")
        
        # Validate account number if provided
        if account_number is not None:
            account_number = str(account_number).strip()
            if not account_number:
                raise ValueError("Account number cannot be empty string")
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'name', formatted_name)
        object.__setattr__(self, 'account_type', account_type)
        object.__setattr__(self, 'account_number', account_number)
        object.__setattr__(self, 'parent_account', parent_account)
    
    @property
    def base_name(self) -> str:
        """
        Get account name without company suffix.
        
        Returns:
            Account name without " - XX" suffix
            
        Example:
            >>> Account("Cash - WC", AccountType.CASH).base_name
            'Cash'
        """
        if " - " in self.name:
            return self.name.rsplit(" - ", 1)[0]
        return self.name
    
    @property
    def company_suffix(self) -> Optional[str]:
        """
        Extract company abbreviation from account name.
        
        Returns:
            Company suffix or None if no suffix present
            
        Example:
            >>> Account("Cash - WC", AccountType.CASH).company_suffix
            'WC'
        """
        if " - " in self.name:
            return self.name.rsplit(" - ", 1)[1]
        return None
    
    def __str__(self) -> str:
        """Human-readable format"""
        if self.account_number:
            return f"{self.account_number} - {self.name}"
        return self.name
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"Account('{self.name}', {self.account_type})"
    
    def is_debit_positive(self) -> bool:
        """
        Check if debits increase this account's balance.
        
        Delegates to AccountType.is_debit_positive()
        
        Returns:
            True if debits increase balance (Assets, Expenses)
            False if credits increase balance (Liabilities, Equity, Income)
        """
        return self.account_type.is_debit_positive()
    
    def is_balance_sheet_account(self) -> bool:
        """Check if account appears on Balance Sheet (vs P&L)"""
        return self.account_type.is_balance_sheet()
    
    def is_profit_and_loss_account(self) -> bool:
        """Check if account appears on Profit & Loss statement"""
        return not self.is_balance_sheet_account()
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext API format for Chart of Accounts.
        
        Returns:
            Dict suitable for ERPNext Account doctype creation
        """
        payload = {
            "doctype": "Account",
            "account_name": self.base_name,
            "account_type": self.account_type.value,
        }
        
        if self.account_number:
            payload["account_number"] = self.account_number
        
        if self.parent_account:
            payload["parent_account"] = self.parent_account
        
        # Company is extracted from name suffix
        if self.company_suffix:
            payload["company"] = self.company_suffix
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'Account':
        """
        Create Account from ERPNext API response.
        
        Args:
            doc: ERPNext Account document dict
            
        Returns:
            Account instance
            
        Example:
            >>> doc = {"name": "Cash - WC", "account_type": "Cash", ...}
            >>> acc = Account.from_erpnext(doc)
        """
        # ERPNext returns full name with company suffix
        name = doc.get("name") or doc.get("account_name", "")
        
        # Map string account_type to enum
        account_type_str = doc.get("account_type", "")
        try:
            account_type = AccountType(account_type_str)
        except ValueError:
            # Fallback to generic type
            if account_type_str in ("Income", "Expense"):
                account_type = AccountType[account_type_str.upper()]
            else:
                account_type = AccountType.ASSET  # Default fallback
        
        return cls(
            name=name,
            account_type=account_type,
            account_number=doc.get("account_number"),
            parent_account=doc.get("parent_account"),
        )


def parse_account_name(name: str) -> tuple[str, Optional[str]]:
    """
    Parse account name into base name and company suffix.
    
    Args:
        name: Full account name (e.g., "Cash - WC")
        
    Returns:
        Tuple of (base_name, company_suffix)
        
    Examples:
        >>> parse_account_name("Cash - WC")
        ('Cash', 'WC')
        
        >>> parse_account_name("Cash")
        ('Cash', None)
    """
    if " - " in name:
        parts = name.rsplit(" - ", 1)
        return (parts[0], parts[1])
    return (name, None)


# Common account references for reuse
def create_standard_accounts(company: str) -> dict[str, Account]:
    """
    Create standard chart of accounts for a company.
    
    Args:
        company: Company abbreviation (e.g., "WC")
        
    Returns:
        Dict mapping account purpose to Account instance
    """
    return {
        # Assets
        "cash": Account("Cash", AccountType.CASH, company=company),
        "bank": Account("Bank", AccountType.BANK, company=company),
        "debtors": Account("Debtors", AccountType.RECEIVABLE, company=company),
        "stock": Account("Stock", AccountType.STOCK, company=company),
        
        # Liabilities
        "creditors": Account("Creditors", AccountType.PAYABLE, company=company),
        
        # Equity
        "capital": Account("Capital Stock", AccountType.EQUITY, company=company),
        "retained_earnings": Account("Retained Earnings", AccountType.EQUITY, company=company),
        
        # Income (P&L)
        "revenue": Account("Sales", AccountType.INCOME, company=company),
        
        # Expenses (P&L)
        "expenses": Account("Expenses", AccountType.EXPENSE, company=company),
    }
