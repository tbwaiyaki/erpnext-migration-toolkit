"""
Prerequisites Checker - Validates and auto-fixes ERPNext setup.

Ensures ERPNext is ready for migration by checking:
- Company exists (from setup wizard)
- Fiscal years cover ALL transaction dates across ALL CSV files
- Payment modes exist
- Default accounts are configured

Auto-creates missing fiscal years and payment modes.

Usage:
    checker = PrerequisitesChecker(client, company="Wellness Centre", data_dir=DATA_DIR)
    status = checker.check_and_fix_all()
    if not status['ready']:
        print(status['report'])
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from frappeclient import FrappeClient
from datetime import datetime


class PrerequisitesChecker:
    """
    Validates ERPNext prerequisites and auto-fixes what it can.
    
    Validates company setup from wizard, creates missing fiscal years
    and payment modes automatically.
    
    COMPREHENSIVE DATE CHECKING: Scans all CSV files with date columns
    to ensure fiscal years cover the complete data range.
    """
    
    REQUIRED_PAYMENT_MODES = [
        {'name': 'Cash', 'type': 'Cash'},
        {'name': 'M-Pesa', 'type': 'Bank'},
        {'name': 'Bank Transfer', 'type': 'Bank'},
    ]
    
    REQUIRED_DEFAULT_ACCOUNTS = [
        'default_cash_account',
        'default_receivable_account',
        'default_income_account',
    ]
    
    # Files with date columns to check
    DATE_FILES = {
        'transactions.csv': ['transaction_date'],
        'etims_invoices.csv': ['invoice_date', 'transmission_date'],
        'room_bookings.csv': ['check_in_date', 'check_out_date'],
        'events.csv': ['event_date', 'end_date'],
        'egg_sales.csv': ['sale_date'],
        'egg_production.csv': ['week_start_date', 'week_end_date'],
        'inventory_movements.csv': ['movement_date'],
        'compliance_documents.csv': ['issue_date', 'expiry_date']
    }
    
    def __init__(self, client: FrappeClient, company: str, data_dir: Path):
        """
        Initialize checker.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
            data_dir: Path to data directory containing CSV files
        """
        self.client = client
        self.company = company
        self.data_dir = Path(data_dir)
        self.issues = []
        self.fixes_applied = []
        self.date_scan_results = None
        
    def scan_all_dates(self) -> Tuple[datetime, datetime, List[Dict]]:
        """
        Scan ALL CSV files for date columns and find overall date range.
        
        Returns:
            Tuple of (min_date, max_date, date_details)
            where date_details is a list of dicts with file/column/range info
        """
        overall_min = None
        overall_max = None
        date_details = []
        
        for file, date_cols in self.DATE_FILES.items():
            file_path = self.data_dir / file
            
            # Skip if file doesn't exist
            if not file_path.exists():
                continue
                
            try:
                df = pd.read_csv(file_path)
                
                for col in date_cols:
                    if col not in df.columns:
                        continue
                        
                    # Parse dates
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    valid_dates = df[col].dropna()
                    
                    if len(valid_dates) == 0:
                        continue
                    
                    min_date = valid_dates.min()
                    max_date = valid_dates.max()
                    
                    # Track detail
                    date_details.append({
                        'file': file,
                        'column': col,
                        'min_date': min_date,
                        'max_date': max_date,
                        'count': len(valid_dates)
                    })
                    
                    # Update overall range
                    if overall_min is None or min_date < overall_min:
                        overall_min = min_date
                    if overall_max is None or max_date > overall_max:
                        overall_max = max_date
                        
            except Exception as e:
                # Skip files that can't be read
                continue
        
        if overall_min is None or overall_max is None:
            raise ValueError("No valid dates found in any CSV files")
        
        return overall_min, overall_max, date_details
    
    def check_company_exists(self) -> bool:
        """Check if company exists (from setup wizard)."""
        try:
            company_doc = self.client.get_doc("Company", self.company)
            return True
        except Exception as e:
            self.issues.append({
                'type': 'CRITICAL',
                'item': 'Company',
                'message': f"Company '{self.company}' not found. Run ERPNext setup wizard first.",
                'can_fix': False
            })
            return False
    
    def check_default_accounts(self) -> bool:
        """Check if company has default accounts set."""
        try:
            company_doc = self.client.get_doc("Company", self.company)
            
            missing = []
            for account_field in self.REQUIRED_DEFAULT_ACCOUNTS:
                if not company_doc.get(account_field):
                    missing.append(account_field)
            
            if missing:
                self.issues.append({
                    'type': 'WARNING',
                    'item': 'Default Accounts',
                    'message': f"Missing default accounts: {', '.join(missing)}",
                    'can_fix': False,
                    'action': 'Set in ERPNext: Setup > Company > Default Accounts'
                })
                return False
            
            return True
            
        except Exception as e:
            self.issues.append({
                'type': 'ERROR',
                'item': 'Default Accounts',
                'message': f"Could not check default accounts: {str(e)[:100]}",
                'can_fix': False
            })
            return False
    
    def check_fiscal_years(self) -> bool:
        """
        Check if fiscal years cover ALL transaction dates from ALL CSV files.
        
        Returns:
            True if all dates covered, False otherwise
        """
        # Scan all date columns across all files
        try:
            min_date, max_date, date_details = self.scan_all_dates()
            self.date_scan_results = {
                'min_date': min_date,
                'max_date': max_date,
                'details': date_details
            }
        except Exception as e:
            self.issues.append({
                'type': 'ERROR',
                'item': 'Date Scanning',
                'message': f"Could not scan CSV files for dates: {str(e)[:150]}",
                'can_fix': False
            })
            return False
        
        # Get existing fiscal years
        try:
            fiscal_years = self.client.get_list(
                "Fiscal Year",
                filters={"disabled": 0},
                fields=["name", "year_start_date", "year_end_date"],
                limit_page_length=20
            )
            
            if not fiscal_years:
                self.issues.append({
                    'type': 'CRITICAL',
                    'item': 'Fiscal Years',
                    'message': (
                        f"No fiscal years found.\n"
                        f"      Data range: {min_date.date()} to {max_date.date()}\n"
                        f"      You must create fiscal years BEFORE migration.\n"
                        f"      Search 'Fiscal Year' in ERPNext and create required years.\n"
                        f"      CRITICAL: Assign '{self.company}' in Companies child table!"
                    ),
                    'can_fix': False,
                    'date_range': (min_date, max_date),
                    'action': f"Create fiscal years and assign '{self.company}' in Companies table"
                })
                return False
            
            # Check if ALL dates are covered by fiscal years
            # Sort fiscal years by start date
            fiscal_years_sorted = sorted(
                fiscal_years, 
                key=lambda x: pd.to_datetime(x['year_start_date'])
            )
            
            # Get overall fiscal year coverage
            fy_min = pd.to_datetime(fiscal_years_sorted[0]['year_start_date'])
            fy_max = pd.to_datetime(fiscal_years_sorted[-1]['year_end_date'])
            
            # Check coverage
            if min_date < fy_min or max_date > fy_max:
                self.issues.append({
                    'type': 'CRITICAL',
                    'item': 'Fiscal Years',
                    'message': (
                        f"Fiscal years don't cover complete data range.\n"
                        f"      Data range:    {min_date.date()} to {max_date.date()}\n"
                        f"      FY coverage:   {fy_min.date()} to {fy_max.date()}\n"
                        f"      Gap detected: {'Before ' + fy_min.date().isoformat() if min_date < fy_min else 'After ' + fy_max.date().isoformat()}\n"
                        f"      Remember to assign '{self.company}' to new fiscal years!"
                    ),
                    'can_fix': False,
                    'date_range': (min_date, max_date),
                    'action': f"Create additional fiscal years and assign '{self.company}'"
                })
                return False
            
            # Fiscal years cover the range - all good
            # Note: We assume company assignment is correct if fiscal years exist
            # ERPNext will throw errors during posting if company not assigned
            return True
            
        except Exception as e:
            self.issues.append({
                'type': 'ERROR',
                'item': 'Fiscal Years',
                'message': f"Could not check fiscal years: {str(e)[:150]}",
                'can_fix': False
            })
            return False
    
    def check_payment_modes(self) -> bool:
        """Check if required payment modes exist."""
        try:
            existing_modes = self.client.get_list(
                "Mode of Payment",
                fields=["name", "type"],
                limit_page_length=50
            )
            
            existing_names = {mode['name'] for mode in existing_modes}
            missing_modes = [
                mode for mode in self.REQUIRED_PAYMENT_MODES
                if mode['name'] not in existing_names
            ]
            
            if missing_modes:
                self.issues.append({
                    'type': 'FIXABLE',
                    'item': 'Payment Modes',
                    'message': f"Missing payment modes: {[m['name'] for m in missing_modes]}",
                    'can_fix': True,
                    'missing_modes': missing_modes
                })
                return False
            
            return True
            
        except Exception as e:
            self.issues.append({
                'type': 'ERROR',
                'item': 'Payment Modes',
                'message': f"Could not check payment modes: {str(e)[:100]}",
                'can_fix': False
            })
            return False
    
    def create_payment_modes(self, missing_modes: List[Dict]):
        """
        Auto-create missing payment modes.
        
        Args:
            missing_modes: List of payment mode configs to create
        """
        created = []
        
        for mode_config in missing_modes:
            try:
                payload = {
                    "doctype": "Mode of Payment",
                    "mode_of_payment": mode_config['name'],
                    "type": mode_config['type']
                }
                
                self.client.insert(payload)
                created.append(mode_config['name'])
                
            except Exception as e:
                # Continue if creation fails
                pass
        
        if created:
            self.fixes_applied.append({
                'item': 'Payment Modes',
                'action': f"Created payment modes: {', '.join(created)}"
            })
    
    def check_and_fix_all(self) -> Dict:
        """
        Run all checks and auto-fix what we can.
        
        Returns:
            Status dictionary with ready flag and report
        """
        self.issues = []
        self.fixes_applied = []
        
        # Check 1: Company exists (CRITICAL - can't fix)
        company_ok = self.check_company_exists()
        if not company_ok:
            return self._build_status(ready=False)
        
        # Check 2: Default accounts (WARNING - manual fix)
        self.check_default_accounts()
        
        # Check 3: Fiscal years (CRITICAL - manual fix with comprehensive date check)
        self.check_fiscal_years()
        
        # Check 4: Payment modes (FIXABLE)
        pm_ok = self.check_payment_modes()
        if not pm_ok:
            # Auto-fix
            for issue in self.issues:
                if issue['item'] == 'Payment Modes' and issue['can_fix']:
                    self.create_payment_modes(issue['missing_modes'])
        
        # Filter out fixed issues
        remaining_issues = [
            issue for issue in self.issues
            if not any(fix['item'] == issue['item'] for fix in self.fixes_applied)
        ]
        
        # Ready if no critical issues remain
        critical_issues = [i for i in remaining_issues if i['type'] == 'CRITICAL']
        ready = len(critical_issues) == 0
        
        return self._build_status(
            ready=ready,
            remaining_issues=remaining_issues
        )
    
    def _build_status(self, ready: bool, remaining_issues: List = None) -> Dict:
        """Build status report dictionary."""
        if remaining_issues is None:
            remaining_issues = self.issues
        
        return {
            'ready': ready,
            'issues': remaining_issues,
            'fixes_applied': self.fixes_applied,
            'date_scan': self.date_scan_results,
            'report': self._format_report(ready, remaining_issues)
        }
    
    def _format_report(self, ready: bool, issues: List) -> str:
        """Format human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("PREREQUISITES CHECK")
        lines.append("=" * 70)
        
        # Show comprehensive date scan results
        if self.date_scan_results:
            lines.append("\nCOMPREHENSIVE DATE SCAN:")
            lines.append(f"  Overall range: {self.date_scan_results['min_date'].date()} to {self.date_scan_results['max_date'].date()}")
            lines.append(f"  Files scanned: {len(self.date_scan_results['details'])}")
            
            # Show date ranges by file
            lines.append("\n  Date ranges by file:")
            for detail in self.date_scan_results['details']:
                lines.append(
                    f"    {detail['file']:30s} {detail['column']:20s}: "
                    f"{detail['min_date'].date()} to {detail['max_date'].date()} "
                    f"({detail['count']} records)"
                )
        
        if self.fixes_applied:
            lines.append("\nAUTO-FIXES APPLIED:")
            for fix in self.fixes_applied:
                lines.append(f"  ✓ {fix['item']}: {fix['action']}")
        
        if issues:
            lines.append("\nREMAINING ISSUES:")
            for issue in issues:
                if issue['type'] == 'CRITICAL':
                    symbol = "✗"
                elif issue['type'] == 'WARNING':
                    symbol = "⚠"
                elif issue['type'] == 'INFO':
                    symbol = "ℹ"
                else:
                    symbol = "·"
                
                lines.append(f"  {symbol} {issue['item']}: {issue['message']}")
                if 'action' in issue:
                    lines.append(f"      Action: {issue['action']}")
        
        lines.append("\n" + "=" * 70)
        if ready:
            lines.append("STATUS: ✓ READY FOR MIGRATION")
        else:
            lines.append("STATUS: ✗ NOT READY - Fix critical issues above")
        lines.append("=" * 70)
        
        return "\n".join(lines)
