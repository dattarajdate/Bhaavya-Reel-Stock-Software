import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import os
from fpdf import FPDF
import io

st.set_page_config(page_title="Bhaavya Ecopack - Reel Stock System", layout="wide")

# Compact CSS Styling
st.markdown("""
    <style>
    .custom-row {
        border-bottom: 1px solid #dcdcdc !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
        margin-bottom: 0px !important;
    }
    .custom-row:hover {
        background-color: #f8f9fa !important;
    }
    .stTextInput div[data-baseweb="input"] {
        min-height: 32px !important;
    }
    </style>
""", unsafe_allow_html=True)

db_file = 'bhaavya_stock.db'

# --- COMPANY DETAILS ---
COMP_NAME = "BHAAVYA ECOPACK"
COMP_DIV = "(Corrugated Box Division)"
COMP_ADDR = "Block No.-250, Nr Shital Hotel, Village.-Sava, Mangrol, Kosamba."
COMP_MSME = "MSME-UDYAM-GJ-22-0027962"
COMP_GST = "GSTIN/UIN: 24AAWFB8208R1ZM"
COMP_STATE = "State Name: Gujarat, Code: 24"
COMP_EMAIL = "E-Mail: bhaavyaecopack@gmail.com"

# --- DATABASE SCHEMA & USER TRACKING UPGRADE ---
def upgrade_db_schema():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receiving_reel ON receiving(company_reel);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receiving_mill_reel ON receiving(mill_reel);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receiving_date ON receiving(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consumption_reel ON consumption(company_reel);")
    except:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS receiving (
            sr INTEGER,
            date TEXT,
            company_reel TEXT PRIMARY KEY,
            mill_reel TEXT,
            mill TEXT,
            gsm INTEGER,
            bf INTEGER,
            deckle INTEGER,
            weight REAL,
            shade TEXT,
            supplier TEXT,
            location TEXT,
            remarks TEXT,
            rate REAL DEFAULT 0.0,
            trans_charges REAL DEFAULT 0.0,
            grn_no TEXT DEFAULT "",
            bill_no TEXT DEFAULT "",
            entered_by TEXT DEFAULT "super_admin",
            po_id INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consumption (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            company_reel TEXT,
            weight_consumed REAL,
            machine TEXT,
            entered_by TEXT DEFAULT "super_admin"
        )
    ''')

    try:
        cursor.execute("PRAGMA table_info(purchase_orders);")
        po_columns = [col[1] for col in cursor.fetchall()]
        if po_columns:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='purchase_orders';")
            sql_res = cursor.fetchone()
            if sql_res and "UNIQUE" in sql_res[0].upper():
                cursor.execute("DROP TABLE purchase_orders;")
    except:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_no TEXT,
            date TEXT,
            mill TEXT,
            gsm INTEGER,
            bf INTEGER,
            deckle INTEGER,
            shade TEXT,
            ordered_qty REAL,
            status TEXT DEFAULT 'PENDING'
        )
    ''')

    try:
        cursor.execute("SELECT rate, trans_charges, grn_no, bill_no, entered_by, po_id FROM receiving LIMIT 1")
    except sqlite3.OperationalError:
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN rate REAL DEFAULT 0.0')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN trans_charges REAL DEFAULT 0.0')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN grn_no TEXT DEFAULT ""')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN bill_no TEXT DEFAULT ""')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN entered_by TEXT DEFAULT "super_admin"')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN po_id INTEGER DEFAULT 0')
        except: pass

    try:
        cursor.execute("SELECT entered_by FROM consumption LIMIT 1")
    except sqlite3.OperationalError:
        try: cursor.execute('ALTER TABLE consumption ADD COLUMN entered_by TEXT DEFAULT "super_admin"')
        except: pass
    
    cursor.execute('CREATE TABLE IF NOT EXISTS mill_master (id INTEGER PRIMARY KEY AUTOINCREMENT, mill_name TEXT UNIQUE NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS shade_master (id INTEGER PRIMARY KEY AUTOINCREMENT, shade_name TEXT UNIQUE NOT NULL)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            can_view_stock INTEGER DEFAULT 1,
            can_add_entry INTEGER DEFAULT 1,
            can_edit_receiving INTEGER DEFAULT 0,
            can_edit_consumption INTEGER DEFAULT 0
        )
    ''')
    
    try:
        cursor.execute("SELECT can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption FROM users LIMIT 1")
    except sqlite3.OperationalError:
        try: cursor.execute('ALTER TABLE users ADD COLUMN can_view_stock INTEGER DEFAULT 1')
        except: pass
        try: cursor.execute('ALTER TABLE users ADD COLUMN can_add_entry INTEGER DEFAULT 1')
        except: pass
        try: cursor.execute('ALTER TABLE users ADD COLUMN can_edit_receiving INTEGER DEFAULT 0')
        except: pass
        try: cursor.execute('ALTER TABLE users ADD COLUMN can_edit_consumption INTEGER DEFAULT 0')
        except: pass

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('super_admin', 'bhaavya123', 'SUPER_ADMIN', 1, 1, 1, 1)")
        cursor.execute("INSERT INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('admin', 'admin123', 'ADMIN', 1, 1, 1, 1)")
        cursor.execute("INSERT INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('operator', 'op123', 'OPERATOR', 1, 1, 0, 0)")
    
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('JAYDIP_PARMAR', 'bhaavya123', 'ADMIN', 1, 1, 1, 1)")
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('KAJAL', 'bhaavya123', 'ADMIN', 1, 1, 1, 1)")
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('DHRUV_CHAUHAN', 'bhaavya123', 'ADMIN', 1, 1, 1, 1)")
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES ('PRIYANSH_MARFATIA', 'bhaavya123', 'ADMIN', 1, 1, 1, 1)")

    cursor.execute("UPDATE users SET can_view_stock = 1, can_add_entry = 1, can_edit_receiving = 1, can_edit_consumption = 1 WHERE username = 'super_admin' OR role = 'SUPER_ADMIN'")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_master (
            gsm INTEGER,
            bf INTEGER,
            deckle INTEGER,
            shade TEXT,
            per_day_consumption REAL DEFAULT 0.0,
            reorder_qty REAL DEFAULT 0.0,
            PRIMARY KEY (gsm, bf, deckle, shade)
        )
    ''')
    
    conn.commit()
    conn.close()

upgrade_db_schema()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "logged_user" not in st.session_state:
    st.session_state.logged_user = ""

def check_login():
    user = st.session_state.username_input.strip()
    pwd = st.session_state.password_input.strip()
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ? AND password = ?", (user, pwd))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        st.session_state.logged_in = True
        st.session_state.user_role = res[0]
        st.session_state.logged_user = user

if not st.session_state.logged_in:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🔐 SECURE LOGIN</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        st.text_input("USERNAME", key="username_input")
        st.text_input("PASSWORD", type="password", key="password_input")
        st.form_submit_button("LOGIN", on_click=check_login)
    st.stop()

def run_query(query, params=()):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    st.cache_data.clear()

@st.cache_data(ttl=300)
def get_data(query, params=()):
    conn = sqlite3.connect(db_file)
    conn.create_function("CLEAN_NAME", 1, lambda x: "".join(str(x).upper().replace(".", "").replace(" ", "").split()) if x else "")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    for col in df.columns:
        if 'DATE' in col.upper(): df[col] = df[col].astype(str).str.split(" ").str[0]
    return df

def get_unique_mills():
    conn = sqlite3.connect(db_file)
    df1 = pd.read_sql_query("SELECT mill_name as mill FROM mill_master", conn)
    df2 = pd.read_sql_query("SELECT mill FROM receiving", conn)
    conn.close()
    combined = pd.concat([df1['mill'], df2['mill']]).dropna().astype(str).str.strip().str.upper()
    return sorted([m for m in combined.unique() if m and m != "NAN"])

def get_unique_shades():
    conn = sqlite3.connect(db_file)
    df1 = pd.read_sql_query("SELECT shade_name as shade FROM shade_master", conn)
    df2 = pd.read_sql_query("SELECT shade FROM receiving", conn)
    conn.close()
    combined = pd.concat([df1['shade'], df2['shade']]).dropna().astype(str).str.strip().str.upper()
    return sorted([s for s in combined.unique() if s and s != "NAN"])

def check_user_permission(username, perm_column):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_column} FROM users WHERE username = ?", (username,))
    res = cursor.fetchone()
    conn.close()
    return res[0] == 1 if res else False

