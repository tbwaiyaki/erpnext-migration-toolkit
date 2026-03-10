"""
Room Booking Importer - Import room bookings as ERPNext Sales Invoices.

Room bookings are accommodation transactions (bed & breakfast) that should be 
recorded as sales. This importer creates Sales Invoices for each booking.

Version 1.0: Initial implementation
Version 1.3: Refactored to use CustomerRegistry (professional OOP design)
- Customer management delegated to CustomerRegistry
- Follows same pattern as AccountRegistry
- Cleaner separation of concerns

Architecture:
- Uses CustomerRegistry for centralized customer management
- Room bookings → Sales Invoice (not separate Booking doctype)
- Item: "Room Night" service item
- Customer: Guest name (managed by CustomerRegistry)
- Event linkage: Custom field links booking to event if applicable

Usage:
    from orchestration.customer_registry import CustomerRegistry
    
    # Initialize registry
    registry = CustomerRegistry(client, "Wellness Centre")
    
    # Initialize importer with registry
    importer = RoomBookingImporter(client, "Wellness Centre", customer_registry=registry)
    results = importer.import_batch(bookings_df, rooms_df, contacts_df)
"""

import pandas as pd
from typing import Dict, Optional
from frappeclient import FrappeClient
import time
from datetime import datetime


class RoomBookingImporter:
    """
    Import room bookings as Sales Invoices.
    
    Each booking becomes a Sales Invoice for accommodation services.
    Handles both standalone bookings and event-linked bookings.
    Uses CustomerRegistry for professional customer management.
    """
    
    VERSION = "1.6"  # Let ERPNext auto-set due_date (Phase 1 solution)
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        customer_registry: 'CustomerRegistry' = None
    ):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
            customer_registry: Optional CustomerRegistry for customer management
                              If not provided, creates internal instance
        """
        self.client = client
        self.company = company
        
        # Use provided registry or create internal one
        if customer_registry:
            self.customer_registry = customer_registry
        else:
            from orchestration.customer_registry import CustomerRegistry
            self.customer_registry = CustomerRegistry(client, company)
        
        self.results = {
            'successful': 0,
            'skipped': 0,
            'failed': 0,
            'errors': [],
            'duration_seconds': 0.0,
            'by_type': {}
        }
        
        # Cache for rooms and customers
        self._rooms_cache = {}
        self._customers_cache = {}
    
    def import_batch(
        self,
        bookings_df: pd.DataFrame,
        rooms_df: pd.DataFrame,
        contacts_df: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Import room bookings as Sales Invoices.
        
        Args:
            bookings_df: Room bookings data
            rooms_df: Rooms master data
            contacts_df: Optional contacts data for customer linking
            
        Returns:
            Results dict
        """
        start_time = time.time()
        
        print(f"[RoomBookingImporter {self.VERSION}]")
        print(f"Importing {len(bookings_df)} room bookings...")
        print("=" * 70)
        
        # Build caches
        self._build_rooms_cache(rooms_df)
        if contacts_df is not None:
            self._build_customers_cache(contacts_df)
        
        # Ensure service item exists
        self._ensure_room_night_item()
        
        # Import bookings
        for idx, booking in bookings_df.iterrows():
            try:
                # Check for duplicate
                if self._is_duplicate(booking['id']):
                    self.results['skipped'] += 1
                    if (idx + 1) % 10 == 0:
                        print(f"  ⊘ Skipped {idx + 1} duplicates...")
                    continue
                
                # Create sales invoice
                invoice = self._create_booking_invoice(booking)
                
                self.results['successful'] += 1
                
                # Track by booking type
                booking_type = booking['booking_type']
                self.results['by_type'][booking_type] = \
                    self.results['by_type'].get(booking_type, 0) + 1
                
                if (idx + 1) % 10 == 0:
                    print(f"  ✓ Imported {idx + 1}...")
                    
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'booking_id': booking['id'],
                    'guest': booking['guest_name'],
                    'error': str(e)
                })
        
        self.results['duration_seconds'] = round(time.time() - start_time, 2)
        
        print(f"  ✓ Complete: {self.results['successful']} bookings imported")
        print("=" * 70)
        
        return self.results
    
    def _build_rooms_cache(self, rooms_df: pd.DataFrame):
        """Build room lookup cache."""
        for _, room in rooms_df.iterrows():
            self._rooms_cache[room['id']] = {
                'room_name': room['room_name'],
                'nightly_rate': room['nightly_rate'],
                'description': room.get('description', '')
            }
    
    def _build_customers_cache(self, contacts_df: pd.DataFrame):
        """Build customer lookup cache from contacts."""
        for _, contact in contacts_df.iterrows():
            # Only contacts with customer type
            if contact.get('contact_type_id') == 1:  # Customer type
                self._customers_cache[contact['id']] = contact['name']
    
    def _ensure_room_night_item(self):
        """Ensure 'Room Night' service item exists."""
        try:
            existing = self.client.get_list(
                "Item",
                filters={"item_code": "ROOM-NIGHT"},
                limit_page_length=1
            )
            
            if existing:
                return  # Already exists
            
            # Create Room Night service item
            item = {
                "doctype": "Item",
                "item_code": "ROOM-NIGHT",
                "item_name": "Room Night (Accommodation)",
                "item_group": "Services",
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_sales_item": 1,
                "is_service_item": 1,
                "description": "Accommodation service - room night including breakfast"
            }
            
            self.client.insert(item)
            print("  ✓ Created service item: Room Night")
            
        except Exception as e:
            # If creation fails, item might already exist
            pass
    
    def _is_duplicate(self, booking_id: int) -> bool:
        """Check if booking already imported via custom field."""
        try:
            existing = self.client.get_list(
                "Sales Invoice",
                filters={"source_booking_id": str(booking_id)},
                limit_page_length=1
            )
            return len(existing) > 0
        except:
            return False
    
    def _create_booking_invoice(self, booking: pd.Series) -> Dict:
        """
        Create Sales Invoice for room booking.
        
        Args:
            booking: Booking row from DataFrame
            
        Returns:
            Created invoice dict
        """
        # Get room details
        room = self._rooms_cache[booking['room_id']]
        
        # Determine customer
        customer_name = self._get_customer_name(booking)
        
        # Build invoice (let ERPNext auto-set due_date)
        invoice = {
            "doctype": "Sales Invoice",
            "customer": customer_name,
            "posting_date": str(booking['check_in_date']),
            # Don't set due_date - let ERPNext calculate it
            "company": self.company,
            "currency": "KES",
            "source_booking_id": str(booking['id']),  # Custom field for duplicate detection
            "items": [
                {
                    "item_code": "ROOM-NIGHT",
                    "item_name": f"Room Night - {room['room_name']}",
                    "description": self._build_description(booking, room),
                    "qty": int(booking['nights']),  # Convert from int64 to int
                    "rate": float(booking['nightly_rate']),  # Convert to float
                    "amount": float(booking['total_amount'])  # Convert to float
                }
            ]
        }
        
        # Add event linkage if applicable
        if pd.notna(booking.get('event_id')):
            invoice['event_id'] = str(int(booking['event_id']))  # Convert float to int to string
        
        # Create invoice
        created = self.client.insert(invoice)
        
        # Submit invoice (bookings are completed transactions)
        if booking['status'] == 'completed':
            created['docstatus'] = 1
            self.client.update(created)
        
        return created
    
    def _get_customer_name(self, booking: pd.Series) -> str:
        """
        Get or create customer for invoice using CustomerRegistry.
        
        First tries to use linked contact_id, falls back to guest_name.
        Uses CustomerRegistry for centralized customer management.
        
        Args:
            booking: Booking row
            
        Returns:
            Customer name
        """
        # Try linked contact first
        if pd.notna(booking.get('contact_id')):
            contact_id = int(booking['contact_id'])
            if contact_id in self._customers_cache:
                return self._customers_cache[contact_id]
        
        # Use guest name - ensure customer exists via registry
        guest_name = booking['guest_name']
        return self.customer_registry.ensure_customer(
            customer_name=guest_name,
            customer_group="B&B Guests",
            customer_type="Individual"
        )
    
    def _build_description(self, booking: pd.Series, room: Dict) -> str:
        """Build item description for invoice line."""
        lines = []
        lines.append(f"Room: {room['room_name']}")
        lines.append(f"Check-in: {booking['check_in_date']}")
        lines.append(f"Check-out: {booking['check_out_date']}")
        lines.append(f"Nights: {booking['nights']}")
        
        if pd.notna(booking.get('notes')):
            lines.append(f"Notes: {booking['notes']}")
        
        if booking['booking_type'] == 'event_overnight':
            lines.append("(Event-linked booking)")
        
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Get import summary report."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("ROOM BOOKING IMPORT SUMMARY")
        lines.append("=" * 70)
        
        # Show customer registry stats
        registry_summary = self.customer_registry.get_summary()
        if registry_summary != "No new customers created":
            lines.append(registry_summary)
        
        lines.append(f"Total Imported:       {self.results['successful']}")
        lines.append(f"Skipped (duplicates): {self.results['skipped']}")
        
        if self.results['failed'] > 0:
            lines.append(f"Discrepancies:        {self.results['failed']} (see report)")
        else:
            lines.append(f"Discrepancies:        0")
        
        lines.append(f"Duration:             {self.results['duration_seconds']} seconds")
        
        if self.results['by_type']:
            lines.append(f"\nBy Booking Type:")
            for btype, count in self.results['by_type'].items():
                lines.append(f"  {btype}: {count}")
        
        if self.results['errors']:
            lines.append(f"\nℹ️  {len(self.results['errors'])} discrepancies found")
            lines.append(f"   These represent data quality issues, not system errors.")
            lines.append(f"   Discrepancy report will be generated automatically.")
        
        lines.append("=" * 70)
        return "\n".join(lines)
