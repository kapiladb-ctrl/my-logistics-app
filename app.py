import streamlit as st
import sqlite3
import math
import pandas as pd
from datetime import datetime
import io

DB_NAME = "billing_system.db"

# --- Database Initialization ---
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            charge_name TEXT NOT NULL,
            amount_lkr INTEGER,
            sscl_tax INTEGER,
            vat_tax INTEGER,
            grand_total INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_database()

# --- Page Configuration ---
st.set_page_config(page_title="Logistics Invoice System", layout="wide")
st.title("🚢 Dynamic Logistics Invoice & Tax System")
st.caption("Auto-Calculates LKR Conversions, SSCL Gross-Up Formulas, and Strict Roundup Logic across all metrics")

# --- Global Settings Sidebar ---
st.sidebar.header("Global Configurations")
dollar_rate = st.sidebar.number_input("Global USD Exchange Rate", value=333.85, step=0.01)

# --- Dynamic Input Panel ---
st.header("1. Data Input Fields")
category = st.selectbox("Select Billing Category", [
    "Amendment Charge (NON VAT)", 
    "Amendment Charge (VAT)",
    "DC PENALTY Charge",
    "Wharf Rent / Basic Handling",
    "Administrative charge 1%"
])

# Dynamically change input boxes based on category selection
with st.form("invoice_form", clear_on_submit=True):
    if "Amendment" in category or "DC PENALTY" in category:
        charge_name = st.text_input("Charge Description", value="Ammendment charge" if "Amendment" in category else "DC Penalty Charge")
        charge_rate = st.number_input("Charge Rate ($)", value=10.0 if "Amendment" in category else 26.0)
        items = st.number_input("Item Count / Qty", value=1, step=1)
        
        # Calculate Base
        base_amount = charge_rate * items * dollar_rate

    elif "Wharf Rent" in category:
        charge_name = st.text_input("Rent Description", value="Basic Rent")
        multiplier = st.number_input("Multiplier (GP/OT Factor)", value=16.0)
        days = st.number_input("Dates / Total Days", value=127, step=1)
        charge_rate = st.number_input("Charge Rate ($)", value=1.0)
        items = st.number_input("Item Quantity", value=1, step=1)
        
        # Calculate Base
        base_amount = (multiplier * charge_rate) * days * items * dollar_rate

    elif "Administrative" in category:
        charge_name = st.text_input("Description", value="Penalty Charge")
        total_amount_lkr = st.number_input("Total Amount (LKR Source)", value=12879.0)
        factor = st.number_input("Rate Factor (e.g., 1%)", value=0.01, format="%.2f")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From Date", datetime(2026, 6, 23))
        with col2:
            end_date = st.date_input("To Date", datetime(2026, 7, 3))
            
        days = abs((end_date - start_date).days)
        # Calculate Base
        base_amount = total_amount_lkr * factor * days

    submit_button = st.form_submit_button("⚡ Calculate & Add Row")

# --- Process Calculations ---
if submit_button:
    is_vat_visible = "NON VAT" not in category
    
    # 1. Base Amount: Implements strict ROUNDUP rule (e.g., 3338.5 -> 3339)
    amount_lkr = int(math.ceil(base_amount))
    
    # 2. SSCL Tax: Implements exact ROUNDUP(Base/97.5*2.5, 0) logic
    sscl_raw = (base_amount / 97.5) * 2.5
    sscl_tax = int(math.ceil(sscl_raw))
    
    # 3. Cascading Tax Foundation Rule: VAT calculation happens regardless of visibility
    vat_base = amount_lkr + sscl_tax
    calculated_vat = int(math.ceil(vat_base * 0.18))
    
    # Apply your conditional visibility rule: 
    # If NON-VAT, display 0 in the column, but add the calculated amount to the grand total.
    vat_column_value = calculated_vat if is_vat_visible else 0
    grand_total = amount_lkr + sscl_tax + calculated_vat
    
    # Save to database simulation
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invoices (category, charge_name, amount_lkr, sscl_tax, vat_tax, grand_total)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (category, charge_name, amount_lkr, sscl_tax, vat_column_value, grand_total))
    conn.commit()
    conn.close()
    st.success(f"Added successfully: {charge_name}")

# --- Data Presentation Matrix Grid ---
st.header("2. Live Spreadsheet Ledger Matrix")

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()
cursor.execute("SELECT * FROM invoices")
rows = cursor.fetchall()

# Calculate totals safely with fallback values
cursor.execute("SELECT SUM(amount_lkr), SUM(sscl_tax), SUM(vat_tax), SUM(grand_total) FROM invoices")
totals_row = cursor.fetchone()
conn.close()

if rows:
    table_data = []
    export_raw_data = [] # Stores unformatted numbers cleanly for genuine Excel usage
    
    for r in rows:
        val_base = int(r) if r is not None else 0
        val_sscl = int(r) if r is not None else 0
        val_vat  = int(r) if r is not None else 0
        val_tot  = int(r) if r is not None else 0
        
        # Display variant (with text commas)
        table_data.append({
            "Row ID": r, "Category Class": r, "Charge Description": r,
            "Base (LKR)": f"{val_base:,}", "SSCL (2.5%)": f"{val_sscl:,}", "VAT (18%)": f"{val_vat:,}", "Net Total": f"{val_tot:,}"
        })
        
        # Export variant (pure integers so Excel formulas can sum them easily)
        export_raw_data.append({
            "Row ID": r, "Category Classification": r, "Description": r,
            "Base Amount (LKR)": val_base, "SSCL (2.5%)": val_sscl, "VAT (18%)": val_vat, "Grand Total (LKR)": val_tot
        })
        
    st.dataframe(table_data, use_container_width=True)

    # Convert dataset to pandas to prepare memory streaming export
    df_export = pd.DataFrame(export_raw_data)
    
    # Stream data into a virtual excel buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Logistics Ledger')
    buffer.seek(0)

    # Action Toolbar Buttons
    col_dl, col_clear = st.columns([1, 5])
    with col_dl:
        st.download_button(
            label="📥 Export to Excel",
            data=buffer,
            file_name=f"logistics_invoice_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- Live Summary Blocks Ribbon ---
    st.markdown("---")
    st.subheader("3. Continuous Calculated Ledger Aggregates")
    
    subtotal = int(totals_row) if totals_row and totals_row is not None else 0
    total_sscl = int(totals_row) if totals_row and totals_row is not None else 0
    total_vat = int(totals_row) if totals_row and totals_row is not None else 0
    grand_final = int(totals_row) if totals_row and totals_row is not None else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Subtotal Amount", f"LKR {subtotal:,}")
    col2.metric("Total SSCL (2.5%)", f"LKR {total_sscl:,}")
    col3.metric("Total VAT (18%)", f"LKR {total_vat:,}")
    col4.metric("GRAND TOTAL RECEIVABLE", f"LKR {grand_final:,}")
    
    with col_clear:
        if st.button("🗑️ Clear Ledger Sheet"):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM invoices")
            conn.commit()
            conn.close()
            st.rerun()
else:
    st.info("The invoice sheet is currently empty. Input values above to generate automated spreadsheet matrix lines.")