def generate_pdf_invoice(title, details_dict, df_items):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, COMP_NAME, 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, COMP_DIV, 0, 1, "C")
    pdf.cell(0, 5, COMP_ADDR, 0, 1, "C")
    pdf.cell(0, 5, f"{COMP_MSME} | {COMP_GST}", 0, 1, "C")
    pdf.cell(0, 5, f"{COMP_STATE} | {COMP_EMAIL}", 0, 1, "C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, title, 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    
    for k, v in details_dict.items():
        pdf.cell(0, 6, f"{k}: {v}", 0, 1, "L")
    pdf.ln(4)
    
    if not df_items.empty:
        pdf.set_font("Arial", "B", 9)
        cols = list(df_items.columns)
        col_w = max(190 // len(cols), 15)
        for c in cols:
            pdf.cell(col_w, 7, str(c)[:12], 1, 0, "C")
        pdf.ln()
        
        pdf.set_font("Arial", "", 8)
        for _, row in df_items.iterrows():
            for c in cols:
                pdf.cell(col_w, 6, str(row[c])[:15], 1, 0, "C")
            pdf.ln()
            
    return pdf.output(dest='S').encode('latin1')

def import_excel_stock(uploaded_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        df_rec = pd.read_excel(uploaded_file, sheet_name=0)
        df_rec.columns = [str(c).strip().title() for c in df_rec.columns]
        
        count = 0
        for _, row in df_rec.iterrows():
            bh_reel = str(row.get('Company Reel', row.get('Bhaavya Reel No', ''))).strip().upper()
            if not bh_reel or bh_reel == 'NAN': continue
            
            m_val = str(row.get('Mill', '')).strip().upper()
            s_val = str(row.get('Shade', '')).strip().upper()
            if m_val and m_val != 'NAN': cursor.execute("INSERT OR IGNORE INTO mill_master (mill_name) VALUES (?)", (m_val,))
            if s_val and s_val != 'NAN': cursor.execute("INSERT OR IGNORE INTO shade_master (shade_name) VALUES (?)", (s_val,))

            cursor.execute("SELECT COALESCE(MAX(sr), 0) + 1 FROM receiving")
            next_sr = cursor.fetchone()[0]

            cursor.execute('''
                INSERT OR REPLACE INTO receiving (sr, date, company_reel, mill_reel, mill, gsm, bf, deckle, weight, shade, supplier, location, remarks, rate, trans_charges, grn_no, bill_no, entered_by, po_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (
                int(row.get('Sr', next_sr)), 
                str(row.get('Date', datetime.today().strftime('%Y-%m-%d'))).split(" ")[0], 
                bh_reel, 
                str(row.get('Mill Reel No', row.get('Mill Reel', ''))).strip().upper(), 
                m_val, 
                int(row.get('Gsm', 0) if pd.notnull(row.get('Gsm')) else 0), 
                int(row.get('Bf', 0) if pd.notnull(row.get('Bf')) else 0), 
                int(row.get('Deckle', 0) if pd.notnull(row.get('Deckle')) else 0), 
                float(row.get('Weight', 0.0) if pd.notnull(row.get('Weight')) else 0.0), 
                s_val, 
                str(row.get('Supplier', '')).strip().upper(), 
                str(row.get('Location', 'MAIN GODOWN')).strip().upper(), 
                str(row.get('Remarks', '')).strip().upper(), 
                float(row.get('Rate', 0.0) if pd.notnull(row.get('Rate')) else 0.0), 
                float(row.get('Trans Charges', 0.0) if pd.notnull(row.get('Trans Charges')) else 0.0), 
                str(row.get('Grn No', '')).strip().upper(), 
                str(row.get('Bill No', '')).strip().upper(), 
                st.session_state.logged_user
            ))
            count += 1
        conn.commit()
        conn.close()
        st.cache_data.clear()
        return True, f"🎉 MIGRATION SUCCESSFUL! {count} Fresh Reels ko database mein import kar diya gaya hai."
    except Exception as e: return False, f"❌ Excel Import Error: {str(e)}"

def import_excel_consumption(uploaded_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        df_cons = pd.read_excel(uploaded_file, sheet_name=0)
        df_cons.columns = [str(c).strip().title() for c in df_cons.columns]
        
        count = 0
        for _, row in df_cons.iterrows():
            bh_reel = str(row.get('Company Reel', row.get('Bhaavya Reel No', ''))).strip().upper()
            if not bh_reel or bh_reel == 'NAN': continue
            
            cursor.execute("SELECT weight FROM receiving WHERE company_reel = ?", (bh_reel,))
            rec_row = cursor.fetchone()
            if not rec_row: continue
            orig_wt = rec_row[0]

            cursor.execute("SELECT SUM(weight_consumed) FROM consumption WHERE company_reel = ?", (bh_reel,))
            past_c = cursor.fetchone()[0] or 0.0
            curr_bal = orig_wt - past_c

            rem_wt = float(row.get('Remaining Weight', row.get('Remaining Wt', row.get('Weight', 0.0))))
            if rem_wt >= curr_bal: continue

            consumed_wt = curr_bal - rem_wt
            machine = str(row.get('Machine', row.get('Machine Name', 'B FLUTE'))).strip().upper()
            if rem_wt <= 200.0:
                machine = f"{machine} - BABY REEL"

            cursor.execute('''
                INSERT INTO consumption (date, company_reel, weight_consumed, machine, entered_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                str(row.get('Date', datetime.today().strftime('%Y-%m-%d'))).split(" ")[0],
                bh_reel,
                consumed_wt,
                machine,
                st.session_state.logged_user
            ))
            count += 1
        conn.commit()
        conn.close()
        st.cache_data.clear()
        return True, f"🎉 SUCCESS! {count} Consumption entries successfully import ho gayi hain."
    except Exception as e: return False, f"❌ Consumption Excel Import Error: {str(e)}"

def get_shortcut_dates(shortcut_name):
    today = datetime.today().date()
    if shortcut_name == "📅 TODAY": return today, today
    elif shortcut_name == "📅 YESTERDAY": return today - timedelta(days=1), today - timedelta(days=1)
    elif shortcut_name == "📅 THIS MONTH": return today.replace(day=1), today
    elif shortcut_name == "📅 LAST 3 MONTH": return today - timedelta(days=90), today
    elif shortcut_name == "📅 CURRENT FINANCIAL YEAR":
        if today.month >= 4: return today.replace(month=4, day=1), today
        else: return today.replace(year=today.year - 1, month=4, day=1), today
    return None

if "r_start" not in st.session_state: st.session_state.r_start = datetime.today().date() - timedelta(days=30)
if "r_end" not in st.session_state: st.session_state.r_end = datetime.today().date()
if "c_start" not in st.session_state: st.session_state.c_start = datetime.today().date() - timedelta(days=30)
if "c_end" not in st.session_state: st.session_state.c_end = datetime.today().date()
if "a_start" not in st.session_state: st.session_state.a_start = datetime.today().date() - timedelta(days=30)
if "a_end" not in st.session_state: st.session_state.a_end = datetime.today().date()

if "rec_version" not in st.session_state: st.session_state.rec_version = 0
if "cons_version" not in st.session_state: st.session_state.cons_version = 0
if "audit_version" not in st.session_state: st.session_state.audit_version = 0

def handle_rec_shortcut():
    val = st.session_state.get("rec_shortcut_pill")
    if val:
        dates = get_shortcut_dates(val)
        if dates: st.session_state.r_start, st.session_state.r_end, st.session_state.rec_version = dates[0], dates[1], st.session_state.rec_version + 1

def handle_cons_shortcut():
    val = st.session_state.get("cons_shortcut_pill")
    if val:
        dates = get_shortcut_dates(val)
        if dates: st.session_state.c_start, st.session_state.c_end, st.session_state.cons_version = dates[0], dates[1], st.session_state.cons_version + 1

def handle_audit_shortcut():
    val = st.session_state.get("audit_shortcut_pill")
    if val:
        dates = get_shortcut_dates(val)
        if dates: st.session_state.a_start, st.session_state.a_end, st.session_state.audit_version = dates[0], dates[1], st.session_state.audit_version + 1

# --- MAIN TITLE & SIDEBAR ---
st.sidebar.markdown(f"**{COMP_NAME}**")
st.sidebar.markdown(f"👤 **Logged User:** `{st.session_state.logged_user}` ({st.session_state.user_role})")
if st.sidebar.button("🚪 LOGOUT"):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.logged_user = ""
    st.rerun()

st.sidebar.write("---")
st.sidebar.header("🔍 QUICK REEL SEARCH")
search_reel = st.sidebar.text_input("ENTER REEL NO (Bhaavya or Mill Reel):")
if search_reel:
    df_search_rec = get_data("SELECT r.date as [DATE], r.company_reel as [BHAAVYA REEL NO], r.mill_reel as [MILL REEL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE], r.weight as [WEIGHT], r.shade as [SHADE], r.supplier as [SUPPLIER], r.location as [LOCATION] FROM receiving r WHERE r.company_reel = ? OR r.mill_reel = ?", (search_reel.strip().upper(), search_reel.strip().upper()))
    
    if not df_search_rec.empty:
        bh_r_no = df_search_rec['BHAAVYA REEL NO'].values[0]
        orig_wt = float(df_search_rec['WEIGHT'].values[0])
        rec_date = df_search_rec['DATE'].values[0]
        mill_n = df_search_rec['MILL'].values[0]
        gsm_n = df_search_rec['GSM'].values[0]
        bf_n = df_search_rec['BF'].values[0]
        deckle_n = df_search_rec['DECKLE'].values[0]
        shade_n = df_search_rec['SHADE'].values[0]
        
        df_search_cons = get_data("SELECT c.id as [ID], c.date as [DATE], c.weight_consumed as [USED (KG)], c.machine as [REMARKS / MACHINE] FROM consumption c WHERE c.company_reel = ? ORDER BY c.date ASC", (bh_r_no,))
        total_c_wt = float(df_search_cons['USED (KG)'].sum()) if not df_search_cons.empty else 0.0
        net_balance = orig_wt - total_c_wt
        
        st.sidebar.success("✅ REEL FOUND IN STOCK!")
        st.sidebar.markdown(f"**🏷️ Bhaavya Reel:** `{bh_r_no}`")
        st.sidebar.markdown(f"**🏭 Mill:** `{mill_n}` | **Shade:** `{shade_n}`")
        st.sidebar.markdown(f"**📏 Specs:** `{deckle_n}mm` | `{gsm_n}GSM` | `{bf_n}BF`")
        st.sidebar.markdown(f"**📅 Rec. Date:** `{rec_date}`")
        st.sidebar.write("---")
        st.sidebar.metric("🏋️‍♂️ OPENING/ORIGINAL WT", f"{orig_wt:,.1f} KG")
        st.sidebar.metric("📉 TOTAL CONSUMED / ADJ.", f"{total_c_wt:,.1f} KG")
        if net_balance > 0: st.sidebar.metric("🔵 CURRENT NET BALANCE", f"{net_balance:,.1f} KG")
        else: st.sidebar.error(f"🔴 CURRENT BALANCE: {net_balance:,.1f} KG (EMPTY)")
    else:
        st.sidebar.error("❌ REEL NO NOT FOUND!")

can_view_stk = check_user_permission(st.session_state.logged_user, 'can_view_stock')
can_add = check_user_permission(st.session_state.logged_user, 'can_add_entry')

# --- NAVIGATION PILLS / SELECTOR ---
if st.session_state.user_role == "SUPER_ADMIN":
    menu_options = [
        "📊 LIVE NET STOCK BALANCE", "📑 PURCHASE ORDERS (PO)", "📥 GRN RECEIVING ENTRY", 
        "📉 DAILY CONSUMPTION ENTRY", "📐 DECKLE CALCULATOR", "🛠️ PHYSICAL STOCK ADJUSTMENT", "🚨 MSL & LOW STOCK ALERTS", 
        "📤 EXCEL STOCK IMPORT", "📈 CONSUMPTION & SUPPLIER REPORTS", "📋 HISTORY LOGS", 
        "💾 BACKUP & RESTORE", "🔐 CHANGE PASSWORD & USERS"
    ]
elif st.session_state.user_role == "ADMIN":
    menu_options = [
        "📊 LIVE NET STOCK BALANCE", "📑 PURCHASE ORDERS (PO)", "📥 GRN RECEIVING ENTRY", 
        "📉 DAILY CONSUMPTION ENTRY", "📐 DECKLE CALCULATOR", "🛠️ PHYSICAL STOCK ADJUSTMENT", "🚨 MSL & LOW STOCK ALERTS", 
        "📤 EXCEL STOCK IMPORT", "📈 CONSUMPTION & SUPPLIER REPORTS", "📋 HISTORY LOGS", 
        "💾 BACKUP & RESTORE"
    ]
else:
    menu_options = []
    if can_view_stk: menu_options.append("📊 LIVE NET STOCK BALANCE")
    menu_options.extend([
        "📑 PURCHASE ORDERS (PO)", "📥 GRN RECEIVING ENTRY", "📉 DAILY CONSUMPTION ENTRY", "📐 DECKLE CALCULATOR",
        "📈 CONSUMPTION & SUPPLIER REPORTS", "📋 HISTORY LOGS"
    ])

selected_menu = st.pills("📌 NAVIGATION MENU", menu_options, selection_mode="single", default=menu_options[0])
st.write("---")

tab_live = (selected_menu == "📊 LIVE NET STOCK BALANCE")
tab_po = (selected_menu == "📑 PURCHASE ORDERS (PO)")
tab_rec = (selected_menu == "📥 GRN RECEIVING ENTRY")
tab_cons = (selected_menu == "📉 DAILY CONSUMPTION ENTRY")
tab_calc = (selected_menu == "📐 DECKLE CALCULATOR")
tab_adj = (selected_menu == "🛠️ PHYSICAL STOCK ADJUSTMENT")
tab_msl = (selected_menu == "🚨 MSL & LOW STOCK ALERTS")
tab_import = (selected_menu == "📤 EXCEL STOCK IMPORT")
tab_rep = (selected_menu == "📈 CONSUMPTION & SUPPLIER REPORTS")
tab_hist = (selected_menu == "📋 HISTORY LOGS")
tab_backup = (selected_menu == "💾 BACKUP & RESTORE")
tab_users = (selected_menu == "🔐 CHANGE PASSWORD & USERS")


# TAB 1: LIVE BALANCE WITH CHART
if tab_live:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>✨ REAL-TIME AVAILABLE STOCK BALANCE</h2>", unsafe_allow_html=True)
    query_live = """
    SELECT 
        r.grn_no as [GRN NO], r.bill_no as [CUSTOMER BILL NO], UPPER(r.mill) as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE (MM)],
        ROUND(cast(r.deckle as REAL) / 25.4, 1) as [DECKLE (INCH)], UPPER(r.shade) as [SHADE],
        r.mill_reel as [MILL REEL NO], r.company_reel as [BHAAVYA REEL NO],
        CASE 
            WHEN (r.weight - COALESCE(c.weight_consumed, 0)) <= 0 THEN 'EMPTY' 
            WHEN (r.weight - COALESCE(c.weight_consumed, 0)) <= 200.0 THEN 'BABY REEL' 
            ELSE 'LIVE' 
        END as [STATUS],
        r.date as [LAST RECEIVING DATE],
        r.weight as [SUM OF ORIGINAL WEIGHT], COALESCE(c.weight_consumed, 0) as [SUM OF TOTAL CONSUMED],
        (r.weight - COALESCE(c.weight_consumed, 0)) as [SUM OF BALANCE WEIGHT],
        r.rate as [RATE/KG], r.trans_charges as [TRANS CHARGES], r.entered_by as [ENTERED BY],
        CLEAN_NAME(r.mill) as [CLEAN_MILL_KEY]
    FROM receiving r
    LEFT JOIN (
        SELECT company_reel, SUM(weight_consumed) as weight_consumed 
        FROM consumption GROUP BY company_reel
    ) c ON r.company_reel = c.company_reel
    ORDER BY r.date DESC
    """
    try:
        df_base = get_data(query_live)
        unique_mills_df = df_base.drop_duplicates(subset=["CLEAN_MILL_KEY"])
        available_mills = sorted(list(unique_mills_df["MILL"].dropna().unique()))
        
        selected_mills = st.session_state.get("pills_mills_key", [])
        selected_deckle_mm = st.session_state.get("pills_deckle_key", [])
        selected_gsm = st.session_state.get("pills_gsm_key", [])
        selected_bf = st.session_state.get("pills_bf_key", [])
        selected_shade = st.session_state.get("pills_shade_key", [])

        df_filtered = df_base.copy()
        if selected_mills:
            clean_selected = ["".join(str(m).upper().replace(".", "").replace(" ", "").split()) for m in selected_mills]
            df_filtered = df_filtered[df_filtered["CLEAN_MILL_KEY"].isin(clean_selected)]
        if selected_deckle_mm: df_filtered = df_filtered[df_filtered["DECKLE (MM)"].isin(selected_deckle_mm)]
        if selected_gsm: df_filtered = df_filtered[df_filtered["GSM"].isin(selected_gsm)]
        if selected_bf: df_filtered = df_filtered[df_filtered["BF"].isin(selected_bf)]
        if selected_shade: df_filtered = df_filtered[df_filtered["SHADE"].isin(selected_shade)]

        df_live_reels = df_filtered[df_filtered['SUM OF BALANCE WEIGHT'] > 0]
        if not df_live_reels.empty:
            chart_df = df_live_reels.groupby("MILL").agg(
                TOTAL_WEIGHT=('SUM OF BALANCE WEIGHT', 'sum'),
                REEL_COUNT=('BHAAVYA REEL NO', 'count')
            ).reset_index()
            
            chart_df['WT_LABEL'] = chart_df['TOTAL_WEIGHT'].apply(lambda w: f"{int(w):,} KG")
            chart_df['COUNT_LABEL'] = chart_df['REEL_COUNT'].apply(lambda c: f"{c} NOS")

            st.markdown("### 📊 MILL-WISE TOTAL AVAILABLE WEIGHT & REEL COUNT")
            bars = alt.Chart(chart_df).mark_bar(color='#4A90E2', opacity=0.85, size=30).encode(
                x=alt.X('MILL:N', sort='-y', title='MILL NAME', axis=alt.Axis(labelAngle=270, labelFontWeight='bold')),
                y=alt.Y('TOTAL_WEIGHT:Q', title='TOTAL WEIGHT (KG)'),
                tooltip=[alt.Tooltip('MILL:N', title='MILL NAME'), alt.Tooltip('TOTAL_WEIGHT:Q', title='TOTAL WEIGHT (KG)', format=',.0f'), alt.Tooltip('REEL_COUNT:Q', title='TOTAL REELS')]
            )
            wt_labels = bars.mark_text(align='left', baseline='middle', dx=14, angle=270, color='black', fontWeight='bold', fontSize=11).encode(text='WT_LABEL:N')
            count_labels = bars.mark_text(align='right', baseline='middle', dx=-14, angle=270, color='#D00000', fontWeight='bold', fontSize=11).encode(text='COUNT_LABEL:N')
            final_chart = (bars + wt_labels + count_labels).properties(height=500, width=alt.Step(70))
            st.altair_chart(final_chart, use_container_width=False)

        st.write("---")
        st.markdown("### 🎛️ CLICK BUTTONS TO FILTER")
        st.pills("🏭 MILL", available_mills, selection_mode="multi", key="pills_mills_key")
        df_curr = df_base.copy()
        if selected_mills:
            clean_selected = ["".join(str(m).upper().replace(".", "").replace(" ", "").split()) for m in selected_mills]
            df_curr = df_curr[df_curr["CLEAN_MILL_KEY"].isin(clean_selected)]
            
        st.pills("📏 DECKLE (MM)", sorted(list(df_curr["DECKLE (MM)"].dropna().unique())), selection_mode="multi", key="pills_deckle_key")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1: st.pills("📄 GSM", sorted(list(df_curr["GSM"].dropna().unique())), selection_mode="multi", key="pills_gsm_key")
        with col_s2: st.pills("💪 BF", sorted(list(df_curr["BF"].dropna().unique())), selection_mode="multi", key="pills_bf_key")
        with col_s3: st.pills("🎨 SHADE", sorted(list(df_curr["SHADE"].dropna().unique())), selection_mode="multi", key="pills_shade_key")

        st.write("---")
        st.markdown("<h2 style='text-align: center;'>📊 CURRENT LIVE STOCK IN GODOWN</h2>", unsafe_allow_html=True)
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("🏋️‍♂️ TOTAL AVAILABLE STOCK WEIGHT", f"{df_filtered['SUM OF BALANCE WEIGHT'].sum():,.2f} KG")
        col_m2.metric("🧻 TOTAL AVAILABLE REELS", f"{len(df_filtered[df_filtered['SUM OF BALANCE WEIGHT'] > 0])} NOS")
        st.dataframe(df_filtered.drop(columns=["CLEAN_MILL_KEY"]), use_container_width=True)
    except Exception as e: st.error(f"Error: {e}")

# TAB 1.5: PURCHASE ORDERS (PO) MANAGEMENT & EDITING
if tab_po:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📑 PURCHASE ORDER (PO) MANAGEMENT & PDF PRINTING</h2>", unsafe_allow_html=True)
    
    with st.form("create_po_form"):
        st.markdown("### ➕ GENERATE NEW PURCHASE ORDER (PO)")
        po_c1, po_c2, po_c3, po_c4 = st.columns(4)
        po_date = po_c1.date_input("PO DATE", datetime.today())
        po_no_input = po_c2.text_input("PO NUMBER (e.g. PO-2026-01)")
        
        mill_list_po = get_unique_mills()
        po_mill = po_c3.selectbox("SELECT MILL", [""] + mill_list_po)
        po_gsm_str = po_c4.text_input("GSM", value="")
        
        po_c5, po_c6, po_c7, po_c8 = st.columns(4)
        po_bf_str = po_c5.text_input("BF", value="")
        po_deckle_str = po_c6.text_input("DECKLE (MM)", value="")
        
        shade_list_po = get_unique_shades()
        po_shade = po_c7.selectbox("SHADE", [""] + shade_list_po)
        po_qty_str = po_c8.text_input("ORDERED QUANTITY (KG)", value="")
        
        if st.form_submit_button("💾 GENERATE & SAVE PO"):
            if not po_no_input.strip() or not po_mill:
                st.error("❌ Kripya PO Number aur Mill Name dono enter karein!")
            else:
                try:
                    po_gsm = int(po_gsm_str) if po_gsm_str else 0
                    po_bf = int(po_bf_str) if po_bf_str else 0
                    po_deckle = int(po_deckle_str) if po_deckle_str else 0
                    po_qty = float(po_qty_str) if po_qty_str else 0.0

                    m_up = po_mill.strip().upper()
                    s_up = po_shade.strip().upper()
                    if m_up: run_query("INSERT OR IGNORE INTO mill_master (mill_name) VALUES (?)", (m_up,))
                    if s_up: run_query("INSERT OR IGNORE INTO shade_master (shade_name) VALUES (?)", (s_up,))

                    run_query("INSERT INTO purchase_orders (po_no, date, mill, gsm, bf, deckle, shade, ordered_qty, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')",
                              (po_no_input.strip().upper(), str(po_date), m_up, po_gsm, po_bf, po_deckle, s_up, po_qty))
                    st.success(f"🎉 PO `{po_no_input.strip().upper()}` successfully generate ho gaya hai!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error generating PO: {e}")

    st.write("---")
    st.markdown("### 📋 ACTIVE & RECENT PURCHASE ORDERS STATUS")
    
    all_mills_po = get_unique_mills()
    selected_mill_filter = st.selectbox("🏭 FILTER BY MILL (PENDING PO SEARCH)", ["-- ALL MILLS --"] + all_mills_po, key="mill_po_filter_dropdown")

    query_po_Conditions = "WHERE 1=1"
    query_params = []
    if selected_mill_filter != "-- ALL MILLS --":
        query_po_Conditions += " AND UPPER(po.mill) = ?"
        query_params.append(selected_mill_filter.strip().upper())

    query_po_list = f"""
        SELECT 
            po.id as [Sr No],
            po.po_no as [PO NO],
            po.date as [PO DATE],
            po.mill as [MILL],
            po.gsm as [GSM],
            po.bf as [BF],
            po.deckle as [DECKLE],
            po.shade as [SHADE],
            po.ordered_qty as [ORDERED (KG)],
            COALESCE(SUM(r.weight), 0.0) as [RECEIVED (KG)],
            (po.ordered_qty - COALESCE(SUM(r.weight), 0.0)) as [PENDING (KG)],
            CASE 
                WHEN (po.ordered_qty - COALESCE(SUM(r.weight), 0.0)) <= 0 THEN 'COMPLETED' 
                ELSE 'PENDING' 
            END as [STATUS]
        FROM purchase_orders po
        LEFT JOIN receiving r ON r.po_id = po.id
        {query_po_Conditions}
        GROUP BY po.id
        ORDER BY po.id DESC
    """
    df_po_display = get_data(query_po_list, tuple(query_params))
    if not df_po_display.empty:
        st.dataframe(df_po_display, use_container_width=True)
        
        tot_ordered = df_po_display['ORDERED (KG)'].sum()
        tot_received = df_po_display['RECEIVED (KG)'].sum()
        tot_pending = df_po_display['PENDING (KG)'].sum()
        
        st.info(f"📊 **SELECTION TOTALS** | 📦 Ordered Qty: **{tot_ordered:,.2f} KG** | 📥 Received Qty: **{tot_received:,.2f} KG** | ⏳ Pending Qty: **{tot_pending:,.2f} KG**")

        st.write("---")
        st.markdown("### 🖨️ DOWNLOAD PURCHASE ORDER PDF INVOICE")
        unique_po_list_pdf = sorted(list(df_po_display['PO NO'].dropna().unique()), key=str)
        sel_po_pdf = st.selectbox("Select PO No to Print PDF", [""] + unique_po_list_pdf, key="pdf_po_dropdown_key")
        
        if sel_po_pdf:
            po_row_data = df_po_display[df_po_display['PO NO'] == sel_po_pdf].iloc[0]
            details = {
                "PO Number": po_row_data['PO NO'],
                "Date": po_row_data['PO DATE'],
                "Mill Name": po_row_data['MILL'],
                "GSM / BF / Deckle": f"{po_row_data['GSM']} GSM | {po_row_data['BF']} BF | {po_row_data['DECKLE']} mm",
                "Shade": po_row_data['SHADE'],
                "Ordered Qty": f"{po_row_data['ORDERED (KG)']} KG",
                "Status": po_row_data['STATUS']
            }
            pdf_bytes = generate_pdf_invoice("PURCHASE ORDER INVOICE", details, pd.DataFrame())
            st.download_button(
                label=f"📥 DOWNLOAD PDF FOR PO: {sel_po_pdf}",
                data=pdf_bytes,
                file_name=f"PO_{sel_po_pdf}.pdf",
                mime="application/pdf"
            )

        st.write("---")
        st.markdown("### ✏️ EDIT OR DELETE EXISTING PURCHASE ORDER (PO)")
        
        typed_po_no = st.text_input("1️⃣ Enter PO Number Manually (e.g., 119)", value="", key="manual_po_input_key")
        
        sel_id = None
        if typed_po_no.strip():
            df_filtered_po = df_po_display[df_po_display['PO NO'].astype(str).str.upper() == typed_po_no.strip().upper()]
            
            if not df_filtered_po.empty:
                po_options_map = {}
                po_labels = [""]
                for _, row in df_filtered_po.iterrows():
                    label = f"Sr No: {row['Sr No']} | Mill: {row['MILL']} | {row['GSM']}GSM | {row['BF']}BF | {row['DECKLE']}mm | Qty: {row['ORDERED (KG)']}kg"
                    po_labels.append(label)
                    po_options_map[label] = int(row['Sr No'])
                
                sel_sr_label = st.selectbox("2️⃣ Select Specific Sr No for this PO", po_labels, key="edit_sr_no_dropdown_key")
                
                if sel_sr_label:
                    sel_id = po_options_map[sel_sr_label]
            else:
                st.warning(f"⚠️ Yeh PO Number `{typed_po_no}` database mein nahi mila!")

        if sel_id:
            po_info = get_data("SELECT date, mill, gsm, bf, deckle, shade, ordered_qty FROM purchase_orders WHERE id = ?", (sel_id,))
            if not po_info.empty:
                with st.form("edit_po_form"):
                    e_po_date = st.date_input("PO Date", value=datetime.strptime(po_info['date'].values[0], "%Y-%m-%d").date())
                    e_po_mill = st.selectbox("Mill Name", mill_list_po, index=mill_list_po.index(po_info['mill'].values[0]) if po_info['mill'].values[0] in mill_list_po else 0)
                    
                    ep_c1, ep_c2, ep_c3 = st.columns(3)
                    e_po_gsm = ep_c1.number_input("GSM", value=int(po_info['gsm'].values[0]))
                    e_po_bf = ep_c2.number_input("BF", value=int(po_info['bf'].values[0]))
                    e_po_deckle = ep_c3.number_input("Deckle", value=int(po_info['deckle'].values[0]))
                    
                    ep_c4, ep_c5 = st.columns(2)
                    e_po_shade = ep_c4.selectbox("Shade", shade_list_po, index=shade_list_po.index(po_info['shade'].values[0]) if po_info['shade'].values[0] in shade_list_po else 0)
                    e_po_qty = ep_c5.number_input("Ordered Qty (KG)", value=float(po_info['ordered_qty'].values[0]))
                    
                    col_po_upd, col_po_del = st.columns(2)
                    if col_po_upd.form_submit_button("💾 UPDATE PO DETAILS"):
                        run_query("UPDATE purchase_orders SET date = ?, mill = ?, gsm = ?, bf = ?, deckle = ?, shade = ?, ordered_qty = ? WHERE id = ?",
                                  (str(e_po_date), e_po_mill.strip().upper(), int(e_po_gsm), int(e_po_bf), int(e_po_deckle), e_po_shade.strip().upper(), float(e_po_qty), sel_id))
                        st.success("🎉 PO entry successfully update ho gayi hai!")
                        st.rerun()
                        
                    if col_po_del.form_submit_button("🗑️ DELETE THIS PO"):
                        run_query("DELETE FROM purchase_orders WHERE id = ?", (sel_id,))
                        run_query("UPDATE receiving SET po_id = 0 WHERE po_id = ?", (sel_id,))
                        st.success("🗑️ PO entry deleted successfully!")
                        st.rerun()
    else:
        st.info("ℹ️ Abhi tak koi Purchase Order generate nahi kiya gaya hai.")

# TAB 2: GRN RECEIVING ENTRY (MANUAL & EXCEL BULK UPLOAD)
if tab_rec:
    if not can_add:
        st.error("🔒 Access Denied: Aapke paas naye Receiving entry add karne ke rights nahi hain.")
    else:
        st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>📥 GRN RECEIVING - MANUAL & EXCEL BULK UPLOAD</h2>", unsafe_allow_html=True)
        
        rec_mode = st.radio("CHOOSE ENTRY MODE", ["✍️ Manual Entry (Grid)", "📤 Excel File Bulk Upload"], horizontal=True)
        
        if rec_mode == "📤 Excel File Bulk Upload":
            st.markdown("### 📤 UPLOAD GRN RECEIVING EXCEL FILE")
            st.info("Excel file mein columns hone chahiye: `Company Reel`, `Mill`, `GSM`, `BF`, `Deckle`, `Weight`, `Shade`, `Supplier`, etc.")
            
            sample_df = pd.DataFrame([{
                'Sr': 1, 'Date': datetime.today().strftime('%Y-%m-%d'), 'Company Reel': '117083', 'Mill Reel No': '107053', 
                'Mill': 'BEST', 'GSM': 150, 'BF': 28, 'Deckle': 1000, 'Weight': 1200.0, 'Shade': 'GOLDEN', 
                'Supplier': 'BEST', 'Location': 'MAIN GODOWN', 'Rate': 35.0, 'Trans Charges': 0.0, 'Grn No': 'GRN-01', 'Bill No': 'B-01'
            }])
            out_sample = io.BytesIO()
            with pd.ExcelWriter(out_sample, engine='openpyxl') as writer:
                sample_df.to_excel(writer, index=False, sheet_name='RECEIVING')
            st.download_button("📥 DOWNLOAD SAMPLE RECEIVING EXCEL", data=out_sample.getvalue(), file_name="Receiving_Sample.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            up_rec_file = st.file_uploader("Upload Receiving Excel (.xlsx)", type=["xlsx"], key="rec_file_up")
            if up_rec_file is not None and st.button("🚀 PROCESS & IMPORT RECEIVING EXCEL"):
                success, msg = import_excel_stock(up_rec_file)
                if success: st.success(msg)
                else: st.error(msg)
        else:
            st.markdown("#### 📑 1. CHALAN / INVOICE HEADER DETAILS")
            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            grn_date = col_h1.date_input("RECEIVING DATE", datetime.today())
            grn_no_val = col_h2.text_input("GRN NO")
            bill_no_val = col_h3.text_input("CUSTOMER BILL NO")
            grn_supplier = col_h4.text_input("SUPPLIER NAME")
            
            col_f1, col_f2, col_f3 = st.columns(3)
            mill_list_rec = get_unique_mills()
            grn_mill = col_f1.selectbox("SELECT MILL NAME", [""] + mill_list_rec)
            grn_trans = col_f2.text_input("TOTAL TRANSPORTATION CHARGES", value="")
            grn_location = col_f3.text_input("GODOWN LOCATION", value="MAIN GODOWN")

            df_pending_pos = get_data("SELECT id, po_no, mill, gsm, bf, deckle, shade, (ordered_qty - COALESCE((SELECT SUM(weight) FROM receiving WHERE po_id = purchase_orders.id), 0)) as pending FROM purchase_orders WHERE (ordered_qty - COALESCE((SELECT SUM(weight) FROM receiving WHERE po_id = purchase_orders.id), 0)) > 0")
            po_options_dict = {"-- NO PO LINK (Direct Receiving) --": 0}
            for _, prow in df_pending_pos.iterrows():
                po_options_dict[f"PO: {prow['po_no']} ({prow['mill']} | {prow['gsm']}GSM | {prow['bf']}BF | {prow['deckle']}mm | {prow['shade']} | Pend: {prow['pending']}kg)"] = int(prow['id'])

            selected_po_label = st.selectbox("🔗 LINK PENDING PURCHASE ORDER (OPTIONAL)", list(po_options_dict.keys()))
            linked_po_id = po_options_dict[selected_po_label]
            
            st.markdown("#### ⚙️ 2. COLUMN SEQUENCE CONFIGURATOR")
            seq_choice = st.selectbox(
                "Apne hisab se columns ka sequence chunye:",
                [
                    "📐 Deckle (mm) ➡️ 📄 GSM ➡️ 💪 BF ➡️ 💰 Rate/Kg",
                    "📄 GSM ➡️ 💪 BF ➡️ 💰 Rate/Kg ➡️ 📐 Deckle (mm)",
                    "💪 BF ➡️ 💰 Rate/Kg ➡️ 📐 Deckle (mm) ➡️ 📄 GSM"
                ]
            )

            with st.expander("➕ Add New Mill Name"):
                new_mill_input = st.text_input("Enter New Mill Name:")
                if st.button("Save New Mill") and new_mill_input:
                    run_query("INSERT OR IGNORE INTO mill_master (mill_name) VALUES (?)", (new_mill_input.strip().upper(),))
                    st.rerun()

            shade_list_rec = get_unique_shades()
            shade_options = [""] + shade_list_rec
            with st.expander("➕ Add New Shade Name"):
                new_shade_input = st.text_input("Enter New Shade Name:")
                if st.button("Save New Shade") and new_shade_input:
                    run_query("INSERT OR IGNORE INTO shade_master (shade_name) VALUES (?)", (new_shade_input.strip().upper(),))
                    st.rerun()

            st.write("---")
            st.markdown("#### 🧻 3. ADD INDIVIDUAL REEL DATA")
            if "grid_reels_count" not in st.session_state: st.session_state.grid_reels_count = 4
            if "grn_realtime_rates" not in st.session_state: st.session_state.grn_realtime_rates = {}

            h_col0, h_col1, h_col2, h_v1, h_v2, h_v3, h_v4, h_col6, h_col7, h_col8 = st.columns([0.6, 1.5, 1.5, 1.1, 1.1, 1.1, 1.1, 1.3, 1.5, 1.8])
            h_col0.markdown("**Item**"); h_col1.markdown("**Bhaavya Reel No ***"); h_col2.markdown("**Mill Reel No**")
            
            if "Deckle (mm) ➡️ 📄 GSM" in seq_choice:
                h_v1.markdown("**Deckle(mm)**"); h_v2.markdown("**GSM**"); h_v3.markdown("**BF**"); h_v4.markdown("**Rate/Kg**")
            elif "GSM ➡️ 💪 BF" in seq_choice:
                h_v1.markdown("**GSM**"); h_v2.markdown("**BF**"); h_v4.markdown("**Rate/Kg**"); h_v3.markdown("**Deckle(mm)**")
            else:
                h_v1.markdown("**BF**"); h_v2.markdown("**Rate/Kg**"); h_v3.markdown("**Deckle(mm)**"); h_v4.markdown("**GSM**")
                
            h_col6.markdown("**Weight(Kg)***"); h_col7.markdown("**Shade**"); h_col8.markdown("**Remarks**")

            for idx in range(st.session_state.grid_reels_count):
                if "Deckle (mm) ➡️ 📄 GSM" in seq_choice:
                    cur_bf = st.session_state.get(f"v3_bf_{idx}", ""); cur_rate = st.session_state.get(f"v4_rat_{idx}", "")
                elif "GSM ➡️ 💪 BF" in seq_choice:
                    cur_bf = st.session_state.get(f"v2_bf_{idx}", ""); cur_rate = st.session_state.get(f"v3_rat_{idx}", "")
                else:
                    cur_bf = st.session_state.get(f"v1_bf_{idx}", ""); cur_rate = st.session_state.get(f"v2_rat_{idx}", "")
                if cur_bf and cur_rate:
                    st.session_state.grn_realtime_rates[str(cur_bf).strip()] = str(cur_rate).strip()

            saved_items_list = []
            for i in range(st.session_state.grid_reels_count):
                r_col0, r_col1, r_col2, r_v1, r_v2, r_v3, r_v4, r_col6, r_col7, r_col8 = st.columns([0.6, 1.5, 1.5, 1.1, 1.1, 1.1, 1.1, 1.3, 1.5, 1.8])
                r_col0.markdown(f"<p style='margin-top:10px; font-weight:bold; color:#1f77b4;'>#{i+1}</p>", unsafe_allow_html=True)
                bh_val = r_col1.text_input("Bhaavya", value="", key=f"bh_st_{i}", label_visibility="collapsed")
                ml_val = r_col2.text_input("MillReel", value="", key=f"ml_st_{i}", label_visibility="collapsed")
                
                dec_input, gsm_input, bf_input, rate_input = "", "", "", ""
                if "Deckle (mm) ➡️ 📄 GSM" in seq_choice:
                    dec_input = r_v1.text_input("Dec", value="", key=f"v1_dec_{i}", label_visibility="collapsed")
                    gsm_input = r_v2.text_input("Gsm", value="", key=f"v2_gsm_{i}", label_visibility="collapsed")
                    bf_input = r_v3.text_input("Bf", value="", key=f"v3_bf_{i}", label_visibility="collapsed")
                    matched_rate = st.session_state.grn_realtime_rates.get(str(bf_input).strip(), "") if bf_input else ""
                    rate_input = r_v4.text_input("Rate", value=matched_rate, key=f"v4_rat_{i}", label_visibility="collapsed")
                elif "GSM ➡️ 💪 BF" in seq_choice:
                    gsm_input = r_v1.text_input("Gsm", value="", key=f"v1_gsm_{i}", label_visibility="collapsed")
                    bf_input = r_v2.text_input("Bf", value="", key=f"v2_bf_{i}", label_visibility="collapsed")
                    matched_rate = st.session_state.grn_realtime_rates.get(str(bf_input).strip(), "") if bf_input else ""
                    rate_input = r_v3.text_input("Rate", value=matched_rate, key=f"v3_rat_{i}", label_visibility="collapsed")
                    dec_input = r_v4.text_input("Dec", value="", key=f"v4_dec_{i}", label_visibility="collapsed")
                else:
                    bf_input = r_v1.text_input("Bf", value="", key=f"v1_bf_{i}", label_visibility="collapsed")
                    matched_rate = st.session_state.grn_realtime_rates.get(str(bf_input).strip(), "") if bf_input else ""
                    rate_input = r_v2.text_input("Rate", value=matched_rate, key=f"v2_rat_{i}", label_visibility="collapsed")
                    dec_input = r_v3.text_input("Dec", value="", key=f"v3_dec_{i}", label_visibility="collapsed")
                    gsm_input = r_v4.text_input("Gsm", value="", key=f"v4_gsm_{i}", label_visibility="collapsed")

                wt_val = r_col6.text_input("Wt", value="", key=f"wt_st_{i}", label_visibility="collapsed")
                sh_val = r_col7.selectbox("Sh", shade_options, index=0, key=f"sh_st_{i}", label_visibility="collapsed")
                rem_val = r_col8.text_input("Rem", value="", key=f"rem_st_{i}", label_visibility="collapsed")
                
                saved_items_list.append({
                    "bhaavya_no": bh_val, "mill_no": ml_val, "deckle": dec_input,
                    "gsm": gsm_input, "bf": bf_input, "weight": wt_val, "shade": sh_val, "remarks": rem_val, "rate": rate_input
                })

            def inc_rows(): st.session_state.grid_reels_count += 1
            def dec_rows(): 
                if st.session_state.grid_reels_count > 1: st.session_state.grid_reels_count -= 1

            col_btn1, col_btn2, _ = st.columns([2, 2, 6])
            col_btn1.button("➕ Add Another Reel Row", on_click=inc_rows)
            col_btn2.button("❌ Remove Last Row", on_click=dec_rows)
            
            st.write("---")
            if st.button("💾 SAVE COMPLETE GRN CHALAN"):
                if not grn_mill: st.error("❌ Kripya Mill Name select karein!")
                else:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    success_flag = True
                    saved_count = 0
                    try:
                        cursor.execute("BEGIN TRANSACTION;")
                        m_main = grn_mill.strip().upper()
                        cursor.execute("INSERT OR IGNORE INTO mill_master (mill_name) VALUES (?)", (m_main,))

                        for index, item in enumerate(saved_items_list):
                            if not item["bhaavya_no"] or not item["weight"]:
                                st.error(f"❌ Row #{index+1} mein Bhaavya Reel No ya Weight khali hai!")
                                success_flag = False
                                break
                            
                            s_item = item["shade"].strip().upper()
                            if s_item: cursor.execute("INSERT OR IGNORE INTO shade_master (shade_name) VALUES (?)", (s_item,))

                            cursor.execute("SELECT COALESCE(MAX(sr), 0) + 1 FROM receiving")
                            next_sr = cursor.fetchone()[0]
                            cursor.execute('''
                                INSERT INTO receiving (sr, date, company_reel, mill_reel, mill, gsm, bf, deckle, weight, shade, supplier, location, remarks, rate, trans_charges, grn_no, bill_no, entered_by, po_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (next_sr, str(grn_date), item["bhaavya_no"].strip().upper(), item["mill_no"].strip().upper(), m_main, 
                                  (int(item["gsm"]) if item["gsm"] else 0), (int(item["bf"]) if item["bf"] else 0), (int(item["deckle"]) if item["deckle"] else 0), 
                                  float(item["weight"]), s_item, grn_supplier.strip().upper(), grn_location.strip().upper(), item["remarks"].strip().upper(), 
                                  (float(item["rate"]) if item["rate"] else 0.0), (float(grn_trans) if grn_trans else 0.0), grn_no_val.strip().upper(), bill_no_val.strip().upper(), st.session_state.logged_user, linked_po_id))
                            saved_count += 1
                        if success_flag:
                            conn.commit()
                            st.success(f"🎉 Success! GRN ke andar {saved_count} Reels register ho gayi hain.")
                            st.session_state.grid_reels_count = 4
                            st.session_state.grn_realtime_rates = {}
                            st.cache_data.clear()
                            st.rerun()
                        else: conn.rollback()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"❌ Save Error: {e}")
                    finally:
                        conn.close()

# TAB 3: DAILY CONSUMPTION ENTRY (MULTIPLE REEL GRID & EXCEL BULK UPLOAD)
if tab_cons:
    if not can_add:
        st.error("🔒 Access Denied: Aapke paas naye entry add karne ke rights nahi hain.")
    else:
        st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>📉 ADD DAILY CONSUMPTION ENTRY (MULTIPLE REELS & EXCEL BULK)</h2>", unsafe_allow_html=True)
        
        cons_mode = st.radio("CHOOSE CONSUMPTION MODE", ["✍️ Manual Multiple Reels Grid", "📤 Excel File Bulk Upload"], horizontal=True)
        
        if cons_mode == "📤 Excel File Bulk Upload":
            st.markdown("### 📤 UPLOAD CONSUMPTION EXCEL FILE")
            st.info("Excel file mein columns hone chahiye: `Company Reel` (ya `Bhaavya Reel No`), `Remaining Weight` (ya `Remaining Wt`), `Machine`, `Date`")
            
            sample_cons_df = pd.DataFrame([{
                'Date': datetime.today().strftime('%Y-%m-%d'), 'Company Reel': '117083', 'Remaining Weight': 250.0, 'Machine': 'B FLUTE'
            }])
            out_c_sample = io.BytesIO()
            with pd.ExcelWriter(out_c_sample, engine='openpyxl') as writer:
                sample_cons_df.to_excel(writer, index=False, sheet_name='CONSUMPTION')
            st.download_button("📥 DOWNLOAD SAMPLE CONSUMPTION EXCEL", data=out_c_sample.getvalue(), file_name="Consumption_Sample.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            up_cons_file = st.file_uploader("Upload Consumption Excel (.xlsx)", type=["xlsx"], key="cons_file_up")
            if up_cons_file is not None and st.button("🚀 PROCESS & IMPORT CONSUMPTION EXCEL"):
                success, msg = import_excel_consumption(up_cons_file)
                if success: st.success(msg)
                else: st.error(msg)
        else:
            st.markdown("#### 📅 1. SELECT COMMON CONSUMPTION DATE")
            c_date_col1, _ = st.columns([2, 6])
            common_cons_date = c_date_col1.date_input("CONSUMPTION DATE (Sabhi reels ke liye common)", datetime.today(), key="common_cons_date_input_perfect_key")

            st.write("---")
            st.markdown("#### 🧻 2. ADD MULTIPLE REELS CONSUMPTION DATA")
            st.info("💡 Aap **Bhaavya Reel No** ya **Mill Reel No** dono mein se koi bhi yahan type kar sakte hain!")
            if "cons_grid_count" not in st.session_state: st.session_state.cons_grid_count = 4

            def inc_cons_rows(): st.session_state.cons_grid_count += 1
            def dec_cons_rows(): 
                if st.session_state.cons_grid_count > 1: st.session_state.cons_grid_count -= 1

            hc0, hc1, hc2, hc3, hc4, hc5, hc6, hc7 = st.columns([0.4, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8, 2.0])
            hc0.markdown("**#**")
            hc1.markdown("**Reel No (Type)**")
            hc2.markdown("**Bhaavya Reel**")
            hc3.markdown("**Mill Reel**")
            hc4.markdown("**Rem Wt (KG)**")
            hc5.markdown("**Machine**")
            hc6.markdown("**Current Bal**")
            hc7.markdown("**Consumed Wt**")

            cons_rows_data = []
            for i in range(st.session_state.cons_grid_count):
                rc0, rc1, rc2, rc3, rc4, rc5, rc6, rc7 = st.columns([0.4, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8, 2.0])
                rc0.markdown(f"<p style='margin-top:10px; font-weight:bold; color:#1f77b4;'>#{i+1}</p>", unsafe_allow_html=True)
                
                input_reel_val = rc1.text_input("Reel No", value="", key=f"c_reel_{i}", label_visibility="collapsed")
                
                curr_bal_val = 0.0
                valid_reel_flag = False
                calculated_consumed = 0.0
                resolved_bhaavya_reel = ""
                resolved_mill_reel = "-"
                
                if input_reel_val.strip():
                    search_key = input_reel_val.strip().upper()
                    r_check = get_data("SELECT company_reel, mill_reel, weight FROM receiving WHERE company_reel = ? OR mill_reel = ?", (search_key, search_key))
                    if not r_check.empty:
                        resolved_bhaavya_reel = str(r_check['company_reel'].values[0])
                        resolved_mill_reel = str(r_check['mill_reel'].values[0]) if r_check['mill_reel'].values[0] else "-"
                        orig_w = float(r_check['weight'].values[0])
                        
                        p_check = get_data("SELECT SUM(weight_consumed) as tot FROM consumption WHERE company_reel = ?", (resolved_bhaavya_reel,))
                        tot_c = float(p_check['tot'].values[0]) if not p_check.empty and p_check['tot'].values[0] is not None else 0.0
                        curr_bal_val = orig_w - tot_c
                        
                        if curr_bal_val > 0:
                            valid_reel_flag = True

                rc2.markdown(f"<p style='margin-top:10px; font-weight:bold; color:#1f77b4;'>{resolved_bhaavya_reel if resolved_bhaavya_reel else '-'}</p>", unsafe_allow_html=True)
                rc3.markdown(f"<p style='margin-top:10px; font-weight:bold; color:#555;'>{resolved_mill_reel}</p>", unsafe_allow_html=True)
                
                rem_wt_str = rc4.text_input("Rem Wt", value="", key=f"c_rem_{i}", label_visibility="collapsed")
                mach_name = rc5.selectbox("Machine", ["B FLUTE", "C FLUTE", "5 PLY LINE", "OTHER"], key=f"c_mach_{i}", label_visibility="collapsed")

                rc6.markdown(f"<p style='margin-top:10px; font-weight:bold; color:#333;'>{curr_bal_val:,.1f} kg</p>" if valid_reel_flag else "<p style='margin-top:10px; color:gray;'>-</p>", unsafe_allow_html=True)

                if valid_reel_flag and rem_wt_str.strip():
                    try:
                        rem_val = float(rem_wt_str)
                        calculated_consumed = curr_bal_val - rem_val
                    except:
                        calculated_consumed = 0.0

                if calculated_consumed > 0:
                    rc7.markdown(f"<p style='margin-top:10px; font-weight:bold; color:green;'>{calculated_consumed:,.1f} kg</p>", unsafe_allow_html=True)
                else:
                    rc7.markdown(f"<p style='margin-top:10px; color:gray;'>-</p>", unsafe_allow_html=True)
                
                cons_rows_data.append({
                    "reel_no": resolved_bhaavya_reel,
                    "rem_wt": rem_wt_str,
                    "machine": mach_name,
                    "curr_bal": curr_bal_val,
                    "is_valid": valid_reel_flag
                })

            c_btn1, c_btn2, _ = st.columns([2, 2, 6])
            c_btn1.button("➕ Add Another Row", on_click=inc_cons_rows)
            c_btn2.button("❌ Remove Last Row", on_click=dec_cons_rows)

            st.write("---")
            if st.button("💾 SAVE ALL CONSUMPTION ENTRIES"):
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                success_all = True
                saved_c_count = 0
                
                try:
                    cursor.execute("BEGIN TRANSACTION;")
                    for idx, row in enumerate(cons_rows_data):
                        r_no = row["reel_no"].strip().upper()
                        if not r_no and not row["rem_wt"].strip():
                            continue
                        
                        if not r_no or not row["rem_wt"].strip():
                            st.error(f"❌ Row #{idx+1}: Valid Reel No aur Remaining Weight dono bharna zaroori hai!")
                            success_all = False
                            break
                        
                        try:
                            rem_w_val = float(row["rem_wt"])
                        except:
                            st.error(f"❌ Row #{idx+1}: Remaining weight valid number hona chahiye!")
                            success_all = False
                            break
                        
                        if not row["is_valid"]:
                            st.error(f"❌ Row #{idx+1}: Di gayi reel invalid hai ya stock mein nahi hai!")
                            success_all = False
                            break
                        
                        if rem_w_val >= row["curr_bal"]:
                            st.error(f"❌ Row #{idx+1}: Reel `{r_no}` ka remaining weight ({rem_w_val}kg) current balance ({row['curr_bal']}kg) se kam hona chahiye!")
                            success_all = False
                            break
                        
                        actual_consumed = row["curr_bal"] - rem_w_val
                        final_mach = row["machine"]
                        if rem_w_val <= 200.0:
                            final_mach = f"{final_mach} - BABY REEL"
                            
                        cursor.execute('''
                            INSERT INTO consumption (date, company_reel, weight_consumed, machine, entered_by)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (str(common_cons_date), r_no, float(actual_consumed), final_mach, st.session_state.logged_user))
                        saved_c_count += 1
                        
                    if success_all and saved_c_count > 0:
                        conn.commit()
                        st.success(f"🎉 Success! Sabhi {saved_c_count} Consumption entries successfully save ho gayi hain.")
                        st.session_state.cons_grid_count = 4
                        st.cache_data.clear()
                        st.rerun()
                    elif saved_c_count == 0:
                        st.warning("⚠️ Kam se kam ek valid row bharna zaroori hai!")
                    else:
                        conn.rollback()
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Database Error: {e}")
                finally:
                    conn.close()

# TAB 3.5: ADVANCED L, W, H DECKLE & SHEET CALCULATOR (100% LIVE REACTIVE STATE SYNC)
if tab_calc:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📐 ADVANCED L, W, H DECKLE & SHEET CALCULATOR</h2>", unsafe_allow_html=True)
    st.info("💡 Box ki Length, Width, Height, Box Type, aur Ply Selection ke adhaar par dynamic layers aur per-layer paper requirement calculate karein.")

    st.markdown("#### 📦 1. BOX SPECIFICATIONS & PLY SELECTION")
    
    c_p1, c_p2 = st.columns(2)
    box_type = c_p1.selectbox("BOX TYPE", ["One Piece Box", "Two Piece Box"], key="calc_box_type")
    ply_selection = c_p2.selectbox("SELECT PLY", ["3 Ply", "5 Ply", "7 Ply"], key="calc_ply_sel")
    
    l_col1, l_col2, l_col3 = st.columns(3)
    box_l = l_col1.number_input("LENGTH (mm) - L", min_value=0.0, value=300.0, step=1.0, key="calc_box_l")
    box_w = l_col2.number_input("WIDTH (mm) - W", min_value=1.0, value=444.0, step=1.0, key="calc_box_w")
    box_h = l_col3.number_input("HEIGHT (mm) - H", min_value=0.0, value=278.0, step=1.0, key="calc_box_h")

    l_col4, l_col5, l_col6, l_col7 = st.columns(4)
    box_qty = l_col4.number_input("QUANTITY (Nos)", min_value=1, value=1, step=1, key="calc_box_qty")
    ups_count = l_col5.number_input("UPS COUNT (1 or 2)", min_value=1, max_value=4, value=1, step=1, key="calc_ups_count")
    master_dl = l_col6.number_input("MASTER DECKLE (DL - mm)", min_value=100.0, value=1735.0, step=10.0, key="calc_master_dl")
    linear_mtr = l_col7.number_input("LINEAR MTR", min_value=0.0, value=3.515, step=0.001, key="calc_linear_mtr")

    st.markdown(f"#### 📄 2. CORRUGATED LAYERS SPECIFICATIONS ({ply_selection})")
    
    if ply_selection == "3 Ply":
        layers_def = [
            ("1 = Top", 250, 24, "Liner", 1.0),
            ("2 = B Flute", 150, 20, "Flute", 1.35),
            ("3 = B F Liner", 150, 24, "Liner", 1.0)
        ]
    elif ply_selection == "5 Ply":
        layers_def = [
            ("1 = Top", 250, 24, "Liner", 1.0),
            ("2 = B Flute", 150, 20, "Flute", 1.35),
            ("3 = B F Liner", 150, 24, "Liner", 1.0),
            ("4 = C Flute", 150, 20, "Flute", 1.45),
            ("5 = C F Liner", 250, 24, "Liner", 1.0)
        ]
    else: # 7 Ply
        layers_def = [
            ("1 = Top", 250, 24, "Liner", 1.0),
            ("2 = B Flute", 150, 20, "Flute", 1.35),
            ("3 = B F Liner", 150, 24, "Liner", 1.0),
            ("4 = C Flute", 150, 20, "Flute", 1.45),
            ("5 = C F Liner", 250, 24, "Liner", 1.0),
            ("6 = A Flute", 150, 20, "Flute", 1.55),
            ("7 = A F Liner", 250, 24, "Liner", 1.0)
        ]

    layer_inputs = []
    for idx, (l_name, def_g, def_b, l_type, def_fact) in enumerate(layers_def):
        st.markdown(f"**{l_name}**")
        lc1, lc2, lc3, lc4, lc5 = st.columns([2, 2, 2, 2, 2.5])
        
        g_key = f"g_{ply_selection}_{idx}"
        b_key = f"b_{ply_selection}_{idx}"
        
        if g_key not in st.session_state: st.session_state[g_key] = def_g
        if b_key not in st.session_state: st.session_state[b_key] = def_b
        
        g_val = lc1.number_input("GSM", min_value=1, max_value=1000, step=5, key=g_key)
        b_val = lc2.number_input("BF", min_value=1, max_value=100, step=1, key=b_key)
        
        auto_rct = round((b_val * g_val) / 3000.0 * 0.1, 2)
        raw_bs = (g_val * b_val) / 1000.0
        auto_bs = round(raw_bs / 2.0 if l_type == "Flute" else raw_bs, 2)

        r_val = lc3.number_input("RCT", value=auto_rct, key=f"rct_{ply_selection}_{idx}", disabled=True)
        s_val = lc4.number_input("BS", value=auto_bs, key=f"bs_{ply_selection}_{idx}", disabled=True)
        
        fact_val = def_fact
        if l_type == "Flute":
            fact_val = lc5.selectbox("Flute Factor", [1.35, 1.45, 1.55], index=0 if def_fact==1.35 else (1 if def_fact==1.45 else 2), key=f"fact_{ply_selection}_{idx}")
        else:
            lc5.markdown("<p style='margin-top:28px; color:gray; font-size:12px;'>Factor: 1.0 (Liner)</p>", unsafe_allow_html=True)

        layer_inputs.append({"name": l_name, "gsm": g_val, "bf": b_val, "rct": auto_rct, "bs": auto_bs, "factor": fact_val, "l_type": l_type})

    st.write("---")
    stitch_flap = 35.0 if box_type == "One Piece Box" else 55.0
    trim_margin = 20.0
    
    calc_cut_length = 2.0 * (box_l + box_w) + stitch_flap + trim_margin
    
    base_w_h = box_w + box_h + 10.0 + 6.0
    if ups_count == 1:
        calc_deckle = base_w_h + 18.0
    else:
        calc_deckle = base_w_h * ups_count + 18.0
    
    area = (calc_cut_length * calc_deckle * box_qty) / 1_000_000.0
    
    total_req_paper = 0.0
    total_bs = 0.0
    table_data = []
    sum_equivalent_gsm = 0.0
    
    for item in layer_inputs:
        effective_gsm = item["gsm"] * item["factor"]
        sum_equivalent_gsm += effective_gsm
        
        req_p = (item["gsm"] * item["factor"] * linear_mtr) / 1000.0
        total_req_paper += req_p
        
        layer_bs = item["bs"]
        total_bs += layer_bs
        
        table_data.append({
            "Layer": item["name"], 
            "GSM": item["gsm"], 
            "BF": item["bf"], 
            "RCT": item["rct"], 
            "BS": f"{layer_bs:,.2f}", 
            "Factor": item["factor"],
            "Per Layer Paper Required (Kg)": f"{req_p:,.3f}"
        })

    sheet_wt = sum_equivalent_gsm * (calc_deckle / 1000.0) * (linear_mtr / 1000.0)

    st.markdown("### 📊 REAL-TIME CALCULATION OUTPUT SUMMARY")
    r_c1, r_c2, r_c3, r_c4, r_c5 = st.columns(5)
    r_c1.metric("✂️ Cut Length (mm)", f"{calc_cut_length:,.1f}")
    r_c2.metric("🎯 Calculated Deckle (mm)", f"{calc_deckle:,.1f}")
    r_c3.metric("📦 Area (Sq.Mtr)", f"{area:,.3f}")
    r_c4.metric("⚖️ Sheet Wt (Kg)", f"{sheet_wt:,.3f}")
    r_c5.metric("💪 Total BS", f"{total_bs:,.2f}")

    df_rec_summary = pd.DataFrame(table_data)
    st.dataframe(df_rec_summary, use_container_width=True)

# TAB 4: PHYSICAL STOCK ADJUSTMENT
if tab_adj:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🛠️ PHYSICAL STOCK AUDIT & ADJUSTMENT</h2>", unsafe_allow_html=True)
    adj_reel_no = st.text_input("ENTER REEL NO (Bhaavya or Mill Reel) TO ADJUST *", key="adj_reel_search_key")
    if adj_reel_no:
        search_adj_key = adj_reel_no.strip().upper()
        check_rec = get_data("SELECT company_reel, weight, mill, gsm, bf, deckle, shade FROM receiving WHERE company_reel = ? OR mill_reel = ?", (search_adj_key, search_adj_key))
        if check_rec.empty: st.error("❌ REEL NO NOT FOUND!")
        else:
            bh_adj_reel = check_rec['company_reel'].values[0]
            orig_wt = float(check_rec['weight'].values[0])
            mill_n = check_rec['mill'].values[0]
            gsm_n = check_rec['gsm'].values[0]
            bf_n = check_rec['bf'].values[0]
            deckle_n = check_rec['deckle'].values[0]
            shade_n = check_rec['shade'].values[0]
            
            check_past = get_data("SELECT SUM(weight_consumed) as total_c FROM consumption WHERE company_reel = ?", (bh_adj_reel,))
            total_c = float(check_past['total_c'].values[0]) if not check_past['total_c'].empty and check_past['total_c'].values[0] is not None else 0.0
            curr_bal = orig_wt - total_c
            
            st.markdown(f"### 📋 CURRENT DETAILS FOR REEL: `{bh_adj_reel}`")
            st.success(f"🏭 Mill: **{mill_n}** | Deckle: **{deckle_n} MM** | GSM: **{gsm_n}** | BF: **{bf_n}** | Shade: **{shade_n}**")
            st.info(f"🏋️‍♂️ Original Weight: **{orig_wt} KG** | Total Consumed: **{total_c} KG** | 🔵 **CURRENT BALANCE:** **{curr_bal} KG**")
            
            with st.form("stock_adjustment_form", clear_on_submit=True):
                col_a1, col_a2 = st.columns(2)
                adj_date = col_a1.date_input("ADJUSTMENT DATE", datetime.today())
                adj_type = col_a2.selectbox("ADJUSTMENT TYPE", ["SET EXACT PHYSICAL WEIGHT (Pura Stock Update)", "ADD WEIGHT (+ Plus)", "SUBTRACT WEIGHT (- Minus)"])
                adj_value_str = col_a1.text_input("ENTER WEIGHT (KG) *", value="")
                adj_remarks = col_a2.text_input("AUDIT / ADJUSTMENT REMARKS", value="Physical Stock Audit Correction")
                
                if st.form_submit_button("💾 CONFIRM & UPDATE PHYSICAL STOCK"):
                    try:
                        adj_val = float(adj_value_str) if adj_value_str else 0.0
                        if adj_val < 0: st.error("❌ Kripya positive number enter karein!")
                        else:
                            audit_remark_text = f"[{st.session_state.logged_user}] {adj_remarks.strip().upper()}"
                            if "SET EXACT PHYSICAL WEIGHT" in adj_type:
                                diff = curr_bal - adj_val
                                if diff > 0:
                                    run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine, entered_by) VALUES (?, ?, ?, ?, ?)", (str(adj_date), bh_adj_reel, diff, f"AUDIT SUB [{diff}KG]: {audit_remark_text}", st.session_state.logged_user))
                                elif diff < 0:
                                    new_orig = orig_wt + abs(diff)
                                    run_query("UPDATE receiving SET weight = ? WHERE company_reel = ?", (new_orig, bh_adj_reel))
                                    run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine, entered_by) VALUES (?, ?, ?, ?, ?)", (str(adj_date), bh_adj_reel, 0.0, f"AUDIT ADD [{abs(diff)}KG]: {audit_remark_text}", st.session_state.logged_user))
                            elif "ADD WEIGHT" in adj_type:
                                new_orig = orig_wt + adj_val
                                run_query("UPDATE receiving SET weight = ? WHERE company_reel = ?", (new_orig, bh_adj_reel))
                                run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine, entered_by) VALUES (?, ?, ?, ?, ?)", (str(adj_date), bh_adj_reel, 0.0, f"AUDIT ADD [{adj_val}KG]: {audit_remark_text}", st.session_state.logged_user))
                            elif "SUBTRACT WEIGHT" in adj_type:
                                run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine, entered_by) VALUES (?, ?, ?, ?, ?)", (str(adj_date), bh_adj_reel, adj_val, f"AUDIT SUB [{adj_val}KG]: {audit_remark_text}", st.session_state.logged_user))
                            st.success(f"🎉 Physical Stock Updated Successfully!")
                            st.rerun()
                    except Exception as e: st.error(f"❌ Adjustment failed: {e}")

