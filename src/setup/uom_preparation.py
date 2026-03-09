"""
UOM Preparation Workflow - Review and map source UOMs before item import.

This workflow ensures users review all UOMs from source data and either:
1. Map to existing ERPNext UOMs
2. Create new UOMs (with confirmation)
3. Consolidate variants (pack/package/pkg → Pack)

Version 1.0: Initial implementation

Usage:
    # Step 1: Discover unique UOMs from source data
    uom_prep = UOMPreparation(client)
    source_uoms = uom_prep.discover_source_uoms(items_df)
    
    # Step 2: Review and map
    uom_prep.display_review_table(source_uoms)
    
    # Step 3: Apply mappings (manual YAML config)
    uom_mappings = uom_prep.load_mappings('config/uom_mappings.yaml')
    uom_prep.create_missing_uoms(uom_mappings)
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Set
from frappeclient import FrappeClient
import yaml


class UOMPreparation:
    """
    Prepare and review UOMs before item import.
    
    Discovers unique UOMs from source data, shows what exists in ERPNext,
    and helps user create mappings/new UOMs.
    """
    
    VERSION = "1.0"
    
    def __init__(self, client: FrappeClient):
        """
        Initialize UOM preparation.
        
        Args:
            client: Authenticated FrappeClient
        """
        self.client = client
        self._erpnext_uoms_cache = None
    
    def discover_source_uoms(self, items_df: pd.DataFrame) -> pd.DataFrame:
        """
        Discover all unique UOMs from source items data.
        
        Args:
            items_df: Items DataFrame with 'unit' column
            
        Returns:
            DataFrame with UOM analysis:
            - source_uom: Original UOM from CSV
            - item_count: How many items use this UOM
            - exists_in_erpnext: Whether it exists
            - suggested_mapping: Recommended ERPNext UOM
        """
        # Get unique UOMs with counts
        uom_counts = items_df['unit'].value_counts()
        
        # Get existing ERPNext UOMs
        erpnext_uoms = self._get_erpnext_uoms()
        
        # Build analysis table
        analysis = []
        for uom, count in uom_counts.items():
            normalized = uom.strip().capitalize()
            
            exists = normalized in erpnext_uoms
            suggestion = normalized if exists else self._suggest_mapping(normalized, erpnext_uoms)
            
            analysis.append({
                'source_uom': uom,
                'normalized': normalized,
                'item_count': count,
                'exists_in_erpnext': exists,
                'suggested_mapping': suggestion if not exists else normalized
            })
        
        return pd.DataFrame(analysis).sort_values('item_count', ascending=False)
    
    def _get_erpnext_uoms(self) -> Set[str]:
        """Get all existing UOMs from ERPNext."""
        if self._erpnext_uoms_cache is None:
            uoms = self.client.get_list(
                "UOM",
                fields=["uom_name"],
                limit_page_length=500
            )
            self._erpnext_uoms_cache = {u['uom_name'] for u in uoms}
        
        return self._erpnext_uoms_cache
    
    def _suggest_mapping(self, source_uom: str, erpnext_uoms: Set[str]) -> str:
        """
        Suggest ERPNext UOM mapping based on similarity.
        
        Args:
            source_uom: Source UOM to map
            erpnext_uoms: Set of existing ERPNext UOMs
            
        Returns:
            Suggested ERPNext UOM or "CREATE NEW"
        """
        # Common mappings (fuzzy matching)
        fuzzy_map = {
            'piece': 'Nos',
            'pieces': 'Nos',
            'pcs': 'Nos',
            'pc': 'Nos',
            'unit': 'Nos',
            'units': 'Nos',
            'each': 'Nos',
            'pack': 'Pack',
            'packs': 'Pack',
            'package': 'Pack',
            'pkg': 'Pack',
            'set': 'Set',
            'sets': 'Set',
            'box': 'Box',
            'boxes': 'Box',
            'kg': 'Kg',
            'kgs': 'Kg',
            'kilogram': 'Kg',
            'gram': 'Gram',
            'grams': 'Gram',
            'litre': 'Litre',
            'litres': 'Litre',
            'liter': 'Litre',
            'meter': 'Meter',
            'metre': 'Meter',
            'meters': 'Meter'
        }
        
        lower_uom = source_uom.lower()
        
        # Check fuzzy map
        if lower_uom in fuzzy_map:
            suggested = fuzzy_map[lower_uom]
            if suggested in erpnext_uoms:
                return suggested
        
        # Check if capitalized version exists
        if source_uom in erpnext_uoms:
            return source_uom
        
        return "CREATE NEW"
    
    def display_review_table(self, analysis_df: pd.DataFrame):
        """
        Display UOM review table for user decision.
        
        Args:
            analysis_df: DataFrame from discover_source_uoms()
        """
        print("=" * 90)
        print("UOM REVIEW - ACTION REQUIRED")
        print("=" * 90)
        print("\nSource UOMs found in items data:")
        print()
        
        for _, row in analysis_df.iterrows():
            status = "✓ EXISTS" if row['exists_in_erpnext'] else "✗ MISSING"
            print(f"  {row['source_uom']:15s} → {row['normalized']:15s} [{status:12s}] "
                  f"(used by {row['item_count']:2d} items)")
            
            if not row['exists_in_erpnext']:
                if row['suggested_mapping'] != "CREATE NEW":
                    print(f"      Suggestion: Map to '{row['suggested_mapping']}'")
                else:
                    print(f"      Suggestion: Create new UOM '{row['normalized']}'")
        
        print()
        print("=" * 90)
        print("NEXT STEPS:")
        print("=" * 90)
        print("1. Review the table above")
        print("2. Decide for each MISSING UOM:")
        print("   - Map to existing ERPNext UOM? (e.g., 'pack' → 'Nos')")
        print("   - Create new UOM? (e.g., 'Pack' if packaging is important)")
        print("3. Update config/uom_mappings.yaml with decisions")
        print("4. Run create_missing_uoms() to apply")
        print("=" * 90)
    
    def generate_mapping_template(
        self,
        analysis_df: pd.DataFrame,
        output_file: Path
    ):
        """
        Generate YAML mapping template for user to edit.
        
        Args:
            analysis_df: DataFrame from discover_source_uoms()
            output_file: Path to save YAML file
        """
        mappings = {
            'uom_mappings': {},
            'create_new_uoms': []
        }
        
        for _, row in analysis_df.iterrows():
            if not row['exists_in_erpnext']:
                source = row['source_uom']
                suggestion = row['suggested_mapping']
                
                if suggestion == "CREATE NEW":
                    # Add to create list with comment
                    mappings['create_new_uoms'].append({
                        'uom_name': row['normalized'],
                        'used_by_items': int(row['item_count'])
                    })
                else:
                    # Add to mapping with suggestion
                    mappings['uom_mappings'][source] = {
                        'maps_to': suggestion,
                        'items_affected': int(row['item_count'])
                    }
        
        # Write YAML with comments
        with open(output_file, 'w') as f:
            f.write("# UOM Mappings Configuration\n")
            f.write("# Generated by UOM Preparation Workflow\n")
            f.write("#\n")
            f.write("# Instructions:\n")
            f.write("# 1. Review each mapping below\n")
            f.write("# 2. Change 'maps_to' value if you want different mapping\n")
            f.write("# 3. Move items from 'create_new_uoms' to 'uom_mappings' if you want to map instead\n")
            f.write("# 4. Run create_missing_uoms() to apply\n")
            f.write("#\n\n")
            
            yaml.dump(mappings, f, default_flow_style=False, sort_keys=False)
        
        print(f"✓ Generated mapping template: {output_file}")
        print(f"  Edit this file to finalize your UOM decisions")
    
    def load_mappings(self, config_file: Path) -> Dict:
        """
        Load user-edited UOM mappings from YAML.
        
        Args:
            config_file: Path to uom_mappings.yaml
            
        Returns:
            Mappings dict
        """
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def create_missing_uoms(self, mappings: Dict) -> Dict:
        """
        Create new UOMs based on user-confirmed mappings.
        
        Args:
            mappings: Dict from load_mappings()
            
        Returns:
            Results dict
        """
        results = {'created': 0, 'skipped': 0, 'errors': []}
        
        create_list = mappings.get('create_new_uoms', [])
        
        print(f"Creating {len(create_list)} new UOMs...")
        
        for uom_config in create_list:
            uom_name = uom_config['uom_name']
            
            try:
                # Check if exists
                existing = self.client.get_list(
                    "UOM",
                    filters={"uom_name": uom_name},
                    limit_page_length=1
                )
                
                if existing:
                    results['skipped'] += 1
                    continue
                
                # Create UOM
                uom_doc = {
                    "doctype": "UOM",
                    "uom_name": uom_name,
                    "enabled": 1
                }
                
                self.client.insert(uom_doc)
                results['created'] += 1
                print(f"  ✓ Created: {uom_name}")
                
            except Exception as e:
                results['errors'].append({'uom': uom_name, 'error': str(e)})
        
        print(f"\n✓ Created {results['created']} UOMs")
        if results['skipped']:
            print(f"  Skipped {results['skipped']} (already exist)")
        if results['errors']:
            print(f"  Failed {len(results['errors'])}")
        
        return results
    
    def get_uom_mapping_dict(self, mappings: Dict) -> Dict[str, str]:
        """
        Get simple dict for ItemImporter: source_uom -> erpnext_uom.
        
        Args:
            mappings: Dict from load_mappings()
            
        Returns:
            Simple mapping dict
        """
        mapping_dict = {}
        
        # Add explicit mappings
        for source, config in mappings.get('uom_mappings', {}).items():
            mapping_dict[source] = config['maps_to']
        
        # Add created UOMs (map to themselves)
        for uom_config in mappings.get('create_new_uoms', []):
            uom_name = uom_config['uom_name']
            mapping_dict[uom_name.lower()] = uom_name
        
        return mapping_dict
