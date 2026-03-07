"""
CSV Loader for wellness centre data.

Loads CSV files and converts to domain models.
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
    
    Examples:
        >>> loader = WellnessCentreDataLoader(Path('/mnt/project'))
        >>> events = loader.load_events()
        >>> rooms = loader.load_room_bookings()
        >>> eggs = loader.load_egg_sales()
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
    
    def load_events(self, limit: Optional[int] = None) -> list[EventBooking]:
        """
        Load event bookings from events.csv.
        
        Args:
            limit: Optional limit on number of records (for testing)
            
        Returns:
            List of EventBooking objects
        """
        csv_path = self.data_dir / 'events.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Events CSV not found: {csv_path}")
        
        df = pd.read_csv(csv_path)
        
        if limit:
            df = df.head(limit)
        
        events = []
        for _, row in df.iterrows():
            try:
                # Map CSV columns to EventBooking fields
                event = EventBooking.from_csv_row({
                    'event_name': row['event_name'],
                    'event_date': row['event_date'],
                    'event_type': row.get('event_type', 'Event'),
                    'client_name': row.get('client_name', 'Unknown'),
                    'hire_fee': row['hire_fee'],
                    'guest_count': row['guest_count'],
                    'deposit_amount': row.get('deposit_amount'),
                    'agent_name': row.get('agent_name'),
                    'notes': row.get('notes'),
                })
                events.append(event)
            except Exception as e:
                # Log error but continue processing
                print(f"Warning: Failed to load event row {row.get('id')}: {e}")
        
        return events
    
    def load_room_bookings(self, limit: Optional[int] = None) -> list[RoomBooking]:
        """
        Load room bookings from room_bookings.csv.
        
        Args:
            limit: Optional limit on number of records
            
        Returns:
            List of RoomBooking objects
        """
        csv_path = self.data_dir / 'room_bookings.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Room bookings CSV not found: {csv_path}")
        
        df = pd.read_csv(csv_path)
        
        if limit:
            df = df.head(limit)
        
        bookings = []
        for _, row in df.iterrows():
            try:
                booking = RoomBooking.from_csv_row({
                    'room_name': row.get('room_name', f"Room {row.get('room_id')}"),
                    'guest_name': row.get('guest_name', 'Guest'),
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
        
        Args:
            limit: Optional limit on number of records
            
        Returns:
            List of EggSale objects
        """
        csv_path = self.data_dir / 'egg_sales.csv'
        
        if not csv_path.exists():
            raise FileNotFoundError(f"Egg sales CSV not found: {csv_path}")
        
        df = pd.read_csv(csv_path)
        
        if limit:
            df = df.head(limit)
        
        sales = []
        for _, row in df.iterrows():
            try:
                sale = EggSale.from_csv_row({
                    'sale_date': row['sale_date'],
                    'customer_name': row.get('customer_name', f"Customer {row.get('contact_id')}"),
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
