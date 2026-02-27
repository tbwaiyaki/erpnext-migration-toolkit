"""
Purchase Invoice for supplier billing.

Represents supplier invoices (bills) for goods/services received.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from core.money import Money
from core.fiscal_period import FiscalPeriod
from documents.invoice_item import InvoiceItem
from documents.invoice_tax import InvoiceTax


@dataclass
class PurchaseInvoice:
    """
    Complete purchase invoice (supplier bill) with automatic calculations.
    
    Similar to SalesInvoice but for purchases from suppliers.
    
    Examples:
        >>> # Supplier bill
        >>> items = [
        ...     InvoiceItem("Inventory Items", 50, Money(100, "KES")),
        ...     InvoiceItem("Animal Feed", 10, Money(250, "KES"))
        ... ]
        >>> 
        >>> vat = InvoiceTax(
        ...     TaxRate(Decimal('0.16'), "VAT"),
        ...     Account("Input VAT - WC", AccountType.ASSET)  # VAT receivable
        ... )
        >>> 
        >>> invoice = PurchaseInvoice(
        ...     supplier="Acme Supplies Ltd",
        ...     posting_date=date(2024, 3, 15),
        ...     items=items,
        ...     taxes=[vat]
        ... )
        >>> 
        >>> invoice.subtotal
        Money(7500.00, 'KES')
        >>> invoice.grand_total
        Money(8700.00, 'KES')
    """
    
    supplier: str
    posting_date: date
    items: list[InvoiceItem]
    taxes: list[InvoiceTax] = field(default_factory=list)
    due_date: Optional[date] = None
    supplier_name: Optional[str] = None
    bill_number: Optional[str] = None  # Supplier's invoice number
    remarks: Optional[str] = None
    
    def __post_init__(self):
        """Validate invoice after initialization"""
        # Validate supplier
        if not self.supplier or not self.supplier.strip():
            raise ValueError("Supplier cannot be empty")
        
        # Validate posting date
        if not isinstance(self.posting_date, date):
            raise ValueError(f"posting_date must be date object, got {type(self.posting_date)}")
        
        # Validate items
        if not self.items:
            raise ValueError("Purchase invoice must have at least one item")
        
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
        
        # Set due date if not provided
        if self.due_date is None:
            object.__setattr__(self, 'due_date', self.posting_date + timedelta(days=30))
        
        # Set supplier_name if not provided
        if self.supplier_name is None:
            object.__setattr__(self, 'supplier_name', self.supplier)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return (
            f"Purchase Invoice: {self.supplier}\n"
            f"Date: {self.posting_date}, Items: {len(self.items)}, "
            f"Total: {self.grand_total}"
        )
    
    @property
    def currency(self) -> str:
        """Get currency used in this invoice"""
        return self.items[0].currency if self.items else "USD"
    
    @property
    def subtotal(self) -> Money:
        """Calculate subtotal (sum of all items before tax)"""
        zero = Money.zero(self.currency)
        return sum((item.amount for item in self.items), zero)
    
    @property
    def total_tax(self) -> Money:
        """Calculate total tax amount"""
        zero = Money.zero(self.currency)
        return sum(
            (tax.calculate_tax(self.subtotal) for tax in self.taxes),
            zero
        )
    
    @property
    def grand_total(self) -> Money:
        """Calculate grand total (subtotal + taxes)"""
        return self.subtotal + self.total_tax
    
    @property
    def outstanding_amount(self) -> Money:
        """Get outstanding amount (unpaid balance)"""
        return self.grand_total
    
    def validate_fiscal_period(self, fiscal_period: FiscalPeriod) -> bool:
        """Check if posting date falls within fiscal period"""
        if not fiscal_period.contains(self.posting_date):
            raise ValueError(
                f"Posting date {self.posting_date} is outside fiscal period "
                f"{fiscal_period.name}"
            )
        return True
    
    def get_tax_details(self) -> list[tuple[InvoiceTax, Money]]:
        """Get tax breakdown"""
        return [
            (tax, tax.calculate_tax(self.subtotal))
            for tax in self.taxes
        ]
    
    def to_erpnext_format(self) -> dict:
        """Convert to ERPNext Purchase Invoice format"""
        payload = {
            "doctype": "Purchase Invoice",
            "supplier": self.supplier,
            "supplier_name": self.supplier_name,
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
        if self.bill_number:
            payload["bill_no"] = self.bill_number
        
        if self.remarks:
            payload["remarks"] = self.remarks
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'PurchaseInvoice':
        """Create PurchaseInvoice from ERPNext document"""
        currency = doc.get("currency", "KES")
        
        items = [
            InvoiceItem.from_erpnext(item_row, currency)
            for item_row in doc.get("items", [])
        ]
        
        taxes = [
            InvoiceTax.from_erpnext(tax_row)
            for tax_row in doc.get("taxes", [])
        ]
        
        return cls(
            supplier=doc["supplier"],
            posting_date=date.fromisoformat(doc["posting_date"]),
            items=items,
            taxes=taxes,
            due_date=date.fromisoformat(doc["due_date"]) if doc.get("due_date") else None,
            supplier_name=doc.get("supplier_name"),
            bill_number=doc.get("bill_no"),
            remarks=doc.get("remarks"),
        )
