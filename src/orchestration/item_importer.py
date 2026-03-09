"""
Item Importer - Import inventory items into ERPNext Item Master.

Handles batch import of physical inventory items (assets, consumables, equipment)
with dynamic Item Group creation and proper configuration.

Version 1.0: Initial implementation
Version 1.2: User-confirmed UOM mappings (no auto-creation)
- Requires UOMPreparation workflow first
- Accepts uom_mappings dict from user review
- Raises error if unmapped UOM found

Usage:
    # Step 1: Prepare UOMs (user review)
    from setup.uom_preparation import UOMPreparation
    uom_prep = UOMPreparation(client)
    analysis = uom_prep.discover_source_uoms(items_df)
    uom_prep.display_review_table(analysis)
    uom_prep.generate_mapping_template(analysis, Path('config/uom_mappings.yaml'))
    # User edits config/uom_mappings.yaml
    mappings = uom_prep.load_mappings(Path('config/uom_mappings.yaml'))
    uom_prep.create_missing_uoms(mappings)
    uom_dict = uom_prep.get_uom_mapping_dict(mappings)
    
    # Step 2: Import items with confirmed mappings
    importer = ItemImporter(client, "Wellness Centre", uom_mappings=uom_dict)
    results = importer.import_batch(items_df, categories_df)
"""

import pandas as pd
from typing import Dict, Optional
from frappeclient import FrappeClient
import time


