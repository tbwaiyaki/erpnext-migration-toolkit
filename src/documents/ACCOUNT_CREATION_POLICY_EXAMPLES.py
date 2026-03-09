# EXAMPLE NOTEBOOK CELLS FOR ACCOUNT CREATION POLICY
# ====================================================
# Add these cells to your notebook BEFORE Phase 1B (AccountRegistry initialization)

# ============================================================================
# CELL: Configure Account Creation Policy
# ============================================================================
from core.account_creation_policy import AccountCreationPolicy

# Choose ONE of the following modes:

# OPTION 1: AUTOMATIC (Default - recommended for initial migration)
# Creates all accounts without confirmation
policy = AccountCreationPolicy(mode=AccountCreationPolicy.AUTOMATIC)

# OPTION 2: CONFIRM (Interactive - prompts for each account)
# Good for cautious users who want to review each account creation
# policy = AccountCreationPolicy(mode=AccountCreationPolicy.CONFIRM)

# OPTION 3: MANUAL (No auto-creation - raises error if account missing)
# User must create accounts manually in ERPNext before import
# policy = AccountCreationPolicy(mode=AccountCreationPolicy.MANUAL)

# OPTION 4: MIXED (Different policies for different account types)
# Example: Manual for Equity, Automatic for Expenses
# policy = AccountCreationPolicy(
#     mode=AccountCreationPolicy.AUTOMATIC,  # Default for most types
#     overrides={
#         "Equity": AccountCreationPolicy.MANUAL,      # Never auto-create equity
#         "Expense": AccountCreationPolicy.AUTOMATIC,  # Always auto-create expenses
#         "Bank": AccountCreationPolicy.CONFIRM        # Confirm bank accounts
#     }
# )

print(f"✓ Account Creation Policy configured: {policy}")

# ============================================================================
# CELL: Initialize AccountRegistry with Policy (REPLACES existing cell 15)
# ============================================================================
from orchestration.account_registry import AccountRegistry

# Create registry with policy
registry = AccountRegistry(
    client=client,
    company="Wellness Centre",
    policy=policy  # Pass the policy here
)

print(f"✓ AccountRegistry initialized with {policy.mode} policy")

# ============================================================================
# DEMONSTRATION: How Each Mode Works
# ============================================================================

# AUTOMATIC MODE:
# ---------------
# policy = AccountCreationPolicy(mode=AccountCreationPolicy.AUTOMATIC)
# registry = AccountRegistry(client, "Wellness Centre", policy=policy)
# account = registry.ensure_account("New Expense", "Expense")
# → Creates "New Expense - WC" immediately, no prompt

# CONFIRM MODE:
# ------------
# policy = AccountCreationPolicy(mode=AccountCreationPolicy.CONFIRM)
# registry = AccountRegistry(client, "Wellness Centre", policy=policy)
# account = registry.ensure_account("New Expense", "Expense")
# → Displays:
#   ======================================================================
#   ACCOUNT CREATION CONFIRMATION
#   ======================================================================
#   Account Name:   New Expense - WC
#   Account Type:   Expense
#   Parent Account: Indirect Expenses - WC
#   ======================================================================
#   Create this account? [y/N]: _
#
# User types 'y' → creates account
# User types 'n' → raises error, stops import

# MANUAL MODE:
# -----------
# policy = AccountCreationPolicy(mode=AccountCreationPolicy.MANUAL)
# registry = AccountRegistry(client, "Wellness Centre", policy=policy)
# account = registry.ensure_account("New Expense", "Expense")
# → Raises ValueError:
#   Account 'New Expense - WC' does not exist.
#   Policy is MANUAL - please create this account manually in ERPNext:
#     Type: Expense
#     Parent: Indirect Expenses - WC
#   Then re-run the import.

# ============================================================================
# RECOMMENDED CONFIGURATION FOR PHASES
# ============================================================================

# PHASE 1 (Sales Invoices & Payments):
# Use AUTOMATIC - payment accounts (M-Pesa, Bank, Cash) should auto-create

# PHASE 2A (Expenses):
# Use AUTOMATIC - expense accounts from YAML config should auto-create

# PHASE 2B (Capital Injections):
# Option 1: AUTOMATIC - let it create equity account
# Option 2: MANUAL with override - review equity accounts manually
#   policy = AccountCreationPolicy(
#       mode=AccountCreationPolicy.AUTOMATIC,
#       overrides={"Equity": AccountCreationPolicy.CONFIRM}
#   )

# PHASE 2C (Savings Transfers):
# Use AUTOMATIC - savings account creation is standard

# ============================================================================
# INTEGRATION WITH CURRENT NOTEBOOK
# ============================================================================

# REPLACE THIS:
# -------------
# from orchestration.account_registry import AccountRegistry
# registry = AccountRegistry(client, "Wellness Centre")

# WITH THIS:
# ----------
# from core.account_creation_policy import AccountCreationPolicy
# from orchestration.account_registry import AccountRegistry
#
# policy = AccountCreationPolicy(mode=AccountCreationPolicy.AUTOMATIC)
# registry = AccountRegistry(client, "Wellness Centre", policy=policy)

# That's it! All importers will now respect the policy.
