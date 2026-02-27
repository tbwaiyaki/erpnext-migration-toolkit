"""
Room Booking domain model for wellness centre B&B.

Links room bookings to financial documents.
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
class RoomBooking:
    """
    Room booking for B&B accommodation.
    
    Can be standalone or linked to an event.
    
    Examples:
        >>> booking = RoomBooking(
        ...     room_name="Master Bedroom",
        ...     guest_name="Jane Doe",
        ...     check_in=date(2024, 6, 15),
        ...     check_out=date(2024, 6, 17),
        ...     nightly_rate=Money(8000, "KES")
        ... )
        >>> 
        >>> booking.nights
        2
        >>> booking.total_amount
        Money(16000.00, 'KES')
        >>> 
        >>> invoice = booking.create_invoice()
    """
    
    room_name: str
    guest_name: str
    check_in: date
    check_out: date
    nightly_rate: Money
    booking_type: str = "Standalone"  # "Standalone" or "Event-linked"
    event_name: Optional[str] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate booking"""
        if not self.room_name.strip():
            raise ValueError("Room name cannot be empty")
        
        if not self.guest_name.strip():
            raise ValueError("Guest name cannot be empty")
        
        if self.check_out <= self.check_in:
            raise ValueError(f"Check-out ({self.check_out}) must be after check-in ({self.check_in})")
        
        if not self.nightly_rate.is_positive():
            raise ValueError(f"Nightly rate must be positive: {self.nightly_rate}")
    
    def __str__(self) -> str:
        return f"{self.room_name}: {self.guest_name} ({self.check_in} to {self.check_out})"
    
    @property
    def nights(self) -> int:
        """Calculate number of nights"""
        return (self.check_out - self.check_in).days
    
    @property
    def total_amount(self) -> Money:
        """Calculate total (nights × rate)"""
        return self.nightly_rate * self.nights
    
    def create_invoice(
        self,
        apply_vat: bool = True,
        invoice_date: Optional[date] = None
    ) -> SalesInvoice:
        """
        Generate Sales Invoice for this room booking.
        
        Args:
            apply_vat: Whether to apply 16% VAT (default: True)
            invoice_date: Invoice date (default: check_in date)
            
        Returns:
            SalesInvoice with room accommodation line item
        """
        # Build description
        description = f"Room Accommodation - {self.room_name}"
        if self.event_name:
            description += f" ({self.event_name})"
        
        # Create line item
        item = InvoiceItem(
            description=description,
            quantity=self.nights,
            rate=self.nightly_rate,
            item_code="Room Accommodation",
            uom="Night"
        )
        
        # Build taxes
        taxes = []
        if apply_vat:
            vat = InvoiceTax(
                tax_rate=TaxRate(Decimal('0.16'), "VAT @ 16%"),
                account=Account("VAT - WC", AccountType.LIABILITY)
            )
            taxes.append(vat)
        
        # Create invoice
        posting_date = invoice_date or self.check_in
        remarks = f"{self.nights} night(s) - {self.check_in} to {self.check_out}"
        
        invoice = SalesInvoice(
            customer=self.guest_name,
            posting_date=posting_date,
            items=[item],
            taxes=taxes,
            remarks=remarks
        )
        
        return invoice
    
    @classmethod
    def from_csv_row(cls, row: dict) -> 'RoomBooking':
        """
        Create RoomBooking from CSV row (room_bookings.csv).
        
        Args:
            row: Dict from CSV with keys: room_id, guest_name,
                 check_in_date, check_out_date, nightly_rate, etc.
                 
        Returns:
            RoomBooking instance
        """
        nightly_rate = Money(row['nightly_rate'], "KES")
        
        return cls(
            room_name=row.get('room_name', f"Room #{row.get('room_id')}"),
            guest_name=row.get('guest_name', 'Guest'),
            check_in=date.fromisoformat(row['check_in_date']),
            check_out=date.fromisoformat(row['check_out_date']),
            nightly_rate=nightly_rate,
            booking_type=row.get('booking_type', 'Standalone'),
            event_name=row.get('event_name'),
            notes=row.get('notes'),
        )
