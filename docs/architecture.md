# Architecture

## Design Philosophy

**Build from primitives upward.** Every complex type depends on validated, tested foundation types.

## Layers

### Layer 1: Core Types (`src/core/`)

**Primitive types with no dependencies on ERPNext or business logic.**

- **Money**: Decimal-based monetary amounts with currency validation
- **Account**: Chart of Accounts reference with type validation
- **Tax**: Tax rate calculations with rounding rules
- **FiscalPeriod**: Date range validation for accounting periods

**Design principles:**
- Immutable (thread-safe, prevents accidental modification)
- Type-safe (Pydantic validation where appropriate)
- Self-validating (raises errors on invalid construction)
- ERPNext-compatible (converts to API formats)

### Layer 2: GL Foundation (`src/gl/`)

**General Ledger operations built on core types.**

- **JournalEntry**: Double-entry bookkeeping transactions
- **ChartOfAccounts**: Account hierarchy validator
- **GLReconciliation**: Balance verification

**Key features:**
- Enforces debit = credit balance
- Validates account types for transaction types
- Supports fiscal period constraints

### Layer 3: Business Documents (`src/documents/`)

**Invoice, payment, and purchasing documents.**

- **SalesInvoice**: Customer invoicing with line items
- **PurchaseInvoice**: Supplier invoicing
- **PaymentEntry**: Payment recording and allocation
- **ExpenseClaim**: Employee expense reimbursement

**Each document:**
- Maps CSV/Excel data to ERPNext format
- Validates referential integrity
- Calculates totals and taxes
- Generates ERPNext API payload

### Layer 4: Domain Models (`src/domain/`)

**Industry-specific business logic.**

- **domain/wellness/**: Event venue, room bookings, poultry farm
- **domain/manufacturing/**: Bill of materials, work orders
- **domain/retail/**: Point of sale, inventory

**Extensibility pattern:**
- Each domain is a separate subpackage
- Inherits from document layer
- Adds domain-specific validation and calculations

### Layer 5: Orchestration

**Migration sequencing and dependency management.**

- Determines import order (Items → Customers → Invoices)
- Handles referential integrity (create dependencies first)
- Provides rollback on errors
- Generates validation reports

## Data Flow

```
CSV/Excel Source Data
    ↓
Domain Model (validates, transforms)
    ↓
Document Builder (creates ERPNext payload)
    ↓
ERPNext Client (API submission)
    ↓
Validation Report (verify import success)
```

## Error Handling Strategy

**Fail-fast during validation:**
- Validate all data before importing anything
- Collect all errors in validation report
- User fixes source data and retries

**Transactional during import:**
- Track successful imports
- On error: report which records failed
- Provide resume capability (skip already imported)

**Post-import reconciliation:**
- Compare source totals vs ERPNext totals
- Flag discrepancies for investigation

## Testing Strategy

**Unit tests** (`tests/test_core/`): Test individual types in isolation  
**Integration tests** (`tests/test_integration/`): Test against real ERPNext instance  
**Notebook tests**: Visual validation during development

## Configuration Management

**Connection config** (`config/erpnext_connection.yaml`):
```yaml
url: https://erpnext-instance.com
api_key: xxx
api_secret: xxx
```

**Mapping config** (`config/mappings.yaml`):
```yaml
customer_name_field: customer_name
customer_type_default: Company
```

**Chart of Accounts template** (`config/chart_of_accounts_template.yaml`):
```yaml
expense_categories:
  - name: Utilities
    parent: Indirect Expenses
  - name: Salaries
    parent: Direct Expenses
```

## Extension Pattern

**To add a new domain:**

1. Create `src/domain/your_domain/`
2. Implement models inheriting from document layer
3. Create notebook `04_your_domain.ipynb`
4. Add tests in `tests/test_domain/`
5. Update orchestrator with new dependencies

## Performance Considerations

- Batch API calls (ERPNext supports bulk creation)
- Use pandas for CSV processing (vectorized operations)
- Cache ERPNext lookups (customer name → ID mappings)
- Parallel processing where possible (independent imports)

## Future Enhancements

- Web UI for non-technical users
- Real-time data sync (not just one-time migration)
- Export from ERPNext (reverse migration)
- Integration with other ERPs (Odoo, QuickBooks)
