import streamlit as st
import sqlite3
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

st.set_page_config(page_title="Bhaavya Ecopack - Reel Stock System", layout="wide")

db_file = 'bhaavya_stock.db'

# --- DATABASE SCHEMA & SPEED OPTIMIZATION (WAL MODE) ---
def upgrade_db_schema():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
    except:
        pass

    # Ensure tables exist first
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
            bill_no TEXT DEFAULT ""
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consumption (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            company_reel TEXT,
            weight_consumed REAL,
            machine TEXT
        )
    ''')

    try:
        cursor.execute("SELECT rate, trans_charges, grn_no, bill_no FROM receiving LIMIT 1")
    except sqlite3.OperationalError:
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN rate REAL DEFAULT 0.0')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN trans_charges REAL DEFAULT 0.0')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN grn_no TEXT DEFAULT ""')
        except: pass
        try: cursor.execute('ALTER TABLE receiving ADD COLUMN bill_no TEXT DEFAULT ""')
        except: pass
    
    cursor.execute('CREATE TABLE IF NOT EXISTS mill_master (id INTEGER PRIMARY KEY AUTOINCREMENT, mill_name TEXT UNIQUE NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS shade_master (id INTEGER PRIMARY KEY AUTOINCREMENT, shade_name TEXT UNIQUE NOT NULL)')
    
    # Users Table for Dynamic Database-driven Login & Passwords
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Insert default Super Admin & Operators if table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('super_admin', 'bhaavya123', 'SUPER_ADMIN')")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'ADMIN')")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('operator', 'op123', 'OPERATOR')")
    
    # Safety upgrade: If old 'admin' was just 'ADMIN', ensure super_admin exists
    cursor.execute("SELECT role FROM users WHERE username = 'super_admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('super_admin', 'bhaavya123', 'SUPER_ADMIN')")

    # Paper Master Table for MSL & Reorder
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paper_master (
            gsm INTEGER,
            bf INTEGER,
            deckle INTEGER,
            shade TEXT,
            msl REAL DEFAULT 0.0,
            reorder_qty REAL DEFAULT 0.0,
            PRIMARY KEY (gsm, bf, deckle, shade)
        )
    ''')
    
    try:
        cursor.execute("SELECT DISTINCT mill FROM receiving WHERE mill IS NOT NULL AND mill != ''")
        for mill in cursor.fetchall():
            if mill[0]: cursor.execute("INSERT OR IGNORE INTO mill_master (mill_name) VALUES (?)", (mill[0].upper(),))
    except:
        pass
            
    try:
        cursor.execute("SELECT DISTINCT shade FROM receiving WHERE shade IS NOT NULL AND shade != ''")
        for shade in cursor.fetchall():
            if shade[0]: cursor.execute("INSERT OR IGNORE INTO shade_master (shade_name) VALUES (?)", (shade[0].upper(),))
    except:
        pass
    
    for default_shade in ["NATURAL", "GOLDEN", "YELLOW", "WHITE", "OTHER"]:
        cursor.execute("INSERT OR IGNORE INTO shade_master (shade_name) VALUES (?)", (default_shade,))
            
    conn.commit()
    conn.close()

upgrade_db_schema()

# --- DYNAMIC DATABASE LOGIN SYSTEM ---
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
    st.markdown("<h2 style='text-align: center;'>🔐 BHAAVYA ECOPACK - SECURE LOGIN</h2>", unsafe_allow_html=True)
    with st.form("login_form"):
        st.text_input("USERNAME", key="username_input")
        st.text_input("PASSWORD", type="password", key="password_input")
        st.form_submit_button("LOGIN", on_click=check_login)
    st.stop()

def run_query(query, params=()):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_data(query, params=()):
    conn = sqlite3.connect(db_file)
    conn.create_function("CLEAN_NAME", 1, lambda x: "".join(str(x).upper().replace(".", "").replace(" ", "").split()) if x else "")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    for col in df.columns:
        if 'DATE' in col.upper(): df[col] = df[col].astype(str).str.split(" ").str[0]
    return df

