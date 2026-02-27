"""
Payment Entry for recording payments received or made.

Handles payment allocation to invoices and bank reconciliation.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional
from enum import Enum

from core.money import Money
from core.account import Account


class PaymentType(Enum):
    """Type of payment"""
    RECEIVE = "Receive"  # Payment from customer
    PAY = "Pay"          # Payment to supplier
    INTERNAL = "Internal Transfer"  # Between bank accounts


@dataclass
class PaymentEntry:
    """
    Payment entry for recording money received or paid.
    
    Links payments to invoices and manages bank reconciliation.
    
    Examples:
        >>> # Customer payment
        >>> payment = PaymentEntry(
        ...     payment_type=PaymentType.RECEIVE,
        ...     party="John Doe",
        ...     party_type="Customer",
        ...     paid_to=Account("Mobile Money - WC", AccountType.BANK),
        ...     paid_from=Account("Debtors - WC", AccountType.RECEIVABLE),
        ...     amount=Money(17400, "KES"),
        ...     posting_date=date(2024, 3, 16),
        ...     reference_no="MPesa-ABC123"
        ... )
        
        >>> # Supplier payment
        >>> payment = PaymentEntry(
        ...     payment_type=PaymentType.PAY,
        ...     party="Acme Supplies Ltd",
        ...     party_type="Supplier",
        ...     paid_from=Account("KCB - WC", AccountType.BANK),
        ...     paid_to=Account("Creditors - WC", AccountType.PAYABLE),
        ...     amount=Money(8700, "KES"),
        ...     posting_date=date(2024, 3, 20),
        ...     reference_no="Cheque-001"
        ... )
    """
    
    payment_type: PaymentType
    party: str  # Customer or Supplier name
    party_type: str  # "Customer" or "Supplier"
    paid_from: Account  # Source account
    paid_to: Account    # Destination account
    amount: Money
    posting_date: date
    reference_no: Optional[str] = None
    reference_date: Optional[date] = None
    remarks: Optional[str] = None
    
    def __post_init__(self):
        """Validate payment after initialization"""
        # Validate payment type
        if not isinstance(self.payment_type, PaymentType):
            raise ValueError(f"payment_type must be PaymentType enum, got {type(self.payment_type)}")
        
        # Validate party
        if not self.party or not self.party.strip():
            raise ValueError("Party cannot be empty")
        
        # Validate party type
        if self.party_type not in ("Customer", "Supplier"):
            raise ValueError(f"party_type must be 'Customer' or 'Supplier', got {self.party_type}")
        
        # Validate accounts
        if not isinstance(self.paid_from, Account):
            raise ValueError(f"paid_from must be Account instance, got {type(self.paid_from)}")
        if not isinstance(self.paid_to, Account):
            raise ValueError(f"paid_to must be Account instance, got {type(self.paid_to)}")
        
        # Validate amount
        if not isinstance(self.amount, Money):
            raise ValueError(f"amount must be Money instance, got {type(self.amount)}")
        if not self.amount.is_positive():
            raise ValueError(f"Payment amount must be positive, got {self.amount}")
        
        # Validate posting date
        if not isinstance(self.posting_date, date):
            raise ValueError(f"posting_date must be date object, got {type(self.posting_date)}")
        
        # Set reference_date to posting_date if not provided
        if self.reference_date is None:
            object.__setattr__(self, 'reference_date', self.posting_date)
    
    def __str__(self) -> str:
        """Human-readable format"""
        return (
            f"{self.payment_type.value}: {self.amount} "
            f"from {self.paid_from.base_name} to {self.paid_to.base_name}"
        )
    
    @property
    def currency(self) -> str:
        """Get currency of this payment"""
        return self.amount.currency
    
    @property
    def is_receipt(self) -> bool:
        """Check if this is a receipt (payment received)"""
        return self.payment_type == PaymentType.RECEIVE
    
    @property
    def is_payment(self) -> bool:
        """Check if this is a payment (payment made)"""
        return self.payment_type == PaymentType.PAY
    
    def to_erpnext_format(self) -> dict:
        """
        Convert to ERPNext Payment Entry format.
        
        Returns:
            Dict suitable for ERPNext API submission
        """
        payload = {
            "doctype": "Payment Entry",
            "payment_type": self.payment_type.value,
            "party_type": self.party_type,
            "party": self.party,
            "posting_date": self.posting_date.isoformat(),
            "paid_from": self.paid_from.name,
            "paid_to": self.paid_to.name,
            "paid_amount": self.amount.to_erpnext_format(),
            "received_amount": self.amount.to_erpnext_format(),
        }
        
        # Add optional fields
        if self.reference_no:
            payload["reference_no"] = self.reference_no
        
        if self.reference_date:
            payload["reference_date"] = self.reference_date.isoformat()
        
        if self.remarks:
            payload["remarks"] = self.remarks
        
        return payload
    
    @classmethod
    def from_erpnext(cls, doc: dict) -> 'PaymentEntry':
        """Create PaymentEntry from ERPNext document"""
        from core.account import AccountType
        
        # Parse payment type
        payment_type_str = doc.get("payment_type", "Receive")
        payment_type = PaymentType(payment_type_str)
        
        # Create accounts (simplified - would need lookup in production)
        paid_from = Account(doc["paid_from"], AccountType.BANK)
        paid_to = Account(doc["paid_to"], AccountType.BANK)
        
        # Get amount
        amount = Money.from_erpnext(
            doc.get("paid_amount") or doc.get("received_amount"),
            doc.get("currency", "KES")
        )
        
        return cls(
            payment_type=payment_type,
            party=doc["party"],
            party_type=doc["party_type"],
            paid_from=paid_from,
            paid_to=paid_to,
            amount=amount,
            posting_date=date.fromisoformat(doc["posting_date"]),
            reference_no=doc.get("reference_no"),
            reference_date=date.fromisoformat(doc["reference_date"]) if doc.get("reference_date") else None,
            remarks=doc.get("remarks"),
        )


def create_customer_payment(
    customer: str,
    amount: Money,
    bank_account: Account,
    posting_date: date,
    reference_no: Optional[str] = None,
) -> PaymentEntry:
    """
    Helper to create customer payment (receipt).
    
    Args:
        customer: Customer name
        amount: Payment amount
        bank_account: Bank account receiving payment
        posting_date: Payment date
        reference_no: Optional reference (M-Pesa, cheque number, etc.)
        
    Returns:
        PaymentEntry for customer payment
    """
    from core.account import AccountType
    
    return PaymentEntry(
        payment_type=PaymentType.RECEIVE,
        party=customer,
        party_type="Customer",
        paid_from=Account("Debtors - WC", AccountType.RECEIVABLE),
        paid_to=bank_account,
        amount=amount,
        posting_date=posting_date,
        reference_no=reference_no,
    )


def create_supplier_payment(
    supplier: str,
    amount: Money,
    bank_account: Account,
    posting_date: date,
    reference_no: Optional[str] = None,
) -> PaymentEntry:
    """
    Helper to create supplier payment.
    
    Args:
        supplier: Supplier name
        amount: Payment amount
        bank_account: Bank account making payment
        posting_date: Payment date
        reference_no: Optional reference (cheque number, etc.)
        
    Returns:
        PaymentEntry for supplier payment
    """
    from core.account import AccountType
    
    return PaymentEntry(
        payment_type=PaymentType.PAY,
        party=supplier,
        party_type="Supplier",
        paid_from=bank_account,
        paid_to=Account("Creditors - WC", AccountType.PAYABLE),
        amount=amount,
        posting_date=posting_date,
        reference_no=reference_no,
    )
