"""
ERPNext Submitter for wellness centre migration.

Integrates professional patterns from trial code with migration toolkit.
Supports Docker network access with Host header.
"""

import logging
from datetime import datetime
from typing import Optional

from frappeclient import FrappeClient
from documents.sales_invoice import SalesInvoice


class ImportResult:
    """
    Track import results with detailed statistics.
    
    Provides comprehensive reporting of successes, failures, and skips.
    """
    
    def __init__(self, doctype: str):
        self.doctype = doctype
        self.total = 0
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0
        self.successes = []
        self.failures = []
        self.skips = []
        self.started_at = datetime.now()
        self.finished_at = None
    
    def finish(self):
        """Mark import as complete"""
        self.finished_at = datetime.now()
    
    @property
    def duration_seconds(self):
        """Calculate duration in seconds"""
        if self.finished_at:
            return (self.finished_at - self.started_at).seconds
        return 0
    
    def summary(self) -> str:
        """
        Generate human-readable summary report.
        
        Returns:
            Formatted summary string
        """
        lines = [
            f"\n{'='*70}",
            f"IMPORT SUMMARY — {self.doctype}",
            f"{'='*70}",
            f"  Total records:  {self.total}",
            f"  Succeeded:      {self.succeeded}",
            f"  Skipped:        {self.skipped}  (already existed)",
            f"  Failed:         {self.failed}",
            f"  Duration:       {self.duration_seconds}s",
        ]
        
        if self.failures:
            lines.append(f"\nFAILURES ({len(self.failures)}):")
            for f in self.failures[:10]:
                error_msg = f['error'][:100] if len(f['error']) > 100 else f['error']
                lines.append(f"  - [{f['record_id']}] {error_msg}")
            if len(self.failures) > 10:
                lines.append(f"  ... and {len(self.failures) - 10} more")
        
        if self.skips:
            lines.append(f"\nSKIPPED ({len(self.skips)}):")
            for s in self.skips[:5]:
                lines.append(f"  - [{s['record_id']}] {s['reason']}")
            if len(self.skips) > 5:
                lines.append(f"  ... and {len(self.skips) - 5} more")
        
        lines.append(f"{'='*70}\n")
        return "\n".join(lines)


