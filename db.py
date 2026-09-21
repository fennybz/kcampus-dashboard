"""
Persistent data layer using SQLite.
Stores all accumulated sales data + upload history logs.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "kcampus.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            week_start TEXT,
            week_end TEXT,
            date_min TEXT,
            date_max TEXT,
            row_count INTEGER,
            net_sales REAL,
            gross_sales REAL,
            total_units INTEGER,
            status TEXT DEFAULT 'ACTIVE',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER NOT NULL,
            sales_date TEXT,
            day_of_week TEXT,
            outlet TEXT,
            channel TEXT,
            menu_category TEXT,
            product TEXT,
            modifier_group TEXT,
            modifier_selection TEXT,
            row_type TEXT,
            raw_quantity REAL,
            primary_units REAL,
            modifier_selections REAL,
            unit_price REAL,
            gross_sales REAL,
            discount REAL,
            net_sales REAL,
            modifier_class TEXT,
            FOREIGN KEY (upload_id) REFERENCES uploads(id)
        );

        CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sales_date);
        CREATE INDEX IF NOT EXISTS idx_sales_outlet ON sales(outlet);
        CREATE INDEX IF NOT EXISTS idx_sales_upload ON sales(upload_id);
    """)
    conn.close()


def get_upload_history():
    """Return all upload logs as a DataFrame."""
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM uploads ORDER BY uploaded_at DESC", conn)
    conn.close()
    return df


def check_duplicate(date_min, date_max, filename):
    """Check if this date range + filename was already uploaded."""
    conn = get_conn()
    cur = conn.execute(
        "SELECT id, filename, uploaded_at FROM uploads WHERE date_min=? AND date_max=? AND status='ACTIVE'",
        (date_min, date_max)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return row  # (id, filename, uploaded_at)
    return None


def insert_upload(filename, rows_df):
    """Insert an upload record and all its sales rows. Returns upload_id."""
    conn = get_conn()

    date_min = rows_df["sales_date"].min()
    date_max = rows_df["sales_date"].max()
    row_count = len(rows_df)
    net_sales = rows_df["net_sales"].sum()
    gross_sales = rows_df["gross_sales"].sum()
    total_units = int(rows_df.loc[rows_df["row_type"] == "Primary", "primary_units"].sum())

    cur = conn.execute(
        """INSERT INTO uploads (filename, uploaded_at, week_start, week_end, date_min, date_max,
           row_count, net_sales, gross_sales, total_units, status, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', '')""",
        (filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         date_min, date_max, date_min, date_max,
         row_count, net_sales, gross_sales, total_units)
    )
    upload_id = cur.lastrowid

    # Insert sales rows
    rows_df["upload_id"] = upload_id
    cols = ["upload_id", "sales_date", "day_of_week", "outlet", "channel", "menu_category",
            "product", "modifier_group", "modifier_selection", "row_type",
            "raw_quantity", "primary_units", "modifier_selections",
            "unit_price", "gross_sales", "discount", "net_sales", "modifier_class"]
    for c in cols:
        if c not in rows_df.columns:
            rows_df[c] = None
    rows_df[cols].to_sql("sales", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()
    return upload_id


def deactivate_upload(upload_id):
    """Soft-delete an upload batch (mark as INACTIVE)."""
    conn = get_conn()
    conn.execute("UPDATE uploads SET status='INACTIVE' WHERE id=?", (upload_id,))
    conn.execute("DELETE FROM sales WHERE upload_id=?", (upload_id,))
    conn.commit()
    conn.close()


def get_all_sales():
    """Return all active sales data."""
    conn = get_conn()
    df = pd.read_sql("""
        SELECT s.*, u.filename, u.uploaded_at, u.status as batch_status
        FROM sales s
        JOIN uploads u ON s.upload_id = u.id
        WHERE u.status = 'ACTIVE'
        ORDER BY s.sales_date
    """, conn)
    conn.close()
    return df


def seed_from_xlsm(xlsm_path):
    """One-time seed: import data from the existing Restaurant_Sales_Dashboard.xlsm."""
    conn = get_conn()
    # Check if already seeded
    cur = conn.execute("SELECT COUNT(*) FROM uploads")
    if cur.fetchone()[0] > 0:
        conn.close()
        return False  # Already has data

    df = pd.read_excel(xlsm_path, sheet_name="Sales Detail")
    if df.empty:
        conn.close()
        return False

    # Normalize column names
    rows = pd.DataFrame()
    rows["sales_date"] = pd.to_datetime(df["Sales Date"]).dt.strftime("%Y-%m-%d")
    rows["day_of_week"] = pd.to_datetime(df["Sales Date"]).dt.day_name()
    rows["outlet"] = df["Outlet"]
    rows["channel"] = df.get("Channel", "")
    rows["menu_category"] = df.get("Menu Category", "")
    rows["product"] = df["Product"]
    rows["modifier_group"] = df.get("Modifier Group", "")
    rows["modifier_selection"] = df.get("Modifier Selection", "")
    rows["row_type"] = df.get("Row Type", "Primary")
    rows["raw_quantity"] = pd.to_numeric(df.get("Raw Quantity", 0), errors="coerce").fillna(0)
    rows["primary_units"] = pd.to_numeric(df.get("Primary Units", 0), errors="coerce").fillna(0)
    rows["modifier_selections"] = pd.to_numeric(df.get("Modifier Selections", 0), errors="coerce").fillna(0)
    rows["unit_price"] = pd.to_numeric(df.get("Unit / Increment Price", 0), errors="coerce").fillna(0)
    rows["gross_sales"] = pd.to_numeric(df.get("Gross Sales", 0), errors="coerce").fillna(0)
    rows["discount"] = pd.to_numeric(df.get("Discount", 0), errors="coerce").fillna(0)
    rows["net_sales"] = pd.to_numeric(df.get("Net Sales", 0), errors="coerce").fillna(0)
    rows["modifier_class"] = df.get("Modifier Class", "")

    source_file = df["Source File"].iloc[0] if "Source File" in df.columns else "initial_seed.xlsm"
    insert_upload(str(source_file), rows)
    conn.close()
    return True


def parse_campus_excel(uploaded_file, filename):
    """Parse the weekly campus Excel format into normalized rows."""
    df = pd.read_excel(uploaded_file, header=None)
    rows = []

    for _, row in df.iterrows():
        date_val = row.iloc[0]
        if not isinstance(date_val, (datetime, pd.Timestamp)):
            continue

        dt = pd.Timestamp(date_val)
        location = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
        item = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
        qty = float(row.iloc[8]) if pd.notna(row.iloc[8]) else 0
        unit_price = float(row.iloc[10]) if pd.notna(row.iloc[10]) else 0
        total = float(row.iloc[11]) if pd.notna(row.iloc[11]) else 0
        tax = float(row.iloc[12]) if pd.notna(row.iloc[12]) else 0
        net = float(row.iloc[13]) if pd.notna(row.iloc[13]) else total

        if not item or qty == 0:
            continue

        rows.append({
            "sales_date": dt.strftime("%Y-%m-%d"),
            "day_of_week": dt.strftime("%A"),
            "outlet": location,
            "channel": "Vending" if location != "Kalachandji's" else "Main Outlet",
            "menu_category": "",
            "product": item,
            "modifier_group": "",
            "modifier_selection": "",
            "row_type": "Primary",
            "raw_quantity": qty,
            "primary_units": qty,
            "modifier_selections": 0,
            "unit_price": unit_price,
            "gross_sales": total,
            "discount": total - net if total > net else 0,
            "net_sales": net,
            "modifier_class": "",
        })

    return pd.DataFrame(rows)
