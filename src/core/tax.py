"""
Tax type for tax rate calculations with proper rounding.

Handles tax calculations consistent with ERPNext's tax rounding behavior
and supports various tax types (VAT, sales tax, withholding tax, etc.).
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from enum import Enum

from .money import Money


class TaxType(Enum):
    """
    Common tax types for business transactions.
    
    These don't map directly to ERPNext fields but help
    document the purpose of each tax in migrations.
    """
    VAT = "VAT"                           # Value Added Tax
    SALES_TAX = "Sales Tax"               # Sales tax
    WITHHOLDING = "Withholding Tax"       # Tax withheld at source
    EXCISE = "Excise Duty"                # Excise duty
    CUSTOMS = "Customs Duty"              # Import duties
    SERVICE_TAX = "Service Tax"           # Service-specific tax
    INCOME_TAX = "Income Tax"             # Income tax
    OTHER = "Other"                       # Other tax types


@dataclass(frozen=True)
class TaxRate:
    """
    Immutable tax rate with calculation methods.
    
    Represents a tax rate (e.g., 16% VAT in Kenya) with methods
    to calculate tax amounts from base amounts.
    
    Examples:
        >>> vat = TaxRate(Decimal('0.16'), "VAT @ 16%")
        >>> base = Money(10000, "KES")
        >>> tax_amount = vat.calculate_tax(base)
        >>> tax_amount
        Money(1600.00, 'KES')
        
        >>> total = vat.calculate_total(base)
        >>> total
        Money(11600.00, 'KES')
        
        >>> # Extract tax from gross amount
        >>> gross = Money(11600, "KES")
        >>> extracted = vat.extract_tax(gross)
        >>> extracted
        Money(1600.00, 'KES')
    """
    
    rate: Decimal
    description: str
    tax_type: TaxType = TaxType.OTHER
    account_name: Optional[str] = None
    
    def __init__(
        self,
        rate: Decimal | float | str,
        description: str,
        tax_type: TaxType = TaxType.OTHER,
        account_name: Optional[str] = None,
    ):
        """
        Initialize TaxRate with validation.
        
        Args:
            rate: Tax rate as decimal (0.16 for 16%)
            description: Human-readable description (e.g., "VAT @ 16%")
            tax_type: Type of tax (from TaxType enum)
            account_name: GL account name for this tax
            
        Raises:
            ValueError: If rate is negative or description empty
        """
        # Convert rate to Decimal
        if isinstance(rate, str):
            decimal_rate = Decimal(rate)
        elif isinstance(rate, float):
            decimal_rate = Decimal(str(rate))
        else:
            decimal_rate = rate
        
        # Validate rate
        if decimal_rate < 0:
            raise ValueError(f"Tax rate cannot be negative: {decimal_rate}")
        
        if decimal_rate > 1:
            # Common mistake: passing 16 instead of 0.16
            raise ValueError(
                f"Tax rate should be decimal (0.16 for 16%), got {decimal_rate}. "
                f"Did you mean {decimal_rate / 100}?"
            )
        
        # Validate description
        if not description or not description.strip():
            raise ValueError("Tax description cannot be empty")
        
        # Validate tax type
        if not isinstance(tax_type, TaxType):
            raise ValueError(f"tax_type must be TaxType enum, got {type(tax_type)}")
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'rate', decimal_rate)
        object.__setattr__(self, 'description', description.strip())
        object.__setattr__(self, 'tax_type', tax_type)
        object.__setattr__(self, 'account_name', account_name)
    
    @property
    def percentage(self) -> Decimal:
        """
        Get rate as percentage.
        
        Returns:
            Rate as percentage (16.00 for 16%)
            
        Example:
            >>> TaxRate(Decimal('0.16'), "VAT").percentage
            Decimal('16.00')
        """
        return (self.rate * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return f"{self.description} ({self.percentage}%)"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"TaxRate({self.rate}, '{self.description}')"
    
    def calculate_tax(self, base_amount: Money) -> Money:
        """
        Calculate tax amount from base amount.
        
        Args:
            base_amount: Amount to calculate tax on
            
        Returns:
            Tax amount in same currency
            
        Example:
            >>> vat = TaxRate(Decimal('0.16'), "VAT")
            >>> base = Money(10000, "KES")
            >>> vat.calculate_tax(base)
            Money(1600.00, 'KES')
        """
        tax_amount = base_amount * self.rate
        return tax_amount
    
    def calculate_total(self, base_amount: Money) -> Money:
        """
        Calculate total amount (base + tax).
        
        Args:
            base_amount: Amount before tax
            
        Returns:
            Total including tax
            
        Example:
            >>> vat = TaxRate(Decimal('0.16'), "VAT")
            >>> base = Money(10000, "KES")
            >>> vat.calculate_total(base)
            Money(11600.00, 'KES')
        """
        tax = self.calculate_tax(base_amount)
        return base_amount + tax
    
    def extract_tax(self, gross_amount: Money) -> Money:
        """
        Extract tax amount from gross (total) amount.
        
        Used when you have the total and need to separate tax.
        Formula: tax = gross * (rate / (1 + rate))
        
        Args:
            gross_amount: Total amount including tax
            
        Returns:
            Tax portion of the gross amount
            
        Example:
            >>> vat = TaxRate(Decimal('0.16'), "VAT")
            >>> gross = Money(11600, "KES")
            >>> vat.extract_tax(gross)
            Money(1600.00, 'KES')
        """
        # Formula: tax = gross * (rate / (1 + rate))
        divisor = Decimal('1') + self.rate
        tax_factor = self.rate / divisor
        tax_amount = gross_amount * tax_factor
        return tax_amount
    
    def extract_base(self, gross_amount: Money) -> Money:
        """
        Extract base amount from gross (total) amount.
        
        Args:
            gross_amount: Total amount including tax
            
        Returns:
            Base amount before tax
            
        Example:
            >>> vat = TaxRate(Decimal('0.16'), "VAT")
            >>> gross = Money(11600, "KES")
            >>> vat.extract_base(gross)
            Money(10000.00, 'KES')
        """
        tax = self.extract_tax(gross_amount)
        return gross_amount - tax
    
    def is_zero_rated(self) -> bool:
        """Check if this is a zero-rate tax"""
        return self.rate == Decimal('0')
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Sales Taxes and Charges format.
        
        Returns:
            Dict suitable for ERPNext tax table row
        """
        payload = {
            "charge_type": "On Net Total",
            "description": self.description,
            "rate": float(self.percentage),  # ERPNext expects percentage
        }
        
        if self.account_name:
            payload["account_head"] = self.account_name
        
        return payload
    
    @classmethod
    def zero_rated(cls, description: str = "Zero Rated") -> 'TaxRate':
        """
        Create zero-rate tax.
        
        Args:
            description: Description for zero-rated tax
            
        Returns:
            TaxRate with 0% rate
        """
        return cls(Decimal('0'), description)
    
    @classmethod
    def from_percentage(
        cls,
        percentage: Decimal | float | str,
        description: str,
        tax_type: TaxType = TaxType.OTHER,
        account_name: Optional[str] = None,
    ) -> 'TaxRate':
        """
        Create TaxRate from percentage value.
        
        Convenience method for cases where you have percentage
        instead of decimal rate.
        
        Args:
            percentage: Tax rate as percentage (16 for 16%)
            description: Tax description
            tax_type: Type of tax
            account_name: GL account for tax
            
        Returns:
            TaxRate instance
            
        Example:
            >>> vat = TaxRate.from_percentage(16, "VAT @ 16%")
            >>> vat.rate
            Decimal('0.16')
        """
        if isinstance(percentage, str):
            pct_decimal = Decimal(percentage)
        elif isinstance(percentage, float):
            pct_decimal = Decimal(str(percentage))
        else:
            pct_decimal = percentage
        
        # Convert percentage to rate
        rate = pct_decimal / 100
        
        return cls(rate, description, tax_type, account_name)


