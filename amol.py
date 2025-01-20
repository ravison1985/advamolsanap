import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# Initialize SQLite database
# Initialize SQLite database
conn = sqlite3.connect("case1_records.db")
cursor = conn.cursor()

# Create cases table if not exists
cursor.execute('''CREATE TABLE IF NOT EXISTS cases (
    sr_no INTEGER PRIMARY KEY,
    next_date TEXT,
    court TEXT,
    case_no TEXT UNIQUE,
    client_name TEXT,
    name TEXT,
    file_no TEXT,
    stage TEXT,
    fee REAL DEFAULT 0,
    advance REAL DEFAULT 0
)''')


# Create payments table if not exists
cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY,
    case_no TEXT,
    payment_amount REAL,
    payment_date TEXT,
    FOREIGN KEY (case_no) REFERENCES cases(case_no)
)''')

conn.commit()

# Function to load data from the database
def load_data():
    query = "SELECT * FROM cases"
    return pd.read_sql_query(query, conn)

# Function to insert or update data in the database
def upsert_case(case, payments=None):
    case = (
        int(case[0]),  # sr_no must be an integer
        str(case[1]),  # next_date must be a string (YYYY-MM-DD)
        str(case[2]),  # court must be a string
        str(case[3]),  # case_no must be a string
        str(case[4]),  # client_name must be a string
        str(case[5]),  # name must be a string
        str(case[6]),  # file_no must be a string
        str(case[7]),  # stage must be a string
        float(case[8]),  # fee must be a float
        float(case[9]),  # advance must be a float
    )
    cursor.execute('''
    INSERT INTO cases (sr_no, next_date, court, case_no, client_name, name, file_no, stage, fee, advance)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(case_no) DO UPDATE SET
        next_date=excluded.next_date,
        court=excluded.court,
        client_name=excluded.client_name,
        name=excluded.name,
        file_no=excluded.file_no,
        stage=excluded.stage,
        fee=excluded.fee,
        advance=excluded.advance
    ''', case)

    if payments:
        for payment in payments:
            payment = (
                str(payment[0]),  # case_no
                float(payment[1]),  # payment_amount
                str(payment[2]),  # payment_date in YYYY-MM-DD format
            )
            cursor.execute('''
            INSERT INTO payments (case_no, payment_amount, payment_date)
            VALUES (?, ?, ?)
            ''', payment)
    
    conn.commit()


# Function to update advance payment
def update_advance(case_no, new_advance):
    cursor.execute('''
    UPDATE cases
    SET advance = ?
    WHERE case_no = ?
    ''', (new_advance, case_no))
    conn.commit()

# Load data
data = load_data()

# Tabs in the main page
tabs = st.tabs(["1. Create New Case", "2. Update Case", "3. Show Database", "4. Alerts", "5. Calculator", "6. Client Fee Management", "7. Graphs of Database"])

# Tab 1: Create New Case
with tabs[0]:
    st.title("Create New Case")
    new_case = {
        "sr_no": len(data) + 1,
        "next_date": st.date_input("Next Date for New Case", value=datetime.today()).strftime("%Y-%m-%d"),
        "court": st.text_input("Court"),
        "case_no": st.text_input("Case No."),
        "client_name": st.text_input("Client Name"),
        "name": st.text_input("Role (Plaintiff/Defendant)"),
        "file_no": st.text_input("File No."),
        "stage": st.text_input("Stage for New Case"),
        "fee": st.number_input("Total Fee", min_value=0.0, step=0.01),
        "advance": st.number_input("Advance Paid", min_value=0.0, step=0.01),
    }

    if st.button("Add Case"):
        if all(new_case.values()):
            new_case_tuple = (
                new_case["sr_no"],
                new_case["next_date"],
                new_case["court"],
                new_case["case_no"],
                new_case["client_name"],
                new_case["name"],
                new_case["file_no"],
                new_case["stage"],
                new_case["fee"],
                new_case["advance"]
            )
            upsert_case(new_case_tuple)
            st.success("New case added successfully!")
            data = load_data()  # Reload data
        else:
            st.error("Please fill in all fields before adding a case.")

# Tab 2: Update Case
# Tab 2: Update Case
with tabs[1]:
    st.title("Update Case Details")
    if not data.empty:
        case_no = st.selectbox("Select Case No.", data["case_no"].unique())
        selected_case = data[data["case_no"] == case_no]

        if not selected_case.empty:
            selected_case = selected_case.iloc[0]

            next_date = st.date_input("Next Date", value=datetime.strptime(selected_case["next_date"], "%Y-%m-%d").date())
            stage = st.text_input("Stage", value=selected_case["stage"])

            # Fee field is now read-only (frozen)
            st.text_input("Total Fee", value=str(selected_case["fee"]), disabled=True)

            # Ensure that the 'advance' is treated as a float (REAL type)
            advance = st.number_input("Advance Paid", value=selected_case["advance"], min_value=0.0, step=0.01)

            # Update Case
            if st.button("Update Case"):
                updated_case = (
                    selected_case["sr_no"],  # sr_no stays the same
                    next_date.strftime("%Y-%m-%d"),  # Ensure the date is in string format
                    selected_case["court"],  # court stays the same
                    case_no,  # case_no stays the same
                    selected_case["client_name"],  # client_name stays the same
                    selected_case["name"],  # name stays the same
                    selected_case["file_no"],  # file_no stays the same
                    stage,  # updated stage
                    float(selected_case["fee"]),  # Fee is kept the same as a float
                    float(advance)  # Ensure advance is a float (REAL type)
                )
                upsert_case(updated_case)
                st.success(f"Case {case_no} updated successfully!")
                data = load_data()  # Reload data
    else:
        st.warning("No data available to update.")



# Tab 3: Show Database
with tabs[2]:
    st.title("Case Records")
    st.dataframe(data)

# Tab 4: Alerts
with tabs[3]:
    st.title("Upcoming Case Alerts")
    today = datetime.today()
    three_days_from_now = today + timedelta(days=3)
    alerts = data[data["next_date"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d")) <= three_days_from_now]
    alerts = alerts[alerts["next_date"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d")) >= today]

    if not alerts.empty:
        st.warning("The following cases have a next date within the next 3 days:")
        st.dataframe(alerts)
    else:
        st.success("No upcoming cases within the next 3 days.")

# Tab 5: Calculator
with tabs[4]:
    st.title("Fee Calculator")
    st.subheader("Calculate Fees")
    case_no = st.text_input("Enter Case No. to calculate fee")
    if case_no:
        selected_case = data[data["case_no"] == case_no]
        if not selected_case.empty:
            selected_case = selected_case.iloc[0]
            total_fee = selected_case["fee"]
            advance_paid = selected_case["advance"]
            pending_fee = total_fee - advance_paid
            st.write(f"**Total Fee:** {total_fee}")
            st.write(f"**Advance Paid:** {advance_paid}")
            st.write(f"**Pending Fee:** {pending_fee}")
        else:
            st.error(f"No case found for Case No. {case_no}.")
    else:
        st.write("Enter the case number to calculate the fee.")

# Tab 6: Client Fee Management
with tabs[5]:
    st.title("Client Fee Management")
    if not data.empty:
        client_name = st.selectbox("Select Client Name", data["client_name"].unique())
        client_data = data[data["client_name"] == client_name]

        if not client_data.empty:
            st.write(client_data[["case_no", "fee", "advance"]])
            total_fee = client_data["fee"].sum()
            total_advance = client_data["advance"].sum()
            pending_fee = total_fee - total_advance

            st.write(f"**Total Fee:** {total_fee}")
            st.write(f"**Advance Paid:** {total_advance}")
            st.write(f"**Pending Fee:** {pending_fee}")

            # Partial payment section
            st.subheader("Add Partial Payment")
            case_no = st.selectbox("Select Case No. for Payment", client_data["case_no"].unique())
            selected_case = client_data[client_data["case_no"] == case_no].iloc[0]
            current_advance = selected_case["advance"]
            additional_payment = st.number_input("Additional Payment", min_value=0.0, step=0.01)

            if st.button("Update Payment"):
                new_advance = current_advance + additional_payment
                update_advance(case_no, new_advance)
                st.success(f"Payment updated! New advance for case {case_no}: {new_advance}")
                data = load_data()  # Reload data to reflect changes
        else:
            st.warning("No cases found for the selected client.")
    else:
        st.warning("No data available.")

import matplotlib.pyplot as plt

with tabs[6]:
    st.title("Graphs of Database")
    
    if not data.empty:
        # Case Count by Court
        st.subheader("Case Count by Court")
        court_counts = data["court"].value_counts()
        fig, ax = plt.subplots()
        ax.pie(court_counts, labels=court_counts.index, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures that pie chart is drawn as a circle.
        st.pyplot(fig)

        # Fee Summary
        st.subheader("Fee Summary")
        fee_summary = data[["fee", "advance"]].sum()
        fig, ax = plt.subplots()
        ax.pie(fee_summary, labels=fee_summary.index, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')
        st.pyplot(fig)

    else:
        st.warning("No data available for graphs.")

