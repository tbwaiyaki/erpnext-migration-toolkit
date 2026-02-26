# Getting Started

## Quick Start (5 minutes)

### 1. Clone and setup

```bash
git clone git@github.com:yourusername/erpnext-migration-toolkit.git
cd erpnext-migration-toolkit

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development

# Install package in editable mode
pip install -e .
```

### 2. Configure ERPNext connection

```bash
cp config/erpnext_connection.yaml.example config/erpnext_connection.yaml
```

Edit `config/erpnext_connection.yaml`:
```yaml
url: https://your-erpnext.com
api_key: your_api_key_here
api_secret: your_api_secret_here
```

**Getting API credentials:**
1. Log into ERPNext
2. Go to: User menu → My Settings → API Access
3. Generate API Key/Secret pair
4. Copy credentials to config file

### 3. Test connection

```bash
jupyter notebook notebooks/01_core_types.ipynb
```

Run the setup cells to verify everything works.

## Development Workflow

### Working with notebooks

**Pattern:**
1. Develop/test in notebook interactively
2. Extract stable code to `src/` modules
3. Import modules back into notebook
4. Write unit tests for extracted code

**Example:**

```python
# In notebook: Experiment
from decimal import Decimal

class Money:
    def __init__(self, amount, currency):
        self.amount = Decimal(str(amount))
        self.currency = currency
    # ... test different approaches ...

# Once working: Extract to src/core/money.py
# Then in notebook: Import and use
from core.money import Money
m = Money(100, "USD")
```

### Auto-reload in notebooks

Add to notebook setup cells:
```python
%load_ext autoreload
%autoreload 2
```

This reloads modules automatically when you edit `src/` files.

### Running tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_core/test_money.py

# With coverage report
pytest --cov=src --cov-report=html
```

View coverage: `open htmlcov/index.html`

### Code quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

## Project Structure Tour

```
erpnext-migration-toolkit/
├── notebooks/              ← Start here: Interactive development
│   └── 01_core_types.ipynb
├── src/                    ← Extracted, reusable code
│   ├── core/              ← Core types (Money, Account, Tax)
│   ├── documents/         ← Business documents (Invoice, Payment)
│   └── erpnext/           ← ERPNext API client
├── tests/                 ← Unit and integration tests
├── data/                  ← Source data (CSV/Excel files)
│   └── wellness_centre/   ← Example: wellness centre data
└── config/                ← Connection and mapping configs
```

## Understanding the Layers

### Layer 1: Core Types (Current Phase)

**File:** `notebooks/01_core_types.ipynb`

Develop fundamental types:
- `Money`: Currency amounts with validation
- `Account`: Chart of accounts references
- `Tax`: Tax calculations
- `FiscalPeriod`: Date range validation

**Why start here?**  
Every higher-level type depends on these. Get the foundation right.

### Layer 2: GL Foundation (Next Phase)

**File:** `notebooks/02_gl_foundation.ipynb`

Build journal entries:
- Double-entry bookkeeping
- Debit = Credit validation
- Account type checking

### Layer 3-5: Build upward

Once foundation is solid, build business documents, domain models, and orchestration.

## Common Tasks

### Adding a new domain model

1. Create module: `src/domain/your_domain/__init__.py`
2. Create notebook: `notebooks/04_your_domain.ipynb`
3. Develop domain-specific types
4. Extract to src when stable
5. Write tests

### Importing data

```python
# In notebook
import pandas as pd
from pathlib import Path

# Load source data
DATA_DIR = Path("../data/your_data")
df = pd.read_csv(DATA_DIR / "transactions.csv")

# Transform using your domain models
from domain.your_domain import Transaction
transactions = [Transaction.from_csv_row(row) for _, row in df.iterrows()]

# Import to ERPNext
from erpnext.client import ERPNextClient
client = ERPNextClient.from_config()
for txn in transactions:
    client.create_document(txn.to_erpnext_format())
```

### Debugging ERPNext API

```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test API call
from erpnext.client import ERPNextClient
client = ERPNextClient.from_config()
response = client.get_doc("Customer", "CUST-00001")
print(response)
```

## Troubleshooting

### Import errors

**Problem:** `ModuleNotFoundError: No module named 'core'`

**Solution:** Make sure you're in the repository root and installed package:
```bash
pip install -e .
```

### ERPNext connection fails

**Problem:** `Connection refused` or `404 Not Found`

**Solutions:**
1. Check URL in config (include https://)
2. Verify API credentials
3. Test URL in browser first
4. Check ERPNext logs for errors

### Git authentication in Jupyter

**Problem:** Can't push to GitHub from Jupyter terminal

**Solution:** Link SSH keys (run once per container restart):
```bash
ln -sf ~/work/.ssh-persistent ~/.ssh
```

## Next Steps

1. **Complete Layer 1:** Finish `01_core_types.ipynb`
   - Develop Account type
   - Develop Tax type
   - Develop FiscalPeriod type

2. **Write tests:** Create `tests/test_core/` tests

3. **Move to Layer 2:** Start `02_gl_foundation.ipynb`

4. **Document decisions:** Update `docs/architecture.md` with learnings

## Getting Help

- **Architecture questions:** See `docs/architecture.md`
- **ERPNext API:** https://frappeframework.com/docs/user/en/api
- **Project issues:** GitHub Issues (when repo is public)