# Helper function for Excel Stock Import
def import_excel_stock(uploaded_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        df_rec = pd.read_excel(uploaded_file, sheet_name='RECEIVING')
        required_cols = ['Sr', 'Date', 'Company Reel', 'Mill Reel No', 'Mill', 'GSM', 'BF', 'Deckle', 'Weight', 'Shade', 'Supplier', 'Location', 'Remarks']
        df_rec_cleaned = df_rec[required_cols].dropna(subset=['Company Reel'])
        count = 0
        for _, row in df_rec_cleaned.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO receiving (sr, date, company_reel, mill_reel, mill, gsm, bf, deckle, weight, shade, supplier, location, remarks, rate, trans_charges, grn_no, bill_no)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, "", "")
            ''', (int(row['Sr']), str(row['Date']), str(row['Company Reel']), str(row['Mill Reel No']), str(row['Mill']), 
                  int(row['GSM']), int(row['BF']), int(row['Deckle']), float(row['Weight']), str(row['Shade']), 
                  str(row['Supplier']), str(row['Location']), str(row['Remarks'])))
            count += 1
        conn.commit()
        conn.close()
        return True, f"🎉 MIGRATION SUCCESSFUL! {count} Fresh Reels ko database mein import kar diya gaya hai."
    except Exception as e: return False, f"❌ Excel Import Error: {str(e)}"

# Helper function to compute date shortcuts
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


# --- MAIN TITLE & ENHANCED SIDEBAR QUICK REEL SEARCH ---
st.sidebar.write(f"👤 **Logged User:** `{st.session_state.logged_user}` ({st.session_state.user_role})")
if st.sidebar.button("🚪 LOGOUT"):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.logged_user = ""
    st.rerun()

st.sidebar.write("---")
st.sidebar.header("🔍 QUICK REEL SEARCH")
search_reel = st.sidebar.text_input("ENTER BHAAVYA REEL NO:")
if search_reel:
    df_search_rec = get_data("SELECT r.date as [DATE], r.company_reel as [BHAAVYA REEL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE], r.weight as [WEIGHT], r.shade as [SHADE], r.supplier as [SUPPLIER], r.location as [LOCATION] FROM receiving r WHERE r.company_reel = ?", (search_reel,))
    
    if not df_search_rec.empty:
        orig_wt = float(df_search_rec['WEIGHT'].values[0])
        rec_date = df_search_rec['DATE'].values[0]
        mill_n = df_search_rec['MILL'].values[0]
        gsm_n = df_search_rec['GSM'].values[0]
        bf_n = df_search_rec['BF'].values[0]
        deckle_n = df_search_rec['DECKLE'].values[0]
        shade_n = df_search_rec['SHADE'].values[0]
        
        df_search_cons = get_data("SELECT c.date as [DATE], c.weight_consumed as [USED (KG)], c.machine as [REMARKS / MACHINE] FROM consumption c WHERE c.company_reel = ? ORDER BY c.date ASC", (search_reel,))
        
        total_c_wt = float(df_search_cons['USED (KG)'].sum()) if not df_search_cons.empty else 0.0
        net_balance = orig_wt - total_c_wt
        
        st.sidebar.success("✅ REEL FOUND IN STOCK!")
        st.sidebar.markdown(f"**🏭 Mill:** `{mill_n}` | **Shade:** `{shade_n}`")
        st.sidebar.markdown(f"**📏 Specs:** `{deckle_n}mm` | `{gsm_n}GSM` | `{bf_n}BF`")
        st.sidebar.markdown(f"**📅 Rec. Date:** `{rec_date}`")
        st.sidebar.write("---")
        
        st.sidebar.metric("🏋️‍♂️ OPENING/ORIGINAL WT", f"{orig_wt:,.1f} KG")
        st.sidebar.metric("📉 TOTAL CONSUMED / ADJ.", f"{total_c_wt:,.1f} KG")
        
        if net_balance > 0:
            st.sidebar.metric("🔵 CURRENT NET BALANCE", f"{net_balance:,.1f} KG")
        else:
            st.sidebar.error(f"🔴 CURRENT BALANCE: {net_balance:,.1f} KG (EMPTY)")
            
        st.sidebar.write("---")
        if not df_search_cons.empty:
            st.sidebar.markdown("#### 📜 CONSUMPTION / AUDIT LOGS:")
            st.sidebar.dataframe(df_search_cons, use_container_width=True)
        else:
            st.sidebar.info("ℹ️ Is reel mein abhi tak koi consumption ya adjustment nahi hua hai.")
    else:
        st.sidebar.error("❌ REEL NO NOT FOUND!")

# Tabs Layout Setup based on Roles
if st.session_state.user_role == "SUPER_ADMIN":
    tabs = st.tabs(["📊 LIVE NET STOCK BALANCE", "📥 GRN RECEIVING ENTRY (MULTIPLE)", "📉 DAILY CONSUMPTION ENTRY", "🛠️ PHYSICAL STOCK ADJUSTMENT", "🚨 MSL & LOW STOCK ALERTS", "📤 EXCEL STOCK IMPORT", "📈 CONSUMPTION REPORTS", "📋 HISTORY LOGS", "🔐 CHANGE PASSWORD & USERS"])
    tab_live, tab_rec, tab_cons, tab_adj, tab_msl, tab_import, tab_rep, tab_hist, tab_users = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7], tabs[8]
elif st.session_state.user_role == "ADMIN":
    tabs = st.tabs(["📊 LIVE NET STOCK BALANCE", "📥 GRN RECEIVING ENTRY (MULTIPLE)", "📉 DAILY CONSUMPTION ENTRY", "🛠️ PHYSICAL STOCK ADJUSTMENT", "🚨 MSL & LOW STOCK ALERTS", "📤 EXCEL STOCK IMPORT", "📈 CONSUMPTION REPORTS", "📋 HISTORY LOGS"])
    tab_live, tab_rec, tab_cons, tab_adj, tab_msl, tab_import, tab_rep, tab_hist = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4], tabs[5], tabs[6], tabs[7]
    tab_users = None
else:
    tabs = st.tabs(["📥 GRN RECEIVING ENTRY (MULTIPLE)", "📉 DAILY CONSUMPTION ENTRY"])
    tab_rec, tab_cons = tabs[0], tabs[1]
    tab_live, tab_adj, tab_msl, tab_import, tab_rep, tab_hist, tab_users = None, None, None, None, None, None, None

# TAB 1: LIVE BALANCE WITH CHART AT THE VERY TOP
if tab_live:
    with tab_live:
        st.markdown("<h2 style='text-align: center;'>✨ REAL-TIME AVAILABLE STOCK BALANCE</h2>", unsafe_allow_html=True)
        query_live = """
        SELECT 
            r.grn_no as [GRN NO], r.bill_no as [CUSTOMER BILL NO], UPPER(r.mill) as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE (MM)],
            ROUND(cast(r.deckle as REAL) / 25.4, 1) as [DECKLE (INCH)], UPPER(r.shade) as [SHADE],
            r.mill_reel as [MILL REEL NO], r.company_reel as [BHAAVYA REEL NO],
            CASE WHEN (r.weight - COALESCE(c.weight_consumed, 0)) <= 0 THEN 'EMPTY' ELSE 'LIVE' END as [STATUS],
            r.date as [LAST RECEIVING DATE],
            r.weight as [SUM OF ORIGINAL WEIGHT], COALESCE(c.weight_consumed, 0) as [SUM OF TOTAL CONSUMED],
            (r.weight - COALESCE(c.weight_consumed, 0)) as [SUM OF BALANCE WEIGHT],
            r.rate as [RATE/KG], r.trans_charges as [TRANS CHARGES],
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
                    tooltip=[
                        alt.Tooltip('MILL:N', title='MILL NAME'),
                        alt.Tooltip('TOTAL_WEIGHT:Q', title='TOTAL WEIGHT (KG)', format=',.0f'),
                        alt.Tooltip('REEL_COUNT:Q', title='TOTAL REELS')
                    ]
                )

                wt_labels = bars.mark_text(
                    align='left', baseline='middle', dx=14, angle=270, color='black', fontWeight='bold', fontSize=11
                ).encode(text='WT_LABEL:N')

                count_labels = bars.mark_text(
                    align='right', baseline='middle', dx=-14, angle=270, color='#D00000', fontWeight='bold', fontSize=11
                ).encode(text='COUNT_LABEL:N')

                final_chart = (bars + wt_labels + count_labels).properties(
                    height=500,
                    width=alt.Step(70)
                )
                
                st.altair_chart(final_chart, use_container_width=False)

            st.write("---")

            st.markdown("### 🎛️ CLICK BUTTONS TO FILTER (EXCEL SLICERS STYLE)")
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

# TAB 2: GRN RECEIVING ENTRY (MULTIPLE)
with tab_rec:
    st.markdown("<h2 style='text-align: center;'>📥 GRN RECEIVING - ADD MULTIPLE REELS IN ONE CHALAN</h2>", unsafe_allow_html=True)
    st.markdown("#### 📑 1. CHALAN / INVOICE HEADER DETAILS")
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)
    grn_date = col_h1.date_input("RECEIVING DATE", datetime.today())
    grn_no_val = col_h2.text_input("GRN NO")
    bill_no_val = col_h3.text_input("CUSTOMER BILL NO")
    grn_supplier = col_h4.text_input("SUPPLIER NAME")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    df_mills = get_data("SELECT mill_name FROM mill_master ORDER BY mill_name ASC")
    mill_options = list(df_mills['mill_name'].values)
    grn_mill = col_f1.selectbox("SELECT MILL NAME", [""] + mill_options)
    grn_trans = col_f2.text_input("TOTAL TRANSPORTATION CHARGES", value="")
    grn_location = col_f3.text_input("GODOWN LOCATION", value="MAIN GODOWN")
    
    st.markdown("#### ⚙️ 2. COLUMN SEQUENCE CONFIGURATOR")
    seq_choice = st.selectbox(
        "Apne hisab se columns ka sequence chunye (Personalise Grid Layout):",
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

    df_shades = get_data("SELECT shade_name FROM shade_master ORDER BY shade_name ASC")
    shade_options = [""] + list(df_shades['shade_name'].values)
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
    h_col0.markdown("**Item**")
    h_col1.markdown("**Bhaavya Reel No ***")
    h_col2.markdown("**Mill Reel No**")
    
    if "Deckle (mm) ➡️ 📄 GSM" in seq_choice:
        h_v1.markdown("**Deckle(mm)**"); h_v2.markdown("**GSM**"); h_v3.markdown("**BF**"); h_v4.markdown("**Rate/Kg**")
    elif "GSM ➡️ 💪 BF" in seq_choice:
        h_v1.markdown("**GSM**"); h_v2.markdown("**BF**"); h_v4.markdown("**Rate/Kg**"); h_v3.markdown("**Deckle(mm)**")
    else:
        h_v1.markdown("**BF**"); h_v2.markdown("**Rate/Kg**"); h_v3.markdown("**Deckle(mm)**"); h_v4.markdown("**GSM**")
        
    h_col6.markdown("**Weight(Kg)***")
    h_col7.markdown("**Shade**")
    h_col8.markdown("**Remarks**")

    for idx in range(st.session_state.grid_reels_count):
        if "Deckle (mm) ➡️ 📄 GSM" in seq_choice:
            cur_bf = st.session_state.get(f"v3_bf_{idx}", "")
            cur_rate = st.session_state.get(f"v4_rat_{idx}", "")
        elif "GSM ➡️ 💪 BF" in seq_choice:
            cur_bf = st.session_state.get(f"v2_bf_{idx}", "")
            cur_rate = st.session_state.get(f"v3_rat_{idx}", "")
        else:
            cur_bf = st.session_state.get(f"v1_bf_{idx}", "")
            cur_rate = st.session_state.get(f"v2_rat_{idx}", "")
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
                for index, item in enumerate(saved_items_list):
                    if not item["bhaavya_no"] or not item["weight"]:
                        st.error(f"❌ Row #{index+1} mein Bhaavya Reel No ya Weight khali hai!")
                        success_flag = False
                        break
                    
                    cursor.execute("SELECT COALESCE(MAX(sr), 0) + 1 FROM receiving")
                    next_sr = cursor.fetchone()[0]
                    cursor.execute('''
                        INSERT INTO receiving (sr, date, company_reel, mill_reel, mill, gsm, bf, deckle, weight, shade, supplier, location, remarks, rate, trans_charges, grn_no, bill_no)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (next_sr, str(grn_date), item["bhaavya_no"].strip(), item["mill_no"].strip(), grn_mill, 
                          (int(item["gsm"]) if item["gsm"] else 0), (int(item["bf"]) if item["bf"] else 0), (int(item["deckle"]) if item["deckle"] else 0), 
                          float(item["weight"]), item["shade"], grn_supplier, grn_location, item["remarks"], 
                          (float(item["rate"]) if item["rate"] else 0.0), (float(grn_trans) if grn_trans else 0.0), grn_no_val.strip(), bill_no_val.strip()))
                    saved_count += 1
                if success_flag:
                    conn.commit()
                    st.success(f"🎉 Success! GRN ke andar {saved_count} Reels register ho gayi hain.")
                    st.session_state.grid_reels_count = 4
                    st.session_state.grn_realtime_rates = {}
                    st.rerun()
                else: conn.rollback()
            except Exception as e:
                conn.rollback()
                st.error(f"❌ Save Error: {e}")
            finally:
                conn.close()

