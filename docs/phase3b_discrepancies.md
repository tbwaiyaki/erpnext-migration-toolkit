# Data Migration Discrepancy Report
**Generated:** 2026-03-09 17:07:57
**Total Discrepancies:** 3

---

## Summary

Total failed imports: **3**

### By Movement Type

- Breakage: 2
- Disposal: 1

---

## Detailed Discrepancies

### Discrepancy 1: Frying Pan (Small)

**Movement ID:** 101
**Item ID:** 4
**Movement Type:** Disposal
**Quantity:** 3
**Date:** 2024-06-12
**Notes:** Too worn/damaged for further use — disposed

**Diagnosis:**
Insufficient stock: Attempting to issue 3 units but insufficient stock available in warehouse. Possible causes: (1) Missing purchase records in source data, (2) Movements out of chronological order, (3) Data entry error in quantity.

**Recommended Actions:**
OPTION A: Verify source data - check if purchase movements are missing. If missing, add to source CSV and re-import. OPTION B: Accept discrepancy - if item was never properly tracked, make manual stock adjustment in ERPNext to reflect current reality. OPTION C: Skip - if item is no longer relevant, document and move on.

**Technical Error:**
```
["Traceback (most recent call last):\n  File \"apps/frappe/frappe/app.py\", line 120, in application\n    response = frappe.api.handle(request)\n               ^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"app
```

---

### Discrepancy 2: Water Jugs

**Movement ID:** 134
**Item ID:** 25
**Movement Type:** Breakage
**Quantity:** 1
**Date:** 2024-09-12
**Notes:** Broken during event cleanup

**Diagnosis:**
Insufficient stock: Attempting to issue 1 units but insufficient stock available in warehouse. Possible causes: (1) Missing purchase records in source data, (2) Movements out of chronological order, (3) Data entry error in quantity.

**Recommended Actions:**
OPTION A: Verify source data - check if purchase movements are missing. If missing, add to source CSV and re-import. OPTION B: Accept discrepancy - if item was never properly tracked, make manual stock adjustment in ERPNext to reflect current reality. OPTION C: Skip - if item is no longer relevant, document and move on.

**Technical Error:**
```
["Traceback (most recent call last):\n  File \"apps/frappe/frappe/app.py\", line 120, in application\n    response = frappe.api.handle(request)\n               ^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"app
```

---

### Discrepancy 3: Water Jugs

**Movement ID:** 160
**Item ID:** 25
**Movement Type:** Breakage
**Quantity:** 3
**Date:** 2024-11-15
**Notes:** Cracked during washing

**Diagnosis:**
Insufficient stock: Attempting to issue 3 units but insufficient stock available in warehouse. Possible causes: (1) Missing purchase records in source data, (2) Movements out of chronological order, (3) Data entry error in quantity.

**Recommended Actions:**
OPTION A: Verify source data - check if purchase movements are missing. If missing, add to source CSV and re-import. OPTION B: Accept discrepancy - if item was never properly tracked, make manual stock adjustment in ERPNext to reflect current reality. OPTION C: Skip - if item is no longer relevant, document and move on.

**Technical Error:**
```
["Traceback (most recent call last):\n  File \"apps/frappe/frappe/app.py\", line 120, in application\n    response = frappe.api.handle(request)\n               ^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"app
```

---

## User Guidance

These discrepancies represent data quality issues in the source CSV files, 
not bugs in the migration toolkit. The toolkit has preserved data integrity 
by refusing to create impossible stock balances (e.g., issuing more items 
than exist in stock).

**Next Steps:**

1. **Review each discrepancy** listed above
2. **Investigate source data** - check if purchase records are missing
3. **Choose resolution approach** per your business policies:
   - Fix source data and re-import
   - Make manual adjustment in ERPNext
   - Accept discrepancy and document
4. **Update this report** with actions taken and resolutions

**This is the professional approach:** Document discrepancies, don't fabricate data.
