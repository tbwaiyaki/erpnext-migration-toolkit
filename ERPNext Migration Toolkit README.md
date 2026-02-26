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
