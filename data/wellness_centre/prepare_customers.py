#!/usr/bin/env python3
"""
Prepare Customer Data for ERPNext Import
Wellness Centre Migration - Financial Data Only
"""

import pandas as pd
import os

# Directories
data_dir = '/mnt/user-data/uploads'
output_dir = '/home/claude/import_data'
os.makedirs(output_dir, exist_ok=True)

# Load data
print("Loading source data...")
invoices = pd.read_csv(f'{data_dir}/etims_invoices.csv')
contacts = pd.read_csv(f'{data_dir}/contacts.csv')

# Find customers who have invoices
invoice_contacts = invoices['contact_id'].dropna().unique()
customers = contacts[contacts['id'].isin(invoice_contacts)].copy()

print(f"Found {len(customers)} customers with invoices")

# Prepare ERPNext Customer import format
# Required fields: customer_name, customer_type, customer_group, territory
erpnext_customers = pd.DataFrame({
    'ID': 'CUST-' + customers['id'].astype(str).str.zfill(5),  # Reference ID for linking
    'Customer Name': customers['name'].values,
    'Customer Type': 'Individual',  # or 'Company' based on data
    'Customer Group': 'Commercial',  # Standard group
    'Territory': 'Kenya',
    'Mobile No': customers['phone'].astype(str).values,
    'Email Id': customers['email'].values,
    'Tax ID': customers['kra_pin'].values,  # Kenya KRA PIN
    'Disabled': 0
})

# Clean phone numbers (remove .0 from float conversion)
erpnext_customers['Mobile No'] = erpnext_customers['Mobile No'].str.replace('.0', '', regex=False)

# Add Walk-in Customer for invoices without contact_id
walk_in = pd.DataFrame({
    'ID': ['CUST-00000'],
    'Customer Name': ['Walk-in Customer'],
    'Customer Type': ['Individual'],
    'Customer Group': ['Commercial'],
    'Territory': ['Kenya'],
    'Mobile No': [''],
    'Email Id': [''],
    'Tax ID': [''],
    'Disabled': [0]
})

erpnext_customers = pd.concat([erpnext_customers, walk_in], ignore_index=True)

# Save to CSV
output_file = f'{output_dir}/customers_import.csv'
erpnext_customers.to_csv(output_file, index=False)

print(f"\n✓ Customer import file created: {output_file}")
print(f"  Total customers: {len(erpnext_customers)}")
print(f"  - Named customers: {len(erpnext_customers) - 1}")
print(f"  - Walk-in customer: 1")
print(f"\nColumns included:")
for col in erpnext_customers.columns:
    print(f"  - {col}")

# Show sample
print(f"\nSample data:")
print(erpnext_customers.head(3).to_string(index=False))

print(f"\n✓ Ready for import into ERPNext")
