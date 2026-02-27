"""
Invoice Generator for wellness centre operations.

Converts domain models to financial documents (invoices).
"""

from typing import Optional
from datetime import date

from core.money import Money
from domain.event_booking import EventBooking
from domain.room_booking import RoomBooking
from domain.egg_sale import EggSale
from documents.sales_invoice import SalesInvoice


class InvoiceGenerator:
    """
    Generate invoices from domain models.
    
    Handles invoice creation with proper sequencing and validation.
    
    Examples:
        >>> generator = InvoiceGenerator()
        >>> 
        >>> # Generate from event
        >>> event = EventBooking(...)
        >>> invoice = generator.from_event(event)
        >>> 
        >>> # Batch generate
        >>> invoices = generator.batch_generate_events(events)
    """
    
    def __init__(self):
        """Initialize generator"""
        self.generated_count = 0
        self.errors = []
    
    def from_event(
        self,
        event: EventBooking,
        apply_vat: bool = True
    ) -> Optional[SalesInvoice]:
        """
        Generate invoice from event booking.
        
        Args:
            event: EventBooking instance
            apply_vat: Whether to apply VAT (default: True)
            
        Returns:
            SalesInvoice or None if generation failed
        """
        try:
            invoice = event.create_invoice(apply_vat=apply_vat)
            self.generated_count += 1
            return invoice
        except Exception as e:
            self.errors.append({
                'type': 'event',
                'name': event.event_name,
                'error': str(e)
            })
            return None
    
    def from_room(
        self,
        room: RoomBooking,
        apply_vat: bool = True
    ) -> Optional[SalesInvoice]:
        """
        Generate invoice from room booking.
        
        Args:
            room: RoomBooking instance
            apply_vat: Whether to apply VAT (default: True)
            
        Returns:
            SalesInvoice or None if generation failed
        """
        try:
            invoice = room.create_invoice(apply_vat=apply_vat)
            self.generated_count += 1
            return invoice
        except Exception as e:
            self.errors.append({
                'type': 'room',
                'name': room.room_name,
                'error': str(e)
            })
            return None
    
    def from_egg_sale(
        self,
        sale: EggSale,
        apply_vat: bool = False  # Typically zero-rated
    ) -> Optional[SalesInvoice]:
        """
        Generate invoice from egg sale.
        
        Args:
            sale: EggSale instance
            apply_vat: Whether to apply VAT (default: False)
            
        Returns:
            SalesInvoice or None if generation failed
        """
        try:
            invoice = sale.create_invoice(apply_vat=apply_vat)
            self.generated_count += 1
            return invoice
        except Exception as e:
            self.errors.append({
                'type': 'egg_sale',
                'name': f"{sale.trays_sold} trays on {sale.sale_date}",
                'error': str(e)
            })
            return None
    
    def batch_generate_events(
        self,
        events: list[EventBooking],
        apply_vat: bool = True
    ) -> list[SalesInvoice]:
        """
        Generate invoices for multiple events.
        
        Args:
            events: List of EventBooking instances
            apply_vat: Whether to apply VAT
            
        Returns:
            List of successfully generated invoices
        """
        invoices = []
        
        for event in events:
            invoice = self.from_event(event, apply_vat)
            if invoice:
                invoices.append(invoice)
        
        return invoices
    
    def batch_generate_rooms(
        self,
        rooms: list[RoomBooking],
        apply_vat: bool = True
    ) -> list[SalesInvoice]:
        """Generate invoices for multiple room bookings"""
        invoices = []
        
        for room in rooms:
            invoice = self.from_room(room, apply_vat)
            if invoice:
                invoices.append(invoice)
        
        return invoices
    
    def batch_generate_eggs(
        self,
        sales: list[EggSale],
        apply_vat: bool = False
    ) -> list[SalesInvoice]:
        """Generate invoices for multiple egg sales"""
        invoices = []
        
        for sale in sales:
            invoice = self.from_egg_sale(sale, apply_vat)
            if invoice:
                invoices.append(invoice)
        
        return invoices
    
    def generate_all(
        self,
        events: list[EventBooking],
        rooms: list[RoomBooking],
        eggs: list[EggSale]
    ) -> dict:
        """
        Generate all invoices from domain models.
        
        Args:
            events: Event bookings
            rooms: Room bookings
            eggs: Egg sales
            
        Returns:
            Dict with invoice lists and summary
        """
        event_invoices = self.batch_generate_events(events)
        room_invoices = self.batch_generate_rooms(rooms)
        egg_invoices = self.batch_generate_eggs(eggs)
        
        return {
            'event_invoices': event_invoices,
            'room_invoices': room_invoices,
            'egg_invoices': egg_invoices,
            'summary': {
                'events': len(event_invoices),
                'rooms': len(room_invoices),
                'eggs': len(egg_invoices),
                'total': len(event_invoices) + len(room_invoices) + len(egg_invoices),
                'errors': len(self.errors),
            }
        }
    
    def get_totals(self, invoices: list[SalesInvoice]) -> dict:
        """
        Calculate totals from invoice list.
        
        Args:
            invoices: List of invoices
            
        Returns:
            Dict with subtotal, tax, grand total
        """
        if not invoices:
            return {
                'count': 0,
                'subtotal': Money.zero("KES"),
                'tax': Money.zero("KES"),
                'grand_total': Money.zero("KES"),
            }
        
        currency = invoices[0].currency
        
        subtotal = sum(
            (inv.subtotal for inv in invoices),
            Money.zero(currency)
        )
        
        tax = sum(
            (inv.total_tax for inv in invoices),
            Money.zero(currency)
        )
        
        grand_total = sum(
            (inv.grand_total for inv in invoices),
            Money.zero(currency)
        )
        
        return {
            'count': len(invoices),
            'subtotal': subtotal,
            'tax': tax,
            'grand_total': grand_total,
        }
    
    def reset_stats(self):
        """Reset generation statistics"""
        self.generated_count = 0
        self.errors = []
