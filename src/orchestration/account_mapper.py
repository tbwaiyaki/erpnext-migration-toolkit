"""
Account Mapper - Maps transaction categories to Chart of Accounts.

Configuration-driven approach - works for any business scenario by
modifying the YAML config file.

Usage:
    mapper = AccountMapper(config_file, company="Wellness Centre")
    mappings = mapper.map_categories(categories_df, transaction_type='expense')
    results = mapper.create_missing_accounts(client, mappings)
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from frappeclient import FrappeClient


class AccountMapper:
    """
    Maps transaction categories to ERPNext Chart of Accounts.
    
    Loads mapping rules from YAML config and applies them to category data.
    Creates missing accounts in ERPNext when needed.
    """
    
    def __init__(self, config_file: Path, company: str):
        """
        Initialize mapper with configuration.
        
        Args:
            config_file: Path to account_mappings.yaml
            company: Company name (e.g., "Wellness Centre")
        """
        self.config_file = Path(config_file)
        self.company = company
        self.config = self._load_config()
        self.company_suffix = self.config.get('company_suffix', 'WC')
        
    def _load_config(self) -> dict:
        """Load YAML configuration file."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
            
        with open(self.config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def _format_account_name(self, template: str, category_name: str) -> str:
        """
        Format account name from template.
        
        Supports placeholders:
        - {category_name}: Exact category name
        - {company}: Company name
        
        Args:
            template: Account name template
            category_name: Category name to substitute
            
        Returns:
            Formatted account name with company suffix
        """
        name = template.replace("{category_name}", category_name)
        name = name.replace("{company}", self.company)
        
        # Add company suffix if not already present
        if not name.endswith(f" - {self.company_suffix}"):
            name = f"{name} - {self.company_suffix}"
            
        return name
    
    def _match_pattern(self, category_name: str, patterns: List[str]) -> bool:
        """
        Check if category name matches any pattern.
        
        Args:
            category_name: Category name to test
            patterns: List of patterns to match
            
        Returns:
            True if category matches any pattern
        """
        for pattern in patterns:
            if pattern == "*":  # Wildcard matches everything
                return True
            if pattern.lower() in category_name.lower():
                return True
        return False
    
    def map_category(
        self, 
        category_name: str, 
        transaction_type: str = 'expense'
    ) -> Dict[str, any]:
        """
        Map a single category to an account.
        
        Args:
            category_name: Name of transaction category
            transaction_type: Type of transaction (expense/income/equity)
            
        Returns:
            Dictionary with account mapping details
        """
        # Get mapping rules for this transaction type
        mapping_key = f"{transaction_type}_mappings"
        rules = self.config.get(mapping_key, [])
        
        if not rules:
            raise ValueError(f"No mapping rules found for {transaction_type}")
        
        # Try to match category against rules
        for rule in rules:
            patterns = rule.get('pattern', [])
            
            if self._match_pattern(category_name, patterns):
                account_name = self._format_account_name(
                    rule['account_name'], 
                    category_name
                )
                parent = self._format_account_name(
                    rule['parent'],
                    category_name
                )
                
                return {
                    'category_name': category_name,
                    'erpnext_account': account_name,
                    'parent_account': parent,
                    'create_if_missing': rule.get('create_if_missing', True),
                    'matched_pattern': patterns[0] if patterns else 'default'
                }
        
        # Should never reach here if config has wildcard rule
        raise ValueError(f"No mapping rule matched for: {category_name}")
    
    def map_categories(
        self,
        categories_df: pd.DataFrame,
        transaction_type: str = 'expense'
    ) -> pd.DataFrame:
        """
        Map all categories in a dataframe to accounts.
        
        Args:
            categories_df: DataFrame with 'name' and 'type' columns
            transaction_type: Filter by this transaction type
            
        Returns:
            DataFrame with mapping results
        """
        # Filter by transaction type
        filtered = categories_df[categories_df['type'] == transaction_type].copy()
        
        mappings = []
        for _, row in filtered.iterrows():
            mapping = self.map_category(row['name'], transaction_type)
            mapping['category_id'] = row['id']
            mappings.append(mapping)
        
        return pd.DataFrame(mappings)
    
    def create_missing_accounts(
        self,
        client: FrappeClient,
        mappings: pd.DataFrame
    ) -> Dict[str, List[str]]:
        """
        Create accounts that don't exist in ERPNext.
        
        Args:
            client: Authenticated FrappeClient
            mappings: DataFrame from map_categories()
            
        Returns:
            Dictionary with 'created', 'existed', 'errors' lists
        """
        results = {
            'created': [],
            'existed': [],
            'errors': []
        }
        
        # Filter to only accounts that need creation
        to_create = mappings[mappings['create_if_missing'] == True].copy()
        
        for _, row in to_create.iterrows():
            account_name = row['erpnext_account']
            category = row['category_name']
            
            try:
                # Check if account exists
                existing = client.get_list(
                    "Account",
                    filters={"name": account_name},
                    limit_page_length=1
                )
                
                if existing:
                    results['existed'].append(category)
                    continue
                
                # Extract account name without suffix for ERPNext
                base_name = account_name.replace(f" - {self.company_suffix}", "")
                
                # Create new account
                payload = {
                    "doctype": "Account",
                    "account_name": base_name,
                    "parent_account": row['parent_account'],
                    "company": self.company,
                    "is_group": 0,
                    "account_type": ""  # Blank for expense accounts
                }
                
                result = client.insert(payload)
                results['created'].append(category)
                
            except Exception as e:
                results['errors'].append({
                    'category': category,
                    'account': account_name,
                    'error': str(e)[:150]
                })
        
        return results
    
    def get_account_for_category(
        self,
        category_id: int,
        mappings: pd.DataFrame
    ) -> Optional[str]:
        """
        Get ERPNext account name for a category ID.
        
        Args:
            category_id: Category ID from source data
            mappings: DataFrame from map_categories()
            
        Returns:
            ERPNext account name or None
        """
        match = mappings[mappings['category_id'] == category_id]
        if len(match) > 0:
            return match.iloc[0]['erpnext_account']
        return None