# TAB 3: DAILY CONSUMPTION ENTRY
with tab_cons:
    st.markdown("<h2 style='text-align: center;'>📉 ADD DAILY CONSUMPTION ENTRY (MAAL MACHINE PAR CHADHAYA)</h2>", unsafe_allow_html=True)
    cons_comp_reel = st.text_input("ENTER BHAAVYA REEL NO TO CONSUME *", key="reel_live_check_input")
    current_balance_weight = 0.0
    reel_valid = False
    
    if cons_comp_reel:
        check_rec = get_data("SELECT weight, mill, gsm, bf, deckle, shade FROM receiving WHERE company_reel = ?", (cons_comp_reel,))
        if check_rec.empty: st.error("❌ BHAAVYA REEL NO NOT FOUND IN STOCK ENTRIES!")
        else:
            reel_valid = True
            orig_wt = check_rec['weight'].values[0]
            mill_n = check_rec['mill'].values[0]
            gsm_n = check_rec['gsm'].values[0]
            bf_n = check_rec['bf'].values[0]
            deckle_n = check_rec['deckle'].values[0]
            shade_n = check_rec['shade'].values[0]
            
            check_past = get_data("SELECT date, weight_consumed, machine FROM consumption WHERE company_reel = ?", (cons_comp_reel,))
            total_consumed = check_past['weight_consumed'].sum() if not check_past.empty else 0.0
            current_balance_weight = float(orig_wt - total_consumed)
            
            st.markdown(f"### 📋 LIVE HISTORY FOR REEL NO: `{cons_comp_reel}` (`{mill_n}` | DECKLE: `{deckle_n} MM` | GSM: `{gsm_n}` | BF: `{bf_n}` | SHADE: `{shade_n}`)")
            st.info(f"🏋️‍♂️ **Original Weight:** {orig_wt} KG | 📉 **Total Consumed Till Now:** {total_consumed} KG | 🔵 **CURRENT BALANCED WEIGHT AVAILABLE:** **{current_balance_weight} KG**")
            if not check_past.empty: st.dataframe(check_past, use_container_width=True)
            if current_balance_weight <= 0:
                st.error("❌ THIS REEL IS COMPLETELY CONSUMED / EMPTY (0 KG LEFT)!")
                reel_valid = False

    st.write("---")
    with st.form("consumption_execution_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        cons_date = col1.date_input("DATE CONSUMED", datetime.today())
        cons_weight_str = col2.text_input("WEIGHT CONSUMED (KG) *", value="")
        cons_machine = col1.selectbox("MACHINE NAME", ["B FLUTE", "C FLUTE", "5 PLY LINE", "OTHER"])
        
        if st.form_submit_button("SAVE CONSUMPTION ENTRY"):
            try: cons_weight = float(cons_weight_str) if cons_weight_str else 0.0
            except: cons_weight = 0.0
            if not cons_comp_reel: st.error("❌ Please enter a Bhaavya Reel Number first.")
            elif not reel_valid: st.error("❌ Cannot record consumption. This reel is invalid or completely empty.")
            elif cons_weight <= 0.0: st.error("❌ Kripya valid Weight Consumed enter karein (Khali ya 0 nahi chalega).")
            elif float(cons_weight) > current_balance_weight: st.error(f"❌ CONSTRAINT BLOCK: Only **{current_balance_weight} KG** left!")
            else:
                try:
                    run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine) VALUES (?, ?, ?, ?)", (str(cons_date), cons_comp_reel, float(cons_weight), cons_machine))
                    st.success("🎉 Successfully consumed!")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# TAB 4: PHYSICAL STOCK ADJUSTMENT
