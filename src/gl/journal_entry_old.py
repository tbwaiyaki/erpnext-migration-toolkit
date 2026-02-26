"""
Journal Entry for GL transactions.

Represents a complete double-entry bookkeeping transaction with
automatic debit/credit balance validation.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from decimal import Decimal

from ..core.money import Money
from ..core.fiscal_period import FiscalPeriod
from .journal_entry_line import JournalEntryLine


@dataclass
class JournalEntry:
    """
    Complete journal entry with balanced debit/credit lines.
    
    Enforces double-entry bookkeeping rule: debits must equal credits.
    
    Examples:
        >>> # Simple cash receipt
        >>> cash = Account("Cash - WC", AccountType.CASH)
        >>> revenue = Account("Sales - WC", AccountType.INCOME)
        >>> 
        >>> entry = JournalEntry(
        ...     posting_date=date(2024, 3, 15),
        ...     lines=[
        ...         JournalEntryLine.debit(cash, Money(15000, "KES")),
        ...         JournalEntryLine.credit(revenue, Money(15000, "KES"))
        ...     ],
        ...     user_remark="Event deposit received"
        ... )
        >>> 
        >>> entry.validate()  # ← Raises if unbalanced
        >>> entry.is_balanced()
        True
    """
    
    posting_date: date
    lines: list[JournalEntryLine]
    user_remark: Optional[str] = None
    voucher_type: str = "Journal Entry"
    cheque_number: Optional[str] = None
    cheque_date: Optional[date] = None
    
    def __post_init__(self):
        """Validate entry after initialization"""
        # Validate posting date
        if not isinstance(self.posting_date, date):
            raise ValueError(f"posting_date must be date object, got {type(self.posting_date)}")
        
        # Validate lines
        if not self.lines:
            raise ValueError("Journal entry must have at least one line")
        
        if len(self.lines) < 2:
            raise ValueError(
                f"Journal entry must have at least 2 lines (double-entry), got {len(self.lines)}"
            )
        
        # Validate all lines are JournalEntryLine instances
        for i, line in enumerate(self.lines):
            if not isinstance(line, JournalEntryLine):
                raise ValueError(f"Line {i} is not JournalEntryLine instance: {type(line)}")
        
        # Check currency consistency
        currencies = {line.currency for line in self.lines}
        if len(currencies) > 1:
            raise ValueError(f"All lines must use same currency, found: {currencies}")
    
    def __str__(self) -> str:
        """Human-readable format"""
        lines_str = "\n  ".join(str(line) for line in self.lines)
        return f"JE {self.posting_date} ({len(self.lines)} lines):\n  {lines_str}"
    
    @property
    def currency(self) -> str:
        """Get currency used in this entry"""
        return self.lines[0].currency if self.lines else "USD"
    
    @property
    def total_debit(self) -> Money:
        """Calculate total debits"""
        zero = Money.zero(self.currency)
        return sum((line.debit for line in self.lines), zero)
    
    @property
    def total_credit(self) -> Money:
        """Calculate total credits"""
        zero = Money.zero(self.currency)
        return sum((line.credit for line in self.lines), zero)
    
    @property
    def difference(self) -> Money:
        """
        Calculate difference between debits and credits.
        
        Returns:
            Difference amount (should be zero for balanced entry)
        """
        return self.total_debit - self.total_credit
    
    def is_balanced(self) -> bool:
        """
        Check if entry is balanced (debits = credits).
        
        Returns:
            True if balanced, False otherwise
        """
        return self.difference.is_zero()
    
    def validate(self) -> None:
        """
        Validate journal entry.
        
        Raises:
            ValueError: If entry is invalid (unbalanced, etc.)
        """
        # Check balance
        if not self.is_balanced():
            raise ValueError(
                f"Journal entry is not balanced:\n"
                f"  Total debits:  {self.total_debit}\n"
                f"  Total credits: {self.total_credit}\n"
                f"  Difference:    {self.difference}"
            )
        
        # Validate each line's account type logic (warning only)
        for i, line in enumerate(self.lines):
            if not line.validates_against_account_type():
                # This is informational - ERPNext allows it, but might be error
                account_nature = "debit" if line.account.is_debit_positive() else "credit"
                line_nature = "debit" if line.is_debit else "credit"
                # Could log warning here in production
                pass
    
    def validate_fiscal_period(self, fiscal_period: FiscalPeriod) -> bool:
        """
        Check if posting date falls within fiscal period.
        
        Args:
            fiscal_period: Fiscal period to validate against
            
        Returns:
            True if date is valid for period
            
        Raises:
            ValueError: If posting date outside fiscal period
        """
        if not fiscal_period.contains(self.posting_date):
            raise ValueError(
                f"Posting date {self.posting_date} is outside fiscal period "
                f"{fiscal_period.name} ({fiscal_period.start_date} to {fiscal_period.end_date})"
            )
        return True
    
    def get_debit_lines(self) -> list[JournalEntryLine]:
        """Get all debit lines"""
        return [line for line in self.lines if line.is_debit]
    
    def get_credit_lines(self) -> list[JournalEntryLine]:
        """Get all credit lines"""
        return [line for line in self.lines if line.is_credit]
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Journal Entry format.
        
        Returns:
            Dict suitable for ERPNext API submission
        """
        payload = {
            "doctype": "Journal Entry",
            "posting_date": self.posting_date.isoformat(),
            "voucher_type": self.voucher_type,
            "accounts": [line.to_erpnext_format() for line in self.lines],
        }
        
        if self.user_remark:
            payload["user_remark"] = self.user_remark
        
        if self.cheque_number:
            payload["cheque_no"] = self.cheque_number
        
        if self.cheque_date:
            payload["cheque_date"] = self.cheque_date.isoformat()
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'JournalEntry':
        """
        Create JournalEntry from ERPNext document.
        
        Args:
            doc: ERPNext Journal Entry document dict
            
        Returns:
            JournalEntry instance
        """
        from ..core.account import Account, AccountType
        
        # Parse lines
        lines = []
        for acc_row in doc.get("accounts", []):
            # Determine account (simplified - would need account lookup in real implementation)
            account_name = acc_row.get("account")
            # For now, create Account with generic type
            # In production, would query ERPNext for actual account type
            account = Account(account_name, AccountType.ASSET)  # Placeholder
            
            debit = Money.from_erpnext(acc_row.get("debit_in_account_currency"), "KES")
            credit = Money.from_erpnext(acc_row.get("credit_in_account_currency"), "KES")
            
            line = JournalEntryLine(
                account=account,
                debit=debit,
                credit=credit,
                cost_center=acc_row.get("cost_center"),
                reference_number=acc_row.get("reference_number"),
                user_remark=acc_row.get("user_remark"),
            )
            lines.append(line)
        
        return cls(
            posting_date=date.fromisoformat(doc["posting_date"]),
            lines=lines,
            user_remark=doc.get("user_remark"),
            voucher_type=doc.get("voucher_type", "Journal Entry"),
            cheque_number=doc.get("cheque_no"),
            cheque_date=date.fromisoformat(doc["cheque_date"]) if doc.get("cheque_date") else None,
        )


def create_simple_entry(
    posting_date: date,
    debit_account: 'Account',
    credit_account: 'Account',
    amount: Money,
    remark: Optional[str] = None,
) -> JournalEntry:
    """
    Helper to create simple two-line journal entry.
    
    Args:
        posting_date: Transaction date
        debit_account: Account to debit
        credit_account: Account to credit
        amount: Transaction amount
        remark: Optional description
        
    Returns:
        Balanced JournalEntry
        
    Example:
        >>> cash = Account("Cash - WC", AccountType.CASH)
        >>> revenue = Account("Sales - WC", AccountType.INCOME)
        >>> entry = create_simple_entry(
        ...     date(2024, 3, 15),
        ...     cash,
        ...     revenue,
        ...     Money(15000, "KES"),
        ...     "Event deposit"
        ... )
    """
    return JournalEntry(
        posting_date=posting_date,
        lines=[
            JournalEntryLine.debit(debit_account, amount),
            JournalEntryLine.credit(credit_account, amount),
        ],
        user_remark=remark,
    )
