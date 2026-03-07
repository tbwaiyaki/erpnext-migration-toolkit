"""
Prerequisites Checker - Validates and auto-fixes ERPNext setup.

Ensures ERPNext is ready for migration by checking:
- Company exists (from setup wizard)
- Fiscal years cover transaction dates
- Payment modes exist
- Default accounts are configured

Auto-creates missing fiscal years and payment modes.

Usage:
    checker = PrerequisitesChecker(client, company="Wellness Centre")
    status = checker.check_and_fix_all(transactions_df)
    if not status['ready']:
        print(status['report'])
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from frappeclient import FrappeClient
from datetime import datetime


class PrerequisitesChecker:
    """
    Validates ERPNext prerequisites and auto-fixes what it can.
    
    Validates company setup from wizard, creates missing fiscal years
    and payment modes automatically.
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
    
    def __init__(self, client: FrappeClient, company: str):
        """
        Initialize checker.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
        """
        self.client = client
        self.company = company
        self.issues = []
        self.fixes_applied = []
        
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
    
    def check_fiscal_years(self, transactions_df: pd.DataFrame) -> bool:
        """
        Check if fiscal years cover all transaction dates.
        
        Args:
            transactions_df: DataFrame with transaction_date column
            
        Returns:
            True if all dates covered, False otherwise
        """
        # Get date range from transactions
        transactions_df['transaction_date'] = pd.to_datetime(transactions_df['transaction_date'])
        min_date = transactions_df['transaction_date'].min()
        max_date = transactions_df['transaction_date'].max()
        
        # Get existing fiscal years
        try:
            fiscal_years = self.client.get_list(
                "Fiscal Year",
                filters={"disabled": 0},
                fields=["name", "year_start_date", "year_end_date"],
                limit_page_length=10
            )
            
            if not fiscal_years:
                self.issues.append({
                    'type': 'FIXABLE',
                    'item': 'Fiscal Years',
                    'message': f"No fiscal years found. Need to cover {min_date.date()} to {max_date.date()}",
                    'can_fix': True,
                    'date_range': (min_date, max_date)
                })
                return False
            
            # Check if date range is covered
            covered = False
            for fy in fiscal_years:
                fy_start = pd.to_datetime(fy['year_start_date'])
                fy_end = pd.to_datetime(fy['year_end_date'])
                
                if fy_start <= min_date and fy_end >= max_date:
                    covered = True
                    break
            
            if not covered:
                self.issues.append({
                    'type': 'FIXABLE',
                    'item': 'Fiscal Years',
                    'message': f"Existing fiscal years don't cover {min_date.date()} to {max_date.date()}",
                    'can_fix': True,
                    'date_range': (min_date, max_date)
                })
                return False
            
            return True
            
        except Exception as e:
            self.issues.append({
                'type': 'ERROR',
                'item': 'Fiscal Years',
                'message': f"Could not check fiscal years: {str(e)[:100]}",
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
    
    def create_fiscal_years(self, min_date: datetime, max_date: datetime):
        """
        Auto-create fiscal years to cover date range.
        
        Args:
            min_date: Earliest transaction date
            max_date: Latest transaction date
        """
        # Create fiscal years for each calendar year in range
        start_year = min_date.year
        end_year = max_date.year
        
        created = []
        for year in range(start_year, end_year + 1):
            fy_name = f"FY {year}"
            
            # Check if already exists
            try:
                existing = self.client.get_list(
                    "Fiscal Year",
                    filters={"name": fy_name},
                    limit_page_length=1
                )
                if existing:
                    continue
            except:
                pass
            
            # Create fiscal year
            try:
                payload = {
                    "doctype": "Fiscal Year",
                    "year": fy_name,
                    "year_start_date": f"{year}-01-01",
                    "year_end_date": f"{year}-12-31",
                    "disabled": 0
                }
                
                self.client.insert(payload)
                created.append(fy_name)
                
            except Exception as e:
                # Continue if creation fails
                pass
        
        if created:
            self.fixes_applied.append({
                'item': 'Fiscal Years',
                'action': f"Created fiscal years: {', '.join(created)}"
            })
            
            # Set first one as company default if not set
            try:
                company_doc = self.client.get_doc("Company", self.company)
                if not company_doc.get('default_fiscal_year'):
                    self.client.update({
                        "doctype": "Company",
                        "name": self.company,
                        "default_fiscal_year": created[0]
                    })
                    self.fixes_applied.append({
                        'item': 'Company Default FY',
                        'action': f"Set default fiscal year to {created[0]}"
                    })
            except:
                pass
    
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
    
    def check_and_fix_all(self, transactions_df: pd.DataFrame) -> Dict:
        """
        Run all checks and auto-fix what we can.
        
        Args:
            transactions_df: DataFrame with transaction_date column
            
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
        
        # Check 3: Fiscal years (FIXABLE)
        fy_ok = self.check_fiscal_years(transactions_df)
        if not fy_ok:
            # Auto-fix
            for issue in self.issues:
                if issue['item'] == 'Fiscal Years' and issue['can_fix']:
                    min_date, max_date = issue['date_range']
                    self.create_fiscal_years(min_date, max_date)
        
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
            'report': self._format_report(ready, remaining_issues)
        }
    
    def _format_report(self, ready: bool, issues: List) -> str:
        """Format human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("PREREQUISITES CHECK")
        lines.append("=" * 70)
        
        if self.fixes_applied:
            lines.append("\nAUTO-FIXES APPLIED:")
            for fix in self.fixes_applied:
                lines.append(f"  ✓ {fix['item']}: {fix['action']}")
        
        if issues:
            lines.append("\nREMAINING ISSUES:")
            for issue in issues:
                symbol = "✗" if issue['type'] == 'CRITICAL' else "⚠"
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
