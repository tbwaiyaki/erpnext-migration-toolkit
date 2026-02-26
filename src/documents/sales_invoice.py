"""
Sales Invoice for customer billing.

Represents a complete sales invoice with items, taxes, and totals.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from core.money import Money
from core.fiscal_period import FiscalPeriod
from documents.invoice_item import InvoiceItem
from documents.invoice_tax import InvoiceTax


@dataclass
class SalesInvoice:
    """
    Complete sales invoice with automatic total calculations.
    
    Calculates subtotal, taxes, and grand total automatically from items.
    
    Examples:
        >>> # Simple invoice
        >>> items = [
        ...     InvoiceItem("Event Venue Hire", 1, Money(15000, "KES")),
        ...     InvoiceItem("Room Night", 2, Money(7000, "KES"))
        ... ]
        >>> 
        >>> vat = InvoiceTax(
        ...     TaxRate(Decimal('0.16'), "VAT"),
        ...     Account("VAT - WC", AccountType.LIABILITY)
        ... )
        >>> 
        >>> invoice = SalesInvoice(
        ...     customer="John Doe",
        ...     posting_date=date(2024, 3, 15),
        ...     items=items,
        ...     taxes=[vat]
        ... )
        >>> 
        >>> invoice.subtotal
        Money(29000.00, 'KES')
        >>> invoice.grand_total
        Money(33640.00, 'KES')
    """
    
    customer: str
    posting_date: date
    items: list[InvoiceItem]
    taxes: list[InvoiceTax] = field(default_factory=list)
    due_date: Optional[date] = None
    customer_name: Optional[str] = None  # For display
    invoice_number: Optional[str] = None
    remarks: Optional[str] = None
    
    def __post_init__(self):
        """Validate invoice after initialization"""
        # Validate customer
        if not self.customer or not self.customer.strip():
            raise ValueError("Customer cannot be empty")
        
        # Validate posting date
        if not isinstance(self.posting_date, date):
            raise ValueError(f"posting_date must be date object, got {type(self.posting_date)}")
        
        # Validate items
        if not self.items:
            raise ValueError("Invoice must have at least one item")
        
        for i, item in enumerate(self.items):
            if not isinstance(item, InvoiceItem):
                raise ValueError(f"Item {i} is not InvoiceItem instance: {type(item)}")
        
        # Check currency consistency
        currencies = {item.currency for item in self.items}
        if len(currencies) > 1:
            raise ValueError(f"All items must use same currency, found: {currencies}")
        
        # Validate taxes
        for i, tax in enumerate(self.taxes):
            if not isinstance(tax, InvoiceTax):
                raise ValueError(f"Tax {i} is not InvoiceTax instance: {type(tax)}")
        
        # Set due date if not provided (default: 15 days from posting)
        if self.due_date is None:
            object.__setattr__(self, 'due_date', self.posting_date + timedelta(days=15))
        
        # Set customer_name if not provided
        if self.customer_name is None:
            object.__setattr__(self, 'customer_name', self.customer)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return (
            f"Sales Invoice: {self.customer}\n"
            f"Date: {self.posting_date}, Items: {len(self.items)}, "
            f"Total: {self.grand_total}"
        )
    
    @property
    def currency(self) -> str:
        """Get currency used in this invoice"""
        return self.items[0].currency if self.items else "USD"
    
    @property
    def subtotal(self) -> Money:
        """
        Calculate subtotal (sum of all item amounts before tax).
        
        Returns:
            Subtotal as Money
        """
        zero = Money.zero(self.currency)
        return sum((item.amount for item in self.items), zero)
    
    @property
    def total_tax(self) -> Money:
        """
        Calculate total tax amount.
        
        Returns:
            Total of all taxes
        """
        zero = Money.zero(self.currency)
        return sum(
            (tax.calculate_tax(self.subtotal) for tax in self.taxes),
            zero
        )
    
    @property
    def grand_total(self) -> Money:
        """
        Calculate grand total (subtotal + taxes).
        
        Returns:
            Grand total as Money
        """
        return self.subtotal + self.total_tax
    
    @property
    def outstanding_amount(self) -> Money:
        """
        Get outstanding amount (unpaid balance).
        
        Note: In this basic version, entire invoice is outstanding.
        Full implementation would track payments.
        
        Returns:
            Outstanding amount (equals grand_total for new invoice)
        """
        return self.grand_total
    
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
    
    def get_tax_details(self) -> list[tuple[InvoiceTax, Money]]:
        """
        Get tax breakdown (tax definition + calculated amount).
        
        Returns:
            List of (InvoiceTax, Money amount) tuples
        """
        return [
            (tax, tax.calculate_tax(self.subtotal))
            for tax in self.taxes
        ]
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Sales Invoice format.
        
        Returns:
            Dict suitable for ERPNext API submission
        """
        payload = {
            "doctype": "Sales Invoice",
            "customer": self.customer,
            "customer_name": self.customer_name,
            "posting_date": self.posting_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "items": [item.to_erpnext_format() for item in self.items],
        }
        
        # Add taxes if present
        if self.taxes:
            tax_details = self.get_tax_details()
            payload["taxes"] = [
                tax.to_erpnext_format(amount)
                for tax, amount in tax_details
            ]
        
        # Add optional fields
        if self.invoice_number:
            payload["name"] = self.invoice_number
        
        if self.remarks:
            payload["remarks"] = self.remarks
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'SalesInvoice':
        """
        Create SalesInvoice from ERPNext document.
        
        Args:
            doc: ERPNext Sales Invoice document dict
            
        Returns:
            SalesInvoice instance
        """
        # Determine currency (from first item or default to KES)
        currency = "KES"
        if doc.get("items") and len(doc["items"]) > 0:
            # Would extract from item in production
            currency = doc.get("currency", "KES")
        
        # Parse items
        items = [
            InvoiceItem.from_erpnext(item_row, currency)
            for item_row in doc.get("items", [])
        ]
        
        # Parse taxes
        taxes = [
            InvoiceTax.from_erpnext(tax_row)
            for tax_row in doc.get("taxes", [])
        ]
        
        return cls(
            customer=doc["customer"],
            posting_date=date.fromisoformat(doc["posting_date"]),
            items=items,
            taxes=taxes,
            due_date=date.fromisoformat(doc["due_date"]) if doc.get("due_date") else None,
            customer_name=doc.get("customer_name"),
            invoice_number=doc.get("name"),
            remarks=doc.get("remarks"),
        )
