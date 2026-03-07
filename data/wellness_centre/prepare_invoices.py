#!/usr/bin/env python3
"""
Prepare Sales Invoice Data for ERPNext Import
Wellness Centre Migration - Financial Data Only
"""

import pandas as pd
import os
from datetime import datetime

# Directories
data_dir = '/mnt/user-data/uploads'
output_dir = '/home/claude/import_data'
os.makedirs(output_dir, exist_ok=True)

# Load data
print("Loading source data...")
invoices = pd.read_csv(f'{data_dir}/etims_invoices.csv')
invoice_items = pd.read_csv(f'{data_dir}/etims_invoice_items.csv')
contacts = pd.read_csv(f'{data_dir}/contacts.csv')

# Convert dates
invoices['invoice_date'] = pd.to_datetime(invoices['invoice_date'])

print(f"Processing {len(invoices)} invoices...")

# Prepare Sales Invoice header data
sales_invoices = []

for idx, inv in invoices.iterrows():
    # Determine customer
    if pd.notna(inv['contact_id']):
        customer_id = f"CUST-{int(inv['contact_id']):05d}"
        customer = contacts[contacts['id'] == inv['contact_id']]['name'].values
        customer_name = customer[0] if len(customer) > 0 else 'Walk-in Customer'
    else:
        customer_id = "CUST-00000"
        customer_name = "Walk-in Customer"
    
    # Get invoice items for this invoice
    items = invoice_items[invoice_items['invoice_id'] == inv['id']]
    
    # Create row for each item (ERPNext needs one row per item)
    for item_idx, item in items.iterrows():
        invoice_row = {
            'ID': inv['invoice_number'],  # Original invoice number
            'Naming Series': 'INV-',  # ERPNext naming series
            'Customer': customer_name,
            'Customer Name': customer_name,
            'Posting Date': inv['invoice_date'].strftime('%Y-%m-%d'),
            'Due Date': inv['invoice_date'].strftime('%Y-%m-%d'),  # Same as posting for now
            'Company': 'Wellness Centre',
            'Currency': 'KES',
            'Price List': 'Standard Selling',
            
            # Item details
            'Item Code': item['item_description'],  # Using description as item code
            'Item Name': item['item_description'],
            'Quantity': item['quantity'],
            'Rate': item['unit_price'],
            'Amount': item['total_price'],
            
            # Tax
            'Tax Rate': item['tax_rate'] * 100 if pd.notna(item['tax_rate']) else 0,  # Convert to percentage
            
            # Status
            'Docstatus': 1,  # 1 = Submitted (official invoice)
            
            # eTIMS compliance fields (custom)
            'Custom eTIMS Invoice Number': inv['invoice_number'],
            'Custom eTIMS CU Serial': inv['cu_serial_number'],
            'Custom eTIMS Status': inv['status'],
            'Custom eTIMS Transmission Date': pd.to_datetime(inv['transmission_date']).strftime('%Y-%m-%d %H:%M:%S') if pd.notna(inv['transmission_date']) else '',
        }
        
        sales_invoices.append(invoice_row)

# Convert to DataFrame
df_invoices = pd.DataFrame(sales_invoices)

# Save to CSV
output_file = f'{output_dir}/sales_invoices_import.csv'
df_invoices.to_csv(output_file, index=False)

print(f"\n✓ Sales Invoice import file created: {output_file}")
print(f"  Total invoice rows: {len(df_invoices)} (includes line items)")
print(f"  Unique invoices: {df_invoices['ID'].nunique()}")
print(f"  Date range: {df_invoices['Posting Date'].min()} to {df_invoices['Posting Date'].max()}")
print(f"  Total amount: KES {df_invoices['Amount'].sum():,.2f}")

# Monthly breakdown
df_invoices['month'] = pd.to_datetime(df_invoices['Posting Date']).dt.to_period('M')
monthly = df_invoices.groupby('month').agg({
    'ID': 'nunique',
    'Amount': 'sum'
}).rename(columns={'ID': 'invoices', 'Amount': 'amount'})

print(f"\n📊 Monthly breakdown:")
print(monthly.to_string())

print(f"\n✓ Ready for import into ERPNext")
print(f"\nNote: Custom eTIMS fields will need to be created in ERPNext first")
