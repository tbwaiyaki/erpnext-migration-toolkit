"""
Event Importer - Import event venue hire as Sales Invoices.

Events are venue rental transactions with deposits and balances.
Creates Sales Invoices for hire fees.

Version 1.0: Initial implementation

Architecture:
- Uses CustomerRegistry for customer management
- Events → Sales Invoice (venue hire service)
- Links to room bookings via event_id custom field
- Item: "Venue Hire" service item

Usage:
    from orchestration.customer_registry import CustomerRegistry
    
    registry = CustomerRegistry(client, "Wellness Centre")
    importer = EventImporter(client, "Wellness Centre", customer_registry=registry)
    results = importer.import_batch(events_df, contacts_df)
"""

import pandas as pd
from typing import Dict, Optional
from frappeclient import FrappeClient
import time


class EventImporter:
    """
    Import events as Sales Invoices for venue hire.
    
    Uses CustomerRegistry for professional customer management.
    """
    
    VERSION = "1.0"
    
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
            customer_registry: CustomerRegistry for customer management
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
        
        # Cache for contacts
        self._contacts_cache = {}
    
    def import_batch(
        self,
        events_df: pd.DataFrame,
        contacts_df: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Import events as Sales Invoices.
        
        Args:
            events_df: Events data
            contacts_df: Optional contacts for customer linking
            
        Returns:
            Results dict
        """
        start_time = time.time()
        
        print(f"[EventImporter {self.VERSION}]")
        print(f"Importing {len(events_df)} events...")
        print("=" * 70)
        
        # Build contacts cache
        if contacts_df is not None:
            self._build_contacts_cache(contacts_df)
        
        # Ensure venue hire item exists
        self._ensure_venue_hire_item()
        
        # Import events
        for idx, event in events_df.iterrows():
            try:
                # Check for duplicate
                if self._is_duplicate(event['id']):
                    self.results['skipped'] += 1
                    if (idx + 1) % 5 == 0:
                        print(f"  ⊘ Skipped {idx + 1} duplicates...")
                    continue
                
                # Create sales invoice
                invoice = self._create_event_invoice(event)
                
                self.results['successful'] += 1
                
                # Track by event type
                event_type = event['event_type']
                self.results['by_type'][event_type] = \
                    self.results['by_type'].get(event_type, 0) + 1
                
                if (idx + 1) % 5 == 0:
                    print(f"  ✓ Imported {idx + 1}...")
                    
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'event_id': event['id'],
                    'event_name': event['event_name'],
                    'error': str(e)
                })
        
        self.results['duration_seconds'] = round(time.time() - start_time, 2)
        
        print(f"  ✓ Complete: {self.results['successful']} events imported")
        print("=" * 70)
        
        return self.results
    
    def _build_contacts_cache(self, contacts_df: pd.DataFrame):
        """Build contact lookup cache."""
        for _, contact in contacts_df.iterrows():
            self._contacts_cache[contact['id']] = contact['name']
    
    def _ensure_venue_hire_item(self):
        """Ensure 'Venue Hire' service item exists."""
        try:
            existing = self.client.get_list(
                "Item",
                filters={"item_code": "VENUE-HIRE"},
                limit_page_length=1
            )
            
            if existing:
                return
            
            # Create Venue Hire service item
            item = {
                "doctype": "Item",
                "item_code": "VENUE-HIRE",
                "item_name": "Venue Hire (Events)",
                "item_group": "Services",
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_sales_item": 1,
                "is_service_item": 1,
                "description": "Event venue hire fee"
            }
            
            self.client.insert(item)
            print("  ✓ Created service item: Venue Hire")
            
        except Exception:
            pass
    
    def _is_duplicate(self, event_id: int) -> bool:
        """Check if event already imported."""
        try:
            existing = self.client.get_list(
                "Sales Invoice",
                filters={"source_event_id": str(event_id)},
                limit_page_length=1
            )
            return len(existing) > 0
        except:
            return False
    
    def _create_event_invoice(self, event: pd.Series) -> Dict:
        """
        Create Sales Invoice for event venue hire.
        
        Args:
            event: Event row from DataFrame
            
        Returns:
            Created invoice dict
        """
        # Get customer
        customer_name = self._get_customer_name(event)
        
        # Build invoice
        invoice = {
            "doctype": "Sales Invoice",
            "customer": customer_name,
            "posting_date": str(event['event_date']),
            # Let ERPNext auto-set due_date
            "company": self.company,
            "currency": "KES",
            "source_event_id": str(event['id']),
            "items": [
                {
                    "item_code": "VENUE-HIRE",
                    "item_name": f"Venue Hire - {event['event_name']}",
                    "description": self._build_description(event),
                    "qty": 1,
                    "rate": float(event['hire_fee']),
                    "amount": float(event['hire_fee'])
                }
            ]
        }
        
        # Create invoice
        created = self.client.insert(invoice)
        
        # Submit if completed
        if event['status'] == 'completed':
            created['docstatus'] = 1
            self.client.update(created)
        
        return created
    
    def _get_customer_name(self, event: pd.Series) -> str:
        """Get or create customer for event."""
        # Try client contact
        if pd.notna(event.get('client_contact_id')):
            contact_id = int(event['client_contact_id'])
            if contact_id in self._contacts_cache:
                contact_name = self._contacts_cache[contact_id]
                # Ensure customer exists
                return self.customer_registry.ensure_customer(
                    customer_name=contact_name,
                    customer_group="Individual",
                    customer_type="Individual"
                )
        
        # Fallback: use event name as reference
        # This shouldn't happen if contacts are complete
        raise ValueError(f"No customer contact for event {event['id']}: {event['event_name']}")
    
    def _build_description(self, event: pd.Series) -> str:
        """Build item description."""
        lines = []
        lines.append(f"Event: {event['event_name']}")
        lines.append(f"Type: {event['event_type']}")
        lines.append(f"Date: {event['event_date']}")
        lines.append(f"Venue: {event['venue_area']}")
        lines.append(f"Guests: {event['guest_count']}")
        
        if pd.notna(event.get('notes')):
            lines.append(f"Notes: {event['notes']}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Get import summary."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("EVENT IMPORT SUMMARY")
        lines.append("=" * 70)
        
        # Customer registry stats
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
            lines.append(f"\nBy Event Type:")
            for etype, count in sorted(self.results['by_type'].items()):
                lines.append(f"  {etype}: {count}")
        
        if self.results['errors']:
            lines.append(f"\nℹ️  {len(self.results['errors'])} discrepancies found")
            lines.append(f"   Discrepancy report will be generated automatically.")
        
        lines.append("=" * 70)
        return "\n".join(lines)