if tab_adj:
    with tab_adj:
        st.markdown("<h2 style='text-align: center;'>🛠️ PHYSICAL STOCK AUDIT & ADJUSTMENT</h2>", unsafe_allow_html=True)
        st.info("💡 Physical Stock Counting ke baad agar godown ka asal vajan software balance se alag aaye, toh yahan se adjustment karein.")
        
        adj_reel_no = st.text_input("ENTER BHAAVYA REEL NO TO ADJUST *", key="adj_reel_search_key")
        
        if adj_reel_no:
            check_rec = get_data("SELECT weight, mill, gsm, bf, deckle, shade FROM receiving WHERE company_reel = ?", (adj_reel_no,))
            if check_rec.empty:
                st.error("❌ BHAAVYA REEL NO NOT FOUND!")
            else:
                orig_wt = float(check_rec['weight'].values[0])
                mill_n = check_rec['mill'].values[0]
                gsm_n = check_rec['gsm'].values[0]
                bf_n = check_rec['bf'].values[0]
                deckle_n = check_rec['deckle'].values[0]
                shade_n = check_rec['shade'].values[0]
                
                check_past = get_data("SELECT SUM(weight_consumed) as total_c FROM consumption WHERE company_reel = ?", (adj_reel_no,))
                total_c = float(check_past['total_c'].values[0]) if not check_past['total_c'].empty and check_past['total_c'].values[0] is not None else 0.0
                curr_bal = orig_wt - total_c
                
                st.markdown(f"### 📋 CURRENT DETAILS FOR REEL: `{adj_reel_no}`")
                st.success(f"🏭 Mill: **{mill_n}** | Deckle: **{deckle_n} MM** | GSM: **{gsm_n}** | BF: **{bf_n}** | Shade: **{shade_n}**")
                st.info(f"🏋️‍♂️ Original Weight: **{orig_wt} KG** | Total Consumed: **{total_c} KG** | 🔵 **CURRENT SOFTWARE BALANCE:** **{curr_bal} KG**")
                
                with st.form("stock_adjustment_form", clear_on_submit=True):
                    col_a1, col_a2 = st.columns(2)
                    adj_date = col_a1.date_input("ADJUSTMENT DATE", datetime.today())
                    adj_type = col_a2.selectbox("ADJUSTMENT TYPE", ["SET EXACT PHYSICAL WEIGHT (Pura Stock Update)", "ADD WEIGHT (+ Plus)", "SUBTRACT WEIGHT (- Minus)"])
                    adj_value_str = col_a1.text_input("ENTER WEIGHT (KG) *", value="")
                    adj_remarks = col_a2.text_input("AUDIT / ADJUSTMENT REMARKS (Reason)", value="Physical Stock Audit Correction")
                    
                    if st.form_submit_button("💾 CONFIRM & UPDATE PHYSICAL STOCK"):
                        try:
                            adj_val = float(adj_value_str) if adj_value_str else 0.0
                            if adj_val < 0:
                                st.error("❌ Kripya positive number enter karein!")
                            else:
                                if "SET EXACT PHYSICAL WEIGHT" in adj_type:
                                    diff = curr_bal - adj_val
                                    if diff > 0:
                                        run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine) VALUES (?, ?, ?, ?)", (str(adj_date), adj_reel_no, diff, f"AUDIT SUB [{diff}KG]: {adj_remarks}"))
                                    elif diff < 0:
                                        new_orig = orig_wt + abs(diff)
                                        run_query("UPDATE receiving SET weight = ? WHERE company_reel = ?", (new_orig, adj_reel_no))
                                        run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine) VALUES (?, ?, ?, ?)", (str(adj_date), adj_reel_no, 0.0, f"AUDIT ADD [{abs(diff)}KG]: {adj_remarks}"))
                                
                                elif "ADD WEIGHT" in adj_type:
                                    new_orig = orig_wt + adj_val
                                    run_query("UPDATE receiving SET weight = ? WHERE company_reel = ?", (new_orig, adj_reel_no))
                                    run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine) VALUES (?, ?, ?, ?)", (str(adj_date), adj_reel_no, 0.0, f"AUDIT ADD [{adj_val}KG]: {adj_remarks}"))
                                
                                elif "SUBTRACT WEIGHT" in adj_type:
                                    run_query("INSERT INTO consumption (date, company_reel, weight_consumed, machine) VALUES (?, ?, ?, ?)", (str(adj_date), adj_reel_no, adj_val, f"AUDIT SUB [{adj_val}KG]: {adj_remarks}"))
                                
                                st.success(f"🎉 Physical Stock Updated Successfully for Reel #{adj_reel_no}!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Adjustment failed: {e}")

