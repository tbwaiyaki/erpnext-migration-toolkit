"""
Expense Importer - Imports expense transactions as Journal Entries.

Maps expense categories to Chart of Accounts and creates proper
double-entry journal entries in ERPNext.

Usage:
    importer = ExpenseImporter(client, company="Wellness Centre")
    results = importer.import_expenses(transactions_df, account_mappings)
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from frappeclient import FrappeClient


class ExpenseImporter:
    """
    Import expense transactions as Journal Entries in ERPNext.
    
    Creates proper double-entry accounting:
    - Debit: Expense account (from category mapping)
    - Credit: Payment account (Cash/Bank/Mobile Money)
    """
    
    # Payment method to account mapping
    PAYMENT_ACCOUNT_MAP = {
        'M-Pesa': 'Mobile Money - {suffix}',
        'Bank Transfer': 'KCB - {suffix}',
        'Cash': 'Cash - {suffix}',
    }
    
    def __init__(self, client: FrappeClient, company: str, company_suffix: str = "WC"):
        """
        Initialize expense importer.
        
        Args:
            client: Authenticated FrappleClient
            company: Company name (e.g., "Wellness Centre")
            company_suffix: Company suffix for accounts (e.g., "WC")
        """
        self.client = client
        self.company = company
        self.suffix = company_suffix
        self.successes = []
        self.failures = []
        self.skipped = []
        
    def _get_payment_account(self, payment_method: str) -> str:
        """
        Get ERPNext account for payment method.
        
        Args:
            payment_method: Payment method from transaction (M-Pesa/Bank Transfer/Cash)
            
        Returns:
            ERPNext account name with company suffix
            
        Raises:
            ValueError: If payment method not recognized
        """
        template = self.PAYMENT_ACCOUNT_MAP.get(payment_method)
        if not template:
            raise ValueError(f"Unknown payment method: {payment_method}")
        
        return template.format(suffix=self.suffix)
    
    def build_journal_entry(
        self,
        transaction: dict,
        expense_account: str
    ) -> dict:
        """
        Build Journal Entry payload for an expense transaction.
        
        Creates double-entry:
        - Debit expense account (expense increases)
        - Credit payment account (cash/bank decreases)
        
        Args:
            transaction: Transaction record from CSV
            expense_account: Mapped expense account name
            
        Returns:
            ERPNext Journal Entry payload
        """
        # Get payment account
        payment_method = transaction['payment_method']
        payment_account = self._get_payment_account(payment_method)
        
        # Build journal entry
        amount = float(transaction['amount'])
        
        payload = {
            "doctype": "Journal Entry",
            "company": self.company,
            "posting_date": transaction['transaction_date'],
            "voucher_type": "Journal Entry",
            "user_remark": transaction.get('description', ''),
            "accounts": [
                {
                    # Debit expense account
                    "account": expense_account,
                    "debit_in_account_currency": amount,
                    "credit_in_account_currency": 0,
                    "reference_type": "",
                    "reference_name": ""
                },
                {
                    # Credit payment account
                    "account": payment_account,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": amount,
                    "reference_type": "",
                    "reference_name": ""
                }
            ]
        }
        
        return payload
    
    def import_expenses(
        self,
        transactions_df: pd.DataFrame,
        account_mappings: pd.DataFrame,
        auto_submit: bool = True,
        limit: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Import expense transactions as Journal Entries.
        
        Args:
            transactions_df: DataFrame with expense transactions
            account_mappings: DataFrame from AccountMapper.map_categories()
            auto_submit: Submit journal entries after creation
            limit: Optional limit for testing (e.g., 10 for first batch)
            
        Returns:
            Dictionary with import results
        """
        # Filter to expenses only
        expenses = transactions_df[transactions_df['type'] == 'expense'].copy()
        
        if limit:
            expenses = expenses.head(limit)
        
        # Create mapping dict for quick lookup
        category_to_account = {
            row['category_id']: row['erpnext_account']
            for _, row in account_mappings.iterrows()
        }
        
        print(f"Importing {len(expenses)} expense transactions...")
        print("=" * 70)
        
        for i, (_, tx) in enumerate(expenses.iterrows(), 1):
            category_id = tx['category_id']
            
            # Get expense account
            expense_account = category_to_account.get(category_id)
            if not expense_account:
                self.failures.append({
                    'transaction_id': tx['id'],
                    'date': tx['transaction_date'],
                    'error': f"No account mapping for category_id {category_id}"
                })
                continue
            
            try:
                # Build payload
                payload = self.build_journal_entry(
                    tx.to_dict(),
                    expense_account
                )
                
                # Insert
                doc = self.client.insert(payload)
                je_name = doc.get('name')
                
                # Auto-submit
                if auto_submit:
                    self.client.update({
                        "doctype": "Journal Entry",
                        "name": je_name,
                        "docstatus": 1
                    })
                
                self.successes.append({
                    'transaction_id': tx['id'],
                    'je_name': je_name,
                    'amount': tx['amount'],
                    'account': expense_account
                })
                
                # Progress indicator every 50 records
                if i % 50 == 0 or i == len(expenses):
                    print(f"  Progress: {i}/{len(expenses)} "
                          f"(✓ {len(self.successes)}, ✗ {len(self.failures)})")
                
            except Exception as e:
                error_msg = str(e)[:200]
                self.failures.append({
                    'transaction_id': tx['id'],
                    'date': tx['transaction_date'],
                    'amount': tx['amount'],
                    'error': error_msg
                })
        
        print("=" * 70)
        
        return self.get_summary()
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get import summary statistics.
        
        Returns:
            Dictionary with counts, totals, and details
        """
        success_total = sum(s['amount'] for s in self.successes)
        
        return {
            'total_attempted': len(self.successes) + len(self.failures),
            'succeeded': len(self.successes),
            'failed': len(self.failures),
            'success_amount': success_total,
            'successes': self.successes,
            'failures': self.failures
        }
    
    def print_summary(self):
        """Print formatted import summary."""
        summary = self.get_summary()
        
        print("\n" + "=" * 70)
        print("EXPENSE IMPORT SUMMARY")
        print("=" * 70)
        print(f"Total attempted:  {summary['total_attempted']}")
        print(f"Succeeded:        {summary['succeeded']}")
        print(f"Failed:           {summary['failed']}")
        print(f"Success amount:   KES {summary['success_amount']:,.2f}")
        
        if summary['failed'] > 0:
            print("\nFirst 5 failures:")
            for failure in summary['failures'][:5]:
                print(f"  ID {failure['transaction_id']}: {failure['error']}")
        
        print("=" * 70)
