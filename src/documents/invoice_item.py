"""
Invoice Item for line items in sales/purchase invoices.

Represents a single line item with quantity, rate, and amount.
"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

from core.money import Money


@dataclass(frozen=True)
class InvoiceItem:
    """
    Immutable invoice line item.
    
    Represents a single product/service line on an invoice with
    quantity × rate = amount calculation.
    
    Examples:
        >>> # Simple item
        >>> item = InvoiceItem(
        ...     description="Event Venue Hire",
        ...     quantity=1,
        ...     rate=Money(15000, "KES")
        ... )
        >>> item.amount
        Money(15000.00, 'KES')
        
        >>> # Multiple quantities
        >>> item = InvoiceItem(
        ...     description="Room Night",
        ...     quantity=2,
        ...     rate=Money(7000, "KES")
        ... )
        >>> item.amount
        Money(14000.00, 'KES')
    """
    
    description: str
    quantity: Decimal
    rate: Money
    item_code: Optional[str] = None
    uom: str = "Nos"  # Unit of measure
    
    def __init__(
        self,
        description: str,
        quantity: Decimal | int | float,
        rate: Money,
        item_code: Optional[str] = None,
        uom: str = "Nos",
    ):
        """
        Initialize invoice item with validation.
        
        Args:
            description: Item description
            quantity: Quantity (converted to Decimal)
            rate: Unit rate as Money object
            item_code: Optional item code/SKU
            uom: Unit of measure (default: "Nos" for numbers)
            
        Raises:
            ValueError: If validation fails
        """
        # Validate description
        if not description or not description.strip():
            raise ValueError("Description cannot be empty")
        
        # Convert quantity to Decimal
        if isinstance(quantity, (int, float)):
            decimal_qty = Decimal(str(quantity))
        else:
            decimal_qty = quantity
        
        # Validate quantity
        if decimal_qty <= 0:
            raise ValueError(f"Quantity must be positive, got {decimal_qty}")
        
        # Validate rate
        if not isinstance(rate, Money):
            raise ValueError(f"Rate must be Money instance, got {type(rate)}")
        
        if rate.is_negative():
            raise ValueError(f"Rate cannot be negative: {rate}")
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'description', description.strip())
        object.__setattr__(self, 'quantity', decimal_qty)
        object.__setattr__(self, 'rate', rate)
        object.__setattr__(self, 'item_code', item_code)
        object.__setattr__(self, 'uom', uom)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return f"{self.quantity} × {self.description} @ {self.rate} = {self.amount}"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"InvoiceItem('{self.description}', qty={self.quantity}, rate={self.rate})"
    
    @property
    def amount(self) -> Money:
        """
        Calculate line amount (quantity × rate).
        
        Returns:
            Total amount for this line
        """
        return self.rate * self.quantity
    
    @property
    def currency(self) -> str:
        """Get currency of this item"""
        return self.rate.currency
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Sales/Purchase Invoice Item format.
        
        Returns:
            Dict suitable for items child table
        """
        payload = {
            "item_name": self.description,
            "description": self.description,
            "qty": float(self.quantity),
            "rate": self.rate.to_erpnext_format(),
            "amount": self.amount.to_erpnext_format(),
            "uom": self.uom,
        }
        
        if self.item_code:
            payload["item_code"] = self.item_code
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict, currency: str = "KES") -> 'InvoiceItem':
        """
        Create InvoiceItem from ERPNext document.
        
        Args:
            doc: ERPNext invoice item row dict
            currency: Currency code
            
        Returns:
            InvoiceItem instance
        """
        return cls(
            description=doc.get("item_name") or doc.get("description", ""),
            quantity=Decimal(str(doc.get("qty", 1))),
            rate=Money.from_erpnext(doc.get("rate"), currency),
            item_code=doc.get("item_code"),
            uom=doc.get("uom", "Nos"),
        )
