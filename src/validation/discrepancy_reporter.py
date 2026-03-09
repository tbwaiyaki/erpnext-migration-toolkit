"""
Discrepancy Reporter - Document failed imports for user review.

Generates professional discrepancy reports when imports fail due to data quality issues.
Users can review reports and make manual adjustments according to their policies.

Version 1.0: Initial implementation

Usage:
    reporter = DiscrepancyReporter()
    reporter.add_stock_movement_failures(failed_movements, movements_df, items_df)
    reporter.generate_report(output_path)
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class DiscrepancyReporter:
    """
    Generate discrepancy reports for failed imports.
    
    Documents data quality issues without forcing reconciliation.
    Provides users with information to make manual adjustments.
    """
    
    VERSION = "1.0"
    
    def __init__(self):
        """Initialize discrepancy reporter."""
        self.discrepancies = []
        self.summary = {
            'total_failed': 0,
            'by_type': {},
            'by_reason': {}
        }
    
    def add_stock_movement_failures(
        self,
        errors: List[Dict],
        movements_df: pd.DataFrame,
        items_df: pd.DataFrame
    ):
        """
        Add stock movement failures to discrepancy report.
        
        Args:
            errors: List of error dicts from StockMovementImporter
            movements_df: Source movements data
            items_df: Source items data
        """
        for error in errors:
            movement_id = error['movement_id']
            movement = movements_df[movements_df['id'] == movement_id].iloc[0]
            
            # Get item details
            item_id = movement['inventory_item_id']
            item = items_df[items_df['id'] == item_id].iloc[0]
            
            discrepancy = {
                'category': 'Stock Movement',
                'movement_id': movement_id,
                'item_id': item_id,
                'item_name': item['item_name'],
                'movement_type': movement['movement_type'],
                'quantity': movement['quantity'],
                'date': movement['movement_date'],
                'notes': movement.get('notes', ''),
                'error': error['error'][:200],
                'likely_reason': self._diagnose_stock_issue(movement, item),
                'recommended_action': self._recommend_action(movement)
            }
            
            self.discrepancies.append(discrepancy)
            
            # Update summary
            self.summary['total_failed'] += 1
            mtype = movement['movement_type']
            self.summary['by_type'][mtype] = self.summary['by_type'].get(mtype, 0) + 1
    
    def _diagnose_stock_issue(self, movement: pd.Series, item: pd.Series) -> str:
        """
        Diagnose likely reason for stock movement failure.
        
        Args:
            movement: Movement row
            item: Item row
            
        Returns:
            Diagnosis string
        """
        if movement['movement_type'] in ['Breakage', 'Loss', 'Disposal']:
            return (
                f"Insufficient stock: Attempting to issue {movement['quantity']} units "
                f"but insufficient stock available in warehouse. "
                f"Possible causes: (1) Missing purchase records in source data, "
                f"(2) Movements out of chronological order, "
                f"(3) Data entry error in quantity."
            )
        else:
            return "Unknown error - see error message for details."
    
    def _recommend_action(self, movement: pd.Series) -> str:
        """
        Recommend action for user to resolve discrepancy.
        
        Args:
            movement: Movement row
            
        Returns:
            Recommendation string
        """
        if movement['movement_type'] in ['Breakage', 'Loss', 'Disposal']:
            return (
                "OPTION A: Verify source data - check if purchase movements are missing. "
                "If missing, add to source CSV and re-import. "
                "OPTION B: Accept discrepancy - if item was never properly tracked, "
                "make manual stock adjustment in ERPNext to reflect current reality. "
                "OPTION C: Skip - if item is no longer relevant, document and move on."
            )
        else:
            return "Review error message and source data to determine cause."
    
    def generate_report(self, output_path: Path) -> str:
        """
        Generate discrepancy report in markdown format.
        
        Args:
            output_path: Path to save report
            
        Returns:
            Report text
        """
        lines = []
        lines.append("# Data Migration Discrepancy Report")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Total Discrepancies:** {self.summary['total_failed']}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"Total failed imports: **{self.summary['total_failed']}**")
        lines.append("")
        
        if self.summary['by_type']:
            lines.append("### By Movement Type")
            lines.append("")
            for mtype, count in sorted(self.summary['by_type'].items()):
                lines.append(f"- {mtype}: {count}")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        
        # Detailed discrepancies
        lines.append("## Detailed Discrepancies")
        lines.append("")
        
        for i, disc in enumerate(self.discrepancies, 1):
            lines.append(f"### Discrepancy {i}: {disc['item_name']}")
            lines.append("")
            lines.append(f"**Movement ID:** {disc['movement_id']}")
            lines.append(f"**Item ID:** {disc['item_id']}")
            lines.append(f"**Movement Type:** {disc['movement_type']}")
            lines.append(f"**Quantity:** {disc['quantity']}")
            lines.append(f"**Date:** {disc['date']}")
            if disc['notes']:
                lines.append(f"**Notes:** {disc['notes']}")
            lines.append("")
            
            lines.append(f"**Diagnosis:**")
            lines.append(f"{disc['likely_reason']}")
            lines.append("")
            
            lines.append(f"**Recommended Actions:**")
            lines.append(f"{disc['recommended_action']}")
            lines.append("")
            
            lines.append(f"**Technical Error:**")
            lines.append(f"```")
            lines.append(f"{disc['error']}")
            lines.append(f"```")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # User guidance
        lines.append("## User Guidance")
        lines.append("")
        lines.append("These discrepancies represent data quality issues in the source CSV files, ")
        lines.append("not bugs in the migration toolkit. The toolkit has preserved data integrity ")
        lines.append("by refusing to create impossible stock balances (e.g., issuing more items ")
        lines.append("than exist in stock).")
        lines.append("")
        lines.append("**Next Steps:**")
        lines.append("")
        lines.append("1. **Review each discrepancy** listed above")
        lines.append("2. **Investigate source data** - check if purchase records are missing")
        lines.append("3. **Choose resolution approach** per your business policies:")
        lines.append("   - Fix source data and re-import")
        lines.append("   - Make manual adjustment in ERPNext")
        lines.append("   - Accept discrepancy and document")
        lines.append("4. **Update this report** with actions taken and resolutions")
        lines.append("")
        lines.append("**This is the professional approach:** Document discrepancies, don't fabricate data.")
        lines.append("")
        
        report_text = '\n'.join(lines)
        
        # Save report
        with open(output_path, 'w') as f:
            f.write(report_text)
        
        return report_text
    
    def get_summary_text(self) -> str:
        """Get brief summary for console output."""
        if not self.discrepancies:
            return "✓ No discrepancies - all imports successful"
        
        lines = []
        lines.append(f"\n⚠ {self.summary['total_failed']} discrepancies found")
        lines.append(f"  See discrepancy report for details")
        
        if self.summary['by_type']:
            lines.append(f"\n  By type:")
            for mtype, count in sorted(self.summary['by_type'].items()):
                lines.append(f"    {mtype}: {count}")
        
        return '\n'.join(lines)
