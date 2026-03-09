"""
Savings Transfer Importer - Imports savings transfers as Journal Entries.

Creates proper double-entry accounting for savings movements:
- Debit: Savings account (savings increases)
- Credit: Operating account (operating cash/bank decreases)

Uses AccountRegistry for dynamic account discovery and includes duplicate detection.

Version 1.0: Initial implementation with AccountRegistry integration

Usage:
    registry = AccountRegistry(client, "Wellness Centre")
    importer = SavingsTransferImporter(client, "Wellness Centre", registry)
    results = importer.import_savings_transfers(transactions_df)
"""

from typing import Dict, List, Optional
import pandas as pd
from frappeclient import FrappeClient


class SavingsTransferImporter:
    """
    Import savings transfer transactions as Journal Entries in ERPNext.
    
    Creates proper double-entry accounting:
    - Debit: Savings account
    - Credit: Operating payment account (via AccountRegistry)
    
    Features:
    - Duplicate detection via source_transaction_id
    - Dynamic payment account discovery
    - Configurable savings account
    - Auto-submit with validation
    """
    
    VERSION = "1.0-accountregistry-duplicate-detection"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        registry,
        savings_account: str = None
    ):
        """
        Initialize savings transfer importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
            registry: AccountRegistry instance for dynamic account lookup
            savings_account: Savings account name (default: auto-detected)
        """
        self.client = client
        self.company = company
        self.registry = registry
        self.savings_account = savings_account or self._detect_savings_account()
        self.successes = []
        self.failures = []
        self.skipped = []
    
    def _detect_savings_account(self) -> str:
        """
        Ensure savings account exists.
        
        Tries to find existing account, creates if missing.
        Uses AccountRegistry.ensure_account() for idempotent creation.
        
        Returns:
            Savings account name
        """
        try:
            # Get company suffix from registry
            suffix = self.registry.suffix
            
            # Try common names first (search for existing)
            common_names = [
                f"Savings Account - {suffix}",
                f"Savings - {suffix}",
                f"Reserve Fund - {suffix}"
            ]
            
            for name in common_names:
                try:
                    accounts = self.client.get_list(
                        "Account",
                        filters={"name": name, "company": self.company},
                        limit_page_length=1
                    )
                    if accounts:
                        return name
                except Exception:
                    continue
            
            # Search for account with "savings" in name
            accounts = self.client.get_list(
                "Account",
                filters={
                    "company": self.company,
                    "is_group": 0
                },
                fields=["name", "account_name"],
                limit_page_length=100
            )
            
            for acc in accounts:
                if 'saving' in acc['account_name'].lower():
                    return acc['name']
            
            # No savings account found - create "Savings Account"
            print(f"  ℹ No savings account found, creating 'Savings Account - {suffix}'")
            account_name = self.registry.ensure_account(
                "Savings Account",
                account_type="Bank",
                parent_account=f"Bank Accounts - {suffix}"
            )
            print(f"  ✓ Created savings account: {account_name}")
            return account_name
            
        except Exception as e:
            raise ValueError(f"Could not ensure savings account exists: {e}")
    
    def build_journal_entry(
        self,
        transaction: dict
    ) -> dict:
        """
        Build Journal Entry payload for savings transfer.
        
        Creates double-entry:
        - Debit: Savings account (savings increases)
        - Credit: Operating payment account (operating cash/bank decreases)
        
        Args:
            transaction: Transaction record from CSV
            
        Returns:
            ERPNext Journal Entry payload
        """
        # Get operating payment account via AccountRegistry
        payment_method = transaction.get('payment_method', 'Bank Transfer')
        try:
            operating_account = self.registry.get_payment_account(payment_method)
        except ValueError as e:
            # Default to Bank Transfer for savings transfers
            print(f"⚠ Payment method '{payment_method}' not found, using Bank Transfer")
            operating_account = self.registry.get_payment_account('Bank Transfer')
        
        # Build journal entry
        amount = float(transaction['amount'])
        
        payload = {
            "doctype": "Journal Entry",
            "company": self.company,
            "posting_date": transaction['transaction_date'],
            "voucher_type": "Journal Entry",
            "user_remark": transaction.get('description', 'Savings transfer'),
            "source_transaction_id": str(transaction['id']),
            "accounts": [
                {
                    # Debit savings account (savings increases)
                    "account": self.savings_account,
                    "debit_in_account_currency": amount,
                    "credit_in_account_currency": 0,
                    "reference_type": "",
                    "reference_name": ""
                },
                {
                    # Credit operating account (operating cash/bank decreases)
                    "account": operating_account,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": amount,
                    "reference_type": "",
                    "reference_name": ""
                }
            ]
        }
        
        return payload
    
    def import_savings_transfers(
        self,
        transactions_df: pd.DataFrame,
        auto_submit: bool = True
    ) -> Dict[str, any]:
        """
        Import savings transfer transactions as Journal Entries.
        
        Args:
            transactions_df: DataFrame with savings transactions
            auto_submit: Submit journal entries after creation
            
        Returns:
            Dictionary with import results
        """
        # Filter to savings type only
        savings = transactions_df[
            transactions_df['type'] == 'savings'
        ].copy()
        
        print(f"Importing {len(savings)} savings transfer transactions...")
        print("=" * 70)
        
        for i, (_, tx) in enumerate(savings.iterrows(), 1):
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
                    print(f"  ⊘ Skipped (duplicate): {tx['transaction_date']} - KES {tx['amount']:,.0f}")
                    continue
            except Exception:
                # Custom field might not exist yet - proceed with import
                pass
            
            try:
                # Build payload
                payload = self.build_journal_entry(tx.to_dict())
                
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
                    'date': tx['transaction_date']
                })
                
                print(f"  ✓ {tx['transaction_date']}: KES {tx['amount']:,.0f} → {je_name}")
                
                # Progress indicator every 5 records
                if i % 5 == 0 or i == len(savings):
                    print(f"  Progress: {i}/{len(savings)} "
                          f"(✓ {len(self.successes)}, ⊘ {len(self.skipped)}, ✗ {len(self.failures)})")
                
            except Exception as e:
                error_msg = str(e)[:200]
                self.failures.append({
                    'transaction_id': transaction_id,
                    'date': tx['transaction_date'],
                    'amount': tx['amount'],
                    'error': error_msg
                })
                print(f"  ✗ {tx['transaction_date']}: {error_msg}")
        
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
            'failures': self.failures,
            'savings_account_used': self.savings_account
        }
    
    def print_summary(self):
        """Print formatted import summary."""
        summary = self.get_summary()
        
        print("\n" + "=" * 70)
        print("SAVINGS TRANSFER IMPORT SUMMARY")
        print("=" * 70)
        print(f"Total attempted:  {summary['total_attempted']}")
        print(f"Succeeded:        {summary['succeeded']}")
        print(f"Skipped:          {summary['skipped']} (duplicates)")
        print(f"Failed:           {summary['failed']}")
        print(f"Success amount:   KES {summary['success_amount']:,.2f}")
        print(f"Savings account:  {summary['savings_account_used']}")
        
        if summary['skipped'] > 0:
            print("\nSkipped (duplicates):")
            for skip in summary['skipped_list']:
                print(f"  ID {skip['transaction_id']}: {skip['reason']}")
        
        if summary['failed'] > 0:
            print("\nFailures:")
            for failure in summary['failures']:
                print(f"  ID {failure['transaction_id']}: {failure['error']}")
        
        print("=" * 70)