# TAB 5: MSL & LOW STOCK ALERTS
if tab_msl:
    with tab_msl:
        st.markdown("<h2 style='text-align: center;'>🚨 DECKLE-GSM-BF-SHADE WISE MINIMUM STOCK LEVEL (MSL) & ALERTS</h2>", unsafe_allow_html=True)
        st.info("💡 Yahan aap unique Deckle, GSM, BF, aur Shade combination ke liye **MSL (Minimum Stock Level)** set kar sakte hain. Jab bhi stock usse kam hoga, red alert show hoga!")

        run_query("""
            INSERT OR IGNORE INTO paper_master (gsm, bf, deckle, shade, msl, reorder_qty)
            SELECT DISTINCT gsm, bf, deckle, UPPER(shade), 0.0, 0.0 
            FROM receiving 
            WHERE gsm > 0 AND bf > 0 AND deckle > 0
        """)

        query_msl_view = """
            SELECT 
                p.gsm as [GSM], 
                p.bf as [BF], 
                p.deckle as [DECKLE (MM)], 
                UPPER(p.shade) as [SHADE],
                COALESCE(p.msl, 0.0) as [MSL (KG)],
                COALESCE(p.reorder_qty, 0.0) as [REORDER QTY (KG)],
                COALESCE(SUM(r.weight - COALESCE(c.weight_consumed, 0)), 0.0) as [CURRENT STOCK (KG)]
            FROM paper_master p
            LEFT JOIN receiving r ON p.gsm = r.gsm AND p.bf = r.bf AND p.deckle = r.deckle AND UPPER(p.shade) = UPPER(r.shade)
            LEFT JOIN (
                SELECT company_reel, SUM(weight_consumed) as weight_consumed 
                FROM consumption GROUP BY company_reel
            ) c ON r.company_reel = c.company_reel
            GROUP BY p.gsm, p.bf, p.deckle, UPPER(p.shade)
            ORDER BY p.gsm DESC, p.bf DESC
        """
        df_msl_check = get_data(query_msl_view)

        if not df_msl_check.empty:
            df_msl_check['STATUS'] = df_msl_check.apply(
                lambda row: '🔴 LOW STOCK ALERT' if row['CURRENT STOCK (KG)'] < row['MSL (KG)'] else '🟢 SUFFICIENT', axis=1
            )
            
            low_stock_df = df_msl_check[df_msl_check['STATUS'] == '🔴 LOW STOCK ALERT']
            
            if not low_stock_df.empty:
                st.error(f"🚨 CRITICAL ALERT: {len(low_stock_df)} paper specifications have dropped below their Minimum Stock Level (MSL)!")
                st.dataframe(low_stock_df, use_container_width=True)
            else:
                st.success("✅ All paper specifications are currently above their Minimum Stock Level (MSL).")

            st.write("---")
            st.markdown("### ⚙️ UPDATE MSL & REORDER QUANTITY PER SPECIFICATION")
            
            with st.form("update_msl_form"):
                col_u1, col_u2, col_u3, col_u4, col_u5 = st.columns(5)
                sel_gsm = col_u1.selectbox("SELECT GSM", sorted(df_msl_check['GSM'].unique()))
                sel_bf = col_u2.selectbox("SELECT BF", sorted(df_msl_check['BF'].unique()))
                sel_dec = col_u3.selectbox("SELECT DECKLE", sorted(df_msl_check['DECKLE (MM)'].unique()))
                sel_shd = col_u4.selectbox("SELECT SHADE", sorted(df_msl_check['SHADE'].unique()))
                
                existing_row = df_msl_check[(df_msl_check['GSM'] == sel_gsm) & (df_msl_check['BF'] == sel_bf) & (df_msl_check['DECKLE (MM)'] == sel_dec) & (df_msl_check['SHADE'] == sel_shd)]
                curr_msl_val = float(existing_row['MSL (KG)'].values[0]) if not existing_row.empty else 0.0
                curr_reorder_val = float(existing_row['REORDER QTY (KG)'].values[0]) if not existing_row.empty else 0.0

                new_msl_str = col_u5.text_input("NEW MSL (KG)", value=str(curr_msl_val))
                new_reorder_str = st.text_input("NEW REORDER QTY (KG)", value=str(curr_reorder_val))

                if st.form_submit_button("💾 SAVE MSL SETTINGS"):
                    try:
                        n_msl = float(new_msl_str) if new_msl_str else 0.0
                        n_reorder = float(new_reorder_str) if new_reorder_str else 0.0
                        run_query("""
                            INSERT INTO paper_master (gsm, bf, deckle, shade, msl, reorder_qty)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(gsm, bf, deckle, shade) DO UPDATE SET msl = ?, reorder_qty = ?
                        """, (int(sel_gsm), int(sel_bf), int(sel_dec), str(sel_shd), n_msl, n_reorder, n_msl, n_reorder))
                        st.success("🎉 MSL settings updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error updating MSL: {e}")

            st.write("---")
            st.markdown("### 📋 COMPLETE SPECIFICATION MSL MASTER LIST")
            st.dataframe(df_msl_check, use_container_width=True)
        else:
            st.info("ℹ️ No paper stock data found yet to configure MSL.")

