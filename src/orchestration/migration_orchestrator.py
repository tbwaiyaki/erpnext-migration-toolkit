"""
Migration Orchestrator for wellness centre data.

Coordinates CSV loading → Domain models → Invoices → ERPNext.
"""

from pathlib import Path
from typing import Optional

from orchestration.csv_loader import WellnessCentreDataLoader
from orchestration.invoice_generator import InvoiceGenerator
from core.money import Money


class MigrationOrchestrator:
    """
    Orchestrate complete migration workflow.
    
    Handles: Load → Transform → Validate → Report
    
    Examples:
        >>> orchestrator = MigrationOrchestrator(Path('/mnt/project'))
        >>> 
        >>> # Small test batch
        >>> results = orchestrator.process_batch(limit=10)
        >>> 
        >>> # Generate report
        >>> report = orchestrator.generate_report(results)
        >>> print(report)
    """
    
    def __init__(self, data_dir: Path):
        """
        Initialize orchestrator.
        
        Args:
            data_dir: Path to CSV data directory
        """
        self.data_dir = Path(data_dir)
        self.loader = WellnessCentreDataLoader(self.data_dir)
        self.generator = InvoiceGenerator()
    
    def process_batch(self, limit: Optional[int] = None) -> dict:
        """
        Process batch of records.
        
        Workflow:
        1. Load CSVs → Domain models
        2. Generate invoices
        3. Calculate totals
        4. Return results
        
        Args:
            limit: Optional limit per data source (for testing)
            
        Returns:
            Dict with domain models, invoices, and summary
        """
        print(f"Starting batch processing (limit: {limit or 'ALL'})...")
        
        # Step 1: Load data
        print("\n1. Loading CSV data...")
        data = self.loader.load_all(limit=limit)
        
        print(f"   Loaded {len(data['events'])} events")
        print(f"   Loaded {len(data['rooms'])} room bookings")
        print(f"   Loaded {len(data['eggs'])} egg sales")
        
        # Step 2: Generate invoices
        print("\n2. Generating invoices...")
        invoices = self.generator.generate_all(
            events=data['events'],
            rooms=data['rooms'],
            eggs=data['eggs']
        )
        
        print(f"   Generated {invoices['summary']['events']} event invoices")
        print(f"   Generated {invoices['summary']['rooms']} room invoices")
        print(f"   Generated {invoices['summary']['eggs']} egg invoices")
        print(f"   Total: {invoices['summary']['total']} invoices")
        
        if invoices['summary']['errors'] > 0:
            print(f"   Errors: {invoices['summary']['errors']}")
        
        # Step 3: Calculate totals
        print("\n3. Calculating totals...")
        
        event_totals = self.generator.get_totals(invoices['event_invoices'])
        room_totals = self.generator.get_totals(invoices['room_invoices'])
        egg_totals = self.generator.get_totals(invoices['egg_invoices'])
        
        all_invoices = (
            invoices['event_invoices'] +
            invoices['room_invoices'] +
            invoices['egg_invoices']
        )
        
        combined_totals = self.generator.get_totals(all_invoices)
        
        print(f"   Event revenue: {event_totals['grand_total']}")
        print(f"   Room revenue: {room_totals['grand_total']}")
        print(f"   Egg revenue: {egg_totals['grand_total']}")
        print(f"   Total revenue: {combined_totals['grand_total']}")
        
        # Return complete results
        return {
            'domain_models': data,
            'invoices': invoices,
            'totals': {
                'events': event_totals,
                'rooms': room_totals,
                'eggs': egg_totals,
                'combined': combined_totals,
            },
            'errors': self.generator.errors,
        }
    
    def generate_report(self, results: dict) -> str:
        """
        Generate human-readable migration report.
        
        Args:
            results: Results from process_batch()
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("WELLNESS CENTRE MIGRATION REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Data loaded
        lines.append("DATA LOADED:")
        data = results['domain_models']
        lines.append(f"  Events:        {len(data['events']):>4}")
        lines.append(f"  Room Bookings: {len(data['rooms']):>4}")
        lines.append(f"  Egg Sales:     {len(data['eggs']):>4}")
        lines.append("")
        
        # Invoices generated
        lines.append("INVOICES GENERATED:")
        summary = results['invoices']['summary']
        lines.append(f"  Event Invoices: {summary['events']:>4}")
        lines.append(f"  Room Invoices:  {summary['rooms']:>4}")
        lines.append(f"  Egg Invoices:   {summary['eggs']:>4}")
        lines.append(f"  Total:          {summary['total']:>4}")
        lines.append("")
        
        # Revenue breakdown
        lines.append("REVENUE BREAKDOWN:")
        totals = results['totals']
        
        lines.append(f"  Events:")
        lines.append(f"    Subtotal: {totals['events']['subtotal']}")
        lines.append(f"    Tax:      {totals['events']['tax']}")
        lines.append(f"    Total:    {totals['events']['grand_total']}")
        lines.append("")
        
        lines.append(f"  Rooms:")
        lines.append(f"    Subtotal: {totals['rooms']['subtotal']}")
        lines.append(f"    Tax:      {totals['rooms']['tax']}")
        lines.append(f"    Total:    {totals['rooms']['grand_total']}")
        lines.append("")
        
        lines.append(f"  Eggs:")
        lines.append(f"    Subtotal: {totals['eggs']['subtotal']}")
        lines.append(f"    Tax:      {totals['eggs']['tax']}")
        lines.append(f"    Total:    {totals['eggs']['grand_total']}")
        lines.append("")
        
        # Combined totals
        lines.append("COMBINED TOTALS:")
        lines.append(f"  Subtotal:    {totals['combined']['subtotal']}")
        lines.append(f"  Tax:         {totals['combined']['tax']}")
        lines.append(f"  Grand Total: {totals['combined']['grand_total']}")
        lines.append("")
        
        # Errors
        if results['errors']:
            lines.append(f"ERRORS: {len(results['errors'])}")
            for error in results['errors'][:5]:  # Show first 5
                lines.append(f"  {error['type']}: {error['name']} - {error['error']}")
            if len(results['errors']) > 5:
                lines.append(f"  ... and {len(results['errors']) - 5} more")
            lines.append("")
        else:
            lines.append("ERRORS: None")
            lines.append("")
        
        lines.append("=" * 70)
        lines.append("STATUS: Complete")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def export_erpnext_payloads(self, results: dict, output_dir: Path) -> dict:
        """
        Export ERPNext-ready JSON payloads.
        
        Args:
            results: Results from process_batch()
            output_dir: Directory to write JSON files
            
        Returns:
            Dict with file paths and counts
        """
        import json
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        all_invoices = (
            results['invoices']['event_invoices'] +
            results['invoices']['room_invoices'] +
            results['invoices']['egg_invoices']
        )
        
        # Export all invoices to single JSON file
        payloads = [inv.to_erpnext_format() for inv in all_invoices]
        
        output_file = output_dir / 'sales_invoices.json'
        with open(output_file, 'w') as f:
            json.dump(payloads, f, indent=2, default=str)
        
        return {
            'file': str(output_file),
            'count': len(payloads),
        }
