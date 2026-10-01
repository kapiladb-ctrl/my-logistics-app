import streamlit as st
import sqlite3
import math
from datetime import datetime

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
st.caption("Auto-Calculates LKR Conversions, SSCL Gross-Up Formulas, and 18% VAT with Strict Roundup Logic")

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
    has_vat = "NON VAT" not in category
    
    # 1. Base Amount (Strictly Rounded Integer)
    amount_lkr = int(round(base_amount))
    
    # 2. SSCL Tax: Implements your exact ROUNDUP(Base/97.5*2.5, 0) logic
    sscl_raw = (base_amount / 97.5) * 2.5
    sscl_tax = int(math.ceil(sscl_raw))  # math.ceil forces any decimal point forward (e.g. 85.01 -> 86)
    
    # 3. Cascading Tax Foundation Rule: VAT is charged on (Base + SSCL)
    vat_base = amount_lkr + sscl_tax
    vat_tax = int(math.ceil(vat_base * 0.18)) if has_vat else 0  # Also applies the ceil roundup for VAT decimal points
    
    # 4. Net Final Grand Total
    grand_total = amount_lkr + sscl_tax + vat_tax
    
    # Save to local session state database simulation
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO invoices (category, charge_name, amount_lkr, sscl_tax, vat_tax, grand_total)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (category, charge_name, amount_lkr, sscl_tax, vat_tax, grand_total))
    conn.commit()
    conn.close()
    st.success(f"Added successfully: {charge_name}")

# --- Data Presentation Matrix Grid ---
st.header("2. Live Spreadsheet Ledger Matrix")

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()
cursor.execute("SELECT * FROM invoices")
rows = cursor.fetchall()

# Calculate totals
cursor.execute("SELECT SUM(amount_lkr), SUM(sscl_tax), SUM(vat_tax), SUM(grand_total) FROM invoices")
totals = cursor.fetchone()
conn.close()

if rows:
    table_data = []
    for r in rows:
        table_data.append({
            "Row ID": r[0], "Category Class": r[1], "Charge Description": r[2],
            "Base (LKR)": f"{r[3]:,}", "SSCL (2.5%)": f"{r[4]:,}", "VAT (18%)": f"{r[5]:,}", "Net Total": f"{r[6]:,}"
        })
    st.dataframe(table_data, use_container_width=True)

    # --- Live Summary Blocks Ribbon ---
    st.markdown("---")
    st.subheader("3. Continuous Calculated Ledger Aggregates")
    
    subtotal = totals[0] if totals[0] else 0
    total_sscl = totals[1] if totals[1] else 0
    total_vat = totals[2] if totals[2] else 0
    grand_final = totals[3] if totals[3] else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Subtotal Amount", f"LKR {subtotal:,}")
    col2.metric("Total SSCL (2.5%)", f"LKR {total_sscl:,}")
    col3.metric("Total VAT (18%)", f"LKR {total_vat:,}")
    col4.metric("GRAND TOTAL RECEIVABLE", f"LKR {grand_final:,}")
    
    if st.button("🗑️ Clear Ledger Sheet"):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices")
        conn.commit()
        conn.close()
        st.rerun()
else:
    st.info("The invoice sheet is currently empty. Input values above to generate automated spreadsheet matrix lines.")

