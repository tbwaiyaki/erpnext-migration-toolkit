"""
CSV Loader for wellness centre data - FIXED VERSION.

Loads CSV files and converts to domain models with proper name lookups.
"""

import pandas as pd
from pathlib import Path
from typing import Optional

from domain.event_booking import EventBooking
from domain.room_booking import RoomBooking
from domain.egg_sale import EggSale


class WellnessCentreDataLoader:
    """
    Load wellness centre data from CSV files.
    
    Now includes proper lookups for customer/guest names from contacts.csv.
    """
    
    def __init__(self, data_dir: Path):
        """
        Initialize loader with data directory.
        
        Args:
            data_dir: Path to directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        
        if not self.data_dir.exists():
            raise ValueError(f"Data directory does not exist: {self.data_dir}")
        
        # Load contacts once for reuse
        self._contacts_df = None
    
    def _load_contacts(self) -> pd.DataFrame:
        """Load contacts CSV (cached)"""
        if self._contacts_df is None:
            contacts_path = self.data_dir / 'contacts.csv'
            if contacts_path.exists():
                self._contacts_df = pd.read_csv(contacts_path)
            else:
                # Empty dataframe if contacts don't exist
                self._contacts_df = pd.DataFrame(columns=['id', 'name'])
        
        return self._contacts_df
    
    def load_events(self, limit: Optional[int] = None) -> list[EventBooking]:
        """
        Load event bookings from events.csv.
        
        Joins with contacts.csv to get actual customer names.
        
        Args:
            limit: Optional limit on number of records (for testing)
            
        Returns:
            List of EventBooking objects
        """
        csv_path = self.data_dir / 'events.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Events CSV not found: {csv_path}")
        
        # Load events
        events_df = pd.read_csv(csv_path)
        
        # Join with contacts to get customer names
        contacts_df = self._load_contacts()
        if not contacts_df.empty:
            events_df = events_df.merge(
                contacts_df[['id', 'name']],
                left_on='client_contact_id',
                right_on='id',
                how='left',
                suffixes=('', '_contact')
            )
            # Rename to client_name
            events_df['client_name'] = events_df['name']
        
        if limit:
            events_df = events_df.head(limit)
        
        events = []
        for _, row in events_df.iterrows():
            try:
                event = EventBooking.from_csv_row({
                    'event_name': row['event_name'],
                    'event_date': row['event_date'],
                    'event_type': row.get('event_type', 'Event'),
                    'client_name': row.get('client_name', f"Customer #{row.get('client_contact_id', 'Unknown')}"),
                    'hire_fee': row['hire_fee'],
                    'guest_count': row['guest_count'],
                    'deposit_amount': row.get('deposit_amount'),
                    'agent_name': row.get('agent_name'),
                    'notes': row.get('notes'),
                })
                events.append(event)
            except Exception as e:
                print(f"Warning: Failed to load event row {row.get('id')}: {e}")
        
        return events
    
    def load_room_bookings(self, limit: Optional[int] = None) -> list[RoomBooking]:
        """
        Load room bookings from room_bookings.csv.
        
        Joins with rooms.csv for room names and contacts.csv for guest names.
        
        Args:
            limit: Optional limit on number of records
            
        Returns:
            List of RoomBooking objects
        """
        csv_path = self.data_dir / 'room_bookings.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Room bookings CSV not found: {csv_path}")
        
        # Load room bookings
        bookings_df = pd.read_csv(csv_path)
        
        # Join with rooms to get room names
        rooms_path = self.data_dir / 'rooms.csv'
        if rooms_path.exists():
            rooms_df = pd.read_csv(rooms_path)
            bookings_df = bookings_df.merge(
                rooms_df[['id', 'room_name']],
                left_on='room_id',
                right_on='id',
                how='left',
                suffixes=('', '_room')
            )
        
        # Join with contacts for guest names (if contact_id exists)
        contacts_df = self._load_contacts()
        if not contacts_df.empty and 'contact_id' in bookings_df.columns:
            bookings_df = bookings_df.merge(
                contacts_df[['id', 'name']],
                left_on='contact_id',
                right_on='id',
                how='left',
                suffixes=('', '_contact')
            )
            # Use contact name if available, otherwise use guest_name column
            bookings_df['final_guest_name'] = bookings_df['name'].fillna(bookings_df.get('guest_name', ''))
        else:
            bookings_df['final_guest_name'] = bookings_df.get('guest_name', 'Guest')
        
        if limit:
            bookings_df = bookings_df.head(limit)
        
        bookings = []
        for _, row in bookings_df.iterrows():
            try:
                booking = RoomBooking.from_csv_row({
                    'room_name': row.get('room_name', f"Room {row.get('room_id')}"),
                    'guest_name': row.get('final_guest_name', 'Guest'),
                    'check_in_date': row['check_in_date'],
                    'check_out_date': row['check_out_date'],
                    'nightly_rate': row['nightly_rate'],
                    'booking_type': row.get('booking_type', 'Standalone'),
                    'event_name': row.get('event_name'),
                    'notes': row.get('notes'),
                })
                bookings.append(booking)
            except Exception as e:
                print(f"Warning: Failed to load room booking row {row.get('id')}: {e}")
        
        return bookings
    
    def load_egg_sales(self, limit: Optional[int] = None) -> list[EggSale]:
        """
        Load egg sales from egg_sales.csv.
        
        Joins with contacts.csv to get customer names.
        
        Args:
            limit: Optional limit on number of records
            
        Returns:
            List of EggSale objects
        """
        csv_path = self.data_dir / 'egg_sales.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Egg sales CSV not found: {csv_path}")
        
        # Load egg sales
        sales_df = pd.read_csv(csv_path)
        
        # Join with contacts for customer names
        contacts_df = self._load_contacts()
        if not contacts_df.empty:
            sales_df = sales_df.merge(
                contacts_df[['id', 'name']],
                left_on='contact_id',
                right_on='id',
                how='left',
                suffixes=('', '_contact')
            )
            sales_df['customer_name'] = sales_df['name']
        
        if limit:
            sales_df = sales_df.head(limit)
        
        sales = []
        for _, row in sales_df.iterrows():
            try:
                sale = EggSale.from_csv_row({
                    'sale_date': row['sale_date'],
                    'customer_name': row.get('customer_name', f"Customer #{row.get('contact_id', 'Unknown')}"),
                    'trays_sold': row['trays_sold'],
                    'price_per_tray': row['price_per_tray'],
                    'notes': row.get('notes'),
                })
                sales.append(sale)
            except Exception as e:
                print(f"Warning: Failed to load egg sale row {row.get('id')}: {e}")
        
        return sales
    
    def load_all(self, limit: Optional[int] = None) -> dict:
        """
        Load all data sources.
        
        Args:
            limit: Optional limit per data source
            
        Returns:
            Dict with keys: events, rooms, eggs
        """
        return {
            'events': self.load_events(limit),
            'rooms': self.load_room_bookings(limit),
            'eggs': self.load_egg_sales(limit),
        }
    
    def get_summary(self) -> dict:
        """
        Get summary of available data without loading.
        
        Returns:
            Dict with record counts per file
        """
        summary = {}
        
        files = {
            'events': 'events.csv',
            'rooms': 'room_bookings.csv',
            'eggs': 'egg_sales.csv',
        }
        
        for key, filename in files.items():
            csv_path = self.data_dir / filename
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                summary[key] = len(df)
            else:
                summary[key] = 0
        
        return summary
