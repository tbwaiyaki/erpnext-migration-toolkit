"""
FiscalPeriod type for accounting period validation.

Represents fiscal years, quarters, and months with date range
validation and ERPNext compatibility.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from enum import Enum
import calendar


class PeriodType(Enum):
    """Types of fiscal periods"""
    YEAR = "Year"
    QUARTER = "Quarter"
    MONTH = "Month"
    CUSTOM = "Custom"


@dataclass(frozen=True)
class FiscalPeriod:
    """
    Immutable fiscal period with date validation.
    
    Represents an accounting period (year, quarter, month) with
    methods to validate dates and check period boundaries.
    
    Examples:
        >>> fy_2024 = FiscalPeriod(
        ...     date(2024, 1, 1),
        ...     date(2024, 12, 31),
        ...     "FY 2024"
        ... )
        >>> fy_2024.contains(date(2024, 6, 15))
        True
        
        >>> q1_2024 = FiscalPeriod.quarter(2024, 1)
        >>> q1_2024.name
        'Q1 2024'
        >>> q1_2024.start_date
        date(2024, 1, 1)
        >>> q1_2024.end_date
        date(2024, 3, 31)
    """
    
    start_date: date
    end_date: date
    name: str
    period_type: PeriodType = PeriodType.CUSTOM
    
    def __init__(
        self,
        start_date: date | str,
        end_date: date | str,
        name: str,
        period_type: PeriodType = PeriodType.CUSTOM,
    ):
        """
        Initialize FiscalPeriod with validation.
        
        Args:
            start_date: Period start date (date object or ISO string)
            end_date: Period end date (date object or ISO string)
            name: Human-readable period name (e.g., "FY 2024")
            period_type: Type of period (Year, Quarter, Month, Custom)
            
        Raises:
            ValueError: If dates invalid or end before start
        """
        # Parse dates if strings
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        
        # Validate dates
        if not isinstance(start_date, date):
            raise ValueError(f"start_date must be date object, got {type(start_date)}")
        if not isinstance(end_date, date):
            raise ValueError(f"end_date must be date object, got {type(end_date)}")
        
        if end_date < start_date:
            raise ValueError(
                f"end_date ({end_date}) cannot be before start_date ({start_date})"
            )
        
        # Validate name
        if not name or not name.strip():
            raise ValueError("Period name cannot be empty")
        
        # Validate period type
        if not isinstance(period_type, PeriodType):
            raise ValueError(f"period_type must be PeriodType enum, got {type(period_type)}")
        
        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, 'start_date', start_date)
        object.__setattr__(self, 'end_date', end_date)
        object.__setattr__(self, 'name', name.strip())
        object.__setattr__(self, 'period_type', period_type)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return f"{self.name} ({self.start_date} to {self.end_date})"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"FiscalPeriod('{self.start_date}', '{self.end_date}', '{self.name}')"
    
    @property
    def duration_days(self) -> int:
        """
        Get period duration in days.
        
        Returns:
            Number of days in period (inclusive)
        """
        return (self.end_date - self.start_date).days + 1
    
    @property
    def year(self) -> int:
        """Get year of period start"""
        return self.start_date.year
    
    def contains(self, check_date: date | str) -> bool:
        """
        Check if date falls within this period.
        
        Args:
            check_date: Date to check (date object or ISO string)
            
        Returns:
            True if date is within period (inclusive)
            
        Example:
            >>> period = FiscalPeriod(date(2024, 1, 1), date(2024, 12, 31), "FY 2024")
            >>> period.contains(date(2024, 6, 15))
            True
            >>> period.contains(date(2025, 1, 1))
            False
        """
        if isinstance(check_date, str):
            check_date = date.fromisoformat(check_date)
        
        return self.start_date <= check_date <= self.end_date
    
    def overlaps(self, other: 'FiscalPeriod') -> bool:
        """
        Check if this period overlaps with another.
        
        Args:
            other: Another FiscalPeriod
            
        Returns:
            True if periods overlap
        """
        return not (self.end_date < other.start_date or self.start_date > other.end_date)
    
    def is_current(self, reference_date: Optional[date] = None) -> bool:
        """
        Check if period contains reference date.
        
        Args:
            reference_date: Date to check (default: today)
            
        Returns:
            True if period is current as of reference date
        """
        if reference_date is None:
            reference_date = date.today()
        return self.contains(reference_date)
    
    def is_closed(self, reference_date: Optional[date] = None) -> bool:
        """
        Check if period has ended.
        
        Args:
            reference_date: Date to check against (default: today)
            
        Returns:
            True if period end date is before reference date
        """
        if reference_date is None:
            reference_date = date.today()
        return self.end_date < reference_date
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Fiscal Year format.
        
        Returns:
            Dict suitable for ERPNext Fiscal Year doctype
        """
        return {
            "doctype": "Fiscal Year",
            "year": self.name,
            "year_start_date": self.start_date.isoformat(),
            "year_end_date": self.end_date.isoformat(),
        }
    
    @classmethod
    def year(cls, year: int, name: Optional[str] = None) -> 'FiscalPeriod':
        """
        Create fiscal year (Jan 1 - Dec 31).
        
        Args:
            year: Calendar year
            name: Optional name (default: "FY {year}")
            
        Returns:
            FiscalPeriod for the year
            
        Example:
            >>> fy = FiscalPeriod.year(2024)
            >>> fy.start_date
            date(2024, 1, 1)
            >>> fy.end_date
            date(2024, 12, 31)
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        period_name = name or f"FY {year}"
        
        return cls(start, end, period_name, PeriodType.YEAR)
    
    @classmethod
    def quarter(cls, year: int, quarter: int) -> 'FiscalPeriod':
        """
        Create fiscal quarter.
        
        Args:
            year: Calendar year
            quarter: Quarter number (1-4)
            
        Returns:
            FiscalPeriod for the quarter
            
        Raises:
            ValueError: If quarter not 1-4
            
        Example:
            >>> q1 = FiscalPeriod.quarter(2024, 1)
            >>> q1.start_date
            date(2024, 1, 1)
            >>> q1.end_date
            date(2024, 3, 31)
        """
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"Quarter must be 1-4, got {quarter}")
        
        # Quarter start months: Q1=Jan, Q2=Apr, Q3=Jul, Q4=Oct
        start_month = (quarter - 1) * 3 + 1
        start = date(year, start_month, 1)
        
        # End is last day of third month
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        end = date(year, end_month, last_day)
        
        return cls(start, end, f"Q{quarter} {year}", PeriodType.QUARTER)
    
    @classmethod
    def month(cls, year: int, month: int) -> 'FiscalPeriod':
        """
        Create fiscal month.
        
        Args:
            year: Calendar year
            month: Month number (1-12)
            
        Returns:
            FiscalPeriod for the month
            
        Raises:
            ValueError: If month not 1-12
            
        Example:
            >>> march = FiscalPeriod.month(2024, 3)
            >>> march.start_date
            date(2024, 3, 1)
            >>> march.end_date
            date(2024, 3, 31)
        """
        if month not in range(1, 13):
            raise ValueError(f"Month must be 1-12, got {month}")
        
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        
        month_name = calendar.month_name[month]
        return cls(start, end, f"{month_name} {year}", PeriodType.MONTH)
    
    @classmethod
    def custom(
        cls,
        start_date: date | str,
        end_date: date | str,
        name: str,
    ) -> 'FiscalPeriod':
        """
        Create custom period with arbitrary dates.
        
        Args:
            start_date: Period start
            end_date: Period end
            name: Period name
            
        Returns:
            FiscalPeriod with CUSTOM type
        """
        return cls(start_date, end_date, name, PeriodType.CUSTOM)
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'FiscalPeriod':
        """
        Create FiscalPeriod from ERPNext Fiscal Year document.
        
        Args:
            doc: ERPNext Fiscal Year document dict
            
        Returns:
            FiscalPeriod instance
        """
        start = date.fromisoformat(doc["year_start_date"])
        end = date.fromisoformat(doc["year_end_date"])
        name = doc["year"]
        
        return cls(start, end, name, PeriodType.YEAR)


def create_fiscal_years(
    start_year: int,
    end_year: int,
) -> list[FiscalPeriod]:
    """
    Create multiple consecutive fiscal years.
    
    Args:
        start_year: First year (inclusive)
        end_year: Last year (inclusive)
        
    Returns:
        List of FiscalPeriod objects
        
    Example:
        >>> years = create_fiscal_years(2024, 2026)
        >>> [y.name for y in years]
        ['FY 2024', 'FY 2025', 'FY 2026']
    """
    return [
        FiscalPeriod.year(year)
        for year in range(start_year, end_year + 1)
    ]


def get_period_for_date(
    check_date: date | str,
    periods: list[FiscalPeriod],
) -> Optional[FiscalPeriod]:
    """
    Find which period contains a given date.
    
    Args:
        check_date: Date to find period for
        periods: List of periods to search
        
    Returns:
        FiscalPeriod containing date, or None if not found
        
    Example:
        >>> years = create_fiscal_years(2024, 2025)
        >>> period = get_period_for_date(date(2024, 6, 15), years)
        >>> period.name
        'FY 2024'
    """
    if isinstance(check_date, str):
        check_date = date.fromisoformat(check_date)
    
    for period in periods:
        if period.contains(check_date):
            return period
    
    return None