# Common tax rates for reuse
def create_kenya_tax_rates(company: str = "WC") -> dict[str, TaxRate]:
    """
    Create standard Kenyan tax rates.
    
    Args:
        company: Company abbreviation for account names
        
    Returns:
        Dict mapping purpose to TaxRate
    """
    return {
        "vat_standard": TaxRate(
            Decimal('0.16'),
            "VAT @ 16%",
            TaxType.VAT,
            f"VAT - {company}",
        ),
        "vat_zero": TaxRate.zero_rated("VAT @ 0% (Zero Rated)"),
        "withholding_resident": TaxRate.from_percentage(
            5,
            "Withholding Tax @ 5% (Resident)",
            TaxType.WITHHOLDING,
            f"TDS Payable - {company}",
        ),
        "withholding_professional": TaxRate.from_percentage(
            5,
            "Withholding Tax @ 5% (Professional Services)",
            TaxType.WITHHOLDING,
            f"TDS Payable - {company}",
        ),
    }


def calculate_tax_breakdown(
    base_amount: Money,
    tax_rates: list[TaxRate],
) -> dict:
    """
    Calculate tax breakdown for multiple tax rates.
    
    Args:
        base_amount: Amount before taxes
        tax_rates: List of applicable tax rates
        
    Returns:
        Dict with base, taxes, and total
        
    Example:
        >>> base = Money(10000, "KES")
        >>> vat = TaxRate(Decimal('0.16'), "VAT")
        >>> breakdown = calculate_tax_breakdown(base, [vat])
        >>> breakdown['total']
        Money(11600.00, 'KES')
    """
    taxes = {}
    total_tax = Money.zero(base_amount.currency)
    
    for tax_rate in tax_rates:
        tax_amount = tax_rate.calculate_tax(base_amount)
        taxes[tax_rate.description] = tax_amount
        total_tax = total_tax + tax_amount
    
    return {
        "base": base_amount,
        "taxes": taxes,
        "total_tax": total_tax,
        "total": base_amount + total_tax,
    }
