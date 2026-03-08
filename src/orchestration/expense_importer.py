"""
Expense Importer - Imports expense transactions as Journal Entries.

Maps expense categories to Chart of Accounts and creates proper
double-entry journal entries in ERPNext using AccountRegistry.

Version 1.1: AccountRegistry integration (eliminates hard-coding)

Usage:
    registry = AccountRegistry(client, "Wellness Centre")
    importer = ExpenseImporter(client, company="Wellness Centre", registry=registry)
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
    - Credit: Payment account (via AccountRegistry)
    """
    
    VERSION = "1.1-accountregistry"
    
    def __init__(self, client: FrappeClient, company: str, registry):
        """
        Initialize expense importer.
        
        Args:
            client: Authenticated FrappleClient
            company: Company name (e.g., "Wellness Centre")
            registry: AccountRegistry instance for dynamic account lookup
        """
        self.client = client
        self.company = company
        self.registry = registry
        self.successes = []
        self.failures = []
        self.skipped = []
        
    def build_journal_entry(
        self,
        transaction: dict,
        expense_account: str
    ) -> dict:
        """
        Build Journal Entry payload for an expense transaction.
        
        Creates double-entry:
        - Debit expense account (expense increases)
        - Credit payment account (cash/bank decreases via AccountRegistry)
        
        Args:
            transaction: Transaction record from CSV
            expense_account: Mapped expense account name
            
        Returns:
            ERPNext Journal Entry payload
        """
        # Get payment account via AccountRegistry
        payment_method = transaction['payment_method']
        try:
            payment_account = self.registry.get_payment_account(payment_method)
        except ValueError as e:
            # Fallback to Cash if payment method not found
            print(f"⚠ Payment method '{payment_method}' not found, using Cash: {e}")
            payment_account = self.registry.get_payment_account('Cash')
        
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
            transaction_id = tx['id']
            
            # Check for duplicate (existing Journal Entry with this source_transaction_id)
            try:
                existing = self.client.get_list(
                    "Journal Entry",
                    filters={"source_transaction_id": str(transaction_id)},
                    fields=["name"],
                    limit_page_length=1
                )
                
                if existing:
                    self.skipped.append({
                        'transaction_id': transaction_id,
                        'date': tx['transaction_date'],
                        'amount': tx['amount'],
                        'reason': f"Already exists: {existing[0]['name']}"
                    })
                    continue
            except Exception:
                # Custom field might not exist yet - proceed with import
                pass
            
            # Get expense account
            expense_account = category_to_account.get(category_id)
            if not expense_account:
                self.failures.append({
                    'transaction_id': transaction_id,
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
                
                # Add source_transaction_id for duplicate detection
                payload['source_transaction_id'] = str(transaction_id)
                
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
                    'transaction_id': transaction_id,
                    'je_name': je_name,
                    'amount': tx['amount'],
                    'account': expense_account
                })
                
                # Progress indicator every 50 records
                if i % 50 == 0 or i == len(expenses):
                    print(f"  Progress: {i}/{len(expenses)} "
                          f"(✓ {len(self.successes)}, ⊘ {len(self.skipped)}, ✗ {len(self.failures)})")
                
            except Exception as e:
                error_msg = str(e)[:200]
                self.failures.append({
                    'transaction_id': transaction_id,
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
            'total_attempted': len(self.successes) + len(self.skipped) + len(self.failures),
            'succeeded': len(self.successes),
            'skipped': len(self.skipped),
            'failed': len(self.failures),
            'success_amount': success_total,
            'successes': self.successes,
            'skipped_list': self.skipped,
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
        print(f"Skipped:          {summary['skipped']} (duplicates)")
        print(f"Failed:           {summary['failed']}")
        print(f"Success amount:   KES {summary['success_amount']:,.2f}")
        
        if summary['skipped'] > 0:
            print("\nFirst 5 skipped (duplicates):")
            for skip in summary['skipped_list'][:5]:
                print(f"  ID {skip['transaction_id']}: {skip['reason']}")
        
        if summary['failed'] > 0:
            print("\nFirst 5 failures:")
            for failure in summary['failures'][:5]:
                print(f"  ID {failure['transaction_id']}: {failure['error']}")
        
        print("=" * 70)
