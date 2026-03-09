"""
Account Creation Policy - Controls automatic account creation behavior.

Provides three modes for account creation during migration:
1. MANUAL: Raise error if account missing (user creates manually)
2. CONFIRM: Prompt for confirmation before each account creation
3. AUTOMATIC: Create accounts without confirmation (default for migration)

Version 1.0

Usage:
    # Automatic mode (default for migration)
    policy = AccountCreationPolicy(mode=AccountCreationPolicy.AUTOMATIC)
    
    # Confirm mode (interactive for cautious users)
    policy = AccountCreationPolicy(mode=AccountCreationPolicy.CONFIRM)
    
    # Manual mode (no auto-creation allowed)
    policy = AccountCreationPolicy(mode=AccountCreationPolicy.MANUAL)
    
    # Use with AccountRegistry
    registry = AccountRegistry(client, company, policy=policy)
"""

from typing import Optional, Dict
from enum import Enum


class AccountCreationMode(Enum):
    """Account creation mode enumeration."""
    MANUAL = "manual"
    CONFIRM = "confirm"
    AUTOMATIC = "automatic"


class AccountCreationPolicy:
    """
    Controls account creation behavior across all importers.
    
    Modes:
    - MANUAL: Raise error if account missing (user creates manually in ERPNext)
    - CONFIRM: Prompt for confirmation before each account creation
    - AUTOMATIC: Create accounts without confirmation (default)
    
    Can also set per-account-type overrides for fine-grained control.
    """
    
    # Class constants for mode access
    MANUAL = "manual"
    CONFIRM = "confirm"
    AUTOMATIC = "automatic"
    
    VERSION = "1.0"
    
    def __init__(
        self,
        mode: str = AUTOMATIC,
        overrides: Optional[Dict[str, str]] = None
    ):
        """
        Initialize policy with mode and optional per-type overrides.
        
        Args:
            mode: Default mode (manual, confirm, or automatic)
            overrides: Optional dict of account_type -> mode overrides
                      Example: {"Equity": "manual", "Expense": "automatic"}
        
        Raises:
            ValueError: If invalid mode specified
        """
        valid_modes = {self.MANUAL, self.CONFIRM, self.AUTOMATIC}
        
        if mode not in valid_modes:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}"
            )
        
        self.mode = mode
        self.overrides = overrides or {}
        
        # Validate overrides
        for account_type, override_mode in self.overrides.items():
            if override_mode not in valid_modes:
                raise ValueError(
                    f"Invalid override mode '{override_mode}' for {account_type}. "
                    f"Must be one of: {', '.join(valid_modes)}"
                )
    
    def should_create_account(
        self,
        account_name: str,
        account_type: str,
        parent_account: str
    ) -> bool:
        """
        Determine if account should be created based on policy.
        
        Args:
            account_name: Name of account to create
            account_type: Type of account (Expense, Bank, Equity, etc.)
            parent_account: Parent account in chart
            
        Returns:
            True if account creation should proceed, False otherwise
            
        Raises:
            ValueError: In MANUAL mode when account doesn't exist
        """
        # Check for account-type specific override
        effective_mode = self.overrides.get(account_type, self.mode)
        
        if effective_mode == self.MANUAL:
            raise ValueError(
                f"Account '{account_name}' does not exist.\n"
                f"Policy is MANUAL - please create this account manually in ERPNext:\n"
                f"  Type: {account_type}\n"
                f"  Parent: {parent_account}\n"
                f"Then re-run the import."
            )
        
        if effective_mode == self.CONFIRM:
            # Interactive confirmation
            print(f"\n{'=' * 70}")
            print(f"ACCOUNT CREATION CONFIRMATION")
            print(f"{'=' * 70}")
            print(f"Account Name:   {account_name}")
            print(f"Account Type:   {account_type}")
            print(f"Parent Account: {parent_account}")
            print(f"{'=' * 70}")
            
            response = input("Create this account? [y/N]: ").strip().lower()
            
            if response in ['y', 'yes']:
                print("✓ Confirmed - will create account")
                return True
            else:
                print("✗ Declined - skipping account creation")
                return False
        
        # AUTOMATIC mode - always create
        return True
    
    def get_mode_for_type(self, account_type: str) -> str:
        """
        Get effective mode for a specific account type.
        
        Args:
            account_type: Type of account (Expense, Bank, etc.)
            
        Returns:
            Effective mode (considering overrides)
        """
        return self.overrides.get(account_type, self.mode)
    
    def __repr__(self):
        """String representation of policy."""
        if self.overrides:
            override_str = ", ".join(
                f"{k}={v}" for k, v in self.overrides.items()
            )
            return f"AccountCreationPolicy(mode={self.mode}, overrides={{{override_str}}})"
        return f"AccountCreationPolicy(mode={self.mode})"