# TAB 6: EXCEL IMPORT
if tab_import:
    with tab_import:
        st.markdown("<h2 style='text-align: center;'>📤 BULK STOCK FILE IMPORT (EXCEL)</h2>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])
        if uploaded_file is not None and st.button("🚀 START BULK IMPORT NOW"):
            success, message = import_excel_stock(uploaded_file)
            if success: st.success(message)
            else: st.error(message)

# TAB 7: CONSUMPTION REPORTS
if tab_rep:
    with tab_rep:
        st.markdown("<h2 style='text-align: center;'>📈 MILL-WISE CONSUMPTION ANALYSIS & REPORTS</h2>", unsafe_allow_html=True)
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

# TAB 8: HISTORY LOGS
if tab_hist:
    with tab_hist:
        st.markdown("<h2 style='text-align: center;'>📋 COMPLETE SYSTEM HISTORY & AUDIT LOGS</h2>", unsafe_allow_html=True)
        
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["🛠️ PHYSICAL STOCK AUDIT LOGS", "📥 RECEIVING HISTORY", "📉 CONSUMPTION HISTORY"])
        
        with sub_tab1:
            st.markdown("### 🛠️ DATE-WISE PHYSICAL STOCK AUDIT & ADJUSTMENT LOGS")
            st.pills("⚡ QUICK DATES:", ["📅 TODAY", "📅 YESTERDAY", "📅 THIS MONTH", "📅 LAST 3 MONTH", "📅 CURRENT FINANCIAL YEAR"], key="audit_shortcut_pill", on_change=handle_audit_shortcut)
            audit_d1, audit_d2 = st.columns(2)
            st.session_state.a_start = audit_d1.date_input("AUDIT FROM DATE", value=st.session_state.a_start, key=f"a_start_input_v_{st.session_state.audit_version}")
            st.session_state.a_end = audit_d2.date_input("AUDIT TO DATE", value=st.session_state.a_end, key=f"a_end_input_v_{st.session_state.audit_version}")
            
            query_audit_raw = """
                SELECT 
                    c.date as [ADJUSTMENT DATE], 
                    c.company_reel as [BHAAVYA REEL NO], 
                    r.mill as [MILL], 
                    r.gsm as [GSM], 
                    r.bf as [BF], 
                    r.deckle as [DECKLE (MM)],
                    c.weight_consumed as [RAW_WEIGHT],
                    c.machine as [FULL AUDIT REMARKS]
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
                        if "[" in remarks and "KG]" in remarks:
                            val = remarks.split("[")[1].split("KG]")[0]
                            return f"+{val} KG"
                        return f"+{raw_wt} KG"
                    else:
                        if raw_wt > 0:
                            return f"-{raw_wt} KG"
                        elif "[" in remarks and "KG]" in remarks:
                            val = remarks.split("[")[1].split("KG]")[0]
                            return f"-{val} KG"
                        return f"-{raw_wt} KG"

                df_audit_raw['ADJUSTMENT TYPE'] = df_audit_raw['FULL AUDIT REMARKS'].apply(parse_audit_type)
                df_audit_raw['WEIGHT CHANGE'] = df_audit_raw.apply(parse_weight_change, axis=1)

                cols_order = ['ADJUSTMENT DATE', 'BHAAVYA REEL NO', 'MILL', 'GSM', 'BF', 'DECKLE (MM)', 'ADJUSTMENT TYPE', 'WEIGHT CHANGE', 'FULL AUDIT REMARKS']
                st.dataframe(df_audit_raw[cols_order], use_container_width=True)
            else:
                st.info("ℹ️ Is date range ke andar koi Physical Stock Adjustment ki entry nahi mili.")

        with sub_tab2:
            st.markdown("### 📥 RECEIVING / GRN HISTORY RECORDS")
            st.pills("⚡ QUICK DATES:", ["📅 TODAY", "📅 YESTERDAY", "📅 THIS MONTH", "📅 LAST 3 MONTH", "📅 CURRENT FINANCIAL YEAR"], key="rec_shortcut_pill", on_change=handle_rec_shortcut)
            rec_d1, rec_d2 = st.columns(2)
            st.session_state.r_start = rec_d1.date_input("RECEIPT FROM DATE", value=st.session_state.r_start, key=f"r_start_input_v_{st.session_state.rec_version}")
            st.session_state.r_end = rec_d2.date_input("RECEIPT TO DATE", value=st.session_state.r_end, key=f"r_end_input_v_{st.session_state.rec_version}")
            df_rec_hist = get_data("SELECT r.date as [DATE], r.grn_no as [GRN NO], r.bill_no as [CUSTOMER BILL NO], r.company_reel as [BHAAVYA REEL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE], r.weight as [WEIGHT], r.rate as [RATE/KG], r.trans_charges as [TRANS CHARGES] FROM receiving r WHERE strftime('%Y-%m-%d', r.date) BETWEEN ? AND ?", (str(st.session_state.r_start), str(st.session_state.r_end)))
            st.dataframe(df_rec_hist, use_container_width=True)

        with sub_tab3:
            st.markdown("### 📉 DAILY CONSUMPTION HISTORY RECORDS")
            st.pills("⚡ QUICK DATES:", ["📅 TODAY", "📅 YESTERDAY", "📅 THIS MONTH", "📅 LAST 3 MONTH", "📅 CURRENT FINANCIAL YEAR"], key="cons_shortcut_pill", on_change=handle_cons_shortcut)
            cons_d1, cons_d2 = st.columns(2)
            st.session_state.c_start = cons_d1.date_input("CONSUMPTION FROM DATE", value=st.session_state.c_start, key=f"c_start_input_v_{st.session_state.cons_version}")
            st.session_state.c_end = cons_d2.date_input("CONSUMPTION TO DATE", value=st.session_state.c_end, key=f"c_end_input_v_{st.session_state.cons_version}")
            
            query_fix_cons = """
                SELECT c.date as [DATE], c.company_reel as [BHAAVYA REEL NO], r.mill as [MILL], r.gsm as [GSM], r.bf as [BF], r.deckle as [DECKLE], c.weight_consumed as [WEIGHT CONSUMED], c.machine as [MACHINE] 
                FROM consumption c LEFT JOIN receiving r ON c.company_reel = r.company_reel 
                WHERE strftime('%Y-%m-%d', c.date) BETWEEN ? AND ? AND c.machine NOT LIKE 'AUDIT%'
            """
            df_cons_hist = get_data(query_fix_cons, (str(st.session_state.c_start), str(st.session_state.c_end)))
            st.dataframe(df_cons_hist, use_container_width=True)

# TAB 9: CHANGE PASSWORD & USERS (SUPER ADMIN ONLY)
if tab_users:
    with tab_users:
        st.markdown("<h2 style='text-align: center;'>🔐 SUPER ADMIN - PASSWORD & USER CONTROL</h2>", unsafe_allow_html=True)
        st.info("💡 Yeh panel sirf **SUPER_ADMIN** ke paas hai. Yahan aap decide kar sakte hain ki kisko kaisa role dena hai aur kiska password change karna hai.")
        
        col_u1, col_u2 = st.columns(2)
        
        with col_u1:
            st.markdown("### 🔑 CHANGE USER PASSWORD")
            df_users = get_data("SELECT username, role FROM users")
            user_list = list(df_users['username'].values)
            
            with st.form("change_pwd_form"):
                sel_user = st.selectbox("SELECT USERNAME", user_list)
                new_pwd1 = st.text_input("NEW PASSWORD", type="password")
                new_pwd2 = st.text_input("CONFIRM NEW PASSWORD", type="password")
                
                if st.form_submit_button("UPDATE PASSWORD"):
                    if not new_pwd1 or not new_pwd2:
                        st.error("❌ Password fields cannot be empty!")
                    elif new_pwd1 != new_pwd2:
                        st.error("❌ Both passwords do not match!")
                    else:
                        run_query("UPDATE users SET password = ? WHERE username = ?", (new_pwd1.strip(), sel_user))
                        st.success(f"🎉 Password updated successfully for user `{sel_user}`!")
                        st.rerun()

        with col_u2:
            st.markdown("### ➕ CREATE NEW USER & ASSIGN ROLE")
            with st.form("add_user_form"):
                new_username = st.text_input("NEW USERNAME")
                new_password = st.text_input("PASSWORD", type="password")
                new_role = st.selectbox("ASSIGN ACCESS ROLE", ["ADMIN", "OPERATOR"])
                
                if st.form_submit_button("CREATE USER"):
                    if not new_username or not new_password:
                        st.error("❌ Username and Password are required!")
                    else:
                        try:
                            run_query("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_username.strip(), new_password.strip(), new_role))
                            st.success(f"🎉 New user `{new_username.strip()}` created with role `{new_role}`!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error creating user (Username might already exist): {e}")

        st.write("---")
        st.markdown("### 📋 ACTIVE SYSTEM USERS & ROLES LIST")
        st.dataframe(df_users, use_container_width=True)
