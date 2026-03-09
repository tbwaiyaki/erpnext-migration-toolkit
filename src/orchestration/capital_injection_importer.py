"""
Capital Injection Importer - Imports owner capital injections as Journal Entries.

Creates proper double-entry accounting for equity investments:
- Debit: Payment account (cash/bank increases)
- Credit: Capital/Equity account (owner equity increases)

Uses AccountRegistry for dynamic account discovery and includes duplicate detection.

Version 1.0: Initial implementation with AccountRegistry integration

Usage:
    registry = AccountRegistry(client, "Wellness Centre")
    importer = CapitalInjectionImporter(client, "Wellness Centre", registry)
    results = importer.import_capital_injections(transactions_df)
"""

from typing import Dict, List
import pandas as pd
from frappeclient import FrappeClient


class CapitalInjectionImporter:
    """
    Import capital injection transactions as Journal Entries in ERPNext.
    
    Creates proper double-entry accounting:
    - Debit: Payment account (via AccountRegistry)
    - Credit: Capital Stock/Owner Equity account
    
    Features:
    - Duplicate detection via source_transaction_id
    - Dynamic payment account discovery
    - Configurable equity account
    - Auto-submit with validation
    """
    
    VERSION = "1.0-accountregistry-duplicate-detection"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        registry,
        equity_account: str = None
    ):
        """
        Initialize capital injection importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name (e.g., "Wellness Centre")
            registry: AccountRegistry instance for dynamic account lookup
            equity_account: Equity account name (default: auto-detected)
        """
        self.client = client
        self.company = company
        self.registry = registry
        self.equity_account = equity_account or self._detect_equity_account()
        self.successes = []
        self.failures = []
        self.skipped = []
    
    def _detect_equity_account(self) -> str:
        """
        Ensure equity/capital account exists.
        
        Tries to find existing account, creates if missing.
        Uses AccountRegistry.ensure_account() for idempotent creation.
        
        Returns:
            Equity account name
        """
        try:
            # Get company suffix from registry
            suffix = self.registry.suffix
            
            # Try common names first (search for existing)
            common_names = [
                f"Capital Stock - {suffix}",
                f"Owner's Equity - {suffix}",
                f"Equity - {suffix}"
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
            
            # Check if any equity account exists
            equity_accounts = self.client.get_list(
                "Account",
                filters={
                    "account_type": "Equity",
                    "company": self.company,
                    "is_group": 0
                },
                fields=["name"],
                limit_page_length=1
            )
            
            if equity_accounts:
                return equity_accounts[0]['name']
            
            # No equity account found - create "Capital Stock"
            print(f"  ℹ No equity account found, creating 'Capital Stock - {suffix}'")
            account_name = self.registry.ensure_account(
                "Capital Stock",
                account_type="Equity",
                parent_account=f"Equity - {suffix}"
            )
            print(f"  ✓ Created equity account: {account_name}")
            return account_name
            
        except Exception as e:
            raise ValueError(f"Could not ensure equity account exists: {e}")
    
    def build_journal_entry(
        self,
        transaction: dict
    ) -> dict:
        """
        Build Journal Entry payload for capital injection.
        
        Creates double-entry:
        - Debit: Payment account (cash/bank increases)
        - Credit: Equity account (owner equity increases)
        
        Args:
            transaction: Transaction record from CSV
            
        Returns:
            ERPNext Journal Entry payload
        """
        # Get payment account via AccountRegistry
        payment_method = transaction.get('payment_method', 'Bank Transfer')
        try:
            payment_account = self.registry.get_payment_account(payment_method)
        except ValueError as e:
            # Default to Bank Transfer for capital injections
            print(f"⚠ Payment method '{payment_method}' not found, using Bank Transfer")
            payment_account = self.registry.get_payment_account('Bank Transfer')
        
        # Build journal entry
        amount = float(transaction['amount'])
        
        payload = {
            "doctype": "Journal Entry",
            "company": self.company,
            "posting_date": transaction['transaction_date'],
            "voucher_type": "Journal Entry",
            "user_remark": transaction.get('description', 'Owner capital injection'),
            "source_transaction_id": str(transaction['id']),
            "accounts": [
                {
                    # Debit payment account (cash/bank increases)
                    "account": payment_account,
                    "debit_in_account_currency": amount,
                    "credit_in_account_currency": 0,
                    "reference_type": "",
                    "reference_name": ""
                },
                {
                    # Credit equity account (owner equity increases)
                    "account": self.equity_account,
                    "debit_in_account_currency": 0,
                    "credit_in_account_currency": amount,
                    "reference_type": "",
                    "reference_name": ""
                }
            ]
        }
        
        return payload
    
    def import_capital_injections(
        self,
        transactions_df: pd.DataFrame,
        auto_submit: bool = True
    ) -> Dict[str, any]:
        """
        Import capital injection transactions as Journal Entries.
        
        Args:
            transactions_df: DataFrame with capital injection transactions
            auto_submit: Submit journal entries after creation
            
        Returns:
            Dictionary with import results
        """
        # Filter to capital_injection type only
        capital = transactions_df[
            transactions_df['type'] == 'capital_injection'
        ].copy()
        
        print(f"Importing {len(capital)} capital injection transactions...")
        print("=" * 70)
        
        for i, (_, tx) in enumerate(capital.iterrows(), 1):
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
            'equity_account_used': self.equity_account
        }
    
    def print_summary(self):
        """Print formatted import summary."""
        summary = self.get_summary()
        
        print("\n" + "=" * 70)
        print("CAPITAL INJECTION IMPORT SUMMARY")
        print("=" * 70)
        print(f"Total attempted:  {summary['total_attempted']}")
        print(f"Succeeded:        {summary['succeeded']}")
        print(f"Skipped:          {summary['skipped']} (duplicates)")
        print(f"Failed:           {summary['failed']}")
        print(f"Success amount:   KES {summary['success_amount']:,.2f}")
        print(f"Equity account:   {summary['equity_account_used']}")
        
        if summary['skipped'] > 0:
            print("\nSkipped (duplicates):")
            for skip in summary['skipped_list']:
                print(f"  ID {skip['transaction_id']}: {skip['reason']}")
        
        if summary['failed'] > 0:
            print("\nFailures:")
            for failure in summary['failures']:
                print(f"  ID {failure['transaction_id']}: {failure['error']}")
        
        print("=" * 70)
