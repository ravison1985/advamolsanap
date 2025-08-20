import streamlit as st
import pandas as pd
import sqlite3
import datetime
from io import BytesIO

# PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ---------------- Page & Style ----------------
st.set_page_config(page_title="Advocate Client Desk", layout="centered")

APP_CSS = """

<style>
body {
    background: linear-gradient(135deg, #e3f2fd, #ffffff);
    font-family: 'Segoe UI', Tahoma, sans-serif;
}
.main-title {
    font-size: 36px;
    font-weight: bold;
    text-align: center;
    color: #0d47a1;
    margin-bottom: 15px;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.2);
}
.alert-section {
    background: #fff8e1;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
    border-left: 6px solid #ffb300;
}
.alert-title {
    font-size: 20px;
    font-weight: bold;
    color: #e65100;
    margin-bottom: 10px;
}
.alert-item {
    font-size: 16px;
    color: #333;
    padding: 5px 0;
    border-bottom: 1px dashed #ccc;
}
.alert-item:last-child {
    border-bottom: none;
}
.login-box {
    background: #ffffff;
    padding: 25px;
    border-radius: 10px;
    width: 350px;
    margin: 100px auto;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.3);
    text-align: center;
}
.stButton button {
    width: 100%;
    background: #1976d2 !important;
    color: white !important;
    font-weight: bold;
    border-radius: 8px;
}
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)


# ---------------- Database ----------------
DB = "advocate_clients.db"

def conn_cur():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.execute("PRAGMA foreign_keys = ON")
    return c, c.cursor()

def table_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def safe_alter(conn, table, col, coltype):
    cols = table_columns(conn, table)
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")

def init_db():
    con, cur = conn_cur()
    # base tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            case_details TEXT,
            contact TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hearings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            hearing_date DATE NOT NULL,
            note TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            pay_date DATE NOT NULL,
            amount REAL NOT NULL,
            mode TEXT,
            note TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)
    # migrate: add new columns if missing
    safe_alter(con, "clients", "agreed_fee", "REAL DEFAULT 0")
    safe_alter(con, "clients", "payment_status", "TEXT DEFAULT 'Unpaid'")
    safe_alter(con, "clients", "commitment_date", "DATE")
    safe_alter(con, "clients", "first_visit_date", "DATE")
    con.commit(); con.close()

def add_client(name, case_details, contact, agreed_fee, status, commitment_date, first_visit_date):
    con, cur = conn_cur()
    cur.execute("""INSERT INTO clients (name, case_details, contact, agreed_fee, payment_status, commitment_date, first_visit_date)
                   VALUES (?,?,?,?,?,?,?)""",
                (name, case_details, contact, agreed_fee, status, str(commitment_date) if commitment_date else None,
                 str(first_visit_date) if first_visit_date else None))
    con.commit(); con.close()

def update_client(cid, name, case_details, contact, agreed_fee, status, commitment_date, first_visit_date):
    con, cur = conn_cur()
    cur.execute("""UPDATE clients SET name=?, case_details=?, contact=?, agreed_fee=?, payment_status=?, commitment_date=?, first_visit_date=?
                   WHERE id=?""",
                (name, case_details, contact, agreed_fee, status,
                 str(commitment_date) if commitment_date else None,
                 str(first_visit_date) if first_visit_date else None, cid))
    con.commit(); con.close()

def delete_client(cid):
    con, cur = conn_cur()
    cur.execute("DELETE FROM clients WHERE id=?", (cid,))
    con.commit(); con.close()

def add_hearing(cid, hearing_date, note):
    con, cur = conn_cur()
    cur.execute("INSERT INTO hearings (client_id, hearing_date, note) VALUES (?,?,?)",
                (cid, str(hearing_date), note))
    con.commit(); con.close()

def add_payment(cid, pay_date, amount, mode, note):
    con, cur = conn_cur()
    cur.execute("INSERT INTO payments (client_id, pay_date, amount, mode, note) VALUES (?,?,?,?,?)",
                (cid, str(pay_date), amount, mode, note))
    con.commit(); con.close()

def df_clients():
    con, cur = conn_cur()
    df = pd.read_sql_query("SELECT * FROM clients ORDER BY name COLLATE NOCASE", con)
    con.close(); return df

def df_hearings():
    con, cur = conn_cur()
    df = pd.read_sql_query("""SELECT h.id, h.client_id, c.name, h.hearing_date, h.note
                              FROM hearings h JOIN clients c ON c.id=h.client_id
                              ORDER BY h.hearing_date ASC, c.name""", con)
    con.close(); return df

def df_payments():
    con, cur = conn_cur()
    df = pd.read_sql_query("""SELECT p.id, p.client_id, c.name, p.pay_date, p.amount, p.mode, p.note
                              FROM payments p JOIN clients c ON c.id=p.client_id
                              ORDER BY p.pay_date DESC""", con)
    con.close(); return df

def total_paid_for(cid):
    con, cur = conn_cur()
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE client_id=?", (cid,))
    val = cur.fetchone()[0] or 0
    con.close(); return float(val)

init_db()

# ---------------- Session: Login ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

USER, PASS = "amol", "amolsanap"

if not st.session_state.logged_in:
    with st.container():
        st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">🔐 Adv Amol Sanap Login</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Enter credentials to continue</div>', unsafe_allow_html=True)
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type="password", key="login_p")
        if st.button("Login", key="login_btn"):
            if u == USER and p == PASS:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid username or password")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ---------------- Main UI ----------------
st.title("⚖️ Advocate Client Desk")

clients = df_clients()
hearings = df_hearings()
payments = df_payments()

today = datetime.date.today()
tomorrow = today + datetime.timedelta(days=1)

# --- Top Alerts: Upcoming hearings in date order ---
if not hearings.empty:
    hearings['hearing_date'] = pd.to_datetime(hearings['hearing_date'], errors='coerce').dt.date
    upcoming = hearings[hearings['hearing_date'] >= today].sort_values(['hearing_date','name'])
    if not upcoming.empty:
        chips = []
        for _, r in upcoming.iterrows():
            d = r['hearing_date']
            if d == today:
                badge = '<span class="badge badge-today">Today</span>'
            elif d == tomorrow:
                badge = '<span class="badge badge-tomorrow">Tomorrow</span>'
            else:
                badge = f'<span class="badge">{d.strftime("%d-%b-%Y")}</span>'
            chips.append(
                f'''<span class="alert-chip">
                        {badge}
                        <span>{r["name"]}</span>
                        <span style="color:#666">— {(r["note"] or "").strip()[:40]}</span>
                    </span>'''
            )
        html = '<div class="alerts-stick">📅 Upcoming Hearings: ' + "".join(chips[:30]) + "</div>"
        st.markdown(html, unsafe_allow_html=True)

# ---- Add Client ----
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 👤 Add New Client")
    c1, c2 = st.columns(2)
    with c1:
        c_name = st.text_input("Client Name", key="add_name")
        c_contact = st.text_input("Contact", key="add_contact")
        c_fee = st.number_input("Agreed Fee (₹)", min_value=0.0, step=500.0, key="add_fee")
        c_first = st.date_input("First Visit Date", key="add_first", value=today)
    with c2:
        c_case = st.text_input("Case Details", key="add_case")
        c_status = st.selectbox("Payment Status", ["Unpaid", "Paid"], key="add_status")
        c_commit = st.date_input("Payment Commitment Date", key="add_commit")
    if st.button("➕ Add Client", key="add_client_btn"):
        if c_name and c_case:
            add_client(c_name, c_case, c_contact, c_fee, c_status, c_commit, c_first)
            st.success(f"Client '{c_name}' added.")
            st.rerun()
        else:
            st.error("Please fill Name and Case Details.")
    st.markdown('</div>', unsafe_allow_html=True)

# ---- Modify Client ----
if not clients.empty:
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ✏️ Modify Client")
        sel_name = st.selectbox("Select Client", options=clients['name'].tolist(), key="mod_select")
        row = clients[clients['name'] == sel_name].iloc[0]
        def safe_iso(d):
            try:
                return datetime.date.fromisoformat(d) if d else None
            except Exception:
                return None
        m1, m2 = st.columns(2)
        with m1:
            e_name = st.text_input("Client Name", value=row.get('name') or "", key="edit_name")
            e_contact = st.text_input("Contact", value=row.get('contact') or "", key="edit_contact")
            e_fee = st.number_input("Agreed Fee (₹)", min_value=0.0, step=500.0, value=float(row.get('agreed_fee') or 0), key="edit_fee")
            e_first = st.date_input("First Visit Date", value=safe_iso(row.get('first_visit_date')) or today, key="edit_first")
        with m2:
            e_case = st.text_input("Case Details", value=row.get('case_details') or "", key="edit_case")
            e_status = st.selectbox("Payment Status", ["Unpaid","Paid"], index=0 if (row.get('payment_status') or "Unpaid")=="Unpaid" else 1, key="edit_status")
            e_commit = st.date_input("Payment Commitment Date", value=safe_iso(row.get('commitment_date')) or today, key="edit_commit")
        colb1, colb2 = st.columns([1,1])
        with colb1:
            if st.button("💾 Save Changes", key="save_client"):
                update_client(int(row['id']), e_name, e_case, e_contact, e_fee, e_status, e_commit, e_first)
                st.success("Updated successfully.")
                st.rerun()
        with colb2:
            if st.button("🗑 Delete Client", key="del_client"):
                delete_client(int(row['id']))
                st.success("Client deleted.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ---- Hearings: Add + History ----
if not clients.empty:
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🧾 Hearings")
        h_client = st.selectbox("Client", options=clients['name'].tolist(), key="hear_client")
        h_cid = int(clients[clients['name']==h_client]['id'].iloc[0])
        hc1, hc2 = st.columns(2)
        with hc1:
            h_date = st.date_input("Hearing Date", key="hear_date")
        with hc2:
            h_note = st.text_input("Note (Court/Stage/etc.)", key="hear_note")
        if st.button("➕ Add Hearing", key="add_hear_btn"):
            add_hearing(h_cid, h_date, h_note)
            st.success("Hearing added.")
            st.rerun()

        # Hearing history
        hdf = df_hearings()
        if not hdf.empty:
            st.markdown("**Hearing History (all clients)**")
            hd = hdf.copy()
            hd['hearing_date'] = pd.to_datetime(hd['hearing_date'], errors='coerce').dt.strftime("%d-%b-%Y")
            st.dataframe(hd[['name','hearing_date','note']].rename(columns={'name':'Client','hearing_date':'Date','note':'Note'}), use_container_width=True)
        else:
            st.info("No hearings recorded yet.")
        st.markdown('</div>', unsafe_allow_html=True)

# ---- Payments: Part Payments + Summary ----
if not clients.empty:
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 💸 Payments")
        p_client = st.selectbox("Client", options=clients['name'].tolist(), key="pay_client")
        p_cid = int(clients[clients['name']==p_client]['id'].iloc[0])
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            p_date = st.date_input("Payment Date", key="pay_date", value= today)
        with pc2:
            p_amount = st.number_input("Amount (₹)", min_value=0.0, step=500.0, key="pay_amount")
        with pc3:
            p_mode = st.selectbox("Mode", ["Cash","UPI","Bank","Cheque","Other"], key="pay_mode")
        p_note = st.text_input("Note (optional)", key="pay_note")

        if st.button("➕ Add Part Payment", key="add_pay_btn"):
            if p_amount > 0:
                add_payment(p_cid, p_date, p_amount, p_mode, p_note)
                st.success("Payment added.")
                st.rerun()
            else:
                st.error("Amount must be greater than 0.")

        pays = df_payments()
        if not pays.empty:
            st.markdown("**Payment History (all clients)**")
            pdv = pays.copy()
            pdv['pay_date'] = pd.to_datetime(pdv['pay_date'], errors='coerce').dt.strftime("%d-%b-%Y")
            st.dataframe(
                pdv[['name','pay_date','amount','mode','note']].rename(
                    columns={'name':'Client','pay_date':'Date','amount':'Amount (₹)','mode':'Mode','note':'Note'}
                ),
                use_container_width=True
            )
        else:
            st.info("No payments recorded yet.")

        # Summary for selected client
        sel_row = clients[clients['name']==p_client].iloc[0]
        agreed = float(sel_row.get('agreed_fee') or 0)
        paid = total_paid_for(int(sel_row['id']))
        pending = max(0.0, agreed - paid)
        b1, b2, b3 = st.columns(3)
        with b1: st.markdown(f"**Agreed Fee:** ₹{agreed:,.0f}")
        with b2: st.markdown(f"**Total Paid:** ₹{paid:,.0f}")
        with b3: st.markdown(f"**Pending:** ₹{pending:,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)

# ---- Clients Master Table ----
if not clients.empty:
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📋 Clients")
        show = clients.copy()
        show['Agreed Fee (₹)'] = show['agreed_fee']
        show['Commitment'] = show['commitment_date']
        show['Status'] = show['payment_status']
        show['First Visit'] = show['first_visit_date']
        show = show[['name','case_details','contact','First Visit','Agreed Fee (₹)','Status','Commitment']].rename(
            columns={'name':'Client','case_details':'Case','contact':'Contact'}
        )
        st.dataframe(show, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ---- PDF Export (well-arranged client database) ----
def build_pdf():
    # gather fresh data
    cdf = df_clients()
    hdf = df_hearings()
    pdf = BytesIO()
    doc = SimpleDocTemplate(pdf, pagesize=A4, leftMargin=24, rightMargin=24, topMargin=36, bottomMargin=24)
    styles = getSampleStyleSheet()
    Story = []

    # Title
    Story.append(Paragraph("Advocate Client Database", styles['Title']))
    Story.append(Paragraph(f"Generated: {datetime.datetime.now().strftime('%d-%b-%Y %H:%M')}", styles['Normal']))
    Story.append(Spacer(1, 12))

    # Overall table (brief)
    if not cdf.empty:
        brief = [["Client","Case","Contact","First Visit","Agreed Fee","Status","Commitment"]]
        for _, r in cdf.sort_values("name").iterrows():
            brief.append([
                r.get("name",""),
                r.get("case_details",""),
                r.get("contact",""),
                (r.get("first_visit_date") or "")[:10],
                f"₹{float(r.get('agreed_fee') or 0):,.0f}",
                r.get("payment_status",""),
                (r.get("commitment_date") or "")[:10],
            ])
        t = Table(brief, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('GRID',(0,0),(-1,-1),0.25,colors.grey),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.whitesmoke, colors.lightgrey]),
        ]))
        Story.append(t)
        Story.append(PageBreak())

    # Per-client sections
    for _, r in cdf.sort_values("name").iterrows():
        cid = int(r["id"])
        Story.append(Paragraph(f"Client: {r.get('name','')}", styles['Heading2']))
        Story.append(Paragraph(f"Case: {r.get('case_details','')}", styles['Normal']))
        Story.append(Paragraph(f"Contact: {r.get('contact','')}", styles['Normal']))
        Story.append(Paragraph(f"First Visit: {(r.get('first_visit_date') or '')[:10]}", styles['Normal']))
        Story.append(Paragraph(f"Agreed Fee: ₹{float(r.get('agreed_fee') or 0):,.0f} | Status: {r.get('payment_status','')} | Commitment: {(r.get('commitment_date') or '')[:10]}", styles['Normal']))
        Story.append(Spacer(1, 8))

        # Hearings for this client
        ch = hdf[hdf["client_id"]==cid].copy()
        Story.append(Paragraph("Hearings", styles['Heading3']))
        if ch.empty:
            Story.append(Paragraph("— No hearings recorded —", styles['Italic']))
        else:
            ch['hearing_date'] = pd.to_datetime(ch['hearing_date'], errors='coerce').dt.strftime("%d-%b-%Y")
            htbl = [["Date","Note"]]+ ch[['hearing_date','note']].fillna("").values.tolist()
            t2 = Table(htbl, repeatRows=1, colWidths=[90, 380])
            t2.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('GRID',(0,0),(-1,-1),0.25,colors.grey),
            ]))
            Story.append(t2)

        Story.append(Spacer(1, 8))

        # Payments for this client
        con, cur = conn_cur()
        pdf_pay = pd.read_sql_query("""SELECT pay_date, amount, mode, note
                                       FROM payments WHERE client_id=?
                                       ORDER BY pay_date DESC""", con, params=(cid,))
        con.close()
        Story.append(Paragraph("Payments", styles['Heading3']))
        if pdf_pay.empty:
            Story.append(Paragraph("— No payments recorded —", styles['Italic']))
        else:
            pdf_pay['pay_date'] = pd.to_datetime(pdf_pay['pay_date'], errors='coerce').dt.strftime("%d-%b-%Y")
            ptab = [["Date","Amount","Mode","Note"]] + [
                [d, f"₹{float(a):,.0f}", m or "", n or ""] for d,a,m,n in pdf_pay.values
            ]
            t3 = Table(ptab, repeatRows=1, colWidths=[90, 80, 80, 220])
            t3.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('GRID',(0,0),(-1,-1),0.25,colors.grey),
            ]))
            Story.append(t3)

        Story.append(Spacer(1, 16))
        Story.append(PageBreak())

    doc.build(Story)
    pdf.seek(0)
    return pdf

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 🖨️ Export")
if st.button("Generate PDF (All Clients)", key="gen_pdf"):
    pdf_bytes = build_pdf().read()
    st.download_button(
        label="⬇️ Download Client Database PDF",
        data=pdf_bytes,
        file_name=f"client_database_{datetime.date.today().isoformat()}.pdf",
        mime="application/pdf",
    )
st.markdown('</div>', unsafe_allow_html=True)

# ---- Logout ----
if st.button("🚪 Logout", key="logout"):
    st.session_state.logged_in = False
    st.rerun()

