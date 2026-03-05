"""
ERPNext Site Snapshot - Jupyter Integration
Simple wrapper for snapshot/restore operations in notebooks
"""

import subprocess
from pathlib import Path
from typing import List, Optional


class Site:
    """
    ERPNext site snapshot manager for Jupyter notebooks.
    
    Example:
        site = Site("well.rosslyn.cloud")
        snapshot_id = site.snapshot()
        site.list_snapshots()
        site.restore(snapshot_id, confirm=True)
    """
    
    def __init__(self, site_name: str):
        self.site_name = site_name
        self.tool_path = "src/utils/erpnext-site-snapshot"
        
        if not Path(self.tool_path).exists():
            raise FileNotFoundError(f"Snapshot tool not found at {self.tool_path}")
    
    def snapshot(self, label: Optional[str] = None) -> str:
        """Create snapshot of site. Returns snapshot ID."""
        print(f"Creating snapshot of {self.site_name}...")
        
        result = subprocess.run(
            [self.tool_path, self.site_name, "snapshot"],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(result.stdout)
        
        # Extract snapshot ID from output
        for line in result.stdout.split('\n'):
            if "Snapshot created:" in line:
                return line.split(':')[1].strip()
        
        return None
    
    def list_snapshots(self, limit: int = 20) -> List[str]:
        """List available snapshots."""
        result = subprocess.run(
            [self.tool_path, self.site_name, "list"],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(result.stdout)
        
        # Parse snapshot IDs
        snapshots = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith('Snapshots') and not line.startswith('No snapshots'):
                parts = line.split()
                if parts:
                    snapshots.append(parts[0])
        
        return snapshots
    
    def restore(self, snapshot_id: str, confirm: bool = False):
        """Restore site from snapshot."""
        if not confirm:
            print(f"⚠️  WARNING: Restore {self.site_name} to {snapshot_id}")
            print("   All current data will be replaced!")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled")
                return
        
        print(f"Restoring {self.site_name} from {snapshot_id}...")
        print("This will take 1-3 minutes...")
        
        result = subprocess.run(
            [self.tool_path, self.site_name, "restore", snapshot_id],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(result.stdout)
    
    def __repr__(self):
        return f"Site('{self.site_name}')"


class SafeImport:
    """
    Context manager for safe imports with automatic rollback.
    
    Example:
        site = Site("well.rosslyn.cloud")
        
        with SafeImport(site, "customer-import"):
            import_customers()
            # Auto-restores on error
    """
    
    def __init__(self, site: Site, label: str = "auto-backup"):
        self.site = site
        self.label = label
        self.snapshot_id = None
    
    def __enter__(self):
        print("=" * 60)
        print(f"SafeImport: Creating backup before {self.label}")
        print("=" * 60)
        self.snapshot_id = self.site.snapshot(self.label)
        print(f"✓ Backup created: {self.snapshot_id}\n")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            print()
            print("=" * 60)
            print(f"✗ Import failed: {exc_val}")
            print("=" * 60)
            print(f"Restoring from backup: {self.snapshot_id}")
            self.site.restore(self.snapshot_id, confirm=True)
            print("✓ Site restored to pre-import state")
            print("=" * 60)
            return False
        else:
            print()
            print("=" * 60)
            print(f"✓ Import successful - backup: {self.snapshot_id}")
            print("=" * 60)
            return True
