"""
Invoice Tax for tax lines on sales/purchase invoices.

Represents tax calculation and GL account for invoice taxes.
"""

from dataclasses import dataclass
from typing import Optional

from core.money import Money
from core.tax import TaxRate
from core.account import Account


@dataclass(frozen=True)
class InvoiceTax:
    """
    Immutable invoice tax line.
    
    Represents a tax applied to an invoice with rate and GL account.
    
    Examples:
        >>> # 16% VAT
        >>> vat_rate = TaxRate(Decimal('0.16'), "VAT @ 16%")
        >>> vat_account = Account("VAT - WC", AccountType.LIABILITY)
        >>> 
        >>> tax = InvoiceTax(
        ...     tax_rate=vat_rate,
        ...     account=vat_account
        ... )
        >>> 
        >>> # Calculate tax on amount
        >>> base = Money(15000, "KES")
        >>> tax_amount = tax.calculate_tax(base)
        >>> tax_amount
        Money(2400.00, 'KES')
    """
    
    tax_rate: TaxRate
    account: Account
    description: Optional[str] = None
    
    def __init__(
        self,
        tax_rate: TaxRate,
        account: Account,
        description: Optional[str] = None,
    ):
        """
        Initialize invoice tax with validation.
        
        Args:
            tax_rate: TaxRate instance
            account: GL account for this tax
            description: Optional description (defaults to tax_rate.description)
            
        Raises:
            ValueError: If validation fails
        """
        # Validate tax_rate
        if not isinstance(tax_rate, TaxRate):
            raise ValueError(f"tax_rate must be TaxRate instance, got {type(tax_rate)}")
        
        # Validate account
        if not isinstance(account, Account):
            raise ValueError(f"account must be Account instance, got {type(account)}")
        
        # Use tax_rate description if not provided
        final_description = description or tax_rate.description
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'tax_rate', tax_rate)
        object.__setattr__(self, 'account', account)
        object.__setattr__(self, 'description', final_description)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return f"{self.description} → {self.account.name}"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"InvoiceTax({self.tax_rate.percentage}%, {self.account.name})"
    
    def calculate_tax(self, base_amount: Money) -> Money:
        """
        Calculate tax amount for given base.
        
        Args:
            base_amount: Amount to calculate tax on
            
        Returns:
            Tax amount
        """
        return self.tax_rate.calculate_tax(base_amount)
    
    def to_erpnext_format(self, tax_amount: Money) -> dict:
        """
        Convert to ERPNext Sales/Purchase Taxes format.
        
        Args:
            tax_amount: Calculated tax amount (must be provided)
            
        Returns:
            Dict suitable for taxes child table
        """
        payload = {
            "charge_type": "On Net Total",
            "account_head": self.account.name,
            "description": self.description,
            "rate": float(self.tax_rate.percentage),
            "tax_amount": tax_amount.to_erpnext_format(),
        }
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'InvoiceTax':
        """
        Create InvoiceTax from ERPNext document.
        
        Note: This creates Account with generic type since we don't
        have full account info. In production, would query ERPNext
        for account details.
        
        Args:
            doc: ERPNext tax row dict
            
        Returns:
            InvoiceTax instance
        """
        from core.account import AccountType
        from decimal import Decimal
        
        # Extract rate percentage and convert to decimal
        rate_pct = Decimal(str(doc.get("rate", 0)))
        
        # Create tax rate from percentage
        tax_rate = TaxRate.from_percentage(
            rate_pct,
            doc.get("description", f"Tax @ {rate_pct}%")
        )
        
        # Create account (would need proper lookup in production)
        account = Account(
            doc.get("account_head", "Tax Account"),
            AccountType.LIABILITY  # Taxes are typically liabilities
        )
        
        return cls(
            tax_rate=tax_rate,
            account=account,
            description=doc.get("description"),
        )
