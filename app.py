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
    "Administrative charge 1%",
    "Pass Cancellation Charges"
])

# Dynamically change input boxes based on category selection
with st.form("invoice_form", clear_on_submit=True):
    # Setup for standard row calculations
    if "Amendment" in category or "DC PENALTY" in category or "Pass Cancellation" in category:
        if "Amendment" in category:
            default_name = "Ammendment charge"
            default_rate = 10.0
        elif "DC PENALTY" in category:
            default_name = "DC Penalty Charge"
            default_rate = 26.0
        else:
            default_name = "Pass Cancellation Charge"
            default_rate = 5.0
            
        charge_name = st.text_input("Charge Description", value=default_name)
        charge_rate = st.number_input("Charge Rate ($)", value=default_rate)
        items = st.number_input("Item Count / Qty", value=1, step=1)
        
        # Calculate Base
        base_amount = charge_rate * items * dollar_rate

    # Setup for the newly redesigned Grouped Wharf Handling calculations
    elif "Wharf Rent" in category:
        charge_name = st.text_input("Invoice Group Identifier", value="Wharf Handling Charge Block")
        st.markdown("#### Grouped Sub-Line Item Parameters")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("**1. Handling Charges**")
            hc_charge = st.number_input("Handling Charge ($)", value=64.0)
            hc_item = st.number_input("Handling Qty", value=1, step=1)
            
        with col2:
            st.markdown("**2. Basic Rent**")
            br_gp = st.number_input("Basic GP", value=16.0)
            br_dates = st.number_input("Basic Dates", value=127, step=1)
            br_charge = st.number_input("Basic Charge ($)", value=1.0)
            br_item = st.number_input("Basic Qty", value=1, step=1)
            
        with col3:
            st.markdown("**3. PNL 1 Rent**")
            p1_gp = st.number_input("PNL 1 GP", value=30.0)
            p1_dates = st.number_input("PNL 1 Dates", value=7, step=1)
            p1_charge = st.number_input("PNL 1 Charge ($)", value=1.0)
            p1_item = st.number_input("PNL 1 Qty", value=1, step=1)
            
        with col4:
            st.markdown("**4. PNL 2 Rent**")
            p2_gp = st.number_input("PNL 2 GP", value=46.0)
            p2_dates = st.number_input("PNL 2 Dates", value=113, step=1)
            p2_charge = st.number_input("PNL 2 Charge ($)", value=1.0)
            p2_item = st.number_input("PNL 2 Qty", value=1, step=1)

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
        base_amount = total_amount_lkr * factor * days

    submit_button = st.form_submit_button("⚡ Calculate & Add Row")

# --- Process Calculations ---
if submit_button:
    is_vat_visible = "NON VAT" not in category
    
    if "Wharf Rent" in category:
        # 1. Calculate each row using strict math.ceil roundup logic separately
        amt_hc = int(math.ceil(hc_charge * hc_item * dollar_rate))
        amt_br = int(math.ceil(br_gp * br_dates * br_charge * br_item * dollar_rate))
        amt_p1 = int(math.ceil(p1_gp * p1_dates * p1_charge * p1_item * dollar_rate))
        amt_p2 = int(math.ceil(p2_gp * p2_dates * p2_charge * p2_item * dollar_rate))
        
        # 2. Combine base amounts to exactly mimic your subtotal column (2,505,213 LKR)
        amount_lkr = amt_hc + amt_br + amt_p1 + amt_p2
        
        # 3. Calculate the cumulative grossed up SSCL (2.5%) based on the total subtotal
        sscl_raw = (amount_lkr / 97.5) * 2.5
        sscl_tax = int(math.ceil(sscl_raw)) # Pushes exactly to 64,237 LKR
        
    else:
        # Standard row-by-row math engine
        amount_lkr = int(math.ceil(base_amount))
        sscl_raw = (base_amount / 97.5) * 2.5
        sscl_tax = int(math.ceil(sscl_raw))
        
    # 4. Cascading Tax Rule: VAT calculation base = Amount + SSCL
    vat_base = amount_lkr + sscl_tax
    calculated_vat = int(math.ceil(vat_base * 0.18))
    
    # 5. Apply conditional column visibility logic
    vat_column_value = calculated_vat if is_vat_visible else 0
    grand_total = amount_lkr + sscl_tax + calculated_vat
    
    # Save parameters to database log
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
    export_raw_data = [] 
    
    for r in rows:
        val_base = int(r) if r is not None else 0
        val_sscl = int(r) if r is not None else 0
        val_vat  = int(r) if r is not None else 0
        val_tot  = int(r) if r is not None else 0
        
        table_data.append({
            "Row ID": r, 
            "Category Class": r, 
            "Charge Description": r,
            "Base (LKR)": f"{val_base:,}", 
            "SSCL (2.5%)": f"{val_sscl:,}", 
            "VAT (18%)": f"{val_vat:,}", 
            "Net Total": f"{val_tot:,}"
        })
        
        export_raw_data.append({
            "Row ID": r, 
            "Category Classification": r, 
            "Description": r,
            "Base Amount (LKR)": val_base, 
            "SSCL (2.5%)": val_sscl, 
            "VAT (18%)": val_vat, 
            "Grand Total (LKR)": val_tot
        })
        
    st.dataframe(table_data, use_container_width=True)

    # Convert dataset to pandas to prepare memory streaming export
    df_export = pd.DataFrame(export_raw_data)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Logistics Ledger')
    buffer.seek(0)

    # Action Toolbar Buttons
    col_dl, col_clear = st.columns(2)
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



