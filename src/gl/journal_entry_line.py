"""
Journal Entry Line for GL transactions.

Represents a single line in a journal entry with account and amount.
"""

from dataclasses import dataclass
from typing import Optional

from core.money import Money
from core.account import Account


@dataclass(frozen=True)
class JournalEntryLine:
    """
    Immutable journal entry line (single account + debit/credit).
    
    In double-entry bookkeeping, each line affects one account.
    Amount goes in either debit or credit column (not both).
    
    Examples:
        >>> # Debit line (increase asset)
        >>> cash = Account("Cash - WC", AccountType.CASH)
        >>> debit_line = JournalEntryLine(
        ...     account=cash,
        ...     debit=Money(15000, "KES"),
        ...     credit=Money.zero("KES")
        ... )
        
        >>> # Credit line (increase income)
        >>> revenue = Account("Event Venue Hire - WC", AccountType.INCOME)
        >>> credit_line = JournalEntryLine(
        ...     account=revenue,
        ...     debit=Money.zero("KES"),
        ...     credit=Money(15000, "KES")
        ... )
        
        >>> # Simplified constructor
        >>> debit_line = JournalEntryLine.debit(cash, Money(15000, "KES"))
        >>> credit_line = JournalEntryLine.credit(revenue, Money(15000, "KES"))
    """
    
    account: Account
    debit: Money
    credit: Money
    cost_center: Optional[str] = None
    reference_number: Optional[str] = None
    user_remark: Optional[str] = None
    
    def __init__(
        self,
        account: Account,
        debit: Money,
        credit: Money,
        cost_center: Optional[str] = None,
        reference_number: Optional[str] = None,
        user_remark: Optional[str] = None,
    ):
        """
        Initialize journal entry line with validation.
        
        Args:
            account: Account this line affects
            debit: Debit amount (use Money.zero() if none)
            credit: Credit amount (use Money.zero() if none)
            cost_center: Optional cost center reference
            reference_number: Optional reference (cheque number, etc.)
            user_remark: Optional line-specific note
            
        Raises:
            ValueError: If validation fails
        """
        # Validate account
        if not isinstance(account, Account):
            raise ValueError(f"account must be Account instance, got {type(account)}")
        
        # Validate amounts
        if not isinstance(debit, Money):
            raise ValueError(f"debit must be Money instance, got {type(debit)}")
        if not isinstance(credit, Money):
            raise ValueError(f"credit must be Money instance, got {type(credit)}")
        
        # Check currency consistency
        if debit.currency != credit.currency:
            raise ValueError(
                f"Debit currency ({debit.currency}) must match credit currency ({credit.currency})"
            )
        
        # Validate amounts are non-negative
        if debit.is_negative():
            raise ValueError(f"Debit amount cannot be negative: {debit}")
        if credit.is_negative():
            raise ValueError(f"Credit amount cannot be negative: {credit}")
        
        # Validate not both debit and credit (line should affect one side only)
        if not debit.is_zero() and not credit.is_zero():
            raise ValueError(
                f"Line cannot have both debit ({debit}) and credit ({credit}). "
                f"Use separate lines or net the amounts."
            )
        
        # At least one must be non-zero
        if debit.is_zero() and credit.is_zero():
            raise ValueError("Line must have either debit or credit amount (both are zero)")
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'account', account)
        object.__setattr__(self, 'debit', debit)
        object.__setattr__(self, 'credit', credit)
        object.__setattr__(self, 'cost_center', cost_center)
        object.__setattr__(self, 'reference_number', reference_number)
        object.__setattr__(self, 'user_remark', user_remark)
    
    def __str__(self) -> str:
        """Human-readable format"""
        if not self.debit.is_zero():
            return f"Dr {self.account.name} {self.debit}"
        else:
            return f"Cr {self.account.name} {self.credit}"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"JournalEntryLine({self.account.name}, debit={self.debit}, credit={self.credit})"
    
    @property
    def amount(self) -> Money:
        """
        Get the non-zero amount (debit or credit).
        
        Returns:
            The debit amount if debit, credit amount if credit
        """
        return self.debit if not self.debit.is_zero() else self.credit
    
    @property
    def is_debit(self) -> bool:
        """Check if this is a debit line"""
        return not self.debit.is_zero()
    
    @property
    def is_credit(self) -> bool:
        """Check if this is a credit line"""
        return not self.credit.is_zero()
    
    @property
    def currency(self) -> str:
        """Get currency of this line"""
        return self.debit.currency
    
    def validates_against_account_type(self) -> bool:
        """
        Check if debit/credit makes sense for account type.
        
        This is informational - ERPNext allows any combination,
        but it helps catch logical errors.
        
        Returns:
            True if direction matches account's normal balance
        """
        if self.is_debit:
            return self.account.is_debit_positive()
        else:
            return not self.account.is_debit_positive()
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Journal Entry Account row format.
        
        Returns:
            Dict suitable for accounts child table in Journal Entry
        """
        payload = {
            "account": self.account.name,
            "debit_in_account_currency": self.debit.to_erpnext_format(),
            "credit_in_account_currency": self.credit.to_erpnext_format(),
        }
        
        if self.cost_center:
            payload["cost_center"] = self.cost_center
        
        if self.reference_number:
            payload["reference_number"] = self.reference_number
        
        if self.user_remark:
            payload["user_remark"] = self.user_remark
        
        return payload
    
    @classmethod
    def debit(
        cls,
        account: Account,
        amount: Money,
        **kwargs
    ) -> 'JournalEntryLine':
        """
        Convenience constructor for debit line.
        
        Args:
            account: Account to debit
            amount: Debit amount
            **kwargs: Optional fields (cost_center, reference_number, user_remark)
            
        Returns:
            JournalEntryLine with debit
            
        Example:
            >>> cash = Account("Cash - WC", AccountType.CASH)
            >>> line = JournalEntryLine.debit(cash, Money(1000, "KES"))
        """
        return cls(
            account=account,
            debit=amount,
            credit=Money.zero(amount.currency),
            **kwargs
        )
    
    @classmethod
    def credit(
        cls,
        account: Account,
        amount: Money,
        **kwargs
    ) -> 'JournalEntryLine':
        """
        Convenience constructor for credit line.
        
        Args:
            account: Account to credit
            amount: Credit amount
            **kwargs: Optional fields (cost_center, reference_number, user_remark)
            
        Returns:
            JournalEntryLine with credit
            
        Example:
            >>> revenue = Account("Sales - WC", AccountType.INCOME)
            >>> line = JournalEntryLine.credit(revenue, Money(1000, "KES"))
        """
        return cls(
            account=account,
            debit=Money.zero(amount.currency),
            credit=amount,
            **kwargs
        )
