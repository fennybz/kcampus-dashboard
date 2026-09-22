"""
Persistent data layer using Supabase (cloud PostgreSQL).
Stores all accumulated sales data + upload history logs.
Falls back to SQLite if Supabase is not configured.
"""

import pandas as pd
import os
import streamlit as st
from datetime import datetime

# ── Supabase connection ──────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")

_sb = None

def _get_sb():
    global _sb
    if _sb is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _sb


def init_db():
    """No-op for Supabase (tables created via SQL editor)."""
    pass


def get_upload_history():
    sb = _get_sb()
    if not sb:
        return pd.DataFrame()
    resp = sb.table("uploads").select("*").order("uploaded_at", desc=True).execute()
    if not resp.data:
        return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    if "is_active" in df.columns:
        df["status"] = df["is_active"].map({True: "ACTIVE", False: "INACTIVE"})
    # Split date_range into date_min/date_max for app compatibility
    if "date_range" in df.columns:
        parts = df["date_range"].str.split(" to ", expand=True)
        df["date_min"] = parts[0] if parts.shape[1] > 0 else ""
        df["date_max"] = parts[1] if parts.shape[1] > 1 else df["date_min"]
    else:
        df["date_min"] = ""
        df["date_max"] = ""
    # Compute net_sales/total_units from sales data if not stored on uploads
    if "net_sales" not in df.columns or df["net_sales"].isna().all():
        df["net_sales"] = 0.0
        df["gross_sales"] = 0.0
        df["total_units"] = 0
        for i, row in df.iterrows():
            sales_resp = sb.table("sales").select("net_sales, gross_sales, primary_units, row_type").eq(
                "upload_id", row["id"]).execute()
            if sales_resp.data:
                sdf = pd.DataFrame(sales_resp.data)
                df.at[i, "net_sales"] = sdf["net_sales"].sum()
                df.at[i, "gross_sales"] = sdf["gross_sales"].sum()
                primary = sdf[sdf["row_type"] == "Primary"] if "row_type" in sdf.columns else sdf
                df.at[i, "total_units"] = int(primary["primary_units"].sum())
    for col, default in [("net_sales", 0.0), ("gross_sales", 0.0), ("total_units", 0)]:
        if col not in df.columns:
            df[col] = default
    return df


def check_duplicate(date_min, date_max, filename):
    sb = _get_sb()
    if not sb:
        return None
    dr = f"{date_min} to {date_max}"
    resp = sb.table("uploads").select("id, filename, uploaded_at").eq(
        "date_range", dr).eq("is_active", True).execute()
    if resp.data:
        r = resp.data[0]
        return (r["id"], r["filename"], r["uploaded_at"])
    return None


def insert_upload(filename, rows_df):
    sb = _get_sb()
    if not sb:
        return None

    date_min = rows_df["sales_date"].min()
    date_max = rows_df["sales_date"].max()
    row_count = len(rows_df)

    resp = sb.table("uploads").insert({
        "filename": filename,
        "uploaded_at": datetime.now().isoformat(),
        "row_count": row_count,
        "date_range": f"{date_min} to {date_max}",
        "is_active": True,
    }).execute()

    upload_id = resp.data[0]["id"]

    # Insert sales in batches
    sale_cols = ["sales_date", "day_of_week", "outlet", "menu_category", "product",
                 "row_type", "primary_units", "raw_quantity", "unit_price",
                 "gross_sales", "discount", "net_sales", "modifier_selections"]
    batch = []
    for _, r in rows_df.iterrows():
        row = {"upload_id": upload_id, "filename": filename,
               "uploaded_at": datetime.now().isoformat()}
        for c in sale_cols:
            val = r.get(c, None) if c in rows_df.columns else None
            if pd.isna(val):
                val = None
            elif isinstance(val, float):
                val = round(val, 4)
            row[c] = val
        batch.append(row)
        if len(batch) >= 200:
            sb.table("sales").insert(batch).execute()
            batch = []
    if batch:
        sb.table("sales").insert(batch).execute()

    return upload_id


def deactivate_upload(upload_id):
    sb = _get_sb()
    if not sb:
        return
    sb.table("uploads").update({"is_active": False}).eq("id", upload_id).execute()
    sb.table("sales").delete().eq("upload_id", upload_id).execute()


def get_all_sales():
    sb = _get_sb()
    if not sb:
        return pd.DataFrame()

    # Get active upload IDs
    uploads = sb.table("uploads").select("id").eq("is_active", True).execute()
    if not uploads.data:
        return pd.DataFrame()
    active_ids = [u["id"] for u in uploads.data]

    # Fetch sales for active uploads (Supabase limits to 1000 per request)
    all_rows = []
    for uid in active_ids:
        offset = 0
        while True:
            resp = sb.table("sales").select("*").eq("upload_id", uid).order(
                "sales_date").range(offset, offset + 999).execute()
            if not resp.data:
                break
            all_rows.extend(resp.data)
            if len(resp.data) < 1000:
                break
            offset += 1000

    if not all_rows:
        return pd.DataFrame()
    return pd.DataFrame(all_rows)


def seed_from_xlsm(xlsm_path):
    """One-time seed from the Restaurant_Sales_Dashboard.xlsm."""
    sb = _get_sb()
    if not sb:
        return False
    # Check if already seeded
    resp = sb.table("uploads").select("id", count="exact").execute()
    if resp.count and resp.count > 0:
        return False

    df = pd.read_excel(xlsm_path, sheet_name="Sales Detail")
    if df.empty:
        return False

    rows = pd.DataFrame()
    rows["sales_date"] = pd.to_datetime(df["Sales Date"]).dt.strftime("%Y-%m-%d")
    rows["day_of_week"] = pd.to_datetime(df["Sales Date"]).dt.day_name()
    rows["outlet"] = df["Outlet"]
    rows["menu_category"] = df.get("Menu Category", "")
    rows["product"] = df["Product"]
    rows["row_type"] = df.get("Row Type", "Primary")
    rows["raw_quantity"] = pd.to_numeric(df.get("Raw Quantity", 0), errors="coerce").fillna(0)
    rows["primary_units"] = pd.to_numeric(df.get("Primary Units", 0), errors="coerce").fillna(0)
    rows["modifier_selections"] = pd.to_numeric(df.get("Modifier Selections", 0), errors="coerce").fillna(0)
    rows["unit_price"] = pd.to_numeric(df.get("Unit / Increment Price", 0), errors="coerce").fillna(0)
    rows["gross_sales"] = pd.to_numeric(df.get("Gross Sales", 0), errors="coerce").fillna(0)
    rows["discount"] = pd.to_numeric(df.get("Discount", 0), errors="coerce").fillna(0)
    rows["net_sales"] = pd.to_numeric(df.get("Net Sales", 0), errors="coerce").fillna(0)

    source_file = df["Source File"].iloc[0] if "Source File" in df.columns else "initial_seed.xlsm"
    insert_upload(str(source_file), rows)
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
            "menu_category": "",
            "product": item,
            "row_type": "Primary",
            "raw_quantity": qty,
            "primary_units": qty,
            "modifier_selections": 0,
            "unit_price": unit_price,
            "gross_sales": total,
            "discount": total - net if total > net else 0,
            "net_sales": net,
        })

    return pd.DataFrame(rows)