class ItemImporter:
    """
    Import inventory items into ERPNext Item Master.
    
    Creates Item Groups from categories, then imports items with
    proper stock tracking and reorder level configuration.
    """
    
    VERSION = "1.2"  # User-confirmed UOM mappings (no auto-creation)
    
    def __init__(
        self,
        client: FrappeClient,
        company: str,
        default_warehouse: str = "Stores - WC",
        uom_mappings: Optional[Dict[str, str]] = None
    ):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
            default_warehouse: Default warehouse for stock (with company suffix)
            uom_mappings: Optional dict mapping source UOMs to ERPNext UOMs
                         Example: {'pack': 'Pack', 'piece': 'Nos'}
                         Use UOMPreparation workflow to generate this
        """
        self.client = client
        self.company = company
        self.default_warehouse = default_warehouse
        self.uom_mappings = uom_mappings or {}
        
        self.results = {
            'successful': 0,
            'skipped': 0,
            'failed': 0,
            'errors': [],
            'item_groups_created': 0,
            'duration_seconds': 0.0
        }
        
        # Cache for created item groups
        self._item_groups_cache = {}
    
    def import_batch(
        self,
        items_df: pd.DataFrame,
        categories_df: pd.DataFrame
    ) -> Dict:
        """
        Import batch of inventory items.
        
        Args:
            items_df: Items data
            categories_df: Item categories (for Item Groups)
            
        Returns:
            Results dict with counts and timing
        """
        print(f"[ItemImporter {self.VERSION}]")
        print(f"Importing {len(items_df)} inventory items...")
        print("=" * 70)
        
        start_time = time.time()
        
        # Step 1: Create Item Groups from categories
        self._create_item_groups(categories_df)
        
        # Step 2: Import items
        for idx, row in items_df.iterrows():
            try:
                # Check for duplicates via source_item_id custom field
                source_id = str(row['id'])
                
                existing = self.client.get_list(
                    "Item",
                    filters={"source_item_id": source_id},
                    fields=["name"],
                    limit_page_length=1
                )
                
                if existing:
                    self.results['skipped'] += 1
                    if self.results['skipped'] % 20 == 1:
                        print(f"  ⊘ Skipped {self.results['skipped']} duplicates...")
                    continue
                
                # Build item document
                item_doc = self._build_item_doc(row, categories_df)
                
                # Insert item
                created = self.client.insert(item_doc)
                
                self.results['successful'] += 1
                
                if self.results['successful'] % 20 == 0:
                    print(f"  ✓ Imported {self.results['successful']}...")
                
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'item_id': row['id'],
                    'item_name': row['item_name'],
                    'error': str(e)[:300]
                })
        
        # Calculate timing
        duration = time.time() - start_time
        self.results['duration_seconds'] = round(duration, 2)
        
        print(f"  ✓ Complete: {self.results['successful']} items imported")
        print("=" * 70)
        
        return self.results
    
    def _create_item_groups(self, categories_df: pd.DataFrame):
        """Create Item Groups from inventory categories."""
        print("Creating Item Groups from categories...")
        
        for _, cat in categories_df.iterrows():
            group_name = cat['name']
            
            try:
                # Check if exists
                existing = self.client.get_list(
                    "Item Group",
                    filters={"item_group_name": group_name},
                    limit_page_length=1
                )
                
                if existing:
                    self._item_groups_cache[cat['id']] = group_name
                    continue
                
                # Create Item Group
                group_doc = {
                    "doctype": "Item Group",
                    "item_group_name": group_name,
                    "parent_item_group": "All Item Groups",
                    "is_group": 0
                }
                
                self.client.insert(group_doc)
                self._item_groups_cache[cat['id']] = group_name
                self.results['item_groups_created'] += 1
                
            except Exception as e:
                # Probably already exists
                self._item_groups_cache[cat['id']] = group_name
        
        print(f"  ✓ Created {self.results['item_groups_created']} Item Groups")
    
    def _build_item_doc(
        self,
        row: pd.Series,
        categories_df: pd.DataFrame
    ) -> Dict:
        """
        Build ERPNext Item document.
        
        Args:
            row: Item data row
            categories_df: Categories for Item Group lookup
            
        Returns:
            Item document dict
        """
        # Get Item Group name from category
        item_group = self._item_groups_cache.get(
            row['category_id'],
            'All Item Groups'
        )
        
        # Build item code from name (ERPNext unique identifier)
        # Use source ID to ensure uniqueness
        item_code = f"ITM-{row['id']:04d}"
        
        doc = {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": row['item_name'],
            "item_group": item_group,
            "stock_uom": self._normalize_uom(row.get('unit', 'Unit')),
            
            # Stock management
            "is_stock_item": 1,
            "maintain_stock": 1,
            "include_item_in_manufacturing": 0,
            "is_fixed_asset": 0,
            
            # Reorder configuration
            "reorder_levels": [{
                "warehouse": self.default_warehouse,
                "warehouse_reorder_level": int(row.get('reorder_level', 0)),
                "warehouse_reorder_qty": int(row.get('reorder_level', 0))
            }] if pd.notna(row.get('reorder_level')) and row.get('reorder_level') > 0 else [],
            
            # Valuation
            "valuation_rate": float(row.get('unit_cost', 0)) if pd.notna(row.get('unit_cost')) else 0,
            "valuation_method": "FIFO",
            
            # Default warehouse
            "default_warehouse": self.default_warehouse,
            
            # Description
            "description": row.get('description', row['item_name']),
            
            # Custom field for duplicate detection
            "source_item_id": str(row['id'])
        }
        
        return doc
    
    def _normalize_uom(self, uom: str) -> str:
        """
        Map source UOM to ERPNext UOM using user-confirmed mappings.
        
        This does NOT auto-create UOMs. User must run UOMPreparation workflow
        first to review and confirm all UOMs.
        
        Args:
            uom: Source UOM string
            
        Returns:
            ERPNext UOM name
            
        Raises:
            ValueError: If UOM not in mappings (user forgot to prepare UOMs)
        """
        # Check if mapping exists
        if uom in self.uom_mappings:
            return self.uom_mappings[uom]
        
        # Try normalized version
        normalized = uom.strip().capitalize()
        if normalized in self.uom_mappings:
            return self.uom_mappings[normalized]
        
        # No mapping found - this is an error (user didn't prepare UOMs)
        raise ValueError(
            f"UOM '{uom}' not found in mappings. "
            f"Run UOMPreparation workflow first to review and map all UOMs."
        )
    
    def get_summary(self) -> str:
        """Get import summary report."""
        lines = []
        lines.append("=" * 70)
        lines.append("ITEM IMPORT SUMMARY")
        lines.append("=" * 70)
        lines.append(f"Item Groups Created:  {self.results['item_groups_created']}")
        lines.append(f"Items Imported:       {self.results['successful']}")
        lines.append(f"Skipped (duplicates): {self.results['skipped']}")
        lines.append(f"Failed:               {self.results['failed']}")
        lines.append(f"Duration:             {self.results['duration_seconds']} seconds")
        
        if self.results['errors']:
            lines.append(f"\nFirst 5 errors:")
            for err in self.results['errors'][:5]:
                lines.append(f"  Item {err['item_id']} ({err['item_name']}): {err['error'][:100]}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
