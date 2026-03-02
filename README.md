# ERPNext Migration Toolkit

**Generic, reusable migration framework for importing business data into ERPNext.**

## Vision

A professional-grade migration toolkit that:
- Builds from accounting primitives (Money, Account, Tax) upward
- Validates data at every layer
- Works for any industry with configuration changes
- Documents itself through Jupyter notebooks
- Can be extended for specific business domains

## Architecture

**Layer 1: Core Types** — Money, Account, Tax, FiscalPeriod  
**Layer 2: GL Foundation** — Journal Entries, Chart of Accounts  
**Layer 3: AP/AR** — Invoices, Payments, Aging  
**Layer 4: Domain Models** — Industry-specific (Events, Bookings, Inventory)  
**Layer 5: Orchestration** — Full migration sequencing with dependency management

## Project Structure

```
notebooks/          Jupyter notebooks for interactive development
src/
  ├── core/         Primitive types (Money, Account, Tax)
  ├── gl/           General Ledger operations
  ├── documents/    Business documents (Invoice, Payment)
  ├── domain/       Industry-specific models
  ├── erpnext/      ERPNext API client
  └── utils/        Validation, logging utilities
tests/              Comprehensive test suite
data/               Source data (CSV, Excel, QuickBooks exports)
config/             Connection configs, mapping templates
docs/               Architecture and API documentation
```

## Setup

### Prerequisites

- Python 3.10+
- Access to ERPNext instance (v14 or v15)
- Jupyter Notebook or JupyterLab

### Installation

```bash
# Clone repository
git clone git@github.com:yourusername/erpnext-migration-toolkit.git
cd erpnext-migration-toolkit

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .

# Run tests
pytest
```

### ERPNext Connection

Copy config template:
```bash
cp config/erpnext_connection.yaml.example config/erpnext_connection.yaml
```

Edit with your ERPNext credentials:
```yaml
url: https://your-erpnext-instance.com
api_key: your_api_key
api_secret: your_api_secret
```

### Quick Start

```bash
jupyter notebook notebooks/01_core_types.ipynb
```

## Development Workflow

1. **Develop in notebooks** — Interactive exploration and testing
2. **Extract to src/** — Stable code becomes reusable modules
3. **Write tests** — Validate each component
4. **Document** — Architecture decisions in docs/
5. **Commit** — Clean Git history with meaningful messages

## Current Status

**Phase 1: Foundation** (In Progress)
- [x] Project structure
- [ ] Core types (Money, Account, Tax, FiscalPeriod)
- [ ] ERPNext API client wrapper
- [ ] Basic validation framework

**Phase 2: GL Layer**
- [ ] Journal Entry builder
- [ ] Chart of Accounts validation
- [ ] GL reconciliation

**Phase 3: Business Documents**
- [ ] Sales Invoice mapper
- [ ] Purchase Invoice mapper
- [ ] Payment Entry builder

**Phase 4: Domain Models**
- [ ] Wellness centre specific (Events, Room Bookings, Inventory)
- [ ] Generic templates for other industries

## Contributing

This is a learning project developed in the open. Contributions, suggestions, and feedback welcome.

## License

MIT License - See LICENSE file for details

## Contact

Project maintained as part of a homelab experimentation and documentation effort.

## Current Status

**Completed Layers:**

### Layer 1: Core Types ✓
- Money: Decimal-based currency with validation
- Account: Chart of Accounts references with debit/credit logic
- TaxRate: Tax calculations with extraction capabilities
- FiscalPeriod: Date range validation for accounting periods

**Features:**
- Immutable dataclasses
- Full arithmetic operations
- ERPNext format conversion
- Comprehensive validation
- 36 test cases passing

### Layer 2: GL Foundation ✓
- JournalEntryLine: Individual debit/credit lines
- JournalEntry: Complete double-entry transactions
- Balance validation (debits = credits)
- Fiscal period validation
- Multi-line entry support

**Features:**
- Automatic balance checking
- Account type validation hints
- ERPNext Journal Entry format
- Helper functions for common entries
- 13 test cases passing

### Layer 3: Data Validation ✓
- Successfully loaded 947 wellness centre transactions
- Converted all amounts to Money objects
- Mapped 28 transaction categories to Accounts
- Created sample Journal Entries from real data
- Validated fiscal period coverage (FY 2024-2025)

**Financial Summary (Mar 2024 - Feb 2025):**
- Total Income: KES 2,589,840
- Total Expenses: KES 4,363,477
- Net Result: KES -1,773,637 (startup loss)
- Capital Injected: KES 4,000,000

**Architecture Validated:**
Build-from-primitives approach proven successful. All core types work together seamlessly with real-world data.

**Next:** Layer 3 - Business Documents (Sales Invoice, Payment Entry, Purchase Invoice)

### Layer 3: Business Documents ✓
- InvoiceItem: Line items with quantity × rate calculations
- InvoiceTax: Tax lines with automatic calculation
- SalesInvoice: Complete customer invoices with multi-item and multi-tax support

**Features:**
- Automatic total calculations (subtotal + taxes = grand total)
- Multi-item invoice support
- Multi-tax support (VAT, withholding, etc.)
- Fiscal period validation
- ERPNext Sales Invoice format
- Integration with Layers 1 & 2

**Architecture Status:**
All 3 layers working seamlessly together. Money + Account + Tax → JournalEntry → SalesInvoice creates complete ERPNext-ready business documents from primitives.
