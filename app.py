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

# --- File extension scanning motor ---
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

# --- TWO COLUMN APP FRAME WORK ---
main_left, main_right = st.columns([1, 3], gap="large")

with main_left:
    st.header("📋 Header Metadata")
    
    # Invoice Header fields from your image template
    serial_no = st.text_input("Serial No", value="29258")
    purchaser_tin = st.text_input("Purchases TIN", value="103252347")
    purchaser_name = st.text_input("Purchases Name", value="M/S. LANKA INTERNATIONAL PORT PVT LTD")
    purchaser_addr = st.text_area("Address", value="NO. 1, LEVEL 6, VALTING TOWER\nNAVAM MAWATHA, COLOMBO 02")
    
    st.markdown("---")
    dollar_rate = st.number_input("Global USD Exchange Rate", value=333.85, step=0.01)
    
    if left_strip_file:
        st.image(left_strip_file, caption="Transit Stream Active", use_container_width=True)
    st.markdown("---")
    if st.button("🔒 Log Out"):
        st.session_state["authenticated"] = False
        st.rerun()

with main_right:
    st.header("1. Input Invoice Details")
    category = st.selectbox("Select Item Category Type", [
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

        elif "Administrative" in category:
            charge_name = st.text_input("Description of Goods or Services", value="Penalty Charge")
            total_amount_lkr = st.number_input("Total Amount (LKR Source)", value=12879.0)
            factor = st.number_input("Rate Factor (e.g., 1%)", value=0.01, format="%.2f")
            col1, col2 = st.columns(2)
            with col1: start_date = st.date_input("From Date", datetime(2026, 6, 23))
            with col2: end_date = st.date_input("To Date", datetime(2026, 7, 3))
            days = abs((end_date - start_date).days)
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
        vat_base = amount_lkr + sscl_tax
        calculated_vat = int(math.ceil(vat_base * 0.18))
        vat_column_value = calculated_vat if is_vat_visible else 0
        grand_total = amount_lkr + sscl_tax + calculated_vat

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO invoices (category, charge_name, amount_lkr, sscl_tax, vat_tax, grand_total) VALUES (?, ?, ?, ?, ?, ?)",
                       (category, charge_name, amount_lkr, sscl_tax, vat_column_value, grand_total))
        conn.commit()
        conn.close()
        st.success("Calculated and added successfully!")

    # --- OUTPUT MANAGEMENT FRAMEWORK ---
    st.markdown("---")
    st.header("2. Choose Output Format Options")
    output_choice = st.radio("Select Output Format Variant:", ["Visual Invoice Sheet (Form Look)", "Raw Excel Spreadsheet (.xlsx)"])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices")
    rows = cursor.fetchall()
    cursor.execute("SELECT SUM(amount_lkr), SUM(sscl_tax), SUM(vat_tax), SUM(grand_total) FROM invoices")
    totals_row = cursor.fetchone()
    conn.close()

    if rows:
        subtotal = int(totals_row[0]) if totals_row[0] is not None else 0
        total_sscl = int(totals_row[1]) if totals_row[1] is not None else 0
        total_vat = int(totals_row[2]) if totals_row[2] is not None else 0
        grand_final = int(totals_row[3]) if totals_row[3] is not None else 0

        # VARIANT 1: VISUAL INVOICE FORM (Exactly matching your submitted image style)
        if output_choice == "Visual Invoice Sheet (Form Look)":
            st.markdown(
                f"""
                <div style="background-color: white; padding: 30px; border: 2px solid #333; color: black; font-family: monospace;">
                    <div style="text-align: center; font-size: 22px; font-weight: bold; text-decoration: underline; margin-bottom: 20px;">Tax Invoice</div>
                    <table style="width: 100%; border: none; color: black; font-size: 14px; margin-bottom: 20px;">
                        <tr>
                            <td style="width: 50%;"><b>Sri Lanka Ports Authority</b><br>No 19, Chaithya Road, Colombo 01.<br>Tel: 0112 483391</td>
                            <td><b>Serial No:</b> {serial_no}<br><b>Purchases TIN:</b> {purchaser_tin}<br><b>Purchases Name:</b> {purchaser_name}</td>
                        </tr>
                    </table>
                    <table style="width:100%; border-collapse: collapse; color: black; font-size: 14px; text-align: center;">
                        <tr style="border-top: 2px solid black; border-bottom: 2px solid black;">
                            <th style="padding: 8px; text-align: left;">Description of Goods or Services</th>
                            <th style="padding: 8px;">Amount Excluding VAT (Rs.)</th>
                        </tr>
                """, unsafe_html=True
            )
            for r in rows:
                st.markdown(
                    f"""
                        <tr style="border-bottom: 1px solid #ddd;">
                            <td style="padding: 8px; text-align: left;">{r[2]} ({r[1]})</td>
                            <td style="padding: 8px;">{int(r[3]):,}</td>
                        </tr>
                    """, unsafe_html=True
                )
            st.markdown(
                f"""
