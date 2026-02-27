"""
Event Booking domain model for wellness centre.

Links event bookings to financial documents (invoices, payments).
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
class EventBooking:
    """
    Event booking with venue hire and optional services.
    
    Represents a complete event booking that generates invoices
    for venue hire, room accommodation, and wellness services.
    
    Examples:
        >>> booking = EventBooking(
        ...     event_name="Smith Wedding",
        ...     event_date=date(2024, 6, 15),
        ...     client_name="John Smith",
        ...     venue_hire_fee=Money(15000, "KES"),
        ...     guest_count=100
        ... )
        >>> 
        >>> # Generate invoice
        >>> invoice = booking.create_invoice()
        >>> invoice.grand_total
        Money(17400.00, 'KES')  # With 16% VAT
    """
    
    event_name: str
    event_date: date
    client_name: str
    venue_hire_fee: Money
    guest_count: int
    event_type: str = "Wedding"  # Wedding, Corporate, Wellness Retreat, etc.
    room_accommodation_fee: Optional[Money] = None
    wellness_services_fee: Optional[Money] = None
    deposit_amount: Optional[Money] = None
    agent_name: Optional[str] = None
    agent_commission_rate: Decimal = Decimal('0')
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate booking"""
        if not self.event_name.strip():
            raise ValueError("Event name cannot be empty")
        
        if not self.client_name.strip():
            raise ValueError("Client name cannot be empty")
        
        if not self.venue_hire_fee.is_positive():
            raise ValueError(f"Venue hire fee must be positive: {self.venue_hire_fee}")
        
        if self.guest_count < 1:
            raise ValueError(f"Guest count must be at least 1: {self.guest_count}")
        
        # Validate optional fees
        if self.room_accommodation_fee and self.room_accommodation_fee.is_negative():
            raise ValueError("Room accommodation fee cannot be negative")
        
        if self.wellness_services_fee and self.wellness_services_fee.is_negative():
            raise ValueError("Wellness services fee cannot be negative")
        
        if self.deposit_amount and self.deposit_amount.is_negative():
            raise ValueError("Deposit amount cannot be negative")
    
    def __str__(self) -> str:
        return f"{self.event_name} on {self.event_date} - {self.client_name}"
    
    @property
    def total_fees(self) -> Money:
        """Calculate total fees (venue + room + wellness)"""
        total = self.venue_hire_fee
        
        if self.room_accommodation_fee:
            total = total + self.room_accommodation_fee
        
        if self.wellness_services_fee:
            total = total + self.wellness_services_fee
        
        return total
    
    @property
    def agent_commission(self) -> Money:
        """Calculate agent commission if applicable"""
        if self.agent_commission_rate == 0:
            return Money.zero(self.venue_hire_fee.currency)
        
        return self.total_fees * self.agent_commission_rate
    
    @property
    def balance_due(self) -> Money:
        """Calculate balance after deposit"""
        if self.deposit_amount:
            return self.total_fees - self.deposit_amount
        return self.total_fees
    
    def create_invoice(
        self,
        apply_vat: bool = True,
        invoice_date: Optional[date] = None
    ) -> SalesInvoice:
        """
        Generate Sales Invoice for this event booking.
        
        Args:
            apply_vat: Whether to apply 16% VAT (default: True)
            invoice_date: Invoice date (default: event_date)
            
        Returns:
            SalesInvoice with line items for venue, rooms, wellness
        """
        # Build line items
        items = []
        
        # Venue hire (always present)
        items.append(InvoiceItem(
            description=f"Event Venue Hire - {self.event_name}",
            quantity=1,
            rate=self.venue_hire_fee,
            item_code="Event Venue Hire"
        ))
        
        # Room accommodation (if booked)
        if self.room_accommodation_fee and self.room_accommodation_fee.is_positive():
            items.append(InvoiceItem(
                description=f"Room Accommodation - {self.event_name}",
                quantity=1,
                rate=self.room_accommodation_fee,
                item_code="Room Accommodation"
            ))
        
        # Wellness services (if booked)
        if self.wellness_services_fee and self.wellness_services_fee.is_positive():
            items.append(InvoiceItem(
                description=f"Wellness Services - {self.event_name}",
                quantity=1,
                rate=self.wellness_services_fee,
                item_code="Wellness Services"
            ))
        
        # Build taxes
        taxes = []
        if apply_vat:
            vat = InvoiceTax(
                tax_rate=TaxRate(Decimal('0.16'), "VAT @ 16%"),
                account=Account("VAT - WC", AccountType.LIABILITY)
            )
            taxes.append(vat)
        
        # Create invoice
        posting_date = invoice_date or self.event_date
        
        invoice = SalesInvoice(
            customer=self.client_name,
            posting_date=posting_date,
            items=items,
            taxes=taxes,
            remarks=f"{self.event_type} event: {self.event_name} ({self.guest_count} guests)"
        )
        
        return invoice
    
    @classmethod
    def from_csv_row(cls, row: dict) -> 'EventBooking':
        """
        Create EventBooking from CSV row (events.csv).
        
        Args:
            row: Dict from CSV with keys: event_name, event_date, 
                 client_contact_id, hire_fee, guest_count, etc.
                 
        Returns:
            EventBooking instance
        """
        # Parse monetary fields
        hire_fee = Money(row['hire_fee'], "KES")
        
        # Parse optional fields
        deposit = Money(row['deposit_amount'], "KES") if row.get('deposit_amount') else None
        
        return cls(
            event_name=row['event_name'],
            event_date=date.fromisoformat(row['event_date']),
            client_name=row.get('client_name', f"Client #{row.get('client_contact_id')}"),
            venue_hire_fee=hire_fee,
            guest_count=int(row['guest_count']),
            event_type=row.get('event_type', 'Event'),
            deposit_amount=deposit,
            agent_name=row.get('agent_name'),
            notes=row.get('notes'),
        )