class ERPNextSubmitter:
    """
    Submit invoices to ERPNext with proper error handling.
    
    Features:
    - Duplicate detection before insert
    - Validation before sending  
    - Document submission (Draft → Submitted)
    - Comprehensive logging
    - Per-record error handling
    - Docker network support with Host header
    
    Examples:
        >>> # For Docker network (your setup)
        >>> client = FrappeClient("http://erpnext-frontend:8080")
        >>> client.authenticate(api_key, api_secret)
        >>> client.session.headers.update({"Host": "well.rosslyn.cloud"})
        >>> 
        >>> submitter = ERPNextSubmitter(client)
        >>> result = submitter.submit_invoices(invoices)
    """
    
    def __init__(self, client: FrappeClient, logger: Optional[logging.Logger] = None):
        """
        Initialize submitter.
        
        Args:
            client: Authenticated FrappeClient (with Host header if needed)
            logger: Optional logger (creates one if not provided)
        """
        self.client = client
        self.logger = logger or self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Create basic logger if not provided"""
        logger = logging.getLogger("erpnext_submitter")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(levelname)-8s | %(message)s"
            ))
            logger.addHandler(handler)
        
        return logger
    
    def _record_exists(
        self,
        doctype: str,
        filters: dict
    ) -> tuple[bool, str]:
        """
        Check if record exists in ERPNext.
        
        Args:
            doctype: ERPNext doctype name
            filters: Search filters
            
        Returns:
            (exists, existing_name)
        """
        try:
            results = self.client.get_list(
                doctype,
                filters=filters,
                fields=["name"],
                limit_page_length=1
            )
            
            if results:
                return True, results[0].get("name", "")
            return False, ""
            
        except Exception as e:
            self.logger.warning(f"Existence check failed: {e}")
            return False, ""
    
    def _validate_invoice(self, invoice: SalesInvoice) -> Optional[str]:
        """
        Validate invoice before submission.
        
        Args:
            invoice: SalesInvoice instance
            
        Returns:
            Error message if invalid, None if valid
        """
        # Check customer
        if not invoice.customer or not invoice.customer.strip():
            return "Missing customer name"
        
        # Check items
        if not invoice.items:
            return "Invoice has no items"
        
        for i, item in enumerate(invoice.items):
            if not item.description:
                return f"Item {i+1} missing description"
            if item.quantity <= 0:
                return f"Item {i+1} has invalid quantity: {item.quantity}"
            if item.rate.is_negative():
                return f"Item {i+1} has negative rate"
        
        # Check date
        if not invoice.posting_date:
            return "Missing posting date"
        
        return None  # Valid
    
    def _submit_document(self, doctype: str, name: str) -> bool:
        """
        Submit document in ERPNext (Draft → Submitted).
        
        Args:
            doctype: Document type
            name: Document name
            
        Returns:
            True if submitted, False if failed
        """
        try:
            self.client.update({
                "doctype": doctype,
                "name": name,
                "docstatus": 1  # Submit
            })
            return True
        except Exception as e:
            self.logger.warning(f"Submit failed for {name}: {e}")
            return False
    
    def submit_invoice(
        self,
        invoice: SalesInvoice,
        check_duplicates: bool = True,
        auto_submit: bool = False
    ) -> dict:
        """
        Submit single invoice to ERPNext.
        
        Args:
            invoice: SalesInvoice instance
            check_duplicates: Check if invoice exists first
            auto_submit: Submit after insert (Draft → Submitted)
            
        Returns:
            Result dict with status and details
        """
        # Validate
        error = self._validate_invoice(invoice)
        if error:
            return {
                'status': 'failed',
                'customer': invoice.customer,
                'error': f"Validation failed: {error}"
            }
        
        # Check duplicates
        if check_duplicates:
            filters = {
                "customer": invoice.customer,
                "posting_date": invoice.posting_date.isoformat()
            }
            
            exists, existing_name = self._record_exists("Sales Invoice", filters)
            if exists:
                return {
                    'status': 'skipped',
                    'customer': invoice.customer,
                    'reason': f"Already exists: {existing_name}"
                }
        
        # Convert to ERPNext format
        try:
            payload = invoice.to_erpnext_format()
        except Exception as e:
            return {
                'status': 'failed',
                'customer': invoice.customer,
                'error': f"Format conversion failed: {e}"
            }
        
        # Insert
        try:
            doc = self.client.insert(payload)
            erpnext_name = doc.get('name')
            
            # Auto-submit if requested
            submitted = False
            if auto_submit:
                submitted = self._submit_document("Sales Invoice", erpnext_name)
            
            return {
                'status': 'success',
                'customer': invoice.customer,
                'erpnext_name': erpnext_name,
                'total': invoice.grand_total,
                'submitted': submitted
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'customer': invoice.customer,
                'error': str(e)[:200]
            }
    
    def submit_invoices(
        self,
        invoices: list[SalesInvoice],
        check_duplicates: bool = True,
        auto_submit: bool = False
    ) -> ImportResult:
        """
        Submit multiple invoices to ERPNext.
        
        Args:
            invoices: List of SalesInvoice instances
            check_duplicates: Check for existing invoices
            auto_submit: Submit after insert
            
        Returns:
            ImportResult with detailed statistics
        """
        result = ImportResult("Sales Invoice")
        result.total = len(invoices)
        
        self.logger.info(f"Submitting {len(invoices)} invoices to ERPNext...")
        self.logger.info(f"  Check duplicates: {check_duplicates}")
        self.logger.info(f"  Auto-submit: {auto_submit}")
        
        for i, invoice in enumerate(invoices, 1):
            # Submit single invoice
            outcome = self.submit_invoice(invoice, check_duplicates, auto_submit)
            
            # Track result
            if outcome['status'] == 'success':
                result.succeeded += 1
                result.successes.append({
                    'record_id': invoice.customer,
                    'erpnext_name': outcome['erpnext_name'],
                    'total': outcome['total']
                })
            
            elif outcome['status'] == 'skipped':
                result.skipped += 1
                result.skips.append({
                    'record_id': invoice.customer,
                    'reason': outcome['reason']
                })
            
            else:  # failed
                result.failed += 1
                result.failures.append({
                    'record_id': invoice.customer,
                    'error': outcome['error']
                })
            
            # Progress indicator
            if i % 10 == 0 or i == len(invoices):
                self.logger.info(
                    f"  Progress: {i}/{len(invoices)} "
                    f"(✓ {result.succeeded}, ⊘ {result.skipped}, ✗ {result.failed})"
                )
        
        result.finish()
        return result