# TAB 5: MSL & LOW STOCK ALERTS WITH EXCEL IMPORT, FULL DATA DOWNLOAD & SORTING BY SHORTAGE AMOUNT
if tab_msl:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🚨 DYNAMIC INVENTORY DAYS, MSL & LINKED PO SCHEDULE</h2>", unsafe_allow_html=True)
    st.info("💡 **PO Tracking:** Pending PO schedule ka total yahan dikhega aur mouse cursor lekar jane par poori detail (PO No, Mill, Pending Qty) dikh jayegi.")

    run_query("""
        INSERT OR IGNORE INTO paper_master (gsm, bf, deckle, shade, per_day_consumption, reorder_qty)
        SELECT DISTINCT gsm, bf, deckle, UPPER(shade), 0.0, 0.0 
        FROM receiving 
        WHERE gsm > 0 AND bf > 0 AND deckle > 0
    """)

    with st.expander("📤 BULK UPLOAD / UPDATE PER DAY CONSUMPTION VIA EXCEL"):
        st.markdown("Aap Excel file upload karke sabhi items ka **Per Day Consumption** ek sath update kar sakte hain.")
        
        df_full_msl = get_data("SELECT gsm as [GSM], bf as [BF], deckle as [Deckle], shade as [Shade], per_day_consumption as [Per_Day] FROM paper_master")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if not df_full_msl.empty:
                df_full_msl.to_excel(writer, index=False, sheet_name='MSL_Data')
            else:
                pd.DataFrame(columns=['GSM', 'BF', 'Deckle', 'Shade', 'Per_Day']).to_excel(writer, index=False, sheet_name='MSL_Data')
        excel_full_bytes = output.getvalue()

        st.download_button(
            label="📥 DOWNLOAD ALL CURRENT MSL SPECIFICATIONS (EXCEL)",
            data=excel_full_bytes,
            file_name=f"MSL_Full_Data_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.write("---")
        msl_uploaded_file = st.file_uploader("Upload MSL Excel File (.xlsx)", type=["xlsx"], key="msl_excel_up")
        if msl_uploaded_file is not None and st.button("🚀 IMPORT PER DAY DATA"):
            try:
                df_msl_imp = pd.read_excel(msl_uploaded_file)
                df_msl_imp.columns = [str(c).strip().replace(" ", "_") for c in df_msl_imp.columns]
                
                required_msl_cols = ['GSM', 'BF', 'Deckle', 'Shade']
                has_per_day = 'Per_Day' in df_msl_imp.columns or 'PerDay' in df_msl_imp.columns
                
                if all(col in df_msl_imp.columns for col in required_msl_cols) and has_per_day:
                    per_day_col = 'Per_Day' if 'Per_Day' in df_msl_imp.columns else 'PerDay'
                    
                    conn_m = sqlite3.connect(db_file)
                    cur_m = conn_m.cursor()
                    count_imp = 0
                    for _, mrow in df_msl_imp.iterrows():
                        g_imp = int(mrow['GSM'])
                        b_imp = int(mrow['BF'])
                        d_imp = int(mrow['Deckle'])
                        s_imp = str(mrow['Shade']).strip().upper()
                        p_imp = float(mrow[per_day_col])
                        
                        cur_m.execute("""
                            INSERT INTO paper_master (gsm, bf, deckle, shade, per_day_consumption, reorder_qty)
                            VALUES (?, ?, ?, ?, ?, 0.0)
                            ON CONFLICT(gsm, bf, deckle, shade) DO UPDATE SET per_day_consumption = ?
                        """, (g_imp, b_imp, d_imp, s_imp, p_imp, p_imp))
                        count_imp += 1
                    conn_m.commit()
                    conn_m.close()
                    st.success(f"🎉 Success! {count_imp} items ka Per Day Consumption update ho gaya hai.")
                    st.rerun()
                else:
                    st.error("❌ Excel file mein required columns nahi mile. Kripya check karein: GSM, BF, Deckle, Shade, Per_Day (ya Per Day)")
            except Exception as e:
                st.error(f"❌ Import Error: {str(e)}")

    inventory_days = st.slider("📅 SELECT TARGET INVENTORY DAYS (MSL Multiplier)", min_value=1, max_value=30, value=10, key="msl_inv_slider")

    query_row_view = f"""
        SELECT 
            p.gsm as [GSM], 
            p.bf as [BF], 
            p.deckle as [DECKLE], 
            UPPER(p.shade) as [SHADE],
            COALESCE(p.per_day_consumption, 0.0) as [PER_DAY],
            COALESCE(SUM(r.weight - COALESCE(c.weight_consumed, 0)), 0.0) as [CURRENT_STOCK]
        FROM paper_master p
        LEFT JOIN receiving r ON p.gsm = r.gsm AND p.bf = r.bf AND p.deckle = r.deckle AND UPPER(p.shade) = UPPER(r.shade)
        LEFT JOIN (
            SELECT company_reel, SUM(weight_consumed) as weight_consumed 
            FROM consumption GROUP BY company_reel
        ) c ON r.company_reel = c.company_reel
        GROUP BY p.gsm, p.bf, p.deckle, UPPER(p.shade)
        ORDER BY 
            CASE 
                WHEN COALESCE(SUM(r.weight - COALESCE(c.weight_consumed, 0)), 0.0) < (COALESCE(p.per_day_consumption, 0.0) * {inventory_days}) THEN 1
                WHEN COALESCE(SUM(r.weight - COALESCE(c.weight_consumed, 0)), 0.0) > (COALESCE(p.per_day_consumption, 0.0) * {inventory_days} * 1.5) THEN 3
                ELSE 2 
            END ASC,
            ((COALESCE(p.per_day_consumption, 0.0) * {inventory_days}) - COALESCE(SUM(r.weight - COALESCE(c.weight_consumed, 0)), 0.0)) DESC,
            p.gsm DESC, p.bf DESC
    """
    df_rows = get_data(query_row_view)

    if not df_rows.empty:
        st.write("---")
        st.markdown("### 🎛️ FILTER SPECIFICATIONS")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        sel_gsm_f = f_col1.multiselect("FILTER GSM", sorted(df_rows['GSM'].unique()))
        sel_bf_f = f_col2.multiselect("FILTER BF", sorted(df_rows['BF'].unique()))
        sel_dec_f = f_col3.multiselect("FILTER DECKLE", sorted(df_rows['DECKLE'].unique()))
        sel_shd_f = f_col4.multiselect("FILTER SHADE", sorted(df_rows['SHADE'].unique()))

        df_filtered_rows = df_rows.copy()
        if sel_gsm_f: df_filtered_rows = df_filtered_rows[df_filtered_rows['GSM'].isin(sel_gsm_f)]
        if sel_bf_f: df_filtered_rows = df_filtered_rows[df_filtered_rows['BF'].isin(sel_bf_f)]
        if sel_dec_f: df_filtered_rows = df_filtered_rows[df_filtered_rows['DECKLE'].isin(sel_dec_f)]
        if sel_shd_f: df_filtered_rows = df_filtered_rows[df_filtered_rows['SHADE'].isin(sel_shd_f)]

        st.write("---")
        h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11 = st.columns([0.5, 0.5, 0.7, 0.8, 0.9, 0.8, 0.8, 1.5, 1.0, 1.0, 0.7])
        h1.markdown("**GSM**"); h2.markdown("**BF**"); h3.markdown("**DECKLE**"); h4.markdown("**SHADE**")
        h5.markdown("**PER DAY**"); h6.markdown("**MSL**"); h7.markdown("**REORDER**")
        h8.markdown("**PENDING PO SCHEDULE**"); h9.markdown("**STATUS**"); h10.markdown("**STOCK DIFF / VALUE**"); h11.markdown("**ACTION**")

        for idx, row in df_filtered_rows.iterrows():
            g = int(row['GSM']); b = int(row['BF']); d = int(row['DECKLE']); s = str(row['SHADE']).strip().upper()
            curr_p_day = float(row['PER_DAY']); curr_stk = float(row['CURRENT_STOCK'])
            dyn_msl = curr_p_day * inventory_days
            reorder_qty = max(0.0, dyn_msl - curr_stk)

            df_po_check = get_data("""
                SELECT po.po_no, po.mill, (po.ordered_qty - COALESCE((SELECT SUM(weight) FROM receiving WHERE po_id = po.id), 0)) as pend 
                FROM purchase_orders po 
                WHERE po.gsm = ? AND po.bf = ? AND po.deckle = ? AND UPPER(po.shade) = ? AND po.status = 'PENDING'
            """, (g, b, d, s))
            
            if not df_po_check.empty:
                total_pend_for_row = 0.0
                tooltip_lines = []
                for _, porow in df_po_check.iterrows():
                    pend_val = float(porow['pend'])
                    if pend_val > 0:
                        total_pend_for_row += pend_val
                        tooltip_lines.append(f"PO: {porow['po_no']} | Mill: {porow['mill']} | Pending: {pend_val:,.0f} kg")
                
                if total_pend_for_row > 0:
                    tooltip_text = "&#10;".join(tooltip_lines)
                    display_title = f"Total: {total_pend_for_row:,.0f} kg"
                    sched_text = f"<span title='{tooltip_text}' style='color:#d9534f; font-weight:bold; cursor:pointer; text-decoration: underline dotted;'>{display_title}</span>"
                else:
                    sched_text = "<span style='color:gray;'>No Pending PO</span>"
            else:
                sched_text = "<span style='color:gray;'>No Pending PO</span>"

            if curr_stk < dyn_msl:
                status_text = "🔴 SHORTAGE"
                val_text = f"{curr_stk:,.1f}"
            elif curr_stk > (dyn_msl * 1.5):
                status_text = "🔵 EXCESS"
                val_text = f"{curr_stk:,.1f}"
            else:
                status_text = "🟢 SUFFICIENT"
                val_text = f"{curr_stk:,.1f}"

            with st.container():
                st.markdown('<div class="custom-row">', unsafe_allow_html=True)
                c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11 = st.columns([0.5, 0.5, 0.7, 0.8, 0.9, 0.8, 0.8, 1.5, 1.0, 1.0, 0.7])
                c1.text(str(g)); c2.text(str(b)); c3.text(str(d)); c4.text(str(s))

                input_key = f"row_pday_{g}_{b}_{d}_{s}_{idx}"
                btn_key = f"row_btn_{g}_{b}_{d}_{s}_{idx}"

                new_p_day_str = c5.text_input("Per Day", value=f"{curr_p_day:.2f}", key=input_key, label_visibility="collapsed")
                c6.text(f"{dyn_msl:,.1f}"); c7.text(f"{reorder_qty:,.1f}")
                c8.markdown(f"<div style='font-size:11px; line-height:1.3;'>{sched_text}</div>", unsafe_allow_html=True)
                c9.markdown(status_text); c10.text(val_text)

                if c11.button("💾", key=btn_key):
                    try:
                        p_val = float(new_p_day_str) if new_p_day_str else 0.0
                        r_val = max(0.0, (p_val * inventory_days) - curr_stk)
                        
                        run_query("""
                            INSERT INTO paper_master (gsm, bf, deckle, shade, per_day_consumption, reorder_qty)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(gsm, bf, deckle, shade) DO UPDATE SET per_day_consumption = ?, reorder_qty = ?
                        """, (g, b, d, s, p_val, r_val, p_val, r_val))
                        
                        st.success(f"✅ Saved GSM {g}, BF {b}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("ℹ️ No paper specifications found yet.")

# TAB 6: EXCEL IMPORT
if tab_import:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📤 BULK STOCK FILE IMPORT (EXCEL)</h2>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])
    if uploaded_file is not None and st.button("🚀 START BULK IMPORT NOW"):
        success, message = import_excel_stock(uploaded_file)
        if success: st.success(message)
        else: st.error(message)

