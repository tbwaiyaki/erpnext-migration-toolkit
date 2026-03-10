"""
License Importer - Import compliance documents as License records.

Tracks business licenses, permits, certificates, and regulatory documents
with expiry dates and renewal tracking.

Version 1.0: Initial implementation

Architecture:
- Creates custom License DocType in ERPNext
- Imports historical compliance documents with original dates
- Tracks expiry and renewal requirements
- No date manipulation - historical reality preserved

Usage:
    importer = LicenseImporter(client, "Wellness Centre")
    results = importer.import_batch(compliance_df)
"""

import pandas as pd
from typing import Dict
from frappeclient import FrappeClient
import time


class LicenseImporter:
    """
    Import compliance documents as License records.
    
    Creates and uses a custom License DocType for compliance tracking.
    """
    
    VERSION = "1.0"
    
    def __init__(
        self,
        client: FrappeClient,
        company: str
    ):
        """
        Initialize importer.
        
        Args:
            client: Authenticated FrappeClient
            company: Company name
        """
        self.client = client
        self.company = company
        
        self.results = {
            'successful': 0,
            'skipped': 0,
            'failed': 0,
            'errors': [],
            'duration_seconds': 0.0,
            'doctype_created': False
        }
    
    def ensure_license_doctype(self):
        """
        Ensure License custom DocType exists.
        
        Creates the DocType if it doesn't exist.
        """
        try:
            # Check if License DocType exists
            existing = self.client.get_list(
                "DocType",
                filters={"name": "License"},
                limit_page_length=1
            )
            
            if existing:
                print("  ✓ License DocType already exists")
                return
            
            # Create License DocType
            doctype = {
                "doctype": "DocType",
                "name": "License",
                "module": "Setup",
                "custom": 1,
                "is_submittable": 0,
                "track_changes": 1,
                "fields": [
                    {
                        "fieldname": "document_type",
                        "label": "Document Type",
                        "fieldtype": "Data",
                        "reqd": 1,
                        "in_list_view": 1
                    },
                    {
                        "fieldname": "document_number",
                        "label": "Document Number",
                        "fieldtype": "Data",
                        "reqd": 1,
                        "in_list_view": 1
                    },
                    {
                        "fieldname": "issuing_authority",
                        "label": "Issuing Authority",
                        "fieldtype": "Data",
                        "in_list_view": 0
                    },
                    {
                        "fieldname": "section_break_1",
                        "fieldtype": "Section Break",
                        "label": "Dates"
                    },
                    {
                        "fieldname": "issue_date",
                        "label": "Issue Date",
                        "fieldtype": "Date",
                        "in_list_view": 0
                    },
                    {
                        "fieldname": "expiry_date",
                        "label": "Expiry Date",
                        "fieldtype": "Date",
                        "in_list_view": 1
                    },
                    {
                        "fieldname": "column_break_1",
                        "fieldtype": "Column Break"
                    },
                    {
                        "fieldname": "status",
                        "label": "Status",
                        "fieldtype": "Select",
                        "options": "Active\nExpired\nRenewing\nCancelled",
                        "default": "Active",
                        "in_list_view": 1
                    },
                    {
                        "fieldname": "is_expired",
                        "label": "Is Expired",
                        "fieldtype": "Check",
                        "read_only": 1,
                        "in_list_view": 0
                    },
                    {
                        "fieldname": "section_break_2",
                        "fieldtype": "Section Break",
                        "label": "Financial"
                    },
                    {
                        "fieldname": "renewal_fee",
                        "label": "Renewal Fee",
                        "fieldtype": "Currency",
                        "options": "Company:company:default_currency"
                    },
                    {
                        "fieldname": "section_break_3",
                        "fieldtype": "Section Break",
                        "label": "Additional Information"
                    },
                    {
                        "fieldname": "notes",
                        "label": "Notes",
                        "fieldtype": "Text"
                    },
                    {
                        "fieldname": "company",
                        "label": "Company",
                        "fieldtype": "Link",
                        "options": "Company",
                        "default": self.company,
                        "hidden": 1
                    }
                ],
                "permissions": [
                    {
                        "role": "System Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1
                    }
                ]
            }
            
            self.client.insert(doctype)
            self.results['doctype_created'] = True
            print("  ✓ Created License DocType")
            
        except Exception as e:
            if "already exists" in str(e).lower():
                print("  ✓ License DocType already exists")
            else:
                raise
    
    def import_batch(self, compliance_df: pd.DataFrame) -> Dict:
        """
        Import compliance documents as License records.
        
        Args:
            compliance_df: Compliance documents data
            
        Returns:
            Results dict
        """
        start_time = time.time()
        
        print(f"[LicenseImporter {self.VERSION}]")
        print(f"Importing {len(compliance_df)} compliance documents...")
        print("=" * 70)
        
        # Ensure License DocType exists
        self.ensure_license_doctype()
        
        # Import licenses
        for idx, doc in compliance_df.iterrows():
            try:
                # Check for duplicate
                if self._is_duplicate(doc['document_number']):
                    self.results['skipped'] += 1
                    continue
                
                # Create license record
                license_rec = self._create_license(doc)
                
                self.results['successful'] += 1
                
                if (idx + 1) % 3 == 0:
                    print(f"  ✓ Imported {idx + 1}...")
                    
            except Exception as e:
                self.results['failed'] += 1
                self.results['errors'].append({
                    'document_type': doc['document_type'],
                    'document_number': doc['document_number'],
                    'error': str(e)
                })
        
        self.results['duration_seconds'] = round(time.time() - start_time, 2)
        
        print(f"  ✓ Complete: {self.results['successful']} licenses imported")
        print("=" * 70)
        
        return self.results
    
    def _is_duplicate(self, document_number: str) -> bool:
        """Check if license already imported."""
        try:
            existing = self.client.get_list(
                "License",
                filters={"document_number": document_number},
                limit_page_length=1
            )
            return len(existing) > 0
        except:
            return False
    
    def _create_license(self, doc: pd.Series) -> Dict:
        """
        Create License record.
        
        Args:
            doc: Compliance document row
            
        Returns:
            Created license dict
        """
        # Build license record
        license_rec = {
            "doctype": "License",
            "document_type": str(doc['document_type']),
            "document_number": str(doc['document_number']),
            "issuing_authority": str(doc['issuing_authority']),
            "status": str(doc['status']).capitalize(),
            "company": self.company
        }
        
        # Add dates (handle NaN)
        if pd.notna(doc.get('issue_date')):
            license_rec['issue_date'] = str(doc['issue_date'])
        
        if pd.notna(doc.get('expiry_date')):
            license_rec['expiry_date'] = str(doc['expiry_date'])
            
            # Check if expired (compare date strings)
            from datetime import datetime
            expiry = datetime.strptime(str(doc['expiry_date']), '%Y-%m-%d').date()
            today = datetime.now().date()
            license_rec['is_expired'] = 1 if expiry < today else 0
        
        # Add renewal fee (handle NaN)
        if pd.notna(doc.get('renewal_fee')):
            license_rec['renewal_fee'] = float(doc['renewal_fee'])
        
        # Add notes (handle NaN)
        if pd.notna(doc.get('notes')):
            license_rec['notes'] = str(doc['notes'])
        
        # Create license
        created = self.client.insert(license_rec)
        
        return created
    
    def get_summary(self) -> str:
        """Get import summary."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("LICENSE IMPORT SUMMARY")
        lines.append("=" * 70)
        
        if self.results['doctype_created']:
            lines.append("License DocType:      Created")
        
        lines.append(f"Total Imported:       {self.results['successful']}")
        lines.append(f"Skipped (duplicates): {self.results['skipped']}")
        
        if self.results['failed'] > 0:
            lines.append(f"Discrepancies:        {self.results['failed']} (see report)")
        else:
            lines.append(f"Discrepancies:        0")
        
        lines.append(f"Duration:             {self.results['duration_seconds']} seconds")
        
        if self.results['errors']:
            lines.append(f"\nℹ️  {len(self.results['errors'])} discrepancies found")
            lines.append(f"   Discrepancy report will be generated automatically.")
        
        lines.append("=" * 70)
        return "\n".join(lines)
