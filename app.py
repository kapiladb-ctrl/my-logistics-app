import streamlit as st
import sqlite3
import math
import pandas as pd
from datetime import datetime
import io
import os

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

# --- SMART BANNER DISPLAYER ---
# Automatically searches for your image file under different extension variations
top_banner_file = None
for ext in ["jpg", "jpeg", "png", "JPG", "PNG", "JPEG"]:
    if os.path.exists(f"top_banner.{ext}"):
        top_banner_file = f"top_banner.{ext}"
        break

if top_banner_file:
    st.image(top_banner_file, use_container_width=True)
else:
    # Beautiful backup banner if the file extension doesn't match perfectly
    st.markdown(
        """
        <div style="background-color:#1E3A8A; padding:25px; border-radius:10px; text-align:center; margin-bottom:20px;">
            <h1 style="color:white; margin:0; font-family:Arial;">🚢 Dynamic Logistics Invoice & Tax System</h1>
            <p style="color:#93C5FD; margin:5px 0 0 0;">Auto-Calculates Conversions, Cascading Rent Tiers, and Strict Roundup Logic</p>
        </div>
        """,
        unsafe_html=True
    )

st.title("🚢 Dynamic Logistics Invoice & Tax System")
st.caption("Auto-Calculates LKR Conversions, Cascading Rent Tiers, and Strict Roundup Logic across all metrics")
st.markdown("---")

# --- MAIN PAGE LAYOUT PANEL ---
main_left, main_right = st.columns([1, 3], gap="large")

with main_left:
    st.header("Configurations")
    dollar_rate = st.number_input("Global USD Exchange Rate", value=333.85, step=0.01)
    
    st.markdown("---")
    
    # --- SMART ACCENT STRIP DISPLAYER ---
    left_strip_file = None
    for ext in ["jpg", "jpeg", "png", "JPG", "PNG", "JPEG"]:
        if os.path.exists(f"left_strip.{ext}"):
            left_strip_file = f"left_strip.{ext}"
            break
            
    if left_strip_file:
        st.image(left_strip_file, caption="Vessel Transit Stream", use_container_width=True)
    else:
        st.markdown(
            """
            <div style="background-color:#ECEFF1; padding:20px; border-radius:8px; text-align:center; border-left:4px solid #607D8B;">
                <span style="font-size:40px;">⚓</span><br>
                <b style="color:#37474F;">Vessel Transit Active</b>
            </div>
            """,
            unsafe_html=True
        )

with main_right:
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
            base_amount = charge_rate * items * dollar_rate

        elif "Wharf Rent" in category:
            charge_name = st.text_input("Invoice Group Identifier", value="Wharf Handling Charge Block")
            st.markdown("##### Automated Wharf Handling & Rent Tier Parameters")
            
            col1, col2 = st.columns(2)
            with col1:
                total_basic_dates = st.number_input("Enter Total Basic Dates/Days (e.g., 127)", value=127, step=1)
                hc_charge = st.number_input("Handling Charge Base ($)", value=64.0)
            with col2:
                br_gp = st.number_input("Basic Rent Factor (GP Multiplier)", value=16.0)
                p1_gp = st.number_input("PNL 1 Factor (Multiplier)", value=30.0)
                p2_gp = st.number_input("PNL 2 Factor (Multiplier)", value=46.0)

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
            amt_hc = int(math.ceil(hc_charge * 1 * dollar_rate))
            amt_br = int(math.ceil(br_gp * total_basic_dates * 1 * 1 * dollar_rate))
            
            p1_days = 7 if total_basic_dates > 7 else max(0, total_basic_dates)
            amt_p1 = int(math.ceil(p1_gp * p1_days * 1 * 1 * dollar_rate))
            
            p2_days = max(0, total_basic_dates - 14)
            amt_p2 = int(math.ceil(p2_gp * p2_days * 1 * 1 * dollar_rate))
            
            amount_lkr = amt_hc + amt_br + amt_p1 + amt_p2
            sscl_raw = (amount_lkr / 97.5) * 2.5
            sscl_tax = int(math.ceil(sscl_raw))
        else:
            amount_lkr = int(math.ceil(base_amount))
            sscl_raw = (base_amount / 97.5) * 2.5
            sscl_tax = int(math.ceil(sscl_raw))
            
        vat_base = amount_lkr + sscl_tax
        calculated_vat = int(math.ceil(vat_base * 0.18))
        
        vat_column_value = calculated_vat if is_vat_visible else 0
        grand_total = amount_lkr + sscl_tax + calculated_vat
        
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

    cursor.execute("SELECT SUM(amount_lkr), SUM(sscl_tax), SUM(vat_tax), SUM(grand_total) FROM invoices")
    totals_row = cursor.fetchone()
    conn.close()

    if rows:
        table_data = []
        export_raw_data = [] 
        
        for r in rows:
            val_base = int(r[3]) if r[3] is not None else 0
            val_sscl = int(r[4]) if r[4] is not None else 0
            val_vat  = int(r[5]) if r[5] is not None else 0
            val_tot  = int(r[6]) if r[6] is not None else 0
            
            table_data.append({
                "Row ID": r[0], 
                "Category Class": r[1], 
                "Charge Description": r[2],
                "Base (LKR)": f"{val_base:,}", 
                "SSCL (2.5%)": f"{val_sscl:,}", 
                "VAT (18%)": f"{val_vat:,}", 
                "Net Total": f"{val_tot:,}"
            })
            
            export_raw_data.append({
                "Row ID": r[0], 
                "Category Classification": r[1], 
                "Description": r[2],
                "Base Amount (LKR)": val_base, 
                "SSCL (2.5%)": val_sscl, 
                "VAT (18%)": val_vat, 
                "Grand Total (LKR)": val_tot
            })
            
        st.dataframe(table_data, use_container_width=True)

        df_export = pd.DataFrame(export_raw_data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Logistics Ledger')
        buffer.seek(0)

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
        
        subtotal = int(totals_row[0]) if totals_row and totals_row[0] is not None else 0
        total_sscl = int(totals_row[1]) if totals_row and totals_row[1] is not None else 0
        total_vat = int(totals_row[2]) if totals_row and totals_row[2] is not None else 0
        grand_final = int(totals_row[3]) if totals_row and totals_row[3] is not None else 0
        