# TAB 7: CONSUMPTION & SUPPLIER RATE HISTORY REPORTS
if tab_rep:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📈 CONSUMPTION & SUPPLIER RATE HISTORY REPORTS</h2>", unsafe_allow_html=True)
    
    rep_sub1, rep_sub2 = st.tabs(["📉 MILL-WISE CONSUMPTION", "💰 SUPPLIER & RATE HISTORY"])
    
    with rep_sub1:
        query_consumption_report = """
        SELECT COALESCE(UPPER(r.mill), 'UNKNOWN/DIRECT ENTRY') as [MILL NAME], COUNT(c.company_reel) as [TOTAL CONSUMPTION ENTRIES], SUM(c.weight_consumed) as [TOTAL WEIGHT CONSUMED (KG)]
        FROM consumption c LEFT JOIN receiving r ON c.company_reel = r.company_reel GROUP BY CLEAN_NAME(r.mill) ORDER BY [TOTAL WEIGHT CONSUMED (KG)] DESC
        """
        try:
            df_cons_report = get_data(query_consumption_report)
            if not df_cons_report.empty:
                st.metric(label="📉 GRAND TOTAL CONSUMED WEIGHT", value=f"{df_cons_report['TOTAL WEIGHT CONSUMED (KG)'].sum():,.2f} KG")
                st.dataframe(df_cons_report, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

    with rep_sub2:
        st.markdown("### 💰 SUPPLIER & RATE HISTORY (PAST PURCHASES)")
        query_rate_hist = """
        SELECT 
            date as [DATE], mill as [MILL], supplier as [SUPPLIER], company_reel as [BHAAVYA REEL],
            gsm as [GSM], bf as [BF], deckle as [DECKLE], rate as [RATE / KG], trans_charges as [TRANS CHARGES], grn_no as [GRN NO]
        FROM receiving ORDER BY date DESC
        """
        df_rate_hist = get_data(query_rate_hist)
        if not df_rate_hist.empty:
            st.dataframe(df_rate_hist, use_container_width=True)
        else:
            st.info("ℹ️ No rate history available yet.")

# TAB 8: HISTORY LOGS
if tab_hist:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>📋 COMPLETE SYSTEM HISTORY & AUDIT LOGS</h2>", unsafe_allow_html=True)
    
    can_edit_rec = check_user_permission(st.session_state.logged_user, 'can_edit_receiving')
    can_edit_cons = check_user_permission(st.session_state.logged_user, 'can_edit_consumption')
    
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["🛠️ PHYSICAL STOCK AUDIT LOGS", "📥 RECEIVING HISTORY", "📉 CONSUMPTION HISTORY"])
    
    with sub_tab1:
        st.markdown("### 🛠️ DATE-WISE PHYSICAL STOCK AUDIT LOGS")
        st.pills("⚡ QUICK DATES:", ["📅 TODAY", "📅 YESTERDAY", "📅 THIS MONTH", "📅 LAST 3 MONTH", "📅 CURRENT FINANCIAL YEAR"], key="audit_shortcut_pill", on_change=handle_audit_shortcut)
        audit_d1, audit_d2 = st.columns(2)
        st.session_state.a_start = audit_d1.date_input("AUDIT FROM DATE", value=st.session_state.a_start, key=f"a_start_input_v_{st.session_state.audit_version}")
        st.session_state.a_end = audit_d2.date_input("AUDIT TO DATE", value=st.session_state.a_end, key=f"a_end_input_v_{st.session_state.audit_version}")
        
        query_audit_raw = """
            SELECT c.date as [ADJUSTMENT DATE], c.company_reel as [BHAAVYA REEL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE (MM)], c.weight_consumed as [RAW_WEIGHT], c.machine as [FULL AUDIT REMARKS], c.entered_by as [UPDATED BY]
            FROM consumption c LEFT JOIN receiving r ON c.company_reel = r.company_reel
            WHERE c.machine LIKE 'AUDIT%' AND strftime('%Y-%m-%d', c.date) BETWEEN ? AND ?
            ORDER BY c.date DESC
        """
        df_audit_raw = get_data(query_audit_raw, (str(st.session_state.a_start), str(st.session_state.a_end)))
        if not df_audit_raw.empty:
            def parse_audit_type(remarks):
                if "ADD" in str(remarks).upper(): return "➕ ADD (+)"
                elif "SUB" in str(remarks).upper(): return "➖ SUBTRACT (-)"
                return "🛠️ ADJUSTMENT"
            def parse_weight_change(row):
                remarks = str(row['FULL AUDIT REMARKS'])
                raw_wt = row['RAW_WEIGHT']
                if "ADD" in remarks.upper():
                    if "[" in remarks and "KG]" in remarks: return f"+{remarks.split('[')[1].split('KG]')[0]} KG"
                    return f"+{raw_wt} KG"
                else:
                    if raw_wt > 0: return f"-{raw_wt} KG"
                    elif "[" in remarks and "KG]" in remarks: return f"-{remarks.split('[')[1].split('KG]')[0]} KG"
                    return f"-{raw_wt} KG"
            df_audit_raw['ADJUSTMENT TYPE'] = df_audit_raw['FULL AUDIT REMARKS'].apply(parse_audit_type)
            df_audit_raw['WEIGHT CHANGE'] = df_audit_raw.apply(parse_weight_change, axis=1)
            st.dataframe(df_audit_raw[['ADJUSTMENT DATE', 'BHAAVYA REEL NO', 'MILL', 'GSM', 'BF', 'DECKLE (MM)', 'ADJUSTMENT TYPE', 'WEIGHT CHANGE', 'UPDATED BY', 'FULL AUDIT REMARKS']], use_container_width=True)
        else: st.info("ℹ️ Is date range ke andar koi Physical Stock Adjustment nahi mila.")

    with sub_tab2:
        st.markdown("### 📥 RECEIVING / GRN HISTORY RECORDS")
        st.pills("⚡ QUICK DATES:", ["📅 TODAY", "📅 YESTERDAY", "📅 THIS MONTH", "📅 LAST 3 MONTH", "📅 CURRENT FINANCIAL YEAR"], key="rec_shortcut_pill", on_change=handle_rec_shortcut)
        rec_d1, rec_d2 = st.columns(2)
        st.session_state.r_start = rec_d1.date_input("RECEIPT FROM DATE", value=st.session_state.r_start, key=f"r_start_input_v_{st.session_state.rec_version}")
        st.session_state.r_end = rec_d2.date_input("RECEIPT TO DATE", value=st.session_state.r_end, key=f"r_end_input_v_{st.session_state.rec_version}")
        
        df_rec_hist = get_data("SELECT r.company_reel as [BHAAVYA REEL NO], r.mill_reel as [MILL REEL NO], r.date as [DATE], r.grn_no as [GRN NO], r.bill_no as [CUSTOMER BILL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE], r.weight as [WEIGHT], r.rate as [RATE/KG], r.trans_charges as [TRANS CHARGES], r.entered_by as [ENTERED BY] FROM receiving r WHERE strftime('%Y-%m-%d', r.date) BETWEEN ? AND ?", (str(st.session_state.r_start), str(st.session_state.r_end)))
        
        if not df_rec_hist.empty:
            st.markdown("#### 🎛️ Filter Receiving History")
            rh_c1, rh_c2, rh_c3, rh_c4 = st.columns(4)
            
            unique_grn_list = sorted(list(df_rec_hist['GRN NO'].dropna().astype(str).unique()))
            sel_grn_filter = rh_c1.selectbox("Filter GRN No", ["-- ALL GRN --"] + unique_grn_list, key="rh_grn_filter")
            
            rh_gsm = rh_c2.multiselect("Filter GSM (History)", sorted(df_rec_hist['GSM'].unique()), key="rh_gsm")
            rh_bf = rh_c3.multiselect("Filter BF (History)", sorted(df_rec_hist['BF'].unique()), key="rh_bf")
            rh_dec = rh_c4.multiselect("Filter Deckle (History)", sorted(df_rec_hist['DECKLE'].unique()), key="rh_dec")
            
            if sel_grn_filter != "-- ALL GRN --":
                df_rec_hist = df_rec_hist[df_rec_hist['GRN NO'].astype(str) == str(sel_grn_filter)]
            if rh_gsm: df_rec_hist = df_rec_hist[df_rec_hist['GSM'].isin(rh_gsm)]
            if rh_bf: df_rec_hist = df_rec_hist[df_rec_hist['BF'].isin(rh_bf)]
            if rh_dec: df_rec_hist = df_rec_hist[df_rec_hist['DECKLE'].isin(rh_dec)]

            st.write("---")
            tot_rec_reels = len(df_rec_hist)
            tot_rec_weight = df_rec_hist['WEIGHT'].sum() if not df_rec_hist.empty else 0.0
            st.info(f"📦 **SELECTED DATE RANGE TOTAL SUMMARY** | Total Reels: **{tot_rec_reels} Nos** | Total Weight: **{tot_rec_weight:,.2f} KG**")

        st.write("---")
        st.dataframe(df_rec_hist, use_container_width=True)
        
        if can_edit_rec and not df_rec_hist.empty:
            st.markdown("#### 🗑️ Multiple Delete Receiving Entries")
            selected_reels_to_delete = st.multiselect(
                "Select Bhaavya Reel Nos to Delete Multiple Entries", 
                options=list(df_rec_hist['BHAAVYA REEL NO'].unique()),
                key="multi_delete_reels_sel"
            )
            
            if selected_reels_to_delete:
                st.warning(f"⚠️ Aapne **{len(selected_reels_to_delete)}** reels select ki hain delete karne ke liye.")
                if st.button("🚨 CONFIRM & DELETE SELECTED MULTIPLE REELS"):
                    conn_del = sqlite3.connect(db_file)
                    cur_del = conn_del.cursor()
                    try:
                        cur_del.execute("BEGIN TRANSACTION;")
                        for r_no in selected_reels_to_delete:
                            cur_del.execute("DELETE FROM receiving WHERE company_reel = ?", (r_no,))
                            cur_del.execute("DELETE FROM consumption WHERE company_reel = ?", (r_no,))
                        conn_del.commit()
                        conn_del.close()
                        st.success(f"🎉 Successfully deleted {len(selected_reels_to_delete)} reels!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        conn_del.rollback()
                        conn_del.close()
                        st.error(f"❌ Delete Error: {e}")

    with sub_tab3:
        st.markdown("### 📉 DAILY CONSUMPTION HISTORY RECORDS")
        st.pills("⚡ QUICK DATES:", ["📅 TODAY", "📅 YESTERDAY", "📅 THIS MONTH", "📅 LAST 3 MONTH", "📅 CURRENT FINANCIAL YEAR"], key="cons_shortcut_pill", on_change=handle_cons_shortcut)
        cons_d1, cons_d2 = st.columns(2)
        st.session_state.c_start = cons_d1.date_input("CONSUMPTION FROM DATE", value=st.session_state.c_start, key=f"c_start_input_v_{st.session_state.cons_version}")
        st.session_state.c_end = cons_d2.date_input("CONSUMPTION TO DATE", value=st.session_state.c_end, key=f"c_end_input_v_{st.session_state.cons_version}")
        
        query_fix_cons = """
            SELECT c.id as [ID], c.date as [DATE], c.company_reel as [BHAAVYA REEL NO], r.mill_reel as [MILL REEL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE], c.weight_consumed as [WEIGHT CONSUMED], c.machine as [MACHINE], c.entered_by as [ENTERED BY] 
            FROM consumption c LEFT JOIN receiving r ON c.company_reel = r.company_reel 
            WHERE strftime('%Y-%m-%d', c.date) BETWEEN ? AND ? AND c.machine NOT LIKE 'AUDIT%'
        """
        df_cons_hist = get_data(query_fix_cons, (str(st.session_state.c_start), str(st.session_state.c_end)))
        
        if not df_cons_hist.empty:
            st.markdown("#### 🎛️ Filter Consumption History")
            ch_c1, ch_c2, ch_c3 = st.columns(3)
            ch_gsm = ch_c1.multiselect("Filter GSM (Consumption)", sorted(df_cons_hist['GSM'].dropna().unique()), key="ch_gsm")
            ch_bf = ch_c2.multiselect("Filter BF (Consumption)", sorted(df_cons_hist['BF'].dropna().unique()), key="ch_bf")
            ch_dec = ch_c3.multiselect("Filter Deckle (Consumption)", sorted(df_cons_hist['DECKLE'].dropna().unique()), key="ch_dec")
            
            if ch_gsm: df_cons_hist = df_cons_hist[df_cons_hist['GSM'].isin(ch_gsm)]
            if ch_bf: df_cons_hist = df_cons_hist[df_cons_hist['BF'].isin(ch_bf)]
            if ch_dec: df_cons_hist = df_cons_hist[df_cons_hist['DECKLE'].isin(ch_dec)]

            st.write("---")
            tot_cons_entries = len(df_cons_hist)
            tot_cons_weight = df_cons_hist['WEIGHT CONSUMED'].sum() if not df_cons_hist.empty else 0.0
            st.info(f"📉 **SELECTED CONSUMPTION DATE RANGE TOTAL SUMMARY** | Total Entries: **{tot_cons_entries} Nos** | Total Consumed Weight: **{tot_cons_weight:,.2f} KG**")

        st.write("---")
        st.dataframe(df_cons_hist.drop(columns=['ID']), use_container_width=True)
        
        if can_edit_cons and not df_cons_hist.empty:
            st.markdown("#### ✏️ Edit or Delete Consumption Entry")
            df_cons_hist['DISPLAY_LABEL'] = df_cons_hist.apply(
                lambda row: f"ID: {row['ID']} | Reel: {row['BHAAVYA REEL NO']} | Date: {row['DATE']} | Consumed: {row['WEIGHT CONSUMED']} KG ({row['MACHINE']})", axis=1
            )
            label_to_id = dict(zip(df_cons_hist['DISPLAY_LABEL'], df_cons_hist['ID']))
            
            sel_label = st.selectbox("Select Consumption Entry to Edit/Delete", [""] + list(label_to_id.keys()), key="edit_cons_sel")
            
            if sel_label:
                sel_cons_id = label_to_id[sel_label]
                c_info = get_data("SELECT date, company_reel, weight_consumed, machine FROM consumption WHERE id = ?", (sel_cons_id,))
                if not c_info.empty:
                    with st.form("edit_consumption_form"):
                        st.write(f"**Selected Reel No:** `{c_info['company_reel'].values[0]}`")
                        ec_date = st.date_input("Date Consumed", value=datetime.strptime(c_info['date'].values[0], "%Y-%m-%d").date())
                        ec_wt = st.number_input("Consumed Weight (KG)", value=float(c_info['weight_consumed'].values[0]))
                        ec_mach = st.text_input("Machine / Remarks", value=str(c_info['machine'].values[0]))
                        
                        col_cupd, col_cdel = st.columns(2)
                        update_clicked = col_cupd.form_submit_button("💾 UPDATE CONSUMPTION")
                        delete_clicked = col_cdel.form_submit_button("🗑️ DELETE CONSUMPTION ENTRY")
                        
                        if update_clicked:
                            run_query("UPDATE consumption SET date = ?, weight_consumed = ?, machine = ?, entered_by = ? WHERE id = ?", (str(ec_date), ec_wt, ec_mach.strip().upper(), st.session_state.logged_user, sel_cons_id))
                            st.success("🎉 Consumption entry updated successfully!")
                            st.rerun()
                        if delete_clicked:
                            run_query("DELETE FROM consumption WHERE id = ?", (sel_cons_id,))
                            st.success("🗑️ Consumption entry deleted successfully!")
                            st.rerun()

# TAB: BACKUP & RESTORE
if tab_backup:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>💾 DATABASE BACKUP & RESTORE</h2>", unsafe_allow_html=True)
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.markdown("### 📥 DOWNLOAD DATABASE BACKUP")
        if os.path.exists(db_file):
            with open(db_file, "rb") as f:
                st.download_button(
                    label="📥 DOWNLOAD BACKUP (.db FILE)",
                    data=f,
                    file_name=f"bhaavya_stock_backup_{datetime.today().strftime('%Y-%m-%d')}.db",
                    mime="application/octet-stream"
                )
    with col_b2:
        st.markdown("### 📤 RESTORE / UPLOAD BACKUP")
        uploaded_backup = st.file_uploader("Upload Backup File (.db)", type=["db"])
        if uploaded_backup is not None and st.button("🚀 CONFIRM & RESTORE DATABASE"):
            with open(db_file, "wb") as f:
                f.write(uploaded_backup.getbuffer())
            st.success("🎉 Database successfully restore ho gaya hai! App ko refresh karein.")
            st.rerun()

# TAB 9: CHANGE PASSWORD & USERS
if tab_users:
    st.markdown(f"<h3 style='text-align: center;'>{COMP_NAME} {COMP_DIV}</h3>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>🔐 SUPER ADMIN - PASSWORD & USER CONTROL</h2>", unsafe_allow_html=True)
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        st.markdown("### 🔑 CHANGE USER PASSWORD")
        df_users = get_data("SELECT username, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption FROM users")
        user_list = list(df_users['username'].values)
        with st.form("change_pwd_form"):
            sel_user = st.selectbox("SELECT USERNAME", user_list)
            new_pwd1 = st.text_input("NEW PASSWORD", type="password")
            new_pwd2 = st.text_input("CONFIRM NEW PASSWORD", type="password")
            if st.form_submit_button("UPDATE PASSWORD"):
                if not new_pwd1 or not new_pwd2: st.error("❌ Password fields cannot be empty!")
                elif new_pwd1 != new_pwd2: st.error("❌ Both passwords do not match!")
                else:
                    run_query("UPDATE users SET password = ? WHERE username = ?", (new_pwd1.strip(), sel_user))
                    st.success(f"🎉 Password updated successfully for `{sel_user}`!")
                    st.rerun()

    with col_u2:
        st.markdown("### ➕ CREATE NEW USER & ASSIGN RIGHTS")
        with st.form("add_user_form"):
            new_username = st.text_input("NEW USERNAME")
            new_password = st.text_input("PASSWORD", type="password")
            new_role = st.selectbox("ASSIGN ACCESS ROLE", ["ADMIN", "OPERATOR"])
            
            new_perm_view = st.checkbox("Allow Viewing Live Net Stock Balance", value=True, key="new_u_view")
            new_perm_add = st.checkbox("Allow Adding New Entries (Receiving & Consumption)", value=True, key="new_u_add")
            new_perm_rec = st.checkbox("Allow Editing/Deleting Receiving Entries", value=False, key="new_u_rec")
            new_perm_cons = st.checkbox("Allow Editing/Deleting Consumption Entries", value=False, key="new_u_cons")
            
            if st.form_submit_button("CREATE USER"):
                if not new_username or not new_password: st.error("❌ Username and Password are required!")
                else:
                    try:
                        run_query(
                            "INSERT INTO users (username, password, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                            (new_username.strip(), new_password.strip(), new_role, 1 if new_perm_view else 0, 1 if new_perm_add else 0, 1 if new_perm_rec else 0, 1 if new_perm_cons else 0)
                        )
                        st.success(f"🎉 User `{new_username.strip()}` created successfully!")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Error creating user: {e}")

    st.write("---")
    st.markdown("### ⚙️ MANAGE EXISTING USERS RIGHTS & DELETE USER")
    
    m_user = st.selectbox("SELECT USERNAME", user_list, key="m_user_sel")
    
    conn_u = sqlite3.connect(db_file)
    cur_u = conn_u.cursor()
    cur_u.execute("SELECT can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption FROM users WHERE username = ?", (m_user,))
    u_row = cur_u.fetchone()
    conn_u.close()
    
    c_view_val = bool(u_row[0]) if u_row else True
    c_add_val = bool(u_row[1]) if u_row else True
    c_rec_val = bool(u_row[2]) if u_row else False
    c_cons_val = bool(u_row[3]) if u_row else False

    is_protected = (m_user == "super_admin")

    if is_protected:
        st.warning(f"🔒 User `{m_user}` ek protected system user hai, isliye iske rights edit ya delete nahi kiye ja sakte.")
    
    with st.form("manage_rights_form"):
        m_perm_view = st.checkbox("Allow Viewing Live Net Stock Balance", value=c_view_val, key="m_u_view", disabled=is_protected)
        m_perm_add = st.checkbox("Allow Adding New Entries (Receiving & Consumption)", value=c_add_val, key="m_u_add", disabled=is_protected)
        m_perm_rec = st.checkbox("Allow Editing/Deleting Receiving Entries", value=c_rec_val, key="m_u_rec", disabled=is_protected)
        m_perm_cons = st.checkbox("Allow Editing/Deleting Consumption Entries", value=c_cons_val, key="m_u_cons", disabled=is_protected)
        
        col_save_u, col_del_u = st.columns(2)
        
        if not is_protected:
            save_rights_clicked = col_save_u.form_submit_button("💾 SAVE USER RIGHTS")
            delete_user_clicked = col_del_u.form_submit_button("🗑️ DELETE THIS USER")
            
            if save_rights_clicked:
                run_query("UPDATE users SET can_view_stock = ?, can_add_entry = ?, can_edit_receiving = ?, can_edit_consumption = ? WHERE username = ?", (1 if m_perm_view else 0, 1 if m_perm_add else 0, 1 if m_perm_rec else 0, 1 if m_perm_cons else 0, m_user))
                st.success(f"🎉 Permissions updated successfully for `{m_user}`!")
                st.rerun()
                
            if delete_user_clicked:
                if m_user == st.session_state.logged_user:
                    st.error("❌ Error: Aap jis user se logged in hain use delete nahi kar sakte!")
                else:
                    run_query("DELETE FROM users WHERE username = ?", (m_user,))
                    st.success(f"🗑️ User `{m_user}` successfully deleted!")
                    st.rerun()
        else:
            st.info("ℹ️ Is user ke options locked hain.")

    st.write("---")
    st.markdown("### 📋 ACTIVE SYSTEM USERS & RIGHTS TABLE")
    df_users_table = get_data("SELECT username, role, can_view_stock, can_add_entry, can_edit_receiving, can_edit_consumption FROM users")
    st.dataframe(df_users_table, use_container_width=True)