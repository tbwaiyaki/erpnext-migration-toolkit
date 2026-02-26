"""
Money type with currency validation and ERPNext-compatible formatting.

The Money class represents monetary amounts with proper rounding, validation,
and conversion for ERPNext's decimal field expectations.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """
    Immutable monetary amount with currency.
    
    ERPNext stores currency amounts as decimals with 2-9 decimal places
    depending on currency precision settings. This class defaults to 2
    decimal places (standard for most currencies) but allows configuration.
    
    Examples:
        >>> m = Money(100.50, "USD")
        >>> m.amount
        Decimal('100.50')
        
        >>> m = Money("99.999", "KES")  # Rounds to 2 decimals
        >>> m.amount
        Decimal('100.00')
        
        >>> m = Money(0, "EUR")
        >>> m.is_zero()
        True
    """
    
    amount: Decimal
    currency: str
    precision: int = 2
    
    def __init__(
        self, 
        amount: Union[int, float, str, Decimal], 
        currency: str,
        precision: int = 2
    ):
        """
        Initialize Money with validation and rounding.
        
        Args:
            amount: Monetary amount (converted to Decimal)
            currency: ISO 4217 currency code (e.g., "KES", "USD")
            precision: Number of decimal places (default: 2)
            
        Raises:
            ValueError: If amount cannot be converted or currency invalid
        """
        # Validate and convert amount
        try:
            decimal_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid amount: {amount}") from e
        
        # Round to specified precision
        quantizer = Decimal('0.1') ** precision
        rounded_amount = decimal_amount.quantize(quantizer, rounding=ROUND_HALF_UP)
        
        # Validate currency code
        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError(f"Invalid currency code: {currency}")
        
        if precision < 0 or precision > 9:
            raise ValueError(f"Precision must be 0-9, got {precision}")
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'amount', rounded_amount)
        object.__setattr__(self, 'currency', currency.upper())
        object.__setattr__(self, 'precision', precision)
    
    def __str__(self) -> str:
        """Human-readable format: KES 100.00"""
        return f"{self.currency} {self.amount:,.{self.precision}f}"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"Money({self.amount}, '{self.currency}')"
    
    def __eq__(self, other) -> bool:
        """Compare money amounts with same currency"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare {self.currency} with {other.currency}")
        return self.amount == other.amount
    
    def __lt__(self, other) -> bool:
        """Less than comparison"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare {self.currency} with {other.currency}")
        return self.amount < other.amount
    
    def __le__(self, other) -> bool:
        """Less than or equal comparison"""
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        """Greater than comparison"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare {self.currency} with {other.currency}")
        return self.amount > other.amount
    
    def __ge__(self, other) -> bool:
        """Greater than or equal comparison"""
        return self == other or self > other
    
    def __add__(self, other):
        """Add two Money amounts"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(
            self.amount + other.amount, 
            self.currency,
            max(self.precision, other.precision)
        )
    
    def __sub__(self, other):
        """Subtract two Money amounts"""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {other.currency} from {self.currency}")
        return Money(
            self.amount - other.amount,
            self.currency,
            max(self.precision, other.precision)
        )
    
    def __mul__(self, multiplier: Union[int, float, Decimal]):
        """Multiply money by a number"""
        if not isinstance(multiplier, (int, float, Decimal)):
            return NotImplemented
        return Money(self.amount * Decimal(str(multiplier)), self.currency, self.precision)
    
    def __truediv__(self, divisor: Union[int, float, Decimal]):
        """Divide money by a number"""
        if not isinstance(divisor, (int, float, Decimal)):
            return NotImplemented
        if divisor == 0:
            raise ZeroDivisionError("Cannot divide money by zero")
        return Money(self.amount / Decimal(str(divisor)), self.currency, self.precision)
    
    def __abs__(self):
        """Absolute value"""
        return Money(abs(self.amount), self.currency, self.precision)
    
    def __neg__(self):
        """Negate amount"""
        return Money(-self.amount, self.currency, self.precision)
    
    def is_zero(self) -> bool:
        """Check if amount is exactly zero"""
        return self.amount == Decimal('0')
    
    def is_positive(self) -> bool:
        """Check if amount is positive (> 0)"""
        return self.amount > Decimal('0')
    
    def is_negative(self) -> bool:
        """Check if amount is negative (< 0)"""
        return self.amount < Decimal('0')
    
    def to_float(self) -> float:
        """
        Convert to float (use with caution - precision loss possible).
        
        Note: Prefer using .amount (Decimal) for calculations.
        Float conversion is mainly for display or legacy API compatibility.
        """
        return float(self.amount)
    
    def to_erpnext_format(self) -> float:
        """
        Convert to ERPNext API format.
        
        ERPNext REST API accepts numeric fields as either int or float.
        This returns a float rounded to the Money's precision.
        
        Returns:
            Float value suitable for ERPNext API submission
        """
        return round(float(self.amount), self.precision)
    
    @classmethod
    def zero(cls, currency: str) -> 'Money':
        """Create zero money amount"""
        return cls(0, currency)
    
    @classmethod
    def from_erpnext(cls, value: Union[int, float, None], currency: str) -> 'Money':
        """
        Create Money from ERPNext API response.
        
        ERPNext may return None for unset currency fields.
        This helper treats None as zero.
        
        Args:
            value: Numeric value from ERPNext (may be None)
            currency: Currency code
            
        Returns:
            Money instance
        """
        if value is None:
            return cls.zero(currency)
        return cls(value, currency)


# Common currency precision settings
CURRENCY_PRECISION = {
    'KES': 2,  # Kenyan Shilling
    'USD': 2,  # US Dollar
    'EUR': 2,  # Euro
    'GBP': 2,  # British Pound
    'JPY': 0,  # Japanese Yen (no decimals)
    'BTC': 8,  # Bitcoin (high precision)
}


def get_currency_precision(currency: str) -> int:
    """
    Get standard decimal precision for currency.
    
    Returns:
        Number of decimal places (default: 2)
    """
    return CURRENCY_PRECISION.get(currency.upper(), 2)
