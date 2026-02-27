"""
Egg Sale domain model for poultry farm operations.

Links egg sales to financial documents.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional
from decimal import Decimal

from core.money import Money
from core.account import Account, AccountType
from core.tax import TaxRate
from documents.sales_invoice import SalesInvoice
from documents.invoice_item import InvoiceItem
from documents.invoice_tax import InvoiceTax


@dataclass
class EggSale:
    """
    Egg sale from poultry farm.
    
    Tracks tray sales with pricing.
    
    Examples:
        >>> sale = EggSale(
        ...     sale_date=date(2024, 5, 10),
        ...     customer_name="Local Market",
        ...     trays_sold=5,
        ...     price_per_tray=Money(350, "KES")
        ... )
        >>> 
        >>> sale.total_amount
        Money(1750.00, 'KES')
        >>> 
        >>> invoice = sale.create_invoice()
    """
    
    sale_date: date
    customer_name: str
    trays_sold: int
    price_per_tray: Money
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate sale"""
        if not self.customer_name.strip():
            raise ValueError("Customer name cannot be empty")
        
        if self.trays_sold < 1:
            raise ValueError(f"Trays sold must be at least 1: {self.trays_sold}")
        
        if not self.price_per_tray.is_positive():
            raise ValueError(f"Price per tray must be positive: {self.price_per_tray}")
    
    def __str__(self) -> str:
        return f"{self.trays_sold} trays @ {self.price_per_tray} = {self.total_amount}"
    
    @property
    def total_amount(self) -> Money:
        """Calculate total (trays × price)"""
        return self.price_per_tray * self.trays_sold
    
    def create_invoice(
        self,
        apply_vat: bool = False,  # Farm eggs often zero-rated
        invoice_date: Optional[date] = None
    ) -> SalesInvoice:
        """
        Generate Sales Invoice for egg sale.
        
        Args:
            apply_vat: Whether to apply VAT (default: False - zero-rated)
            invoice_date: Invoice date (default: sale_date)
            
        Returns:
            SalesInvoice with egg sale line item
        """
        # Create line item
        item = InvoiceItem(
            description="Farm Eggs (Fresh)",
            quantity=self.trays_sold,
            rate=self.price_per_tray,
            item_code="Farm Eggs",
            uom="Tray"
        )
        
        # Build taxes (usually zero-rated for agricultural produce)
        taxes = []
        if apply_vat:
            vat = InvoiceTax(
                tax_rate=TaxRate(Decimal('0.16'), "VAT @ 16%"),
                account=Account("VAT - WC", AccountType.LIABILITY)
            )
            taxes.append(vat)
        else:
            # Zero-rated VAT
            zero_vat = InvoiceTax(
                tax_rate=TaxRate.zero_rated("VAT @ 0% (Zero Rated)"),
                account=Account("VAT - WC", AccountType.LIABILITY)
            )
            taxes.append(zero_vat)
        
        # Create invoice
        posting_date = invoice_date or self.sale_date
        remarks = f"Egg sale: {self.trays_sold} tray(s)"
        
        invoice = SalesInvoice(
            customer=self.customer_name,
            posting_date=posting_date,
            items=[item],
            taxes=taxes,
            remarks=remarks
        )
        
        return invoice
    
    @classmethod
    def from_csv_row(cls, row: dict) -> 'EggSale':
        """
        Create EggSale from CSV row (egg_sales.csv).
        
        Args:
            row: Dict from CSV with keys: sale_date, contact_id,
                 trays_sold, price_per_tray, total_amount, notes
                 
        Returns:
            EggSale instance
        """
        price_per_tray = Money(row['price_per_tray'], "KES")
        
        return cls(
            sale_date=date.fromisoformat(row['sale_date']),
            customer_name=row.get('customer_name', f"Customer #{row.get('contact_id')}"),
            trays_sold=int(row['trays_sold']),
            price_per_tray=price_per_tray,
            notes=row.get('notes'),
        )
