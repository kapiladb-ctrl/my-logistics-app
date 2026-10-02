import streamlit as st
import sqlite3
import math
import pandas as pd
from datetime import datetime, date, timedelta
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
st.set_page_config(page_title="SLPA Tax Invoice Engine", layout="wide")

# =====================================================================
#                         PASSWORD LOGIN SYSTEM
# =====================================================================
CORRECT_PASSWORD = "Logistics2026"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("## 🔒 System Security Gate")
    st.info("Enter credentials below to access calculations.")
    with st.form("login_form"):
        user_password = st.text_input("Enter System Password", type="password")
        if st.form_submit_button("🔓 Access System"):
            if user_password == CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# =====================================================================
#                         MAIN APPLICATION ENGINE
# =====================================================================
all_files = os.listdir(".") if os.path.exists(".") else []
top_banner_file = None
left_strip_file = None
for f in all_files:
    f_lower = f.lower()
    if "top" in f_lower and "banner" in f_lower and any(ext in f_lower for ext in [".jpg", ".jpeg", ".png"]):
        top_banner_file = f
    if "left" in f_lower and "strip" in f_lower and any(ext in f_lower for ext in [".jpg", ".jpeg", ".png"]):
        left_strip_file = f

if top_banner_file:
    st.image(top_banner_file, use_container_width=True)

st.title("🚢 SLPA Customs Tax Invoice Generation Engine")
st.markdown("---")

# --- TWO COLUMN MAIN APP FRAME WORK ---
main_left, main_right = st.columns([1, 3], gap="large")

with main_left:
    st.header("📋 Header Metadata")
    serial_no = st.text_input("Serial No", value="29258")
    purchaser_tin = st.text_input("Purchases TIN", value="103252347")
    purchaser_name = st.text_input("Purchases Name", value="M/S. LANKA INTERNATIONAL PORT PVT LTD")
    purchaser_addr = st.text_area("Address", value="NO. 1, LEVEL 6, VALTING TOWER\nNAVAM MAWATHA, COLOMBO 02")
    
    st.markdown("---")
    dollar_rate = st.number_input("Global USD Exchange Rate", value=333.85, step=0.01)
    
    st.markdown("---")
    st.subheader("🛠️ Maintenance Controls")
    
    if st.button("🗑️ Clear Current Invoice Sheet", type="secondary", use_container_width=True):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices")
        conn.commit()
        conn.close()
        st.success("Ledger matrix cache purged clean!")
        st.rerun()
        
    if st.button("🔒 Log Out Component", type="primary", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()
        
    st.markdown("---")
    if left_strip_file:
        st.image(left_strip_file, caption="Transit Stream Active", use_container_width=True)

with main_right:
    st.header("1. Input Invoice Details")
    category = st.selectbox("Select Billing Category Type", [
        "Amendment Charge (NON VAT)", 
        "Amendment Charge (VAT)",
        "DC PENALTY Charge",
        "Wharf Rent / Basic Handling",
        "Administrative charge 1%",
        "Pass Cancellation Charges"
    ])

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
                
            charge_name = st.text_input("Description of Goods or Services", value=default_name)
            charge_rate = st.number_input("Unit Price USD", value=default_rate)
            items = st.number_input("Quantity", value=1, step=1)
            base_amount = charge_rate * items * dollar_rate

        elif "Wharf Rent" in category:
            charge_name = st.text_input("Description of Goods or Services", value="Wharf Handling Charge Block")
            total_basic_dates = st.number_input("Enter Total Basic Dates/Days", value=127, step=1)
            hc_charge = st.number_input("Handling Charge Base ($)", value=64.0)
            br_gp = st.number_input("Basic Rent Factor (GP Multiplier)", value=16.0)
            p1_gp = st.number_input("PNL 1 Factor", value=30.0)
            p2_gp = st.number_input("PNL 2 Factor", value=46.0)
            base_amount = 0.0

        elif "Administrative" in category:
            charge_name = st.text_input("Description of Goods or Services", value="Penalty Charge")
            total_amount_lkr = st.number_input("Total Amount (LKR Source)", value=12879.0)
            factor = st.number_input("Rate Factor (e.g., 1%)", value=0.01, format="%.2f")
            
            today_date = date.today()
            one_month_ago = today_date - timedelta(days=30)
            
            col1, col2 = st.columns(2)
            with col1: 
                st.date_input("From Date", one_month_ago)
            with col2: 
                st.date_input("To Date", today_date)
            
            days = abs((today_date - one_month_ago).days) + 1
            base_amount = total_amount_lkr * factor * days

        submit_button = st.form_submit_button("⚡ Compute & Commit Line")

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
        else:
            amount_lkr = int(math.ceil(base_amount))
            
        sscl_raw = (amount_lkr / 97.5) * 2.5
        sscl_tax = int(math.ceil(sscl_raw))
        
        if is_vat_visible:
            vat_base = amount_lkr + sscl_tax
            vat_column_value = int(math.ceil(vat_base * 0.18))
        else:
            vat_column_value = 0
            
        grand_total = amount_lkr + sscl_tax + vat_column_value

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO invoices (category, charge_name, amount_lkr, sscl_tax, vat_tax, grand_total) VALUES (?, ?, ?, ?, ?, ?)",
                       (category, charge_name, amount_lkr, sscl_tax, vat_column_value, grand_total))
        conn.commit()
        conn.close()
        st.success("Calculated and added successfully!")

    # =====================================================================
    #   SECTION 2: OUTPUT SELECTION CARD PANEL
    # =====================================================================
    st.markdown("---")
    st.header("2. Choose Output Format Options")
    output_choice = st.radio("Select Output Format Variant:", ["Visual Invoice Sheet (Form Look)", "Raw Excel Spreadsheet (.xlsx)"])

    # --- CRASH-PROOF DATA DICTIONARY ENGINE ---
    # Connects columns to explicit text titles instead of numbers to stop syntax crashes
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  
    cursor = conn.cursor()
    
    cursor.execute("SELECT category, charge_name, amount_lkr, sscl_tax, vat_tax, grand_total FROM invoices")
    rows = cursor.fetchall()
    
    cursor.execute("SELECT SUM(amount_lkr) as total_base, SUM(sscl_tax) as total_sscl, SUM(vat_tax) as total_vat, SUM(grand_total) as total_grand FROM invoices")
    totals_row = cursor.fetchone()
    conn.close()

    # Extract data securely using explicit word keys with safe zeros fallback
    subtotal = int(totals_row["total_base"]) if totals_row and totals_row["total_base"] is not None else 0
    total_sscl = int(totals_row["total_sscl"]) if totals_row and totals_row["total_sscl"] is not None else 0
    total_vat = int(totals_row["total_vat"]) if totals_row and totals_row["total_vat"] is not None else 0
    grand_final = int(totals_row["total_grand"]) if totals_row and totals_row["total_grand"] is not None else 0

    if rows:
        if output_choice == "Visual Invoice Sheet (Form Look)":
            st.info(f"📄 **TAX INVOICE** | Serial No: {serial_no} | Purchases TIN: {purchaser_tin}")
            st.write(f"**Customer Name:** {purchaser_name}")
            st.write(f"**Billing Address:** {purchaser_addr}")
            
            table_data = []
            for row in rows:
                table_data.append({
                    "Description of Goods or Services": f"{row['charge_name']} ({row['category']})",
                    "Amount Excluding VAT (Rs.)": f"{int(row['amount_lkr']):,}.00"
                })
            st.table(table_data)
            
